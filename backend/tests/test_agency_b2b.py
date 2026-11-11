"""Panels Phase 2 — agency B2B core: money math (VAT on commission, markup, CAO cap), licence verification per registry,
KYC, maker-checker wallet/credit, booking on credit (hold → capture / release), concurrency, isolation, statement CSV."""
import json
import threading
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import agency_b2b as B
from app import operations as m
from app.main import SessionLocal, Tenant, User


# ------------------------------------------------------------------------------------------------ helpers
def _user(role: str, tenant_slug: str = "aftab-bank") -> str:
    email = f"b2b-{role}-{uuid.uuid4().hex[:10]}@{tenant_slug}.test"
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        db.add(User(tenant_id=tenant.id, email=email, name=f"آزمون {role}", role=role))
        db.commit()
    return email


def login(client, email: str) -> dict:
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def key() -> dict:
    return {"Idempotency-Key": f"b2b-{uuid.uuid4().hex}"}


def uid(email: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def make_agency(owner_email: str, commission_bps: int = 120, agent_email: str | None = None) -> str:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == owner_email))
        ag = m.Agency(tenant_id=u.tenant_id, display_name=f"آژانس آزمون {uuid.uuid4().hex[:6]}", status="active", commission_bps=commission_bps)
        db.add(ag)
        db.flush()
        db.add(m.AgencyMembership(tenant_id=u.tenant_id, user_id=u.id, agency_id=ag.id, agency_role="owner"))
        if agent_email:
            a = db.scalar(select(User).where(User.email == agent_email))
            db.add(m.AgencyMembership(tenant_id=u.tenant_id, user_id=a.id, agency_id=ag.id, agency_role="agent"))
        db.commit()
        return ag.id


PROFILE = {"legal_name": "شرکت خدمات مسافرتی آزمون (نمونه)", "national_id": "۱۴۰۰۰۰۰۰۰۰۰", "economic_code": "411400000000", "postal_code": "1969000000",
           "ceo_name": "مدیر نمونه", "iban": "IR000000000000000000000000"}


def activate(client, owner_h, ops_h, agency_id, licence_type="BAND_ALEF") -> str:
    """Owner fills profile + licence, staff verify every required registry and approve KYC. Returns the licence id."""
    assert client.put(f"/agency/{agency_id}/profile", json=PROFILE, headers=owner_h).status_code == 200
    lic = client.post(f"/agency/{agency_id}/licences", headers=owner_h, json={"licence_type": licence_type, "number": f"A-{uuid.uuid4().hex[:6]}",
                                                                              "expires_on": (date.today() + timedelta(days=400)).isoformat(), "attest": True})
    assert lic.status_code == 201, lic.text
    lid = lic.json()["id"]
    assert client.post(f"/agency/{agency_id}/profile/submit", headers=owner_h).status_code == 200
    for reg in [r["registry"] for r in lic.json()["registries"]]:
        r = client.post(f"/staff/agencies/{agency_id}/licences/{lid}/checks", headers=ops_h, json={"registry": reg, "result": "confirmed", "reference": f"INQ-{reg}"})
        assert r.status_code == 201, r.text
    r = client.post(f"/staff/agencies/{agency_id}/kyc", headers=ops_h, json={"decision": "approve"})
    assert r.status_code == 200, r.text
    return lid


def fund(client, fin1, fin2, agency_id, *, limit=0, topup=0):
    steps = []
    if limit:
        steps.append((f"/finance/agency-accounts/{agency_id}/credit-limit", {"new_limit_irr": limit, "reason": "قرارداد اعتبار"}))
    if topup:
        steps.append((f"/finance/agency-accounts/{agency_id}/adjustments", {"direction": "topup", "amount_irr": topup, "reason": "واریز", "bank_reference": "BR-1"}))
    for path, body in steps:
        r = client.post(path, json=body, headers={**fin1, **key()})
        assert r.status_code == 202, r.text
        ok = client.post(f"/maker-checker/requests/{r.json()['request_id']}/approve", json={}, headers=fin2)
        assert ok.status_code == 200, ok.text


def flight_offer(email: str, amount: int, origin="IKA", dest="IST", day: date | None = None, units=9) -> str:
    day = day or (date.today() + timedelta(days=20))
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        sup = m.Supplier(tenant_id=u.tenant_id, supplier_type="airline", display_name="ایرلاین آزمون", status="active", lifecycle_status="CONTRACTED")
        db.add(sup)
        db.flush()
        dep = datetime(day.year, day.month, day.day, 8, 0, tzinfo=timezone.utc)
        attrs = {"origin": origin, "destination": dest, "origin_code": origin, "destination_code": dest, "flight_date": day.isoformat(), "departure_time": dep.isoformat(),
                 "arrival_time": (dep + timedelta(hours=3)).isoformat(), "flight_type": "system"}
        o = m.Offer(tenant_id=u.tenant_id, supplier_id=sup.id, service_type="flight", title=f"پرواز آزمون {origin}-{dest}", amount=amount, currency="IRR", available_units=units,
                    status="active", provider_key="manual_supplier", fulfillment_mode="manual_supplier", attributes_json=json.dumps(attrs), policy_json=json.dumps({"verified": True}),
                    valid_until=datetime.now(timezone.utc) + timedelta(days=10))
        db.add(o)
        db.commit()
        return o.id


def price_check(client, h, offer_id, units=1):
    r = client.post(f"/offers/{offer_id}/price-check", json={"units": units, "command_id": f"pc-{uuid.uuid4().hex}"}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def world(client):
    owner, agent, ops, fin1, fin2 = _user("agency_partner"), _user("agency_partner"), _user("backoffice_expert"), _user("finance_operator"), _user("finance_operator")
    agency_id = make_agency(owner, agent_email=agent)
    return {"agency_id": agency_id, "owner_email": owner, "owner": login(client, owner), "agent": login(client, agent), "ops": login(client, ops),
            "fin1": login(client, fin1), "fin2": login(client, fin2)}


# ------------------------------------------------------------------------------------------------ money math
def test_half_up_and_vat_schedule_is_dated():
    assert B.half_up(5, 10) == 1 and B.half_up(4, 10) == 0 and B.half_up(-5, 10) == -1 and B.half_up(15, 10) == 2
    assert B.vat_rate_on(date(2026, 11, 10)).rate_bps == 1000
    assert B.vat_rate_on(date(2023, 6, 1)).rate_bps == 900
    with pytest.raises(LookupError):
        B.vat_rate_on(date(2020, 1, 1))  # no rate configured before the 1400 law: nothing is guessed


def test_vat_is_on_commission_not_on_fare_figma_ag07_example():
    v = B.vat_rate_on(date(2026, 11, 10))
    out = B.compute_line(net_irr=42_800_000, units=1, commission_bps=120, vat=v, markup_irr=3_500_000, cap_unit_irr=45_000_000)
    assert out["commission_irr"] == 513_600 and out["vat_irr"] == 51_360  # 10% of the commission (Figma AG-07)
    assert out["vat_irr"] != B.bps_of(42_800_000, 1000)  # never VAT on the ticket fare
    assert out["customer_price_irr"] == 46_300_000 and out["agency_pays_irr"] == 42_800_000
    assert out["price_cap_status"] == "exceeded" and out["max_markup_irr"] == 2_200_000
    ok = B.compute_line(net_irr=42_800_000, units=1, commission_bps=120, vat=v, markup_irr=2_200_000, cap_unit_irr=45_000_000)
    assert ok["price_cap_status"] == "within" and ok["customer_price_irr"] == 45_000_000
    none = B.compute_line(net_irr=10_000_000, units=2, commission_bps=0, vat=v, markup_irr=0, cap_unit_irr=None)
    assert none["price_cap_status"] == "not_configured" and none["commission_irr"] == 0 and none["vat_irr"] == 0


def test_rounding_half_up_on_commission_and_vat():
    v = B.VatRate("T", 1000, "test")
    out = B.compute_line(net_irr=1_234_567, units=1, commission_bps=125, vat=v, markup_irr=0, cap_unit_irr=None)
    assert out["commission_irr"] == 15_432  # 15,432.0875 → 15,432
    assert out["vat_irr"] == 1_543  # 1,543.2 → 1,543
    out = B.compute_line(net_irr=1_000_004, units=1, commission_bps=5, vat=v, markup_irr=0, cap_unit_irr=None)
    assert out["commission_irr"] == 500  # 500.002


def test_markup_rules_pct_fixed_and_clamps():
    r = B.AgencyMarkupRule(kind="pct", value_bps=200, fixed_irr=0, min_irr=200_000, max_irr=1_500_000)
    assert B.markup_for(r, 42_800_000, 1) == 856_000
    assert B.markup_for(r, 5_000_000, 2) == 400_000  # 100,000/unit → clamped to min 200,000 × 2
    assert B.markup_for(r, 200_000_000, 1) == 1_500_000
    f = B.AgencyMarkupRule(kind="fixed", value_bps=0, fixed_irr=1_000_000, min_irr=None, max_irr=None)
    assert B.markup_for(f, 1, 3) == 3_000_000 and B.markup_for(None, 10, 1) == 0


# ------------------------------------------------------------------------------------------------ licences / KYC
def test_licence_needs_every_registry_and_staff_only(client, world):
    a, owner, agent, ops = world["agency_id"], world["owner"], world["agent"], world["ops"]
    assert client.put(f"/agency/{a}/profile", json=PROFILE, headers=agent).status_code == 403  # agent role cannot edit legal data
    r = client.put(f"/agency/{a}/profile", json={**PROFILE, "postal_code": "123"}, headers=owner)
    assert r.status_code == 422
    assert client.put(f"/agency/{a}/profile", json=PROFILE, headers=owner).json()["national_id"] == "14000000000"  # Persian digits accepted
    assert client.post(f"/agency/{a}/licences", headers=owner, json={"licence_type": "BAND_BE", "number": "B-1", "expires_on": "2020-01-01", "attest": True}).status_code == 422
    lic = client.post(f"/agency/{a}/licences", headers=owner, json={"licence_type": "BAND_BE", "number": "B-1405-0441",
                                                                     "expires_on": (date.today() + timedelta(days=90)).isoformat(), "attest": True}).json()
    assert [x["registry"] for x in lic["registries"]] == ["national_portal", "mcth"] and lic["status"] == "pending"
    path = f"/staff/agencies/{a}/licences/{lic['id']}/checks"
    assert client.post(path, headers=owner, json={"registry": "mcth", "result": "confirmed", "reference": "X"}).status_code == 403  # no self-verification
    assert client.post(path, headers=ops, json={"registry": "cao", "result": "confirmed", "reference": "X"}).status_code == 422  # not this licence's registry
    assert client.post(path, headers=ops, json={"registry": "mcth", "result": "confirmed"}).status_code == 422  # lookup needs an inquiry reference
    one = client.post(path, headers=ops, json={"registry": "mcth", "result": "confirmed", "reference": "MCTH-INQ-1"}).json()
    assert one["status"] == "pending"
    assert client.post(f"/agency/{a}/profile/submit", headers=owner).status_code == 200
    assert client.post(f"/staff/agencies/{a}/kyc", headers=ops, json={"decision": "approve"}).status_code == 422  # licence not verified yet
    two = client.post(path, headers=ops, json={"registry": "national_portal", "result": "confirmed", "reference": "NP-1"}).json()
    assert two["status"] == "verified"
    bad = client.post(path, headers=ops, json={"registry": "national_portal", "result": "mismatch", "reference": "NP-2"}).json()
    assert bad["status"] == "rejected"
    client.post(path, headers=ops, json={"registry": "national_portal", "result": "confirmed", "reference": "NP-3"})
    assert client.post(f"/staff/agencies/{a}/kyc", headers=ops, json={"decision": "approve"}).json()["kyc_status"] == "active"
    assert client.put(f"/agency/{a}/profile", json=PROFILE, headers=owner).status_code == 409  # legal fields locked after activation
    assert client.post(f"/staff/agencies/{a}/kyc", headers=ops, json={"decision": "suspend"}).status_code == 422  # reason required
    ctx = client.get(f"/agency/{a}/b2b", headers=agent).json()
    assert ctx["member_role"] == "agent" and ctx["kyc_status"] == "active" and ctx["valid_licence_types"] == ["BAND_BE"] and ctx["can_charter"] is False
    assert client.get(f"/staff/agencies/{a}", headers=ops).json()["audit"]


def test_online_sales_licence_needs_its_issuer():
    assert B.required_registries("ONLINE_SALES", "mcth") == ("national_portal", "mcth")
    assert B.required_registries("ONLINE_SALES", "cao") == ("national_portal", "cao")
    assert B.required_registries("BAND_ALEF", None) == ("national_portal", "cao")


# ------------------------------------------------------------------------------------------------ maker-checker credit
def test_wallet_and_limit_only_move_after_a_second_finance_person(client, world):
    a, owner, fin1, fin2, ops = world["agency_id"], world["owner"], world["fin1"], world["fin2"], world["ops"]
    assert client.post(f"/agency/{a}/topup-requests", json={"amount_irr": 5_000_000, "bank_reference": "1405081700"}, headers={**owner, **key()}).status_code == 409  # not active yet
    activate(client, owner, ops, a)
    k = key()
    req = client.post(f"/agency/{a}/topup-requests", json={"amount_irr": 5_000_000, "bank_reference": "1405081700"}, headers={**owner, **k})
    assert req.status_code == 202, req.text
    again = client.post(f"/agency/{a}/topup-requests", json={"amount_irr": 5_000_000, "bank_reference": "1405081700"}, headers={**owner, **k})
    assert again.json()["request_id"] == req.json()["request_id"]  # same key + same payload = same request
    assert client.post(f"/agency/{a}/topup-requests", json={"amount_irr": 6_000_000, "bank_reference": "1405081700"}, headers={**owner, **k}).status_code == 409
    w = client.get(f"/agency/{a}/wallet", headers=owner).json()
    assert w["balances"]["balance_irr"] == 0 and w["requests"][0]["status"] == "pending"  # nothing moved yet
    rid = req.json()["request_id"]
    assert client.post(f"/maker-checker/requests/{rid}/approve", json={}, headers=owner).status_code == 403  # maker cannot check
    assert client.post(f"/maker-checker/requests/{rid}/approve", json={}, headers=ops).status_code == 403  # ops has no credit:fund
    assert client.post(f"/maker-checker/requests/{rid}/approve", json={}, headers=fin1).status_code == 200
    w = client.get(f"/agency/{a}/wallet", headers=owner).json()
    assert w["balances"]["balance_irr"] == 5_000_000 and w["entries"][0]["entry_type"] == "TOPUP" and w["entries"][0]["reference"] == "1405081700"
    # finance-made limit change: the maker cannot approve it, a different finance user can
    lim = client.post(f"/finance/agency-accounts/{a}/credit-limit", json={"new_limit_irr": 20_000_000, "reason": "قرارداد"}, headers={**fin1, **key()}).json()
    assert client.post(f"/maker-checker/requests/{lim['request_id']}/approve", json={}, headers=fin1).status_code == 403
    assert client.post(f"/maker-checker/requests/{lim['request_id']}/approve", json={}, headers=fin2).status_code == 200
    b = client.get(f"/agency/{a}/wallet", headers=owner).json()["balances"]
    assert b["credit_limit_irr"] == 20_000_000 and b["available_irr"] == 25_000_000
    # a decrease larger than what is available is refused at approval and nothing changes
    dec = client.post(f"/finance/agency-accounts/{a}/adjustments", json={"direction": "decrease", "amount_irr": 30_000_000, "reason": "اصلاح"}, headers={**fin1, **key()}).json()
    assert client.post(f"/maker-checker/requests/{dec['request_id']}/approve", json={}, headers=fin2).status_code == 409
    assert client.get(f"/agency/{a}/wallet", headers=owner).json()["balances"]["available_irr"] == 25_000_000
    # agent sees balances but not the ledger, and cannot request money movements
    aw = client.get(f"/agency/{a}/wallet", headers=world["agent"]).json()
    assert aw["entries_visible"] is False and aw["entries"] == []
    assert client.post(f"/agency/{a}/credit-limit-requests", json={"new_limit_irr": 1, "reason": "x x x"}, headers={**world["agent"], **key()}).status_code == 403
    assert client.post(f"/finance/agency-accounts/{a}/adjustments", json={"direction": "topup", "amount_irr": 1, "reason": "abc"}, headers={**owner, **key()}).status_code == 403


def test_limit_cannot_drop_below_what_is_used():
    with SessionLocal() as db:
        t = db.scalar(select(Tenant.id).where(Tenant.slug == "aftab-bank"))
        ag = m.Agency(tenant_id=t, display_name=f"آژانس سقف {uuid.uuid4().hex[:5]}", status="active")
        db.add(ag)
        db.flush()
        acc = B.account_for(db, t, ag.id, create=True)
        B.set_limit(db, acc, 10_000_000, key=f"t-{uuid.uuid4()}", user_id=None)
        B.hold(db, acc, 6_000_000, key=f"t-{uuid.uuid4()}", user_id=None)
        with pytest.raises(ValueError):
            B.set_limit(db, acc, 5_000_000, key=f"t-{uuid.uuid4()}", user_id=None)
        db.refresh(acc)
        assert acc.credit_limit_irr == 10_000_000 and acc.held_irr == 6_000_000
        db.rollback()


# ------------------------------------------------------------------------------------------------ credit check concurrency
def test_stale_reads_cannot_both_spend_the_last_credit():
    with SessionLocal() as db:
        t = db.scalar(select(Tenant.id).where(Tenant.slug == "aftab-bank"))
        ag = m.Agency(tenant_id=t, display_name=f"آژانس هم‌زمان {uuid.uuid4().hex[:5]}", status="active")
        db.add(ag)
        db.flush()
        acc = B.account_for(db, t, ag.id, create=True)
        B.set_limit(db, acc, 1_000_000, key=f"s-{uuid.uuid4()}", user_id=None)
        db.commit()
        acc_id, agency_id = acc.id, ag.id
    s1, s2 = SessionLocal(), SessionLocal()
    try:
        a1, a2 = s1.get(B.AgencyAccount, acc_id), s2.get(B.AgencyAccount, acc_id)
        assert B.balances(a1)["available_irr"] == B.balances(a2)["available_irr"] == 1_000_000  # both read "enough"
        B.hold(s1, a1, 700_000, key=f"s-{uuid.uuid4()}", user_id=None)
        s1.commit()
        with pytest.raises(B.CreditError) as exc:
            B.hold(s2, a2, 700_000, key=f"s-{uuid.uuid4()}", user_id=None)  # its read is stale; the conditional update refuses
        assert exc.value.code == "INSUFFICIENT_CREDIT"
        s2.rollback()
    finally:
        s1.close()
        s2.close()
    with SessionLocal() as db:
        acc = db.scalar(select(B.AgencyAccount).where(B.AgencyAccount.agency_id == agency_id))
        assert acc.held_irr == 700_000


def test_parallel_holds_never_overdraw():
    with SessionLocal() as db:
        t = db.scalar(select(Tenant.id).where(Tenant.slug == "aftab-bank"))
        ag = m.Agency(tenant_id=t, display_name=f"آژانس موازی {uuid.uuid4().hex[:5]}", status="active")
        db.add(ag)
        db.flush()
        acc = B.account_for(db, t, ag.id, create=True)
        B.set_limit(db, acc, 1_000_000, key=f"p-{uuid.uuid4()}", user_id=None)
        db.commit()
        acc_id = acc.id
    barrier, results = threading.Barrier(10), []

    def worker():
        with SessionLocal() as s:
            acc = s.get(B.AgencyAccount, acc_id)
            barrier.wait()
            try:
                B.hold(s, acc, 300_000, key=f"p-{uuid.uuid4()}", user_id=None)
                s.commit()
                results.append("ok")
            except B.CreditError:
                s.rollback()
                results.append("refused")

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert results.count("ok") == 3 and results.count("refused") == 7
    with SessionLocal() as db:
        acc = db.get(B.AgencyAccount, acc_id)
        assert acc.held_irr == 900_000 and B.balances(acc)["available_irr"] == 100_000
        assert len(db.scalars(select(B.AgencyLedgerEntry).where(B.AgencyLedgerEntry.account_id == acc_id, B.AgencyLedgerEntry.entry_type == "HOLD")).all()) == 3


# ------------------------------------------------------------------------------------------------ booking on credit
def test_booking_on_credit_hold_capture_and_breakdown(client, world):
    a, owner, agent, ops = world["agency_id"], world["owner"], world["agent"], world["ops"]
    activate(client, owner, ops, a)
    fund(client, world["fin1"], world["fin2"], a, limit=50_000_000)
    assert client.post(f"/agency/{a}/markup-rules", headers=agent, json={"kind": "pct", "value_bps": 200}).status_code == 403
    rule = client.post(f"/agency/{a}/markup-rules", headers=owner, json={"kind": "fixed", "fixed_irr": 1_000_000, "min_irr": 500_000, "max_irr": 2_000_000, "service_scope": "flight"})
    assert rule.status_code == 201, rule.text
    offer = flight_offer(world["owner_email"], 42_800_000)
    pc = price_check(client, agent, offer)
    prev = client.post(f"/agency/{a}/credit-bookings/preview", headers=agent, json={"price_check_id": pc["id"]}).json()
    assert prev["breakdown"]["markup_irr"] == 1_000_000 and prev["breakdown"]["commission_irr"] == 513_600 and prev["breakdown"]["vat_irr"] == 51_360
    assert prev["breakdown"]["price_cap_status"] == "not_configured" and prev["sufficient_credit"] is True
    assert "platform_markup" not in json.dumps(prev) and "supplier" not in json.dumps(prev["breakdown"])  # agency_buyer view only
    bad = client.post(f"/agency/{a}/credit-bookings", headers=agent, json={"price_check_id": pc["id"], "markup_irr": 3_000_000, "command_id": f"cb-{uuid.uuid4().hex}"})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "MARKUP_OUT_OF_RULE"
    cmd = f"cb-{uuid.uuid4().hex}"
    r = client.post(f"/agency/{a}/credit-bookings", headers=agent, json={"price_check_id": pc["id"], "command_id": cmd})
    assert r.status_code == 201, r.text
    line = r.json()
    assert line["status"] == "captured" and line["reservation_status"] == "confirmed" and line["booking_reference"]
    assert line["breakdown"]["agency_pays_irr"] == 42_800_000 and line["breakdown"]["customer_price_irr"] == 43_800_000
    replay = client.post(f"/agency/{a}/credit-bookings", headers=agent, json={"price_check_id": pc["id"], "command_id": cmd})
    assert replay.status_code == 201 and replay.json()["id"] == line["id"]
    assert client.post(f"/agency/{a}/credit-bookings", headers=agent, json={"price_check_id": pc["id"], "markup_irr": 600_000, "command_id": cmd}).status_code == 409
    w = client.get(f"/agency/{a}/wallet", headers=owner).json()
    assert w["balances"]["balance_irr"] == -42_800_000 and w["balances"]["held_irr"] == 0 and w["balances"]["available_irr"] == 7_200_000
    assert [e["entry_type"] for e in w["entries"][:2]] == ["CAPTURE", "HOLD"]
    inv = client.get(f"/agency/{a}/invoices", headers=owner).json()
    assert inv["items"][0]["commission_irr"] == 513_600 and inv["items"][0]["vat_irr"] == 51_360 and inv["moadian"] == "not_sent"
    assert client.get(f"/agency/{a}/invoices", headers=agent).status_code == 403
    with SessionLocal() as db:
        res = db.get(m.Reservation, line["reservation_id"])
        from app.main import _reservation_settlement_ready
        assert res.status == "confirmed" and _reservation_settlement_ready(db, res)  # paid from the agency account → ready for fulfilment
    csv = client.get(f"/agency/{a}/wallet/statement.csv", headers=owner)
    assert csv.status_code == 200 and "CAPTURE" in csv.text and line["booking_reference"] in csv.text
    assert client.get(f"/agency/{a}/wallet/statement.csv", headers=agent).status_code == 403


def test_insufficient_credit_holds_nothing_and_inactive_agency_cannot_book(client, world):
    a, owner, agent, ops = world["agency_id"], world["owner"], world["agent"], world["ops"]
    offer = flight_offer(world["owner_email"], 30_000_000)
    pc = price_check(client, agent, offer)
    r = client.post(f"/agency/{a}/credit-bookings", headers=agent, json={"price_check_id": pc["id"], "command_id": f"cb-{uuid.uuid4().hex}"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "AGENCY_NOT_ACTIVE"
    activate(client, owner, ops, a)
    fund(client, world["fin1"], world["fin2"], a, limit=10_000_000)
    r = client.post(f"/agency/{a}/credit-bookings", headers=agent, json={"price_check_id": pc["id"], "command_id": f"cb-{uuid.uuid4().hex}"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "INSUFFICIENT_CREDIT"
    w = client.get(f"/agency/{a}/wallet", headers=owner).json()
    assert w["balances"]["held_irr"] == 0 and not any(e["entry_type"] == "HOLD" for e in w["entries"])
    assert client.get(f"/agency/{a}/credit-bookings", headers=owner).json()["items"] == []


def test_cao_cap_blocks_agency_markup_and_b2c_price(client, world):
    a, owner, agent, ops = world["agency_id"], world["owner"], world["agent"], world["ops"]
    activate(client, owner, ops, a)
    fund(client, world["fin1"], world["fin2"], a, limit=100_000_000)
    admin = login(client, _user("tenant_admin"))
    day = date.today() + timedelta(days=25)
    origin, dest = "MHD", "NJF"
    assert client.post("/staff/charter/price-caps", headers=ops, json={"origin": origin, "destination": dest, "valid_from": day.isoformat(), "valid_to": day.isoformat(),
                                                                        "cap_unit_irr": 45_000_000, "legal_reference": "اطلاعیهٔ آزمون سازمان هواپیمایی"}).status_code == 403
    assert client.post("/staff/charter/price-caps", headers=admin, json={"origin": origin, "destination": dest, "valid_from": day.isoformat(), "valid_to": day.isoformat(),
                                                                          "cap_unit_irr": 45_000_000, "legal_reference": "اطلاعیهٔ آزمون سازمان هواپیمایی"}).status_code == 201
    offer = flight_offer(world["owner_email"], 42_800_000, origin, dest, day)
    pc = price_check(client, agent, offer)
    r = client.post(f"/agency/{a}/credit-bookings", headers=agent, json={"price_check_id": pc["id"], "markup_irr": 3_500_000, "command_id": f"cb-{uuid.uuid4().hex}"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PRICE_CAP_EXCEEDED" and r.json()["detail"]["max_markup_irr"] == 2_200_000
    assert client.get(f"/agency/{a}/wallet", headers=owner).json()["balances"]["held_irr"] == 0
    ok = client.post(f"/agency/{a}/credit-bookings", headers=agent, json={"price_check_id": pc["id"], "markup_irr": 2_200_000, "command_id": f"cb-{uuid.uuid4().hex}"})
    assert ok.status_code == 201, ok.text
    assert ok.json()["breakdown"]["price_cap_unit_irr"] == 45_000_000
    # B2C: a flight whose own price is above the cap cannot be price-checked
    over = flight_offer(world["owner_email"], 46_000_000, origin, dest, day)
    cust = login(client, _user("customer"))
    r = client.post(f"/offers/{over}/price-check", json={"units": 1, "command_id": f"pc-{uuid.uuid4().hex}"}, headers=cust)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PRICE_CAP_EXCEEDED"


def test_agency_isolation(client, world):
    other_owner = _user("agency_partner")
    other = make_agency(other_owner)
    oh = login(client, other_owner)
    a = world["agency_id"]
    for path in (f"/agency/{a}/b2b", f"/agency/{a}/profile", f"/agency/{a}/wallet", f"/agency/{a}/credit-bookings", f"/agency/{a}/members", f"/agency/{a}/charter/blocks"):
        assert client.get(path, headers=oh).status_code == 404, path
    assert client.get(f"/agency/{other}/wallet", headers=world["owner"]).status_code == 404
    assert client.get("/staff/agencies", headers=oh).status_code == 403
    assert client.get("/finance/agency-accounts", headers=oh).status_code == 403
    # another tenant's staff cannot see this agency
    foreign = login(client, _user("backoffice_expert", "faraz-industries"))
    assert client.get(f"/staff/agencies/{a}", headers=foreign).status_code == 404


def test_member_roles_owner_only(client, world):
    a = world["agency_id"]
    me = client.get(f"/agency/{a}/members", headers=world["agent"]).json()
    agent_id = next(x["user_id"] for x in me["items"] if x["role"] == "agent")
    assert client.put(f"/agency/{a}/members/{agent_id}/role", json={"role": "owner"}, headers=world["agent"]).status_code == 403
    assert client.put(f"/agency/{a}/members/{uid(world['owner_email'])}/role", json={"role": "agent"}, headers=world["owner"]).status_code == 409
    assert client.put(f"/agency/{a}/members/{agent_id}/role", json={"role": "owner"}, headers=world["owner"]).json()["role"] == "owner"


def test_csv_cells_are_formula_safe():
    assert B.safe_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)" and B.safe_cell("KS-1") == "KS-1" and B.safe_cell(5) == 5
