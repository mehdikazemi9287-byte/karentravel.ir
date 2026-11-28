"""Staff desks (sales desk, train desk, partner requests, Safarsaz staff side) are for the group's own staff only (QA 2026-11-28).
Legacy organization roles (manager, welfare_manager, organization_admin) hold `reservation:manage` for their own bookings;
that never opens a desk. The desks check `desk:manage` (security.DESK_PERMISSION).

Test rows: one synthetic `manager` user is created when missing; nothing is deleted.
"""
import uuid

import pytest
from sqlalchemy import select

from app.main import SessionLocal, User
from app.security import DESK_PERMISSION, ROLE_PERMISSIONS, role_has_permission

MANAGER_EMAIL = "legacy-manager-desk-test@aftab.test"
ORG_ROLES = ("manager", "welfare_manager", "organization_admin")
READS = ("/sales-desk/cases", "/train-desk/requests", "/partner-desk/requests", "/safarsaz/tours")


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _ensure_manager():
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == MANAGER_EMAIL)) is None:
            tenant_id = db.scalar(select(User.tenant_id).where(User.email == "backoffice@aftab.test"))
            db.add(User(tenant_id=tenant_id, email=MANAGER_EMAIL, name="مدیر سازمان آزمون", role="manager"))
            db.commit()
    return MANAGER_EMAIL


def test_desk_permission_is_staff_only():
    holders = {r for r in ROLE_PERMISSIONS if role_has_permission(r, DESK_PERMISSION)}
    assert holders == {"backoffice_expert", "tenant_admin", "platform_admin"}
    for role in (*ORG_ROLES, "customer", "employee", "supplier", "agency_partner", "finance_operator"):
        assert not role_has_permission(role, DESK_PERMISSION), role


@pytest.mark.parametrize("path", READS)
def test_organization_managers_get_403_on_staff_desks(client, path):
    for email in (_ensure_manager(), "welfare@aftab.test", "org-admin@aftab.test"):
        r = client.get(path, headers=_h(client, email))
        assert r.status_code == 403, (email, path, r.status_code)


@pytest.mark.parametrize("path", READS)
def test_staff_get_200_on_staff_desks(client, path):
    for email in ("backoffice@aftab.test", "tenant-admin@aftab.test"):
        r = client.get(path, headers=_h(client, email))
        assert r.status_code == 200, (email, path, r.status_code, r.text)


def test_organization_manager_cannot_create_a_sales_case(client):
    body = {"customer_name": "مشتری آزمون", "mobile": "09123456789", "channel": "whatsapp", "trip": f"آزمون {uuid.uuid4().hex[:6]}", "travellers": 1}
    for email in (_ensure_manager(), "welfare@aftab.test", "org-admin@aftab.test"):
        assert client.post("/sales-desk/cases", json=body, headers=_h(client, email)).status_code == 403, email
    assert client.post("/sales-desk/cases", json=body, headers=_h(client, "backoffice@aftab.test")).status_code == 201


def test_commerce_panel_organization_list_endpoint(client):
    """/admin/commerce «وصل به گروه» lists organizations from /enterprise/organizations (a list of {id, name, status});
    /organizations does not exist (QA 2026-11-28)."""
    h = _h(client, "tenant-admin@aftab.test")
    name = f"سازمان آزمون گروه قیمت {uuid.uuid4().hex[:6]}"
    assert client.post("/enterprise/organizations", json={"name": name}, headers=h).status_code == 201
    r = client.get("/enterprise/organizations", headers=h)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and all({"id", "name", "status"} <= set(o) for o in rows)
    assert name in [o["name"] for o in rows]
    assert client.get("/organizations", headers=h).status_code == 404
