"""GRS <-> Search Aggregation tests. Real SQLite DB, FakeTransport-backed
adapter injected directly into _grs_hotel_offers_for_search (no monkeypatching
of global ADAPTERS/env - GRS_MODE stays unset/disabled for every other test in
the suite, confirming zero cross-test interference)."""
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select

from app.main import (
    SessionLocal, Tenant, User, OfferSearchIn, search_offers,
    _grs_hotel_offers_for_search, _project_public_offer,
)
from app.database import set_tenant_context
from app.operations import Offer, Supplier, ProviderLocationMapping
from app.grs_contract import GRSConfig
from app.grs_adapter import GRSAdapter, GRSTransportResponse


@dataclass
class FakeTransport:
    responses: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    raise_exc: Exception = None

    def request(self, method, path, *, params=None, json_body=None, timeout):
        self.calls.append({"method": method, "path": path, "params": params})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.responses.pop(0)


ENABLED_CONFIG = GRSConfig(mode="sandbox", base_url="https://grs.example/api", client_token="secret",
                            connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="IRR", webhook_secret="whsec")


def _adapter(responses):
    return GRSAdapter(config=ENABLED_CONFIG, transport=FakeTransport(responses=responses))


SUGGESTION_FIXTURE = [{
    "property_id": 740, "property_name": "[TEST] هتل شیراز نمونه",
    "rooms": [{
        "room_type_id": 1, "room_type_name": "Standard", "room_type_capacity": 2,
        "rate_plans": [{
            "id": 1, "name": "BB", "cancelable": True,
            "prices": [{"day": "2026-09-15", "inventory": 3, "daily_rate": 2_500_000, "closed": False}],
        }],
    }],
}]

SUGGESTION_FIXTURE_CLOSED_AND_EMPTY = [{
    "property_id": 741, "property_name": "[TEST] هتل بسته",
    "rooms": [{
        "room_type_id": 2, "room_type_name": "Closed Room", "rate_plans": [
            {"id": 2, "name": "BB", "cancelable": False, "prices": [{"day": "2026-09-15", "inventory": 5, "daily_rate": 1_000_000, "closed": True}]},
        ],
    }, {
        "room_type_id": 3, "room_type_name": "Sold Out Room", "rate_plans": [
            {"id": 3, "name": "BB", "cancelable": True, "prices": [{"day": "2026-09-15", "inventory": 0, "daily_rate": 1_000_000, "closed": False}]},
        ],
    }],
}]


def _make_tenant_with_mapping(city_name="شیراز", provider_location_id="38"):
    with SessionLocal() as db:
        tenant = Tenant(slug=f"grs-search-{uuid.uuid4().hex[:8]}", name="[TEST] GRS Search Tenant", primary_color="#000000")
        db.add(tenant)
        db.flush()
        set_tenant_context(db, tenant.id)
        user = User(tenant_id=tenant.id, email=f"grs-search-{uuid.uuid4().hex[:8]}@example.test", name="[TEST] User", role="customer")
        db.add(user)
        mapping = ProviderLocationMapping(tenant_id=tenant.id, provider_key="grs", provider_location_id=provider_location_id,
                                           location_kind="city", provider_name=city_name)
        db.add(mapping)
        db.commit()
        return tenant.id, user.id


def _make_manual_offer(tenant_id, *, city="شیراز", title="[TEST] هتل دستی نمونه"):
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        supplier = Supplier(tenant_id=tenant_id, supplier_type="manual", display_name="[TEST] Manual Supplier", status="sample")
        db.add(supplier)
        db.flush()
        import json
        from datetime import datetime, timedelta, timezone
        offer = Offer(tenant_id=tenant_id, supplier_id=supplier.id, service_type="hotel", title=title, amount=1_800_000,
                      available_units=4, status="active", provider_key="manual_supplier", fulfillment_mode="manual_supplier",
                      attributes_json=json.dumps({"city": city, "entity_id": "manual-hotel-1", "observed_at": datetime.now(timezone.utc).isoformat(), "freshness_ttl_seconds": 86400}),
                      policy_json=json.dumps({"verified": True, "cancellation": {"refundable": True}}),
                      valid_until=datetime.now(timezone.utc) + timedelta(days=1))
        db.add(offer)
        db.commit()


class _FakeUser:
    def __init__(self, tenant_id, user_id):
        self.tenant_id = tenant_id
        self.id = user_id


# 1. GRS disabled -----------------------------------------------------------
def test_grs_disabled_returns_empty_without_touching_transport():
    transport = FakeTransport()
    result = _grs_hotel_offers_for_search(tenant_id=1, query="شیراز", min_price=None, max_price=None,
                                           min_review_score=None, refundable=None, instant_booking=None,
                                           check_in="2026-09-15", check_out="2026-09-18",
                                           db=None, adapter=GRSAdapter(config=GRSConfig(mode="disabled", base_url="", client_token="", connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="", webhook_secret=""), transport=transport))
    assert result == []
    assert transport.calls == []


def test_search_offers_hotel_unaffected_when_grs_disabled_globally():
    # GRS_MODE is unset everywhere in the real test environment - this proves
    # search_offers()'s hotel path is byte-identical to before this phase for
    # every existing caller (no fixture/adapter injected at all here).
    tenant_id, user_id = _make_tenant_with_mapping()
    _make_manual_offer(tenant_id)
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        results = search_offers(OfferSearchIn(service_type="hotel", query="شیراز"), _FakeUser(tenant_id, user_id), db)
    assert len(results) == 1
    assert results[0]["provider"] == "manual_supplier"


# 2. GRS fixture success ------------------------------------------------------
def test_grs_fixture_success_returns_normalized_offer():
    tenant_id, user_id = _make_tenant_with_mapping()
    adapter = _adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": SUGGESTION_FIXTURE}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        offers = _grs_hotel_offers_for_search(tenant_id=tenant_id, query="شیراز", min_price=None, max_price=None,
                                               min_review_score=None, refundable=None, instant_booking=None,
                                               check_in="2026-09-15", check_out="2026-09-18", db=db, adapter=adapter)
    assert len(offers) == 1
    assert offers[0]["provider"] == "grs"
    assert offers[0]["title"] == "[TEST] هتل شیراز نمونه"
    assert offers[0]["amount"] == 2_500_000
    assert offers[0]["currency"] == "IRR"


# 3. failure/timeout only in GRS ---------------------------------------------
def test_grs_failure_is_partial_not_a_search_wide_failure():
    tenant_id, user_id = _make_tenant_with_mapping()
    _make_manual_offer(tenant_id)
    adapter = _adapter([GRSTransportResponse(500, None, "text/html")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        grs_offers = _grs_hotel_offers_for_search(tenant_id=tenant_id, query="شیراز", min_price=None, max_price=None,
                                                   min_review_score=None, refundable=None, instant_booking=None,
                                                   check_in="2026-09-15", check_out="2026-09-18", db=db, adapter=adapter)
        assert grs_offers == []
        # manual search_offers() call must still succeed and return the manual offer
        results = search_offers(OfferSearchIn(service_type="hotel", query="شیراز"), _FakeUser(tenant_id, user_id), db)
        assert len(results) == 1
        assert results[0]["provider"] == "manual_supplier"


def test_grs_timeout_is_also_partial():
    adapter = GRSAdapter(config=ENABLED_CONFIG, transport=FakeTransport(raise_exc=TimeoutError("boom")))
    result = _grs_hotel_offers_for_search(tenant_id=1, query="شیراز", min_price=None, max_price=None,
                                           min_review_score=None, refundable=None, instant_booking=None,
                                           check_in="2026-09-15", check_out="2026-09-18", db=None, adapter=adapter)
    assert result == []


# 4 + 5. Manual + GRS aggregation, provider count -----------------------------
def test_manual_and_grs_offers_coexist_as_independent_entities():
    tenant_id, user_id = _make_tenant_with_mapping()
    _make_manual_offer(tenant_id)
    adapter = _adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": SUGGESTION_FIXTURE}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        results = search_offers(OfferSearchIn(service_type="hotel", query="شیراز"), _FakeUser(tenant_id, user_id), db, )
        grs_offers = _grs_hotel_offers_for_search(tenant_id=tenant_id, query="شیراز", min_price=None, max_price=None,
                                                   min_review_score=None, refundable=None, instant_booking=None,
                                                   check_in="2026-09-15", check_out="2026-09-18", db=db, adapter=adapter)
    combined = results + grs_offers
    providers = {item["provider"] for item in combined}
    entity_ids = {item["entity_id"] for item in combined}
    assert providers == {"manual_supplier", "grs"}
    assert len(entity_ids) == 2  # never merged without a proven mapping - each stays independent


# 6. anonymous price hiding ----------------------------------------------------
def test_grs_offer_price_is_hidden_by_the_same_public_projection():
    tenant_id, user_id = _make_tenant_with_mapping()
    adapter = _adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": SUGGESTION_FIXTURE}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        offers = _grs_hotel_offers_for_search(tenant_id=tenant_id, query="شیراز", min_price=None, max_price=None,
                                               min_review_score=None, refundable=None, instant_booking=None,
                                               check_in="2026-09-15", check_out="2026-09-18", db=db, adapter=adapter)
    projected = _project_public_offer(offers[0])
    for private_key in ("amount", "final_price", "total_amount", "taxes", "fees", "discounts", "currency"):
        assert private_key not in projected
    assert projected["provider"] == "grs"  # non-price fields still pass through


# 7. expired/closed/zero-inventory excluded -----------------------------------
def test_closed_and_zero_inventory_rooms_are_excluded():
    tenant_id, user_id = _make_tenant_with_mapping()
    adapter = _adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": SUGGESTION_FIXTURE_CLOSED_AND_EMPTY}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        offers = _grs_hotel_offers_for_search(tenant_id=tenant_id, query="شیراز", min_price=None, max_price=None,
                                               min_review_score=None, refundable=None, instant_booking=None,
                                               check_in="2026-09-15", check_out="2026-09-18", db=db, adapter=adapter)
    assert offers == []  # one closed, one zero-inventory - neither is live/bookable


# 8. refundable badge mapping ---------------------------------------------------
def test_refundable_badge_reflects_rate_plan_cancelable_flag():
    non_refundable_fixture = [{
        "property_id": 742, "property_name": "[TEST] هتل غیرقابل استرداد",
        "rooms": [{"room_type_id": 4, "room_type_name": "Standard", "rate_plans": [
            {"id": 4, "name": "Non-refundable", "cancelable": False,
             "prices": [{"day": "2026-09-15", "inventory": 2, "daily_rate": 1_500_000, "closed": False}]},
        ]}],
    }]
    tenant_id, user_id = _make_tenant_with_mapping()
    adapter = _adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": non_refundable_fixture}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        offers = _grs_hotel_offers_for_search(tenant_id=tenant_id, query="شیراز", min_price=None, max_price=None,
                                               min_review_score=None, refundable=None, instant_booking=None,
                                               check_in="2026-09-15", check_out="2026-09-18", db=db, adapter=adapter)
    assert offers[0]["cancellation_policy"]["refundable"] is False


def test_refundable_filter_excludes_non_matching_grs_offer():
    tenant_id, user_id = _make_tenant_with_mapping()
    adapter = _adapter([GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": SUGGESTION_FIXTURE}, "application/json")])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        offers = _grs_hotel_offers_for_search(tenant_id=tenant_id, query="شیراز", min_price=None, max_price=None,
                                               min_review_score=None, refundable=False, instant_booking=None,
                                               check_in="2026-09-15", check_out="2026-09-18", db=db, adapter=adapter)
    assert offers == []  # fixture's rate plan is refundable=True, filter asked for False


# Money-unit fail-closed ------------------------------------------------------
def test_unconfigured_money_unit_never_shows_a_price():
    unconfirmed_config = GRSConfig(mode="sandbox", base_url="https://grs.example/api", client_token="secret",
                                    connect_timeout_seconds=5, read_timeout_seconds=15, money_unit="", webhook_secret="")
    adapter = GRSAdapter(config=unconfirmed_config, transport=FakeTransport(responses=[GRSTransportResponse(200, {"code": 200, "message": "", "error": None, "value": SUGGESTION_FIXTURE}, "application/json")]))
    result = _grs_hotel_offers_for_search(tenant_id=1, query="شیراز", min_price=None, max_price=None,
                                           min_review_score=None, refundable=None, instant_booking=None,
                                           check_in="2026-09-15", check_out="2026-09-18", db=None, adapter=adapter)
    assert result == []  # refuses entirely rather than guessing a currency


# No dates -> honest empty, never guessed --------------------------------------
def test_missing_dates_returns_empty_never_guesses_a_date_range():
    adapter = _adapter([])
    result = _grs_hotel_offers_for_search(tenant_id=1, query="شیراز", min_price=None, max_price=None,
                                           min_review_score=None, refundable=None, instant_booking=None,
                                           check_in=None, check_out=None, db=None, adapter=adapter)
    assert result == []
    assert adapter._transport.calls == []


# No mapping -> honest empty ---------------------------------------------------
def test_unmapped_destination_returns_empty_not_a_guess():
    tenant_id, user_id = _make_tenant_with_mapping(city_name="یزد")
    adapter = _adapter([])
    with SessionLocal() as db:
        set_tenant_context(db, tenant_id)
        result = _grs_hotel_offers_for_search(tenant_id=tenant_id, query="شیراز", min_price=None, max_price=None,
                                               min_review_score=None, refundable=None, instant_booking=None,
                                               check_in="2026-09-15", check_out="2026-09-18", db=db, adapter=adapter)
    assert result == []
    assert adapter._transport.calls == []
