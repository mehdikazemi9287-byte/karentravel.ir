"""Launch V1 item 8.3 (owner decision 2026-11-24): everyone is a customer; organization authority comes from membership +
enterprise_grants, always scoped by tenant and organization. Case from the plan: one person who is a customer, an employee of
organization A and a manager of organization B."""
import json
from uuid import uuid4

from sqlalchemy import select

from app.enterprise_models import EnterpriseGrant
from app.main import SessionLocal, User
from app.operations import EmployeeAssignment, Organization


def _login(client, email):
    r = client.post('/auth/dev-login', json={'email': email})
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['access_token']}


def _setup():
    tag = uuid4().hex[:8]
    with SessionLocal() as db:
        aftab = db.scalar(select(User).where(User.email == 'employee@aftab.test')).tenant_id
        faraz = db.scalar(select(User).where(User.email == 'employee@faraz.test')).tenant_id
        person = User(tenant_id=aftab, email=f'dual-{tag}@aftab.test', name='کاربر دو زمینه', role='customer')
        db.add(person); db.flush()
        org_a = Organization(tenant_id=aftab, name=f'سازمان الف {tag}', status='active')
        org_b = Organization(tenant_id=aftab, name=f'سازمان ب {tag}', status='active')
        org_x = Organization(tenant_id=faraz, name=f'سازمان مستأجر دیگر {tag}', status='active')
        db.add_all([org_a, org_b, org_x]); db.flush()
        db.add_all([EmployeeAssignment(tenant_id=aftab, user_id=person.id, organization_id=org_a.id),
                    EmployeeAssignment(tenant_id=aftab, user_id=person.id, organization_id=org_b.id),
                    EnterpriseGrant(tenant_id=aftab, organization_id=org_b.id, user_id=person.id,
                                    permissions_json=json.dumps(['requests.approve', 'requests.read_all', 'roles.manage']))])
        db.commit()
        return person.email, org_a.id, org_b.id, org_x.id


def test_customer_employee_of_a_and_manager_of_b(client):
    email, org_a, org_b, org_x = _setup()
    h = _login(client, email)
    with SessionLocal() as db:
        assert db.scalar(select(User.role).where(User.email == email)) == 'customer'

    # Personal purchase: a customer passes the reservation:create guard (404/422 is about the fake unit, never 403).
    assert client.post(f'/vacation-units/{uuid4()}/reservations', headers=h, json={}).status_code != 403
    assert client.post(f'/vacation-units/{uuid4()}/reservations', headers=_login(client, 'supplier@aftab.test'), json={}).status_code == 403
    assert client.get('/me/reservations', headers=h).status_code == 200

    # Context lists exactly the two organizations with their own permissions.
    ctx = {o['id']: o['permissions'] for o in client.get('/enterprise/context', headers=h).json()['organizations']}
    assert ctx == {org_a: [], org_b: ['requests.approve', 'requests.read_all', 'roles.manage']}

    # Organization A as an employee: member pages open.
    assert client.get(f'/enterprise/organizations/{org_a}/policy', headers=h).status_code == 200
    assert client.get(f'/enterprise/requests?org={org_a}', headers=h).status_code == 200

    # Organization B as a manager: records, structure, passengers, financial context.
    assert client.get(f'/enterprise/organizations/{org_b}/summary', headers=h).status_code == 200
    assert client.get(f'/enterprise/organizations/{org_b}/members', headers=h).status_code == 200
    r = client.post(f'/organizations/{org_b}/departments', headers=h, json={'name': 'فروش', 'code': 'SALES'})
    assert r.status_code == 201, r.text
    assert client.post(f'/organizations/{org_b}/cost-centers', headers=h, json={'name': 'سفر', 'code': 'TRAVEL', 'budget_amount': 1000}).status_code == 201
    assert client.get(f'/scopes/organization/{org_b}/passengers', headers=h).status_code == 200
    assert client.get(f'/ecosystem/organizations/{org_b}/financial-links', headers=h).status_code == 200
    overview = client.get('/organization/overview', headers=h)
    assert overview.status_code == 200
    assert [o['id'] for o in overview.json()['organizations']] == [org_b]                  # never organization A or others
    assert {d['organization_id'] for d in overview.json()['departments']} == {org_b}

    # Organization A manager pages are denied (membership without a grant).
    assert client.get(f'/enterprise/organizations/{org_a}/summary', headers=h).status_code == 403
    assert client.get(f'/enterprise/organizations/{org_a}/members', headers=h).status_code == 403
    assert client.post(f'/organizations/{org_a}/departments', headers=h, json={'name': 'فروش', 'code': 'SALES'}).status_code == 403
    assert client.get(f'/scopes/organization/{org_a}/passengers', headers=h).status_code == 404
    assert client.get(f'/ecosystem/organizations/{org_a}/financial-links', headers=h).status_code == 403
    assert client.put(f'/enterprise/organizations/{org_a}/grants', headers=h,
                      json={'command_id': 'grant-' + uuid4().hex, 'user_id': 1, 'permissions': ['roles.manage']}).status_code == 403

    # Cross-tenant: an organization of another tenant does not exist for this person.
    assert client.post(f'/organizations/{org_x}/departments', headers=h, json={'name': 'فروش', 'code': 'SALES'}).status_code == 404
    assert client.get(f'/enterprise/organizations/{org_x}/summary', headers=h).status_code == 403
    assert client.get(f'/scopes/organization/{org_x}/passengers', headers=h).status_code == 404
    # ... and a user of the other tenant cannot reach organization B.
    other = _login(client, 'employee@faraz.test')
    assert client.post(f'/organizations/{org_b}/departments', headers=other, json={'name': 'فروش', 'code': 'SALES'}).status_code == 404
    assert client.get('/organization/overview', headers=other).status_code == 403


def test_plain_customer_and_tenant_staff(client):
    _, org_a, org_b, _ = _setup()
    with SessionLocal() as db:
        tenant = db.scalar(select(User).where(User.email == 'employee@aftab.test')).tenant_id
        plain = User(tenant_id=tenant, email=f'plain-{uuid4().hex[:8]}@aftab.test', name='مشتری عادی', role='customer'); db.add(plain); db.commit(); plain_email = plain.email
    h = _login(client, plain_email)
    assert client.get('/enterprise/context', headers=h).json()['organizations'] == []
    assert client.get('/organization/overview', headers=h).status_code == 403
    assert client.post(f'/organizations/{org_b}/departments', headers=h, json={'name': 'فروش', 'code': 'SALES'}).status_code == 404
    # Tenant staff still manage every organization of their own tenant.
    staff = _login(client, 'tenant-admin@aftab.test')
    assert client.post(f'/organizations/{org_a}/departments', headers=staff, json={'name': 'مالی', 'code': 'FIN'}).status_code == 201
    ids = [o['id'] for o in client.get('/organization/overview', headers=staff).json()['organizations']]
    assert org_a in ids and org_b in ids


def test_legacy_org_admin_role_no_longer_has_tenant_wide_user_admin(client):
    # organization_admin used to carry member:manage (tenant-wide user list / role change); organization authority is per organization now.
    h = _login(client, 'org-admin@aftab.test')
    assert client.get('/admin/users', headers=h).status_code == 403
    assert client.get('/admin/users', headers=_login(client, 'tenant-admin@aftab.test')).status_code == 200
