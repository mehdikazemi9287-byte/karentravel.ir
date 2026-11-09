"""/reservations/{id}/fulfill object-level scope (SECURITY_FOLLOWUPS).

Scope is checked before the payment gate, so an unpaid reservation answers
409 to an in-scope fulfiller and 403 to anyone outside its scope."""
import uuid

import pytest
from sqlalchemy import delete, select

from app.main import SessionLocal, User
from app.operations import Agency, AgencyMembership, SupplierMembership
from test_booking_orchestration import active_supplier, auth, login, policy


def _unpaid_reservation(client):
    supplier_id = active_supplier()
    supplier = login(client, "supplier@aftab.test")
    employee = login(client, "employee@aftab.test")
    tag = uuid.uuid4().hex[:8]
    offer = client.post("/supplier/offers", headers=auth(supplier["access_token"]), json={"supplier_id": supplier_id, "service_type": "tour", "title": f"scope-{tag}", "amount": 400_000, "available_units": 1, "valid_minutes": 60, "policy": policy(), "attributes": {}, "fulfillment_mode": "manual_supplier", "provider_key": "manual_supplier"}).json()
    checked = client.post(f"/offers/{offer['id']}/price-check", headers=auth(employee["access_token"]), json={"units": 1, "command_id": f"scope-check-{tag}"}).json()
    booked = client.post("/orchestration/bookings", headers=auth(employee["access_token"]), json={"price_check_id": checked["id"], "command_id": f"scope-book-{tag}"}).json()
    return supplier_id, booked["id"]


def _fulfil(client, session, reservation_id):
    return client.post(f"/reservations/{reservation_id}/fulfill", headers=auth(session["access_token"]), json={"command_id": f"scope-fulfil-{uuid.uuid4().hex}", "provider_reference": "ref", "document_reference": "document://scope"})


def _agency_user():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "agency@aftab.test"))
        db.expunge(user)
        return user


@pytest.fixture()
def restore_agency_memberships():
    """Tests share one database: put the seeded agency user's memberships back."""
    user = _agency_user()
    with SessionLocal() as db:
        saved = [m.agency_id for m in db.scalars(select(AgencyMembership).where(AgencyMembership.user_id == user.id))]
    yield
    with SessionLocal() as db:
        db.execute(delete(AgencyMembership).where(AgencyMembership.user_id == user.id))
        for agency_id in saved:
            db.add(AgencyMembership(tenant_id=user.tenant_id, user_id=user.id, agency_id=agency_id))
        db.commit()


def test_agency_without_membership_cannot_fulfil(client, restore_agency_memberships):
    _, reservation_id = _unpaid_reservation(client)
    agency_user = _agency_user()
    with SessionLocal() as db:
        db.execute(delete(AgencyMembership).where(AgencyMembership.user_id == agency_user.id)); db.commit()
    assert _fulfil(client, login(client, "agency@aftab.test"), reservation_id).status_code == 403


def test_agency_linked_to_the_supplier_reaches_payment_gate(client, restore_agency_memberships):
    supplier_id, reservation_id = _unpaid_reservation(client)
    agency_user = _agency_user()
    with SessionLocal() as db:
        agency = Agency(tenant_id=agency_user.tenant_id, display_name=f"scope-agency-{uuid.uuid4().hex[:6]}", status="active", supplier_id=supplier_id)
        db.add(agency); db.flush()
        db.add(AgencyMembership(tenant_id=agency_user.tenant_id, user_id=agency_user.id, agency_id=agency.id)); db.commit()
    assert _fulfil(client, login(client, "agency@aftab.test"), reservation_id).status_code == 409  # in scope, not paid


def test_agency_of_another_supplier_is_refused(client, restore_agency_memberships):
    _, reservation_id = _unpaid_reservation(client)
    other_supplier_id, _ = _unpaid_reservation(client)
    agency_user = _agency_user()
    with SessionLocal() as db:
        db.execute(delete(AgencyMembership).where(AgencyMembership.user_id == agency_user.id))
        agency = Agency(tenant_id=agency_user.tenant_id, display_name=f"scope-other-{uuid.uuid4().hex[:6]}", status="active", supplier_id=other_supplier_id)
        db.add(agency); db.flush()
        db.add(AgencyMembership(tenant_id=agency_user.tenant_id, user_id=agency_user.id, agency_id=agency.id)); db.commit()
    assert _fulfil(client, login(client, "agency@aftab.test"), reservation_id).status_code == 403


def test_supplier_only_own_and_platform_any(client):
    _, reservation_id = _unpaid_reservation(client)
    supplier_user_id = None
    with SessionLocal() as db:
        supplier_user = db.scalar(select(User).where(User.email == "supplier@aftab.test"))
        supplier_user_id, supplier_tenant = supplier_user.id, supplier_user.tenant_id
        saved = [(m.supplier_id, m.role) for m in db.scalars(select(SupplierMembership).where(SupplierMembership.user_id == supplier_user_id))]
        db.execute(delete(SupplierMembership).where(SupplierMembership.user_id == supplier_user_id)); db.commit()
    try:
        assert _fulfil(client, login(client, "supplier@aftab.test"), reservation_id).status_code == 403
    finally:
        with SessionLocal() as db:
            for sid, role in saved:
                db.add(SupplierMembership(tenant_id=supplier_tenant, user_id=supplier_user_id, supplier_id=sid, role=role))
            db.commit()
    assert _fulfil(client, login(client, "supplier@aftab.test"), reservation_id).status_code == 409
    assert _fulfil(client, login(client, "platform-admin@aftab.test"), reservation_id).status_code == 409
    assert _fulfil(client, login(client, "employee@aftab.test"), reservation_id).status_code == 403
