"""
GRS (hotel provider) contract layer — AUDIT / SCAFFOLDING PHASE ONLY.

Nothing in this module calls the real GRS endpoint, writes to the database, or is
wired into any FastAPI route. It exists to make the documented contract (GRS Agency
API Document v1.18.4, primary; Postman Collection v1.17.0, secondary/example-only)
testable in isolation before any production wiring is authorized.

Design decisions this module encodes (see GRS_AUDIT_REPORT for full reasoning):
  - GRS's own reservation state/status is NEVER written directly into
    Reservation.status. KarenSeir's existing internal state machine
    (app/operations.py BOOKING_TRANSITIONS) is reused as-is - no parallel enum.
    map_grs_event_to_internal_transition() returns an existing BOOKING_TRANSITIONS
    target, or None when the GRS signal does not correspond to a safe forced
    transition (ambiguous/exception states are surfaced for BackOffice review
    instead of silently forced into the internal enum).
  - Money unit is never assumed. GRSConfig.validate() fails closed unless
    GRS_MONEY_UNIT is one of the explicit, confirmed values.
  - The envelope parser tolerates every known documented inconsistency (error vs
    errors, typo'd field names, HTTP 200 carrying a business error) without
    guessing at anything undocumented.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

# ---------------------------------------------------------------------------
# Reused, NOT reinvented: KarenSeir's own existing internal reservation states.
# Mirrors app/operations.py BOOKING_TRANSITIONS exactly (kept as a literal copy
# here, not an import, so this module stays independently unit-testable without
# a DB/app-context dependency during the audit phase; the real wiring phase
# must import the actual BOOKING_TRANSITIONS from app.operations instead of
# this copy, to guarantee zero drift).
# ---------------------------------------------------------------------------
KARENSEIR_BOOKING_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending", "failed", "expired"},
    "pending": {"reserved", "failed", "expired"},
    "reserved": {"awaiting_payment", "confirmed", "cancel_requested", "expired"},
    "awaiting_payment": {"confirmed", "failed", "expired", "cancel_requested"},
    "confirmed": {"issued", "change_requested", "cancel_requested", "refund_requested"},
    "issued": {"completed", "change_requested", "cancel_requested", "refund_requested"},
    "cancel_requested": {"cancelled", "confirmed"},
    "change_requested": {"changed", "confirmed"},
    "refund_requested": {"refunded", "confirmed"},
    "changed": {"issued", "completed"},
}


# ---------------------------------------------------------------------------
# 1. Config - fail closed, names harmonized with the existing {KEY}_PROVIDER_*
#    and provider-specific ({ZARINPAL_*}) conventions in app/providers.py.
# ---------------------------------------------------------------------------
GRS_ALLOWED_MONEY_UNITS = {"IRR", "IRT"}  # explicit allow-list; nothing implied


class GRSConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class GRSConfig:
    mode: str  # "disabled" | "sandbox" | "production" - mirrors ZARINPAL_MODE, not a boolean flag
    base_url: str
    client_token: str  # never logged; read from env/secret mount, never hardcoded
    connect_timeout_seconds: float
    read_timeout_seconds: float
    money_unit: str
    webhook_secret: str  # empty means webhook signature verification cannot run (see AUDIT finding)

    @classmethod
    def from_env(cls) -> "GRSConfig":
        return cls(
            mode=os.getenv("GRS_MODE", "disabled"),
            base_url=os.getenv("GRS_BASE_URL", ""),
            client_token=os.getenv("GRS_CLIENT_TOKEN", ""),
            connect_timeout_seconds=float(os.getenv("GRS_CONNECT_TIMEOUT_SECONDS", "5")),
            read_timeout_seconds=float(os.getenv("GRS_READ_TIMEOUT_SECONDS", "15")),
            money_unit=os.getenv("GRS_MONEY_UNIT", ""),
            webhook_secret=os.getenv("GRS_WEBHOOK_SECRET", ""),
        )

    def validate(self) -> None:
        if self.mode not in {"disabled", "sandbox", "production"}:
            raise GRSConfigError("grs: mode must be disabled, sandbox or production")
        if self.mode == "disabled":
            return
        if not self.base_url.startswith("https://"):
            raise GRSConfigError("grs: base_url must be explicit HTTPS")
        if not self.client_token:
            raise GRSConfigError("grs: client_token is required (Client-Token header is mandatory per v1.18.4)")
        if self.money_unit not in GRS_ALLOWED_MONEY_UNITS:
            raise GRSConfigError(
                f"grs: money_unit must be one of {sorted(GRS_ALLOWED_MONEY_UNITS)} and explicitly confirmed "
                "with the provider - the contract document does not state a unit, so nothing is assumed"
            )

    def can_accept_bookable_prices(self) -> bool:
        """Prices from GRS are usable for a real booking only once the adapter is
        actually enabled AND the money unit is explicitly configured and valid -
        never assumed IRR/IRT by default, and never true while disabled."""
        if self.mode not in {"sandbox", "production"}:
            return False
        try:
            self.validate()
        except GRSConfigError:
            return False
        return True


# ---------------------------------------------------------------------------
# 2. Envelope parsing - tolerant of every documented inconsistency, never of
#    anything undocumented (an unrecognized shape is a protocol error, not a
#    best-effort guess).
# ---------------------------------------------------------------------------
class GRSProtocolError(RuntimeError):
    """Raised when a GRS response does not match any documented envelope shape."""


@dataclass(frozen=True)
class GRSEnvelope:
    code: int
    message: str
    errors: list[dict[str, str]]  # normalized: always a list, even if the source had none/one/null
    value: Any
    raw_ok: bool  # True only if code indicates success AND errors is empty


def parse_grs_envelope(payload: Mapping[str, Any]) -> GRSEnvelope:
    if not isinstance(payload, Mapping) or "code" not in payload:
        raise GRSProtocolError("grs: response is not a recognized envelope shape (missing 'code')")
    code = payload.get("code")
    if not isinstance(code, int):
        raise GRSProtocolError("grs: envelope 'code' is not an integer")
    message = payload.get("message") or ""
    # Documented inconsistency: some responses use "error", some "errors"; either
    # may be null, a single object, or a list.
    raw_errors = payload.get("errors", payload.get("error"))
    if raw_errors is None:
        errors: list[dict[str, str]] = []
    elif isinstance(raw_errors, list):
        errors = [dict(item) for item in raw_errors if isinstance(item, Mapping)]
    elif isinstance(raw_errors, Mapping):
        errors = [dict(raw_errors)]
    else:
        raise GRSProtocolError("grs: envelope error/errors field is neither null, object, nor array")
    value = payload.get("value")
    raw_ok = code == 200 and not errors
    return GRSEnvelope(code=code, message=str(message), errors=errors, value=value, raw_ok=raw_ok)


# Business-error names that are documented as failures even under HTTP/code 200 -
# copied verbatim from the contract, matched case-insensitively against each
# error entry's "name" field.
GRS_BUSINESS_FAILURE_NAMES = {
    "inventory", "rate", "capacity", "stay",
}
GRS_BUSINESS_FAILURE_MESSAGE_MARKERS = (
    "reserve expired", "reserve not exists", "room closed",
    "inventory insufficient", "rate not valid", "room without rate",
)


def envelope_is_business_failure(envelope: GRSEnvelope) -> bool:
    """True for any of the documented 'looks like success, isn't' shapes: an
    HTTP/code-200 envelope carrying an inventory/rate/capacity/stay error, or a
    reserve payload whose state/status/message indicates rejection."""
    if envelope.errors:
        for err in envelope.errors:
            name = str(err.get("name", "")).strip().lower()
            message = str(err.get("message", "")).strip().lower()
            if name in GRS_BUSINESS_FAILURE_NAMES:
                return True
            if any(marker in message for marker in GRS_BUSINESS_FAILURE_MESSAGE_MARKERS):
                return True
    value = envelope.value
    if isinstance(value, Mapping):
        reserve = value.get("reserve", value)
        if isinstance(reserve, Mapping) and str(reserve.get("status", "")).strip().lower() == "rejected":
            return True
    return False


def normalize_reserve_details(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Tolerates the documented PDF typos (Status / Property_confirmation_code /
    total_canellation_fee) by reading either spelling, always writing the
    correct name into the returned dict. Never invents a field the source
    payload does not contain."""
    result = dict(raw)
    if "Status" in result and "status" not in result:
        result["status"] = result.pop("Status")
    if "Property_confirmation_code" in result and "property_confirmation_code" not in result:
        result["property_confirmation_code"] = result.pop("Property_confirmation_code")
    if "total_canellation_fee" in result and "total_cancellation_fee" not in result:
        result["total_cancellation_fee"] = result.pop("total_canellation_fee")
    return result


def normalize_rate_plan_price(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Tolerates the documented baby_cot_racke_rate typo."""
    result = dict(raw)
    if "baby_cot_racke_rate" in result and "baby_cot_rack_rate" not in result:
        result["baby_cot_rack_rate"] = result.pop("baby_cot_racke_rate")
    return result


def normalize_suggestion_room(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Tolerates the documented roome_type_extra typo (reads the provider's
    actual field name, exposes it under the correct internal name)."""
    result = dict(raw)
    if "roome_type_extra" in result and "room_type_extra" not in result:
        result["room_type_extra"] = result.pop("roome_type_extra")
    return result


# ---------------------------------------------------------------------------
# 3. Reservation status mapping - GRS's raw state/status is ALWAYS retained
#    separately (never discarded); this function only decides whether a given
#    GRS signal corresponds to one of KarenSeir's existing, already-approved
#    internal transitions. It never invents a new internal status name.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GRSTransitionDecision:
    target_status: Optional[str]  # a KARENSEIR_BOOKING_TRANSITIONS value, or None
    requires_backoffice_review: bool
    reason: str


def map_grs_event_to_internal_transition(
    current_internal_status: str, grs_state: str, grs_status: str
) -> GRSTransitionDecision:
    """
    current_internal_status: KarenSeir's own Reservation.status right now.
    grs_state / grs_status: GRS's own raw "state" ("online"/"offline") and
        "status" (pending/booking/booked/definite/rejected/suggested/
        modify_booking/modifying/modified/rejected_modify/overbooking/refund/
        canceling/canceled/cancellation_rejected) fields, stored verbatim
        elsewhere regardless of what this function returns.

    Returns a KARENSEIR_BOOKING_TRANSITIONS-legal target, or None when the GRS
    signal is ambiguous/exceptional and must go to BackOffice review instead of
    being force-mapped into an internal status that does not actually exist for
    it (e.g. "suggested", "overbooking" - these are not silently invented as new
    enum values, per the no-parallel-enum rule).
    """
    status = grs_status.strip().lower()
    allowed = KARENSEIR_BOOKING_TRANSITIONS.get(current_internal_status, set())

    def decide(target: str, reason: str) -> GRSTransitionDecision:
        if target not in allowed:
            return GRSTransitionDecision(
                target_status=None,
                requires_backoffice_review=True,
                reason=f"grs status '{status}' would map to '{target}', which is not a valid transition "
                f"from '{current_internal_status}' in KARENSEIR_BOOKING_TRANSITIONS - {reason} "
                "(rejected, not silently applied; recorded for BackOffice review)",
            )
        return GRSTransitionDecision(target_status=target, requires_backoffice_review=False, reason=reason)

    if status in {"pending", "booking"}:
        # A hold now exists at the provider - this is KarenSeir's own "reserved"
        # (a hold placed, not yet paid/confirmed), never "confirmed"/"issued".
        return decide("reserved", "provider hold acknowledged, not yet a confirmed booking")
    if status in {"booked", "definite"}:
        # Deliberately NOT auto-applied: per contract rule, "booked" must not be
        # treated as final without KarenSeir's own /v1/book confirmation, and
        # "definite" still requires KarenSeir's own payment/credit gate (see
        # AGENTS.md: price/availability/policy are never frontend-authoritative,
        # and Book must only follow a real verified payment/credit lock - not an
        # incoming provider signal alone). Surfaced for the caller (the real
        # booking flow, not this pure function) to decide once those internal
        # preconditions are independently verified.
        return GRSTransitionDecision(
            target_status=None,
            requires_backoffice_review=False,
            reason=f"grs status '{status}' observed - internal 'confirmed'/'issued' transition must be "
            "driven by KarenSeir's own payment/credit verification, never applied directly from this signal",
        )
    if status == "rejected":
        return decide("failed", "provider rejected the reservation")
    if status in {"canceling"}:
        return decide("cancel_requested", "provider cancellation in progress, not yet final")
    if status == "canceled":
        return decide("cancelled", "provider confirms cancellation is final")
    if status == "cancellation_rejected":
        return GRSTransitionDecision(
            target_status=None, requires_backoffice_review=True,
            reason="provider rejected a cancellation request - reservation must remain in its prior "
            "confirmed/issued state, needs explicit reconciliation, never silently re-confirmed here",
        )
    if status == "modify_booking":
        return decide("change_requested", "modification requested, not yet accepted")
    if status == "modifying":
        return GRSTransitionDecision(
            target_status=None, requires_backoffice_review=False,
            reason="modification accepted by provider but not yet complete - stays in 'change_requested' "
            "until the provider confirms 'modified'",
        )
    if status == "modified":
        return decide("changed", "provider confirms modification is complete")
    if status == "rejected_modify":
        return decide("confirmed", "provider rejected the modification - reservation reverts to its prior confirmed state")
    if status == "refund":
        return GRSTransitionDecision(
            target_status=None, requires_backoffice_review=True,
            reason="grs 'refund' status does not distinguish pending vs processed - contract gap, "
            "never auto-set to the internal terminal 'refunded' status without independent confirmation",
        )
    if status in {"suggested", "overbooking"}:
        return GRSTransitionDecision(
            target_status=None, requires_backoffice_review=True,
            reason=f"grs status '{status}' has no corresponding KarenSeir internal state - exception, "
            "routed to BackOffice review, never forced into the enum",
        )
    return GRSTransitionDecision(
        target_status=None, requires_backoffice_review=True,
        reason=f"unrecognized grs status '{status}' - mapped to provider_unknown (raw value retained "
        "separately), routed to BackOffice review, does not crash",
    )
