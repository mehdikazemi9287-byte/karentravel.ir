from datetime import datetime, timedelta, timezone

from app.main import SessionLocal
from app.operations import LeisureSession, Reservation, sweep_expired_reservations
from tests.test_leisure_commerce import auth, login, make_place, make_product, make_session, make_ticket_type, price_check, book, supplier


def test_sweep_releases_leisure_session_capacity(client):
    supplier_session = login(client, "supplier@aftab.test")
    customer = login(client, "employee@aftab.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]))
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id)
    product = make_product(client, auth(supplier_session["access_token"]), place["id"])
    ticket_type = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"])
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"], capacity=3)

    checked = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": ticket_type["id"], "quantity": 1}])
    assert checked.status_code == 201, checked.text
    booked = book(client, auth(customer["access_token"]), checked.json()["id"])
    assert booked.status_code == 201, booked.text
    reservation_id = booked.json()["id"]

    with SessionLocal() as db:
        session_after_book = db.get(LeisureSession, session_row["id"])
        assert session_after_book.capacity_available == 2  # 3 - 1 held

        reservation = db.get(Reservation, reservation_id)
        reservation.updated_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        db.commit()

        expired = sweep_expired_reservations(db, now=datetime.now(timezone.utc))
        assert expired == [reservation_id]

        session_after_sweep = db.get(LeisureSession, session_row["id"])
        assert session_after_sweep.capacity_available == 3  # released back


def test_sweep_leisure_release_is_idempotent(client):
    supplier_session = login(client, "supplier@aftab.test")
    customer = login(client, "employee@aftab.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]))
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id)
    product = make_product(client, auth(supplier_session["access_token"]), place["id"])
    ticket_type = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"])
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"], capacity=3)

    checked = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": ticket_type["id"], "quantity": 2}])
    booked = book(client, auth(customer["access_token"]), checked.json()["id"])
    assert booked.status_code == 201, booked.text
    reservation_id = booked.json()["id"]

    with SessionLocal() as db:
        reservation = db.get(Reservation, reservation_id)
        reservation.updated_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        db.commit()

        sweep_expired_reservations(db, now=datetime.now(timezone.utc))
        sweep_expired_reservations(db, now=datetime.now(timezone.utc))

        session_after = db.get(LeisureSession, session_row["id"])
        assert session_after.capacity_available == 3  # credited exactly once (3 - 2 + 2), not double
