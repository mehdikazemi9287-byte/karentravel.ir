"""Loyalty call schedule: generated from real completed trips and dormant members, deduplicated, claim and result."""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import operations as m
from app.loyalty import LoyaltyAccount
from app.loyalty_calls import LoyaltyCallTask
from app.main import SessionLocal, User


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_call_schedule(client):
    bo = _h(client, "backoffice@aftab.test")
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        tid = db.scalar(select(User.tenant_id).where(User.email == "employee@aftab.test"))
        traveller = User(tenant_id=tid, email=f"lc-{uuid.uuid4().hex[:6]}@aftab.test", name="مسافر تماس", role="customer", mobile_e164="+98912" + str(uuid.uuid4().int)[:7])
        sleeper = User(tenant_id=tid, email=f"lc-{uuid.uuid4().hex[:6]}@aftab.test", name="مشتری کم‌فعال", role="customer")
        db.add_all([traveller, sleeper]); db.flush()
        done = m.Reservation(tenant_id=tid, user_id=traveller.id, service_type="tour", status="completed", booking_reference="LC-" + uuid.uuid4().hex[:6],
                             price_snapshot_json="{}", policy_at_booking_json="{}", current_policy_json="{}")
        old = m.Reservation(tenant_id=tid, user_id=sleeper.id, service_type="hotel", status="completed", booking_reference="LC-" + uuid.uuid4().hex[:6],
                            price_snapshot_json="{}", policy_at_booking_json="{}", current_policy_json="{}")
        db.add_all([done, old]); db.flush()
        done.updated_at = now - timedelta(days=5)
        old.created_at = old.updated_at = now - timedelta(days=400)
        db.add(LoyaltyAccount(tenant_id=tid, user_id=sleeper.id, referral_code="LC" + uuid.uuid4().hex[:6].upper()))
        db.commit()
        traveller_id, sleeper_id, done_id = traveller.id, sleeper.id, done.id

    assert client.post("/loyalty/calls/generate", json={}, headers=_h(client, "employee@aftab.test")).status_code == 403
    g = client.post("/loyalty/calls/generate", json={}, headers=bo).json()["created"]
    assert g["post_trip"] >= 1 and g["dormant"] >= 1
    again = client.post("/loyalty/calls/generate", json={}, headers=bo).json()["created"]
    with SessionLocal() as db:
        assert db.scalar(select(LoyaltyCallTask).where(LoyaltyCallTask.reservation_id == done_id)) is not None
        assert len(db.scalars(select(LoyaltyCallTask).where(LoyaltyCallTask.user_id == sleeper_id, LoyaltyCallTask.reason == "dormant")).all()) == 1
    assert again == {"post_trip": 0, "dormant": 0} or again["post_trip"] + again["dormant"] < g["post_trip"] + g["dormant"]

    items = client.get("/loyalty/calls", headers=bo).json()["items"]
    trip = next(i for i in items if i["reason"] == "post_trip" and i["customer"] == "مسافر تماس")
    assert trip["booking_reference"].startswith("LC-") and trip["mobile"].startswith("+98912")
    assert client.post(f"/loyalty/calls/{trip['id']}/claim", headers=bo).json()["assigned"]
    admin = _h(client, "tenant-admin@aftab.test")
    assert client.post(f"/loyalty/calls/{trip['id']}/result", json={"outcome": "reached"}, headers=admin).status_code == 409   # claimed by someone else
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert client.post(f"/loyalty/calls/{trip['id']}/result", json={"outcome": "reached", "next_call_on": yesterday}, headers=bo).status_code == 422
    nxt = (date.today() + timedelta(days=7)).isoformat()
    r = client.post(f"/loyalty/calls/{trip['id']}/result", json={"outcome": "reached", "note": "از تور راضی بود", "next_call_on": nxt}, headers=bo).json()
    assert r["status"] == "done" and r["follow_up_created"]
    follow = [i for i in client.get("/loyalty/calls", headers=bo).json()["items"] if i["customer"] == "مسافر تماس" and i["reason"] == "manual"]
    assert follow and follow[0]["due_on"] == nxt
    assert client.post("/loyalty/calls", json={"user_id": traveller_id, "due_on": nxt}, headers=bo).status_code == 409
    assert client.post(f"/loyalty/calls/{follow[0]['id']}/skip", headers=bo).json()["status"] == "skipped"

    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"lc-bo-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="عملیات فراز", role="backoffice_expert"))
        db.commit()
    other = _h(client, oemail)
    assert client.post(f"/loyalty/calls/{trip['id']}/claim", headers=other).status_code == 404
    assert client.post("/loyalty/calls", json={"user_id": traveller_id, "due_on": nxt}, headers=other).status_code == 404
