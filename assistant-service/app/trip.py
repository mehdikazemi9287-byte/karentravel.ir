"""Trip State domain object + deterministic booking-readiness evaluator +
LEVEL_1 booking-DRAFT creation. No provider call, no payment, no PNR, no
reservation hold -- this module can only ever produce a local, reversible
draft row. Nothing here calls out to any external system."""
from __future__ import annotations

import hashlib
import json
import uuid

from . import db

STATUS_DRAFT = "DRAFT"
STATUS_PLANNING = "PLANNING"
STATUS_SHORTLIST_READY = "SHORTLIST_READY"
STATUS_SELECTION_READY = "SELECTION_READY"
STATUS_READY_FOR_BOOKING_PREP = "READY_FOR_BOOKING_PREP"
STATUS_TRAVELLER_INFO_NEEDED = "TRAVELLER_INFO_NEEDED"
STATUS_BOOKING_PREPARED = "BOOKING_PREPARED"
STATUS_APPROVAL_NEEDED = "APPROVAL_NEEDED"
STATUS_RESERVATION_PENDING = "RESERVATION_PENDING"
STATUS_BOOKED = "BOOKED"
STATUS_DISRUPTED = "DISRUPTED"
STATUS_COMPLETED = "COMPLETED"
STATUS_CANCELLED = "CANCELLED"

# Phase 3 sec 9: a validated state machine -- impossible transitions are
# rejected rather than silently allowed. Every state can reach CANCELLED;
# every state except the two terminal ones can be marked DISRUPTED.
_TERMINAL = {STATUS_COMPLETED, STATUS_CANCELLED}
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STATUS_DRAFT: {STATUS_PLANNING},
    STATUS_PLANNING: {STATUS_SHORTLIST_READY, STATUS_SELECTION_READY, STATUS_READY_FOR_BOOKING_PREP},
    STATUS_SHORTLIST_READY: {STATUS_SELECTION_READY},
    STATUS_SELECTION_READY: {STATUS_READY_FOR_BOOKING_PREP, STATUS_PLANNING},   # re-selection after revalidation
    STATUS_READY_FOR_BOOKING_PREP: {STATUS_TRAVELLER_INFO_NEEDED, STATUS_BOOKING_PREPARED, STATUS_APPROVAL_NEEDED, STATUS_PLANNING},
    STATUS_TRAVELLER_INFO_NEEDED: {STATUS_READY_FOR_BOOKING_PREP, STATUS_BOOKING_PREPARED},
    STATUS_BOOKING_PREPARED: {STATUS_APPROVAL_NEEDED, STATUS_PLANNING},
    STATUS_APPROVAL_NEEDED: {STATUS_RESERVATION_PENDING, STATUS_BOOKING_PREPARED},
    STATUS_RESERVATION_PENDING: {STATUS_BOOKED, STATUS_DISRUPTED},
    STATUS_BOOKED: {STATUS_COMPLETED, STATUS_DISRUPTED},
    STATUS_DISRUPTED: {STATUS_PLANNING, STATUS_CANCELLED},
}
for _s in list(ALLOWED_TRANSITIONS) + [STATUS_COMPLETED]:
    if _s not in _TERMINAL:
        ALLOWED_TRANSITIONS.setdefault(_s, set()).add(STATUS_CANCELLED)


class InvalidTransition(Exception):
    pass


def transition(trip_state_id: str, current_status: str, new_status: str) -> str:
    """Validated status change. Raises InvalidTransition rather than
    silently allowing an impossible jump (e.g. DRAFT -> BOOKED). Setting the
    same status again is always a safe no-op (idempotent), not a transition."""
    if new_status == current_status:
        return current_status
    if current_status in _TERMINAL:
        raise InvalidTransition(f"{current_status} is terminal, cannot transition to {new_status}")
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise InvalidTransition(f"{current_status} -> {new_status} is not an allowed transition")
    db.conn().execute("UPDATE trip_states SET status = %s, updated_at = now() WHERE id = %s", (new_status, trip_state_id))
    return new_status


def get_or_create(conversation_id: str, existing_trip_state_id: str | None) -> dict:
    c = db.conn()
    if existing_trip_state_id:
        row = c.execute("SELECT id, status FROM trip_states WHERE id = %s", (existing_trip_state_id,)).fetchone()
        if row:
            return {"id": str(row[0]), "status": row[1]}
    new_id = str(uuid.uuid4())
    c.execute("INSERT INTO trip_states (id, conversation_id, status) VALUES (%s,%s,%s)",
              (new_id, conversation_id, STATUS_DRAFT))
    return {"id": new_id, "status": STATUS_DRAFT}


def update_from_selection(trip_state_id: str, vertical: str, selected_item: dict) -> None:
    """Records the selection as the trip's selected_transport (route
    verticals) or selected_accommodation (hotel/accommodation/vacation_rental).
    Never a reservation -- purely local state."""
    field = "selected_transport" if vertical in ("flight", "train", "bus") else "selected_accommodation"
    row = db.conn().execute("SELECT status FROM trip_states WHERE id = %s", (trip_state_id,)).fetchone()
    current = row[0] if row else STATUS_DRAFT
    db.conn().execute(f"UPDATE trip_states SET {field} = %s, updated_at = now() WHERE id = %s",
                       (json.dumps(selected_item, ensure_ascii=False), trip_state_id))
    # A re-selection after booking prep already started returns the trip to
    # PLANNING (a fresh selection invalidates whatever was prepared for the
    # old one) -- reachable per ALLOWED_TRANSITIONS; DRAFT/PLANNING move
    # forward to PLANNING normally.
    target = STATUS_PLANNING
    try:
        transition(trip_state_id, current, target)
    except InvalidTransition:
        pass   # already at/past PLANNING via a path that doesn't loop back -- selection itself still recorded above


def evaluate_readiness(vertical: str, selected_item: dict | None, party: dict | None) -> dict:
    """Deterministic. Never implies provider availability beyond what
    Search already returned for the selected item."""
    missing: list[str] = []
    warnings: list[str] = []
    if not selected_item:
        missing.append("selected_offer")
    if vertical in ("flight", "train", "bus"):
        if not party or not party.get("travellers"):
            missing.append("passenger_count")
        warnings.append("passenger_identity_documents_not_collected")
    elif vertical in ("hotel", "accommodation", "vacation_rental"):
        if not party or not party.get("rooms"):
            missing.append("room_count")
        if not party or not party.get("travellers"):
            missing.append("guest_count")
    else:
        warnings.append(f"readiness_rules_not_defined_for_vertical:{vertical}")
    return {"ready": not missing, "missing": missing, "warnings": warnings}


def create_booking_draft(trip_state_id: str, vertical: str, selected_item: dict, missing_fields: list[str]) -> dict:
    """LEVEL_1 / DRAFT only. Idempotent: a repeated prep request for the
    same (trip_state_id, offer) returns the existing draft instead of
    creating a duplicate."""
    idem_key = hashlib.sha256(
        json.dumps({"offer_id": selected_item.get("offer_id"), "entity_id": selected_item.get("entity_id")},
                   sort_keys=True).encode()
    ).hexdigest()[:24]
    c = db.conn()
    row = c.execute("SELECT id, status FROM booking_drafts WHERE trip_state_id = %s AND idempotency_key = %s",
                     (trip_state_id, idem_key)).fetchone()
    if row:
        return {"id": str(row[0]), "status": row[1], "duplicate": True}
    new_id = str(uuid.uuid4())
    c.execute(
        """INSERT INTO booking_drafts
           (id, trip_state_id, vertical, selected_offer_ref, missing_fields, status, idempotency_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (new_id, trip_state_id, vertical, json.dumps(selected_item, ensure_ascii=False),
         json.dumps(missing_fields, ensure_ascii=False), STATUS_DRAFT, idem_key),
    )
    current = c.execute("SELECT status FROM trip_states WHERE id = %s", (trip_state_id,)).fetchone()
    current_status = current[0] if current else STATUS_PLANNING
    target = STATUS_READY_FOR_BOOKING_PREP if not missing_fields else STATUS_TRAVELLER_INFO_NEEDED
    try:
        transition(trip_state_id, current_status, target)
    except InvalidTransition:
        pass
    return {"id": new_id, "status": STATUS_DRAFT, "duplicate": False}
