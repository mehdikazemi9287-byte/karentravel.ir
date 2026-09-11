"""Central Query Intelligence planner: the only place that sequences
normalize -> intent -> entities -> route -> dates -> constraints ->
ambiguity -> SearchPlan. Structured fields on CanonicalQueryInput ALWAYS
take precedence over anything inferred from free text -- a parser guess
never overwrites an explicit caller-supplied value.

Phase 5 (Search Intelligence) adds: trip-type/round-trip inference, weekday
departure+return pairs, adults/children breakdown, cabin class, nearby/sort
hints, a captured (not searched) intermediate stop, and explicit/inferred/
unresolved field provenance for explainability. None of this changes the
Phase 4 execution contract (main.py still reads date_range/party/filters
exactly as before) -- new fields are additive."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from ..domain import ALLOWED_VERTICALS
from . import ambiguity as amb
from . import constraints, dates, entities, intent, route
from .models import (
    CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM,
    STATUS_AMBIGUOUS, STATUS_INVALID, STATUS_UNSUPPORTED, STATUS_VALID,
    TRIP_ONE_WAY, TRIP_ROUND_TRIP, TRIP_UNSPECIFIED,
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

    ambiguities: list[Ambiguity] = []
    unsupported_constraints: list[str] = []
    inferred_fields: list[str] = []
    explicit_fields: list[str] = []
    unresolved_fields: list[str] = []

    # ---- intent ----
    if data.vertical:
        intents: tuple[str, ...] = (data.vertical,)
        explicit_fields.append("vertical")
    else:
        intents = intent.detect_supported_intents(normalized_text)
        if intents:
            inferred_fields.append("vertical")
    unsupported_intents = () if data.vertical else intent.detect_unsupported_intents(normalized_text)

    multi_intent = len(intents) > 1
    vertical = intents[0] if len(intents) == 1 else None
    if vertical is None and not data.vertical:
        unresolved_fields.append("vertical")

    # ---- locations ----
    origin: ResolvedEntity | None = None
    destination: ResolvedEntity | None = None
    intermediate_stops: tuple[ResolvedEntity, ...] = ()
    if data.origin:
        origin = _resolve_explicit_location(data.origin)
        explicit_fields.append("origin")
    if data.destination:
        destination = _resolve_explicit_location(data.destination)
        explicit_fields.append("destination")

    if origin is None and destination is None and vertical:
        if vertical in route.ROUTE_VERTICALS:
            inferred = route.infer_route(normalized_text)
            if inferred["origin"] and inferred["destination"]:
                origin = _entity_from_dict(inferred["origin"])
                destination = _entity_from_dict(inferred["destination"])
                inferred_fields += ["origin", "destination"]
                if inferred["intermediate_stops"]:
                    intermediate_stops = tuple(_entity_from_dict(e) for e in inferred["intermediate_stops"])
                    inferred_fields.append("intermediate_stops")
                    unsupported_constraints.append(amb.MULTI_LEG_ROUTE_NOT_SEARCHABLE)
            elif inferred["ambiguous"]:
                ambiguities.append(Ambiguity(inferred["reason"], amb.MESSAGES.get(inferred["reason"], inferred["reason"])))
                unresolved_fields += ["origin", "destination"]
        else:
            found = entities.resolve_locations(normalized_text)
            if len(found) == 1:
                destination = _entity_from_dict(found[0])
                inferred_fields.append("destination")
            elif len(found) > 1:
                ambiguities.append(Ambiguity(amb.AMBIGUOUS_MULTIPLE_DESTINATIONS, amb.MESSAGES[amb.AMBIGUOUS_MULTIPLE_DESTINATIONS]))
                unresolved_fields.append("destination")

    # ---- dates: departure/return, explicit fields win, weekday pairs
    # detected before falling back to a single relative/explicit date ----
    departure_date: str | None = None
    return_date: str | None = None
    date_source = "none"
    if data.start_date:
        departure_date = data.start_date
        date_source = "explicit"
        explicit_fields.append("departure_date")
        if data.end_date:
            return_date = data.end_date
            explicit_fields.append("return_date")
    else:
        weekday_dates = dates.find_weekday_dates(normalized_text, today)
        if len(weekday_dates) >= 2:
            departure_date, return_date = weekday_dates[0], weekday_dates[1]
            date_source = "relative"
            inferred_fields += ["departure_date", "return_date"]
        else:
            resolved = dates.resolve_relative_date(normalized_text, today) or dates.resolve_explicit_date(normalized_text)
            if resolved and resolved.start_date:
                departure_date = resolved.start_date
                date_source = resolved.source
                inferred_fields.append("departure_date")

    nights = constraints.extract_nights(normalized_text)
    if nights and departure_date and not return_date:
        return_date = (date.fromisoformat(departure_date) + timedelta(days=nights)).isoformat()
        inferred_fields.append("nights")
    elif nights and not departure_date:
        # a night count with no resolvable start date is never used to
        # invent one -- surfaced instead of silently dropped
        unsupported_constraints.append("duration_without_start_date")
    elif not departure_date:
        unresolved_fields.append("departure_date")

    date_range = DateRange(start_date=departure_date, end_date=return_date or departure_date, source=date_source)

    # ---- trip type: explicit phrase/field wins; two dates -> round trip;
    # a single date on a route vertical is a normal one-way default, but the
    # ambiguity is still recorded (a "soft" ambiguity -- see amb.HARD_AMBIGUITY_CODES) ----
    if data.trip_type:
        trip_type = data.trip_type
        explicit_fields.append("trip_type")
    else:
        phrase_trip_type = constraints.extract_trip_type(normalized_text)
        if phrase_trip_type:
            trip_type = phrase_trip_type
            inferred_fields.append("trip_type")
        elif return_date:
            trip_type = TRIP_ROUND_TRIP
            inferred_fields.append("trip_type")
        elif vertical in route.ROUTE_VERTICALS and departure_date:
            trip_type = TRIP_UNSPECIFIED
            ambiguities.append(Ambiguity(amb.RETURN_DATE_UNSPECIFIED, amb.MESSAGES[amb.RETURN_DATE_UNSPECIFIED]))
        else:
            trip_type = TRIP_UNSPECIFIED

    # ---- party ----
    travellers = data.passengers if data.passengers is not None else constraints.extract_travellers(normalized_text)
    if data.passengers is not None:
        explicit_fields.append("passengers")
    elif travellers is not None:
        inferred_fields.append("passengers")

    children = data.children if data.children is not None else constraints.extract_children(normalized_text)
    adults = data.adults
    if adults is None and travellers is not None:
        adults = travellers - children if children else travellers
    if data.adults is not None:
        explicit_fields.append("adults")

    rooms = data.rooms if data.rooms is not None else constraints.extract_rooms(normalized_text)
    if data.rooms is not None:
        explicit_fields.append("rooms")
    elif rooms is not None:
        inferred_fields.append("rooms")

    quantity = data.quantity
    party = Party(travellers=travellers, adults=adults, children=children,
                  infants=data.infants, rooms=rooms, quantity=quantity)

    # ---- cabin ----
    cabin = data.cabin or constraints.extract_cabin(normalized_text)
    if data.cabin:
        explicit_fields.append("cabin")
    elif cabin:
        inferred_fields.append("cabin")

    # ---- filters / budget / sort / nearby ----
    inferred_filters, inferred_unsupported = constraints.extract_filters_and_unsupported(normalized_text)
    filters = {**inferred_filters, **(data.filters or {})}   # explicit filters win over inferred ones
    unsupported_constraints.extend(inferred_unsupported)

    budget_max = data.budget_max if data.budget_max is not None else filters.get("max_price")
    if data.budget_max is not None:
        explicit_fields.append("budget_max")
    elif budget_max is not None:
        inferred_fields.append("budget_max")
    budget_min = data.budget_min
    if budget_min is not None:
        explicit_fields.append("budget_min")

    sort = data.sort or constraints.extract_sort_hint(normalized_text) or "recommended"
    if data.sort:
        explicit_fields.append("sort")
    elif sort != "recommended":
        inferred_fields.append("sort")

    flexibility = data.flexibility or "exact"
    if data.flexibility:
        explicit_fields.append("flexibility")

    nearby_allowed = constraints.extract_nearby_allowed(normalized_text)
    if nearby_allowed:
        inferred_fields.append("nearby_allowed")

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
    elif any(a.code in amb.HARD_AMBIGUITY_CODES for a in ambiguities):
        status = STATUS_AMBIGUOUS
    else:
        status = STATUS_VALID

    if status == STATUS_VALID and (unsupported_constraints or any(a.code not in amb.HARD_AMBIGUITY_CODES for a in ambiguities)):
        confidence = CONFIDENCE_MEDIUM
    elif status == STATUS_VALID:
        confidence = CONFIDENCE_HIGH
    else:
        confidence = CONFIDENCE_LOW

    return SearchPlan(
        query_id=query_id, original_text=original_text, normalized_text=normalized_text,
        intent=intents, vertical=vertical, multi_intent=multi_intent,
        origin=origin, destination=destination, intermediate_stops=intermediate_stops,
        date_range=date_range, departure_date=departure_date, return_date=return_date,
        nights=nights, trip_type=trip_type, party=party, cabin=cabin,
        budget_min=budget_min, budget_max=budget_max, currency=data.currency,
        filters=filters, sort=sort, flexibility=flexibility, nearby_allowed=nearby_allowed,
        unsupported_constraints=tuple(unsupported_constraints),
        inferred_fields=tuple(inferred_fields), explicit_fields=tuple(explicit_fields),
        unresolved_fields=tuple(unresolved_fields),
        public=data.public, tenant_ref=data.tenant_ref, confidence=confidence, status=status,
        ambiguities=tuple(ambiguities), locale=data.locale,
        planner_version=PLANNER_VERSION, correlation_id=query_id,
    )
