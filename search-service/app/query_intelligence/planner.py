"""Central Query Intelligence planner: the only place that sequences
normalize -> intent -> entities -> route -> dates -> constraints ->
ambiguity -> SearchPlan. Structured fields on CanonicalQueryInput ALWAYS
take precedence over anything inferred from free text -- a parser guess
never overwrites an explicit caller-supplied value."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from ..domain import ALLOWED_VERTICALS
from . import ambiguity as amb
from . import constraints, dates, entities, intent, route
from .models import (
    CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM,
    STATUS_AMBIGUOUS, STATUS_INVALID, STATUS_UNSUPPORTED, STATUS_VALID,
    Ambiguity, CanonicalQueryInput, DateRange, Party, PLANNER_VERSION, ResolvedEntity, SearchPlan,
)
from .normalizer import normalize_query


def _entity_from_dict(e: dict) -> ResolvedEntity:
    return ResolvedEntity(id=e["id"], title=e["title"], type=e["type"], code=e.get("code"))


def _resolve_explicit_location(raw: str) -> ResolvedEntity:
    matches = entities.resolve_locations(raw)
    if len(matches) == 1:
        return _entity_from_dict(matches[0])
    return ResolvedEntity(id="", title=raw, type="free_text")   # explicit input, kept verbatim -- never dropped


def plan_query(data: CanonicalQueryInput, *, today: date | None = None) -> SearchPlan:
    query_id = data.correlation_id or str(uuid.uuid4())
    today = today or datetime.now(timezone.utc).date()

    original_text = data.text or ""
    normalized_text = normalize_query(original_text)
    truncated = len(original_text) > 300

    ambiguities: list[Ambiguity] = []
    unsupported_constraints: list[str] = []

    # ---- intent ----
    if data.vertical:
        intents: tuple[str, ...] = (data.vertical,)
    else:
        intents = intent.detect_supported_intents(normalized_text)
    unsupported_intents = () if data.vertical else intent.detect_unsupported_intents(normalized_text)

    multi_intent = len(intents) > 1
    vertical = intents[0] if len(intents) == 1 else None

    # ---- locations ----
    origin: ResolvedEntity | None = None
    destination: ResolvedEntity | None = None
    if data.origin:
        origin = _resolve_explicit_location(data.origin)
    if data.destination:
        destination = _resolve_explicit_location(data.destination)

    if origin is None and destination is None and vertical:
        if vertical in route.ROUTE_VERTICALS:
            inferred = route.infer_route(normalized_text)
            if inferred["origin"] and inferred["destination"]:
                origin = _entity_from_dict(inferred["origin"])
                destination = _entity_from_dict(inferred["destination"])
            elif inferred["ambiguous"]:
                ambiguities.append(Ambiguity(inferred["reason"], amb.MESSAGES.get(inferred["reason"], inferred["reason"])))
        else:
            found = entities.resolve_locations(normalized_text)
            if len(found) == 1:
                destination = _entity_from_dict(found[0])
            elif len(found) > 1:
                ambiguities.append(Ambiguity(amb.AMBIGUOUS_MULTIPLE_DESTINATIONS, amb.MESSAGES[amb.AMBIGUOUS_MULTIPLE_DESTINATIONS]))

    # ---- dates ----
    if data.start_date:
        date_range = DateRange(start_date=data.start_date, end_date=data.end_date or data.start_date, source="explicit")
    else:
        date_range = dates.resolve_relative_date(normalized_text, today) or dates.resolve_explicit_date(normalized_text) or DateRange()
        # A night count ("سه شب") only refines an already-resolved single-day
        # start date into a stay window; it never invents a start date.
        nights = constraints.extract_nights(normalized_text)
        if nights and date_range.start_date and date_range.end_date == date_range.start_date:
            end = date.fromisoformat(date_range.start_date) + timedelta(days=nights)
            date_range = DateRange(start_date=date_range.start_date, end_date=end.isoformat(), source=date_range.source)
        elif nights and not date_range.start_date:
            # a night count with no resolvable start date is never used to
            # invent one -- surfaced instead of silently dropped
            unsupported_constraints.append("duration_without_start_date")

    # ---- party ----
    travellers = data.passengers if data.passengers is not None else constraints.extract_travellers(normalized_text)
    rooms = data.rooms if data.rooms is not None else constraints.extract_rooms(normalized_text)
    party = Party(travellers=travellers, rooms=rooms)

    # ---- filters ----
    inferred_filters, inferred_unsupported = constraints.extract_filters_and_unsupported(normalized_text)
    filters = {**inferred_filters, **(data.filters or {})}   # explicit filters win over inferred ones
    unsupported_constraints.extend(inferred_unsupported)

    # ---- status / ambiguity assembly ----
    if not original_text.strip() and not (data.vertical or data.origin or data.destination):
        status = STATUS_INVALID
        ambiguities.append(Ambiguity(amb.EMPTY_QUERY, amb.MESSAGES[amb.EMPTY_QUERY]))
    elif data.vertical and data.vertical not in ALLOWED_VERTICALS:
        status = STATUS_UNSUPPORTED
        ambiguities.append(Ambiguity(amb.UNSUPPORTED_INTENT, amb.MESSAGES[amb.UNSUPPORTED_INTENT]))
    elif multi_intent:
        status = STATUS_UNSUPPORTED
        ambiguities.append(Ambiguity(amb.UNSUPPORTED_COMBINED_REQUEST, amb.MESSAGES[amb.UNSUPPORTED_COMBINED_REQUEST]))
    elif vertical is None and unsupported_intents:
        status = STATUS_UNSUPPORTED
        ambiguities.append(Ambiguity(amb.UNSUPPORTED_INTENT, amb.MESSAGES[amb.UNSUPPORTED_INTENT]))
    elif vertical is None:
        status = STATUS_AMBIGUOUS
        ambiguities.append(Ambiguity(amb.NO_INTENT_DETECTED, amb.MESSAGES[amb.NO_INTENT_DETECTED]))
    elif ambiguities:
        status = STATUS_AMBIGUOUS
    else:
        status = STATUS_VALID

    if status == STATUS_VALID and unsupported_constraints:
        confidence = CONFIDENCE_MEDIUM
    elif status == STATUS_VALID:
        confidence = CONFIDENCE_HIGH
    else:
        confidence = CONFIDENCE_LOW

    return SearchPlan(
        query_id=query_id, original_text=original_text, normalized_text=normalized_text,
        intent=intents, vertical=vertical, multi_intent=multi_intent,
        origin=origin, destination=destination, date_range=date_range, party=party,
        filters=filters, unsupported_constraints=tuple(unsupported_constraints),
        public=data.public, tenant_ref=data.tenant_ref, confidence=confidence, status=status,
        ambiguities=tuple(ambiguities), planner_version=PLANNER_VERSION, correlation_id=query_id,
    )
