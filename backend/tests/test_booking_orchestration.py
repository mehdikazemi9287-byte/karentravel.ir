import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.main import SessionLocal, User
from app.operations import BookingStatusHistory, Offer, PaymentIntent, RefundRecord, Reservation, Supplier, Voucher


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def active_supplier():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "supplier@aftab.test"))
        supplier = Supplier(tenant_id=user.tenant_id, supplier_type="travel", display_name="تأمین‌کننده آزمون", status="active")
        db.add(supplier); db.commit()
        return supplier.id


def policy():
    return {"verified": True, "source": "supplier-contract-test", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True, "penalty_amount": 100_000}}


@pytest.mark.parametrize("service_type,attributes", [
    ("flight", {"origin": "THR", "destination": "SYZ", "baggage": "20kg"}),
    ("hotel", {"city": "Shiraz", "amenities": ["breakfast"]}),
    ("tour", {"destination": "Yazd", "duration_days": 3}),
    ("package", {"items": [{"type": "flight"}, {"type": "hotel"}]}),
])
def test_offer_price_check_booking_payment_fulfillment_and_voucher(client, service_type, attributes):
    supplier_id = active_supplier()
    supplier_session = login(client, "supplier@aftab.test")
    employee = login(client, "employee@aftab.test")
    offer_response = client.post("/supplier/offers", headers=auth(supplier_session["access_token"]), json={"supplier_id": supplier_id, "service_type": service_type, "title": f"offer-{service_type}", "amount": 1_000_000, "available_units": 3, "valid_minutes": 60, "policy": policy(), "attributes": attributes, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"})
    assert offer_response.status_code == 201
    offer_id = offer_response.json()["id"]
    search = client.post("/search/offers", headers=auth(employee["access_token"]), json={"service_type": service_type})
    assert search.status_code == 200 and any(row["id"] == offer_id for row in search.json())
    checked = client.post(f"/offers/{offer_id}/price-check", headers=auth(employee["access_token"]), json={"units": 1, "command_id": f"price-check-{service_type}"})
    assert checked.status_code == 201 and checked.json()["amount"] == 1_000_000
    booking_payload = {"price_check_id": checked.json()["id"], "command_id": f"booking-command-{service_type}"}
    booked = client.post("/orchestration/bookings", headers=auth(employee["access_token"]), json=booking_payload)
    assert booked.status_code == 201 and booked.json()["status"] == "reserved"
    assert client.post("/orchestration/bookings", headers=auth(employee["access_token"]), json=booking_payload).json()["id"] == booked.json()["id"]
    reservation_id = booked.json()["id"]
    payment = client.post(f"/reservations/{reservation_id}/payment-intents", headers={**auth(employee["access_token"]), "Idempotency-Key": f"payment-{service_type}"})
    assert payment.status_code == 201
    with SessionLocal() as db:
        intent = db.get(PaymentIntent, payment.json()["id"])
        intent.status = "captured"; intent.captured_amount = intent.amount
        db.commit()
    fulfilled = client.post(f"/reservations/{reservation_id}/fulfill", headers=auth(supplier_session["access_token"]), json={"command_id": f"fulfill-{service_type}", "provider_reference": f"supplier-ref-{service_type}", "document_reference": f"document://voucher/{service_type}"})
    assert fulfilled.status_code == 200
    assert fulfilled.json()["reservation"]["status"] == "issued"
    assert fulfilled.json()["voucher"]["status"] == "issued"
    replay = client.post(f"/reservations/{reservation_id}/fulfill", headers=auth(supplier_session["access_token"]), json={"command_id": f"fulfill-{service_type}", "provider_reference": f"supplier-ref-{service_type}", "document_reference": f"document://voucher/{service_type}"})
    assert replay.status_code == 200 and replay.json()["voucher"]["id"] == fulfilled.json()["voucher"]["id"]
    history = client.get(f"/reservations/{reservation_id}/history", headers=auth(employee["access_token"])).json()["history"]
    assert [row["to"] for row in history] == ["reserved", "confirmed", "issued"]
    quote = client.get(f"/reservations/{reservation_id}/cancellation-quote", headers=auth(employee["access_token"]))
    assert quote.status_code == 200 and quote.json()["refundable_amount"] == 900_000
    reissued = client.post(f"/reservations/{reservation_id}/voucher/reissue", headers=auth(supplier_session["access_token"]), json={"command_id": f"voucher-reissue-{service_type}", "document_reference": f"document://voucher/{service_type}/v2", "reason": "اصلاح اطلاعات"})
    assert reissued.status_code == 200 and reissued.json()["revision"] == 2
    assert client.post(f"/reservations/{reservation_id}/voucher/reissue", headers=auth(supplier_session["access_token"]), json={"command_id": f"voucher-reissue-{service_type}", "document_reference": f"document://voucher/{service_type}/v2", "reason": "اصلاح اطلاعات"}).json()["revision"] == 2
    cancelled = client.post(f"/reservations/{reservation_id}/service-requests", headers={**auth(employee["access_token"]), "Idempotency-Key": f"cancel-request-{service_type}"}, json={"request_type": "cancel", "reason": "تغییر برنامه"})
    assert cancelled.status_code == 202 and cancelled.json()["consequence_preview"] == "verified_policy"
    assert cancelled.json()["booking_status"] == "cancel_requested"


def test_price_check_expiry_cross_tenant_and_unverified_policy_are_rejected(client):
    supplier_id = active_supplier()
    supplier_session = login(client, "supplier@aftab.test")
    employee = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    invalid = client.post("/supplier/offers", headers=auth(supplier_session["access_token"]), json={"supplier_id": supplier_id, "service_type": "hotel", "title": "invalid-policy", "amount": 1_000_000, "available_units": 1, "valid_minutes": 60, "policy": {"verified": False}, "attributes": {}, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"})
    assert invalid.status_code == 422
    valid = client.post("/supplier/offers", headers=auth(supplier_session["access_token"]), json={"supplier_id": supplier_id, "service_type": "hotel", "title": "expires", "amount": 1_000_000, "available_units": 1, "valid_minutes": 60, "policy": policy(), "attributes": {}, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"})
    offer_id = valid.json()["id"]
    assert client.post("/search/offers", headers=auth(faraz["access_token"]), json={"service_type": "hotel"}).json() == []
    with SessionLocal() as db:
        offer = db.get(Offer, offer_id); offer.valid_until = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    assert client.post(f"/offers/{offer_id}/price-check", headers=auth(employee["access_token"]), json={"units": 1, "command_id": "expired-price-check"}).status_code == 409


def test_fulfillment_requires_captured_payment_and_safe_document_reference(client):
    supplier_id = active_supplier()
    supplier_session = login(client, "supplier@aftab.test")
    employee = login(client, "employee@aftab.test")
    offer = client.post("/supplier/offers", headers=auth(supplier_session["access_token"]), json={"supplier_id": supplier_id, "service_type": "tour", "title": "tour", "amount": 400_000, "available_units": 1, "valid_minutes": 60, "policy": policy(), "attributes": {}, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"}).json()
    checked = client.post(f"/offers/{offer['id']}/price-check", headers=auth(employee["access_token"]), json={"units": 1, "command_id": "tour-check-no-payment"}).json()
    booked = client.post("/orchestration/bookings", headers=auth(employee["access_token"]), json={"price_check_id": checked["id"], "command_id": "tour-book-no-payment"}).json()
    payload = {"command_id": "tour-fulfill-no-payment", "provider_reference": "supplier-ref", "document_reference": "https://unsafe.example/voucher"}
    assert client.post(f"/reservations/{booked['id']}/fulfill", headers=auth(supplier_session["access_token"]), json=payload).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BookingStatusHistory).where(BookingStatusHistory.reservation_id == booked["id"])) == 1


def test_manage_booking_refund_uses_verified_snapshot_and_captured_payment(client):
    employee = login(client, "employee@aftab.test")
    verified_policy = json.dumps(policy())
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="issued", price_snapshot_json='{"total_amount":1000000,"currency":"IRR"}', policy_at_booking_json=verified_policy, current_policy_json=verified_policy)
        db.add(reservation); db.flush()
        payment = PaymentIntent(tenant_id=user.tenant_id, reservation_id=reservation.id, user_id=user.id, command_id="manage-refund-payment", amount=1_000_000, captured_amount=1_000_000, status="captured")
        db.add(payment); db.commit(); reservation_id = reservation.id
    headers = {**auth(employee["access_token"]), "Idempotency-Key": "manage-refund-command"}
    requested = client.post(f"/reservations/{reservation_id}/service-requests", headers=headers, json={"request_type": "refund", "reason": "لغو سفر"})
    assert requested.status_code == 202 and requested.json()["quote"]["refundable_amount"] == 900_000
    assert requested.json()["refund_id"] is not None and requested.json()["booking_status"] == "refund_requested"
    assert client.post(f"/reservations/{reservation_id}/service-requests", headers=headers, json={"request_type": "refund", "reason": "لغو سفر"}).json()["refund_id"] == requested.json()["refund_id"]
    with SessionLocal() as db:
        refund = db.get(RefundRecord, requested.json()["refund_id"])
        assert refund.amount == 900_000 and refund.status == "requested"


def test_manage_booking_change_does_not_invent_quote(client):
    employee = login(client, "employee@aftab.test")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="flight", status="issued", price_snapshot_json='{"total_amount":1000000,"currency":"IRR"}', policy_at_booking_json="{}")
        db.add(reservation); db.commit(); reservation_id = reservation.id
    response = client.post(f"/reservations/{reservation_id}/service-requests", headers={**auth(employee["access_token"]), "Idempotency-Key": "manage-change-command"}, json={"request_type": "change", "reason": "تغییر تاریخ"})
    assert response.status_code == 202
    assert response.json()["quote"] is None and response.json()["consequence_preview"] == "requires_provider_review"
