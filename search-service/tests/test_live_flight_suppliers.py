"""Live Niira/Mahan request-only flights (provider `flight_suppliers_live`): listed next to the pool, sell price carried in a
public attribute, a failing supplier provider never breaks the search, and it is not attempted without origin/date.

TEST FIXTURES ONLY: both providers are stubbed; nothing calls the monolith or an airline."""
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import providers
from app.cache import CACHE
from app.main import app

client = TestClient(app)
DAY = (date.today() + timedelta(days=10)).isoformat()


def _row(fn, price):
    now = datetime.now(timezone.utc).isoformat()
    return {"id": f"supplier-flight:{fn}", "service_type": "flight", "title": "پرواز تهران به مشهد", "amount": price, "currency": "IRR",
            "available_units": None, "provider_key": "nira", "fulfillment_mode": "request", "policy": {}, "updated_at": now,
            "valid_until": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "attributes": {"booking_mode": "request", "entity_id": f"supplier-flight:{fn}", "airline": "وارش", "airline_code": "VR", "flight_number": fn,
                           "origin": "تهران", "destination": "مشهد", "departure_time": f"{DAY}T08:30:00+03:30", "arrival_time": f"{DAY}T10:00:00+03:30",
                           "request_price": price, "request_token": "tok", "observed_at": now, "freshness_ttl_seconds": 600}}


def _body(**extra):
    return {"verticals": ["flight"], "origin": "تهران", "destination": "مشهد", "public": True, "filters": {"depart": DAY, "adults": 1}, **extra}


def _clear():
    if hasattr(CACHE, "_d"):
        CACHE._d.clear()


def test_request_flights_listed_with_public_price(monkeypatch):
    _clear()
    monkeypatch.setattr(providers._POOL, "fetch", lambda v, req: [])
    seen = []
    monkeypatch.setattr(providers._LIVE_FLIGHTS, "fetch", lambda v, req: seen.append(req) or [_row("1001", 27_500_000), _row("1003", 26_000_000)])
    r = client.post("/v1/search", json=_body())
    assert r.status_code == 200
    ents = r.json()["entities"]
    assert len(ents) == 2                                            # one entity per flight, not merged under the shared title
    a = ents[0]["best_offer"]["attributes"]
    assert a["booking_mode"] == "request" and a["request_price"] in (26_000_000, 27_500_000)
    assert seen and seen[0].origin == "تهران"


def test_supplier_failure_keeps_pool_results(monkeypatch):
    _clear()
    pool_row = _row("POOL", 30_000_000)
    pool_row.update(id="pool-1", provider_key="manual_supplier", fulfillment_mode="manual_supplier")
    pool_row["attributes"] = {**pool_row["attributes"], "booking_mode": None, "entity_id": "pool-1"}
    monkeypatch.setattr(providers._POOL, "fetch", lambda v, req: [pool_row])

    def boom(v, req):
        raise RuntimeError("monolith supplier endpoint down")
    monkeypatch.setattr(providers._LIVE_FLIGHTS, "fetch", boom)
    r = client.post("/v1/search", json=_body(sort="cheapest"))
    assert r.status_code == 200
    body = r.json()
    assert [e["best_offer"]["id"] for e in body["entities"]] == ["pool-1"]
    assert body["search_metadata"]["partial_results"] is True


def test_not_attempted_without_origin_or_date(monkeypatch):
    _clear()
    monkeypatch.setattr(providers._POOL, "fetch", lambda v, req: [])
    called = []
    monkeypatch.setattr(providers._LIVE_FLIGHTS, "fetch", lambda v, req: called.append(1) or [])
    r = client.post("/v1/search", json={"verticals": ["flight"], "destination": "مشهد", "public": True})
    assert r.status_code == 200 and called == []
    fan = {m["provider"]: m["status"] for m in r.json()["provider_fanout"]}
    assert fan["flight_suppliers_live"] == "not_applicable"
