import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.main import SessionLocal, Tenant, User
from app.operations import Offer, Supplier


def _seed_public_tenant() -> int:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == "karenseir-public"))
        if tenant is None:
            tenant = Tenant(slug="karenseir-public", name="کارن‌سیر — کاتالوگ عمومی", primary_color="#0B6E4F")
            db.add(tenant); db.flush()
        identity = db.scalar(select(User).where(User.tenant_id == tenant.id, User.role == "public_search_identity"))
        if identity is None:
            db.add(User(tenant_id=tenant.id, email="system+public-search@karenseir.internal", name="KarenSeir Public Search", role="public_search_identity"))
        db.commit()
        return tenant.id


def _public_offer(tenant_id: int, *, title: str, entity_id: str) -> None:
    with SessionLocal() as db:
        supplier = Supplier(tenant_id=tenant_id, supplier_type="multi_service", display_name=f"public-{uuid.uuid4()}", status="active")
        db.add(supplier); db.flush()
        attrs = {"entity_id": entity_id, "city": "شیراز", "review_score": 8.5, "observed_at": datetime.now(timezone.utc).isoformat(), "freshness_ttl_seconds": 3600}
        row = Offer(tenant_id=tenant_id, supplier_id=supplier.id, service_type="hotel", title=title, amount=1_000_000, available_units=3, provider_key="manual_supplier", fulfillment_mode="manual_supplier", attributes_json=json.dumps(attrs), policy_json=json.dumps({"verified": True, "cancellation": {"refundable": True}}), valid_until=datetime.now(timezone.utc) + timedelta(hours=2))
        db.add(row); db.commit()


def test_public_search_fails_closed_then_returns_only_public_offers_with_no_price(client):
    # Before the public tenant/identity exists, anonymous discovery must fail closed —
    # never silently fall back to a corporate tenant.
    unseeded = client.post("/search/v2/public", json={"verticals": ["hotel"], "destination": "شیراز"})
    assert unseeded.status_code == 503

    public_tenant_id = _seed_public_tenant()
    _public_offer(public_tenant_id, title="هتل عمومی نمونه", entity_id="public-hotel-1")

    response = client.post("/search/v2/public", json={"verticals": ["hotel"], "destination": "شیراز"})
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_data_included"] is False

    titles = [entity["title"] for entity in body["entities"]]
    assert "هتل عمومی نمونه" in titles
    # never the private aftab-bank fixture hotel used by other tests in this suite
    assert all("زندیه" not in title for title in titles)

    for entity in body["entities"]:
        for offer in (entity["best_offer"], *entity["offers"]):
            for private_key in ("final_price", "amount", "total_amount", "taxes", "fees", "discounts"):
                assert private_key not in offer


def test_authenticated_search_v2_is_unaffected_and_still_tenant_scoped(client):
    response = client.post("/auth/dev-login", json={"email": "employee@aftab.test"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    result = client.post("/search/v2", json={"verticals": ["hotel"], "destination": "شیراز"}, headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200
    body = result.json()
    assert "tenant_data_included" not in body
    titles = [entity["title"] for entity in body["entities"]]
    assert "هتل عمومی نمونه" not in titles
