"""Organization panel backend: organizations, membership, current policy, real counts — with tenant and role isolation."""
from uuid import uuid4

from sqlalchemy import delete, select

from app.main import SessionLocal, User
from app.operations import EmployeeAssignment, Organization


def _login(client, email):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"email": email}).json()["access_token"]}


def test_organization_admin_flow_and_isolation(client):
    tenant_admin, org_admin, employee, outsider = (_login(client, e) for e in ("tenant-admin@aftab.test", "org-admin@aftab.test", "employee@aftab.test", "employee@faraz.test"))
    name = f"سازمان آزمون {uuid4().hex[:6]}"
    assert client.post("/enterprise/organizations", json={"name": name}, headers=org_admin).status_code == 403 and client.get("/enterprise/organizations", headers=employee).status_code == 403
    assert client.post("/enterprise/organizations", json={"name": name, "credit": 1}, headers=tenant_admin).status_code == 422
    org = client.post("/enterprise/organizations", json={"name": name}, headers=tenant_admin).json()
    assert org["members"] == 0 and client.post("/enterprise/organizations", json={"name": name}, headers=tenant_admin).status_code == 409
    base = f"/enterprise/organizations/{org['id']}"
    with SessionLocal() as db: emp_id = db.scalar(select(User.id).where(User.email == "employee@aftab.test")); admin_id = db.scalar(select(User.id).where(User.email == "org-admin@aftab.test"))
    try:
        assert client.post(base + "/members", json={"email": "org-admin@aftab.test"}, headers=org_admin).status_code == 403            # not a member yet: cannot add itself
        assert client.post(base + "/members", json={"email": "nobody@aftab.test"}, headers=tenant_admin).status_code == 404
        assert client.post(base + "/members", json={"email": "employee@faraz.test"}, headers=tenant_admin).status_code == 404         # a user of another tenant is not addable
        assert [u["email"] for u in client.post(base + "/members", json={"email": "ORG-ADMIN@aftab.test"}, headers=tenant_admin).json()] == ["org-admin@aftab.test"]
        members = client.post(base + "/members", json={"email": "employee@aftab.test"}, headers=org_admin).json()                        # the organization admin manages members from here on
        assert {u["email"] for u in members} == {"org-admin@aftab.test", "employee@aftab.test"} and len(client.post(base + "/members", json={"email": "employee@aftab.test"}, headers=org_admin).json()) == 2
        assert client.post(base + "/members", json={"email": "finance@aftab.test"}, headers=employee).status_code == 403
        assert client.get(base + "/policy", headers=employee).json() == {"version": None, "rules": None} and client.get(base + "/policy", headers=outsider).status_code == 403
        rules = {"allowed_services": ["hotel"], "approval_required": True, "approver_ids": [admin_id], "maximum_budget": 1000}
        assert client.put(base + "/policy", json={"command_id": str(uuid4()), "rules": rules}, headers=org_admin).status_code == 200
        policy = client.get(base + "/policy", headers=employee).json()
        assert policy["version"] == 1 and policy["rules"]["maximum_budget"] == 1000
        summary = client.get(base + "/summary", headers=org_admin).json()
        assert summary["members"] == 2 and summary["requests"] == {"total": 0, "by_status": {}, "by_use_case": {}, "by_policy_result": {}} and summary["linked_bookings"] == 0 and summary["credit_accounts"] == 0
        assert client.get(base + "/summary", headers=employee).status_code == 403 and client.get(base + "/summary", headers=outsider).status_code == 403
        members = client.get(base + "/members", headers=org_admin).json()
        assert {u["email"]: u["permissions"] for u in members}["employee@aftab.test"] == [] and len({u["email"]: u["permissions"] for u in members}["org-admin@aftab.test"]) == 7
        assert client.put(base + "/grants", json={"command_id": str(uuid4()), "user_id": emp_id, "permissions": ["requests.read_all"]}, headers=org_admin).status_code == 200
        assert client.get(base + "/summary", headers=employee).status_code == 200                                                          # the grant opens the organization report
        trail = client.get(base + "/audit", headers=org_admin).json()
        assert {ev["type"] for ev in trail} >= {"grant.changed"} and all(ev["actor"] for ev in trail) and client.get(base + "/audit", headers=outsider).status_code == 403
        assert client.put(base + "/grants", json={"command_id": str(uuid4()), "user_id": emp_id, "permissions": []}, headers=org_admin).status_code == 200
        assert client.get(base + "/audit", headers=employee).status_code == 403 and client.get(base + "/statement", headers=employee).status_code == 403
        assert client.get(base + "/statement", headers=org_admin).json() == {"linked_bookings": 0, "items": [], "totals": []}
        assert client.get(base + "/credit", headers=org_admin).json() == [] and client.get(base + "/credit", headers=tenant_admin).json() == [] and client.get(base + "/credit", headers=outsider).status_code in (403, 404)
        events = client.get("/admin/audit-events", headers=tenant_admin)
        assert events.status_code == 200 and isinstance(events.json(), list) and client.get("/admin/audit-events", headers=employee).status_code == 403 and client.get("/admin/audit-events", headers=org_admin).status_code in (200, 403)
        assert org["id"] in {o["id"] for o in client.get("/enterprise/context", headers=employee).json()["organizations"]}
        assert client.post(f"{base}/members/{admin_id}/remove", headers=org_admin).status_code == 409                                     # nobody removes itself
        assert client.post(f"{base}/members/{emp_id}/remove", headers=employee).status_code == 403
        assert [u["email"] for u in client.post(f"{base}/members/{emp_id}/remove", headers=org_admin).json()] == ["org-admin@aftab.test"]
        assert client.get(base + "/policy", headers=employee).status_code == 403                                                          # membership ended, access ended
        assert client.get(f"/enterprise/organizations/{uuid4()}/summary", headers=tenant_admin).status_code == 403
    finally:
        with SessionLocal() as db:
            from app import enterprise_models as e
            for model in (e.EnterpriseRequestEvent, e.EnterprisePolicy, e.EnterpriseGrant): db.execute(delete(model).where(model.organization_id == org["id"]))
            db.execute(delete(EmployeeAssignment).where(EmployeeAssignment.organization_id == org["id"])); db.execute(delete(Organization).where(Organization.id == org["id"])); db.commit()
