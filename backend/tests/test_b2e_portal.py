"""B2E: /me/approval-workflows — owner-scoped, tenant-scoped, auth-required."""
import uuid

from app.main import SessionLocal
from app import operations as om


def login(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _reservation_with_workflow(tenant_id, user_id, status="pending"):
    with SessionLocal() as db:
        from app.database import set_tenant_context
        set_tenant_context(db, tenant_id)
        res = om.Reservation(tenant_id=tenant_id, user_id=user_id, service_type="hotel",
                             status="reserved", booking_reference=f"KS-{uuid.uuid4().hex[:8].upper()}",
                             price_snapshot_json="{}", policy_at_booking_json="{}", current_policy_json="{}")
        db.add(res); db.flush()
        wf = om.ApprovalWorkflow(tenant_id=tenant_id, reservation_id=res.id, status=status, current_step_order=1)
        db.add(wf); db.commit()
        return res.id, wf.id


def test_approval_workflows_owner_scoped(client):
    me = login(client, "employee@aftab.test")           # user 1 tenant 1
    rid, wid = _reservation_with_workflow(1, 1)
    rows = client.get("/me/approval-workflows", headers=me)
    assert rows.status_code == 200
    assert any(w["id"] == wid and w["reservation_id"] == rid and w["status"] == "pending" for w in rows.json())


def test_approval_workflows_not_visible_to_other_user(client):
    _reservation_with_workflow(1, 1)                     # owned by user 1
    other = login(client, "welfare@aftab.test")          # user 2, same tenant, no reservations
    assert client.get("/me/approval-workflows", headers=other).json() == []


def test_approval_workflows_cross_tenant(client):
    _reservation_with_workflow(1, 1)
    faraz = login(client, "employee@faraz.test")         # tenant 2
    assert client.get("/me/approval-workflows", headers=faraz).json() == []


def test_approval_workflows_requires_auth(client):
    assert client.get("/me/approval-workflows").status_code == 401
