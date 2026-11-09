"""Regression tests for the 1405-08-17 security review (docs/reports/1405-08-17-security-review.md).

C-1  customer self-transition of a reservation to confirmed/issued/completed/refunded
H-1  organization admin minting wallet money / credit accounts with arbitrary limits
H-2  supplier role passing the inventory module's admin/staff checks
M-1  refund request for the full amount ignoring the verified cancellation penalty
M-2  /me/dashboard listing other users' legacy bookings in the same tenant
M-6  tenant-wide daily SMS cap on OTP / registration sends
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

import app.main as main_module
from maker_checker_helpers import approve, ensure_user
from app.main import AuditEvent, Booking, Hotel, SessionLocal, User
from app.operations import (OTPChallenge, PaymentIntent, RefundRecord, Reservation, Supplier, SupplierMembership,
                            Wallet, Organization, CreditAccount)


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _user(db, email):
    return db.scalar(select(User).where(User.email == email))


def _reservation(email, status="reserved", total=1_000_000, policy=None):
    with SessionLocal() as db:
        u = _user(db, email)
        r = Reservation(tenant_id=u.tenant_id, user_id=u.id, service_type="hotel", status=status,
                        price_snapshot_json=json.dumps({"total_amount": total, "currency": "IRR"}),
                        policy_at_booking_json=json.dumps(policy or {"verified": True}))
        db.add(r); db.commit()
        return r.id


# ---------------------------------------------------------------- C-1
@pytest.mark.parametrize("start,target", [("reserved", "confirmed"), ("awaiting_payment", "confirmed"), ("confirmed", "issued"),
                                          ("issued", "completed"), ("refund_requested", "refunded"), ("cancel_requested", "cancelled"),
                                          ("cancel_requested", "confirmed"), ("change_requested", "changed"), ("reserved", "expired")])
def test_customer_cannot_self_transition_reservation_to_operational_states(client, start, target):
    emp = login(client, "employee@aftab.test")
    rid = _reservation("employee@aftab.test", status=start)
    r = client.post(f"/reservations/{rid}/commands", headers=emp, json={"target": target, "command_id": f"c1-{uuid.uuid4().hex}"})
    assert r.status_code == 403, r.text
    with SessionLocal() as db:
        assert db.get(Reservation, rid).status == start


def test_customer_can_still_request_cancellation_or_change(client):
    emp = login(client, "employee@aftab.test")
    rid = _reservation("employee@aftab.test", status="confirmed")
    r = client.post(f"/reservations/{rid}/commands", headers=emp, json={"target": "cancel_requested", "command_id": f"c1-ok-{uuid.uuid4().hex}"})
    assert r.status_code == 200 and r.json()["status"] == "cancel_requested"
    rid2 = _reservation("employee@aftab.test", status="issued")
    r = client.post(f"/reservations/{rid2}/commands", headers=emp, json={"target": "change_requested", "command_id": f"c1-ok-{uuid.uuid4().hex}"})
    assert r.status_code == 200 and r.json()["status"] == "change_requested"


# ---------------------------------------------------------------- H-1
def _wallet_for(client, headers):
    return client.post("/me/wallets", headers={**headers, "Idempotency-Key": f"h1-w-{uuid.uuid4().hex}"}, json={"currency": "IRR"}).json()


def test_org_admin_cannot_fund_wallets_or_create_credit_accounts(client):
    adm = login(client, "org-admin@aftab.test"); emp = login(client, "employee@aftab.test")
    own = _wallet_for(client, adm); other = _wallet_for(client, emp)
    for wid in (own["id"], other["id"]):
        r = client.post(f"/wallets/{wid}/commands", headers=adm, json={"command_id": f"h1-{uuid.uuid4().hex}", "entry_type": "allocate", "amount": 9_000_000_000})
        assert r.status_code == 403, r.text
    with SessionLocal() as db:
        u = _user(db, "org-admin@aftab.test"); o = Organization(tenant_id=u.tenant_id, name="سازمان آزمون H-1", status="active"); db.add(o); db.commit(); oid = o.id
    for email in ("org-admin@aftab.test", "tenant-admin@aftab.test"):
        r = client.post(f"/organizations/{oid}/credit-accounts", headers=login(client, email), json={"organization_id": oid, "limit_amount": 999_999_999_999, "currency": "IRR", "command_id": f"h1-ca-{uuid.uuid4().hex}"})
        assert r.status_code == 403, (email, r.text)


def test_finance_funding_is_capped_audited_and_never_self_funding(client, monkeypatch):
    monkeypatch.setattr(main_module, "WALLET_FUNDING_MAX_PER_OPERATION", 50_000_000, raising=False)
    monkeypatch.setattr(main_module, "CREDIT_ACCOUNT_MAX_LIMIT", 200_000_000, raising=False)
    fin = login(client, "finance@aftab.test"); emp = login(client, "employee@aftab.test")
    emp_wallet = _wallet_for(client, emp); fin_wallet = _wallet_for(client, fin)
    assert client.post(f"/wallets/{fin_wallet['id']}/commands", headers=fin, json={"command_id": f"h1-self-{uuid.uuid4().hex}", "entry_type": "allocate", "amount": 1_000}).status_code == 403
    assert client.post(f"/wallets/{emp_wallet['id']}/commands", headers=fin, json={"command_id": f"h1-cap-{uuid.uuid4().hex}", "entry_type": "allocate", "amount": 50_000_001}).status_code == 409
    ok = client.post(f"/wallets/{emp_wallet['id']}/commands", headers=fin, json={"command_id": f"h1-ok-{uuid.uuid4().hex}", "entry_type": "allocate", "amount": 1_000_000})
    assert ok.status_code == 202 and ok.json()["status"] == "pending_approval"
    assert approve(client, ok, login(client, "platform-admin@aftab.test"))["result"]["available"] >= 1_000_000
    # manual reserve/capture/release/reverse of the ledger is never an API operation
    assert client.post(f"/wallets/{emp_wallet['id']}/commands", headers=fin, json={"command_id": f"h1-rev-{uuid.uuid4().hex}", "entry_type": "reverse_capture", "amount": 1}).status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == "wallet.allocate", AuditEvent.detail.contains(emp_wallet["id"]))) == 1
        u = _user(db, "finance@aftab.test"); o = Organization(tenant_id=u.tenant_id, name="سازمان آزمون سقف", status="active"); db.add(o); db.commit(); oid = o.id
    over = client.post(f"/organizations/{oid}/credit-accounts", headers=fin, json={"organization_id": oid, "limit_amount": 200_000_001, "currency": "IRR", "command_id": f"h1-ca-{uuid.uuid4().hex}"})
    assert over.status_code == 409
    created = client.post(f"/organizations/{oid}/credit-accounts", headers=fin, json={"organization_id": oid, "limit_amount": 100_000_000, "currency": "IRR", "command_id": f"h1-ca-{uuid.uuid4().hex}"})
    assert created.status_code == 202
    assert approve(client, created, login(client, "platform-admin@aftab.test"))["result"]["limit_amount"] == 100_000_000
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == "credit_account.created", AuditEvent.detail.contains(oid))) == 1


def test_org_admin_cannot_move_organization_credit_ledger(client):
    with SessionLocal() as db:
        u = _user(db, "org-admin@aftab.test"); o = Organization(tenant_id=u.tenant_id, name="سازمان آزمون دفتر", status="active"); db.add(o); db.flush()
        ca = CreditAccount(tenant_id=u.tenant_id, organization_id=o.id, currency="IRR", limit_amount=1_000_000); db.add(ca); db.commit(); caid = ca.id
    r = client.post(f"/organization-credit/{caid}/commands", headers=login(client, "org-admin@aftab.test"), json={"command_id": f"h1-oc-{uuid.uuid4().hex}", "entry_type": "reserve", "amount": 1})
    assert r.status_code == 403


# ---------------------------------------------------------------- H-2
def _supplier_with_membership(email="supplier@aftab.test"):
    with SessionLocal() as db:
        u = _user(db, email)
        s = Supplier(tenant_id=u.tenant_id, supplier_type="travel", display_name=f"تأمین‌کننده {uuid.uuid4().hex[:4]}", status="active"); db.add(s); db.flush()
        db.add(SupplierMembership(tenant_id=u.tenant_id, user_id=u.id, supplier_id=s.id, role="owner")); db.commit()
        return s.id


def test_supplier_cannot_use_tenant_staff_inventory_endpoints(client):
    _supplier_with_membership()
    sup = login(client, "supplier@aftab.test")
    assert client.post("/inventory/contract-templates", headers=sup, json={"service_type": "any", "title": "قرارداد", "body": "متن {{customer_name}}", "status": "active"}).status_code == 403
    assert client.get("/inventory/contract-templates", headers=sup).status_code == 403
    assert client.get("/commerce/reports/sales", headers=sup).status_code == 403
    assert client.post("/inventory/routes", headers=sup, json={"origin": "THR", "destination": "MHD", "origin_city": "تهران", "destination_city": "مشهد", "scope": "domestic", "status": "active"}).status_code == 403
    assert client.post("/inventory/suppliers", headers=sup, json={"name": "تأمین‌کننده جعلی", "supplier_type": "airline"}).status_code == 403


def test_supplier_only_sees_and_edits_its_own_flight_series(client):
    own_supplier = _supplier_with_membership()
    admin = login(client, "platform-admin@aftab.test"); sup = login(client, "supplier@aftab.test")
    with SessionLocal() as db:
        u = _user(db, "platform-admin@aftab.test")
        other = Supplier(tenant_id=u.tenant_id, supplier_type="airline", display_name="ایرلاین دیگر", status="active"); db.add(other); db.commit(); other_id = other.id
    import random, string
    o, d = "".join(random.choices(string.ascii_uppercase, k=3)), "".join(random.choices(string.ascii_uppercase, k=3))
    while d == o: d = "".join(random.choices(string.ascii_uppercase, k=3))
    route = client.post("/inventory/routes", headers=admin, json={"origin": o, "destination": d, "origin_city": "الف", "destination_city": "ب", "scope": "domestic", "status": "active"}).json()
    base = {"route_id": route["id"], "airline_code": "KS", "flight_number": "100", "date_from": "2099-01-01", "date_to": "2099-01-10", "capacity": 10, "adult_fare": 1_000_000, "child_fare": 800_000, "infant_fare": 100_000,
            "schedule": {"0": {"time": "08:00", "duration": 60}}}
    other_series = client.post("/inventory/flight-series", headers=admin, json={**base, "supplier_id": other_id})
    assert other_series.status_code == 201, other_series.text
    # supplier may manage a series of its own supplier ...
    mine = client.post("/inventory/flight-series", headers=sup, json={**base, "flight_number": "101", "supplier_id": own_supplier})
    assert mine.status_code == 201, mine.text
    # ... but never create/modify/generate one for another supplier, nor read passenger manifests
    assert client.post("/inventory/flight-series", headers=sup, json={**base, "flight_number": "102", "supplier_id": other_id}).status_code == 403
    assert client.put(f"/inventory/flight-series/{other_series.json()['id']}", headers=sup, json={**base, "supplier_id": own_supplier}).status_code == 403
    assert client.post(f"/inventory/flight-series/{other_series.json()['id']}/generate", headers=sup).status_code == 403
    listed = client.get("/inventory/flight-series", headers=sup).json()["items"]
    assert all(s["supplier_id"] == own_supplier or s["supplier_id"] in _scope("supplier@aftab.test") for s in listed)
    assert other_series.json()["id"] not in {s["id"] for s in listed}
    gen = client.post(f"/inventory/flight-series/{other_series.json()['id']}/generate", headers=admin).json()
    assert gen["created"] >= 1
    flight = client.get("/inventory/flights", headers=admin, params={"series_id": other_series.json()["id"]}).json()["items"][0]
    assert client.get(f"/inventory/flights/{flight['id']}/manifest", headers=sup).status_code == 403
    assert client.put(f"/inventory/flights/{flight['id']}", headers=sup, json={"capacity": 1}).status_code == 403
    assert flight["id"] not in {f["id"] for f in client.get("/inventory/flights", headers=sup).json()["items"]}
    assert client.get(f"/inventory/flights/{flight['id']}/manifest", headers=admin).status_code == 200


def _scope(email):
    with SessionLocal() as db:
        u = _user(db, email)
        return set(db.scalars(select(SupplierMembership.supplier_id).where(SupplierMembership.user_id == u.id)).all())


# ---------------------------------------------------------------- M-1
def _captured_payment(reservation_id, email, amount):
    with SessionLocal() as db:
        u = _user(db, email)
        p = PaymentIntent(tenant_id=u.tenant_id, reservation_id=reservation_id, user_id=u.id, command_id=f"m1-{uuid.uuid4().hex}", amount=amount, status="captured", captured_amount=amount)
        db.add(p); db.commit(); return p.id


def test_refund_request_respects_verified_cancellation_penalty(client):
    emp = login(client, "employee@aftab.test")
    policy = {"verified": True, "source": "supplier-contract", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True, "penalty_amount": 300_000}}
    rid = _reservation("employee@aftab.test", status="cancel_requested", total=1_000_000, policy=policy)
    pid = _captured_payment(rid, "employee@aftab.test", 1_000_000)
    full = client.post(f"/payments/{pid}/refunds", headers=emp, json={"amount": 1_000_000, "command_id": f"m1-full-{uuid.uuid4().hex}"})
    assert full.status_code == 409, full.text
    ok = client.post(f"/payments/{pid}/refunds", headers=emp, json={"amount": 700_000, "command_id": f"m1-ok-{uuid.uuid4().hex}"})
    assert ok.status_code == 202 and ok.json()["status"] == "requested" and ok.json()["penalty_amount"] == 300_000
    assert client.post(f"/payments/{pid}/refunds", headers=emp, json={"amount": 1, "command_id": f"m1-more-{uuid.uuid4().hex}"}).status_code == 409


def test_refund_without_verified_policy_waits_for_finance_review(client, monkeypatch):
    emp = login(client, "employee@aftab.test"); fin = login(client, "finance@aftab.test")
    rid = _reservation("employee@aftab.test", status="confirmed", total=1_000_000)
    pid = _captured_payment(rid, "employee@aftab.test", 1_000_000)
    r = client.post(f"/payments/{pid}/refunds", headers=emp, json={"amount": 1_000_000, "command_id": f"m1-rev-{uuid.uuid4().hex}"})
    assert r.status_code == 202 and r.json()["status"] == "pending_review" and r.json()["penalty_status"] == "pending_review"
    # a provider callback can never settle a refund finance has not approved
    monkeypatch.setattr(main_module, "PAYMENT_WEBHOOK_SECRET", "m1-secret")
    with SessionLocal() as db:
        tenant_id = _user(db, "employee@aftab.test").tenant_id
    raw = json.dumps({"tenant_id": tenant_id, "payment_intent_id": pid, "event_id": f"m1-{uuid.uuid4().hex}", "status": "refund_succeeded", "amount": 1_000_000, "refund_id": r.json()["id"]}).encode()
    sig = hmac.new(b"m1-secret", raw, hashlib.sha256).hexdigest()
    assert client.post("/payments/callback/payment", content=raw, headers={"Content-Type": "application/json", "X-Payment-Signature": sig}).status_code == 409
    # the customer cannot approve it; finance approves a reviewed (penalised) amount
    assert client.post(f"/refunds/{r.json()['id']}/review", headers=emp, json={"approve": True, "amount": 1_000_000}).status_code == 403
    assert client.post(f"/refunds/{r.json()['id']}/review", headers=fin, json={"approve": True, "amount": 1_000_001}).status_code == 409
    approved = client.post(f"/refunds/{r.json()['id']}/review", headers=fin, json={"approve": True, "amount": 800_000, "note": "جریمه طبق قرارداد"})
    assert approved.status_code == 200 and approved.json()["status"] == "requested" and approved.json()["amount"] == 800_000
    with SessionLocal() as db:
        assert db.get(RefundRecord, r.json()["id"]).amount == 800_000


# ---------------------------------------------------------------- M-2
def test_dashboard_lists_only_the_callers_own_legacy_bookings(client):
    with SessionLocal() as db:
        other = _user(db, "welfare@aftab.test"); hotel = db.scalar(select(Hotel).order_by(Hotel.id))
        b = Booking(tenant_id=other.tenant_id, user_id=other.id, hotel_id=hotel.id, nights=1, total_amount=1); db.add(b); db.commit(); bid = b.id
    ids = {b["id"] for b in client.get("/me/dashboard", headers=login(client, "employee@aftab.test")).json()["bookings"]}
    assert bid not in ids
    assert bid in {b["id"] for b in client.get("/me/dashboard", headers=login(client, "welfare@aftab.test")).json()["bookings"]}


# ---------------------------------------------------------------- M-6
class _CountingOTP:
    def __init__(self): self.calls = 0
    def execute(self, operation, payload, context):
        self.calls += 1
        return {"ok": True, "status": "accepted", "reference": "counting-adapter"}


def test_tenant_daily_sms_cap_stops_otp_and_registration_sends(client, monkeypatch):
    import app.providers as providers
    adapter = _CountingOTP(); monkeypatch.setitem(providers.ADAPTERS, "otp", adapter)
    suffix = uuid.uuid4().int % 10_000_000
    email, mobile = f"sms-cap-{suffix}@aftab.test", f"+98912{suffix:07d}"
    with SessionLocal() as db:
        tenant_id = _user(db, "employee@aftab.test").tenant_id
        db.add(User(tenant_id=tenant_id, email=email, name="کاربر آزمون سقف پیامک", role="employee", mobile_e164=mobile)); db.commit()
        sent_today = db.scalar(select(func.count(OTPChallenge.id)).where(OTPChallenge.tenant_id == tenant_id))
    monkeypatch.setattr(main_module, "SMS_DAILY_CAP_PER_TENANT", sent_today, raising=False)
    r = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": email})
    assert r.status_code == 202 and adapter.calls == 0
    monkeypatch.setattr(main_module, "SMS_DAILY_CAP_PER_TENANT", sent_today + 1, raising=False)
    client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": email})
    assert adapter.calls == 1
    # registration path (consumer tenant) is capped by the same setting
    monkeypatch.setattr(main_module, "SMS_DAILY_CAP_PER_TENANT", 0, raising=False)
    r = client.post("/auth/register/request", json={"mobile": f"0913{suffix:07d}"})
    assert r.status_code == 202 and adapter.calls == 1


def test_supplier_cannot_touch_other_suppliers_hotel_contracts_or_agency_quotas(client):
    from datetime import date, timedelta
    from app.catalog import CatalogHotel
    own_supplier = _supplier_with_membership()
    admin = login(client, "platform-admin@aftab.test"); sup = login(client, "supplier@aftab.test")
    hid = "t-" + uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        db.add(CatalogHotel(id=hid, slug=f"sec-stay-{hid}", country_code="IR", hotel_type="hotel", name_fa="هتل آزمون امنیت", stars=3, status="published", source="inhouse")); db.commit()
    other = client.post("/inventory/suppliers", headers=admin, json={"name": "هتل‌دار دیگر", "supplier_type": "hotel"}).json()
    d0 = date.today() + timedelta(days=10)
    body = {"hotel_id": hid, "title": "قرارداد آزمون", "valid_from": d0.isoformat(), "valid_to": (d0 + timedelta(days=5)).isoformat()}
    theirs = client.post("/stays/contracts", headers=admin, json={**body, "supplier_id": other["id"]}).json()
    room = client.post(f"/stays/contracts/{theirs['id']}/rooms", headers=admin, json={"name": "دوتخته", "board": "BB", "max_adults": 2, "max_children": 0, "extra_beds": 0}).json()
    assert client.post("/stays/contracts", headers=sup, json={**body, "supplier_id": other["id"]}).status_code == 403
    assert client.put(f"/stays/contracts/{theirs['id']}", headers=sup, json={**body, "supplier_id": own_supplier}).status_code == 403
    assert client.get(f"/stays/contracts/{theirs['id']}/rooms", headers=sup).status_code == 403
    assert client.put(f"/stays/rooms/{room['id']}/calendar", headers=sup, json={"date_from": d0.isoformat(), "date_to": d0.isoformat(), "weekdays": [0, 1, 2, 3, 4, 5, 6], "allotment": 1, "price": 1}).status_code == 403
    assert theirs["id"] not in {c["id"] for c in client.get("/stays/contracts", headers=sup).json()["items"]}
    assert client.post("/stays/contracts", headers=sup, json={**body, "supplier_id": own_supplier}).status_code == 201
    assert client.get("/charter-quotas/agencies", headers=sup).status_code == 403



# ---------------------------------------------------------------- H-1 maker-checker
def _pending_wallet_request(client, fin, amount=2_000_000):
    emp_wallet = _wallet_for(client, login(client, "employee@aftab.test"))
    r = client.post(f"/wallets/{emp_wallet['id']}/commands", headers=fin, json={"command_id": f"mc-{uuid.uuid4().hex}", "entry_type": "allocate", "amount": amount})
    assert r.status_code == 202, r.text
    return emp_wallet, r.json()


def test_wallet_funding_needs_a_different_approver_and_executes_once(client):
    fin = login(client, "finance@aftab.test")
    wallet, body = _pending_wallet_request(client, fin)
    rid = body["approval_request"]["id"]
    before = body["available"]
    assert client.get(f"/wallets/{wallet['id']}", headers=fin).json()["available"] == before  # nothing moved yet
    # the maker cannot approve or reject their own request
    assert client.post(f"/maker-checker/requests/{rid}/approve", json={}, headers=fin).status_code == 403
    assert client.post(f"/maker-checker/requests/{rid}/reject", json={}, headers=fin).status_code == 403
    # a non-finance user cannot approve, and does not see it
    emp = login(client, "employee@aftab.test")
    assert client.post(f"/maker-checker/requests/{rid}/approve", json={}, headers=emp).status_code == 403
    assert rid not in {i["id"] for i in client.get("/maker-checker/requests", headers=emp).json()["items"]}
    # a second finance user sees it as decidable and approves
    fin2 = login(client, ensure_user("finance@aftab.test", "finance_operator", "finance-checker"))
    listed = {i["id"]: i for i in client.get("/maker-checker/requests", headers=fin2).json()["items"]}
    assert listed[rid]["can_decide"] is True and listed[rid]["kind"] == "wallet.fund"
    first = client.post(f"/maker-checker/requests/{rid}/approve", json={"note": "واریز بانکی بررسی شد"}, headers=fin2)
    assert first.status_code == 200 and first.json()["result"]["available"] == before + 2_000_000
    replay = client.post(f"/maker-checker/requests/{rid}/approve", json={}, headers=fin2)
    assert replay.status_code == 200 and replay.json()["result"]["entry_id"] == first.json()["result"]["entry_id"]
    assert client.post(f"/maker-checker/requests/{rid}/approve", json={}, headers=login(client, "platform-admin@aftab.test")).status_code == 409
    assert client.get(f"/wallets/{wallet['id']}", headers=fin).json()["available"] == before + 2_000_000
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == "maker_checker.wallet.fund.requested", AuditEvent.detail.contains(rid))) == 1
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == "maker_checker.wallet.fund.approved", AuditEvent.detail.contains(rid))) == 1
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == "wallet.allocate", AuditEvent.detail.contains(rid))) == 1


def test_rejected_and_expired_funding_requests_never_move_the_ledger(client):
    from datetime import timedelta
    from app.approvals import MakerCheckerRequest
    fin = login(client, "finance@aftab.test"); checker = login(client, "platform-admin@aftab.test")
    wallet, body = _pending_wallet_request(client, fin)
    before = body["available"]
    rid = body["approval_request"]["id"]
    rejected = client.post(f"/maker-checker/requests/{rid}/reject", json={"note": "سند بانکی ناقص"}, headers=checker)
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert client.post(f"/maker-checker/requests/{rid}/approve", json={}, headers=checker).status_code == 409
    wallet2, body2 = _pending_wallet_request(client, fin)
    with SessionLocal() as db:
        row = db.get(MakerCheckerRequest, body2["approval_request"]["id"]); row.expires_at = row.created_at - timedelta(seconds=1); db.commit()
    assert client.post(f"/maker-checker/requests/{body2['approval_request']['id']}/approve", json={}, headers=checker).status_code == 409
    assert wallet2["id"] == wallet["id"]  # one IRR wallet per user
    assert client.get(f"/wallets/{wallet['id']}", headers=fin).json()["available"] == before
    # same command id + different amount is a conflict, same body is the same request
    cmd = f"mc-idem-{uuid.uuid4().hex}"
    a = client.post(f"/wallets/{wallet['id']}/commands", headers=fin, json={"command_id": cmd, "entry_type": "allocate", "amount": 5})
    b = client.post(f"/wallets/{wallet['id']}/commands", headers=fin, json={"command_id": cmd, "entry_type": "allocate", "amount": 5})
    assert a.json()["approval_request"]["id"] == b.json()["approval_request"]["id"]
    assert client.post(f"/wallets/{wallet['id']}/commands", headers=fin, json={"command_id": cmd, "entry_type": "allocate", "amount": 6}).status_code == 409


def test_checker_may_not_approve_funding_of_their_own_wallet(client):
    fin = login(client, "finance@aftab.test")
    fin2_email = ensure_user("finance@aftab.test", "finance_operator", "finance-checker")
    fin2 = login(client, fin2_email)
    own = _wallet_for(client, fin2)
    before = client.get(f"/wallets/{own['id']}", headers=fin).json()["available"]
    r = client.post(f"/wallets/{own['id']}/commands", headers=fin, json={"command_id": f"mc-own-{uuid.uuid4().hex}", "entry_type": "allocate", "amount": 1_000})
    assert r.status_code == 202
    assert client.post(f"/maker-checker/requests/{r.json()['approval_request']['id']}/approve", json={}, headers=fin2).status_code == 403
    assert client.get(f"/wallets/{own['id']}", headers=fin).json()["available"] == before
