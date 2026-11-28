"""Live Niira/Mahan flights in the customer search as request-only offers (owner decision 1405-09-08):
sell price per price group, never the net; above the CAO cap not listed; one failing supplier never breaks the search;
sandbox/QAA never reach it; no DB transaction open during supplier calls; short cache; «درخواست رزرو» lands in the
sales desk with the verified flight details.

TEST FIXTURES ONLY: synthetic NRS / Mahan answers and fake credentials; HTTP is an httpx.MockTransport or a stub adapter.
Test rows (markup rules, caps) are disabled afterwards, never deleted.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app import main
from app import mahan_flight as mf
from app import public_flight_suppliers as pfs
from app.catalog import CatalogAirport
from app.flight_port import FareOffer, FlightSegment
from app.main import SessionLocal, Tenant, User
from app.sales_desk import SalesCase, SalesCaseActivity
from tests.test_nira_flight import DAY, PASS, Mock, avail, clean_env, creds, transport  # noqa: F401  (fixtures)

TOKEN = "test-internal-token-not-real"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(main, "_SEARCH_INTERNAL_TOKEN", TOKEN)
    monkeypatch.delenv("MAHAN_MODE", raising=False)
    pfs.clear_cache()
    with SessionLocal() as db:
        for code, city in (("THR", "تهران"), ("MHD", "مشهد")):
            a = db.get(CatalogAirport, code)
            if not a.city_name:
                a.city_name = city
        db.commit()
    yield
    pfs.clear_cache()


def _tenant():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "backoffice@aftab.test"))
        return user.tenant_id, db.get(Tenant, user.tenant_id).slug


def _live_nira(monkeypatch, **hosts):
    monkeypatch.setenv("NIRA_MODE", "live")
    monkeypatch.setenv("NIRA_AIRLINES", "VR,J1")
    creds(monkeypatch, "VR", "J1")


def _call(client, slug, origin="تهران", destination="مشهد", **filters):
    body = {"public": False, "tenant_ref": slug, "origin": origin, "destination": destination, "travellers": 1,
            "filters": {"depart": DAY, "adults": 1, **filters}}
    r = client.post("/internal/search/flight-suppliers", json=body, headers={"X-Internal-Token": TOKEN})
    assert r.status_code == 200, r.text
    return r.json()


def _rule(tenant_id, **kw):
    from app.commerce import MarkupRule
    with SessionLocal() as db:
        rule = MarkupRule(tenant_id=tenant_id, service_type="flight", supplier_id="nira", calc="percent", **kw)
        db.add(rule)
        db.commit()
        return rule.id


def _disable(model, row_id):
    with SessionLocal() as db:
        db.execute(update(model).where(model.id == row_id).values(status="disabled"))
        db.commit()


def test_requires_internal_token(client):
    assert client.post("/internal/search/flight-suppliers", json={"origin": "THR", "destination": "MHD"}).status_code == 401


def test_live_niira_rows_are_sell_side_request_only_and_net_free(client, monkeypatch, transport):
    from app.commerce import MarkupRule
    _live_nira(monkeypatch)
    mock = transport(Mock({"api.vareshair.ir": avail(fn="2001", price="30000000"), "apps.merajairlines.ir": avail(fn="4001", price="31000000")}))
    tenant_id, slug = _tenant()
    rid = _rule(tenant_id, title="test public nira 10%", adult=1000)
    try:
        body = _call(client, slug)
        rows = body["offers"]
        got = sorted((r["attributes"]["flight_number"], r["attributes"]["fare_class"], r["amount"]) for r in rows)
        assert got == [("2001", "Y", 33000000), ("4001", "Y", 34100000)]   # class B is closed (Cap C)
        a = rows[0]["attributes"]
        assert a["booking_mode"] == "request" and a["request_price"] == rows[0]["amount"] and a["origin"] == "تهران" and a["origin_code"] == "THR"
        assert a["departure_time"].endswith("+03:30") and a["airline"] in ("وارش", "معراج")
        text = json.dumps(body, ensure_ascii=False)
        for secret in ("30000000", "31000000", "19000000", PASS, "WS.TEST"):
            assert secret not in text
        keys = {k for r in rows for k in [*r, *r["attributes"]]}
        assert not keys & {"net", "net_total", "net_unit", "margin", "indicative_adult_fare", "offer_ref", "total_amount"}
        assert len({r["attributes"]["entity_id"] for r in rows}) == 2       # one entity per flight
        n = len(mock.requests)
        _call(client, slug)                                                # cached: no second supplier call
        assert len(mock.requests) == n
    finally:
        _disable(MarkupRule, rid)


def test_price_group_and_cap(client, monkeypatch, transport):
    from app.charter_blocks import PriceCap
    from app.commerce import CustomerGroup, MarkupRule
    _live_nira(monkeypatch)
    monkeypatch.setenv("NIRA_AIRLINES", "VR")
    transport(Mock({"api.vareshair.ir": avail(fn="2001", price="30000000")}))
    tenant_id, slug = _tenant()
    with SessionLocal() as db:
        g = CustomerGroup(tenant_id=tenant_id, code="tpf" + uuid.uuid4().hex[:8], name="test public flights group")
        db.add(g)
        db.commit()
        gid = g.id
    rid = _rule(tenant_id, title="test group-only 50%", adult=5000, group_id=gid)
    try:
        plain = {r["attributes"]["fare_class"]: r["amount"] for r in _call(client, slug)["offers"]}
        assert plain["Y"] == 30000000                                    # no rule for the default group: sell = supplier fare
        body = {"public": False, "tenant_ref": slug, "price_group": gid, "origin": "THR", "destination": "MHD", "filters": {"depart": DAY}}
        grp = client.post("/internal/search/flight-suppliers", json=body, headers={"X-Internal-Token": TOKEN}).json()
        assert {r["attributes"]["fare_class"]: r["amount"] for r in grp["offers"]}["Y"] == 45000000
        with SessionLocal() as db:
            uid = db.scalar(select(User.id).where(User.email == "backoffice@aftab.test"))
            cap = PriceCap(tenant_id=tenant_id, origin="THR", destination="MHD", valid_from=datetime.now().date(),
                           valid_to=datetime.now().date() + timedelta(days=30), cap_unit_irr=25000000, legal_reference="TEST-CAP-PUBLIC", created_by_user_id=uid)
            db.add(cap)
            db.commit()
            cap_id = cap.id
        try:
            assert _call(client, slug)["offers"] == []                      # Y sell 30M > CAO cap 25M: not listed
        finally:
            _disable(PriceCap, cap_id)
    finally:
        _disable(MarkupRule, rid)


def test_sandbox_and_qaa_never_reach_public_search(client, monkeypatch, transport):
    monkeypatch.setenv("NIRA_MODE", "sandbox")
    monkeypatch.setenv("NIRA_AIRLINES", "A1")
    creds(monkeypatch, "A1")
    mock = transport(Mock({"a1.nirasoft.ir": avail()}))
    monkeypatch.setenv("MAHAN_MODE", "qaa")
    monkeypatch.setenv("MAHAN_QAA_API_KEY", "test-key-not-real")
    monkeypatch.setenv("MAHAN_QAA_OFFICE_USER", "TEST.USER")
    monkeypatch.setenv("MAHAN_QAA_OFFICE_PASS", "test-pass-not-real")
    mahan_calls = []
    monkeypatch.setattr(mf, "_transport", lambda: (lambda *a, **k: mahan_calls.append(a)))
    _, slug = _tenant()
    assert _call(client, slug)["offers"] == [] and mock.requests == [] and mahan_calls == []


class _StubMahan:
    key = "mahan"

    def __init__(self, fail=False):
        self.fail = fail

    def search(self, q, tz=None):
        if self.fail:
            raise mf.MahanError("NETWORK")
        dep = q.depart_on.replace(hour=9)
        seg = FlightSegment("W5", "1061", q.origin, q.destination, dep, dep + timedelta(minutes=80))
        return [FareOffer("ref", (seg,), 28000000, "IRR", "Y", None, datetime.now(timezone.utc) + timedelta(minutes=20))]


def test_one_supplier_failing_never_breaks_the_other(client, monkeypatch, transport):
    _live_nira(monkeypatch)
    transport(Mock({"api.vareshair.ir": avail(fn="2001", price="30000000"), "apps.merajairlines.ir": avail(fn="4001")}))
    monkeypatch.setenv("MAHAN_MODE", "live")
    monkeypatch.setattr(mf, "build_adapter", lambda secret: (_StubMahan(fail=True), {"mode": "live", "enabled": True}))
    _, slug = _tenant()
    body = _call(client, slug)
    assert {r["provider_key"] for r in body["offers"]} == {"nira"}
    assert any(s["provider"] == "mahan" and s["status"] == "error" for s in body["suppliers"])
    pfs.clear_cache()
    # Niira fully down, Mahan answers
    transport(Mock({"api.vareshair.ir": {"Error": "Sales Channel not Allowed"}, "apps.merajairlines.ir": {"Error": "Sales Channel not Allowed"}}))
    monkeypatch.setattr(mf, "build_adapter", lambda secret: (_StubMahan(), {"mode": "live", "enabled": True}))
    body = _call(client, slug)
    assert [(r["provider_key"], r["attributes"]["flight_number"], r["amount"]) for r in body["offers"]] == [("mahan", "1061", 28000000)]
    assert any(s["provider"] == "nira" and s["status"] == "error" for s in body["suppliers"])
    # the all-error Niira outcome was not cached: once it recovers, it is called again
    transport(Mock({"api.vareshair.ir": avail(fn="2001", price="30000000"), "apps.merajairlines.ir": avail(fn="4001")}))
    assert "nira" in {r["provider_key"] for r in _call(client, slug)["offers"]}


def test_slow_supplier_is_cut_at_the_deadline(client, monkeypatch, transport):
    import threading
    import time as _t
    monkeypatch.setenv("PUBLIC_FLIGHT_SUPPLIER_DEADLINE", "2")
    monkeypatch.setenv("MAHAN_MODE", "live")

    class Slow(_StubMahan):
        def search(self, q, tz=None):
            threading.Event().wait(4)      # time.sleep is stubbed out by the Niira test fixture
            return super().search(q, tz)
    monkeypatch.setattr(mf, "build_adapter", lambda secret: (Slow(), {"mode": "live", "enabled": True}))
    _, slug = _tenant()
    t0 = _t.monotonic()
    body = _call(client, slug)
    assert _t.monotonic() - t0 < 3.5
    assert body["offers"] == [] and [s["status"] for s in body["suppliers"]] == ["timeout"]


def test_unknown_city_or_missing_date_makes_no_supplier_call(client, monkeypatch, transport):
    _live_nira(monkeypatch)
    mock = transport(Mock({"api.vareshair.ir": avail()}))
    _, slug = _tenant()
    assert _call(client, slug, destination="شهر ناموجود")["offers"] == []
    body = {"public": False, "tenant_ref": slug, "origin": "THR", "destination": "MHD", "filters": {}}
    assert client.post("/internal/search/flight-suppliers", json=body, headers={"X-Internal-Token": TOKEN}).json()["offers"] == []
    assert mock.requests == []


def test_no_db_transaction_is_open_while_suppliers_are_called(client, monkeypatch, transport):
    _live_nira(monkeypatch)
    monkeypatch.setenv("NIRA_AIRLINES", "VR")
    seen = []
    real = pfs.fetch_offers

    def spy(*a, **k):
        seen.append(any(s.in_transaction() for s in list(_SESSIONS)))
        return real(*a, **k)
    _SESSIONS = []
    orig_rows = pfs.search_rows

    def rows(db, **kw):
        _SESSIONS.append(db)
        return orig_rows(db, **kw)
    monkeypatch.setattr(pfs, "fetch_offers", spy)
    monkeypatch.setattr(pfs, "search_rows", rows)
    transport(Mock({"api.vareshair.ir": avail(fn="2001")}))
    _, slug = _tenant()
    assert _call(client, slug)["offers"]
    assert seen == [False]


def test_request_token_round_trip_and_tamper():
    spec = {"p": "nira", "fn": "2001", "price": 33000000, "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())}
    tok = pfs.sign_request("s3cret", spec)
    assert pfs.verify_request("s3cret", tok)["price"] == 33000000
    raw, mac = tok.split(".")
    import base64
    forged = base64.urlsafe_b64encode(json.dumps({**spec, "price": 1}).encode()).decode().rstrip("=")
    for bad in (f"{forged}.{mac}", tok + "x", "nope", pfs.sign_request("other", spec)):
        with pytest.raises(pfs.RequestTokenError):
            pfs.verify_request("s3cret", bad)
    with pytest.raises(pfs.RequestTokenError):
        pfs.verify_request("s3cret", pfs.sign_request("s3cret", {**spec, "exp": 1}))


def test_booking_request_lands_in_the_sales_desk_with_flight_details(client, monkeypatch, transport):
    _live_nira(monkeypatch)
    monkeypatch.setenv("NIRA_AIRLINES", "VR")
    transport(Mock({"api.vareshair.ir": avail(fn="2001", price="30000000")}))
    _, slug = _tenant()
    monkeypatch.setenv("SALES_DESK_PUBLIC_TENANT", slug)
    row = next(r for r in _call(client, slug)["offers"] if r["attributes"]["fare_class"] == "Y")
    token = row["attributes"]["request_token"]
    mobile = "0912" + str(uuid.uuid4().int)[:7]
    base = {"customer_name": "مسافر آزمایشی", "mobile": mobile, "trip": "متن مرورگر که نباید ثبت شود", "travellers": 2, "consent": True,
            "description": "صبح زود تماس بگیرید"}
    assert client.post("/public/sales-desk/requests", json={**base, "flight_request": token + "x"}).status_code == 422
    r = client.post("/public/sales-desk/requests", json={**base, "flight_request": token})
    assert r.status_code == 202 and r.json() == {"received": True}
    with SessionLocal() as db:
        case = db.scalar(select(SalesCase).where(SalesCase.mobile == mobile))
        assert case.channel == "web_form" and case.stage == "new" and case.travellers == 2 and case.travel_date == DAY
        assert "2001" in case.trip and "THR" in case.trip and "MHD" in case.trip and "مرورگر" not in case.trip
        assert "30٬000٬000 ریال" in case.description and "کلاس نرخ: Y" in case.description and "صبح زود" in case.description
        created = db.scalar(select(SalesCaseActivity).where(SalesCaseActivity.case_id == case.id, SalesCaseActivity.kind == "created"))
        assert "30٬000٬000" in created.body and json.loads(created.detail_json)["flight_request"]["fn"] == "2001"
        case_id = case.id
    # the same request again is appended to the open case (duplicate branch) and still carries the flight details
    assert client.post("/public/sales-desk/requests", json={**base, "flight_request": token}).status_code == 202
    with SessionLocal() as db:
        assert len(db.scalars(select(SalesCase).where(SalesCase.mobile == mobile)).all()) == 1
        msg = db.scalar(select(SalesCaseActivity).where(SalesCaseActivity.case_id == case_id, SalesCaseActivity.kind == "message"))
        assert "2001" in msg.body and json.loads(msg.detail_json)["flight_request"]["price"] == 30000000
    # visible to the desk
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"email": "backoffice@aftab.test"}).json()["access_token"]}
    found = client.get("/sales-desk/cases", params={"q": mobile}, headers=h).json()["items"]
    assert [c["id"] for c in found] == [case_id]


def test_city_names_resolve_like_the_shipped_catalog():
    """Shape of build_catalog.py output: a city place + airports linked by city_id (city_name = the place's Persian name),
    Persian airport names, normalized search_text. Arabic ي/ك variants and the IATA code resolve too; nothing is guessed."""
    from app.catalog import CatalogPlace, normalize_text
    tag = uuid.uuid4().hex[:4]
    city_fa, city_id = f"شهرکی آزمون {tag}", f"ir-test-{tag}"
    letter = "ABCDEFGHIJKLMNOP"[int(tag[0], 16)]
    codes = [f"Q{letter}A", f"Q{letter}B"]                                   # IATA codes are letters only
    with SessionLocal() as db:
        db.add(CatalogPlace(id=city_id, kind="city", country_code="IR", name_fa=city_fa, name_en=f"Testcity {tag}",
                            search_text=normalize_text(f"{city_fa} testcity {tag}"), source="test"))
        for i, code in enumerate(codes):
            if db.get(CatalogAirport, code) is None:
                db.add(CatalogAirport(id=code, name_fa=f"فرودگاه آزمون {tag} {i}", name_en=f"Test {tag} {i}", city_id=city_id, city_name=city_fa,
                                      country_code="IR", latitude=0.0, longitude=0.0, timezone="Asia/Tehran", airport_type="medium_airport",
                                      scheduled_service=True, search_text=normalize_text(f"فرودگاه آزمون {tag} {i} {code} {city_fa}"), source="test"))
        db.commit()
    with SessionLocal() as db:
        assert set(pfs.resolve_airports(db, city_fa)) == set(codes)
        assert set(pfs.resolve_airports(db, city_fa.replace("ی", "ي").replace("ک", "ك"))) == set(codes)
        assert pfs.resolve_airports(db, f"فرودگاه آزمون {tag} 1") == [codes[1]]
        assert pfs.resolve_airports(db, codes[0].lower()) == [codes[0]]
        assert pfs.resolve_airports(db, f"آزمون {tag}") == []                 # partial text is not guessed into a city


def test_tehran_resolves_to_thr_and_ika_even_when_catalog_city_is_parandak():
    """The shipped catalogue lists THR and IKA under «پرندک» (OurAirports municipality); «تهران» must still find them."""
    for code, name in (("THR", "فرودگاه مهرآباد"), ("IKA", "فرودگاه امام خمینی")):
        with SessionLocal() as db:
            if db.get(CatalogAirport, code) is None:
                db.add(CatalogAirport(id=code, name_fa=name, name_en=code, city_id=None, city_name="پرندک", country_code="IR",
                                      latitude=0.0, longitude=0.0, timezone="Asia/Tehran", airport_type="large_airport",
                                      scheduled_service=True, search_text=name, source="test"))
                db.commit()
    with SessionLocal() as db:
        assert pfs.resolve_airports(db, "تهران") == ["THR", "IKA"]
        assert pfs.resolve_airports(db, "Tehran") == ["THR", "IKA"]
