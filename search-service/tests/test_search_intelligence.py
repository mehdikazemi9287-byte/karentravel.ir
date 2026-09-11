"""Phase 5 (Search Intelligence) tests: expanded QueryPlan contract, trip
type/round-trip inference, weekday dates, party breakdown, offer dedup,
cache-key provider_set, and API backward compatibility."""
import os
from datetime import date

os.environ.setdefault("SEARCH_INTERNAL_TOKEN", "test-token")

import pytest
from fastapi.testclient import TestClient

from app import dedup, providers
from app.main import app
from app.query_intelligence import CanonicalQueryInput, plan_query
from app.query_intelligence.models import (
    STATUS_AMBIGUOUS, STATUS_UNSUPPORTED, STATUS_VALID, TRIP_ONE_WAY, TRIP_ROUND_TRIP, TRIP_UNSPECIFIED,
)

client = TestClient(app)
TODAY = date(2026, 9, 11)   # Friday


def plan(text="", **kw):
    return plan_query(CanonicalQueryInput(text=text, **kw), today=TODAY)


@pytest.fixture(autouse=True)
def _clear_cache():
    from app.cache import CACHE
    if hasattr(CACHE, "_d"):
        CACHE._d.clear()


# ---- Persian number words / digits (already covered in Phase 4, re-asserted here for adults/children) ----

def test_children_extraction_persian_word():
    p = plan("هتل مشهد سه شب برای دو نفر یک کودک")
    assert p.party.children == 1


def test_children_extraction_digit():
    p = plan("هتل مشهد ۲ نفر ۱ کودک")
    assert p.party.children == 1


# ---- one-way / round-trip ----

def test_explicit_one_way_phrase():
    p = plan("پرواز تهران به مشهد فردا یک طرفه")
    assert p.trip_type == TRIP_ONE_WAY
    assert p.status == STATUS_VALID   # one-way phrase resolves the ambiguity -- no soft ambiguity left


def test_explicit_round_trip_phrase():
    p = plan("پرواز تهران به مشهد فردا رفت و برگشت")
    assert p.trip_type == TRIP_ROUND_TRIP


def test_weekday_pair_infers_round_trip():
    p = plan("جمعه برم شیراز یکشنبه برگردم")
    assert p.trip_type == TRIP_ROUND_TRIP
    assert p.departure_date and p.return_date
    assert p.departure_date < p.return_date


def test_single_date_route_is_soft_ambiguous_but_still_valid():
    """«تهران شیراز جمعه»-style: a single date on a route vertical records
    the return-date ambiguity for explainability but does NOT block
    execution -- a one-way search is a normal, common, executable request."""
    p = plan("پرواز تهران به مشهد فردا")
    assert p.trip_type == TRIP_UNSPECIFIED
    assert any(a.code == "return_date_unspecified" for a in p.ambiguities)
    assert p.status == STATUS_VALID   # soft ambiguity does not block


# ---- multi-city / intermediate stop ----

def test_multi_city_intermediate_stop_captured():
    # explicit vertical keyword -- the bare golden example "تهران به شیراز
    # بعد کیش" (no vertical word) is honestly ambiguous about what service
    # is wanted at all (see GOLDEN below); this test exercises the
    # intermediate-stop capture once a vertical is resolved.
    p = plan("پرواز تهران به شیراز بعد کیش")
    assert p.origin and p.origin.title == "تهران"
    assert p.destination and p.destination.title == "شیراز"
    assert len(p.intermediate_stops) == 1 and p.intermediate_stops[0].title == "کیش"
    assert "multi_leg_route_not_searchable" in p.unsupported_constraints


# ---- adults/children/rooms ----

def test_adults_children_rooms_breakdown():
    p = plan("هتل مشهد سه شب برای دو نفر یک اتاق")
    assert p.party.travellers == 2
    assert p.party.adults == 2
    assert p.party.rooms == 1


# ---- ambiguous inputs (existing categories, re-confirmed under new contract) ----

def test_ambiguous_route_direction_still_blocks():
    p = plan("پرواز تهران مشهد")
    assert p.status == STATUS_AMBIGUOUS


def test_multi_intent_still_unsupported():
    p = plan("پرواز و هتل کیش")
    assert p.status == STATUS_UNSUPPORTED


# ---- explainability: inferred/explicit/unresolved provenance ----

def test_explicit_field_provenance():
    p = plan("هتل کیش", destination="مشهد")
    assert "destination" in p.explicit_fields
    assert "destination" not in p.inferred_fields


def test_inferred_field_provenance():
    p = plan("هتل کیش")
    assert "destination" in p.inferred_fields


def test_unresolved_field_provenance_blank_query():
    p = plan("")
    assert "vertical" in p.unresolved_fields


# ---- cheap / nearby hints ----

def test_cheapest_hint_sets_sort():
    p = plan("ارزان ترین پرواز تهران کیش هفته بعد", vertical="flight")
    assert p.sort == "price_asc"


def test_nearby_hint():
    p = plan("هتل نزدیک حرم زیر پنج میلیون", vertical="hotel")
    assert p.nearby_allowed is True
    assert p.budget_max == 5_000_000


# ---- OFFER DEDUP (distinct from ENTITY DEDUP) ----

def test_offer_dedup_removes_exact_duplicate_row():
    offers = [
        {"provider": "p1", "id": "o1", "total_amount": 100, "observed_at": "t1", "entity_id": "e1"},
        {"provider": "p1", "id": "o1", "total_amount": 100, "observed_at": "t1", "entity_id": "e1"},   # exact dup
    ]
    out = dedup.dedup_offers(offers)
    assert len(out) == 1


def test_offer_dedup_keeps_different_fare_conditions():
    offers = [
        {"provider": "p1", "id": "o1", "total_amount": 100, "observed_at": "t1"},
        {"provider": "p1", "id": "o1", "total_amount": 120, "observed_at": "t1"},   # different price -- not a dup
    ]
    out = dedup.dedup_offers(offers)
    assert len(out) == 2


def test_offer_dedup_end_to_end_via_search(monkeypatch):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    row = {
        "id": "o-dup", "service_type": "hotel", "title": "هتل تست", "amount": 100, "currency": "IRR",
        "available_units": 5, "provider_key": "manual_supplier", "fulfillment_mode": "manual_supplier",
        "attributes": {"city": "تهران", "observed_at": now.isoformat(), "taxes": 0, "fees": 0, "discounts": 0},
        "policy": {"verified": True}, "valid_until": (now + timedelta(hours=1)).isoformat(),
    }
    monkeypatch.setattr(providers._POOL, "fetch", lambda vertical, req: [dict(row), dict(row)])
    r = client.post("/v1/search", json={"verticals": ["hotel"], "public": True}).json()
    assert r["pagination"]["total"] == 1
    assert len(r["entities"][0]["offers"]) == 1   # exact duplicate row collapsed
    assert r["search_metadata"]["result_counts"]["offer_dedup_removed"] == 1
    assert r["search_metadata"]["result_counts"]["raw_offer_count"] == 2


# ---- deterministic cache key with provider_set ----

def test_cache_key_provider_set_changes_key():
    from app.cache_keys import query_plan_cache_key
    k1 = query_plan_cache_key({"a": 1}, "v2-deterministic", ("p1",))
    k2 = query_plan_cache_key({"a": 1}, "v2-deterministic", ("p1", "p2"))
    assert k1 != k2


# ---- registry capability metadata ----

def test_registry_capability_matrix_has_regions_and_priority():
    from app.registry import REGISTRY
    matrix = REGISTRY.capability_matrix()
    pool = next(m for m in matrix if m["provider"] == "karenseir_supplier_pool")
    assert pool["regions"] == ["*"]
    assert pool["priority"] == 0
    assert pool["timeout_seconds"] is not None


# ---- Search API backward compatibility ----

def test_existing_v1_search_unaffected(monkeypatch):
    monkeypatch.setattr(providers._POOL, "fetch", lambda vertical, req: [])
    r = client.post("/v1/search", json={"verticals": ["hotel"], "public": True})
    assert r.status_code == 200
    assert "search_metadata" in r.json() and "result_counts" in r.json()["search_metadata"]


def test_existing_query_plan_endpoint_unaffected():
    r = client.post("/v1/query/plan", json={"text": "هتل کیش"})
    assert r.status_code == 200
    assert r.json()["plan"]["planner_version"] == "v2-deterministic"


# ---- golden examples from the master prompt ----

GOLDEN = [
    # "تهران شیراز" with no directional token (به/از/تا) is the SAME shape
    # as the already-accepted Phase 4 test plan("پرواز تهران مشهد") ->
    # missing_route_direction. Preserving that established, tested rule
    # (never invent a direction) takes precedence over this new example --
    # documented here rather than silently making the two inconsistent.
    ("پرواز تهران شیراز برای سه نفر فردا", "flight", STATUS_AMBIGUOUS),
    ("هتل مشهد سه شب برای دو نفر یک اتاق", "hotel", STATUS_VALID),
    ("جمعه برم شیراز یکشنبه برگردم", None, STATUS_AMBIGUOUS),   # no vertical keyword -> no_intent_detected
    ("ارزان ترین پرواز تهران کیش هفته بعد", "flight", STATUS_AMBIGUOUS),   # missing route direction
    ("هتل نزدیک حرم زیر پنج میلیون", "hotel", STATUS_VALID),
    ("تهران به شیراز بعد کیش", None, STATUS_AMBIGUOUS),   # no vertical keyword
]

@pytest.mark.parametrize("text,expected_vertical,expected_status", GOLDEN)
def test_golden_examples(text, expected_vertical, expected_status):
    p = plan(text)
    assert p.status == expected_status, f"{text!r} -> {p.status}, ambiguities={p.ambiguities}"
    if expected_vertical is not None:
        assert p.vertical == expected_vertical
