"""Webhook inbox/processing tests - real SQLite DB, no network, [TEST] fixtures only."""
import uuid

from sqlalchemy import select

from app.main import SessionLocal, Tenant, User
from app.database import set_tenant_context
from app.operations import Reservation, ProviderWebhookEvent, ProviderReconciliationCase
from app.grs_webhook import (
    verify_webhook_signature, compute_event_key, sanitize_payload,
    record_webhook_event, process_webhook_event,
)


def test_signature_verification_never_claims_verified():
    result = verify_webhook_signature(headers={}, raw_body=b"{}", configured_secret="whatever")
    assert result.verified is False
    assert "no webhook signature scheme" in result.reason.lower()


def test_sanitize_payload_redacts_known_pii_recursively():
    raw = {"value": {"reserve": {"booker_phone": "0912xxxxxxx", "guest_first_name": "Real Name",
                                  "status": "booking"}}}
    clean = sanitize_payload(raw)
    assert clean["value"]["reserve"]["booker_phone"] == "[REDACTED]"
    assert clean["value"]["reserve"]["guest_first_name"] == "[REDACTED]"
    assert clean["value"]["reserve"]["status"] == "booking"  # non-PII untouched


def test_same_payload_produces_same_dedup_key():
    p1 = {"method": "reserve_changed", "value": {"a": 1}}
    p2 = {"value": {"a": 1}, "method": "reserve_changed"}  # different key order
    assert compute_event_key(p1) == compute_event_key(p2)


def _make_tenant_user_reservation(provider_reference):
    with SessionLocal() as db:
        tenant = Tenant(slug=f"grs-wh-{uuid.uuid4().hex[:8]}", name="[TEST] GRS Webhook Tenant", primary_color="#000000")
        db.add(tenant)
        db.flush()
        set_tenant_context(db, tenant.id)
        user = User(tenant_id=tenant.id, email=f"grs-wh-{uuid.uuid4().hex[:8]}@example.test", name="[TEST] Guest", role="customer")
        db.add(user)
        db.flush()
        reservation = Reservation(tenant_id=tenant.id, user_id=user.id, service_type="hotel", status="reserved", provider_reference=provider_reference)
        db.add(reservation)
        db.commit()
        return tenant.id, reservation.id


def test_duplicate_webhook_delivery_is_deduplicated_not_processed_twice():
    tenant_id, reservation_id = _make_tenant_user_reservation("C-WH-1")
    payload = {"method": "reserve_changed", "value": {"reserve": {"state": "online", "status": "booking", "confirmation_code": "C-WH-1"}}}
    with SessionLocal() as db:
        event1, is_new1 = record_webhook_event(db, provider_key="grs", method="reserve_changed", raw_payload=payload)
        db.commit()
        assert is_new1 is True
        event2, is_new2 = record_webhook_event(db, provider_key="grs", method="reserve_changed", raw_payload=payload)
        assert is_new2 is False
        assert event2.id == event1.id
        count = db.scalar(select(ProviderWebhookEvent).where(ProviderWebhookEvent.provider_key == "grs")) is not None
        assert count


def test_unknown_reservation_reference_is_quarantined_not_applied():
    payload = {"method": "reserve_changed", "value": {"reserve": {"state": "online", "status": "booking", "confirmation_code": "C-DOES-NOT-EXIST"}}}
    with SessionLocal() as db:
        event, _ = record_webhook_event(db, provider_key="grs", method="reserve_changed", raw_payload=payload)
        db.commit()
        result = process_webhook_event(db, event)
        db.commit()
        assert result.outcome == "manual_review_required"
        assert event.processing_status == "quarantined"
        assert event.resolved_tenant_id is None


def test_matching_reservation_gets_tenant_resolved_and_transition_applied():
    tenant_id, reservation_id = _make_tenant_user_reservation("C-WH-2")
    payload = {"method": "reserve_changed", "value": {"reserve": {"state": "offline", "status": "canceling", "confirmation_code": "C-WH-2"}}}
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        event, _ = record_webhook_event(db, provider_key="grs", method="reserve_changed", raw_payload=payload)
        db.commit()
        result = process_webhook_event(db, event)
        db.commit()
        assert result.outcome == "reconciled_internal_update"
        assert event.resolved_tenant_id == tenant_id
        reservation = db.get(Reservation, reservation_id)
        assert reservation.status == "cancel_requested"


def test_ambiguous_status_opens_reconciliation_case_via_webhook():
    tenant_id, reservation_id = _make_tenant_user_reservation("C-WH-3")
    payload = {"method": "reserve_changed", "value": {"reserve": {"state": "online", "status": "overbooking", "confirmation_code": "C-WH-3"}}}
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        event, _ = record_webhook_event(db, provider_key="grs", method="reserve_changed", raw_payload=payload)
        db.commit()
        result = process_webhook_event(db, event)
        db.commit()
        assert result.outcome == "manual_review_required"
        case = db.scalar(select(ProviderReconciliationCase).where(ProviderReconciliationCase.reservation_id == reservation_id))
        assert case is not None


def test_out_of_order_webhook_never_regresses_a_newer_state():
    tenant_id, reservation_id = _make_tenant_user_reservation("C-WH-4")
    # reservation is already "confirmed" (newer); an old "pending" event arrives late
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        reservation = db.get(Reservation, reservation_id)
        reservation.status = "confirmed"
        db.commit()

    payload = {"method": "reserve_changed", "value": {"reserve": {"state": "online", "status": "pending", "confirmation_code": "C-WH-4"}}}
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        event, _ = record_webhook_event(db, provider_key="grs", method="reserve_changed", raw_payload=payload)
        db.commit()
        result = process_webhook_event(db, event)
        db.commit()
        reservation = db.get(Reservation, reservation_id)
        # "confirmed" -> "reserved" is not a legal BOOKING_TRANSITIONS edge, so
        # this must be rejected, never silently applied backward
        assert reservation.status == "confirmed"
        assert result.outcome == "manual_review_required"


def test_non_reservation_event_type_is_marked_processed_with_no_change():
    payload = {"method": "property_changed", "value": {"id": 740, "name": "[TEST] Property"}}
    with SessionLocal() as db:
        event, _ = record_webhook_event(db, provider_key="grs", method="property_changed", raw_payload=payload)
        db.commit()
        result = process_webhook_event(db, event)
        db.commit()
        assert result.outcome == "reconciled_no_change"
        assert event.processing_status == "processed"


def test_reprocessing_an_already_processed_event_is_idempotent():
    payload = {"method": "property_changed", "value": {"id": 1}}
    with SessionLocal() as db:
        event, _ = record_webhook_event(db, provider_key="grs", method="property_changed", raw_payload=payload)
        db.commit()
        process_webhook_event(db, event)
        db.commit()
        result_again = process_webhook_event(db, event)
        assert result_again.outcome == "reconciled_no_change"
        assert "already processed" in result_again.detail
