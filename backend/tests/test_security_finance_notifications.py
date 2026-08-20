from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

import pytest
from sqlalchemy import func, select

import app.main as main_module
from app.main import SessionLocal, User
from app.operations import (
    ApprovalWorkflow,
    FinancialLedgerEntry,
    NotificationDeliveryAttempt,
    NotificationRecord,
    NotificationPreference,
    OutboxEvent,
    Reservation,
    SupportMessage,
    Trip,
    TripEventRecord,
    Wallet,
    OTPChallenge,
    PaymentIntent,
    apply_credit_command,
    ingest_trip_event,
    wallet_balances,
)
from app.outbox_worker import process_batch
from app.observability import prometheus_metrics
from app.providers import ADAPTERS
from app.providers import ProviderContext
from app.security import hash_password, role_has_permission, verify_password


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client, email: str) -> dict:
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def test_password_hash_and_role_permissions_are_fail_closed():
    encoded = hash_password("a-long-development-password")
    assert encoded != "a-long-development-password"
    assert verify_password("a-long-development-password", encoded)
    assert not verify_password("wrong-password", encoded)
    assert role_has_permission("organization_admin", "credit:manage")
    assert not role_has_permission("employee", "credit:manage")
    assert not role_has_permission("unknown-role", "reservation:read")


def test_refresh_token_rotates_and_old_token_cannot_be_reused(client):
    session = login(client, "employee@aftab.test")
    assert session["refresh_token"].startswith("1.")
    rotated = client.post("/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != session["refresh_token"]
    assert client.post("/auth/refresh", json={"refresh_token": session["refresh_token"]}).status_code == 401

    tampered_tenant = "2." + rotated.json()["refresh_token"].split(".", 1)[1]
    assert client.post("/auth/refresh", json={"refresh_token": tampered_tenant}).status_code == 401


class SuccessfulOTPAdapter:
    def __init__(self):
        self.code = None

    def execute(self, operation, payload, context):
        self.code = payload["code"]
        return {"ok": True, "status": "accepted", "reference": "sandbox-delivery-reference"}


class FailingOTPAdapter:
    def execute(self, operation, payload, context):
        raise TimeoutError("provider timeout")


def test_otp_login_is_one_time_tenant_aware_and_logout_revokes(client, monkeypatch):
    import app.providers as providers

    adapter = SuccessfulOTPAdapter()
    monkeypatch.setitem(providers.ADAPTERS, "otp", adapter)
    requested = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "employee@aftab.test"})
    assert requested.status_code == 202
    challenge_id = requested.json()["challenge_id"]
    verified = client.post("/auth/otp/verify", json={"tenant_slug": "aftab-bank", "challenge_id": challenge_id, "code": adapter.code, "device_id": "browser-device-001"})
    assert verified.status_code == 200
    tokens = verified.json()
    assert client.post("/auth/otp/verify", json={"tenant_slug": "aftab-bank", "challenge_id": challenge_id, "code": adapter.code, "device_id": "browser-device-001"}).status_code == 401
    assert client.post("/auth/otp/verify", json={"tenant_slug": "faraz-industries", "challenge_id": challenge_id, "code": adapter.code, "device_id": "browser-device-001"}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"], "device_id": "wrong-device-001"}).status_code == 401
    assert client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=auth(tokens["access_token"])).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_otp_provider_failure_and_unknown_user_are_enumeration_safe(client):
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(OTPChallenge))
    known = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "employee@aftab.test"})
    unknown = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "missing@aftab.test"})
    assert known.status_code == unknown.status_code == 202
    assert set(known.json()) == set(unknown.json()) == {"status", "challenge_id", "expires_in"}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OTPChallenge)) == before


def test_otp_provider_exception_is_fail_closed_and_does_not_persist_code(client, monkeypatch):
    import app.providers as providers

    monkeypatch.setitem(providers.ADAPTERS, "otp", FailingOTPAdapter())
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(OTPChallenge))
    response = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "employee@aftab.test"})
    assert response.status_code == 202
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OTPChallenge)) == before


def test_otp_wrong_code_locks_challenge_and_account(client, monkeypatch):
    import app.providers as providers

    adapter = SuccessfulOTPAdapter()
    monkeypatch.setitem(providers.ADAPTERS, "otp", adapter)
    challenge_id = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "employee@aftab.test"}).json()["challenge_id"]
    wrong_code = "999999" if adapter.code != "999999" else "000000"
    for _ in range(5):
        assert client.post("/auth/otp/verify", json={"tenant_slug": "aftab-bank", "challenge_id": challenge_id, "code": wrong_code, "device_id": "bruteforce-device"}).status_code == 401
    assert client.post("/auth/otp/verify", json={"tenant_slug": "aftab-bank", "challenge_id": challenge_id, "code": adapter.code, "device_id": "bruteforce-device"}).status_code == 401


def test_credit_reserve_capture_release_and_idempotency():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        wallet = Wallet(tenant_id=user.tenant_id, owner_type="user", owner_reference=f"credit-{user.id}")
        db.add(wallet)
        db.flush()
        apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id="allocate-credit-1", entry_type="allocate", amount=2_000_000)
        reserve = apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id="reserve-credit-1", entry_type="reserve", amount=700_000)
        duplicate = apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id="reserve-credit-1", entry_type="reserve", amount=700_000)
        db.flush()
        assert duplicate.id == reserve.id
        apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id="capture-credit-1", entry_type="capture", amount=400_000)
        apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id="release-credit-1", entry_type="release", amount=300_000)
        db.commit()
        assert wallet_balances(db, tenant_id=user.tenant_id, wallet_id=wallet.id) == {"available": 1_600_000, "reserved": 0, "consumed": 400_000}
        assert db.scalar(select(func.count()).select_from(FinancialLedgerEntry).where(FinancialLedgerEntry.wallet_id == wallet.id)) == 4


class SuccessfulPaymentAdapter:
    def execute(self, operation, payload, context):
        return {"ok": True, "status": "accepted", "reference": "sandbox-payment-ref", "redirect_url": "https://sandbox.payment.test/pay/123"}


def test_payment_intent_signed_callback_duplicate_and_partial_refund(client, monkeypatch):
    import app.providers as providers

    session = login(client, "employee@aftab.test")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="pending_payment", price_snapshot_json=json.dumps({"total_amount": 1_500_000, "currency": "IRR"}), policy_at_booking_json='{"verified":true}')
        db.add(reservation); db.commit(); reservation_id = reservation.id
    created = client.post(f"/reservations/{reservation_id}/payment-intents", headers={**auth(session["access_token"]), "Idempotency-Key": "payment-create-001"})
    assert created.status_code == 201
    assert client.post(f"/reservations/{reservation_id}/payment-intents", headers={**auth(session["access_token"]), "Idempotency-Key": "payment-create-001"}).json()["id"] == created.json()["id"]
    payment_id = created.json()["id"]
    assert client.post(f"/payments/{payment_id}/initiate", headers=auth(session["access_token"])).status_code == 503
    monkeypatch.setitem(providers.ADAPTERS, "payment", SuccessfulPaymentAdapter())
    assert client.post(f"/payments/{payment_id}/initiate", headers=auth(session["access_token"])).status_code == 202
    monkeypatch.setattr(main_module, "PAYMENT_WEBHOOK_SECRET", "test-webhook-secret")
    payload = {"tenant_id": 1, "payment_intent_id": payment_id, "event_id": "provider-event-capture-1", "status": "captured", "amount": 1_500_000}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(b"test-webhook-secret", raw, hashlib.sha256).hexdigest()
    callback = client.post("/payments/callback/payment", content=raw, headers={"Content-Type": "application/json", "X-Payment-Signature": signature})
    assert callback.status_code == 200 and callback.json()["payment_status"] == "captured"
    duplicate = client.post("/payments/callback/payment", content=raw, headers={"Content-Type": "application/json", "X-Payment-Signature": signature})
    assert duplicate.status_code == 200 and duplicate.json()["status"] == "duplicate"
    bad_signature = client.post("/payments/callback/payment", content=raw, headers={"Content-Type": "application/json", "X-Payment-Signature": "0" * 64})
    assert bad_signature.status_code == 401
    refund = client.post(f"/payments/{payment_id}/refunds", json={"amount": 500_000, "command_id": "refund-command-001"}, headers=auth(session["access_token"]))
    assert refund.status_code == 202
    assert client.post(f"/payments/{payment_id}/refunds", json={"amount": 500_000, "command_id": "refund-command-001"}, headers=auth(session["access_token"])).json()["id"] == refund.json()["id"]
    assert client.post(f"/payments/{payment_id}/refunds", json={"amount": 1_200_000, "command_id": "refund-command-over-pending"}, headers=auth(session["access_token"])).status_code == 409
    assert client.post(f"/payments/{payment_id}/refunds", json={"amount": 2_000_000, "command_id": "refund-command-002"}, headers=auth(session["access_token"])).status_code == 409
    metrics = client.get("/metrics").text
    assert 'karenseir_business_events_total{event="payment",status="captured"}' in metrics
    assert 'karenseir_business_events_total{event="refund",status="requested"}' in metrics


def test_payment_intent_rejects_cross_tenant_and_unverified_price(client):
    aftab = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="flight", status="draft", price_snapshot_json="{}")
        db.add(reservation); db.commit(); reservation_id = reservation.id
    assert client.post(f"/reservations/{reservation_id}/payment-intents", headers={**auth(faraz["access_token"]), "Idempotency-Key": "cross-tenant-pay"}).status_code == 404
    assert client.post(f"/reservations/{reservation_id}/payment-intents", headers={**auth(aftab["access_token"]), "Idempotency-Key": "missing-price-pay"}).status_code == 409


def test_credit_cannot_cross_tenant_or_overdraw():
    with SessionLocal() as db:
        aftab = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        faraz = db.scalar(select(User).where(User.email == "employee@faraz.test"))
        wallet = Wallet(tenant_id=aftab.tenant_id, owner_type="user", owner_reference="isolated-wallet")
        db.add(wallet)
        db.flush()
        with pytest.raises(ValueError, match="wallet not found"):
            apply_credit_command(db, tenant_id=faraz.tenant_id, wallet_id=wallet.id, command_id="cross-tenant-credit", entry_type="allocate", amount=10)
        apply_credit_command(db, tenant_id=aftab.tenant_id, wallet_id=wallet.id, command_id="small-allocation", entry_type="allocate", amount=100)
        db.flush()
        with pytest.raises(ValueError, match="insufficient available"):
            apply_credit_command(db, tenant_id=aftab.tenant_id, wallet_id=wallet.id, command_id="overdraw-credit", entry_type="reserve", amount=101)


def test_trip_event_materializes_notification_channels_and_source_distinction():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        trip = Trip(tenant_id=user.tenant_id, user_id=user.id, title="سفر عملیاتی شیراز", origin="تهران", destination="شیراز")
        db.add(trip)
        db.flush()
        event = ingest_trip_event(db, TripEventRecord(tenant_id=user.tenant_id, trip_id=trip.id, event_key="verified-change-1", event_type="schedule_changed", severity="warning", source="system_provider", title="ساعت حرکت تغییر کرد", message="اطلاعات تأییدشده نمونه", effective_at=datetime.now(timezone.utc), deep_link=f"/trips/{trip.id}?event=verified-change-1"))
        db.add(SupportMessage(tenant_id=user.tenant_id, trip_id=trip.id, sender_type="human_support", body="پیام نمونه کارشناس"))
        db.commit()
        notification = db.scalar(select(NotificationRecord).where(NotificationRecord.trip_event_id == event.id))
        attempts = db.scalars(select(NotificationDeliveryAttempt).where(NotificationDeliveryAttempt.notification_id == notification.id)).all()
        assert {attempt.channel for attempt in attempts} == {"in_app", "push", "sms"}
        assert event.source == "system_provider"
        assert db.scalar(select(SupportMessage.sender_type).where(SupportMessage.trip_id == trip.id)) == "human_support"


def test_notification_preference_prevents_disabled_channel_materialization():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        trip = Trip(tenant_id=user.tenant_id, user_id=user.id, title="سفر ترجیحات", origin="تهران", destination="یزد")
        db.add_all([trip, NotificationPreference(tenant_id=user.tenant_id, user_id=user.id, topic="important_trip_changes", channel="sms", enabled=False)])
        db.flush()
        event = ingest_trip_event(db, TripEventRecord(tenant_id=user.tenant_id, trip_id=trip.id, event_key="preference-event", event_type="schedule_changed", severity="warning", source="provider", title="تغییر", message="پیام"))
        db.commit()
        notification = db.scalar(select(NotificationRecord).where(NotificationRecord.trip_event_id == event.id))
        channels = set(db.scalars(select(NotificationDeliveryAttempt.channel).where(NotificationDeliveryAttempt.notification_id == notification.id)).all())
        assert channels == {"in_app", "push"}


def test_outbox_retries_then_dead_letters_without_claiming_delivery():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        event = OutboxEvent(tenant_id=user.tenant_id, aggregate_type="test", aggregate_id="dead-letter-test", event_type="notification.test", payload_json="{}", status="retry", attempts=4, available_at=datetime.now(timezone.utc) - timedelta(seconds=1), correlation_id="corr-dead-letter", idempotency_key="dead-letter-key")
        db.add(event)
        db.commit()
        event_id = event.id
    assert process_batch(limit=100, adapter=ADAPTERS["push"]) >= 1
    with SessionLocal() as db:
        saved = db.get(OutboxEvent, event_id)
        assert saved.status == "dead_letter"
        assert saved.attempts == 5
        assert saved.dead_lettered_at is not None
        assert saved.last_error == "external_provider_not_configured"
    metrics = prometheus_metrics()
    assert "karenseir_outbox_queue_depth" in metrics
    assert "karenseir_outbox_dead_letter_depth" in metrics


def test_rbac_and_tenant_scoped_deep_links(client):
    employee = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    org_admin = login(client, "org-admin@aftab.test")
    with SessionLocal() as db:
        aftab_user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=aftab_user.tenant_id, user_id=aftab_user.id, service_type="hotel", status="confirmed")
        wallet = Wallet(tenant_id=aftab_user.tenant_id, owner_type="organization", owner_reference="aftab-rbac")
        db.add_all([reservation, wallet])
        db.flush()
        approval = ApprovalWorkflow(tenant_id=aftab_user.tenant_id, reservation_id=reservation.id)
        trip = Trip(tenant_id=aftab_user.tenant_id, user_id=aftab_user.id, title="سفر لینک", origin="تهران", destination="شیراز")
        db.add_all([approval, trip])
        db.flush()
        event = ingest_trip_event(db, TripEventRecord(tenant_id=aftab_user.tenant_id, trip_id=trip.id, event_key="deep-link-event", event_type="voucher_reissued", severity="info", source="system_provider", title="واچر جدید", message="نمونه", deep_link=f"/trips/{trip.id}?event=deep-link-event"))
        db.commit()
        reservation_id, wallet_id, approval_id, trip_id, event_id = reservation.id, wallet.id, approval.id, trip.id, event.id
    assert client.get(f"/reservations/{reservation_id}", headers=auth(employee["access_token"])).status_code == 200
    assert client.get(f"/reservations/{reservation_id}", headers=auth(faraz["access_token"])).status_code == 404
    assert client.get(f"/trips/{trip_id}/events/{event_id}", headers=auth(employee["access_token"])).status_code == 200
    assert client.get(f"/trips/{trip_id}/events/{event_id}", headers=auth(faraz["access_token"])).status_code == 404
    assert client.post(f"/wallets/{wallet_id}/commands", json={"command_id": "employee-denied", "entry_type": "allocate", "amount": 10}, headers=auth(employee["access_token"])).status_code == 403
    assert client.post(f"/wallets/{wallet_id}/commands", json={"command_id": "admin-allocate", "entry_type": "allocate", "amount": 10}, headers=auth(org_admin["access_token"])).status_code == 200
    assert client.post(f"/approvals/{approval_id}/decision", json={"decision": "approve"}, headers=auth(org_admin["access_token"])).status_code == 200


def test_production_configuration_rejects_unapproved_real_provider(monkeypatch):
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    monkeypatch.setattr(main_module, "JWT_SECRET", "a-production-secret-that-is-long-enough")
    monkeypatch.setattr(main_module, "DATABASE_URL", "postgresql+psycopg://example")
    monkeypatch.setenv("CORS_ORIGINS", "https://travel.example")
    monkeypatch.setenv("PAYMENT_PROVIDER_MODE", "real")
    with pytest.raises(RuntimeError, match="authorized production adapter"):
        main_module.validate_production_config()


@pytest.mark.parametrize("adapter_key,operation", [("otp", "send_otp"), ("sms", "deliver_sms"), ("push", "deliver_push")])
def test_communication_adapters_never_claim_mock_delivery(adapter_key, operation):
    result = ADAPTERS[adapter_key].execute(operation, {"reference": "sample"}, ProviderContext(tenant_id=1, correlation_id=f"corr-{adapter_key}", idempotency_key=f"idem-{adapter_key}"))
    assert result["ok"] is False
    assert result["status"] == "not_sent"
    assert result["error"]["retryable"] is False


def test_timeline_hides_internal_events(client):
    session = login(client, "employee@aftab.test")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        trip = Trip(tenant_id=user.tenant_id, user_id=user.id, title="سفر با رخداد داخلی", origin="تهران", destination="یزد")
        db.add(trip)
        db.flush()
        customer = TripEventRecord(tenant_id=user.tenant_id, trip_id=trip.id, event_key="customer-visible", event_type="general_update", severity="info", source="system_provider", title="تغییر قابل نمایش", message="نمونه", visibility="customer")
        internal = TripEventRecord(tenant_id=user.tenant_id, trip_id=trip.id, event_key="internal-only", event_type="support_note", severity="info", source="human_support", title="یادداشت داخلی", message="نباید نمایش داده شود", visibility="internal")
        db.add_all([customer, internal])
        db.commit()
        trip_id = trip.id
    response = client.get(f"/trips/{trip_id}/timeline", headers=auth(session["access_token"]))
    assert response.status_code == 200
    assert [event["title"] for event in response.json()["events"]] == ["تغییر قابل نمایش"]


def test_development_login_is_hidden_in_production(client, monkeypatch):
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    assert client.post("/auth/dev-login", json={"email": "employee@aftab.test"}).status_code == 404
