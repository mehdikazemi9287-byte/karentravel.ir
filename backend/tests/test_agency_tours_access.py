"""Contracted agency manages its own tours from the agency panel (AgencyMembership -> linked tour organiser),
sees bookings received per departure, and never sees another agency's tours or bookings."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.main import SessionLocal, User


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _agency_user(email_prefix):
    with SessionLocal() as db:
        tid = db.scalar(select(User.tenant_id).where(User.email == "agency@aftab.test"))
        email = f"{email_prefix}-{uuid.uuid4().hex[:8]}@aftab.test"
        u = User(tenant_id=tid, email=email, name="کاربر آژانس آزمون", role="agency_partner")
        db.add(u); db.commit()
        return email, u.id


def _setup(client):
    admin, tadmin = _h(client, "platform-admin@aftab.test"), _h(client, "tenant-admin@aftab.test")
    s = uuid.uuid4().hex[:8]
    sup_a = client.post("/inventory/suppliers", json={"name": f"برگزارکننده الف {s}", "supplier_type": "tour_operator"}, headers=admin).json()["id"]
    sup_b = client.post("/inventory/suppliers", json={"name": f"برگزارکننده ب {s}", "supplier_type": "tour_operator"}, headers=admin).json()["id"]
    ag_a = client.post("/admin/partners/agencies", json={"display_name": f"آژانس الف {s}", "commission_bps": 500, "markup_bps": 0}, headers=tadmin)
    ag_b = client.post("/admin/partners/agencies", json={"display_name": f"آژانس ب {s}", "commission_bps": 500, "markup_bps": 0}, headers=tadmin)
    assert ag_a.status_code == 201 and ag_b.status_code == 201, (ag_a.text, ag_b.text)
    ag_a, ag_b = ag_a.json()["id"], ag_b.json()["id"]
    email_a, uid_a = _agency_user("ag-a")
    email_b, uid_b = _agency_user("ag-b")
    assert client.post(f"/agency/{ag_a}/members", json={"user_id": uid_a}, headers=tadmin).status_code == 201
    assert client.post(f"/agency/{ag_b}/members", json={"user_id": uid_b}, headers=tadmin).status_code == 201
    return {"admin": admin, "tadmin": tadmin, "sup_a": sup_a, "sup_b": sup_b, "ag_a": ag_a, "ag_b": ag_b, "a": _h(client, email_a), "b": _h(client, email_b), "s": s}


FULL = {"description": "سه شب اقامت در شیراز با اتوبوس رفت و برگشت، ترانسفر و بازدید از تخت جمشید و پاسارگاد.",
        "itinerary": [{"title": "روز اول", "body": "حرکت و تحویل اتاق"}], "hotels": [{"name": "هتل آزمون", "city": "شیراز", "nights": 3, "board": "BB", "stars": 4}],
        "inclusions": ["اتوبوس"], "documents": ["کارت ملی"], "cancellation": [{"days_before": 3, "penalty_bps": 2000}]}


def test_agency_needs_linked_organiser_and_link_is_admin_only(client):
    x = _setup(client)
    assert client.get("/safarsaz/tours", headers=x["a"]).status_code == 403  # agency not yet linked to a tour organiser
    assert client.put(f"/admin/partners/agencies/{x['ag_a']}/tour-organiser", json={"supplier_id": x["sup_a"]}, headers=x["a"]).status_code == 403
    assert client.put(f"/admin/partners/agencies/{x['ag_a']}/tour-organiser", json={"supplier_id": str(uuid.uuid4())}, headers=x["tadmin"]).status_code == 422
    ok = client.put(f"/admin/partners/agencies/{x['ag_a']}/tour-organiser", json={"supplier_id": x["sup_a"]}, headers=x["tadmin"])
    assert ok.status_code == 200 and ok.json()["supplier_id"] == x["sup_a"]
    # one organiser belongs to one agency
    assert client.put(f"/admin/partners/agencies/{x['ag_b']}/tour-organiser", json={"supplier_id": x["sup_a"]}, headers=x["tadmin"]).status_code == 409
    listed = [ag for ag in client.get("/admin/partners", headers=x["tadmin"]).json()["agencies"] if ag["id"] == x["ag_a"]]
    assert listed and listed[0]["supplier_id"] == x["sup_a"]
    sup = client.get("/safarsaz/suppliers", headers=x["a"]).json()
    assert sup["partner"] is True and [i["id"] for i in sup["items"]] == [x["sup_a"]]
    # agency B still has nothing
    assert client.get("/safarsaz/tours", headers=x["b"]).status_code == 403


def test_agency_tours_and_bookings_are_isolated_between_agencies(client):
    x = _setup(client)
    for ag, sup in ((x["ag_a"], x["sup_a"]), (x["ag_b"], x["sup_b"])):
        assert client.put(f"/admin/partners/agencies/{ag}/tour-organiser", json={"supplier_id": sup}, headers=x["tadmin"]).status_code == 200
    body = {"title": f"شیراز ۳ شب {x['s']}", "origin": "تهران", "destination": "شیراز", "source": "manual"}
    assert client.post("/safarsaz/tours", json={**body, "supplier_id": x["sup_b"]}, headers=x["a"]).status_code == 422  # not its organiser
    t = client.post("/safarsaz/tours", json={**body, "supplier_id": x["sup_a"], **FULL}, headers=x["a"])
    assert t.status_code == 201, t.text
    tid = t.json()["id"]
    tb = client.post("/safarsaz/tours", json={**body, "title": f"تور ب {x['s']}", "supplier_id": x["sup_b"]}, headers=x["b"]).json()["id"]

    # B cannot read, edit, add departures to, or see bookings of A's tour (and vice versa)
    assert client.get(f"/safarsaz/tours/{tid}", headers=x["b"]).status_code == 404
    assert client.put(f"/safarsaz/tours/{tid}", json={**body, "supplier_id": x["sup_b"]}, headers=x["b"]).status_code == 404
    assert client.get(f"/safarsaz/tours/{tid}/bookings", headers=x["b"]).status_code == 404
    assert all(r["id"] != tid for r in client.get("/safarsaz/tours", headers=x["b"]).json()["items"])
    assert all(r["id"] != tb for r in client.get("/safarsaz/tours", headers=x["a"]).json()["items"])
    assert client.get(f"/safarsaz/tours/{tb}/bookings", headers=x["a"]).status_code == 404

    start = datetime.now(timezone.utc) + timedelta(days=12)
    dep = {"starts_at": start.isoformat(), "ends_at": (start + timedelta(days=3)).isoformat(), "booking_deadline": (start - timedelta(days=1)).isoformat(),
           "capacity": 8, "prices": [{"room": "double", "adult": 9_000_000}]}
    assert client.post(f"/safarsaz/tours/{tid}/departures", json=dep, headers=x["b"]).status_code == 404
    assert client.post(f"/safarsaz/tours/{tid}/departures", json=dep, headers=x["a"]).status_code == 201
    # before publication: departures listed with no bookings, no figure invented
    pre = client.get(f"/safarsaz/tours/{tid}/bookings", headers=x["a"]).json()
    assert pre["departures"][0]["published"] is False and pre["departures"][0]["bookings"] == [] and pre["departures"][0]["remaining"] is None

    assert client.post(f"/safarsaz/tours/{tid}/publish", headers=x["a"]).status_code == 403  # agency cannot publish
    assert client.post(f"/safarsaz/tours/{tid}/submit", headers=x["a"]).status_code == 200
    pub = client.post(f"/safarsaz/tours/{tid}/publish", headers=x["tadmin"])
    assert pub.status_code == 200, pub.text
    product = pub.json()["published_tour_id"]

    emp = _h(client, "employee@aftab.test")
    departure = client.get(f"/tour-products/{product}", headers=emp).json()["departures"][0]
    booked = client.post(f"/tour-departures/{departure['id']}/reservations", json={"travellers": 2, "room_type": "double", "command_id": f"agtour-{x['s']}"}, headers=emp)
    assert booked.status_code == 201, booked.text

    got = client.get(f"/safarsaz/tours/{tid}/bookings", headers=x["a"])
    assert got.status_code == 200, got.text
    d = got.json()["departures"][0]
    assert d["published"] is True and d["capacity"] == 8 and d["remaining"] == 6 and d["booked_travellers"] == 2
    assert len(d["bookings"]) == 1 and d["bookings"][0]["travellers"] == 2 and d["bookings"][0]["total_amount"] == 18_000_000
    assert not {"user_id", "customer_id", "customer", "name", "email", "mobile"} & set(d["bookings"][0])  # no customer identity to the partner
    # B still sees nothing; staff see it; a customer is refused
    assert client.get(f"/safarsaz/tours/{tid}/bookings", headers=x["b"]).status_code == 404
    assert client.get(f"/safarsaz/tours/{tid}/bookings", headers=_h(client, "backoffice@aftab.test")).status_code == 200
    assert client.get(f"/safarsaz/tours/{tid}/bookings", headers=emp).status_code == 403

    # removing A's membership removes its access
    with SessionLocal() as db:
        from app import operations as om
        from sqlalchemy import delete
        db.execute(delete(om.AgencyMembership).where(om.AgencyMembership.agency_id == x["ag_a"])); db.commit()
    assert client.get(f"/safarsaz/tours/{tid}", headers=x["a"]).status_code == 403
