"""Synthetic isolated organization audit regression; never uses runtime business records."""
from uuid import uuid4
from sqlalchemy import select, delete
from app.main import SessionLocal, User, AuditEvent
from app import operations as m, enterprise_models as e

def test_membership_mutations_are_atomic_audited_and_tenant_scoped(client):
    def auth(email):
        token=client.post("/auth/dev-login",json={"email":email}).json()["access_token"]
        return {"Authorization":"Bearer "+token}
    admin=auth("tenant-admin@aftab.test");outsider=auth("employee@faraz.test")
    response=client.post("/enterprise/organizations",headers=admin,json={"name":"Mock QA audit "+uuid4().hex})
    assert response.status_code==201
    org=response.json()["id"];base="/enterprise/organizations/"+org
    with SessionLocal() as db:
        target=db.scalar(select(User).where(User.email=="employee@aftab.test")).id
        actor=db.scalar(select(User).where(User.email=="tenant-admin@aftab.test")).id
    try:
        assert [x["type"] for x in client.get(base+"/audit",headers=admin).json()]==["created"]
        assert client.post(base+"/members",headers=admin,json={"email":"employee@aftab.test"}).status_code==201
        assert client.post(base+"/members",headers=admin,json={"email":"employee@aftab.test"}).status_code==201
        assert client.post(base+"/members",headers=outsider,json={"email":"employee@aftab.test"}).status_code in (403,404)
        assert client.post(base+f"/members/{target}/remove",headers=admin).status_code==200
        assert client.post(base+f"/members/{target}/remove",headers=admin).status_code==404
        events=client.get(base+"/audit",headers=admin).json()
        assert [ev["type"] for ev in events]==["member.removed","member.added","created"]
        assert all(ev["actor"] and ev["at"] for ev in events)
        with SessionLocal() as db:
            logs=db.scalars(select(AuditEvent).where(AuditEvent.entity=="organization",AuditEvent.detail.contains(org))).all()
            assert {ev.action for ev in logs}=={"organization.created","organization.member.added","organization.member.removed"}
            assert all(ev.actor_id==actor for ev in logs)
    finally:
        with SessionLocal() as db:
            db.execute(delete(e.EnterpriseRequestEvent).where(e.EnterpriseRequestEvent.organization_id==org))
            db.execute(delete(m.EmployeeAssignment).where(m.EmployeeAssignment.organization_id==org))
            db.execute(delete(AuditEvent).where(AuditEvent.entity=="organization",AuditEvent.detail.contains(org)))
            db.execute(delete(m.Organization).where(m.Organization.id==org));db.commit()
