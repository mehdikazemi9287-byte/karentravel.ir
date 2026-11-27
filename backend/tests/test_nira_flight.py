"""Niira supplier behind flight_port: off ⇒ zero HTTP calls, sandbox ⇒ A1 only + staff only, live search across airlines with
route table and per-airline failure isolation, no internal fields to customers, staff console redaction, guarded writes.

TEST FIXTURES ONLY: synthetic NRS answers, fake users/passwords. HTTP is an httpx.MockTransport; nothing leaves the process.
"""
import json
import os
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from app import nira_flight as nf
from app.catalog import CatalogAirport
from app.flight_port import FlightContractViolation
from app.main import SessionLocal

DAY = (date.today() + timedelta(days=10)).isoformat()
NEXT = (date.today() + timedelta(days=11)).isoformat()
BACK = (date.today() + timedelta(days=14)).isoformat()
PASS = "pw-not-real-123"


def avail(day=DAY, o="THR", d="MHD", fn="1001", price="25000000"):
    return {"AvailableFlights": [
        {"Origin": o, "Destination": d, "DepartureDateTime": f"{day} 08:30:00", "ArrivalDateTime": f"{day} 10:00:00", "FlightNo": fn,
         "ClassesStatus": [{"FlightClass": "Y", "Cap": "A", "Price": price, "CurrencyCode": "IRR"},
                           {"FlightClass": "B", "Cap": "C", "Price": "19000000", "CurrencyCode": "IRR"}]},
        {"Origin": o, "Destination": d, "DepartureDateTime": f"{NEXT} 07:00:00", "ArrivalDateTime": f"{NEXT} 08:30:00", "FlightNo": "1099",   # other day
         "ClassesStatus": [{"FlightClass": "Y", "Cap": "A", "Price": "1000", "CurrencyCode": "IRR"}]}]}


class Mock:
    def __init__(self, by_host):
        self.by_host, self.requests = by_host, []

    def __call__(self, request):
        self.requests.append(request)
        ans = self.by_host.get(request.url.host)
        if callable(ans):
            ans = ans(request)
        if isinstance(ans, Exception):
            raise ans
        if ans is None:
            return httpx.Response(404)
        return httpx.Response(200, content=json.dumps(ans).encode())


def _login(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("NIRA_"):
            monkeypatch.delenv(k)
    monkeypatch.setattr(nf.time, "sleep", lambda s: None)
    with SessionLocal() as db:
        for code in ("THR", "MHD"):
            a = db.get(CatalogAirport, code)
            if a is None:
                db.add(CatalogAirport(id=code, name_en=f"{code} test airport", country_code="IR", latitude=0.0, longitude=0.0, timezone="Asia/Tehran", source="test"))
            elif not a.timezone:
                a.timezone = "Asia/Tehran"
        db.commit()
    yield


@pytest.fixture()
def transport(monkeypatch):
    def use(mock):
        monkeypatch.setattr(nf, "_http", lambda: httpx.Client(transport=httpx.MockTransport(mock)))
        return mock
    return use


def creds(monkeypatch, *codes):
    for c in codes:
        monkeypatch.setenv(f"NIRA_{c}_USER", f"{c}WS.TEST")
        monkeypatch.setenv(f"NIRA_{c}_PASS", PASS)


def _search(client, h, **extra):
    return client.post("/flights/suppliers/nira/search", headers=h, json={"origin": "THR", "destination": "MHD", "depart_on": DAY, "adults": 1, **extra})


def test_off_by_default_makes_zero_http_calls(client, monkeypatch, transport):
    mock = transport(Mock({}))
    calls = []
    monkeypatch.setattr(nf, "_http", lambda: calls.append(1))
    h = _login(client, "backoffice@aftab.test")
    r = _search(client, h).json()
    assert r["status"] == "unavailable" and r["reason"] == "off" and r["offers"] == []
    st = client.get("/flights/suppliers/nira/status", headers=h).json()
    assert st["mode"] == "off" and st["enabled"] is False and st["airlines"] == []
    assert client.post("/flights/suppliers/nira/console/availability", headers=h,
                       json={"airline": "A1", "origin": "THR", "destination": "MHD", "depart_on": DAY}).status_code == 503
    monkeypatch.setenv("NIRA_MODE", "bogus")
    assert _search(client, h).json()["reason"] == "invalid_mode"
    assert calls == [] and mock.requests == []


def test_sandbox_is_a1_only_and_staff_only(client, monkeypatch, transport):
    monkeypatch.setenv("NIRA_MODE", "sandbox")
    monkeypatch.setenv("NIRA_AIRLINES", "A1,VR")
    creds(monkeypatch, "A1", "VR")
    mock = transport(Mock({"a1.nirasoft.ir": avail()}))
    st = client.get("/flights/suppliers/nira/status", headers=_login(client, "backoffice@aftab.test")).json()
    assert {a["code"]: a["reason"] for a in st["airlines"]} == {"A1": "ok", "VR": "sandbox_only_a1"} and PASS not in json.dumps(st)
    cust = _search(client, _login(client, "employee@aftab.test")).json()
    assert cust["reason"] == "sandbox_test_only" and mock.requests == []
    body = _search(client, _login(client, "backoffice@aftab.test")).json()
    assert body["status"] == "ok" and body["test_inventory"] is True
    assert [(o["segments"][0]["carrier"], o["booking_class"], o["indicative_adult_fare"]) for o in body["offers"]] == [("A1", "Y", 25000000)]
    assert body["offers"][0]["segments"][0]["departs_at"].endswith("+03:30")
    assert {r.url.host for r in mock.requests} == {"a1.nirasoft.ir"} and len(mock.requests) == 1


def test_live_queries_only_enabled_airlines_on_route_and_isolates_failures(client, monkeypatch, transport):
    monkeypatch.setenv("NIRA_MODE", "live")
    monkeypatch.setenv("NIRA_AIRLINES", "VAR,J1,PA,QB,A1")
    creds(monkeypatch, "VR", "J1", "PA", "A1")                               # QB has no credentials
    monkeypatch.setenv("NIRA_PA_ROUTES", "THR-KIH")                          # PA does not fly THR-MHD
    mock = transport(Mock({"api.vareshair.ir": avail(fn="2001", price="30000000"), "apps.merajairlines.ir": httpx.ConnectError("down"),
                           "api.parsair.ir": avail(fn="3001")}))
    h = _login(client, "employee@aftab.test")
    body = _search(client, h).json()
    assert body["status"] == "ok" and body["test_inventory"] is False
    assert [(o["segments"][0]["carrier"], o["segments"][0]["flight_number"]) for o in body["offers"]] == [("VR", "2001")]
    hosts = [r.url.host for r in mock.requests]
    assert "api.parsair.ir" not in hosts and "a1.nirasoft.ir" not in hosts and hosts.count("apps.merajairlines.ir") == 3   # reads retry
    text = json.dumps(body)
    assert "airlines" not in body and PASS not in text and "WS.TEST" not in text and "office" not in text.lower() and "commission" not in text.lower()
    staff = _search(client, _login(client, "backoffice@aftab.test")).json()
    outcome = {a["code"]: (a["status"], a["error_code"]) for a in staff["airlines"]}
    assert outcome == {"VR": ("ok", None), "J1": ("error", "NETWORK")}


def test_live_all_airlines_failing_is_unavailable_not_empty_success(client, monkeypatch, transport):
    monkeypatch.setenv("NIRA_MODE", "live")
    monkeypatch.setenv("NIRA_AIRLINES", "VR")
    creds(monkeypatch, "VR")
    transport(Mock({"api.vareshair.ir": {"Error": "Sales Channel not Allowed"}}))
    body = _search(client, _login(client, "backoffice@aftab.test")).json()
    assert body["status"] == "unavailable" and body["reason"] == "provider_error" and body["offers"] == []
    assert body["airlines"][0]["error_code"] == "SALES_CHANNEL_NOT_ALLOWED"


def test_round_trip_pairs_same_airline(client, monkeypatch, transport):
    monkeypatch.setenv("NIRA_MODE", "live")
    monkeypatch.setenv("NIRA_AIRLINES", "VR")
    creds(monkeypatch, "VR")
    transport(Mock({"api.vareshair.ir": lambda req: avail(BACK, "MHD", "THR", "2002", "28000000") if req.url.params["cbSource"] == "MHD" else avail(fn="2001")}))
    body = _search(client, _login(client, "backoffice@aftab.test"), return_on=BACK).json()
    assert [(len(o["segments"]), o["indicative_adult_fare"]) for o in body["offers"]] == [(2, 53000000)]


def test_console_single_call_redacted_raw_and_errors(client, monkeypatch, transport):
    monkeypatch.setenv("NIRA_MODE", "sandbox")
    monkeypatch.setenv("NIRA_AIRLINES", "A1")
    creds(monkeypatch, "A1")
    answer = avail()
    answer["Echo"] = {"OfficePass": PASS, "Note": f"user A1WS.TEST pass {PASS}"}
    mock = transport(Mock({"a1.nirasoft.ir": answer}))
    staff = _login(client, "backoffice@aftab.test")
    body = {"airline": "A1", "origin": "THR", "destination": "MHD", "depart_on": DAY}
    assert client.post("/flights/suppliers/nira/console/availability", headers=_login(client, "employee@aftab.test"), json=body).status_code == 403
    r = client.post("/flights/suppliers/nira/console/availability", headers=staff, json=body).json()
    assert r["status"] == "ok" and [f["flight_no"] for f in r["flights"]] == ["1001"] and r["rejected"] == [{"flight_no": "1099", "reason": "date_mismatch"}]
    assert PASS not in json.dumps(r) and "A1WS.TEST" not in json.dumps(r) and r["raw"]["AvailableFlights"]
    assert len(mock.requests) == 1
    assert client.post("/flights/suppliers/nira/console/availability", headers=staff, json={**body, "airline": "VR"}).status_code == 404
    mock.by_host["a1.nirasoft.ir"] = {"Error": "Sales Channel not Allowed"}
    r = client.post("/flights/suppliers/nira/console/availability", headers=staff, json=body).json()
    assert r["status"] == "error" and r["error"]["code"] == "SALES_CHANNEL_NOT_ALLOWED" and r["error"]["category"] == "account" and r["error"]["message"]
    mock.by_host["a1.nirasoft.ir"] = httpx.ConnectError("x")
    before = len(mock.requests)
    r = client.post("/flights/suppliers/nira/console/availability", headers=staff, json=body).json()
    assert r["error"]["code"] == "NETWORK" and len(mock.requests) - before == 1                # console: exactly one call


def test_offer_ref_signing_and_guarded_writes():
    now = datetime.now(timezone.utc)
    adapter = nf.NiraFlightAdapter("live", {}, nf.OfferSigner("secret"), now=lambda: now)
    ref = adapter.signer.sign({"p": "nira", "env": "live", "exp": int((now + timedelta(minutes=5)).timestamp())})
    assert adapter.selection(ref)["env"] == "live"
    with pytest.raises(nf.OfferRefError):
        adapter.selection(ref[:-2] + "xx")
    with pytest.raises(nf.OfferRefError):
        nf.NiraFlightAdapter("sandbox", {}, nf.OfferSigner("secret"), now=lambda: now).selection(ref)
    for call in (lambda: adapter.create_pnr(None, [], "k"), lambda: adapter.issue("X", "k"), lambda: adapter.void("X", "k"), lambda: adapter.refund("X", "k")):
        with pytest.raises(FlightContractViolation):
            call()
