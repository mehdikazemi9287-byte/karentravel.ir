from test_checkout_reviews_zarinpal import hotel_terms
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.main import SessionLocal, User
from app.operations import Offer, PriceCheck, Reservation, Supplier, SupplierMembership, sweep_expired_reservations


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def _policy():
    return {"verified": True, "source": "reaper-test", "verified_at": datetime.now(timezone.utc).isoformat(), "cancellation": {"refundable": True, "penalty_amount": 100_000}}


def _reserve_one_hotel_offer(client):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "supplier@aftab.test"))
        supplier = Supplier(tenant_id=user.tenant_id, supplier_type="travel", display_name="تأمین‌کننده تست انقضا", status="active")
        db.add(supplier); db.flush()
        db.add(SupplierMembership(tenant_id=user.tenant_id, user_id=user.id, supplier_id=supplier.id, role="owner"))
        db.commit()
        supplier_id = supplier.id

    supplier_session = login(client, "supplier@aftab.test")
    employee = login(client, "employee@aftab.test")
    offer_response = client.post("/supplier/offers", headers=auth(supplier_session["access_token"]), json={
        "supplier_id": supplier_id, "service_type": "hotel", "title": "offer-reaper", "amount": 1_000_000,
        "available_units": 3, "valid_minutes": 120, "policy": _policy(),
        "attributes": {"city": "Shiraz", **hotel_terms()[0]}, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier",
    })
    assert offer_response.status_code == 201
    offer_id = offer_response.json()["id"]

    unique = uuid.uuid4().hex[:8]
    checked = client.post(f"/offers/{offer_id}/price-check", headers=auth(employee["access_token"]), json={"hotel_stay": hotel_terms()[1], "units": 1, "command_id": f"price-check-reaper-{unique}"})
    assert checked.status_code == 201
    booking = client.post("/orchestration/bookings", headers=auth(employee["access_token"]), json={"price_check_id": checked.json()["id"], "command_id": f"booking-command-reaper-{unique}"})
    assert booking.status_code == 201
    return offer_id, booking.json()["id"]


def test_sweep_expires_stale_reservation_and_releases_offer_units(client):
    offer_id, reservation_id = _reserve_one_hotel_offer(client)

    with SessionLocal() as db:
        offer = db.get(Offer, offer_id)
        assert offer.available_units == 2  # 3 - 1 held by the reservation

        reservation = db.get(Reservation, reservation_id)
        assert reservation.status == "reserved"
        reservation.updated_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        db.commit()

        expired = sweep_expired_reservations(db, now=datetime.now(timezone.utc))
        assert expired == [reservation_id]

        db.refresh(reservation)
        assert reservation.status == "expired"
        offer = db.get(Offer, offer_id)
        assert offer.available_units == 3  # released back


def test_sweep_ignores_recent_reservations(client):
    offer_id, reservation_id = _reserve_one_hotel_offer(client)
    with SessionLocal() as db:
        expired = sweep_expired_reservations(db, now=datetime.now(timezone.utc))
        assert reservation_id not in expired
        offer = db.get(Offer, offer_id)
        assert offer.available_units == 2  # still held, not released early


def test_sweep_is_idempotent_no_double_credit(client):
    offer_id, reservation_id = _reserve_one_hotel_offer(client)
    with SessionLocal() as db:
        reservation = db.get(Reservation, reservation_id)
        reservation.updated_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        db.commit()

        sweep_expired_reservations(db, now=datetime.now(timezone.utc))
        sweep_expired_reservations(db, now=datetime.now(timezone.utc))

        offer = db.get(Offer, offer_id)
        assert offer.available_units == 3  # credited exactly once, not twice
