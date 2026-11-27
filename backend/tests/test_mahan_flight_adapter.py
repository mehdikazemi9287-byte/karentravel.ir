"""Mahan flight adapter behind flight_port: disabled/credential fail-closed, search mapping, revalidate price change,
hold (Book) with idempotency, errors, CAO cap, and the disabled issuance path.

TEST FIXTURES ONLY: every Mahan answer below is synthetic (fake flights, fake prices, fake PNR "TST001", fake keys).
The HTTP layer is replaced by `Fake`; no test reaches a real Mahan endpoint.
"""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import delete, select

from app import mahan_flight as mf
from app import operations as m
from app.catalog import CatalogAirport
from app.charter_blocks import PriceCap
from app.commerce import MarkupRule
from app.main import AuditEvent, SessionLocal, User
from app.mahan_mrs import MahanClient, MahanError, parse_quote

DAY = (date.today() + timedelta(days=10)).isoformat()
BACK = (date.today() + timedelta(days=14)).isoformat()

# --- synthetic MRS answers (test fixtures, not real Mahan data) ---
AVAIL_OUT = {"AvailableFlights": [
    {"FlightNo": "9001", "Origin": "IKA", "Destination": "BKK", "DepartureDateTime": f"{DAY} 02:30", "ArrivalDateTime": f"{DAY} 12:10",
     "ClassesStatus": [{"FlightClass": "Y", "Cap": "YA", "Price": "50000000", "CurrencyCode": "IRR"},
                       {"FlightClass": "R", "Cap": "R2", "Price": "90000000", "CurrencyCode": "IRR"},
                       {"FlightClass": "B", "Cap": "BX", "Price": "40000000", "CurrencyCode": "IRR"},     # closed
                       {"FlightClass": "M", "Cap": "MA", "Price": "-", "CurrencyCode": "IRR"}]},          # no price
    {"FlightNo": "9003", "Origin": "IKA", "Destination": "BKK", "DepartureDateTime": f"{DAY} 08:00",       # no arrival time -> dropped
     "ClassesStatus": [{"FlightClass": "Y", "Cap": "YA", "Price": "45000000", "CurrencyCode": "IRR"}]}]}
AVAIL_BACK = {"AvailableFlights": [
    {"FlightNo": "9002", "Origin": "BKK", "Destination": "IKA", "DepartureDateTime": f"{BACK} 14:00", "ArrivalDateTime": f"{BACK} 18:30",
     "ClassesStatus": [{"FlightClass": "Y", "Cap": "Y4", "Price": "52000000", "CurrencyCode": "IRR"}]}]}


def quote(total=64000000, ad=1, ch=0, per_type=None):
    br = [{"AgeType": "AD", "Quantity": ad, "TotalPrice": str(per_type["AD"]) if per_type else None,
           "Taxes": [{"TaxType": "YQ", "TotalTaxAmount": "1000000"}]}]
    if ch:
        br.append({"AgeType": "CH", "Quantity": ch, "TotalPrice": str(per_type["CH"]) if per_type else None, "Taxes": []})
    return {"errorCode": 0, "result": {"Currency": "IRR", "TotalFare": str(total - 4000000), "TotalTax": "4000000", "TotalPrice": str(total),
                                       "Cabin": "Y", "Coupons": [], "PassengerBreakdown": br}}


BOOK_OK = {"errorCode": 0, "result": {"PNR": "TST001"}}


class Fake:
    """Replaces the HTTP layer. Routes: url fragment -> list of (status, body) answers, consumed in order (last repeats)."""

    def __init__(self, routes):
        self.routes = {k: list(v) if isinstance(v, list) else [v] for k, v in routes.items()}
        self.calls = []

    def __call__(self, method, url, json=None, headers=None):
        self.calls.append((method, url, json))
        assert url.startswith("https://api.mahanair.co.ir/ws") and "-qaa" in url, "tests only ever address the QAA shape"
        for key, answers in self.routes.items():
            if key in url:
                ans = answers.pop(0) if len(answers) > 1 else answers[0]
                if isinstance(ans, Exception):
                    raise ans
                status, body = ans
                return httpx.Response(status, content=__import__("json").dumps(body).encode(), headers={"content-type": "application/json"})
        return httpx.Response(404)

    def count(self, frag):
        return sum(1 for c in self.calls if frag in c[1])


class AvailFake(Fake):
    """Availability answer depends on the requested direction."""

    def __call__(self, method, url, json=None, headers=None):
        if "AvailabilityFareJS" in url:
            self.calls.append((method, url, json))
            body = AVAIL_BACK if "cbSource=BKK" in url else AVAIL_OUT
            return httpx.Response(200, content=__import__("json").dumps(body).encode(), headers={"content-type": "application/json"})
        return super().__call__(method, url, json, headers)


def _login(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def qaa(monkeypatch):
    monkeypatch.setenv("MAHAN_MODE", "qaa")
    monkeypatch.setenv("MAHAN_QAA_API_KEY", "test-key-not-real")
    monkeypatch.setenv("MAHAN_QAA_OFFICE_USER", "TEST.USER")
    monkeypatch.setenv("MAHAN_QAA_OFFICE_PASS", "test-pass-not-real")
    monkeypatch.setattr(mf.time, "sleep", lambda s: None)

    def use(fake):
        monkeypatch.setattr(mf, "_transport", lambda: fake)
        return fake
    return use


@pytest.fixture(autouse=True)
def airports():
    with SessionLocal() as db:
        for code, tz, cc in (("IKA", "Asia/Tehran", "IR"), ("BKK", "Asia/Bangkok", "TH")):
            if db.get(CatalogAirport, code) is None:
                db.add(CatalogAirport(id=code, name_en=f"{code} test airport", country_code=cc, latitude=0.0, longitude=0.0, timezone=tz, source="test"))
            elif not db.get(CatalogAirport, code).timezone:
                db.get(CatalogAirport, code).timezone = tz
        db.commit()
    yield


@pytest.fixture()
def markup():
    """A fixed 1,000,000 IRR/adult markup for supplier 'mahan' (test rule, removed afterwards)."""
    with SessionLocal() as db:
        tenant_id = db.scalar(select(User.tenant_id).where(User.email == "backoffice@aftab.test"))
        rule = MarkupRule(tenant_id=tenant_id, title="test mahan markup", service_type="flight", supplier_id="mahan", calc="fixed", adult=1_000_000, child=500_000)
        db.add(rule)
        db.commit()
        rid = rule.id
    yield tenant_id
    with SessionLocal() as db:
        db.execute(delete(MarkupRule).where(MarkupRule.id == rid))
        db.commit()


def _search(client, h, **extra):
    body = {"origin": "IKA", "destination": "BKK", "depart_on": DAY, "adults": 1, **extra}
    return client.post("/flights/suppliers/mahan/search", headers=h, json=body)


PAX = {"type": "ADT", "first_name": "Testa", "last_name": "Fixture", "gender": "F", "birth_date": "1986-01-07", "document_type": "P",
       "document_number": "T1234567", "document_expiry": "2030-11-16", "nationality": "IRN"}


# ---------------------------------------------------------------- fail closed
def test_disabled_by_default_returns_no_flights_and_never_calls_mahan(client, monkeypatch):
    monkeypatch.delenv("MAHAN_MODE", raising=False)
    calls = []
    monkeypatch.setattr(mf, "_transport", lambda: calls.append(1))
    h = _login(client, "backoffice@aftab.test")
    r = _search(client, h)
    assert r.status_code == 200 and r.json()["offers"] == [] and r.json()["reason"] == "disabled" and r.json()["status"] == "unavailable"
    assert client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": "x" * 30}).status_code == 503
    hold = client.post("/flights/suppliers/mahan/hold", headers={**h, "Idempotency-Key": "k-disabled-1"},
                       json={"offer_ref": "x" * 30, "expected_total": 1, "contact_phone": "+989000000000", "passengers": [PAX]})
    assert hold.status_code == 503 and hold.json()["detail"]["code"] == "MAHAN_DISABLED"
    assert calls == [] and client.get("/flights/suppliers/mahan/status", headers=h).json()["enabled"] is False


def test_invalid_mode_and_missing_credentials_fail_closed(client, monkeypatch):
    for var in ("MAHAN_API_KEY", "MAHAN_API_KEY_B64", "MAHAN_OFFICE_USER", "MAHAN_OFFICE_PASS"):
        monkeypatch.delenv(var, raising=False)
    h = _login(client, "backoffice@aftab.test")
    monkeypatch.setenv("MAHAN_MODE", "production")
    assert _search(client, h).json()["reason"] == "invalid_mode"
    monkeypatch.setenv("MAHAN_MODE", "live")                    # Mahan has not granted production access: no live credentials
    st = client.get("/flights/suppliers/mahan/status", headers=h).json()
    assert st["reason"] == "missing_credentials" and set(st["missing_settings"]) == {"MAHAN_API_KEY", "MAHAN_OFFICE_USER", "MAHAN_OFFICE_PASS"}
    assert "test-key" not in json.dumps(st)
    r = _search(client, h)
    assert r.json()["offers"] == [] and r.json()["reason"] == "missing_credentials"


def test_qaa_is_staff_only(client, qaa):
    fake = qaa(AvailFake({}))
    r = _search(client, _login(client, "employee@aftab.test"))
    assert r.json()["reason"] == "qaa_test_only" and r.json()["offers"] == [] and fake.calls == []
    hold = client.post("/flights/suppliers/mahan/hold", headers={**_login(client, "employee@aftab.test"), "Idempotency-Key": "k-qaa-cust-1"},
                       json={"offer_ref": "x" * 30, "expected_total": 1, "contact_phone": "+989000000000", "passengers": [PAX]})
    assert hold.status_code == 403


# ---------------------------------------------------------------- search mapping
def test_search_maps_open_priced_classes_with_timezones(client, qaa):
    fake = qaa(AvailFake({}))
    r = _search(client, _login(client, "backoffice@aftab.test"))
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok" and body["test_inventory"] is True and body["price_state"] == "INDICATIVE"
    got = [(o["segments"][0]["flight_number"], o["booking_class"], o["indicative_adult_fare"]) for o in body["offers"]]
    assert got == [("9001", "Y", 50000000), ("9001", "R", 90000000)]        # closed, unpriced and arrival-less options dropped
    seg = body["offers"][0]["segments"][0]
    assert seg["departs_at"].endswith("+03:30") and seg["arrives_at"].endswith("+07:00") and seg["carrier"] == "W5"
    assert "net" not in json.dumps(body) and "supplier" not in json.dumps(body)
    assert fake.count("AvailabilityFareJS") == 1 and "test-key-not-real" not in fake.calls[0][1]


def test_round_trip_search_pairs_legs(client, qaa):
    qaa(AvailFake({}))
    body = _search(client, _login(client, "backoffice@aftab.test"), return_on=BACK).json()
    assert [(len(o["segments"]), o["indicative_adult_fare"]) for o in body["offers"]] == [(2, 102000000), (2, 142000000)]


def test_search_retries_transport_errors_then_reports_provider_error(client, qaa):
    fake = qaa(Fake({"AvailabilityFareJS": [httpx.ConnectError("boom"), (200, AVAIL_OUT)]}))
    assert len(_search(client, _login(client, "backoffice@aftab.test")).json()["offers"]) == 2 and fake.count("AvailabilityFareJS") == 2
    fake = qaa(Fake({"AvailabilityFareJS": (503, {})}))
    r = _search(client, _login(client, "backoffice@aftab.test")).json()
    assert r["offers"] == [] and r["status"] == "unavailable" and fake.count("AvailabilityFareJS") == 1 + mf.READ_RETRIES


def test_tampered_or_foreign_offer_ref_is_refused(client, qaa):
    qaa(AvailFake({}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    raw, sig = ref.split(".")
    assert client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": raw[:-2] + "AA." + sig}).json()["detail"]["code"] == "OFFER_EXPIRED"
    other = mf.OfferSigner("another-secret").sign({"p": "mahan", "env": "qaa", "pax": [1, 0, 0], "exp": 9999999999, "segs": []})
    assert client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": other}).status_code == 409


# ---------------------------------------------------------------- revalidate
def test_revalidate_applies_markup_and_reports_price_change(client, qaa, markup):
    fake = qaa(AvailFake({"FareQuote": (200, quote(64000000))}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    r = client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": ref, "expected_total": 65000000}).json()
    assert r["status"] == "ok" and r["total_amount"] == 65000000 and r["price_state"] == "RECHECKED"
    assert r["per_passenger"] == [{"type": "adult", "count": 1, "unit_amount": 65000000}]
    assert "64000000" not in json.dumps(r) and "margin" not in r and "net_total" not in r   # supplier cost never shown
    seg = fake.calls[-1][2]["Segments"][0]
    assert seg == {"AirlineCode": "W5", "Origin": "IKA", "Destination": "BKK", "FlightClass": "Y", "Departure": DAY, "FlightNo": "9001"}
    fake.routes["FareQuote"] = [(200, quote(70000000))]
    r = client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": ref, "expected_total": 65000000}).json()
    assert r["status"] == "price_changed" and r["total_amount"] == 71000000 and r["previous_amount"] == 65000000 and r["delta"] == 6000000


def test_mixed_party_needs_verifiable_breakdown(client, qaa, markup):
    fake = qaa(AvailFake({"FareQuote": (200, quote(100000000, ad=1, ch=1))}))     # no per-passenger totals
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h, children=1).json()["offers"][0]["offer_ref"]
    assert client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": ref}).json()["detail"]["code"] == "FARE_UNAVAILABLE"
    fake.routes["FareQuote"] = [(200, quote(100000000, ad=1, ch=1, per_type={"AD": 60000000, "CH": 40000000}))]
    r = client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": ref}).json()
    assert r["per_passenger"] == [{"type": "adult", "count": 1, "unit_amount": 61000000}, {"type": "child", "count": 1, "unit_amount": 40500000}]
    assert r["total_amount"] == 101500000


def test_cao_cap_blocks_price_above_cap(client, qaa, markup):
    qaa(AvailFake({"FareQuote": (200, quote(64000000))}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == "backoffice@aftab.test"))
        cap = PriceCap(tenant_id=markup, origin="IKA", destination="BKK", valid_from=date.today(), valid_to=date.today() + timedelta(days=30),
                       cap_unit_irr=64500000, legal_reference="TEST-CAP", created_by_user_id=uid)
        db.add(cap)
        db.commit()
        cap_id = cap.id
    try:
        r = client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": ref})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "PRICE_CAP_EXCEEDED"
    finally:
        with SessionLocal() as db:
            db.execute(delete(PriceCap).where(PriceCap.id == cap_id))
            db.commit()


# ---------------------------------------------------------------- hold / book
def _hold(client, h, ref, key, total=65000000, pax=None):
    return client.post("/flights/suppliers/mahan/hold", headers={**h, "Idempotency-Key": key},
                       json={"offer_ref": ref, "expected_total": total, "contact_phone": "+989000000000", "passengers": pax or [PAX]})


def test_hold_books_once_is_idempotent_and_never_issues(client, qaa, markup):
    fake = qaa(AvailFake({"FareQuote": (200, quote(64000000)), "Res/Book": (200, BOOK_OK)}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    key = f"hold-{uuid.uuid4().hex}"
    r = _hold(client, h, ref, key)
    body = r.json()
    assert r.status_code == 201 and body["status"] == "held" and body["ticketing"] == "not_issued" and body["test_booking"] is True
    assert body["total_amount"] == 65000000 and body["record_locator"] == "TST001"          # staff (QAA) sees the locator
    book = fake.calls[-1][2]
    assert book["Contact"] == "+989000000000" and book["Passengers"][0]["SSRs"][0]["FreeText"] == "P/IRN/T1234567/IRN/07JAN86/F/16NOV30/FIXTURE/TESTA"
    assert _hold(client, h, ref, key).json() == body and fake.count("Res/Book") == 1           # replay: no second Book
    assert _hold(client, h, ref, key, pax=[{**PAX, "first_name": "Other"}]).status_code == 409  # same key, different request
    assert not any("ETIssueJS" in c[1] for c in fake.calls)
    issue = client.post(f"/flights/suppliers/mahan/holds/{body['hold_id']}/issue", headers=h)
    assert issue.status_code == 423 and issue.json()["detail"]["code"] == "ISSUANCE_DISABLED"
    with SessionLocal() as db:
        ev = db.scalar(select(AuditEvent).where(AuditEvent.action == "flight.mahan.held").order_by(AuditEvent.id.desc()))
        detail = json.loads(ev.detail)
        assert detail["record_locator"] == "TST001" and detail["net_total"] == 64000000 and detail["margin"] == 1000000
        assert detail["vat_on_commission"] == 100000 and "Testa" not in ev.detail and "T1234567" not in ev.detail   # VAT on commission only; no PII


def test_recent_holds_list_is_staff_only_tenant_scoped_and_has_no_passenger_data(client, qaa, markup):
    qaa(AvailFake({"FareQuote": (200, quote(64000000)), "Res/Book": (200, BOOK_OK)}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    held = _hold(client, h, ref, f"hold-{uuid.uuid4().hex}").json()
    changed = _hold(client, h, ref, f"hold-{uuid.uuid4().hex}", total=1).json()["detail"]
    r = client.get("/flights/suppliers/mahan/holds", headers=h)
    assert r.status_code == 200
    items = {i["hold_id"]: i for i in r.json()["items"]}
    assert items[held["hold_id"]]["status"] == "held" and items[held["hold_id"]]["record_locator"] == "TST001"
    assert items[held["hold_id"]]["total_amount"] == 65000000 and items[held["hold_id"]]["test_booking"] is True
    assert items[changed["hold_id"]]["status"] == "price_changed"
    assert "Testa" not in r.text and "T1234567" not in r.text and "net_total" not in r.text and "margin" not in r.text
    assert client.get("/flights/suppliers/mahan/holds", headers=_login(client, "employee@aftab.test")).status_code == 403
    with SessionLocal() as db:                                   # another tenant's hold is never listed
        other = db.scalar(select(User.tenant_id).where(User.tenant_id != markup))
        assert other is not None
        db.add(m.IdempotencyKey(tenant_id=other, scope=mf.HOLD_SCOPE, key=f"foreign-{uuid.uuid4().hex}", request_hash="x",
                                response_json=json.dumps({"status": "held", "record_locator": "FOREIGN"})))
        db.commit()
    assert "FOREIGN" not in client.get("/flights/suppliers/mahan/holds?limit=100", headers=h).text


def test_hold_price_changed_does_not_book(client, qaa, markup):
    fake = qaa(AvailFake({"FareQuote": (200, quote(70000000)), "Res/Book": (200, BOOK_OK)}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    r = _hold(client, h, ref, f"hold-{uuid.uuid4().hex}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PRICE_CHANGED" and r.json()["detail"]["total_amount"] == 71000000
    assert fake.count("Res/Book") == 0


def test_hold_refused_and_lost_answers(client, qaa, markup):
    fake = qaa(AvailFake({"FareQuote": (200, quote(64000000)), "Res/Book": (200, {"errorCode": 12, "result": {}, "description_en": "test refusal"})}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    r = _hold(client, h, ref, f"hold-{uuid.uuid4().hex}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "BOOK_REFUSED" and "test refusal" not in r.text
    fake.routes["Res/Book"] = [httpx.ReadTimeout("lost")]
    key = f"hold-{uuid.uuid4().hex}"
    r = _hold(client, h, ref, key)
    assert r.status_code == 201 and r.json()["status"] == "unknown" and fake.count("Res/Book") == 2   # one attempt each, no retry
    assert _hold(client, h, ref, key).json()["status"] == "unknown" and fake.count("Res/Book") == 2


def test_hold_validates_party_against_offer(client, qaa, markup):
    fake = qaa(AvailFake({"FareQuote": (200, quote(64000000)), "Res/Book": (200, BOOK_OK)}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    r = _hold(client, h, ref, f"hold-{uuid.uuid4().hex}", pax=[PAX, {**PAX, "first_name": "Second", "document_number": "T7654321"}])
    assert r.status_code == 422 and fake.count("Res/Book") == 0


def test_in_progress_claim_blocks_parallel_duplicate(client, qaa):
    qaa(AvailFake({}))
    h = _login(client, "backoffice@aftab.test")
    ref = _search(client, h).json()["offers"][0]["offer_ref"]
    key = f"hold-{uuid.uuid4().hex}"
    body = {"offer_ref": ref, "expected_total": 65000000, "contact_phone": "+989000000000", "passengers": [PAX]}
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "backoffice@aftab.test"))
        pax = [mf.PassengerIn(**PAX).model_dump()]
        h_ = mf._canonical_hash({"user": u.id, "offer_ref": ref, "expected_total": 65000000, "contact": "+989000000000", "passengers": pax})
        db.add(m.IdempotencyKey(tenant_id=u.tenant_id, scope=mf.HOLD_SCOPE, key=key, request_hash=h_, response_json=json.dumps({"status": "in_progress"})))
        db.commit()
    r = client.post("/flights/suppliers/mahan/hold", headers={**h, "Idempotency-Key": key}, json=body)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "HOLD_IN_PROGRESS"


# ---------------------------------------------------------------- port surface
def test_adapter_port_surface_and_passenger_mapping():
    fake = Fake({"FareQuote": (200, quote(64000000))})
    cli = MahanClient(env="qaa", api_key="test-key-not-real", transport=fake)
    ad = mf.MahanFlightAdapter("qaa", cli, mf.OfferSigner("s"), sleep=lambda s: None)
    with pytest.raises(Exception):
        ad.issue("TST001", "k")
    assert ad.schedule_changes(datetime.now(timezone.utc)) == [] and ad.fare_rules(None) == {}
    with pytest.raises(ValueError):
        mf.MahanFlightAdapter("disabled", cli, mf.OfferSigner("s"))
    segs = [{"FlightNo": "9001", "DepartureDate": DAY}]
    inf = {**PAX, "type": "INF", "first_name": "Baby", "birth_date": (date.today() - timedelta(days=270)).isoformat()}
    rows = mf.mahan_passengers([mf.PassengerIn(**p).model_dump() for p in (PAX, inf)], segs)
    assert len(rows) == 1 and [s["SSRType"] for s in rows[0]["SSRs"]] == ["DOCS", "INFT"] and rows[0]["SSRs"][1]["FreeText"].startswith("FIXTURE/BABY ")
    with pytest.raises(ValueError):
        mf.mahan_passengers([mf.PassengerIn(**inf).model_dump()], segs)
    with pytest.raises(MahanError):
        mf.priced_quote(parse_quote({**quote(), "result": {**quote()["result"], "Currency": "USD"}}), {"adult": 1})


# ---------------------------------------------------------------- system-flight markup (flight_pricing, PR-1)
def _rules(tenant_id, *specs):
    """Test markup rules for supplier 'mahan'; returns ids for cleanup."""
    with SessionLocal() as db:
        rows = [MarkupRule(tenant_id=tenant_id, service_type="flight", supplier_id="mahan", calc="percent", **s) for s in specs]
        db.add_all(rows)
        db.commit()
        return [r.id for r in rows]


def _drop_rules(ids):
    with SessionLocal() as db:
        db.execute(delete(MarkupRule).where(MarkupRule.id.in_(ids)))
        db.commit()


def _tenant():
    with SessionLocal() as db:
        return db.scalar(select(User.tenant_id).where(User.email == "backoffice@aftab.test"))


def test_system_domestic_rule_applies_to_mahan_and_charter_rule_does_not():
    from app.flight_pricing import flight_scope
    tenant_id = _tenant()
    with SessionLocal() as db:
        for code in ("THR", "MHD"):
            if db.get(CatalogAirport, code) is None:
                db.add(CatalogAirport(id=code, name_en=f"{code} test airport", country_code="IR", latitude=0.0, longitude=0.0, timezone="Asia/Tehran", source="test"))
        db.commit()
    ids = _rules(tenant_id,
                 {"title": "test system domestic 15%", "scope": "domestic", "flight_type": "system", "adult": 1500},
                 {"title": "test charter 40% (must not match)", "scope": "domestic", "flight_type": "charter", "adult": 4000, "priority": 1},
                 {"title": "test international 30% (must not match domestic)", "scope": "international", "flight_type": "system", "adult": 3000, "priority": 1})
    try:
        pq = mf.PricedQuote(currency="IRR", net_total=20000000, net_unit={"adult": 20000000}, counts={"adult": 1}, cabin="Y")
        sel = {"segs": [{"o": "THR", "d": "MHD", "dt": DAY}]}
        with SessionLocal() as db:
            assert flight_scope(db, ["THR", "MHD"]) == "domestic" and flight_scope(db, ["IKA", "BKK"]) == "international"
            assert flight_scope(db, ["THR", "ZZZ"]) == "international"                 # unknown airport is never assumed domestic
            p = mf.sell_price(db, tenant_id, None, sel, pq)
        assert p["scope"] == "domestic" and p["sell_total"] == 23000000 and p["sell_unit"] == {"adult": 23000000} and p["margin"] == 3000000
        assert ids[0] == p["rule_id"]
        assert mf.public_price(p) == {"total_amount": 23000000, "currency": "IRR", "per_passenger": [{"type": "adult", "count": 1, "unit_amount": 23000000}]}
    finally:
        _drop_rules(ids)


def test_system_international_rule_changes_search_and_revalidate_and_hides_net(client, qaa):
    fake = qaa(AvailFake({"FareQuote": (200, quote(64000000))}))
    ids = _rules(_tenant(), {"title": "test system intl 10%", "scope": "international", "flight_type": "system", "adult": 1000},
                 {"title": "test domestic 50% (must not match IKA-BKK)", "scope": "domestic", "flight_type": "system", "adult": 5000, "priority": 1})
    try:
        h = _login(client, "backoffice@aftab.test")
        body = _search(client, h).json()
        assert [o["indicative_adult_fare"] for o in body["offers"]] == [55000000, 99000000]     # 50M / 90M net + 10%
        assert "50000000" not in json.dumps(body) and "90000000" not in json.dumps(body)
        r = client.post("/flights/suppliers/mahan/revalidate", headers=h, json={"offer_ref": body["offers"][0]["offer_ref"]}).json()
        assert r["total_amount"] == 70400000 and "64000000" not in json.dumps(r) and "net_total" not in r
        assert fake.count("AvailabilityFareJS") == 1
    finally:
        _drop_rules(ids)
