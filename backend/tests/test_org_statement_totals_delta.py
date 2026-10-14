"""Synthetic isolated fixtures: statement totals must never depend on the display limit."""
from uuid import uuid4
from sqlalchemy import select, delete
from app.main import SessionLocal, User
from app import operations as m, enterprise_models as e


def test_statement_totals_cover_all_invoices_and_exclude_other_organizations(client, request):
    token = client.post("/auth/dev-login", json={"email": "tenant-admin@aftab.test"}).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    suffix = uuid4().hex
    org = client.post("/enterprise/organizations", headers=headers, json={"name": "Mock QA totals " + suffix}).json()["id"]
    other_org = client.post("/enterprise/organizations", headers=headers, json={"name": "Mock QA excluded " + suffix}).json()["id"]
    reservation_ids = []
    def cleanup():
        with SessionLocal() as db:
            db.execute(delete(m.Invoice).where(m.Invoice.reservation_id.in_(reservation_ids)))
            db.execute(delete(e.EnterpriseBookingLink).where(e.EnterpriseBookingLink.reservation_id.in_(reservation_ids)))
            db.execute(delete(m.Reservation).where(m.Reservation.id.in_(reservation_ids)))
            db.execute(delete(e.EnterpriseRequest).where(e.EnterpriseRequest.organization_id.in_([org, other_org])))
            db.execute(delete(e.EnterpriseRequestEvent).where(e.EnterpriseRequestEvent.organization_id.in_([org, other_org])))
            db.execute(delete(m.Organization).where(m.Organization.id.in_([org, other_org])))
            db.commit()
    request.addfinalizer(cleanup)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        requests = []
        for organization in (org, other_org):
            req = e.EnterpriseRequest(tenant_id=user.tenant_id, organization_id=organization, requester_id=user.id,
                                      use_case="hotel", title="Mock QA totals", status="approved", requirements_json="{}",
                                      policy_snapshot_json="{}", policy_result="allowed")
            db.add(req); db.flush(); requests.append(req)
        for index in range(503):
            reservation = m.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="confirmed",
                                         price_snapshot_json="{}", policy_at_booking_json="{}", current_policy_json="{}")
            db.add(reservation); db.flush(); reservation_ids.append(reservation.id)
            db.add(e.EnterpriseBookingLink(tenant_id=user.tenant_id, request_id=requests[1 if index == 502 else 0].id,
                                           reservation_id=reservation.id, linked_by=user.id))
            amount, currency = (7, "USD") if index == 501 else ((99999, "IRR") if index == 502 else (10, "IRR"))
            db.add(m.Invoice(tenant_id=user.tenant_id, user_id=user.id, reservation_id=reservation.id,
                             invoice_number=f"QA-{suffix}-{index}", command_id=f"QA-{suffix}-{index}",
                             subtotal_amount=amount, tax_amount=0, total_amount=amount, currency=currency))
        db.commit()
    response = client.get(f"/enterprise/organizations/{org}/statement", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 500
    assert data["linked_bookings"] == 502
    assert {(row["currency"], row["status"]): row["amount"] for row in data["totals"]} == {("IRR", "issued"): 5010, ("USD", "issued"): 7}
    outsider = client.post("/auth/dev-login", json={"email": "employee@faraz.test"}).json()["access_token"]
    assert client.get(f"/enterprise/organizations/{org}/statement", headers={"Authorization": "Bearer " + outsider}).status_code in (403, 404)
