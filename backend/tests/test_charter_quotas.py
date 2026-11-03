"""Charter seat quotas: held seats leave public sale, are not counted as sold, come back on release or at stop-quota time."""
import random
import string
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update

from app import operations as m
from app.charter_quotas import SeatQuota
from app.main import SessionLocal, User


def _h(client, email):
    return {"Authorization": f"Bearer {client.post('/auth/dev-login', json={'email': email}).json()['access_token']}"}


def _flight(client, admin, capacity=20):
    sup = client.post("/inventory/suppliers", json={"name": "چارتر سهمیه", "supplier_type": "charterer"}, headers=admin).json()
    o, d = "K" + "".join(random.choices(string.ascii_uppercase, k=2)), "W" + "".join(random.choices(string.ascii_uppercase, k=2))
    route = client.post("/inventory/routes", json={"origin": o, "destination": d}, headers=admin).json()
    start = date.today() + timedelta(days=5)
    body = {"route_id": route["id"], "supplier_id": sup["id"], "airline_code": "ep", "flight_number": str(random.randint(1000, 9999)),
            "date_from": start.isoformat(), "date_to": start.isoformat(), "schedule": {str(start.weekday()): {"time": "09:00", "duration": 60}},
            "capacity": capacity, "adult_fare": 20_000_000, "child_fare": 20_000_000, "infant_fare": 2_000_000}
    sid = client.post("/inventory/flight-series", json=body, headers=admin).json()["id"]
    client.post(f"/inventory/flight-series/{sid}/generate", headers=admin)
    return client.get("/inventory/flights", params={"series_id": sid}, headers=admin).json()["items"][0]


def test_quota_hold_release_and_auto_release(client):
    admin = _h(client, "platform-admin@aftab.test")
    with SessionLocal() as db:
        tid = db.scalar(select(User.tenant_id).where(User.email == "platform-admin@aftab.test"))
        ag = m.Agency(tenant_id=tid, display_name="آژانس سهمیه " + uuid.uuid4().hex[:4], status="active")
        db.add(ag); db.commit(); agency_id = ag.id
    f = _flight(client, admin, capacity=20)
    assert client.get("/charter-quotas", headers=_h(client, "employee@aftab.test")).status_code == 403
    assert client.post("/charter-quotas", json={"instance_id": f["id"], "agency_id": agency_id, "seats": 21}, headers=admin).status_code == 409
    q = client.post("/charter-quotas", json={"instance_id": f["id"], "agency_id": agency_id, "seats": 8, "note": "تور نوروز"}, headers=admin)
    assert q.status_code == 201, q.text
    qid = q.json()["id"]
    av = client.get(f"/charter-quotas/flights/{f['id']}", headers=admin).json()
    assert av["public_available"] == 12 and av["held_quota"] == 8 and av["sold"] == 0
    row = next(i for i in client.get("/inventory/flights", params={"series_id": f["series_id"]}, headers=admin).json()["items"] if i["id"] == f["id"])
    assert row["sold"] == 0 and row["held_quota"] == 8 and row["remaining"] == 12
    emp = _h(client, "employee@aftab.test")
    assert client.get(f"/offers/{f['offer_id']}", headers=emp).json()["max_units"] == 12  # public sale only sees free seats
    # capacity cannot drop below sold + held; editing the flight keeps the hold
    assert client.put(f"/inventory/flights/{f['id']}", json={"capacity": 7}, headers=admin).status_code == 409
    assert client.put(f"/inventory/flights/{f['id']}", json={"capacity": 18}, headers=admin).json()["remaining"] == 10
    # partial release for the agency's booking, then the rest at stop-quota time
    r = client.post(f"/charter-quotas/{qid}/release", json={"seats": 3, "reason": "agency_booking"}, headers=admin).json()
    assert r["released_now"] == 3 and r["seats"] == 5 and r["status"] == "held"
    assert client.get(f"/charter-quotas/flights/{f['id']}", headers=admin).json()["public_available"] == 13
    with SessionLocal() as db:
        db.execute(update(SeatQuota).where(SeatQuota.id == qid).values(release_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    lst = client.get("/charter-quotas", params={"instance_id": f["id"]}, headers=admin).json()
    assert lst["auto_released_seats"] == 5 and lst["items"][0]["status"] == "released" and lst["items"][0]["released_reason"] == "stop_quota"
    assert client.get(f"/charter-quotas/flights/{f['id']}", headers=admin).json()["public_available"] == 18
    assert client.post(f"/charter-quotas/{qid}/release", json={}, headers=admin).status_code == 409
    # other tenant cannot see or touch it
    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"q-admin-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="مدیر فراز", role="tenant_admin")); db.commit()
    other = _h(client, oemail)
    assert client.get(f"/charter-quotas/flights/{f['id']}", headers=other).status_code == 404
    assert client.post("/charter-quotas", json={"instance_id": f["id"], "agency_id": agency_id, "seats": 1}, headers=other).status_code == 404
