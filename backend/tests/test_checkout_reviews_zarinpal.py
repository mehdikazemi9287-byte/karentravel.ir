import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select

from app import operations as models
from app.main import JWT_ISSUER, JWT_SECRET, SessionLocal, User
from app.providers import ProviderContext, ZarinPalAdapter


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email}); assert response.status_code == 200; return response.json()


def auth(session): return {"Authorization": f"Bearer {session['access_token']}"}


def reservation_fixture(client, suffix):
    supplier = login(client, "supplier@aftab.test")
    supplier_row = client.post("/supplier/onboarding", headers={**auth(supplier), "Idempotency-Key": f"checkout-supplier-{suffix}"}, json={"supplier_type": "hotel", "display_name": f"Checkout supplier {suffix}"}).json()
    policy = {"verified": True, "source": "contract:test", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True, "penalty_amount": 0}}
    offer = client.post("/supplier/offers", headers=auth(supplier), json={"supplier_id": supplier_row["id"], "service_type": "hotel", "title": "هتل Checkout", "amount": 2_000_000, "available_units": 3, "valid_minutes": 60, "policy": policy, "attributes": {}, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"}).json()
    employee = login(client, "employee@aftab.test")
    checked = client.post(f"/offers/{offer['id']}/price-check", headers=auth(employee), json={"units": 1, "command_id": f"checkout-price-{suffix}"}).json()
    reservation = client.post("/orchestration/bookings", headers=auth(employee), json={"price_check_id": checked["id"], "command_id": f"checkout-booking-{suffix}"}).json()
    traveller = client.post("/me/travellers", headers=auth(employee), json={"full_name": "مسافر Checkout", "profile_reference": "masked:test"}).json()
    return employee, reservation, traveller, offer


def test_checkout_is_resumable_server_authoritative_and_tenant_owned(client):
    suffix = uuid.uuid4().hex; employee, reservation, traveller, _ = reservation_fixture(client, suffix); faraz = login(client, "employee@faraz.test")
    created = client.post(f"/reservations/{reservation['id']}/checkout-sessions", headers=auth(employee), json={"command_id": f"checkout-{suffix}"})
    replay = client.post(f"/reservations/{reservation['id']}/checkout-sessions", headers=auth(employee), json={"command_id": f"checkout-{suffix}"})
    assert created.status_code == 201 and replay.json()["id"] == created.json()["id"]
    checkout_id = created.json()["id"]
    assert client.get(f"/checkout-sessions/{checkout_id}", headers=auth(faraz)).status_code == 404
    assert client.put(f"/checkout-sessions/{checkout_id}/steps/traveller", headers=auth(faraz), json={"command_id": f"cross-{suffix}", "traveller_ids": [traveller["id"]]}).status_code == 404
    step = client.put(f"/checkout-sessions/{checkout_id}/steps/traveller", headers=auth(employee), json={"command_id": f"traveller-{suffix}", "traveller_ids": [traveller["id"]]}); assert step.status_code == 200 and step.json()["stage"] == "traveller"
    recheck = client.put(f"/checkout-sessions/{checkout_id}/steps/recheck", headers=auth(employee), json={"command_id": f"recheck-{suffix}"}); assert recheck.status_code == 200 and recheck.json()["state"]["recheck"]["total_amount"] == 2_000_000
    assert client.put(f"/checkout-sessions/{checkout_id}/steps/policy", headers=auth(employee), json={"command_id": f"policy-no-{suffix}", "acknowledged": False}).status_code == 422
    assert client.put(f"/checkout-sessions/{checkout_id}/steps/policy", headers=auth(employee), json={"command_id": f"policy-{suffix}", "acknowledged": True}).json()["stage"] == "policy"
    assert client.put(f"/checkout-sessions/{checkout_id}/steps/funding", headers=auth(employee), json={"command_id": f"funding-tamper-{suffix}", "wallet_amount": 2_000_001}).status_code == 409
    assert client.put(f"/checkout-sessions/{checkout_id}/steps/funding", headers=auth(employee), json={"command_id": f"funding-{suffix}", "wallet_amount": 0}).json()["stage"] == "funding"
    assert client.put(f"/checkout-sessions/{checkout_id}/steps/invoice", headers=auth(employee), json={"command_id": f"invoice-{suffix}"}).json()["state"]["invoice_preview"]["subtotal_amount"] == 2_000_000
    payment = client.put(f"/checkout-sessions/{checkout_id}/steps/payment", headers=auth(employee), json={"command_id": f"payment-{suffix}"})
    assert payment.status_code == 200 and payment.json()["stage"] == "awaiting_payment" and payment.json()["payment_intent_id"]
    assert client.put(f"/checkout-sessions/{checkout_id}/steps/confirmation", headers=auth(employee), json={"command_id": f"confirmation-{suffix}"}).status_code == 409


def test_reviews_pagination_reporting_and_verified_flag_are_backend_only(client):
    suffix = uuid.uuid4().hex; employee = login(client, "employee@aftab.test"); backoffice = login(client, "backoffice@aftab.test")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test")); reservation = models.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="issued", provider_reference="verified-provider", price_snapshot_json='{"total_amount":1000}', policy_at_booking_json="{}", current_policy_json="{}"); db.add(reservation); db.commit(); reservation_id = reservation.id
    review = client.post("/reviews", headers=auth(employee), json={"rating": 5, "title": "تجربه واقعی", "body": "اقامت واقعی و تمیز با موقعیت مناسب", "service_type": "hotel", "service_reference": f"hotel:{suffix}", "reservation_id": reservation_id, "command_id": f"review-{suffix}"}).json(); assert review["verified_booking"] is True
    client.put(f"/reviews/{review['id']}/moderation", headers=auth(backoffice), json={"state": "approved", "reason": "بررسی انسانی"})
    listed = client.get(f"/reviews?service_type=hotel&service_reference=hotel:{suffix}&page=1&page_size=1", headers=auth(employee)); assert listed.status_code == 200 and listed.json()["total"] == 1 and listed.json()["items"][0]["verified_booking"] is True
    report_payload = {"reason": "irrelevant", "detail": "نیازمند بازبینی", "command_id": f"report-{suffix}"}
    first = client.post(f"/reviews/{review['id']}/reports", headers=auth(employee), json=report_payload); replay = client.post(f"/reviews/{review['id']}/reports", headers=auth(employee), json=report_payload)
    assert first.status_code == 201 and replay.json()["id"] == first.json()["id"]


class FakeZarinPalTransport:
    def __init__(self): self.calls = []
    def post_json(self, url, payload, timeout_seconds):
        self.calls.append((url, payload, timeout_seconds))
        if url.endswith("request.json"): return {"data": {"code": 100, "authority": "A" + "1" * 35}, "errors": []}
        return {"data": {"code": 100, "ref_id": 987654321}, "errors": []}


def test_zarinpal_adapter_request_verify_contract_without_claiming_sandbox_purchase():
    transport = FakeZarinPalTransport(); adapter = ZarinPalAdapter(mode="sandbox", merchant_id="12345678-1234-1234-1234-123456789012", callback_url="https://staging.example.test/payments/zarinpal/callback", transport=transport)
    context = ProviderContext(tenant_id=1, correlation_id="corr", idempotency_key="idem")
    initiated = adapter.execute("initiate", {"payment_intent_id": str(uuid.uuid4()), "amount": 1_000_000, "currency": "IRR", "callback_state": "signed-state"}, context)
    assert initiated["ok"] is True and initiated["redirect_url"].startswith("https://sandbox.zarinpal.com/pg/StartPay/") and transport.calls[0][1]["callback_url"].endswith("state=signed-state")
    verified = adapter.execute("verify", {"amount": 1_000_000, "currency": "IRR", "authority": initiated["authority"]}, context)
    assert verified == {"ok": True, "status": "verified", "provider": "zarinpal", "already_verified": False, "authority": "A" + "1" * 35, "ref_id": "987654321", "amount": 1_000_000}
    assert adapter.execute("verify", {"amount": 1_000_000, "currency": "IRR", "authority": "wrong"}, context)["reason"] == "authority_mismatch"


def test_zarinpal_callback_requires_server_verify_and_is_idempotent(client, monkeypatch):
    suffix = uuid.uuid4().hex; employee, reservation, _, _ = reservation_fixture(client, suffix); authority = "A" + "2" * 35
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test")); intent = models.PaymentIntent(tenant_id=user.tenant_id, reservation_id=reservation["id"], user_id=user.id, command_id=f"zarinpal-{suffix}", amount=2_000_000, currency="IRR", status="initiated", provider_key="zarinpal", provider_authority=authority); db.add(intent); db.commit(); intent_id = intent.id; tenant_id = user.tenant_id; user_id = user.id
    transport = FakeZarinPalTransport(); adapter = ZarinPalAdapter(mode="sandbox", merchant_id="12345678-1234-1234-1234-123456789012", callback_url="https://staging.example.test/payments/zarinpal/callback", transport=transport)
    from app import providers
    monkeypatch.setitem(providers.ADAPTERS, "payment", adapter)
    state = jwt.encode({"iss": JWT_ISSUER, "aud": "karenseir-zarinpal-callback", "tenant_id": tenant_id, "payment_intent_id": intent_id, "user_id": user_id, "amount": 2_000_000, "exp": datetime.now(timezone.utc) + timedelta(minutes=5), "iat": datetime.now(timezone.utc), "jti": str(uuid.uuid4())}, JWT_SECRET, algorithm="HS256")
    callback = f"/payments/zarinpal/callback?state={state}&Authority={authority}&Status=OK"
    first = client.get(callback); duplicate = client.get(callback)
    assert first.status_code == 200 and first.json()["payment_status"] == "captured" and duplicate.json()["status"] == "duplicate"
    wrong = client.get(f"/payments/zarinpal/callback?state={state}&Authority={'A'+'3'*35}&Status=OK"); assert wrong.status_code == 409
