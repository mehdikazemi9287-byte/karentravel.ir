"""Phase 3 orchestration tests: provider registry, orchestrator, dedup,
ranking determinism, tenant cache isolation, correlation ID, diagnostics."""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SEARCH_INTERNAL_TOKEN", "test-token")

import pytest
from fastapi.testclient import TestClient

from app import dedup, providers, registry
from app.cache import _Redis
from app.cache_keys import search_cache_key
from app.main import app
from app.ranking import RANKING_VERSION

client = TestClient(app)


def _offer(service_type, amount, title="آفر تست", city="تهران", provider="manual_supplier", entity_id=None):
    now = datetime.now(timezone.utc)
    row = {
        "id": f"o-{title}-{amount}-{provider}", "service_type": service_type, "title": title, "amount": amount,
        "currency": "IRR", "available_units": 5, "provider_key": provider, "fulfillment_mode": "manual_supplier",
        "attributes": {"city": city, "observed_at": now.isoformat(), "review_score": 8.5, "taxes": 0, "fees": 0, "discounts": 0},
        "policy": {"verified": True, "cancellation": {"refundable": True}},
        "valid_until": (now + timedelta(hours=2)).isoformat(),
        "created_at": now.isoformat(), "updated_at": now.isoformat(),
    }
    if entity_id:
        row["attributes"]["entity_id"] = entity_id
    return row


@pytest.fixture(autouse=True)
def _clear_cache():
    from app.cache import CACHE
    if hasattr(CACHE, "_d"):
        CACHE._d.clear()


# ---- provider registry ----

def test_registry_for_vertical_includes_internal_pool_and_matching_externals():
    eligible = registry.REGISTRY.for_vertical("flight")
    keys = {p.key for p in eligible}
    assert "karenseir_supplier_pool" in keys
    assert "flight_carrier" in keys
    assert "hotel_bedbank" not in keys       # hotel provider not eligible for a flight search


def test_registry_capability_matrix_is_truthful():
    matrix = registry.REGISTRY.capability_matrix()
    by_key = {m["provider"]: m for m in matrix}
    assert by_key["karenseir_supplier_pool"]["connected"] is True
    assert by_key["flight_carrier"]["connected"] is False
    assert by_key["flight_carrier"]["capabilities"]["search"] is False


def test_provider_supports_method_matches_verticals_tuple():
    assert providers.DisabledFlightProvider.supports("flight") is True
    assert providers.DisabledFlightProvider.supports("hotel") is False
    assert providers._POOL.supports("anything") is True   # empty verticals tuple == any


# ---- deduplication ----

def test_dedup_same_provider_duplicate_offers_merge_into_one_entity():
    groups = dedup.group_by_entity([
        {"entity_id": "e1", "title": "A", "service_type": "flight", "provider": "p1", "final_price": 100, "ranking_score": 1},
        {"entity_id": "e1", "title": "A", "service_type": "flight", "provider": "p1", "final_price": 100, "ranking_score": 1},
    ])
    assert len(groups) == 1 and len(groups["e1"]["offers"]) == 2


def test_dedup_same_entity_two_providers_stays_one_entity_two_offers():
    groups = dedup.group_by_entity([
        {"entity_id": "e1", "title": "A", "service_type": "hotel", "provider": "p1", "final_price": 100, "ranking_score": 1},
        {"entity_id": "e1", "title": "A", "service_type": "hotel", "provider": "p2", "final_price": 90, "ranking_score": 2},
    ])
    assert len(groups) == 1
    assert {o["provider"] for o in groups["e1"]["offers"]} == {"p1", "p2"}


def test_dedup_similar_but_not_identical_stays_separate():
    groups = dedup.group_by_entity([
        {"entity_id": "e1", "title": "Hotel A", "service_type": "hotel", "provider": "p1", "final_price": 100, "ranking_score": 1},
        {"entity_id": "e2", "title": "Hotel A Annex", "service_type": "hotel", "provider": "p1", "final_price": 100, "ranking_score": 1},
    ])
    assert len(groups) == 2   # conservative: different entity_id, never force-merged


def test_dedup_output_is_deterministic_across_runs():
    offers = [
        {"entity_id": "e1", "title": "A", "service_type": "hotel", "provider": "p1", "final_price": 100, "ranking_score": 1},
        {"entity_id": "e2", "title": "B", "service_type": "hotel", "provider": "p2", "final_price": 50, "ranking_score": 3},
    ]
    g1 = dedup.group_by_entity(offers)
    g2 = dedup.group_by_entity(offers)
    assert list(g1.keys()) == list(g2.keys())


# ---- orchestrator / end-to-end pipeline ----

@pytest.fixture
def _stub_pool(monkeypatch):
    def fake_fetch(vertical, req):
        if vertical == "flight":
            return [_offer("flight", 3_000_000, "پرواز تهران کیش")]
        if vertical == "cruise":
            raise RuntimeError("provider blew up")
        return []
    monkeypatch.setattr(providers._POOL, "fetch", fake_fetch)
    monkeypatch.setattr(providers._POOL, "status", lambda: {"provider": "karenseir_supplier_pool", "status": "available", "offer_count": 0})


def test_ranking_version_present_and_stable_ordering(_stub_pool):
    from app.cache import CACHE
    body = {"verticals": ["flight"], "destination": "کیش", "public": True}
    r1 = client.post("/v1/search", json=body).json()
    assert r1["search_metadata"]["ranking_version"] == RANKING_VERSION
    if hasattr(CACHE, "_d"):
        CACHE._d.clear()   # force a second real (non-cached) run to prove determinism, not a cache echo
    r2 = client.post("/v1/search", json=body).json()
    assert [e["entity_id"] for e in r1["entities"]] == [e["entity_id"] for e in r2["entities"]]
    assert [e["ranking_score"] for e in r1["entities"]] == [e["ranking_score"] for e in r2["entities"]]


def test_provider_latency_recorded_in_metadata(_stub_pool):
    r = client.post("/v1/search", json={"verticals": ["flight"], "public": True}).json()
    assert "karenseir_supplier_pool" in r["search_metadata"]["provider_latency_ms"]
    assert r["search_metadata"]["provider_latency_ms"]["karenseir_supplier_pool"] >= 0


def test_provider_timeout_is_isolated_not_fatal(monkeypatch):
    import time as _time
    def slow_fetch(vertical, req):
        _time.sleep(0.3)     # exceeds the 0.05s provider timeout below, short enough to keep the suite fast
        return []
    monkeypatch.setattr(providers._POOL, "fetch", slow_fetch)
    monkeypatch.setattr(providers._POOL, "timeout_seconds", 0.05)
    r = client.post("/v1/search", json={"verticals": ["flight"], "public": True})
    # every eligible connected provider timed out -> fail closed, not a fake empty 200
    assert r.status_code == 503
    assert r.json()["code"] == "PROVIDER_UNAVAILABLE"


def test_partial_failure_plus_success_returns_200_with_partial_metadata(_stub_pool):
    r = client.post("/v1/search", json={"verticals": ["flight", "cruise"], "public": False}).json()
    assert r["pagination"]["total"] == 1
    assert r["search_metadata"]["partial_results"] is True
    assert r["search_metadata"]["providers_succeeded"] == 1
    assert r["search_metadata"]["providers_failed"] == 1


# ---- correlation ID ----

def test_correlation_id_echoed_from_request_header(_stub_pool):
    r = client.post("/v1/search", json={"verticals": ["flight"], "public": True},
                     headers={"X-Correlation-ID": "corr-fixed-123"}).json()
    assert r["search_metadata"]["correlation_id"] == "corr-fixed-123"


def test_correlation_id_generated_when_absent(_stub_pool):
    r = client.post("/v1/search", json={"verticals": ["flight"], "public": True}).json()
    assert r["search_metadata"]["correlation_id"]  # non-empty, service-generated


# ---- cache isolation ----

def test_tenant_cache_keys_never_collide():
    base = {"verticals": ["hotel"], "public": False, "page": 1, "page_size": 20, "sort": "recommended",
            "flexibility": "exact", "include_stale": False, "filters": {}, "query": None, "origin": None,
            "destination": None, "travellers": 1}
    key_a = search_cache_key({**base, "tenant_ref": "aftab-bank"})
    key_b = search_cache_key({**base, "tenant_ref": "faraz-industries"})
    key_pub = search_cache_key({**base, "public": True, "tenant_ref": None})
    assert len({key_a, key_b, key_pub}) == 3   # all three distinct -- no collision possible


# ---- Redis-down operation (unit level; the module-level CACHE singleton in
# this test env is already in-memory, so this exercises _Redis directly) ----

def test_redis_backend_swallows_errors_and_degrades_gracefully():
    class _BoomRedis:
        def get(self, *a, **k): raise ConnectionError("down")
        def set(self, *a, **k): raise ConnectionError("down")
        def setex(self, *a, **k): raise ConnectionError("down")
        def ping(self): raise ConnectionError("down")

    r = _Redis.__new__(_Redis)   # bypass __init__ (no real redis connection needed)
    r._r = _BoomRedis()
    r.backend = "redis"
    assert r.get("k") is None            # never raises
    r.set("k", {"a": 1}, 10)             # never raises
    assert r.ping() is False             # never raises


# ---- diagnostics endpoint ----

def test_diagnostics_endpoint_has_no_secrets():
    r = client.get("/v1/diagnostics").json()
    assert r["ranking_version"] == RANKING_VERSION
    assert "capability_matrix" in r and "cache" in r and "telemetry" in r
    blob = str(r)
    assert "test-token" not in blob and "SEARCH_INTERNAL_TOKEN" not in blob


def test_diagnostics_provider_counts_match_registry():
    r = client.get("/v1/diagnostics").json()
    assert r["providers_enabled"] == len(registry.REGISTRY.all())
    assert r["providers_connected"] == 1   # only the internal pool is connected today


# ---- malformed provider row classification (Phase 3 explicit guard) ----

def test_malformed_row_missing_service_type_is_skipped(monkeypatch):
    def bad(vertical, req):
        return [{"id": "x", "amount": 100}]   # missing service_type
    monkeypatch.setattr(providers._POOL, "fetch", bad)
    r = client.post("/v1/search", json={"verticals": ["flight"], "public": True})
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 0
