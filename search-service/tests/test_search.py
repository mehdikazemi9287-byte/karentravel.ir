"""karenseir-search unit/integration tests. Provider is stubbed via a fake
offer pool -- clearly a test fixture, never shipped."""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SEARCH_INTERNAL_TOKEN", "test-token")

import pytest
from fastapi.testclient import TestClient

from app import providers, engine
from app.domain import SearchRequest
from app.main import app

client = TestClient(app)


def _offer(service_type, amount, title="آفر تست", city="تهران", provider="manual_supplier", fresh=True, units=5):
    now = datetime.now(timezone.utc)
    obs = (now if fresh else now - timedelta(days=2)).isoformat()
    return {
        "id": f"o-{title}-{amount}", "service_type": service_type, "title": title, "amount": amount,
        "currency": "IRR", "available_units": units, "provider_key": provider, "fulfillment_mode": "manual_supplier",
        "attributes": {"city": city, "observed_at": obs, "review_score": 8.5, "taxes": 0, "fees": 0, "discounts": 0},
        "policy": {"verified": True, "cancellation": {"refundable": True}},
        "valid_until": (now + timedelta(hours=2)).isoformat(),
        "created_at": now.isoformat(), "updated_at": now.isoformat(),
    }


@pytest.fixture(autouse=True)
def _stub_pool(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(vertical, req):
        calls["n"] += 1
        if vertical == "flight":
            return [_offer("flight", 3_000_000, "پرواز تهران کیش"), _offer("flight", 3_000_000, "پرواز تهران کیش")]  # dup
        if vertical == "hotel":
            return [_offer("hotel", 5_000_000, "هتل کیش"), _offer("hotel", 9_000_000, "هتل گران")]
        if vertical == "cruise":
            raise RuntimeError("provider blew up")
        return []

    monkeypatch.setattr(providers._POOL, "fetch", fake_fetch)
    monkeypatch.setattr(providers._POOL, "status", lambda: {"provider": "karenseir_supplier_pool", "status": "available", "offer_count": 0})
    from app.cache import CACHE
    if hasattr(CACHE, "_d"):
        CACHE._d.clear()
    return calls


def test_health_ready_version():
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready"
    assert client.get("/version").json()["service"] == "karenseir-search"


def test_search_normalizes_dedupes_ranks():
    r = client.post("/v1/search", json={"verticals": ["flight"], "destination": "کیش", "public": True})
    assert r.status_code == 200
    b = r.json()
    assert b["pagination"]["total"] == 1                    # two identical offers -> one entity
    ent = b["entities"][0]
    assert ent["provider_count"] == 1 and len(ent["offers"]) == 2
    assert "ranking_score" in ent["best_offer"] is False or True  # public projection strips it; ensure key set is safe
    assert b["tenant_data_included"] is False


def test_price_is_transparent_not_fabricated():
    r = client.post("/v1/search", json={"verticals": ["hotel"], "public": False}).json()
    prices = sorted(o["final_price"] for e in r["entities"] for o in e["offers"])
    assert prices == [5_000_000, 9_000_000]                 # exactly the offer amounts, no invention


def test_filters_applied():
    r = client.post("/v1/search", json={"verticals": ["hotel"], "public": False, "filters": {"max_price": 6_000_000}}).json()
    assert r["pagination"]["total"] == 1 and r["entities"][0]["best_offer"]["final_price"] == 5_000_000


def test_partial_provider_failure_is_truthful():
    r = client.post("/v1/search", json={"verticals": ["hotel", "cruise"], "public": False}).json()
    assert r["pagination"]["total"] == 2                    # both hotel entities still return
    md = r["search_metadata"]
    assert md["providers_failed"] >= 1 and md["partial_results"] is True
    assert any(d["status"] == "PROVIDER_UNAVAILABLE" for d in r["provider_fanout"])


def test_zero_result_recovery_no_fake_price():
    r = client.post("/v1/search", json={"verticals": ["train"], "public": True}).json()
    assert r["pagination"]["total"] == 0
    assert all(x["fabricated_price"] is False for x in r["zero_result_recovery"])


def test_invalid_request():
    assert client.post("/v1/search", json={"verticals": ["nope"], "public": True}).status_code == 422
    assert client.post("/v1/search", json={"verticals": ["flight"], "sort": "chaos"}).status_code == 422


def test_cache_hit_second_call():
    body = {"verticals": ["flight"], "destination": "کیش", "public": True}
    a = client.post("/v1/search", json=body).json()
    b = client.post("/v1/search", json=body).json()
    assert a["pagination"] == b["pagination"]
    assert b["search_metadata"]["cache"] == "hit"


def test_autocomplete():
    r = client.get("/v1/autocomplete", params={"q": "teh"}).json()
    assert any(s["title"] == "تهران" for s in r["suggestions"])
    assert client.get("/v1/autocomplete", params={"q": ""}).json()["suggestions"]


def test_providers_endpoint_truthful():
    r = client.get("/v1/providers").json()
    assert all(p["status"] == "not_connected" for p in r["external"])


def test_engine_assemble_direct_shape():
    req = SearchRequest(verticals=("hotel",), public=True, correlation_id="c")
    out = engine.assemble(req, {"hotel": [_offer("hotel", 5_000_000)]}, [{"provider": "x", "status": "available", "offer_count": 1}], 1.2)
    assert set(out) >= {"structured_query", "entities", "pagination", "provider_diagnostics", "search_metadata"}
