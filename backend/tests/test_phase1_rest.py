"""Panels Phase 1 (rest) + security follow-ups: wallet decrease maker-checker, global per-destination SMS cap,
/me/capabilities, /panel/today, configurable SLA, dated tax rates, failed payments, change-price proposals, scoped
passengers, settlement import and bank payout batches (app/panel_ops.py, app/sms_guard.py)."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

import app.providers as providers_module
from app import after_sales as A
from app import panel_ops as P
from app import sms_guard
from app.main import AuditEvent, SessionLocal, Tenant, User
from app.operations import (Agency, AgencyMembership, EmployeeAssignment, OTPChallenge, Organization, PaymentIntent, RefundRecord, Reservation)

from maker_checker_helpers import approve


def _user(role: str, tenant_slug: str = "aftab-bank", mobile: str | None = None) -> str:
    email = f"p1r-{role}-{uuid.uuid4().hex[:10]}@{tenant_slug}.test"
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        db.add(User(tenant_id=tenant.id, email=email, name=f"آزمون {role}", role=role, mobile_e164=mobile)); db.commit()
    return email


def login(client, email: str) -> dict:
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def key() -> dict:
    return {"Idempotency-Key": f"p1r-{uuid.uuid4().hex}"}


def uid(email: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def reservation(email: str, total=20_000_000, status="confirmed", pay_status="captured", authority=None) -> tuple[str, str]:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        r = Reservation(tenant_id=u.tenant_id, user_id=u.id, service_type="flight", status=status, booking_reference=f"KR-{uuid.uuid4().hex[:8].upper()}",
                        price_snapshot_json=json.dumps({"total_amount": total, "currency": "IRR"}))
        db.add(r); db.flush()
        p = PaymentIntent(tenant_id=u.tenant_id, reservation_id=r.id, user_id=u.id, command_id=f"p1r-pay-{uuid.uuid4().hex}", amount=total,
                          captured_amount=total if pay_status == "captured" else 0, status=pay_status, provider_authority=authority or f"A{uuid.uuid4().hex[:20]}")
        db.add(p); db.commit()
        return r.id, p.id


@pytest.fixture()
def people(client):
    cust = _user("customer"); ops = _user("backoffice_expert"); fin1 = _user("finance_operator"); fin2 = _user("finance_operator"); admin = _user("tenant_admin")
    return {"cust_email": cust, "cust": login(client, cust), "ops": login(client, ops), "fin1": login(client, fin1), "fin2": login(client, fin2),
            "admin": login(client, admin), "ops_email": ops, "fin1_email": fin1}


# ---------------------------------------------------------------------------------------------- 1a wallet decrease
def test_commerce_wallet_decrease_needs_a_second_finance_user(client, people):
    p = people
    target = _user("customer")
    tid = uid(target)
    inc = client.post(f"/commerce/users/{tid}/adjust", json={"target": "wallet", "direction": "increase", "amount": 9_000_000, "description": "شارژ"}, headers=p["fin1"])
    approve(client, inc, p["fin2"])
    bal = lambda: client.get(f"/commerce/users/{tid}/account", headers=p["fin1"]).json()["wallet"]["available"]
    assert bal() == 9_000_000
    assert client.post(f"/commerce/users/{tid}/adjust", json={"target": "wallet", "direction": "decrease", "amount": 9_000_001, "description": "کسر"}, headers=p["fin1"]).status_code == 409
    dec = client.post(f"/commerce/users/{tid}/adjust", json={"target": "wallet", "direction": "decrease", "amount": 4_000_000, "description": "کسر اشتباه واریز"}, headers=p["fin1"])
    assert dec.status_code == 202 and dec.json()["status"] == "pending_approval"
    assert bal() == 9_000_000  # nothing moved yet
    assert client.post(f"/maker-checker/requests/{dec.json()['approval_request']['id']}/approve", json={}, headers=p["fin1"]).status_code == 403  # maker
    approve(client, dec, p["fin2"])
    assert bal() == 5_000_000


# ---------------------------------------------------------------------------------------------- 1b SMS cap
class _Recorder:
    def __init__(self):
        self.calls = []

    def execute(self, operation, payload, context):
        self.calls.append(payload)
        return {"ok": True, "status": "accepted", "reference": "rec"}


def test_reserve_sms_caps_hour_and_day_atomically(monkeypatch):
    monkeypatch.setattr(sms_guard, "SMS_DEST_MAX_PER_HOUR", 3)
    monkeypatch.setattr(sms_guard, "SMS_DEST_MAX_PER_DAY", 5)
    dest, day_start = f"+98912{uuid.uuid4().int % 10**7:07d}", 86400 * 20833.0

    def attempt(db, at):  # like the OTP endpoints: a refused attempt is rolled back and sends nothing
        with db.begin_nested() as sp:
            ok = sms_guard.reserve_sms(db, dest, now=at)
            if not ok:
                sp.rollback()
        return ok

    with SessionLocal() as db:
        assert [attempt(db, day_start) for _ in range(4)] == [True, True, True, False]       # hour cap
        assert [attempt(db, day_start + 3600) for _ in range(3)] == [True, True, False]      # day cap (5)
        assert attempt(db, day_start + 86400) is True                                      # next day
        assert sms_guard.reserve_sms(db, "+989120000001", now=day_start) is True            # other numbers are independent
        db.commit()
        stored = db.scalars(select(sms_guard.SmsDestinationCounter.destination_hash)).all()
        assert all(len(h) == 64 and dest[1:] not in h for h in stored)                     # only a keyed hash is stored


def test_otp_cap_is_global_across_tenants_and_enumeration_safe(client, monkeypatch):
    monkeypatch.setattr(sms_guard, "SMS_DEST_MAX_PER_HOUR", 2)
    rec = _Recorder()
    monkeypatch.setitem(providers_module.ADAPTERS, "otp", rec)
    mobile = f"+98912{uuid.uuid4().int % 10**7:07d}"
    email = _user("customer", "aftab-bank", mobile=mobile)
    bodies = [client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "0" + mobile[3:]}) for _ in range(2)]
    assert all(b.status_code == 202 for b in bodies) and len(rec.calls) == 2
    # a third request (and the consumer-registration path from another tenant) for the same number sends nothing ...
    third = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "0" + mobile[3:]})
    reg = client.post("/auth/register/request", json={"mobile": "0" + mobile[3:], "name": "آزمون"})
    assert len(rec.calls) == 2
    # ... and answers exactly like any unknown number would (same status, same keys)
    unknown = client.post("/auth/otp/request", json={"tenant_slug": "aftab-bank", "identifier": "09129999999"})
    assert third.status_code == unknown.status_code == 202 and set(third.json()) == set(unknown.json()) == {"status", "challenge_id", "expires_in"}
    assert reg.status_code == 202 and reg.json()["status"] == "accepted"
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        assert db.scalar(select(func.count()).select_from(OTPChallenge).where(OTPChallenge.user_id == u.id)) == 2


# ---------------------------------------------------------------------------------------------- 2 capabilities + today
def test_capabilities_follow_the_rbac_table_and_memberships(client, people):
    fin = client.get("/me/capabilities", headers=people["fin1"]).json()
    assert "refund:manage" in fin["permissions"] and "tenant:manage" not in fin["permissions"] and fin["source"] == "security.ROLE_PERMISSIONS"
    agency_email = _user("agency_partner")
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == agency_email))
        ag = Agency(tenant_id=u.tenant_id, display_name="آژانس آزمون قابلیت", status="active"); db.add(ag); db.flush()
        db.add(AgencyMembership(tenant_id=u.tenant_id, user_id=u.id, agency_id=ag.id, agency_role="agent")); db.commit()
        agency_id = ag.id
    cap = client.get("/me/capabilities", headers=login(client, agency_email)).json()
    assert cap["memberships"]["agencies"] == [{"id": agency_id, "name": "آژانس آزمون قابلیت", "role": "agent"}] and "agency:manage" in cap["permissions"]
    admin = client.get("/me/capabilities", headers=login(client, "platform-admin@aftab.test")).json()
    assert "refund:manage" in admin["permissions"] and "platform:manage" in admin["permissions"]
    assert client.get("/me/capabilities").status_code in (401, 403)


def test_today_is_role_aware_and_shows_sla_breaches_and_pending_approvals(client, people):
    p = people
    rid, _ = reservation(p["cust_email"], status="issued")
    req = client.post(f"/reservations/{rid}/service-requests", headers={**p["cust"], **key()}, json={"request_type": "cancel", "reason": "تغییر برنامه", "refund_destination": "wallet"})
    assert req.status_code == 202, req.text
    with SessionLocal() as db:  # the request has been waiting 6 hours; default SLA for «submitted» is 4h
        h = db.scalar(select(A.ServiceRequestHandling).where(A.ServiceRequestHandling.request_id == req.json()["id"]))
        h.status_since = datetime.now(timezone.utc) - timedelta(hours=6); db.commit()
    ops = client.get("/panel/today", headers=p["ops"]).json()
    keys = {i["key"]: i for i in ops["items"]}
    assert keys["ops.sla_breached"]["level"] == "bad" and keys["ops.sla_breached"]["count"] >= 1 and ops["items"][0]["level"] == "bad"
    assert "finance.refunds_to_prepare" not in keys
    cust = client.get("/panel/today", headers=p["cust"]).json()
    assert not any(i["key"].startswith(("ops.", "finance.")) for i in cust["items"])
    # a maker-checker request appears for the other finance user, not for its maker
    tid = uid(_user("customer"))
    client.post(f"/commerce/users/{tid}/adjust", json={"target": "wallet", "direction": "increase", "amount": 1_000_000, "description": "شارژ"}, headers=p["fin1"])
    f1 = {i["key"] for i in client.get("/panel/today", headers=p["fin1"]).json()["items"]}
    f2 = {i["key"]: i for i in client.get("/panel/today", headers=p["fin2"]).json()["items"]}
    assert "approvals.pending_for_me" in f2 and f2["approvals.pending_for_me"]["href"] == "/finance/approvals"
    assert "approvals.pending_for_me" not in f1 or client.get("/panel/today", headers=p["fin1"]).json()["approvals"] != []


# ---------------------------------------------------------------------------------------------- 3 SLA, tax rates, failed payments
def test_sla_is_admin_editable_with_audit_and_drives_the_queue_eta(client, people):
    p = people
    body = {"request_type": "change", "status": "submitted", "minutes": 30, "reason": "هدف تازهٔ پاسخ اولیه"}
    assert client.put("/admin/sla-policies", json=body, headers=p["ops"]).status_code == 403
    assert client.put("/admin/sla-policies", json={**body, "status": "needs_customer"}, headers=p["admin"]).status_code == 422
    assert client.put("/admin/sla-policies", json={**body, "minutes": 5}, headers=p["admin"]).status_code == 422
    out = client.put("/admin/sla-policies", json=body, headers=p["admin"]).json()["items"]
    row = next(r for r in out if r["request_type"] == "change" and r["status"] == "submitted")
    assert row["minutes"] == 30 and row["source"] == "tenant" and row["default_minutes"] == 240
    assert client.get("/ops/sla-policies", headers=p["ops"]).status_code == 200
    with SessionLocal() as db:
        ev = db.scalar(select(AuditEvent).where(AuditEvent.action == "ops.sla.updated").order_by(AuditEvent.id.desc()))
        assert json.loads(ev.detail)["before_minutes"] == 240 and json.loads(ev.detail)["after_minutes"] == 30
    rid, _ = reservation(p["cust_email"], status="issued")
    req_id = client.post(f"/reservations/{rid}/service-requests", headers={**p["cust"], **key()}, json={"request_type": "change", "reason": "تغییر تاریخ", "refund_destination": "wallet"}).json()["id"]
    nxt = client.get(f"/ops/service-requests/{req_id}", headers=p["ops"]).json()
    nxt = nxt.get("request", nxt)["next"]
    assert nxt["sla_minutes"] == 30 and nxt["sla_source"] == "tenant"
    client.post("/admin/sla-policies/reset", json={"request_type": "change", "status": "submitted", "reason": "بازگشت به پیش‌فرض"}, headers=p["admin"])
    assert A.next_step("submitted", datetime.now(timezone.utc))["sla_minutes"] == 240


def test_dated_tax_rate_table_drives_vat_without_overlap(client, people):
    from app.agency_b2b import vat_rate_on
    p = people
    other = _user("tenant_admin", "faraz-industries")
    h = login(client, other)
    listing = client.get("/finance/tax-rates", headers=h).json()
    assert listing["source"] == "code_default" and listing["current"]["rate_bps"] == 1000
    base = {"code": "IR-VAT-T1", "rate_bps": 1000, "effective_from": "2024-03-20", "legal_reference": "قانون بودجه (آزمون)"}
    assert client.post("/admin/tax-rates", json=base, headers=p["fin1"]).status_code == 403
    assert client.post("/admin/tax-rates", json=base, headers=h).status_code == 201
    assert client.post("/admin/tax-rates", json={**base, "code": "IR-VAT-T2", "effective_from": "2025-01-01"}, headers=h).status_code == 409
    out = client.get("/finance/tax-rates", headers=h).json()
    assert out["source"] == "table" and out["current"]["id"] == "IR-VAT-T1"
    with SessionLocal() as db:
        tid = db.scalar(select(Tenant.id).where(Tenant.slug == "faraz-industries"))
        assert vat_rate_on(date(2026, 11, 10), db, tid).id == "IR-VAT-T1"
        with pytest.raises(LookupError):
            vat_rate_on(date(2023, 1, 1), db, tid)  # the table does not cover it: error, never a guess
        aftab = db.scalar(select(Tenant.id).where(Tenant.slug == "aftab-bank"))
        assert vat_rate_on(date(2023, 1, 1), db, aftab).rate_bps == 900  # tenants without rows keep the reviewed schedule
    rid = out["items"][0]["id"]
    client.post(f"/admin/tax-rates/{rid}/retire", json={"reason": "پایان آزمون"}, headers=h)
    assert client.get("/finance/tax-rates", headers=h).json()["source"] == "code_default"


def test_failed_payments_list_is_finance_only_and_marks_recovered(client, people):
    p = people
    rid, pid = reservation(p["cust_email"], pay_status="failed")
    assert client.get("/finance/payments/failed", headers=p["ops"]).status_code == 403
    assert client.get("/finance/payments/failed", headers=p["cust"]).status_code == 403
    out = client.get("/finance/payments/failed", headers=p["fin1"]).json()
    row = next(i for i in out["items"] if i["id"] == pid)
    assert row["status"] == "failed" and row["later_paid"] is False and row["reservation"]["id"] == rid
    other = client.get("/finance/payments/failed", headers=login(client, _user("finance_operator", "faraz-industries"))).json()
    assert pid not in {i["id"] for i in other["items"]}


# ---------------------------------------------------------------------------------------------- 4 change price
def test_price_change_is_proposed_approved_by_finance_and_accepted_by_the_customer(client, people):
    p = people
    rid, pid = reservation(p["cust_email"], total=20_000_000)
    body = {"reservation_id": rid, "proposed_total": 23_500_000, "reason": "افزایش نرخ ایرلاین پس از صدور"}
    assert client.post("/ops/price-changes", json=body, headers={**p["fin1"], **key()}).status_code == 403  # ops proposes
    k = key()
    prop = client.post("/ops/price-changes", json=body, headers={**p["ops"], **k})
    assert prop.status_code == 201, prop.text
    prop = prop.json()
    assert prop["status"] == "pending_approval" and prop["difference"] == 3_500_000
    assert client.post("/ops/price-changes", json={**body, "proposed_total": 1}, headers={**p["ops"], **k}).status_code == 409  # key bound to body
    assert client.post("/ops/price-changes", json=body, headers={**p["ops"], **key()}).status_code == 409  # one open proposal
    assert client.get("/me/price-changes", headers=p["cust"]).json()["items"] == []  # not visible before approval
    mc = prop["approval_request_id"]
    assert client.post(f"/maker-checker/requests/{mc}/approve", json={}, headers=p["ops"]).status_code == 403
    assert client.post(f"/maker-checker/requests/{mc}/approve", json={}, headers=p["fin1"]).status_code == 200
    mine = client.get("/me/price-changes", headers=p["cust"]).json()["items"]
    assert [i["status"] for i in mine] == ["awaiting_customer"] and "proposed_by" not in mine[0]
    stranger = login(client, _user("customer"))
    assert client.post(f"/me/price-changes/{prop['id']}/accept", json={}, headers=stranger).status_code == 404
    acc = client.post(f"/me/price-changes/{prop['id']}/accept", json={"note": "قبول"}, headers=p["cust"]).json()
    assert acc["status"] == "accepted" and acc["settlement"] == "collect_difference"
    assert client.post(f"/me/price-changes/{prop['id']}/decline", json={}, headers=p["cust"]).status_code == 409
    with SessionLocal() as db:  # no automatic charge: the payment and the reservation are untouched
        pay = db.get(PaymentIntent, pid)
        assert pay.captured_amount == 20_000_000 and pay.status == "captured"
        assert json.loads(db.get(Reservation, rid).price_snapshot_json)["total_amount"] == 20_000_000


def test_price_change_rejection_by_checker_closes_the_proposal(client, people):
    p = people
    rid, _ = reservation(p["cust_email"], total=10_000_000)
    prop = client.post("/ops/price-changes", json={"reservation_id": rid, "proposed_total": 9_000_000, "reason": "کاهش نرخ طبق اعلام هتل"}, headers={**p["ops"], **key()}).json()
    assert client.post(f"/maker-checker/requests/{prop['approval_request_id']}/reject", json={"note": "مدرک ناکافی"}, headers=p["fin2"]).status_code == 200
    rows = client.get("/ops/price-changes", headers=p["ops"]).json()["items"]
    assert next(r for r in rows if r["id"] == prop["id"])["status"] == "rejected"
    assert client.post(f"/me/price-changes/{prop['id']}/accept", json={}, headers=p["cust"]).status_code == 409


# ---------------------------------------------------------------------------------------------- 6 passengers
def test_scoped_passengers_are_masked_and_isolated(client, people):
    mgr_email = _user("organization_admin"); other_mgr = _user("organization_admin"); emp = _user("employee")
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == mgr_email))
        o1 = Organization(tenant_id=u.tenant_id, name=f"سازمان مسافران {uuid.uuid4().hex[:4]}"); o2 = Organization(tenant_id=u.tenant_id, name=f"سازمان دیگر {uuid.uuid4().hex[:4]}")
        db.add_all([o1, o2]); db.flush()
        for email, org in ((mgr_email, o1), (other_mgr, o2), (emp, o1)):
            db.add(EmployeeAssignment(tenant_id=u.tenant_id, user_id=db.scalar(select(User.id).where(User.email == email)), organization_id=org.id))
        db.commit(); org1 = o1.id
    h = login(client, mgr_email)
    base = f"/scopes/organization/{org1}/passengers"
    assert client.post(base, json={"full_name": "مسافر آزمون", "national_code": "0012345678"}, headers=h).status_code == 422  # check digit
    created = client.post(base, json={"full_name": "مسافر آزمون", "national_code": "۰۰۱۲۳۴۵۶۷۹", "passport_number": "X1234567", "passport_expiry": "2030-01-01"}, headers=h)
    assert created.status_code == 201, created.text
    listing = client.get(base, headers=h).json()
    text = json.dumps(listing, ensure_ascii=False)
    assert listing["items"][0]["national_code_masked"].endswith("5679") and "0012345679" not in text and "X1234567" not in text
    tid = created.json()["id"]
    full = client.get(f"{base}/{tid}/identity", headers=h).json()
    assert full["national_code"] == "0012345679"
    for outsider in (login(client, other_mgr), login(client, emp), login(client, _user("organization_admin", "faraz-industries"))):
        assert client.get(base, headers=outsider).status_code == 404
        assert client.get(f"{base}/{tid}/identity", headers=outsider).status_code == 404
    assert client.post(f"{base}/{tid}/remove", json={}, headers=h).json() == {"removed": tid}
    assert client.get(base, headers=h).json()["items"] == []
    with SessionLocal() as db:
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == "scoped_traveller.identity_read").order_by(AuditEvent.id.desc())) is not None


def test_agency_passengers_need_agency_membership(client):
    a1, a2 = _user("agency_partner"), _user("agency_partner")
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == a1))
        ag = Agency(tenant_id=u.tenant_id, display_name="آژانس مسافران", status="active"); db.add(ag); db.flush()
        db.add(AgencyMembership(tenant_id=u.tenant_id, user_id=u.id, agency_id=ag.id, agency_role="agent")); db.commit(); agency = ag.id
    base = f"/scopes/agency/{agency}/passengers"
    assert client.post(base, json={"full_name": "مسافر آژانس"}, headers=login(client, a1)).status_code == 201
    assert client.get(base, headers=login(client, a2)).status_code == 404
    assert client.get(f"/scopes/supplier/{agency}/passengers", headers=login(client, a1)).status_code == 404


# ---------------------------------------------------------------------------------------------- 7 settlement + bank batch
def test_settlement_csv_parser_reports_rows_and_columns():
    rows, errors = P.parse_settlement_csv("reference,amount,settled_on\nA1,۱۲٬۳۴۵,1405-08-19\n,100,\nB2,-5,\n")
    assert rows == [{"line": 2, "reference": "A1", "amount": 12345, "settled_on": "1405-08-19"}]
    assert [(e["line"], e["column"]) for e in errors] == [(3, "reference"), (4, "amount")]
    assert P.parse_settlement_csv("ref,price\nA,1\n")[1][0]["column"] == "header"


def test_settlement_import_matches_payments_and_lists_unmatched(client, people):
    p = people
    auth_ok, auth_diff, auth_failed = (f"T{uuid.uuid4().hex[:18]}" for _ in range(3))
    _, ok_id = reservation(p["cust_email"], total=5_000_000, authority=auth_ok)
    reservation(p["cust_email"], total=7_000_000, authority=auth_diff)
    reservation(p["cust_email"], total=1_000_000, pay_status="failed", authority=auth_failed)
    csv_text = f"reference,amount\n{auth_ok},5000000\n{auth_diff},6900000\n{auth_failed},1000000\nNOPE-{uuid.uuid4().hex[:6]},10\n{auth_ok},5000000\n"
    body = {"filename": "zp-1405-08-19.csv", "content": csv_text}
    assert client.post("/finance/settlement-imports", json=body, headers=p["ops"]).status_code == 403
    dry = client.post("/finance/settlement-imports", json={**body, "dry_run": True}, headers=p["fin1"]).json()
    assert dry["dry_run"] and dry["matched_count"] == 1
    imp = client.post("/finance/settlement-imports", json=body, headers=p["fin1"])
    assert imp.status_code == 201, imp.text
    lines = {(l["reference"], l["match_status"]) for l in imp.json()["lines"]}
    assert (auth_ok, "matched") in lines and (auth_diff, "amount_mismatch") in lines and (auth_failed, "not_captured") in lines
    assert (auth_ok, "duplicate") in lines and any(s == "unmatched" for _, s in lines)
    assert imp.json()["matched_count"] == 1 and imp.json()["unmatched_count"] == 4
    again = client.post("/finance/settlement-imports", json=body, headers=p["fin2"]).json()
    assert again["duplicate_file"] and again["id"] == imp.json()["id"]
    bad = client.post("/finance/settlement-imports", json={"filename": "x.csv", "content": "reference,amount\nA,abc\n"}, headers=p["fin1"])
    assert bad.status_code == 422 and bad.json()["detail"]["errors"][0]["line"] == 2
    with SessionLocal() as db:
        assert db.get(PaymentIntent, ok_id).status == "captured"  # import never changes a payment


def test_bank_batch_file_only_after_second_finance_approval(client, people):
    p = people
    from app.commerce import UserBankAccount
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == p["cust_email"]))
        db.add(UserBankAccount(tenant_id=u.tenant_id, user_id=u.id, holder_name="مشتری آزمون", sheba="IR060120000000001234567890", sheba_bank="ملت")); db.commit()
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == p["cust_email"]))
        r = Reservation(tenant_id=u.tenant_id, user_id=u.id, service_type="flight", status="issued", booking_reference=f"KR-{uuid.uuid4().hex[:8].upper()}",
                        price_snapshot_json=json.dumps({"total_amount": 8_000_000, "currency": "IRR"}),
                        policy_at_booking_json=json.dumps({"verified": True, "source": "t", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True, "penalty_amount": 1_000_000}}))
        db.add(r); db.flush()
        db.add(PaymentIntent(tenant_id=u.tenant_id, reservation_id=r.id, user_id=u.id, command_id=f"bb-{uuid.uuid4().hex}", amount=8_000_000, captured_amount=8_000_000, status="captured"))
        db.commit(); rid = r.id
    req_id = client.post(f"/reservations/{rid}/service-requests", headers={**p["cust"], **key()}, json={"request_type": "cancel", "reason": "لغو سفر", "refund_destination": "bank_transfer"}).json()["id"]
    client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**p["ops"], **key()}, json={"action": "start_review"})
    refund_id = client.post(f"/backoffice/booking-requests/{req_id}/actions", headers={**p["ops"], **key()}, json={"action": "approve", "penalty_mode": "policy"}).json()["refund"]["id"]
    cands = client.get("/finance/bank-batches/candidates", headers=p["fin1"]).json()["items"]
    row = next(c for c in cands if c["refund_id"] == refund_id)
    assert row["amount"] == 7_000_000 and "1234567890" not in json.dumps(row)
    assert client.get("/finance/bank-batches/candidates", headers=p["ops"]).status_code == 403
    batch = client.post("/finance/bank-batches", json={"refund_ids": [refund_id]}, headers={**p["fin1"], **key()})
    assert batch.status_code == 201, batch.text
    b = batch.json()
    assert b["status"] == "pending_approval" and b["total_amount"] == 7_000_000
    assert refund_id not in {c["refund_id"] for c in client.get("/finance/bank-batches/candidates", headers=p["fin1"]).json()["items"]}  # one batch per refund
    assert client.get(f"/finance/bank-batches/{b['id']}/file", headers=p["fin1"]).status_code == 409
    assert client.post(f"/maker-checker/requests/{b['approval_request_id']}/approve", json={}, headers=p["fin1"]).status_code == 403
    assert client.post(f"/maker-checker/requests/{b['approval_request_id']}/approve", json={}, headers=p["fin2"]).status_code == 200
    f = client.get(f"/finance/bank-batches/{b['id']}/file", headers=p["fin2"])
    assert f.status_code == 200 and "IR060120000000001234567890" in f.text and ",7000000," in f.text and f.headers["x-file-sha256"]
    with SessionLocal() as db:  # the file is only a file: the refund still waits for finance to record the bank reference
        assert db.get(RefundRecord, refund_id).status == "pending_finance"
    other = login(client, _user("finance_operator", "faraz-industries"))
    assert client.get(f"/finance/bank-batches/{b['id']}/file", headers=other).status_code == 404
