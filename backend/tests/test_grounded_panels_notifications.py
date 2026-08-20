import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import app.main as main_module
from app.main import SessionLocal, User
from app.operations import NotificationDeliveryAttempt, NotificationRecord, Offer, Organization, PaymentIntent, RefundRecord, Reservation, Supplier, Trip


def auth(token): return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def test_white_label_is_persistent_config_not_fork_and_is_tenant_isolated(client):
    tenant_admin = login(client, "tenant-admin@aftab.test")
    employee = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    payload = {"display_name": "کارن‌سیر آفتاب", "logo_reference": "asset://tenant/aftab/logo.svg", "primary_color": "#0E7490", "secondary_color": "#082F49", "custom_domain": "travel.aftab.example", "support": {"phone": "internal-reference"}, "enabled_services": ["hotel", "flight", "hotel"], "organization_policy": {"approval_required": True}, "feature_flags": {"assistant": True}}
    saved = client.put("/tenant/white-label", headers=auth(tenant_admin["access_token"]), json=payload)
    assert saved.status_code == 200 and saved.json()["domain_status"] == "unverified"
    assert saved.json()["enabled_services"] == ["flight", "hotel"]
    assert client.get("/tenant/white-label", headers=auth(employee["access_token"])).json()["display_name"] == "کارن‌سیر آفتاب"
    assert client.get("/tenant/white-label", headers=auth(faraz["access_token"])).status_code == 404


def test_explainable_comparison_and_ai_context_use_only_tenant_backend_data(client):
    employee = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        supplier = Supplier(tenant_id=user.tenant_id, supplier_type="hotel", display_name="supplier", status="active")
        db.add(supplier); db.flush()
        policy = json.dumps({"verified": True, "source": "contract", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True, "penalty_amount": 0}})
        first = Offer(tenant_id=user.tenant_id, supplier_id=supplier.id, service_type="hotel", title="هتل اول", amount=1_000_000, available_units=2, valid_until=datetime.now(timezone.utc)+timedelta(hours=1), policy_json=policy, attributes_json=json.dumps({"rating": 4.8, "location_score": 8, "amenities": ["breakfast", "wifi"], "organization_policy_compliant": True}))
        second = Offer(tenant_id=user.tenant_id, supplier_id=supplier.id, service_type="hotel", title="هتل دوم", amount=1_200_000, available_units=2, valid_until=datetime.now(timezone.utc)+timedelta(hours=1), policy_json=policy, attributes_json=json.dumps({"rating": 4.0, "location_score": 6, "amenities": ["wifi"]}))
        reservation = Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="issued", booking_reference="KS-GROUNDED", price_snapshot_json='{"total_amount":1000000,"currency":"IRR"}', policy_at_booking_json=policy, current_policy_json=policy)
        db.add_all([first, second, reservation]); db.commit(); ids = [first.id, second.id]; reservation_id = reservation.id
    compared = client.post("/compare/offers", headers=auth(employee["access_token"]), json={"offer_ids": ids})
    assert compared.status_code == 200 and compared.json()["authoritative"] is True
    assert compared.json()["results"][0]["score"] > compared.json()["results"][1]["score"]
    assert set(compared.json()["results"][0]["breakdown"]) == {"price", "quality", "cancellation", "location", "amenities", "organization_policy"}
    assert client.post("/compare/offers", headers=auth(faraz["access_token"]), json={"offer_ids": ids}).status_code == 404
    context = client.get(f"/ai/grounded-context?reservation_id={reservation_id}", headers=auth(employee["access_token"]))
    assert context.status_code == 200 and context.json()["generated_transactional_data"] is False
    assert context.json()["booking"]["price_snapshot"]["total_amount"] == 1_000_000
    assert client.get(f"/ai/grounded-context?reservation_id={reservation_id}", headers=auth(faraz["access_token"])).status_code == 404


def test_notification_preferences_and_signed_delivery_receipts(client, monkeypatch):
    employee = login(client, "employee@aftab.test")
    preference = client.put("/me/notification-preferences", headers=auth(employee["access_token"]), json={"topic": "trip_changes", "channel": "sms", "enabled": False})
    assert preference.status_code == 200
    assert client.get("/me/notification-preferences", headers=auth(employee["access_token"])).json() == [{"topic": "trip_changes", "channel": "sms", "enabled": False}]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        notification = NotificationRecord(tenant_id=user.tenant_id, user_id=user.id, topic="trip_changes", title="تغییر", message="پیام", status="pending")
        db.add(notification); db.flush()
        attempt = NotificationDeliveryAttempt(tenant_id=user.tenant_id, notification_id=notification.id, channel="sms", status="pending")
        db.add(attempt); db.commit(); attempt_id = attempt.id
    monkeypatch.setattr(main_module, "NOTIFICATION_WEBHOOK_SECRET", "notification-test-secret")
    payload = {"tenant_id": 1, "attempt_id": attempt_id, "receipt_event_id": "sms-receipt-1", "status": "delivered", "provider_message_id": "provider-message-1"}
    raw = json.dumps(payload, separators=(",", ":")).encode(); signature = hmac.new(b"notification-test-secret", raw, hashlib.sha256).hexdigest()
    assert client.post("/notification-receipts/sms", content=raw, headers={"Content-Type": "application/json", "X-Notification-Signature": "0"*64}).status_code == 401
    accepted = client.post("/notification-receipts/sms", content=raw, headers={"Content-Type": "application/json", "X-Notification-Signature": signature})
    assert accepted.status_code == 200 and accepted.json()["delivery_status"] == "delivered"
    duplicate = client.post("/notification-receipts/sms", content=raw, headers={"Content-Type": "application/json", "X-Notification-Signature": signature})
    assert duplicate.json()["status"] == "duplicate"


def test_supplier_agency_and_backoffice_operational_views(client):
    supplier = login(client, "supplier@aftab.test")
    agency = login(client, "agency@aftab.test")
    backoffice = login(client, "backoffice@aftab.test")
    created = client.post("/agency/sub-agencies", headers=auth(agency["access_token"]), json={"display_name": "زیرآژانس", "markup_bps": 250, "commission_bps": 500})
    assert created.status_code == 201
    assert client.get("/agency/dashboard", headers=auth(agency["access_token"])).json()["agencies"][0]["commission_bps"] == 500
    assert client.get("/supplier/dashboard", headers=auth(supplier["access_token"])).status_code == 200
    overview = client.get("/backoffice/overview", headers=auth(backoffice["access_token"]))
    assert overview.status_code == 200
    assert "payments" in overview.json()["counts"] and "providers" in overview.json()


def test_finance_reconciliation_is_tenant_scoped_read_only_and_role_guarded(client):
    finance = login(client, "finance@aftab.test")
    employee = login(client, "employee@aftab.test")
    login(client, "employee@faraz.test")
    with SessionLocal() as db:
        aftab_user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        faraz_user = db.scalar(select(User).where(User.email == "employee@faraz.test"))
        aftab_reservation = Reservation(tenant_id=aftab_user.tenant_id, user_id=aftab_user.id, service_type="hotel", status="confirmed", price_snapshot_json='{"total_amount":1000}', policy_at_booking_json="{}", current_policy_json="{}")
        faraz_reservation = Reservation(tenant_id=faraz_user.tenant_id, user_id=faraz_user.id, service_type="hotel", status="confirmed", price_snapshot_json='{"total_amount":9000}', policy_at_booking_json="{}", current_policy_json="{}")
        db.add_all([aftab_reservation, faraz_reservation]); db.flush()
        balanced = PaymentIntent(tenant_id=aftab_user.tenant_id, reservation_id=aftab_reservation.id, user_id=aftab_user.id, command_id="reconcile-aftab", amount=1000, status="captured", captured_amount=1000, refunded_amount=200, provider_reference="provider-1")
        hidden = PaymentIntent(tenant_id=faraz_user.tenant_id, reservation_id=faraz_reservation.id, user_id=faraz_user.id, command_id="reconcile-faraz", amount=9000, status="captured", captured_amount=9000, provider_reference="provider-2")
        db.add_all([balanced, hidden]); db.flush()
        db.add(RefundRecord(tenant_id=aftab_user.tenant_id, payment_intent_id=balanced.id, command_id="refund-reconcile-aftab", amount=200, status="succeeded")); balanced_id = balanced.id; db.commit()
    response = client.get("/finance/reconciliation", headers=auth(finance["access_token"]))
    assert response.status_code == 200
    body = response.json()
    row = next(item for item in body["payments"] if item["payment_id"] == balanced_id)
    assert row["issues"] == [] and row["succeeded_refund_amount"] == 200
    assert all(item["intent_amount"] != 9000 for item in body["payments"])
    assert client.get("/finance/reconciliation", headers=auth(employee["access_token"])).status_code == 403


def test_authenticated_frontend_read_models_are_tenant_and_role_scoped(client):
    employee = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    organization_admin = login(client, "org-admin@aftab.test")
    with SessionLocal() as db:
        aftab_user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        faraz_user = db.scalar(select(User).where(User.email == "employee@faraz.test"))
        own_trip = Trip(tenant_id=aftab_user.tenant_id, user_id=aftab_user.id, title="سفر معتبر آفتاب", destination="یزد", status="planned")
        hidden_trip = Trip(tenant_id=faraz_user.tenant_id, user_id=faraz_user.id, title="سفر محرمانه فراز", destination="تبریز", status="planned")
        own_notice = NotificationRecord(tenant_id=aftab_user.tenant_id, user_id=aftab_user.id, topic="trip_changes", title="تغییر معتبر", message="جزئیات", status="pending")
        hidden_notice = NotificationRecord(tenant_id=faraz_user.tenant_id, user_id=faraz_user.id, topic="trip_changes", title="اعلان فراز", message="محرمانه", status="pending")
        organization = Organization(tenant_id=aftab_user.tenant_id, name="سازمان آفتاب", status="active")
        db.add_all([own_trip, hidden_trip, own_notice, hidden_notice, organization]); db.commit()
    trips = client.get("/me/trips", headers=auth(employee["access_token"]))
    assert trips.status_code == 200 and [row["title"] for row in trips.json()] == ["سفر معتبر آفتاب"]
    notices = client.get("/me/notifications", headers=auth(employee["access_token"]))
    assert notices.status_code == 200 and all(row["title"] != "اعلان فراز" for row in notices.json())
    overview = client.get("/organization/overview", headers=auth(organization_admin["access_token"]))
    assert overview.status_code == 200 and "سازمان آفتاب" in [row["name"] for row in overview.json()["organizations"]]
    assert client.get("/organization/overview", headers=auth(employee["access_token"])).status_code == 403
    assert client.get("/me/trips", headers=auth(faraz["access_token"])).json()[0]["title"] == "سفر محرمانه فراز"


def test_supplier_onboarding_is_idempotent_tenant_scoped_and_role_guarded(client):
    supplier = login(client, "supplier@aftab.test")
    employee = login(client, "employee@aftab.test")
    headers = {**auth(supplier["access_token"]), "Idempotency-Key": "supplier-onboarding-test"}
    payload = {"supplier_type": "hotel", "display_name": "تأمین‌کننده معتبر تست"}
    first = client.post("/supplier/onboarding", headers=headers, json=payload)
    replay = client.post("/supplier/onboarding", headers=headers, json=payload)
    conflict = client.post("/supplier/onboarding", headers=headers, json={**payload, "display_name": "نام متفاوت"})
    assert first.status_code == 201 and replay.json() == first.json()
    assert conflict.status_code == 409
    assert client.post("/supplier/onboarding", headers={**auth(employee["access_token"]), "Idempotency-Key": "supplier-denied-test"}, json=payload).status_code == 403
