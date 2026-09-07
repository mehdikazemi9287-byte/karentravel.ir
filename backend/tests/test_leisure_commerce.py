import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.main import SessionLocal, User
from app.operations import PaymentIntent, PricingRule, Supplier


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def supplier(client, headers, kind="pool_sport"):
    key = f"supplier-leisure-{kind}-{uuid.uuid4().hex}"
    response = client.post("/supplier/onboarding", headers={**headers, "Idempotency-Key": key}, json={"supplier_type": kind, "display_name": f"[TEST] leisure supplier {kind}"})
    assert response.status_code == 201
    return response.json()["id"]


def make_place(client, supplier_headers, supplier_id, place_type="pool_sport"):
    payload = {"supplier_id": supplier_id, "name": f"[TEST] استخر نمونه {uuid.uuid4().hex[:6]}", "slug": f"test-place-{uuid.uuid4().hex}", "place_type": place_type, "city": "شیراز"}
    response = client.post("/supplier/places", headers=supplier_headers, json=payload)
    assert response.status_code == 201
    return response.json()


def make_product(client, supplier_headers, place_id, service_type="pool_sport", booking_mode="SESSION_BASED"):
    payload = {"service_type": service_type, "title": "[TEST] بلیت استخر", "booking_mode": booking_mode}
    response = client.post(f"/supplier/places/{place_id}/experience-products", headers=supplier_headers, json=payload)
    assert response.status_code == 201
    return response.json()


def make_ticket_type(client, supplier_headers, product_id, code="adult", price=500_000, quota=None):
    payload = {"code": code, "label": code, "price": price, "quota": quota}
    response = client.post(f"/supplier/experience-products/{product_id}/ticket-types", headers=supplier_headers, json=payload)
    assert response.status_code == 201
    return response.json()


def make_session(client, supplier_headers, product_id, capacity=2, starts_in_hours=2):
    starts_at = datetime.now(timezone.utc) + timedelta(hours=starts_in_hours)
    ends_at = starts_at + timedelta(hours=2)
    payload = {"starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(), "capacity_total": capacity}
    response = client.post(f"/supplier/experience-products/{product_id}/sessions", headers=supplier_headers, json=payload)
    assert response.status_code == 201
    return response.json()


def price_check(client, headers, session_id, selections, command_id=None, organization_id=None):
    payload = {"selections": selections, "command_id": command_id or f"leisure-pc-{uuid.uuid4().hex}"}
    if organization_id: payload["organization_id"] = organization_id
    return client.post(f"/leisure-sessions/{session_id}/price-check", headers=headers, json=payload)


def book(client, headers, price_check_id, command_id=None):
    return client.post("/orchestration/bookings", headers=headers, json={"price_check_id": price_check_id, "command_id": command_id or f"leisure-book-{uuid.uuid4().hex}"})


def full_end_to_end_booking(client, supplier_headers, customer_headers, session_id, ticket_type_id, quantity=1, organization_id=None):
    checked = price_check(client, customer_headers, session_id, [{"ticket_type_id": ticket_type_id, "quantity": quantity}], organization_id=organization_id)
    assert checked.status_code == 201, checked.text
    booked = book(client, customer_headers, checked.json()["id"])
    assert booked.status_code == 201, booked.text
    reservation_id = booked.json()["id"]
    payment = client.post(f"/reservations/{reservation_id}/payment-intents", headers={**customer_headers, "Idempotency-Key": f"leisure-pay-{uuid.uuid4().hex}"})
    assert payment.status_code == 201
    with SessionLocal() as db:
        intent = db.get(PaymentIntent, payment.json()["id"])
        intent.status = "captured"; intent.captured_amount = intent.amount
        db.commit()
    fulfilled = client.post(f"/reservations/{reservation_id}/fulfill", headers=supplier_headers, json={"command_id": f"leisure-fulfill-{uuid.uuid4().hex}", "provider_reference": "supplier-ref-leisure", "document_reference": "document://voucher/leisure"})
    assert fulfilled.status_code == 200, fulfilled.text
    return checked.json(), booked.json(), fulfilled.json()


def test_place_product_session_ticket_type_tenant_isolation_and_supplier_ownership(client):
    supplier_session = login(client, "supplier@aftab.test")
    foreign = login(client, "employee@faraz.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]))
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id)
    product = make_product(client, auth(supplier_session["access_token"]), place["id"])
    ticket_type = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"])
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"])
    assert place["status"] == "published" and product["status"] == "published" and session_row["capacity_available"] == session_row["capacity_total"]
    assert client.get(f"/places/{place['id']}", headers=auth(foreign["access_token"])).status_code == 404
    assert client.get(f"/experience-products/{product['id']}", headers=auth(foreign["access_token"])).status_code == 404
    # employee@faraz.test lacks inventory:manage entirely, so the permission gate (403) fires
    # before ownership is even checked; either denial proves a foreign tenant cannot mutate this row.
    assert client.post(f"/supplier/places/{place['id']}/experience-products", headers=auth(foreign["access_token"]), json={"service_type": "pool_sport", "title": "hijack", "booking_mode": "SESSION_BASED"}).status_code in (403, 404)
    assert client.post(f"/supplier/experience-products/{product['id']}/ticket-types", headers=auth(foreign["access_token"]), json={"code": "adult", "label": "adult", "price": 1}).status_code in (403, 404)
    detail = client.get(f"/experience-products/{product['id']}", headers=auth(supplier_session["access_token"])).json()
    assert detail["place"]["id"] == place["id"] and any(s["id"] == session_row["id"] for s in detail["sessions"]) and any(t["id"] == ticket_type["id"] for t in detail["ticket_types"])


def test_leisure_session_capacity_prevents_oversell_and_ticket_type_validation(client):
    supplier_session = login(client, "supplier@aftab.test")
    customer = login(client, "employee@aftab.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]))
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id, place_type="restaurant")
    product = make_product(client, auth(supplier_session["access_token"]), place["id"], service_type="restaurant", booking_mode="TABLE_RESERVATION")
    ticket_type = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"], code="generic", price=200_000)
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"], capacity=1)
    bad_selection = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": str(uuid.uuid4()), "quantity": 1}])
    assert bad_selection.status_code == 422
    over_capacity = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": ticket_type["id"], "quantity": 2}])
    assert over_capacity.status_code == 409
    # Two price-checks are taken against the single remaining unit before either is booked
    # (price-check is a side-effect-free quote, same as the generic /offers/{id}/price-check) —
    # this simulates two customers racing for the last slot.
    check_a = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": ticket_type["id"], "quantity": 1}])
    assert check_a.status_code == 201 and check_a.json()["amount"] == 200_000
    check_b = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": ticket_type["id"], "quantity": 1}])
    assert check_b.status_code == 201
    book_a = book(client, auth(customer["access_token"]), check_a.json()["id"])
    assert book_a.status_code == 201
    # Only one of the two quotes can ever convert to a reservation: the row-locked capacity
    # decrement inside /orchestration/bookings rejects the second one — this is the actual
    # no-oversell guarantee, not the price-check step.
    book_b = book(client, auth(customer["access_token"]), check_b.json()["id"])
    assert book_b.status_code == 409
    with SessionLocal() as db:
        from app.operations import LeisureSession
        refreshed = db.get(LeisureSession, session_row["id"])
        assert refreshed.capacity_available == 0
    # Capacity is now genuinely exhausted: a brand new price-check correctly fails fast too.
    exhausted = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": ticket_type["id"], "quantity": 1}])
    assert exhausted.status_code == 409


def test_adult_child_pricing_and_pricing_rule_organization_discount(client):
    supplier_session = login(client, "supplier@aftab.test")
    customer = login(client, "employee@aftab.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]))
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id, place_type="attraction")
    product = make_product(client, auth(supplier_session["access_token"]), place["id"], service_type="attraction", booking_mode="TIMED_ENTRY")
    adult = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"], code="adult", price=1_000_000)
    child = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"], code="child", price=400_000)
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"], capacity=10)
    mixed = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": adult["id"], "quantity": 2}, {"ticket_type_id": child["id"], "quantity": 1}])
    assert mixed.status_code == 201 and mixed.json()["amount"] == 2_400_000
    breakdown = {row["code"]: row["subtotal"] for row in mixed.json()["ticket_breakdown"]}
    assert breakdown == {"adult": 2_000_000, "child": 400_000}
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        from app.operations import Membership, Organization
        org = Organization(tenant_id=user.tenant_id, name="[TEST] سازمان نمونه اوقات فراغت")
        db.add(org); db.flush()
        db.add(Membership(tenant_id=user.tenant_id, user_id=user.id, organization_id=org.id, role="employee"))
        db.add(PricingRule(tenant_id=user.tenant_id, rule_type="organization_discount", service_type="attraction", configuration_json='{"scope": "organization", "organization_id": "%s", "discount_type": "percent", "discount_value": 10}' % org.id, status="active"))
        db.commit()
        organization_id = org.id
    without_org = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": adult["id"], "quantity": 1}])
    assert without_org.status_code == 201 and without_org.json()["amount"] == 1_000_000 and without_org.json()["applied_pricing_rule"] is None
    with_org = price_check(client, auth(customer["access_token"]), session_row["id"], [{"ticket_type_id": adult["id"], "quantity": 1}], organization_id=organization_id)
    assert with_org.status_code == 201 and with_org.json()["amount"] == 900_000 and with_org.json()["applied_pricing_rule"]["discount_type"] == "percent"
    # A foreign-tenant user can't even see this session (tenant isolation fires first, 409
    # "session not valid" — never reaching the organization-membership check at all).
    foreign = login(client, "employee@faraz.test")
    cross_tenant = price_check(client, auth(foreign["access_token"]), session_row["id"], [{"ticket_type_id": adult["id"], "quantity": 1}], organization_id=organization_id)
    assert cross_tenant.status_code == 409
    # A same-tenant user who is simply not a member of this organization is correctly denied
    # by the membership check itself (403), proving that check is real and not a no-op.
    with SessionLocal() as db:
        from app.main import User as UserModel
        outsider_user = UserModel(tenant_id=(db.scalar(select(User).where(User.email == "employee@aftab.test"))).tenant_id, email=f"leisure-outsider-{uuid.uuid4().hex}@aftab.test", name="[TEST] بدون عضویت سازمانی", role="employee")
        db.add(outsider_user); db.commit()
        outsider_email = outsider_user.email
    outsider = login(client, outsider_email)
    denied = price_check(client, auth(outsider["access_token"]), session_row["id"], [{"ticket_type_id": adult["id"], "quantity": 1}], organization_id=organization_id)
    assert denied.status_code == 403


def test_admission_ticket_issue_qr_validate_redeem_idempotent_and_lifecycle(client):
    supplier_session = login(client, "supplier@aftab.test")
    customer = login(client, "employee@aftab.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]), kind="event_hall")
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id, place_type="event_hall")
    product = make_product(client, auth(supplier_session["access_token"]), place["id"], service_type="event_hall", booking_mode="EVENT_TICKET")
    ticket_type = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"], code="generic", price=300_000)
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"], capacity=5)
    _, booked, fulfilled = full_end_to_end_booking(client, auth(supplier_session["access_token"]), auth(customer["access_token"]), session_row["id"], ticket_type["id"])
    assert fulfilled["admission_ticket"] is not None and fulfilled["admission_ticket"]["status"] == "issued"
    qr_token = fulfilled["admission_ticket"]["qr_token"]
    assert len(qr_token) >= 16 and qr_token != booked["id"] and qr_token != fulfilled["reservation"]["id"]
    listed = client.get(f"/reservations/{booked['id']}/admission-tickets", headers=auth(customer["access_token"]))
    assert listed.status_code == 200 and listed.json()["items"][0]["qr_token"] == qr_token
    pre_validate = client.get("/admission-tickets/validate", headers=auth(supplier_session["access_token"]), params={"qr_token": qr_token})
    assert pre_validate.status_code == 200 and pre_validate.json()["redeemable"] is True
    redeemed = client.post("/admission-tickets/redeem", headers=auth(supplier_session["access_token"]), json={"qr_token": qr_token})
    assert redeemed.status_code == 200 and redeemed.json()["status"] == "used" and redeemed.json()["redeemed_at"]
    post_validate = client.get("/admission-tickets/validate", headers=auth(supplier_session["access_token"]), params={"qr_token": qr_token})
    assert post_validate.status_code == 200 and post_validate.json()["redeemable"] is False
    replay = client.post("/admission-tickets/redeem", headers=auth(supplier_session["access_token"]), json={"qr_token": qr_token})
    assert replay.status_code == 409 and replay.json()["detail"]["code"] == "ALREADY_REDEEMED"
    replay_again = client.post("/admission-tickets/redeem", headers=auth(supplier_session["access_token"]), json={"qr_token": qr_token})
    assert replay_again.status_code == 409 and replay_again.json()["detail"]["code"] == "ALREADY_REDEEMED"
    unknown = client.post("/admission-tickets/redeem", headers=auth(supplier_session["access_token"]), json={"qr_token": "not-a-real-token-xxxxxxxx"})
    assert unknown.status_code == 404


def test_admission_ticket_rejects_expired_session(client):
    supplier_session = login(client, "supplier@aftab.test")
    customer = login(client, "employee@aftab.test")
    supplier_id = supplier(client, auth(supplier_session["access_token"]), kind="pool_sport")
    place = make_place(client, auth(supplier_session["access_token"]), supplier_id, place_type="pool_sport")
    product = make_product(client, auth(supplier_session["access_token"]), place["id"], service_type="pool_sport", booking_mode="SESSION_BASED")
    ticket_type = make_ticket_type(client, auth(supplier_session["access_token"]), product["id"], code="adult", price=150_000)
    session_row = make_session(client, auth(supplier_session["access_token"]), product["id"], capacity=3, starts_in_hours=1)
    _, booked, fulfilled = full_end_to_end_booking(client, auth(supplier_session["access_token"]), auth(customer["access_token"]), session_row["id"], ticket_type["id"])
    qr_token = fulfilled["admission_ticket"]["qr_token"]
    with SessionLocal() as db:
        from app.operations import LeisureSession
        row = db.get(LeisureSession, session_row["id"])
        row.ends_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    expired = client.post("/admission-tickets/redeem", headers=auth(supplier_session["access_token"]), json={"qr_token": qr_token})
    assert expired.status_code == 409 and expired.json()["detail"]["code"] == "TICKET_EXPIRED"
