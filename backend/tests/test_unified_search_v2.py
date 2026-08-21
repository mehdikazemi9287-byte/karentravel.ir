import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.main import SessionLocal, User, _normalize_search_text
from app.operations import Offer, Supplier


def auth(token): return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def offer(*, title="هتل زندیه", service_type="hotel", amount=2_000_000, entity_id="hotel-zandiyeh", stale=False, city="شیراز"):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "supplier@aftab.test"))
        supplier = Supplier(tenant_id=user.tenant_id, supplier_type="multi_service", display_name=f"search-v2-{uuid.uuid4()}", status="active")
        db.add(supplier); db.flush()
        observed = datetime.now(timezone.utc) - (timedelta(hours=2) if stale else timedelta(seconds=2))
        attrs = {"entity_id": entity_id, "city": city, "review_score": 9.2, "quality_score": 8.8, "taxes": 100_000, "fees": 50_000, "discounts": 25_000, "observed_at": observed.isoformat(), "freshness_ttl_seconds": 60 if stale else 3600, "amenities": ["صبحانه"], "provider_reliability": 8}
        row = Offer(tenant_id=user.tenant_id, supplier_id=supplier.id, service_type=service_type, title=title, amount=amount, available_units=5, provider_key=f"provider-{uuid.uuid4().hex[:6]}", fulfillment_mode="manual_supplier", attributes_json=json.dumps(attrs), policy_json=json.dumps({"verified": True, "source": "test", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True}}), valid_until=datetime.now(timezone.utc) + timedelta(hours=2))
        db.add(row); db.commit(); return row.id


def test_normalization_alias_digits_punctuation_and_typo_autocomplete(client):
    assert _normalize_search_text("  كيش، ۱۲ نفر ") == "کیش 12 نفر"
    assert _normalize_search_text("THR") == "تهران"
    token = login(client, "employee@aftab.test")["access_token"]
    exact = client.get("/search/autocomplete", params={"q": "Tehran"}, headers=auth(token)).json()
    assert exact["normalized_query"] == "تهران" and exact["suggestions"][0]["title"] == "تهران"
    typo = client.get("/search/autocomplete", params={"q": "شیراژ"}, headers=auth(token)).json()
    assert any(item["title"] == "شیراز" and item["match_type"] == "fuzzy" for item in typo["suggestions"])


def test_public_autocomplete_is_typo_tolerant_and_excludes_tenant_offers(client):
    response = client.get("/search/autocomplete/public", params={"q": "تهرون"})
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_data_included"] is False
    assert body["suggestions"][0]["title"] == "تهران"
    assert all(item["source"] == "karenseir_geo_catalog" for item in body["suggestions"])
    tehran = client.get("/search/autocomplete/public", params={"q": "تهر"}).json()["suggestions"]
    assert {"تهران", "فرودگاه مهرآباد", "فرودگاه امام خمینی"}.issubset({item["title"] for item in tehran})


def test_unified_multi_vertical_deduplicates_offers_and_explains_ranking(client):
    first = offer(amount=2_100_000); second = offer(amount=1_900_000)
    offer(title="پرواز تهران شیراز", service_type="flight", amount=3_000_000, entity_id="flight-thr-syz")
    token = login(client, "employee@aftab.test")["access_token"]
    response = client.post("/search/v2", headers=auth(token), json={"verticals": ["hotel", "flight"], "query": "شیراز", "flexibility": "plus_minus_1", "sort": "lowest_price"})
    assert response.status_code == 200
    payload = response.json(); hotel = next(item for item in payload["entities"] if item["entity_id"] == "hotel-zandiyeh")
    assert hotel["provider_count"] == 2 and {item["id"] for item in hotel["offers"]} == {first, second}
    assert hotel["best_offer"]["final_price"] == 2_025_000
    assert hotel["best_offer"]["ranking_explanation"] and payload["availability_recheck_required_before_checkout"] is True


def test_stale_is_explicit_and_price_recheck_rejects_tampering(client):
    stale_id = offer(title="تور قدیمی", service_type="tour", stale=True, entity_id="tour-stale")
    live_id = offer(title="تور تازه", service_type="tour", amount=1_000_000, entity_id="tour-live")
    token = login(client, "employee@aftab.test")["access_token"]
    hidden = client.post("/search/v2", headers=auth(token), json={"verticals": ["tour"], "query": "تور"}).json()
    assert all(item["entity_id"] != "tour-stale" for item in hidden["entities"])
    visible = client.post("/search/v2", headers=auth(token), json={"verticals": ["tour"], "query": "تور", "include_stale": True}).json()
    stale = next(item for item in visible["entities"] if item["entity_id"] == "tour-stale")["best_offer"]
    assert stale["freshness_state"] == "STALE" and stale["availability_state"] == "REQUIRES_RECHECK"
    changed = client.post(f"/offers/{live_id}/price-check", headers=auth(token), json={"units": 1, "command_id": "price-change-001", "expected_final_price": 1})
    assert changed.status_code == 409 and changed.json()["detail"]["code"] == "PRICE_CHANGED"


def test_saved_search_idempotency_and_cross_tenant_ownership(client):
    own = login(client, "employee@aftab.test")["access_token"]; other = login(client, "employee@faraz.test")["access_token"]
    body = {"title": "شیراز آخر هفته", "query": {"verticals": ["hotel"], "destination": "شیراز"}, "command_id": "saved-search-001", "alert_type": "price"}
    first = client.post("/search/saved", headers=auth(own), json=body)
    second = client.post("/search/saved", headers=auth(own), json=body)
    assert first.status_code == 201 and first.json()["id"] == second.json()["id"]
    assert first.json()["alert_status"] == "external_blocked" and first.json()["external_delivery"] is False
    assert client.get("/search/saved", headers=auth(other)).json() == []
    assert client.delete(f"/search/saved/{first.json()['id']}", headers=auth(other)).status_code == 404


def test_natural_language_foundation_budget_and_zero_result_recovery(client):
    offer(title="هتل چهار ستاره شیراز", amount=2_000_000)
    token = login(client, "employee@aftab.test")["access_token"]
    parsed = client.post("/search/v2", headers=auth(token), json={"verticals": ["hotel", "flight"], "query": "شیراز 3 شب برای 2 نفر هتل 4 ستاره و پرواز صبح"})
    assert parsed.status_code == 200
    intent = parsed.json()["structured_query"]
    assert intent["destination"] == "شیراز" and intent["nights"] == 3 and intent["travellers"] == 2 and intent["star_rating"] == 4 and intent["departure_window"] == "morning"
    zero = client.post("/search/v2", headers=auth(token), json={"verticals": ["train"], "query": "مقصد بدون موجودی"}).json()
    assert zero["entities"] == [] and zero["zero_result_recovery"] and all(not item["fabricated_price"] for item in zero["zero_result_recovery"])
    budget = client.post("/search/budget-trips", headers=auth(token), json={"origin": "تهران", "destination": "شیراز", "travellers": 2, "budget": 10_000_000, "interests": ["تاریخی"]})
    assert budget.status_code == 200 and budget.json()["categories"]["ai_recommended"] is None
