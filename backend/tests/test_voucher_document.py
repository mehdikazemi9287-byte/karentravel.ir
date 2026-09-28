from sqlalchemy import select

from app.main import SessionLocal, User
from tests.test_leisure_commerce import auth, login, make_place, make_product, make_session, make_ticket_type, price_check, book, supplier, full_end_to_end_booking


def test_voucher_document_contains_reference_customer_and_qr(client):
    supplier_session = login(client, "supplier@aftab.test")
    customer = login(client, "employee@aftab.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]))
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id)
    product = make_product(client, auth(supplier_session["access_token"]), place["id"])
    ticket_type = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"])
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"], capacity=3)
    _, booked, fulfilled = full_end_to_end_booking(client, auth(supplier_session["access_token"]), auth(customer["access_token"]), session_row["id"], ticket_type["id"])

    r = client.get(f"/reservations/{booked['id']}/voucher", headers=auth(customer["access_token"]))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert booked["id"] in html or (booked.get("booking_reference") or "") in html
    with SessionLocal() as db:
        current_name = db.scalar(select(User.name).where(User.email == "employee@aftab.test"))
    assert current_name in html  # whatever this seeded user's name currently is -- other tests may rename it
    qr_token = fulfilled["admission_ticket"]["qr_token"]
    assert qr_token in html
    assert "<svg" in html and "<path" in html


def test_voucher_document_denied_for_other_customers_reservation(client):
    supplier_session = login(client, "supplier@aftab.test")
    customer = login(client, "employee@aftab.test")
    other = login(client, "welfare@aftab.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]))
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id)
    product = make_product(client, auth(supplier_session["access_token"]), place["id"])
    ticket_type = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"])
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"], capacity=3)
    checked = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": ticket_type["id"], "quantity": 1}])
    booked = book(client, auth(customer["access_token"]), checked.json()["id"])
    assert booked.status_code == 201

    r = client.get(f"/reservations/{booked.json()['id']}/voucher", headers=auth(other["access_token"]))
    assert r.status_code == 404
