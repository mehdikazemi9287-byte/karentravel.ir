"""Phase 4: Query Intelligence & Search Planning tests. Covers the 26
required cases plus a small golden-query regression set, all deterministic
-- zero AI/LLM dependency anywhere in this file or the code under test."""
import os
from datetime import date

os.environ.setdefault("SEARCH_INTERNAL_TOKEN", "test-token")

import pytest
from fastapi.testclient import TestClient

from app import autocomplete
from app.main import app
from app.query_intelligence import CanonicalQueryInput, plan_query
from app.query_intelligence.models import (
    CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM,
    STATUS_AMBIGUOUS, STATUS_INVALID, STATUS_UNSUPPORTED, STATUS_VALID,
)
from app.query_intelligence.normalizer import normalize_query

client = TestClient(app)
TODAY = date(2026, 9, 11)   # fixed reference date for deterministic relative-date tests


def plan(text="", **kw):
    return plan_query(CanonicalQueryInput(text=text, **kw), today=TODAY)


@pytest.fixture(autouse=True)
def _clear_cache():
    from app.cache import CACHE
    if hasattr(CACHE, "_d"):
        CACHE._d.clear()


# ---- 1. Persian character normalization ----

def test_persian_character_normalization():
    assert normalize_query("كيش") == normalize_query("کیش")   # Arabic ك/ي -> Persian ک/ی


# ---- 2. digit normalization ----

def test_digit_normalization():
    assert normalize_query("۲ نفر") == normalize_query("٢ نفر") == normalize_query("2 نفر")


# ---- 3-7. vertical intent detection ----

def test_flight_intent():
    assert plan("پرواز تهران به مشهد").vertical == "flight"

def test_hotel_intent():
    assert plan("هتل کیش").vertical == "hotel"

def test_train_intent():
    assert plan("قطار تهران شیراز").vertical == "train"

def test_bus_intent():
    assert plan("اتوبوس تهران اصفهان").vertical == "bus"

def test_car_rental_intent():
    assert plan("اجاره ماشین در مشهد").vertical == "car_rental"


# ---- 8. origin/destination extraction ----

def test_origin_destination_extraction():
    p = plan("پرواز تهران به مشهد")
    assert p.origin is not None and p.origin.title == "تهران"
    assert p.destination is not None and p.destination.title == "مشهد"
    assert p.status == STATUS_VALID


# ---- 9. one-location ambiguity ----

def test_one_location_ambiguity():
    p = plan("پرواز کیش")
    assert p.status == STATUS_AMBIGUOUS
    assert any(a.code == "single_location_no_direction" for a in p.ambiguities)


# ---- 10. tomorrow parsing ----

def test_tomorrow_parsing():
    p = plan("پرواز کیش فردا")
    # single-location route ambiguity still applies, but date must resolve regardless
    assert p.date_range.start_date == "2026-09-12"
    assert p.date_range.source == "relative"


# ---- 11. relative-date boundary (month/year rollover) ----

def test_relative_date_month_boundary():
    p = plan_query(CanonicalQueryInput(text="هتل کیش فردا"), today=date(2026, 1, 31))
    assert p.date_range.start_date == "2026-02-01"

def test_relative_date_year_boundary():
    p = plan_query(CanonicalQueryInput(text="هتل کیش فردا"), today=date(2026, 12, 31))
    assert p.date_range.start_date == "2027-01-01"

def test_day_after_tomorrow_not_confused_with_tomorrow():
    p = plan_query(CanonicalQueryInput(text="هتل کیش پس فردا"), today=date(2026, 9, 11))
    assert p.date_range.start_date == "2026-09-13"


# ---- 12. passenger extraction ----

def test_passenger_extraction():
    p = plan("پرواز تهران به مشهد برای دو نفر ۲ نفر")
    assert p.party.travellers == 2


# ---- 13. room extraction ----

def test_room_extraction():
    p = plan("هتل کیش ۲ اتاق")
    assert p.party.rooms == 2


# ---- 14. unsupported filter reporting ----

def test_unsupported_filter_reporting():
    p = plan("هتل ۵ ستاره کیش پرواز مستقیم")
    assert "star_rating_5" in p.unsupported_constraints
    # "مستقیم" only applies to flight semantically, but detection itself is
    # constraint-text-based -- direct_flight_only surfaces whenever the
    # phrase appears, matching "do not pretend unsupported filters are applied"
    assert "max_price" not in p.filters   # nothing fabricated for constraints we don't parse here


# ---- 15. explicit structured value overrides inference ----

def test_explicit_structured_value_overrides_inference():
    p = plan("پرواز تهران به مشهد", destination="کیش")
    assert p.destination.title == "کیش"   # explicit wins over "مشهد" found in the text
    assert p.origin is None or p.origin.title != "کیش"

def test_explicit_vertical_overrides_inferred_intent():
    p = plan("هتل کیش", vertical="train")
    assert p.vertical == "train"


# ---- 16. ambiguity response ----

def test_ambiguity_response_has_machine_readable_code():
    p = plan("پرواز تهران مشهد")   # two cities, no directional token
    assert p.status == STATUS_AMBIGUOUS
    assert p.ambiguities and p.ambiguities[0].code == "missing_route_direction"
    assert p.confidence == CONFIDENCE_LOW


# ---- 17. unsupported vertical ----

def test_unsupported_vertical_reserved_vocabulary():
    p = plan("رستوران ایتالیایی تهران")
    assert p.status == STATUS_UNSUPPORTED
    assert any(a.code == "unsupported_intent" for a in p.ambiguities)

def test_unsupported_vertical_explicit_not_in_allowed_set():
    p = plan("چیزی", vertical="teleportation")
    assert p.status == STATUS_UNSUPPORTED


# ---- 18. multi-intent detection ----

def test_multi_intent_detection():
    p = plan("پرواز و هتل کیش")
    assert p.multi_intent is True
    assert set(p.intent) >= {"flight", "hotel"}
    assert p.status == STATUS_UNSUPPORTED   # combined execution deferred, never routed as a fake single search


# ---- 19. planner version in metadata ----

def test_planner_version_in_plan():
    p = plan("هتل کیش")
    assert p.planner_version == "v2-deterministic"

def test_planner_version_in_endpoint_response():
    r = client.post("/v1/query/plan", json={"text": "هتل کیش"}).json()
    assert r["plan"]["planner_version"] == "v2-deterministic"


# ---- 20. cache key planner-version isolation ----

def test_cache_key_changes_with_planner_version():
    from app.cache_keys import query_plan_cache_key
    k1 = query_plan_cache_key({"a": 1}, "v1-deterministic")
    k2 = query_plan_cache_key({"a": 1}, "v2-deterministic")
    assert k1 != k2


# ---- 21. tenant cache isolation remains intact ----

def test_query_plan_cache_key_tenant_isolation():
    from app.cache_keys import query_plan_cache_key
    base = {"vertical": "hotel", "destination_id": "city-kish"}
    k_a = query_plan_cache_key({**base, "tenant_ref": "aftab-bank", "public": False}, "v1-deterministic")
    k_b = query_plan_cache_key({**base, "tenant_ref": "faraz-industries", "public": False}, "v1-deterministic")
    k_pub = query_plan_cache_key({**base, "tenant_ref": None, "public": True}, "v1-deterministic")
    assert len({k_a, k_b, k_pub}) == 3


# ---- 22. malformed natural-language input ----

def test_malformed_input_does_not_crash():
    p = plan("!!!@@@###  ...   ")
    assert p.status in (STATUS_INVALID, STATUS_AMBIGUOUS)

def test_very_long_input_is_truncated_safely():
    p = plan("هتل کیش " + ("ز" * 2000))
    assert p.status in (STATUS_VALID, STATUS_AMBIGUOUS, STATUS_UNSUPPORTED)   # never raises


# ---- 23. blank query ----

def test_blank_query_is_invalid():
    p = plan("")
    assert p.status == STATUS_INVALID
    assert any(a.code == "empty_query" for a in p.ambiguities)

def test_blank_query_with_explicit_vertical_is_not_invalid():
    p = plan("", vertical="hotel")
    assert p.status != STATUS_INVALID


# ---- 24. entity resolution through canonical source ----

def test_entity_resolution_uses_canonical_autocomplete_corpus():
    from app.query_intelligence.entities import resolve_locations
    ids = {e["id"] for e in resolve_locations("تهران")}
    assert ids == {e["id"] for e in autocomplete.ENTITIES if e["id"] == "city-tehran"}


# ---- 25. autocomplete parity remains 7/7 ----

@pytest.mark.parametrize("q,expected_titles", [
    ("ته", ["تهران", "فرودگاه مهرآباد", "فرودگاه امام خمینی"]),
    ("شیر", ["شیراز", "حافظیه"]),
    ("مشهد", ["مشهد"]),
    ("یز", ["یزد"]),
    ("kish", ["کیش"]),
    ("IKA", ["فرودگاه امام خمینی"]),
    ("تخت", ["تخت جمشید"]),
])
def test_autocomplete_parity_unaffected(q, expected_titles):
    r = client.get("/v1/autocomplete", params={"q": q}).json()
    assert [s["title"] for s in r["suggestions"]] == expected_titles


# ---- 26. deterministic parser works with zero AI dependency ----

def test_deterministic_parser_has_no_network_or_ai_calls(monkeypatch):
    import socket
    def _boom(*a, **k):
        raise AssertionError("query_intelligence must never open a network connection")
    monkeypatch.setattr(socket, "socket", _boom)
    p = plan("پرواز تهران به مشهد فردا برای دو نفر")
    assert p.status == STATUS_VALID


# ---- golden query set (Step 24) ----

GOLDEN_QUERIES = [
    ("پرواز تهران به مشهد فردا", "flight", STATUS_VALID),
    ("بلیط هواپیما تهران مشهد برای دو نفر", "flight", STATUS_AMBIGUOUS),   # no directional token -> route ambiguous
    ("هتل ۵ ستاره کیش", "hotel", STATUS_VALID),
    ("قطار تهران شیراز", "train", STATUS_AMBIGUOUS),
    ("اتوبوس تهران اصفهان", "bus", STATUS_AMBIGUOUS),
    ("اجاره خودرو در مشهد", "car_rental", STATUS_VALID),
    ("هتل کیش برای سه شب", "hotel", STATUS_VALID),
    ("پرواز کیش فردا", "flight", STATUS_AMBIGUOUS),   # single location, no direction
    ("تهران مشهد", None, STATUS_AMBIGUOUS),            # no vertical keyword at all
    ("پرواز و هتل کیش", None, STATUS_UNSUPPORTED),     # multi-intent, deferred
]

@pytest.mark.parametrize("text,expected_vertical,expected_status", GOLDEN_QUERIES)
def test_golden_query_set(text, expected_vertical, expected_status):
    p = plan(text)
    assert p.status == expected_status, f"{text!r} -> {p.status} (expected {expected_status}), ambiguities={p.ambiguities}"
    if expected_vertical is not None:
        assert p.vertical == expected_vertical

def test_golden_query_hotel_three_nights_derives_end_date():
    p = plan("هتل کیش برای سه شب فردا")
    assert p.date_range.start_date == "2026-09-12"
    assert p.date_range.end_date == "2026-09-15"


# ---- endpoint-level: /v1/query/plan and /v1/query/search ----

def test_query_plan_endpoint_never_calls_a_provider(monkeypatch):
    from app import providers
    def _boom(vertical, req):
        raise AssertionError("plan-only endpoint must never fetch from a provider")
    monkeypatch.setattr(providers._POOL, "fetch", _boom)
    r = client.post("/v1/query/plan", json={"text": "پرواز تهران به مشهد فردا"})
    assert r.status_code == 200
    assert r.json()["plan"]["status"] == STATUS_VALID


def test_query_search_endpoint_executes_valid_plan(monkeypatch):
    from app import providers
    from datetime import datetime, timedelta, timezone
    def fake_fetch(vertical, req):
        now = datetime.now(timezone.utc)
        return [{
            "id": "o1", "service_type": "hotel", "title": "هتل کیش", "amount": 4_000_000, "currency": "IRR",
            "available_units": 3, "provider_key": "manual_supplier", "fulfillment_mode": "manual_supplier",
            "attributes": {"city": "کیش", "observed_at": now.isoformat(), "taxes": 0, "fees": 0, "discounts": 0},
            "policy": {"verified": True}, "valid_until": (now + timedelta(hours=1)).isoformat(),
        }]
    monkeypatch.setattr(providers._POOL, "fetch", fake_fetch)
    r = client.post("/v1/query/search", json={"text": "هتل کیش"})
    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is True
    assert body["result"]["pagination"]["total"] == 1
    assert body["result"]["plan"]["vertical"] == "hotel"


def test_query_search_endpoint_returns_clarification_for_ambiguous_plan(monkeypatch):
    from app import providers
    def _boom(vertical, req):
        raise AssertionError("ambiguous plan must never reach a provider")
    monkeypatch.setattr(providers._POOL, "fetch", _boom)
    r = client.post("/v1/query/search", json={"text": "پرواز کیش"})
    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is False
    assert body["plan"]["status"] == STATUS_AMBIGUOUS


def test_query_search_endpoint_never_calls_provider_for_unsupported_plan(monkeypatch):
    from app import providers
    def _boom(vertical, req):
        raise AssertionError("unsupported plan must never reach a provider")
    monkeypatch.setattr(providers._POOL, "fetch", _boom)
    r = client.post("/v1/query/search", json={"text": "رستوران تهران"})
    assert r.status_code == 200
    assert r.json()["executed"] is False


def test_existing_v1_search_contract_unchanged(monkeypatch):
    """/v1/search must remain fully backward-compatible -- Phase 4 is additive."""
    from app import providers
    monkeypatch.setattr(providers._POOL, "fetch", lambda vertical, req: [])
    r = client.post("/v1/search", json={"verticals": ["hotel"], "public": True})
    assert r.status_code == 200
    assert "entities" in r.json() and "search_metadata" in r.json()
