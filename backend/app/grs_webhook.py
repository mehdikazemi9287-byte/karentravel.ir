"""
GRS webhook intake - Inbox -> dedup -> tenant resolution -> state mapping ->
reconciliation, per the required flow. NOT wired to any public route and NOT
registered with the real GRS endpoint - both require explicit permission this
phase deliberately withholds (see module docstring rationale below).

Signature verification: GRS's documentation gives no signature scheme at all.
This module does NOT invent one. verify_webhook_signature() always returns
False (fail closed) with an explicit reason, until GRS confirms a real scheme.
A public endpoint must not be exposed as "secure" on the strength of this
module alone - IP allowlist/mTLS at the reverse-proxy layer is a separate,
necessary control this module cannot provide.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .grs_contract import map_grs_event_to_internal_transition
from .operations import Reservation, ProviderWebhookEvent, transition_reservation
from .grs_lifecycle import open_reconciliation_case


@dataclass(frozen=True)
class WebhookSignatureResult:
    verified: bool
    reason: str


def verify_webhook_signature(*, headers: Mapping[str, str], raw_body: bytes, configured_secret: str) -> WebhookSignatureResult:
    """No documented GRS signature scheme exists. This deliberately never
    returns verified=True - a secret path/header alone is NOT treated as
    equivalent to a real signature, per the explicit rule."""
    return WebhookSignatureResult(verified=False, reason="GRS defines no webhook signature scheme in v1.18.4 - cannot be verified; blocked pending official provider confirmation")


def compute_event_key(payload: Mapping[str, Any]) -> str:
    """Deterministic dedup key from the payload content itself, since GRS
    documents no explicit event id. Same payload -> same key -> safe re-delivery."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_PII_KEYS = {"guest_first_name", "guest_last_name", "guest_phone", "guest_email", "guest_national_code",
             "guest_passport_number", "booker_first_name", "booker_last_name", "booker_phone", "booker_email"}


def sanitize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Strips known PII field names recursively before anything is persisted -
    per the explicit 'raw payload with PII must never be stored without a
    retention policy' rule. Conservative: only removes documented PII field
    names, never guesses at unknown ones."""
    def _clean(node: Any) -> Any:
        if isinstance(node, Mapping):
            return {k: ("[REDACTED]" if k in _PII_KEYS else _clean(v)) for k, v in node.items()}
        if isinstance(node, list):
            return [_clean(item) for item in node]
        return node
    return _clean(payload)


def record_webhook_event(db: Session, *, provider_key: str, method: str, raw_payload: Mapping[str, Any], correlation_id: Optional[str] = None) -> tuple[ProviderWebhookEvent, bool]:
    """Step 1-2: Inbox + dedup. Returns (event, is_new). A duplicate delivery
    returns the existing row with is_new=False and never creates a second one."""
    event_key = compute_event_key(raw_payload)
    existing = db.scalar(select(ProviderWebhookEvent).where(
        ProviderWebhookEvent.provider_key == provider_key, ProviderWebhookEvent.event_key == event_key,
    ))
    if existing is not None:
        return existing, False
    event = ProviderWebhookEvent(
        provider_key=provider_key, event_key=event_key, event_type=str(raw_payload.get("method", method)),
        provider_reference=_extract_provider_reference(raw_payload), received_at=datetime.now(timezone.utc),
        processing_status="received", correlation_id=correlation_id,
        sanitized_payload_json=json.dumps(sanitize_payload(raw_payload), ensure_ascii=False),
    )
    db.add(event)
    db.flush()
    return event, True


def _extract_provider_reference(raw_payload: Mapping[str, Any]) -> Optional[str]:
    value = raw_payload.get("value")
    if not isinstance(value, Mapping):
        return None
    reserve = value.get("reserve", value)
    if isinstance(reserve, Mapping):
        ref = reserve.get("confirmation_code") or reserve.get("agency_confirmation_code")
        return str(ref) if ref else None
    return None


@dataclass(frozen=True)
class WebhookProcessingResult:
    outcome: str  # "reconciled_no_change" | "reconciled_internal_update" | "manual_review_required"
    detail: str


def process_webhook_event(db: Session, event: ProviderWebhookEvent) -> WebhookProcessingResult:
    """Step 3+: tenant/provider resolution -> state mapping -> reconciliation.
    Never mutates a Reservation for an event whose tenant cannot be resolved,
    and never lets an older event move a newer state backward."""
    if event.processing_status == "processed":
        return WebhookProcessingResult(outcome="reconciled_no_change", detail="already processed (idempotent)")

    if event.event_type != "reserve_changed" or not event.provider_reference:
        event.processing_status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        return WebhookProcessingResult(outcome="reconciled_no_change", detail=f"event_type '{event.event_type}' has no reservation state to apply")

    reservation = db.scalar(select(Reservation).where(Reservation.provider_reference == event.provider_reference))
    if reservation is None:
        event.processing_status = "quarantined"
        event.error_category = "unknown_reservation"
        return WebhookProcessingResult(outcome="manual_review_required", detail=f"no internal reservation matches provider_reference '{event.provider_reference}'")

    event.resolved_tenant_id = reservation.tenant_id

    payload = json.loads(event.sanitized_payload_json)
    value = payload.get("value") or {}
    reserve_value = value.get("reserve", value)
    grs_state = str(reserve_value.get("state", ""))
    grs_status = str(reserve_value.get("status", ""))

    decision = map_grs_event_to_internal_transition(reservation.status, grs_state, grs_status)
    event.processing_status = "processed"
    event.processed_at = datetime.now(timezone.utc)

    if decision.target_status is not None:
        try:
            transition_reservation(db, reservation, decision.target_status, actor_id=0, command_id=f"webhook:{event.id}")
        except ValueError:
            # Out-of-order event trying an already-superseded transition -
            # never applied, never regresses a newer state.
            open_reconciliation_case(db, tenant_id=reservation.tenant_id, reservation_id=reservation.id, operation="webhook",
                                      reason=f"out-of-order webhook: '{reservation.status}' cannot move to '{decision.target_status}'",
                                      observed_state=grs_status)
            return WebhookProcessingResult(outcome="manual_review_required", detail="out-of-order transition rejected")
        return WebhookProcessingResult(outcome="reconciled_internal_update", detail=f"applied transition to '{decision.target_status}'")

    if decision.requires_backoffice_review:
        open_reconciliation_case(db, tenant_id=reservation.tenant_id, reservation_id=reservation.id, operation="webhook",
                                  reason=decision.reason, observed_state=grs_status)
        return WebhookProcessingResult(outcome="manual_review_required", detail=decision.reason)

    return WebhookProcessingResult(outcome="reconciled_no_change", detail=decision.reason)
