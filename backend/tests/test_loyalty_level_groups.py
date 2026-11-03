"""Loyalty level -> customer group: members of a level join its group (priced by existing group sales rules); organization groups are not overridden."""
import uuid

from sqlalchemy import select

from app.commerce import CustomerGroup, CustomerGroupMember
from app.main import SessionLocal, User


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_level_group_sync(client):
    admin = _h(client, "tenant-admin@aftab.test")
    tag = uuid.uuid4().hex[:5]
    with SessionLocal() as db:
        tid = db.scalar(select(User.tenant_id).where(User.email == "tenant-admin@aftab.test"))
        silver = CustomerGroup(tenant_id=tid, code=f"lvl-silver-{tag}", name="سطح نقره‌ای")
        org = CustomerGroup(tenant_id=tid, code=f"org-{tag}", name="سازمان")
        a = User(tenant_id=tid, email=f"lg-a-{tag}@aftab.test", name="عضو یک", role="customer")
        b = User(tenant_id=tid, email=f"lg-b-{tag}@aftab.test", name="عضو سازمانی", role="customer")
        db.add_all([silver, org, a, b]); db.flush()
        db.add(CustomerGroupMember(tenant_id=tid, user_id=b.id, group_id=org.id))
        db.commit()
        a_id, b_id, silver_id, org_id = a.id, b.id, silver.id, org.id
    levels = [{"key": "bronze", "name": "برنزی", "min_points": 0}, {"key": "silver", "name": "نقره‌ای", "min_points": 500, "group_code": f"lvl-silver-{tag}"}]
    assert client.put("/loyalty/settings", json={"enabled": True, "irr_per_point": 100_000, "referral_bonus_points": 0,
                                                 "levels": [levels[0], {**levels[1], "group_code": "missing-group"}]}, headers=admin).status_code == 422
    assert client.put("/loyalty/settings", json={"enabled": True, "irr_per_point": 100_000, "referral_bonus_points": 0, "levels": levels}, headers=admin).status_code == 200
    for uid in (a_id, b_id):
        assert client.post("/loyalty/adjust", json={"user_id": uid, "points": 600, "reason": "آزمون سطح"}, headers=admin).status_code == 201
    with SessionLocal() as db:
        ga = db.scalar(select(CustomerGroupMember.group_id).where(CustomerGroupMember.user_id == a_id))
        gb = db.scalar(select(CustomerGroupMember.group_id).where(CustomerGroupMember.user_id == b_id))
    assert ga == silver_id and gb == org_id
    assert client.post("/loyalty/adjust", json={"user_id": a_id, "points": -200, "reason": "برگشت"}, headers=admin).status_code == 201
    with SessionLocal() as db:
        assert db.scalar(select(CustomerGroupMember.group_id).where(CustomerGroupMember.user_id == a_id)) is None
    client.put("/loyalty/settings", json={"enabled": False, "irr_per_point": 100_000, "referral_bonus_points": 0,
                                          "levels": [{"key": "bronze", "name": "برنزی", "min_points": 0}]}, headers=admin)
