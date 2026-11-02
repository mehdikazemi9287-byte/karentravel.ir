import uuid
from datetime import date, timedelta

from app.catalog import CatalogHotel
from app.main import SessionLocal


def _h(client, email):
    return {"Authorization": f"Bearer {client.post('/auth/dev-login', json={'email': email}).json()['access_token']}"}


def _hotel():
    hid = "t-" + uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        db.add(CatalogHotel(id=hid, slug=f"stay-test-{hid}", country_code="IR", hotel_type="hotel", name_fa="هتل آزمون قرارداد", stars=4, status="published", source="inhouse"))
        db.commit()
    return hid


def test_contract_calendar_availability_and_booking_handoff(client):
    admin = _h(client, "platform-admin@aftab.test")
    emp = _h(client, "employee@aftab.test")
    hid = _hotel()
    sup = client.post("/inventory/suppliers", json={"name": "هتل‌دار آزمون", "supplier_type": "hotel"}, headers=admin).json()
    d0 = date.today() + timedelta(days=10)
    c = client.post("/stays/contracts", json={"hotel_id": hid, "supplier_id": sup["id"], "title": "قرارداد پاییز", "valid_from": d0.isoformat(),
                                              "valid_to": (d0 + timedelta(days=30)).isoformat(), "release_days": 2, "min_stay": 2}, headers=admin)
    assert c.status_code == 201, c.text
    room = client.post(f"/stays/contracts/{c.json()['id']}/rooms", json={"name": "دوتخته استاندارد", "board": "BB", "max_adults": 2, "max_children": 1, "extra_beds": 1}, headers=admin).json()
    cal = client.put(f"/stays/rooms/{room['id']}/calendar", json={"date_from": d0.isoformat(), "date_to": (d0 + timedelta(days=9)).isoformat(),
                                                                  "allotment": 2, "price": 40_000_000, "single_price": 30_000_000, "extra_bed_price": 10_000_000, "child_price": 5_000_000}, headers=admin)
    assert cal.json()["nights_updated"] == 10
    slug = f"stay-test-{hid}"
    q = lambda **kw: client.get(f"/stays/hotels/{slug}/availability", params={"checkin": d0.isoformat(), "checkout": (d0 + timedelta(days=3)).isoformat(), **kw}, headers=emp).json()["offers"]
    offers = q(adults=2)
    assert len(offers) == 1 and offers[0]["total_per_room"] == 120_000_000 and offers[0]["rooms_left"] == 2
    assert q(adults=1)[0]["total_per_room"] == 90_000_000
    assert q(adults=3)[0]["total_per_room"] == 150_000_000           # extra bed
    assert q(adults=2, children_ages="7")[0]["total_per_room"] == 135_000_000
    assert q(adults=2, children_ages="1")[0]["total_per_room"] == 120_000_000   # infant free
    assert q(adults=4) == [] and q(adults=2, rooms=3) == []
    one_night = client.get(f"/stays/hotels/{slug}/availability", params={"checkin": d0.isoformat(), "checkout": (d0 + timedelta(days=1)).isoformat()}, headers=emp).json()["offers"]
    assert one_night == []                                             # min stay 2
    # stop sell one night closes the stay
    client.put(f"/stays/rooms/{room['id']}/calendar", json={"date_from": (d0 + timedelta(days=1)).isoformat(), "date_to": (d0 + timedelta(days=1)).isoformat(), "stop_sell": True}, headers=admin)
    assert q(adults=2) == []
    client.put(f"/stays/rooms/{room['id']}/calendar", json={"date_from": (d0 + timedelta(days=1)).isoformat(), "date_to": (d0 + timedelta(days=1)).isoformat(), "stop_sell": False}, headers=admin)
    # booking handoff -> normal offer
    b = client.post(f"/stays/hotels/{slug}/book", json={"room_id": room["id"], "checkin": d0.isoformat(), "checkout": (d0 + timedelta(days=3)).isoformat(), "adults": 2, "rooms": 1}, headers=emp)
    assert b.status_code == 201, b.text
    detail = client.get(f"/offers/{b.json()['offer_id']}", headers=emp).json()
    assert detail["amount"] == 120_000_000 and detail["service_type"] == "hotel"
    # simulate a sold room: consuming one unit reduces the night allotment for everyone
    from app import operations as m
    with SessionLocal() as db:
        o = db.get(m.Offer, b.json()["offer_id"]); o.available_units = 0; db.commit()
    assert q(adults=2)[0]["rooms_left"] == 1
    cal2 = client.get(f"/stays/rooms/{room['id']}/calendar", params={"date_from": d0.isoformat(), "date_to": (d0 + timedelta(days=3)).isoformat()}, headers=admin).json()
    assert [n["sold"] for n in cal2["nights"]] == [1, 1, 1, 0]
    assert client.put(f"/stays/rooms/{room['id']}/calendar", json={"date_from": d0.isoformat(), "date_to": d0.isoformat(), "allotment": 0}, headers=admin).status_code == 409
    assert client.get("/stays/contracts", headers=emp).status_code == 403
