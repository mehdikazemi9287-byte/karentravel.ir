"""Flight+Hotel combined engine: real dual price-check, transparent package total,
independent expiry, availability recheck, partial-failure rollback, idempotency,
tenant isolation. Independent flight/hotel search is untouched (regression)."""
import uuid
import json
from test_checkout_reviews_zarinpal import hotel_terms
from datetime import datetime, timedelta, timezone

from app.main import SessionLocal
from app import operations as om


def login(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _offer(tenant_id, service_type, amount, units=5, minutes=30, supplier_id=None):
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, tenant_id)
        if supplier_id is None:
            sup = om.Supplier(tenant_id=tenant_id, supplier_type=service_type, display_name=f"S-{service_type}", status="active")
            db.add(sup); db.flush(); supplier_id = sup.id
        o = om.Offer(tenant_id=tenant_id, supplier_id=supplier_id, service_type=service_type,
                     title=f"{service_type} test", amount=amount, currency="IRR", available_units=units,
                     status="active", attributes_json=json.dumps(hotel_terms()[0] if service_type == "hotel" else {}), policy_json="{}",
                     valid_until=datetime.now(timezone.utc) + timedelta(minutes=minutes))
        db.add(o); db.commit()
        return o.id


def _quote(client, headers, f_id, h_id, **kw):
    stay = hotel_terms()[1]; stay["rooms"] *= kw.get("hotel_units", 1)
    body = {"hotel_stay": stay, "flight_offer_id": f_id, "hotel_offer_id": h_id, "command_id": f"q-{uuid.uuid4().hex[:16]}", **kw}
    return client.post("/combined/flight-hotel/quote", headers=headers, json=body)


def test_quote_transparent_sum_no_discount(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 3_000_000); h = _offer(1, "hotel", 5_000_000)
    r = _quote(client, me, f, h)
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["legs"]["flight"]["amount"] == 3_000_000
    assert q["legs"]["hotel"]["amount"] == 5_000_000
    assert q["package_total"] == 8_000_000            # exact sum, no synthetic discount
    assert q["bookable"] is True


def test_quote_wrong_service_type_rejected(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 1000); t = _offer(1, "tour", 1000)
    assert _quote(client, me, f, t).status_code == 422


def test_quote_leg_unavailable_no_partial(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 1000); h = _offer(1, "hotel", 1000, units=0)  # hotel sold out
    r = _quote(client, me, f, h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "LEG_UNAVAILABLE"
    # flight price-check must NOT have been persisted (all-or-nothing quote)
    with SessionLocal() as db:
        assert db.query(om.PriceCheck).filter(om.PriceCheck.offer_id == f).count() == 0


def test_quote_package_price_changed(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 2000); h = _offer(1, "hotel", 3000)
    r = _quote(client, me, f, h, expected_package_total=9999)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "PACKAGE_PRICE_CHANGED" and d["new_total"] == 5000 and d["delta"] == 5000 - 9999


def test_independent_expiry_is_the_min(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 1000, minutes=3)     # binding leg
    h = _offer(1, "hotel", 1000, minutes=30)
    q = _quote(client, me, f, h).json()
    fexp = datetime.fromisoformat(q["legs"]["flight"]["expires_at"])
    hexp = datetime.fromisoformat(q["legs"]["hotel"]["expires_at"])
    qexp = datetime.fromisoformat(q["expires_at"])
    assert qexp == min(fexp, hexp) == fexp        # flight (3 min) binds


def test_book_happy_creates_package_reservation(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 3_000_000); h = _offer(1, "hotel", 5_000_000)
    q = _quote(client, me, f, h).json()
    b = client.post(f"/combined/flight-hotel/{q['id']}/book", headers=me, json={"command_id": f"b-{uuid.uuid4().hex[:16]}"})
    assert b.status_code == 201, b.text
    body = b.json()
    assert body["package_total"] == 8_000_000
    with SessionLocal() as db:
        res = db.get(om.Reservation, body["id"])
        assert res.service_type == "package" and res.status == "reserved"
        items = db.query(om.BookingItem).filter(om.BookingItem.reservation_id == res.id).all()
        assert {i.item_type for i in items} == {"flight", "hotel"}
        assert db.get(om.Offer, f).available_units == 4      # 5 - 1
        assert db.get(om.Offer, h).available_units == 4
        cq = db.get(om.CombinedQuote, q["id"])
        assert cq.status == "consumed" and cq.reservation_id == res.id


def test_book_idempotent(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 1000); h = _offer(1, "hotel", 1000)
    q = _quote(client, me, f, h).json()
    cmd = f"b-{uuid.uuid4().hex[:16]}"
    a = client.post(f"/combined/flight-hotel/{q['id']}/book", headers=me, json={"command_id": cmd})
    b = client.post(f"/combined/flight-hotel/{q['id']}/book", headers=me, json={"command_id": cmd})
    assert a.status_code == 201 and b.status_code == 201 and a.json()["id"] == b.json()["id"]
    with SessionLocal() as db:
        assert db.get(om.Offer, f).available_units == 4   # decremented once only


def test_book_rolls_back_when_hotel_sells_out_after_quote(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 1000, units=3); h = _offer(1, "hotel", 1000, units=3)
    q = _quote(client, me, f, h).json()
    with SessionLocal() as db:      # hotel sells out between quote and book
        from app.database import set_tenant_context
        set_tenant_context(db, 1)
        db.get(om.Offer, h).available_units = 0
        db.commit()
    b = client.post(f"/combined/flight-hotel/{q['id']}/book", headers=me, json={"command_id": f"b-{uuid.uuid4().hex[:16]}"})
    assert b.status_code == 409 and b.json()["detail"]["code"] == "LEG_UNAVAILABLE"
    with SessionLocal() as db:
        assert db.get(om.Offer, f).available_units == 3   # flight NOT decremented -- full rollback
        cq = db.get(om.CombinedQuote, q["id"])
        assert cq.status != "consumed" and cq.reservation_id is None


def test_book_expired_quote_rejected(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 1000); h = _offer(1, "hotel", 1000)
    q = _quote(client, me, f, h).json()
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, 1)
        cq = db.get(om.CombinedQuote, q["id"])
        cq.flight_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        cq.expires_at = cq.flight_expires_at
        db.commit()
    b = client.post(f"/combined/flight-hotel/{q['id']}/book", headers=me, json={"command_id": f"b-{uuid.uuid4().hex[:16]}"})
    assert b.status_code == 409 and b.json()["detail"]["code"] == "QUOTE_EXPIRED"


def test_release_quote(client):
    me = login(client, "employee@aftab.test")
    f = _offer(1, "flight", 1000); h = _offer(1, "hotel", 1000)
    q = _quote(client, me, f, h).json()
    r = client.post(f"/combined/flight-hotel/{q['id']}/release", headers=me)
    assert r.status_code == 200 and r.json()["stored_status"] == "released"
    b = client.post(f"/combined/flight-hotel/{q['id']}/book", headers=me, json={"command_id": f"b-{uuid.uuid4().hex[:16]}"})
    assert b.status_code == 409


def test_tenant_isolation(client):
    me = login(client, "employee@aftab.test")
    faraz = login(client, "employee@faraz.test")
    f = _offer(1, "flight", 1000); h = _offer(1, "hotel", 1000)
    q = _quote(client, me, f, h).json()
    assert client.get(f"/combined/flight-hotel/{q['id']}", headers=faraz).status_code == 404
    assert client.get("/me/combined-quotes", headers=faraz).json() == []


def test_independent_search_regression(client):
    """The combined engine must not disturb single-vertical flight/hotel search."""
    me = login(client, "employee@aftab.test")
    for v in ("flight", "hotel"):
        r = client.post("/search/v2", headers=me, json={"verticals": [v], "destination": "تهران", "page": 1, "page_size": 5})
        assert r.status_code == 200
