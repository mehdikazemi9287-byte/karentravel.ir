"""Safarsaz: draft tour -> checklist -> publish into the bookable tour catalogue -> quote/book -> auto-draft when expired."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.main import SessionLocal
from app.safarsaz import SafarsazDeparture, pricing_for_engine


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_pricing_for_engine_maps_rooms_to_surcharges():
    base, pricing = pricing_for_engine([{"room": "double", "adult": 10_000_000, "child": 7_000_000, "infant": 1_000_000},
                                        {"room": "single", "adult": 13_000_000}, {"room": "triple", "adult": 9_500_000}])
    assert base == 10_000_000 and pricing["single_surcharge"] == 3_000_000 and pricing["triple_surcharge"] == -500_000
    assert "extra_bed_surcharge" not in pricing and pricing["matrix"][0]["child"] == 7_000_000


def test_safarsaz_publish_flow(client):
    admin = _h(client, "platform-admin@aftab.test")
    desk = _h(client, "backoffice@aftab.test")
    tadmin = _h(client, "tenant-admin@aftab.test")
    emp = _h(client, "employee@aftab.test")
    suffix = uuid.uuid4().hex[:8]
    sup = client.post("/inventory/suppliers", json={"name": f"برگزارکننده {suffix}", "supplier_type": "tour_operator"}, headers=admin)
    assert sup.status_code == 201, sup.text
    sid = sup.json()["id"]

    assert client.get("/safarsaz/tours", headers=emp).status_code == 403
    bad = client.post("/safarsaz/tours", json={"title": "تور بد", "origin": "تهران", "destination": "کیش", "source": "charter_block"}, headers=desk)
    assert bad.status_code == 422  # charter source needs a reference
    assert client.post("/safarsaz/tours", json={"title": "تور بد", "origin": "تهران", "destination": "کیش", "source": "scraped"}, headers=desk).status_code == 422

    body = {"title": f"کیش ۳ شب {suffix}", "origin": "تهران", "destination": "کیش", "supplier_id": sid, "source": "manual"}
    t = client.post("/safarsaz/tours", json=body, headers=desk)
    assert t.status_code == 201, t.text
    tour = t.json()
    assert tour["status"] == "draft" and not tour["ready"] and tour["slug"]
    pub = client.post(f"/safarsaz/tours/{tour['id']}/publish", headers=tadmin)
    assert pub.status_code == 409 and "missing" in pub.json()["detail"]
    assert client.post(f"/safarsaz/tours/{tour['id']}/publish", headers=desk).status_code == 403

    full = {**body, "description": "سه شب اقامت در کیش با پرواز رفت و برگشت، ترانسفر فرودگاهی و گشت دریایی نیم‌روزه.",
            "itinerary": [{"title": "روز اول", "body": "پرواز و تحویل اتاق"}, {"title": "روز دوم", "body": "گشت دریایی"}],
            "hotels": [{"name": "هتل آزمون", "city": "کیش", "nights": 3, "board": "bb", "stars": 4}],
            "inclusions": ["پرواز", "ترانسفر"], "documents": ["کارت ملی"], "cancellation": [{"days_before": 7, "penalty_bps": 1000}, {"days_before": 0, "penalty_bps": 5000}],
            "deposit_bps": 3000}
    u = client.put(f"/safarsaz/tours/{tour['id']}", json=full, headers=desk)
    assert u.status_code == 200, u.text
    assert u.json()["hotels"][0]["board"] == "BB" and u.json()["cancellation"][0]["days_before"] == 7
    start = datetime.now(timezone.utc) + timedelta(days=20)
    dep = {"starts_at": start.isoformat(), "ends_at": (start + timedelta(days=3)).isoformat(), "booking_deadline": (start - timedelta(days=2)).isoformat(),
           "capacity": 20, "prices": [{"room": "double", "adult": 12_000_000, "child": 9_000_000}, {"room": "single", "adult": 16_000_000}]}
    assert client.post(f"/safarsaz/tours/{tour['id']}/departures", json={**dep, "prices": [{"room": "single", "adult": 1}]}, headers=desk).status_code == 422
    assert client.post(f"/safarsaz/tours/{tour['id']}/departures", json={**dep, "booking_deadline": (start + timedelta(days=1)).isoformat()}, headers=desk).status_code == 422
    d = client.post(f"/safarsaz/tours/{tour['id']}/departures", json=dep, headers=desk)
    assert d.status_code == 201 and d.json()["ready"] is True, d.json().get("checklist")

    p = client.post(f"/safarsaz/tours/{tour['id']}/publish", headers=tadmin)
    assert p.status_code == 200, p.text
    published = p.json()
    assert published["status"] == "published" and published["new_departures"] == 1
    product_id = published["published_tour_id"]
    # republishing does not duplicate departures
    assert client.post(f"/safarsaz/tours/{tour['id']}/publish", headers=tadmin).json()["new_departures"] == 0

    detail = client.get(f"/tour-products/{product_id}", headers=emp)
    assert detail.status_code == 200, detail.text
    dd = detail.json()
    assert dd["details"]["requirements"] == ["کارت ملی"] and len(dd["departures"]) == 1
    departure = dd["departures"][0]
    assert departure["base_price"] == 12_000_000 and set(departure["available_room_types"]) == {"double", "single"}
    q = client.get(f"/tour-departures/{departure['id']}/quote", params={"travellers": 2, "room_type": "single"}, headers=emp)
    assert q.status_code == 200 and q.json()["total_amount"] == 32_000_000
    assert client.get(f"/tour-departures/{departure['id']}/quote", params={"travellers": 1, "room_type": "triple"}, headers=emp).status_code == 409
    booked = client.post(f"/tour-departures/{departure['id']}/reservations", json={"travellers": 2, "room_type": "double", "command_id": f"safarsaz-{suffix}"}, headers=emp)
    assert booked.status_code == 201 and booked.json()["total_amount"] == 24_000_000
    # child prices from the room x passenger matrix; a missing price is not sellable online
    qc = client.get(f"/tour-departures/{departure['id']}/quote", params={"travellers": 2, "children": 1, "room_type": "double"}, headers=emp)
    assert qc.status_code == 200 and qc.json()["total_amount"] == 2 * 12_000_000 + 9_000_000
    assert client.get(f"/tour-departures/{departure['id']}/quote", params={"travellers": 1, "infants": 1, "room_type": "double"}, headers=emp).status_code == 409
    assert client.get(f"/tour-departures/{departure['id']}/quote", params={"travellers": 1, "children": 1, "room_type": "single"}, headers=emp).status_code == 409
    fam = client.post(f"/tour-departures/{departure['id']}/reservations", json={"travellers": 2, "children": 1, "room_type": "double", "command_id": f"safarsaz-fam-{suffix}"}, headers=emp)
    assert fam.status_code == 201 and fam.json()["total_amount"] == 33_000_000
    after = client.get(f"/tour-products/{product_id}", headers=emp).json()["departures"][0]
    assert after["remaining"] == 20 - 2 - 3

    # published departures are not deletable from the builder
    assert client.delete(f"/safarsaz/tours/{tour['id']}/departures/{published['departures'][0]['id']}", headers=desk).status_code == 409
    copy = client.post(f"/safarsaz/tours/{tour['id']}/copy", headers=desk)
    assert copy.status_code == 201 and copy.json()["source"] == "copy" and copy.json()["departures"] == [] and copy.json()["status"] == "draft"

    # every departure closed -> back to draft and gone from the catalogue
    with SessionLocal() as db:
        db.execute(update(SafarsazDeparture).where(SafarsazDeparture.tour_id == tour["id"]).values(booking_deadline=datetime.now(timezone.utc) - timedelta(hours=1)))
        db.commit()
    ex = client.post("/safarsaz/expire", headers=desk).json()
    assert tour["id"] in ex["ids"]
    assert client.get(f"/safarsaz/tours/{tour['id']}", headers=desk).json()["status"] == "draft"
    assert client.get(f"/tour-products/{product_id}", headers=emp).status_code == 404


def test_safarsaz_is_tenant_isolated(client):
    desk = _h(client, "backoffice@aftab.test")
    t = client.post("/safarsaz/tours", json={"title": "تور ایزوله", "origin": "تهران", "destination": "شیراز"}, headers=desk).json()
    from app.main import User
    from sqlalchemy import select
    with SessionLocal() as db:
        other_tid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        email = f"ss-{uuid.uuid4().hex[:8]}@faraz.test"
        db.add(User(tenant_id=other_tid, email=email, name="کارشناس فراز", role="backoffice_expert"))
        db.commit()
    other = _h(client, email)
    assert client.get(f"/safarsaz/tours/{t['id']}", headers=other).status_code == 404
    assert all(i["id"] != t["id"] for i in client.get("/safarsaz/tours", headers=other).json()["items"])
    assert client.post(f"/safarsaz/tours/{t['id']}/copy", headers=other).status_code == 404
