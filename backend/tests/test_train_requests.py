"""Train ticket requests: customer request → agent offers → customer accepts (reservation + checkout) → paid → ticket issued."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import operations as m
from app.main import SessionLocal, User
from app.train_requests import office_state


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_office_hours():
    hours = {"days": [0, 1, 2, 3, 4], "start": "08:00", "end": "17:00", "thursday_end": "13:00"}
    tehran = timezone(timedelta(hours=3, minutes=30))
    # 2026-11-07 is a Saturday
    assert office_state(hours, datetime(2026, 11, 7, 10, 0, tzinfo=tehran))["open"]
    closed = office_state(hours, datetime(2026, 11, 7, 18, 0, tzinfo=tehran))
    assert not closed["open"] and closed["next_open"].startswith("2026-11-08T08:00")
    friday = office_state(hours, datetime(2026, 11, 6, 10, 0, tzinfo=tehran))
    assert not friday["open"] and friday["next_open"].startswith("2026-11-07T08:00")


def test_train_request_flow(client):
    cust = _h(client, "employee@aftab.test")
    agent = _h(client, "backoffice@aftab.test")
    other = _h(client, "tenant-admin@aftab.test")
    day = (date.today() + timedelta(days=10)).isoformat()
    assert client.post("/train-requests", json={"origin": "تهران", "destination": "تهران", "depart_on": day}, headers=cust).status_code == 422
    assert client.post("/train-requests", json={"origin": "تهران", "destination": "مشهد", "depart_on": "2020-01-01"}, headers=cust).status_code == 422
    r = client.post("/train-requests", json={"origin": "تهران", "destination": "مشهد", "depart_on": day, "adults": 2, "children": 1, "wagon": "coupe4",
                                            "passenger_kind": "sisters", "exclusive_coupe": True}, headers=cust)
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "submitted" and "open" in req["desk"]
    assert client.get("/train-desk/requests", headers=cust).status_code == 403

    q = client.get("/train-desk/requests", headers=agent).json()
    assert any(i["id"] == req["id"] and i["passenger_kind_fa"] == "ویژه‌ی خواهران" for i in q["items"])
    assert client.post(f"/train-desk/requests/{req['id']}/claim", headers=agent).json()["assigned"]
    dep = datetime.now(timezone.utc) + timedelta(days=10)
    offer = {"train_name": "فدک", "train_number": "354", "company": "فدک", "departs_at": dep.isoformat(), "arrives_at": (dep + timedelta(hours=11)).isoformat(),
             "wagon": "کوپه‌ی ۴ تخته", "price_adult": 30_000_000}
    assert client.post(f"/train-desk/requests/{req['id']}/offers", json={"offers": [offer]}, headers=agent).status_code == 422   # child price missing
    assert client.post(f"/train-desk/requests/{req['id']}/offers", json={"offers": [{**offer, "price_child": 20_000_000}]}, headers=other).status_code == 409   # claimed by someone else
    o = client.post(f"/train-desk/requests/{req['id']}/offers", json={"offers": [{**offer, "price_child": 20_000_000}, {**offer, "train_name": "غزال", "price_adult": 25_000_000, "price_child": 18_000_000}]}, headers=agent)
    assert o.status_code == 200, o.text
    offers = o.json()["offers"]
    assert offers[0]["total"] == 2 * 30_000_000 + 20_000_000 and o.json()["status"] == "offered"

    mine = client.get("/me/train-requests", headers=cust).json()["items"]
    assert mine[0]["id"] == req["id"] and len(mine[0]["offers"]) == 2
    assert client.post(f"/me/train-requests/{req['id']}/accept", json={"offer_ids": ["nope"]}, headers=cust).status_code == 422
    a = client.post(f"/me/train-requests/{req['id']}/accept", json={"offer_ids": [offers[1]["id"]]}, headers=cust)
    assert a.status_code == 200, a.text
    acc = a.json()
    assert acc["status"] == "accepted" and acc["checkout_url"] == f"/checkout/{acc['reservation_id']}"
    with SessionLocal() as db:
        res = db.scalar(select(m.Reservation).where(m.Reservation.id == acc["reservation_id"]))
        assert res.service_type == "train" and res.status == "reserved"
        assert '"total_amount": 68000000' in res.price_snapshot_json
    assert client.post(f"/train-desk/requests/{req['id']}/issue", json={"ticket_numbers": "123456"}, headers=agent).status_code == 409   # not paid yet
    with SessionLocal() as db:   # payment confirmed by the checkout
        res = db.scalar(select(m.Reservation).where(m.Reservation.id == acc["reservation_id"]))
        res.status = "confirmed"; db.commit()
    i = client.post(f"/train-desk/requests/{req['id']}/issue", json={"ticket_numbers": "123456، 123457، 123458"}, headers=agent)
    assert i.status_code == 200, i.text
    assert i.json()["status"] == "issued"
    with SessionLocal() as db:
        assert db.scalar(select(m.Reservation.status).where(m.Reservation.id == acc["reservation_id"])) == "issued"


def test_unavailable_refer_and_settings(client):
    cust = _h(client, "employee@aftab.test")
    agent = _h(client, "backoffice@aftab.test")
    admin = _h(client, "tenant-admin@aftab.test")
    day = (date.today() + timedelta(days=5)).isoformat()
    a = client.post("/train-requests", json={"origin": "تهران", "destination": "اصفهان", "depart_on": day}, headers=cust).json()
    assert client.post(f"/train-desk/requests/{a['id']}/unavailable", json={}, headers=agent).json()["status"] == "unavailable"
    b = client.post("/train-requests", json={"origin": "تهران", "destination": "یزد", "depart_on": day}, headers=cust).json()
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        u.mobile_e164 = u.mobile_e164 or "+989121234567"; db.commit()
    ref = client.post(f"/train-desk/requests/{b['id']}/refer", json={"note": "تور یزد با هتل"}, headers=agent)
    assert ref.status_code == 200, ref.text
    assert ref.json()["status"] == "referred" and ref.json()["sales_case_code"]
    assert client.put("/train-desk/settings", json={"days": [0, 1], "start": "09:00", "end": "16:00", "offer_valid_minutes": 45}, headers=agent).status_code == 403
    s = client.put("/train-desk/settings", json={"days": [0, 1, 2, 3, 4], "start": "08:30", "end": "17:00", "thursday_end": "13:00", "offer_valid_minutes": 45}, headers=admin)
    assert s.status_code == 200 and s.json()["offer_valid_minutes"] == 45
    assert client.get("/train-requests/desk", headers=cust).json()["hours"]["start"] == "08:30"
