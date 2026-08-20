from sqlalchemy import select

from app.main import SessionLocal, User
from app.operations import ApprovalInstanceStep, Organization, Reservation


def auth(token): return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def create_context():
    with SessionLocal() as db:
        employee = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        organization = Organization(tenant_id=employee.tenant_id, name="سازمان گردش تأیید", status="active")
        reservation = Reservation(tenant_id=employee.tenant_id, user_id=employee.id, service_type="flight", status="reserved", price_snapshot_json='{"total_amount":1000000,"currency":"IRR"}', policy_at_booking_json='{"verified":true}')
        db.add_all([organization, reservation]); db.commit()
        return organization.id, reservation.id


def test_configurable_multistep_approval_sla_escalation_and_audit(client):
    organization_id, reservation_id = create_context()
    org_admin = login(client, "org-admin@aftab.test")
    employee = login(client, "employee@aftab.test")
    backoffice = login(client, "backoffice@aftab.test")
    welfare = login(client, "welfare@aftab.test")
    finance = login(client, "finance@aftab.test")
    department = client.post(f"/organizations/{organization_id}/departments", headers=auth(org_admin["access_token"]), json={"name": "فروش", "code": "SALES"})
    cost_center = client.post(f"/organizations/{organization_id}/cost-centers", headers=auth(org_admin["access_token"]), json={"name": "سفر", "code": "TRAVEL", "budget_amount": 5_000_000})
    assert department.status_code == cost_center.status_code == 201
    template = client.post(f"/organizations/{organization_id}/approval-templates", headers=auth(org_admin["access_token"]), json={"name": "گردش کامل", "version": 1, "steps": [{"required_role": "backoffice_expert", "sla_minutes": 30}, {"required_role": "welfare_manager", "sla_minutes": 60}, {"required_role": "finance_operator", "sla_minutes": 90}, {"required_role": "organization_admin", "sla_minutes": 120}]})
    assert template.status_code == 201 and template.json()["steps"] == 4
    started = client.post(f"/reservations/{reservation_id}/approval-workflows", headers=auth(employee["access_token"]), json={"template_id": template.json()["id"], "command_id": "approval-start-full"})
    assert started.status_code == 201
    workflow_id = started.json()["id"]
    assert client.post(f"/approvals/{workflow_id}/escalate", headers=auth(org_admin["access_token"]), json={"reason": "SLA نزدیک است"}).json()["escalation_count"] == 1
    assert client.post(f"/approvals/{workflow_id}/decision", headers=auth(welfare["access_token"]), json={"decision": "approve"}).status_code == 403
    for order, actor in enumerate((backoffice, welfare, finance, org_admin), 1):
        decision = client.post(f"/approvals/{workflow_id}/decision", headers=auth(actor["access_token"]), json={"decision": "approve"})
        assert decision.status_code == 200
        assert decision.json()["step_status"] == "approved"
        assert decision.json()["status"] == ("approved" if order == 4 else "pending")
    with SessionLocal() as db:
        rows = db.scalars(select(ApprovalInstanceStep).where(ApprovalInstanceStep.workflow_id == workflow_id).order_by(ApprovalInstanceStep.step_order)).all()
        assert [row.status for row in rows] == ["approved"] * 4
        assert all(row.sla_due_at is not None and row.decided_at is not None for row in rows)


def test_rejection_requires_reason_and_stops_workflow(client):
    organization_id, reservation_id = create_context()
    org_admin = login(client, "org-admin@aftab.test")
    employee = login(client, "employee@aftab.test")
    template = client.post(f"/organizations/{organization_id}/approval-templates", headers=auth(org_admin["access_token"]), json={"name": "CEO", "version": 1, "steps": [{"required_role": "organization_admin", "sla_minutes": 30}]}).json()
    workflow = client.post(f"/reservations/{reservation_id}/approval-workflows", headers=auth(employee["access_token"]), json={"template_id": template["id"], "command_id": "approval-start-reject"}).json()
    assert client.post(f"/approvals/{workflow['id']}/decision", headers=auth(org_admin["access_token"]), json={"decision": "reject"}).status_code == 422
    rejected = client.post(f"/approvals/{workflow['id']}/decision", headers=auth(org_admin["access_token"]), json={"decision": "reject", "rejection_reason": "خارج از سیاست سفر"})
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert client.post(f"/approvals/{workflow['id']}/decision", headers=auth(org_admin["access_token"]), json={"decision": "approve"}).status_code == 409
