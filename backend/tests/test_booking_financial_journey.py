import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import app.main as main_module
from app.main import SessionLocal, User
from app.operations import CreditAccount, EmployeeAssignment, Organization


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email}); assert response.status_code == 200; return response.json()


def auth(session): return {"Authorization": f"Bearer {session['access_token']}"}


class SuccessfulPaymentAdapter:
    def execute(self, operation, payload, context):
        return {"ok": True, "status": "accepted", "reference": "sandbox-payment-ref", "redirect_url": "https://sandbox.payment.test/pay/123"}


def fresh_employee(tenant_id, suffix):
    """A brand-new, isolated employee user per test, so an EmployeeAssignment to a
    test-specific Organization can never be ambiguous with another test's Organization
    for the same shared seeded account (the real /me/organization-credit and
    /reservations/.../installments lookups already pick a single match with no
    explicit tie-break, same pre-existing pattern as InstallmentPlan's org scoping)."""
    email = f"fin-employee-{suffix}@aftab.test"
    with SessionLocal() as db:
        db.add(User(tenant_id=tenant_id, email=email, name="کارمند سفر مالی", role="employee")); db.commit()
    return email


def reservation_fixture(client, suffix, amount=2_000_000, customer_email="employee@aftab.test"):
    supplier = login(client, "supplier@aftab.test")
    supplier_row = client.post("/supplier/onboarding", headers={**auth(supplier), "Idempotency-Key": f"fin-supplier-{suffix}"}, json={"supplier_type": "hotel", "display_name": f"Financial journey supplier {suffix}"}).json()
    policy = {"verified": True, "source": "contract:test", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True, "penalty_amount": 0}}
    offer = client.post("/supplier/offers", headers=auth(supplier), json={"supplier_id": supplier_row["id"], "service_type": "hotel", "title": "هتل سفر مالی", "amount": amount, "available_units": 3, "valid_minutes": 60, "policy": policy, "attributes": {}, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"}).json()
    employee = login(client, customer_email)
    checked = client.post(f"/offers/{offer['id']}/price-check", headers=auth(employee), json={"units": 1, "command_id": f"fin-price-{suffix}"}).json()
    reservation = client.post("/orchestration/bookings", headers=auth(employee), json={"price_check_id": checked["id"], "command_id": f"fin-booking-{suffix}"}).json()
    traveller = client.post("/me/travellers", headers=auth(employee), json={"full_name": "مسافر سفر مالی", "profile_reference": "masked:test"}).json()
    return employee, reservation, traveller


def test_organization_credit_and_wallet_funding_reserve_capture_release_and_isolation(client, monkeypatch):
    import app.providers as providers
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        tenant_id = db.scalar(select(User.tenant_id).where(User.email == "employee@aftab.test"))
    customer_email = fresh_employee(tenant_id, suffix)
    employee, reservation, traveller = reservation_fixture(client, suffix, amount=3_000_000, customer_email=customer_email)
    faraz = login(client, "employee@faraz.test")

    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == customer_email))
        organization = Organization(tenant_id=owner.tenant_id, name="سازمان اعتبار مالی", status="active"); db.add(organization); db.flush()
        db.add(EmployeeAssignment(tenant_id=owner.tenant_id, user_id=owner.id, organization_id=organization.id))
        credit_account = CreditAccount(tenant_id=owner.tenant_id, organization_id=organization.id, currency="IRR", limit_amount=1_500_000); db.add(credit_account); db.flush()
        db.commit(); credit_account_id = credit_account.id

    # Wallet is created self-service with zero balance; must be topped up by an admin allocate first.
    wallet = client.post("/me/wallets", headers={**auth(employee), "Idempotency-Key": f"fin-wallet-{suffix}"}, json={"currency": "IRR"}).json()
    org_admin = login(client, "org-admin@aftab.test")
    allocate = client.post(f"/wallets/{wallet['id']}/commands", headers=auth(org_admin), json={"command_id": f"fin-allocate-{suffix}", "entry_type": "allocate", "amount": 1_000_000})
    assert allocate.status_code == 200 and allocate.json()["available"] == 1_000_000

    # Organization credit is visible to the employee via /me/organization-credit with real ledger-derived balances.
    my_credit = client.get("/me/organization-credit", headers=auth(employee)).json()
    assert any(item["id"] == credit_account_id and item["available"] == 1_500_000 for item in my_credit)
    # The other tenant's employee must never see it.
    assert all(item["id"] != credit_account_id for item in client.get("/me/organization-credit", headers=auth(faraz)).json())

    checkout = client.post(f"/reservations/{reservation['id']}/checkout-sessions", headers=auth(employee), json={"command_id": f"fin-checkout-{suffix}"}).json()
    checkout_id = checkout["id"]
    client.put(f"/checkout-sessions/{checkout_id}/steps/traveller", headers=auth(employee), json={"command_id": f"fin-traveller-{suffix}", "traveller_ids": [traveller["id"]]})
    client.put(f"/checkout-sessions/{checkout_id}/steps/recheck", headers=auth(employee), json={"command_id": f"fin-recheck-{suffix}"})
    client.put(f"/checkout-sessions/{checkout_id}/steps/policy", headers=auth(employee), json={"command_id": f"fin-policy-{suffix}", "acknowledged": True})

    # Fail closed: organization credit above the real limit is rejected, nothing partially applied.
    over_limit = client.put(f"/checkout-sessions/{checkout_id}/steps/funding", headers=auth(employee), json={"command_id": f"fin-over-{suffix}", "wallet_amount": 0, "credit_amount": 2_000_000})
    assert over_limit.status_code == 409

    funding = client.put(f"/checkout-sessions/{checkout_id}/steps/funding", headers=auth(employee), json={"command_id": f"fin-funding-{suffix}", "wallet_amount": 500_000, "credit_amount": 1_000_000})
    assert funding.status_code == 200
    assert funding.json()["state"]["funding"] == {"wallet_amount": 500_000, "credit_amount": 1_000_000, "payable_amount": 1_500_000}

    # Reserved amounts are real and visible immediately (not fabricated success).
    assert next(w for w in client.get("/me/wallets", headers=auth(employee)).json() if w["id"] == wallet["id"])["reserved"] == 500_000
    credit_after_reserve = next(item for item in client.get("/me/organization-credit", headers=auth(employee)).json() if item["id"] == credit_account_id)
    assert credit_after_reserve["reserved"] == 1_000_000 and credit_after_reserve["available"] == 500_000

    client.put(f"/checkout-sessions/{checkout_id}/steps/invoice", headers=auth(employee), json={"command_id": f"fin-invoice-{suffix}"})
    payment_step = client.put(f"/checkout-sessions/{checkout_id}/steps/payment", headers=auth(employee), json={"command_id": f"fin-payment-{suffix}"})
    payment_intent_id = payment_step.json()["payment_intent_id"]

    # Real initiate step (sandboxed provider adapter, matching the established test double for this contract).
    monkeypatch.setitem(providers.ADAPTERS, "payment", SuccessfulPaymentAdapter())
    initiated = client.post(f"/payments/{payment_intent_id}/initiate", headers=auth(employee))
    assert initiated.status_code == 202

    # Capture the payable remainder via the real signed webhook (fail-closed contract already covered elsewhere).
    main_module.PAYMENT_WEBHOOK_SECRET = "test-fin-secret"
    payload = {"tenant_id": tenant_id, "payment_intent_id": payment_intent_id, "event_id": f"fin-capture-{suffix}", "status": "captured", "amount": 1_500_000}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(b"test-fin-secret", raw, hashlib.sha256).hexdigest()
    captured = client.post("/payments/callback/payment", content=raw, headers={"Content-Type": "application/json", "X-Payment-Signature": signature})
    assert captured.status_code == 200 and captured.json()["payment_status"] == "captured"

    # Fulfillment: real provider-free manual document reference, triggers confirmed->issued,
    # which must capture the reserved wallet/credit (reserved -> consumed) and auto-issue a real invoice.
    supplier = login(client, "supplier@aftab.test")
    fulfilled = client.post(f"/reservations/{reservation['id']}/fulfill", headers=auth(supplier), json={"provider_reference": "manual-ref", "document_reference": "document://fin-voucher", "command_id": f"fin-fulfill-{suffix}"})
    assert fulfilled.status_code == 200
    assert fulfilled.json()["invoice"] is not None and fulfilled.json()["invoice"]["total_amount"] >= 3_000_000

    wallet_after_capture = next(w for w in client.get("/me/wallets", headers=auth(employee)).json() if w["id"] == wallet["id"])
    assert wallet_after_capture["reserved"] == 0 and wallet_after_capture["consumed"] == 500_000
    credit_after_capture = next(item for item in client.get("/me/organization-credit", headers=auth(employee)).json() if item["id"] == credit_account_id)
    assert credit_after_capture["reserved"] == 0 and credit_after_capture["consumed"] == 1_000_000 and credit_after_capture["available"] == 500_000

    # The invoice is real, owner-scoped, appears on /me/invoices.
    invoices = client.get("/me/invoices", headers=auth(employee)).json()
    assert any(inv["reservation_id"] == reservation["id"] for inv in invoices)
    assert all(inv["reservation_id"] != reservation["id"] for inv in client.get("/me/invoices", headers=auth(faraz)).json())

    # Payment capture must appear on the real Trip Timeline (it was silent before this fix).
    trip_id = client.get("/me/trips", headers=auth(employee)).json()
    trip = next(t for t in trip_id if t["destination"])
    timeline = client.get(f"/trips/{trip['id']}/timeline", headers=auth(employee)).json()
    assert any(e["type"] == "payment.captured" and e["source"] == "system" for e in timeline["events"])


def test_organization_credit_reservation_release_on_cancellation(client):
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        tenant_id = db.scalar(select(User.tenant_id).where(User.email == "employee@aftab.test"))
    customer_email = fresh_employee(tenant_id, suffix)
    employee, reservation, traveller = reservation_fixture(client, suffix, amount=1_000_000, customer_email=customer_email)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == customer_email))
        organization = Organization(tenant_id=owner.tenant_id, name="سازمان اعتبار لغو", status="active"); db.add(organization); db.flush()
        db.add(EmployeeAssignment(tenant_id=owner.tenant_id, user_id=owner.id, organization_id=organization.id))
        credit_account = CreditAccount(tenant_id=owner.tenant_id, organization_id=organization.id, currency="IRR", limit_amount=1_000_000); db.add(credit_account); db.commit(); credit_account_id = credit_account.id; owner_id = owner.id
    checkout = client.post(f"/reservations/{reservation['id']}/checkout-sessions", headers=auth(employee), json={"command_id": f"rel-checkout-{suffix}"}).json()
    checkout_id = checkout["id"]
    client.put(f"/checkout-sessions/{checkout_id}/steps/traveller", headers=auth(employee), json={"command_id": f"rel-traveller-{suffix}", "traveller_ids": [traveller["id"]]})
    client.put(f"/checkout-sessions/{checkout_id}/steps/recheck", headers=auth(employee), json={"command_id": f"rel-recheck-{suffix}"})
    client.put(f"/checkout-sessions/{checkout_id}/steps/policy", headers=auth(employee), json={"command_id": f"rel-policy-{suffix}", "acknowledged": True})
    client.put(f"/checkout-sessions/{checkout_id}/steps/funding", headers=auth(employee), json={"command_id": f"rel-funding-{suffix}", "wallet_amount": 0, "credit_amount": 1_000_000})
    credit_reserved = next(item for item in client.get("/me/organization-credit", headers=auth(employee)).json() if item["id"] == credit_account_id)
    assert credit_reserved["reserved"] == 1_000_000 and credit_reserved["available"] == 0

    cancel = client.post(f"/reservations/{reservation['id']}/service-requests", headers={**auth(employee), "Idempotency-Key": f"rel-cancel-{suffix}"}, json={"request_type": "cancel"})
    assert cancel.status_code == 202

    with SessionLocal() as db:
        from app.operations import Reservation, transition_reservation
        row = db.scalar(select(Reservation).where(Reservation.id == reservation["id"]))
        transition_reservation(db, row, "cancelled", owner_id, f"rel-cancel-final-{suffix}")
        db.commit()

    credit_released = next(item for item in client.get("/me/organization-credit", headers=auth(employee)).json() if item["id"] == credit_account_id)
    assert credit_released["reserved"] == 0 and credit_released["consumed"] == 0 and credit_released["available"] == 1_000_000
