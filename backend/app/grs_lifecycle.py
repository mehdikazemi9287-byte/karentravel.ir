"""
GRS booking lifecycle orchestration - Reserve/Book/Modify/Cancel, built entirely
on KarenSeir's EXISTING primitives:
  - Reservation ("draft" status IS the booking intent; provider_reference holds
    the GRS confirmation_code) + BOOKING_TRANSITIONS + transition_reservation()
  - IdempotencyKey (reused as-is - no parallel idempotency mechanism)
  - OutboxEvent (already written by transition_reservation() for every change)
  - PriceCheck (reused as the revalidation snapshot mechanism)
  - ProviderReconciliationCase (the one new table - ambiguous outcomes only)

No real network call is possible in this environment (no GRS credential), so
every test exercises this module with a FakeTransport-backed GRSAdapter,
exactly like the adapter-core tests. No Reserve/Book/Modify/Cancel has ever
been sent to a real endpoint.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .grs_contract import map_grs_event_to_internal_transition

# Categories where a POST outcome is genuinely UNKNOWN (never observed a clean
# accept/reject from the provider) - these must open a reconciliation case,
# never be treated as a definitive failure. Distinct from "retryable": a 429/5xx
# on reserve/book/modify/cancel is correctly never blindly retried, but it is
# still ambiguous, not a clean rejection.
_AMBIGUOUS_ERROR_CATEGORIES = {
    "provider_timeout", "provider_unavailable", "provider_rate_limited",
    "provider_protocol_error", "provider_result_unknown",
}
from .operations import (
    Reservation, BOOKING_TRANSITIONS, transition_reservation,
    IdempotencyKey, ProviderReconciliationCase,
)
from .providers import ProviderContext
from .security import role_has_permission


class GRSLifecycleError(RuntimeError):
    pass


class GRSPermissionError(GRSLifecycleError):
    pass


def _authorize(actor, reservation: Reservation, permission: str) -> None:
    """Real tenant-ownership + RBAC enforcement for every GRS lifecycle
    mutation. `actor` is duck-typed (id/tenant_id/role) to avoid importing the
    User model here (would create a circular import with app.main) - reuses
    the EXISTING role_has_permission()/ROLE_PERMISSIONS table, no parallel
    permission system. confirmation_code/reservation_id alone is never enough
    - the actor must belong to the reservation's own tenant AND hold the
    permission."""
    if actor.tenant_id != reservation.tenant_id:
        raise GRSPermissionError("actor does not belong to this reservation's tenant")
    if not role_has_permission(actor.role, permission):
        raise GRSPermissionError(f"role '{actor.role}' lacks permission '{permission}'")


def _idempotent_guard(db: Session, *, tenant_id: int, scope: str, key: str, request_hash: str) -> Optional[dict]:
    """Returns the stored response if this exact (scope, key) already ran -
    mirrors the pattern transition_reservation()/save_search() already use."""
    prior = db.scalar(select(IdempotencyKey).where(
        IdempotencyKey.tenant_id == tenant_id, IdempotencyKey.scope == scope, IdempotencyKey.key == key,
    ))
    if prior is None:
        return None
    if prior.request_hash != request_hash:
        raise GRSLifecycleError(f"idempotency key '{key}' reused for a different request")
    return json.loads(prior.response_json) if prior.response_json else {}


def _record_idempotency(db: Session, *, tenant_id: int, scope: str, key: str, request_hash: str, response: dict) -> None:
    db.add(IdempotencyKey(tenant_id=tenant_id, scope=scope, key=key, request_hash=request_hash, response_json=json.dumps(response, ensure_ascii=False)))


def open_reconciliation_case(
    db: Session, *, tenant_id: int, reservation_id: Optional[str], operation: str, reason: str,
    expected_state: Optional[str] = None, observed_state: Optional[str] = None,
) -> ProviderReconciliationCase:
    case = ProviderReconciliationCase(
        tenant_id=tenant_id, provider_key="grs", reservation_id=reservation_id, operation=operation,
        reason=reason, expected_state=expected_state, observed_state=observed_state,
        status="manual_review_required",
    )
    db.add(case)
    db.flush()
    return case


@dataclass(frozen=True)
class GRSReserveOutcome:
    ok: bool
    reservation: Reservation
    provider_confirmation_code: Optional[str]
    reconciliation_case: Optional[ProviderReconciliationCase]
    detail: str


def reserve_with_grs(
    db: Session, *, reservation: Reservation, adapter, reserve_payload: Mapping[str, Any], command_id: str, actor,
) -> GRSReserveOutcome:
    """Calls GRS reserve for an existing draft/pending Reservation. Never
    guesses on ambiguous outcomes - opens a reconciliation case instead."""
    _authorize(actor, reservation, "reservation:create")
    request_hash = json.dumps(dict(reserve_payload), sort_keys=True)
    cached = _idempotent_guard(db, tenant_id=reservation.tenant_id, scope="grs.reserve", key=command_id, request_hash=request_hash)
    if cached is not None:
        return GRSReserveOutcome(ok=cached.get("ok", False), reservation=reservation,
                                  provider_confirmation_code=cached.get("confirmation_code"),
                                  reconciliation_case=None, detail="idempotent replay")

    if reservation.status not in {"draft", "pending"}:
        raise GRSLifecycleError(f"cannot reserve from status '{reservation.status}'")

    if reservation.status == "draft":
        transition_reservation(db, reservation, "pending", actor_id=actor.id, command_id=f"{command_id}:to-pending")

    context = ProviderContext(tenant_id=reservation.tenant_id, correlation_id=str(uuid.uuid4()), idempotency_key=command_id)
    result = adapter.execute("reserve", reserve_payload, context)

    if not result.get("ok"):
        error = result.get("error", {})
        if error.get("code") in _AMBIGUOUS_ERROR_CATEGORIES:
            case = open_reconciliation_case(db, tenant_id=reservation.tenant_id, reservation_id=reservation.id,
                                             operation="reserve", reason=f"ambiguous outcome, never guessed: {error.get('code')}")
            _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.reserve", key=command_id, request_hash=request_hash, response={"ok": False})
            return GRSReserveOutcome(ok=False, reservation=reservation, provider_confirmation_code=None, reconciliation_case=case, detail=error.get("code", "unknown"))
        transition_reservation(db, reservation, "failed", actor_id=actor.id, command_id=f"{command_id}:failed")
        _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.reserve", key=command_id, request_hash=request_hash, response={"ok": False})
        return GRSReserveOutcome(ok=False, reservation=reservation, provider_confirmation_code=None, reconciliation_case=None, detail=error.get("code", "unknown"))

    value = result.get("value") or {}
    reserve_value = value.get("reserve", value)
    grs_state = str(reserve_value.get("state", ""))
    grs_status = str(reserve_value.get("status", ""))
    confirmation_code = reserve_value.get("confirmation_code")

    decision = map_grs_event_to_internal_transition(reservation.status, grs_state, grs_status)
    reservation.provider_reference = confirmation_code
    if decision.target_status is not None:
        transition_reservation(db, reservation, decision.target_status, actor_id=actor.id, command_id=f"{command_id}:{decision.target_status}")
    elif decision.requires_backoffice_review:
        open_reconciliation_case(db, tenant_id=reservation.tenant_id, reservation_id=reservation.id, operation="reserve",
                                  reason=decision.reason, observed_state=grs_status)

    response = {"ok": True, "confirmation_code": confirmation_code, "grs_status": grs_status}
    _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.reserve", key=command_id, request_hash=request_hash, response=response)
    return GRSReserveOutcome(ok=True, reservation=reservation, provider_confirmation_code=confirmation_code, reconciliation_case=None, detail=decision.reason)


def book_with_grs(db: Session, *, reservation: Reservation, adapter, command_id: str, payment_or_credit_confirmed: bool, actor) -> GRSReserveOutcome:
    """Calls GRS book. Per the explicit rule, this function REQUIRES the
    caller to prove payment/credit was independently confirmed - a Reserve
    response or a provider 'booked'/'definite' signal is never sufficient on
    its own, and this function will refuse to proceed without that proof."""
    _authorize(actor, reservation, "reservation:manage")
    if not payment_or_credit_confirmed:
        raise GRSLifecycleError("book_with_grs refused: payment/credit confirmation was not proven by the caller")
    if not reservation.provider_reference:
        raise GRSLifecycleError("cannot book: no provider_reference (confirmation_code) stored on this reservation")

    request_hash = reservation.provider_reference
    cached = _idempotent_guard(db, tenant_id=reservation.tenant_id, scope="grs.book", key=command_id, request_hash=request_hash)
    if cached is not None:
        return GRSReserveOutcome(ok=cached.get("ok", False), reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=None, detail="idempotent replay")
    if reservation.status not in {"awaiting_payment", "reserved"}:
        raise GRSLifecycleError(f"cannot book from status '{reservation.status}'")

    # No pre-transition here: payment_or_credit_confirmed is already an
    # independently-proven precondition (checked above), so there is nothing
    # to "await" - reserved -> confirmed is a direct, legal BOOKING_TRANSITIONS
    # edge, and inventing an intermediate awaiting_payment step here would
    # misrepresent a payment that is already settled.
    context = ProviderContext(tenant_id=reservation.tenant_id, correlation_id=str(uuid.uuid4()), idempotency_key=command_id)
    result = adapter.execute("book", {"confirmation_code": reservation.provider_reference}, context)

    if not result.get("ok"):
        error = result.get("error", {})
        case = open_reconciliation_case(db, tenant_id=reservation.tenant_id, reservation_id=reservation.id, operation="book",
                                         reason=f"book failed or ambiguous: {error.get('code')}")
        _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.book", key=command_id, request_hash=request_hash, response={"ok": False})
        return GRSReserveOutcome(ok=False, reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=case, detail=error.get("code", "unknown"))

    value = result.get("value") or {}
    reserve_value = value.get("reserve", value)
    grs_status = str(reserve_value.get("status", ""))
    if grs_status in {"booked", "definite"}:
        # Payment/credit already proven by the caller (checked above) - this IS
        # the one legitimate path to a confirmed transition.
        transition_reservation(db, reservation, "confirmed", actor_id=actor.id, command_id=f"{command_id}:confirmed")
        detail = "booked confirmed with independently-verified payment/credit"
    else:
        open_reconciliation_case(db, tenant_id=reservation.tenant_id, reservation_id=reservation.id, operation="book",
                                  reason=f"book call succeeded but provider status was '{grs_status}', not booked/definite", observed_state=grs_status)
        detail = f"unexpected post-book status '{grs_status}'"

    response = {"ok": True, "confirmation_code": reservation.provider_reference}
    _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.book", key=command_id, request_hash=request_hash, response=response)
    return GRSReserveOutcome(ok=True, reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=None, detail=detail)


def request_cancellation_with_grs(db: Session, *, reservation: Reservation, adapter, command_id: str, actor) -> GRSReserveOutcome:
    _authorize(actor, reservation, "reservation:manage")
    if not reservation.provider_reference:
        raise GRSLifecycleError("cannot cancel: no provider_reference stored")

    request_hash = reservation.provider_reference
    cached = _idempotent_guard(db, tenant_id=reservation.tenant_id, scope="grs.cancel", key=command_id, request_hash=request_hash)
    if cached is not None:
        return GRSReserveOutcome(ok=cached.get("ok", False), reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=None, detail="idempotent replay")
    if "cancel_requested" not in BOOKING_TRANSITIONS.get(reservation.status, set()):
        raise GRSLifecycleError(f"cannot request cancellation from status '{reservation.status}'")

    transition_reservation(db, reservation, "cancel_requested", actor_id=actor.id, command_id=f"{command_id}:cancel-requested")
    context = ProviderContext(tenant_id=reservation.tenant_id, correlation_id=str(uuid.uuid4()), idempotency_key=command_id)
    result = adapter.execute("request_cancellation", {"confirmation_code": reservation.provider_reference}, context)

    if not result.get("ok"):
        case = open_reconciliation_case(db, tenant_id=reservation.tenant_id, reservation_id=reservation.id, operation="cancel",
                                         reason=f"cancel request failed or ambiguous: {result.get('error', {}).get('code')}")
        _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.cancel", key=command_id, request_hash=request_hash, response={"ok": False})
        return GRSReserveOutcome(ok=False, reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=case, detail="cancel request not confirmed")

    # The reservation STAYS in cancel_requested here - actual cancellation
    # only becomes final via accept_cancellation_with_grs (a separate,
    # explicit step), matching the rule "canceling را canceled نشان نده".
    response = {"ok": True}
    _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.cancel", key=command_id, request_hash=request_hash, response=response)
    return GRSReserveOutcome(ok=True, reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=None, detail="cancellation requested, awaiting provider acceptance")


def accept_cancellation_with_grs(db: Session, *, reservation: Reservation, adapter, command_id: str, actor) -> GRSReserveOutcome:
    _authorize(actor, reservation, "reservation:manage")
    request_hash = reservation.provider_reference or ""
    cached = _idempotent_guard(db, tenant_id=reservation.tenant_id, scope="grs.accept_cancel", key=command_id, request_hash=request_hash)
    if cached is not None:
        return GRSReserveOutcome(ok=cached.get("ok", False), reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=None, detail="idempotent replay")
    if reservation.status != "cancel_requested":
        raise GRSLifecycleError(f"cannot accept cancellation from status '{reservation.status}'")

    context = ProviderContext(tenant_id=reservation.tenant_id, correlation_id=str(uuid.uuid4()), idempotency_key=command_id)
    result = adapter.execute("accept_cancellation", {"confirmation_code": reservation.provider_reference}, context)
    if not result.get("ok"):
        case = open_reconciliation_case(db, tenant_id=reservation.tenant_id, reservation_id=reservation.id, operation="accept_cancellation",
                                         reason=f"accept-cancel failed: {result.get('error', {}).get('code')}")
        _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.accept_cancel", key=command_id, request_hash=request_hash, response={"ok": False})
        return GRSReserveOutcome(ok=False, reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=case, detail="not cancelled")

    transition_reservation(db, reservation, "cancelled", actor_id=actor.id, command_id=f"{command_id}:cancelled")
    _record_idempotency(db, tenant_id=reservation.tenant_id, scope="grs.accept_cancel", key=command_id, request_hash=request_hash, response={"ok": True})
    return GRSReserveOutcome(ok=True, reservation=reservation, provider_confirmation_code=reservation.provider_reference, reconciliation_case=None, detail="cancellation final")
