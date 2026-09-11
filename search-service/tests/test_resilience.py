"""Phase 2 resilience + telemetry-boundary tests."""
import pytest
from fastapi.testclient import TestClient

from app import providers, telemetry_store
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_cache():
    from app.cache import CACHE
    if hasattr(CACHE, "_d"):
        CACHE._d.clear()


def test_total_provider_failure_is_explicit_not_fake_zero_result(monkeypatch):
    def boom(vertical, req):
        raise RuntimeError("network down")
    monkeypatch.setattr(providers._POOL, "fetch", boom)
    r = client.post("/v1/search", json={"verticals": ["flight"], "public": True})
    assert r.status_code == 503
    assert r.json()["code"] == "PROVIDER_UNAVAILABLE"


def test_malformed_offer_row_is_skipped_not_crashed(monkeypatch):
    def bad(vertical, req):
        return [{"id": "x"}]  # missing required fields entirely
    monkeypatch.setattr(providers._POOL, "fetch", bad)
    r = client.post("/v1/search", json={"verticals": ["flight"], "public": True})
    assert r.status_code == 200  # degrades gracefully, no 500


def test_telemetry_disabled_backend_never_raises():
    telemetry_store._DISABLED = False
    telemetry_store._POOL = None
    from app import config
    config.TELEMETRY_DB_URL = ""
    telemetry_store.record({"correlation_id": "c", "verticals": ["flight"], "public": True,
                            "tenant_ref": None, "result_count": 0, "partial_results": False,
                            "providers_requested": 1, "providers_failed": 0, "elapsed_ms": 1.0,
                            "cache": "miss", "failure_code": None})
    assert telemetry_store.health()["backend"] == "disabled"


def test_provider_capabilities_declared_truthfully():
    for p in providers.EXTERNAL_PROVIDERS:
        s = p.status()
        assert s["capabilities"]["search"] is False
        assert s["status"] == "not_connected"


def test_authenticated_context_not_public_keeps_full_fields(monkeypatch):
    from datetime import datetime, timedelta, timezone

    def rows(vertical, req):
        assert req.public is False and req.tenant_ref == "aftab-bank"
        return [{
            "id": "o1", "service_type": "hotel", "title": "هتل تست", "amount": 4_000_000, "currency": "IRR",
            "available_units": 3, "provider_key": "manual_supplier", "fulfillment_mode": "manual_supplier",
            "attributes": {"city": "تهران", "observed_at": datetime.now(timezone.utc).isoformat(), "taxes": 0, "fees": 0, "discounts": 0},
            "policy": {"verified": True}, "valid_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }]
    monkeypatch.setattr(providers._POOL, "fetch", rows)
    r = client.post("/v1/search", json={"verticals": ["hotel"], "public": False, "tenant_ref": "aftab-bank"})
    assert r.status_code == 200
    ent = r.json()["entities"][0]
    assert "ranking_breakdown" in ent["best_offer"]   # full detail present, not stripped like public
    assert r.json()["tenant_data_included"] is True
