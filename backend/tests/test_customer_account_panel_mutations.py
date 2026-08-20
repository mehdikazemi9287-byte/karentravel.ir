import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.main import SessionLocal, User
from app.operations import Agency, Offer, Reservation, Supplier, Traveller


def auth(token): return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def test_profile_travellers_wallets_and_payments_are_owned_and_tenant_scoped(client):
    aftab = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    updated = client.put("/me/profile", headers=auth(aftab["access_token"]), json={"name": "کاربر ویرایش‌شده", "locale": "fa-IR"})
    assert updated.status_code == 200 and updated.json()["name"] == "کاربر ویرایش‌شده"
    created = client.post("/me/travellers", headers=auth(aftab["access_token"]), json={"full_name": "مسافر آفتاب", "profile_reference": "passport:masked"})
    assert created.status_code == 201
    traveller_id = created.json()["id"]
    assert client.put(f"/me/travellers/{traveller_id}", headers=auth(faraz["access_token"]), json={"full_name": "دسترسی غیرمجاز"}).status_code == 404
    assert client.post(f"/me/travellers/{traveller_id}/remove", headers=auth(faraz["access_token"])).status_code == 404
    assert client.get("/me/travellers", headers=auth(faraz["access_token"])).json() == []
    wallet_headers = {**auth(faraz["access_token"]), "Idempotency-Key": "wallet-create-faraz"}
    wallet = client.post("/me/wallets", headers=wallet_headers, json={"currency": "IRR"})
    replay = client.post("/me/wallets", headers=wallet_headers, json={"currency": "IRR"})
    assert wallet.status_code == 201 and replay.json()["id"] == wallet.json()["id"]
    assert client.get("/me/wallets", headers=auth(aftab["access_token"])).json() == []
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="awaiting_payment", price_snapshot_json='{"total_amount":1000,"currency":"IRR"}', policy_at_booking_json="{}", current_policy_json="{}")
        db.add(reservation); db.commit(); reservation_id = reservation.id
    intent = client.post(f"/reservations/{reservation_id}/payment-intents", headers={**auth(aftab["access_token"]), "Idempotency-Key": "payment-ui-aftab"})
    assert intent.status_code == 201 and client.get("/me/payments", headers=auth(aftab["access_token"])).json()[0]["amount"] == 1000
    assert client.get("/me/payments", headers=auth(faraz["access_token"])).json() == []


def test_support_messages_require_an_owned_scope(client):
    aftab = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="confirmed", price_snapshot_json="{}", policy_at_booking_json="{}", current_policy_json="{}")
        db.add(reservation); db.commit(); reservation_id = reservation.id
    assert client.post("/me/support/messages", headers=auth(faraz["access_token"]), json={"reservation_id": reservation_id, "body": "پیام غیرمجاز"}).status_code == 404
    created = client.post("/me/support/messages", headers=auth(aftab["access_token"]), json={"reservation_id": reservation_id, "body": "نیاز به بررسی رزرو دارم"})
    assert created.status_code == 201 and created.json()["sender_type"] == "customer"
    assert client.post("/me/support/messages", headers=auth(aftab["access_token"]), json={"body": "بدون زمینه"}).status_code == 422


def test_supplier_agency_backoffice_mutations_enforce_rbac_and_tenant(client):
    supplier_user = login(client, "supplier@aftab.test")
    agency_user = login(client, "agency@aftab.test")
    backoffice = login(client, "backoffice@aftab.test")
    employee = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    policy = {"verified": True, "source": "contract", "verified_at": datetime.now(timezone.utc).isoformat()}
    onboarded = client.post("/supplier/onboarding", headers={**auth(supplier_user["access_token"]), "Idempotency-Key": "supplier-mutation-onboard"}, json={"supplier_type": "hotel", "display_name": "تأمین‌کننده عملیات"})
    supplier_id = onboarded.json()["id"]
    offer = client.post("/supplier/offers", headers=auth(supplier_user["access_token"]), json={"supplier_id": supplier_id, "service_type": "hotel", "title": "موجودی عملیاتی", "amount": 1200, "available_units": 3, "valid_minutes": 60, "policy": policy, "attributes": {}, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"})
    assert offer.status_code == 201
    offer_id = offer.json()["id"]
    changed = client.put(f"/supplier/offers/{offer_id}", headers=auth(supplier_user["access_token"]), json={"available_units": 2, "status": "paused"})
    assert changed.status_code == 200 and changed.json()["available_units"] == 2
    assert client.put(f"/supplier/offers/{offer_id}", headers=auth(employee["access_token"]), json={"available_units": 1}).status_code == 403
    assert client.put(f"/supplier/offers/{offer_id}", headers=auth(faraz["access_token"]), json={"available_units": 1}).status_code == 403
    agency = client.post("/agency/sub-agencies", headers=auth(agency_user["access_token"]), json={"display_name": "آژانس قابل ویرایش", "markup_bps": 100, "commission_bps": 200})
    agency_id = agency.json()["id"]
    assert client.put(f"/agency/agencies/{agency_id}", headers=auth(agency_user["access_token"]), json={"markup_bps": 150}).json()["markup_bps"] == 150
    assert client.put(f"/agency/agencies/{agency_id}", headers=auth(employee["access_token"]), json={"markup_bps": 999}).status_code == 403
    suspended = client.put(f"/backoffice/suppliers/{supplier_id}/status", headers=auth(backoffice["access_token"]), json={"status": "suspended", "reason": "بررسی قرارداد"})
    assert suspended.status_code == 200 and suspended.json()["status"] == "suspended"
    assert client.put(f"/backoffice/suppliers/{supplier_id}/status", headers=auth(employee["access_token"]), json={"status": "active", "reason": "غیرمجاز"}).status_code == 403
