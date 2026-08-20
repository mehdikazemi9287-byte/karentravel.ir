import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.main import SessionLocal, User
from app.operations import Offer, Supplier


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def create_offer(*, service_type="hotel", title="هتل کیان شیراز", amount=2_000_000, attributes=None, observed_at=None):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "supplier@aftab.test"))
        supplier = Supplier(tenant_id=user.tenant_id, supplier_type="multi_service", display_name=f"search-{uuid.uuid4()}", status="active")
        db.add(supplier); db.flush()
        attrs = {"city": "شیراز", "review_score": 9.1, "quality_score": 8.7, "amenities": ["صبحانه", "wifi"], "latitude": 29.5918, "longitude": 52.5837, "taxes": 100_000, "fees": 50_000, "instant_booking": True, "organization_policy_compliant": True, **(attributes or {})}
        if observed_at is not None: attrs["observed_at"] = observed_at.isoformat()
        row = Offer(tenant_id=user.tenant_id, supplier_id=supplier.id, service_type=service_type, title=title, amount=amount, available_units=4, provider_key="manual_supplier", fulfillment_mode="manual_supplier", attributes_json=json.dumps(attrs), policy_json=json.dumps({"verified": True, "source": "search-test", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True}}), valid_until=datetime.now(timezone.utc) + timedelta(hours=2))
        db.add(row); db.commit(); return row.id


def test_persian_normalization_filters_ranking_and_freshness_metadata(client):
    offer_id = create_offer()
    employee = login(client, "employee@aftab.test")
    response = client.post("/search/offers", headers=auth(employee["access_token"]), json={"service_type": "hotel", "query": "هتل كيان شيراز", "min_price": 1_000_000, "max_price": 3_000_000, "min_review_score": 9, "refundable": True, "amenities": ["صبحانه"], "instant_booking": True, "map_bounds": {"north": 30, "south": 29, "east": 53, "west": 52}, "sort": "recommended"})
    assert response.status_code == 200
    result = next(item for item in response.json() if item["id"] == offer_id)
    assert result["freshness"] == "live" and result["available"] is True
    assert result["total_amount"] == 2_150_000
    assert result["policy_verified"] is True and result["cancellation_policy"]["refundable"] is True
    assert result["last_updated_at"] and result["availability_checked_at"] and result["price_checked_at"]
    assert result["provider"] == "manual_supplier" and result["ranking_score"] > 0


def test_stale_offer_is_not_presented_as_live_and_can_only_be_inspected_explicitly(client):
    offer_id = create_offer(title="قطار قدیمی", service_type="train", observed_at=datetime.now(timezone.utc) - timedelta(hours=3), attributes={"freshness_ttl_seconds": 60})
    employee = login(client, "employee@aftab.test")
    base = {"service_type": "train", "query": "قطار قدیمی"}
    assert client.post("/search/offers", headers=auth(employee["access_token"]), json=base).json() == []
    inspected = client.post("/search/offers", headers=auth(employee["access_token"]), json={**base, "include_stale": True})
    assert inspected.status_code == 200
    result = next(item for item in inspected.json() if item["id"] == offer_id)
    assert result["freshness"] == "stale" and result["available"] is False
    assert result["inventory_status"] == "stale_unknown" and result["available_units"] is None


def test_all_ecosystem_verticals_share_contract_and_recent_search_is_user_tenant_scoped(client):
    verticals = ["flight", "hotel", "train", "tour", "package", "accommodation", "car_rental", "restaurant", "event_hall", "pool_sport", "attraction", "travel_guide", "handicraft", "tourist_transportation"]
    employee = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    faraz_before = client.get("/search/recent", headers=auth(faraz["access_token"])).json()
    for vertical in verticals:
        response = client.post("/search/offers", headers=auth(employee["access_token"]), json={"service_type": vertical, "flexible_dates": True})
        assert response.status_code == 200
    recent = client.get("/search/recent", headers=auth(employee["access_token"]))
    assert recent.status_code == 200 and len(recent.json()) == 10
    faraz_recent = client.get("/search/recent", headers=auth(faraz["access_token"]))
    assert faraz_recent.status_code == 200 and faraz_recent.json() == faraz_before


def test_autocomplete_normalizes_arabic_characters_and_never_leaks_tenant_offer(client):
    create_offer(title="هتل کیان اختصاصی")
    employee = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    own = client.get("/search/autocomplete", params={"q": "كيان"}, headers=auth(employee["access_token"])).json()
    assert own["normalized_query"] == "کیان"
    assert any(item["label"] == "هتل کیان اختصاصی" for item in own["suggestions"])
    other = client.get("/search/autocomplete", params={"q": "كيان"}, headers=auth(faraz["access_token"])).json()
    assert all(item["label"] != "هتل کیان اختصاصی" for item in other["suggestions"])


def test_invalid_price_and_map_ranges_fail_closed(client):
    employee = login(client, "employee@aftab.test")
    headers = auth(employee["access_token"])
    assert client.post("/search/offers", headers=headers, json={"service_type": "hotel", "min_price": 20, "max_price": 10}).status_code == 422
    assert client.post("/search/offers", headers=headers, json={"service_type": "hotel", "map_bounds": {"north": 20, "south": 30, "east": 50, "west": 40}}).status_code == 422
