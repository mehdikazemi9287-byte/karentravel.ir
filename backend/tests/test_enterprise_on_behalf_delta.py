"""D3 (QA 1405-08-18): booking on behalf of another member of the same organization (`requests.on_behalf`)."""
import uuid

from sqlalchemy import func, select

from app.enterprise_models import EnterpriseOnBehalfBooking, EnterpriseRequestEvent
from app.main import AuditEvent, SessionLocal, User
from app.operations import EmployeeAssignment, Organization
from test_checkout_reviews_zarinpal import auth, login, reservation_fixture


def cmd(**data):
    return {"command_id": str(uuid.uuid4()), **data}


def _org(client, *, max_budget=5_000_000, members=("employee@aftab.test", "welfare@aftab.test", "org-admin@aftab.test")):
    with SessionLocal() as db:
        users = {u.email: u for u in db.scalars(select(User)).all()}
        org = Organization(tenant_id=users["employee@aftab.test"].tenant_id, name="On-behalf QA " + uuid.uuid4().hex[:6], status="active"); db.add(org); db.flush()
        db.add_all([EmployeeAssignment(tenant_id=org.tenant_id, user_id=users[e].id, organization_id=org.id) for e in members]); db.commit()
        oid, ids = org.id, {e: u.id for e, u in users.items()}
    admin = auth(login(client, "org-admin@aftab.test"))
    r = client.put(f"/enterprise/organizations/{oid}/policy", headers=admin, json=cmd(rules={"allowed_services": ["hotel"], "approval_required": True, "approver_ids": [ids["org-admin@aftab.test"]], "maximum_budget": max_budget}))
    assert r.status_code == 200, r.text
    return oid, ids, admin


def test_on_behalf_requires_permission_same_org_member_and_is_audited(client):
    oid, ids, admin = _org(client)
    officer, reservation, _, _ = reservation_fixture(client, uuid.uuid4().hex)  # reservation owned by employee@aftab.test
    base = f"/enterprise/organizations/{oid}/on-behalf-bookings"
    body = cmd(reservation_id=reservation["id"], beneficiary_user_id=ids["welfare@aftab.test"])
    assert client.post(base, headers=auth(officer), json=body).status_code == 403  # no requests.on_behalf yet
    grant = client.put(f"/enterprise/organizations/{oid}/grants", headers=admin, json=cmd(user_id=ids["employee@aftab.test"], permissions=["requests.on_behalf"]))
    assert grant.status_code == 200, grant.text
    # beneficiary must be a member of the same organization (same tenant non-member, other tenant user, self)
    for uid, code in [(ids["backoffice@aftab.test"], 422), (ids["employee@faraz.test"], 422), (ids["employee@aftab.test"], 422)]:
        assert client.post(base, headers=auth(officer), json=cmd(reservation_id=reservation["id"], beneficiary_user_id=uid)).status_code == code
    # another user's reservation cannot be designated
    welfare = auth(login(client, "welfare@aftab.test"))
    assert client.post(base, headers=welfare, json=cmd(reservation_id=reservation["id"], beneficiary_user_id=ids["employee@aftab.test"])).status_code == 403
    created = client.post(base, headers=auth(officer), json=body)
    assert created.status_code == 201, created.text
    out = created.json()
    assert out["actor_id"] == ids["employee@aftab.test"] and out["beneficiary_user_id"] == ids["welfare@aftab.test"] and out["traveller_id"]
    assert client.post(base, headers=auth(officer), json=body).json() == out  # idempotent replay
    assert client.post(base, headers=auth(officer), json=cmd(reservation_id=reservation["id"], beneficiary_user_id=ids["org-admin@aftab.test"])).status_code == 409
    # the beneficiary appears as a selectable traveller in the officer's account (identity still to be filled)
    assert any(t["id"] == out["traveller_id"] for t in client.get("/me/travellers", headers=auth(officer)).json())
    # visibility: officer/admin see it, the beneficiary sees their own, an outsider org member cannot read the org list
    assert [r["id"] for r in client.get(base, headers=welfare).json()] == [out["id"]]
    assert out["id"] in [r["id"] for r in client.get(base, headers=admin).json()]
    assert client.get(base, headers=auth(login(client, "employee@faraz.test"))).status_code == 403
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(EnterpriseOnBehalfBooking).where(EnterpriseOnBehalfBooking.reservation_id == reservation["id"])) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "organization.booking.on_behalf", AuditEvent.detail.contains(reservation["id"]))) == 1
        assert db.scalar(select(func.count()).select_from(EnterpriseRequestEvent).where(EnterpriseRequestEvent.organization_id == oid, EnterpriseRequestEvent.event_type == "booking.on_behalf")) == 1


def test_on_behalf_follows_org_policy(client):
    oid, ids, admin = _org(client, max_budget=1_000_000)
    officer, reservation, _, _ = reservation_fixture(client, uuid.uuid4().hex)  # hotel, 2,000,000 IRR
    r = client.post(f"/enterprise/organizations/{oid}/on-behalf-bookings", headers=admin, json=cmd(reservation_id=reservation["id"], beneficiary_user_id=ids["welfare@aftab.test"]))
    assert r.status_code == 404  # org admin may book on behalf, but only their own reservation
    client.put(f"/enterprise/organizations/{oid}/grants", headers=admin, json=cmd(user_id=ids["employee@aftab.test"], permissions=["requests.on_behalf"]))
    r = client.post(f"/enterprise/organizations/{oid}/on-behalf-bookings", headers=auth(officer), json=cmd(reservation_id=reservation["id"], beneficiary_user_id=ids["welfare@aftab.test"]))
    assert r.status_code == 409 and "سقف" in r.json()["detail"]
