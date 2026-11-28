"""/search/v3 → karenseir-search → /internal/search/offer-pool must price like /search/offers: commerce markup is applied,
flights above the CAO cap are not listed (owner decision, PR #119), and the net price never leaves the monolith.

TEST FIXTURES ONLY: synthetic offers, rules and caps; nothing calls a real provider. Rows are disabled, not deleted.
"""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import main
from app.main import SessionLocal, Tenant, User
from app.operations import Offer, Supplier

TOKEN = "test-internal-token-not-real"
DAY = (date.today() + timedelta(days=12)).isoformat()


@pytest.fixture(autouse=True)
def internal_token(monkeypatch):
    monkeypatch.setattr(main, "_SEARCH_INTERNAL_TOKEN", TOKEN)


def _tenant():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "backoffice@aftab.test"))
        return user.tenant_id, db.get(Tenant, user.tenant_id).slug, user.id


def _flight(tenant_id, net, origin, dest):
    with SessionLocal() as db:
        supplier = Supplier(tenant_id=tenant_id, supplier_type="airline", display_name=f"v3-{uuid.uuid4()}", status="active")
        db.add(supplier); db.flush()
        attrs = {"origin_code": origin, "destination_code": dest, "flight_date": DAY, "airline_code": "ZV", "flight_type": "system",
                 "observed_at": datetime.now(timezone.utc).isoformat(), "freshness_ttl_seconds": 3600}
        row = Offer(tenant_id=tenant_id, supplier_id=supplier.id, service_type="flight", title=f"پرواز {origin}-{dest}", amount=net, available_units=4,
                    provider_key="manual_supplier", fulfillment_mode="manual_supplier", attributes_json=json.dumps(attrs), policy_json="{}",
                    valid_until=datetime.now(timezone.utc) + timedelta(hours=2))
        db.add(row); db.commit()
        return supplier.id, row.id


def _add(row):
    with SessionLocal() as db:
        db.add(row); db.commit()
        return row.id


def _disable(model, row_id, value="inactive"):
    with SessionLocal() as db:
        db.get(model, row_id).status = value
        db.commit()


def _pool(client, slug, **extra):
    body = {"service_type": "flight", "public": False, "tenant_ref": slug, **extra}
    response = client.post("/internal/search/offer-pool", json=body, headers={"X-Internal-Token": TOKEN})
    assert response.status_code == 200, response.text
    return response.json()["offers"]


def test_pool_is_sell_side_and_hides_flights_above_the_cap(client):
    from app.charter_blocks import PriceCap
    from app.commerce import MarkupRule
    tenant_id, slug, uid = _tenant()
    supplier_id, offer_id = _flight(tenant_id, 20_000_000, "AZD", "BND")
    rule = _add(MarkupRule(tenant_id=tenant_id, title="test v3 10%", service_type="flight", supplier_id=supplier_id, calc="percent", adult=1000))
    try:
        mine = [o for o in _pool(client, slug) if o["id"] == offer_id]
        assert [o["amount"] for o in mine] == [22_000_000]
        assert "20000000" not in json.dumps(mine)
        cap = _add(PriceCap(tenant_id=tenant_id, origin="AZD", destination="BND", valid_from=date.today(), valid_to=date.today() + timedelta(days=30),
                            cap_unit_irr=21_000_000, legal_reference="TEST-CAP-V3", created_by_user_id=uid))
        try:
            assert offer_id not in {o["id"] for o in _pool(client, slug)}            # sell 22M > cap 21M: not listed
        finally:
            _disable(PriceCap, cap)
        assert offer_id in {o["id"] for o in _pool(client, slug)}
    finally:
        _disable(MarkupRule, rule)
    assert [o["amount"] for o in _pool(client, slug) if o["id"] == offer_id] == [20_000_000]   # no rule: sell equals net


def test_price_group_is_validated_against_the_tenant(client):
    from app.commerce import CustomerGroup, MarkupRule
    tenant_id, slug, _ = _tenant()
    supplier_id, offer_id = _flight(tenant_id, 10_000_000, "AWZ", "ABD")
    group = _add(CustomerGroup(tenant_id=tenant_id, code=f"v3-{uuid.uuid4().hex[:8]}", name="گروه آزمایشی v3"))
    rule = _add(MarkupRule(tenant_id=tenant_id, title="test v3 group 5%", service_type="flight", supplier_id=supplier_id, group_id=group, calc="percent", adult=500))
    try:
        price = lambda **kw: [o["amount"] for o in _pool(client, slug, **kw) if o["id"] == offer_id]
        assert price(price_group=group) == [10_500_000]
        assert price() == [10_000_000]                                   # group rule does not leak to the tenant default
        assert price(price_group="not-a-group-of-this-tenant") == [10_000_000]
    finally:
        _disable(MarkupRule, rule)
        _disable(CustomerGroup, group)


def test_v3_gateway_sends_the_resolved_price_group_only(client, monkeypatch):
    from app.commerce import user_group_id
    seen = {}

    async def fake_call(data, *, public, tenant_ref, price_group=None):
        seen.update(public=public, tenant_ref=tenant_ref, price_group=price_group)
        return {"entities": []}

    monkeypatch.setattr(main, "_search_service_call", fake_call)
    token = client.post("/auth/dev-login", json={"email": "employee@aftab.test"}).json()["access_token"]
    response = client.post("/search/v3", json={"verticals": ["flight"]}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        expected = user_group_id(db, user.tenant_id, user.id)
        slug = db.get(Tenant, user.tenant_id).slug
    assert seen == {"public": False, "tenant_ref": slug, "price_group": expected}
