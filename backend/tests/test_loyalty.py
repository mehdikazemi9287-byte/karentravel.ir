"""Loyalty circle: off by default, points only for completed trips, one referral before the first trip, tenant isolation."""
import json
import uuid

from sqlalchemy import select

from app import operations as m
from app.loyalty import LoyaltyEntry, level_for, DEFAULT_LEVELS
from app.main import SessionLocal, User


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _new_customer(tenant_email="employee@aftab.test"):
    with SessionLocal() as db:
        tid = db.scalar(select(User.tenant_id).where(User.email == tenant_email))
        email = f"loyal-{uuid.uuid4().hex[:8]}@aftab.test"
        u = User(tenant_id=tid, email=email, name="مسافر وفادار", role="customer")
        db.add(u)
        db.commit()
        return email, u.id, tid


def _complete_trip(user_id, tid, amount, suffix):
    with SessionLocal() as db:
        res = m.Reservation(tenant_id=tid, user_id=user_id, service_type="tour", status="issued", booking_reference="LY-" + uuid.uuid4().hex[:8],
                            price_snapshot_json=json.dumps({"total_amount": amount, "currency": "IRR"}))
        db.add(res)
        db.flush()
        m.transition_reservation(db, res, "completed", None, f"ly-complete-{suffix}")
        db.commit()
        return res.id


def test_level_for():
    cur, nxt = level_for(DEFAULT_LEVELS, 600)
    assert cur["key"] == "silver" and nxt["key"] == "gold"
    assert level_for(DEFAULT_LEVELS, 0)[0]["key"] == "bronze" and level_for(DEFAULT_LEVELS, 99999)[1] is None


def test_loyalty_flow(client):
    admin = _h(client, "tenant-admin@aftab.test")
    a_email, a_id, tid = _new_customer()
    b_email, b_id, _ = _new_customer()
    a, b = _h(client, a_email), _h(client, b_email)
    client.put("/loyalty/settings", json={"enabled": False, "irr_per_point": 100_000, "referral_bonus_points": 0,
                                          "levels": [{"key": "bronze", "name": "برنزی", "min_points": 0}]}, headers=admin)
    assert client.get("/me/loyalty", headers=a).json() == {"enabled": False}
    _complete_trip(a_id, tid, 50_000_000, "off-" + uuid.uuid4().hex[:6])  # nothing earned while off
    assert client.get("/loyalty/settings", headers=a).status_code == 403
    bad = client.put("/loyalty/settings", json={"enabled": True, "irr_per_point": 100_000, "referral_bonus_points": 50,
                                                "levels": [{"key": "x", "name": "x", "min_points": 10}]}, headers=admin)
    assert bad.status_code == 422  # first level must start at zero
    ok = client.put("/loyalty/settings", json={"enabled": True, "irr_per_point": 100_000, "referral_bonus_points": 50,
                                               "levels": [{"key": "bronze", "name": "برنزی", "min_points": 0}, {"key": "silver", "name": "نقره‌ای", "min_points": 500, "benefits": "پشتیبانی اختصاصی"}]}, headers=admin)
    assert ok.status_code == 200 and ok.json()["enabled"] is True
    me_a = client.get("/me/loyalty", headers=a).json()
    assert me_a["enabled"] and me_a["points_earned"] == 0 and me_a["level"]["key"] == "bronze" and me_a["referral_code"].startswith("KS")
    # B uses A's code, own code rejected, unknown rejected
    me_b = client.get("/me/loyalty", headers=b).json()
    assert client.post("/me/loyalty/referral", json={"code": me_b["referral_code"]}, headers=b).status_code == 422
    assert client.post("/me/loyalty/referral", json={"code": "KSNOPE00"}, headers=b).status_code == 404
    assert client.post("/me/loyalty/referral", json={"code": me_a["referral_code"].lower()}, headers=b).status_code == 200
    assert client.post("/me/loyalty/referral", json={"code": me_a["referral_code"]}, headers=b).status_code == 409
    # B completes a 60M IRR trip -> 600 points (silver); A gets the referral bonus once
    sfx = uuid.uuid4().hex[:6]
    rid = _complete_trip(b_id, tid, 60_000_000, sfx)
    me_b = client.get("/me/loyalty", headers=b).json()
    assert me_b["points_earned"] == 600 and me_b["level"]["key"] == "silver" and me_b["next_level"] is None and not me_b["can_enter_referral"]
    assert client.get("/me/loyalty", headers=a).json()["points_earned"] == 50
    with SessionLocal() as db:  # idempotent: awarding again changes nothing
        from app.loyalty import award_trip
        award_trip(db, db.get(m.Reservation, rid))
        db.commit()
        assert len(db.scalars(select(LoyaltyEntry).where(LoyaltyEntry.ref == f"trip:{rid}")).all()) == 1
    _complete_trip(b_id, tid, 10_000_000, sfx + "b")
    assert client.get("/me/loyalty", headers=a).json()["points_earned"] == 50  # referral bonus only on the first trip
    # admin adjust, cannot go negative
    assert client.post("/loyalty/adjust", json={"user_id": b_id, "points": -100000, "reason": "اصلاح"}, headers=admin).status_code == 409
    adj = client.post("/loyalty/adjust", json={"user_id": b_id, "points": -100, "reason": "استفاده در جشنواره"}, headers=admin)
    assert adj.status_code == 201 and adj.json()["points_balance"] == 600
    members = client.get("/loyalty/members", headers=admin).json()
    assert any(i["user_id"] == b_id and i["level"] == "نقره‌ای" for i in members["items"])
    # another tenant cannot adjust this user
    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"ly-admin-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="مدیر فراز", role="tenant_admin"))
        db.commit()
    other = _h(client, oemail)
    assert client.post("/loyalty/adjust", json={"user_id": b_id, "points": 10, "reason": "تست نفوذ"}, headers=other).status_code == 404
    assert all(i["user_id"] != b_id for i in client.get("/loyalty/members", headers=other).json()["items"])
    client.put("/loyalty/settings", json={"enabled": False, "irr_per_point": 100_000, "referral_bonus_points": 0,
                                          "levels": [{"key": "bronze", "name": "برنزی", "min_points": 0}]}, headers=admin)
