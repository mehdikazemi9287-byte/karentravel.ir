import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.main import SessionLocal, User
import app.main as main_module
from app.operations import EmployeeAssignment, InstallmentPlan, Offer, Organization, PaymentIntent, PriceCheck, Reservation, Supplier


def auth(token): return {"Authorization": f"Bearer {token}"}


def login(client, email):
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200
    return response.json()


def test_invoice_is_backend_derived_idempotent_and_owner_scoped(client):
    suffix = uuid.uuid4().hex
    employee = login(client, "employee@aftab.test"); faraz = login(client, "employee@faraz.test"); backoffice = login(client, "backoffice@aftab.test")
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=owner.tenant_id, user_id=owner.id, service_type="hotel", status="confirmed", price_snapshot_json='{"total_amount":4200000,"currency":"IRR"}', policy_at_booking_json="{}", current_policy_json="{}")
        db.add(reservation); db.commit(); reservation_id = reservation.id
    headers = {**auth(backoffice["access_token"]), "Idempotency-Key": f"invoice-final-domain-{suffix}"}
    issued = client.post(f"/reservations/{reservation_id}/invoice", headers=headers)
    replay = client.post(f"/reservations/{reservation_id}/invoice", headers=headers)
    assert issued.status_code == 201 and issued.json()["total_amount"] == 4_200_000 and issued.json()["tax_amount"] == 0
    assert replay.json()["id"] == issued.json()["id"]
    assert client.get("/me/invoices", headers=auth(employee["access_token"])).json()[0]["id"] == issued.json()["id"]
    assert client.get("/me/invoices", headers=auth(faraz["access_token"])).json() == []
    assert client.post(f"/reservations/{reservation_id}/invoice", headers={**auth(employee["access_token"]), "Idempotency-Key": "invoice-denied"}).status_code == 403


def test_invoice_tax_policy_is_configurable_and_production_fail_closed(monkeypatch):
    monkeypatch.delenv("INVOICE_TAX_BPS", raising=False); monkeypatch.delenv("INVOICE_TAX_POLICY_REFERENCE", raising=False)
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    with pytest.raises(Exception) as blocked:
        main_module._invoice_tax_policy()
    assert getattr(blocked.value, "status_code", None) == 503
    monkeypatch.setenv("INVOICE_TAX_BPS", "900"); monkeypatch.setenv("INVOICE_TAX_POLICY_REFERENCE", "approved-policy:v1")
    assert main_module._invoice_tax_policy() == (900, "approved-policy:v1")


def test_support_case_thread_distinguishes_human_and_blocks_cross_tenant(client):
    suffix = uuid.uuid4().hex
    employee = login(client, "employee@aftab.test"); faraz = login(client, "employee@faraz.test"); agent = login(client, "backoffice@aftab.test")
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        reservation = Reservation(tenant_id=owner.tenant_id, user_id=owner.id, service_type="tour", status="confirmed", price_snapshot_json="{}", policy_at_booking_json="{}", current_policy_json="{}")
        db.add(reservation); db.commit(); reservation_id = reservation.id
    payload = {"reservation_id": reservation_id, "subject": "بررسی واچر", "body": "لطفاً واچر را بررسی کنید", "priority": "high"}
    assert client.post("/support/cases", headers={**auth(faraz["access_token"]), "Idempotency-Key": f"case-cross-tenant-{suffix}"}, json=payload).status_code == 404
    opened = client.post("/support/cases", headers={**auth(employee["access_token"]), "Idempotency-Key": f"case-owner-final-{suffix}"}, json=payload)
    assert opened.status_code == 201 and opened.json()["messages"][0]["sender_type"] == "customer"
    case_id = opened.json()["id"]
    reply = client.post(f"/support/cases/{case_id}/human-replies", headers=auth(agent["access_token"]), json={"body": "پیام کارشناس انسانی"})
    assert reply.status_code == 201 and reply.json()["sender_type"] == "human_agent"
    thread = client.get("/support/cases", headers=auth(employee["access_token"])).json()[0]
    assert [item["sender_type"] for item in thread["messages"]] == ["customer", "human_agent"]
    assert client.post(f"/support/cases/{case_id}/human-replies", headers=auth(employee["access_token"]), json={"body": "جعل کارشناس"}).status_code == 403


def test_installment_execution_and_settlement_posting_are_tenant_safe(client):
    suffix = uuid.uuid4().hex
    employee = login(client, "employee@aftab.test"); faraz = login(client, "employee@faraz.test"); finance = login(client, "finance@aftab.test")
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        organization = Organization(tenant_id=owner.tenant_id, name="سازمان اقساط", status="active"); db.add(organization); db.flush()
        db.add(EmployeeAssignment(tenant_id=owner.tenant_id, user_id=owner.id, organization_id=organization.id))
        plan = InstallmentPlan(tenant_id=owner.tenant_id, organization_id=organization.id, title="سه ماهه", terms_json='{"months":3,"fee_bps":300}', status="active"); supplier = Supplier(tenant_id=owner.tenant_id, supplier_type="hotel", display_name="تأمین تسویه", status="active"); db.add_all([plan, supplier]); db.flush()
        offer = Offer(tenant_id=owner.tenant_id, supplier_id=supplier.id, service_type="hotel", title="هتل تسویه", amount=3_000_000, available_units=2, valid_until=datetime.now(timezone.utc)+timedelta(hours=1), policy_json="{}", attributes_json="{}"); db.add(offer); db.flush()
        check = PriceCheck(tenant_id=owner.tenant_id, offer_id=offer.id, user_id=owner.id, command_id=f"final-check-{suffix}", units=1, amount=3_000_000, currency="IRR", snapshot_json='{"total_amount":3000000,"currency":"IRR"}', snapshot_hash=f"final-snapshot-{suffix}", expires_at=datetime.now(timezone.utc)+timedelta(minutes=10)); db.add(check); db.flush()
        reservation = Reservation(tenant_id=owner.tenant_id, user_id=owner.id, service_type="hotel", status="confirmed", price_check_id=check.id, price_snapshot_json='{"total_amount":3000000,"currency":"IRR"}', policy_at_booking_json="{}", current_policy_json="{}"); db.add(reservation); db.flush()
        payment = PaymentIntent(tenant_id=owner.tenant_id, reservation_id=reservation.id, user_id=owner.id, command_id=f"captured-final-{suffix}", amount=3_000_000, status="captured", captured_amount=3_000_000, provider_reference="sandbox-evidence"); db.add(payment); db.commit(); plan_id = plan.id; reservation_id = reservation.id
    requested = client.post(f"/reservations/{reservation_id}/installments?plan_id={plan_id}", headers={**auth(employee["access_token"]), "Idempotency-Key": f"installment-final-{suffix}"})
    assert requested.status_code == 201 and len(requested.json()["schedule"]) == 3 and sum(x["amount"] for x in requested.json()["schedule"]) == requested.json()["total_payable"]
    agreement_id = requested.json()["id"]
    assert client.put(f"/finance/installments/{agreement_id}/decision", headers=auth(finance["access_token"]), json={"decision": "activate"}).json()["status"] == "active"
    assert client.put(f"/finance/installments/{agreement_id}/decision", headers=auth(faraz["access_token"]), json={"decision": "activate"}).status_code == 403
    settlement_headers = {**auth(finance["access_token"]), "Idempotency-Key": f"settlement-final-{suffix}"}
    settlement = client.post(f"/finance/reservations/{reservation_id}/settlements", headers=settlement_headers)
    replay = client.post(f"/finance/reservations/{reservation_id}/settlements", headers=settlement_headers)
    assert settlement.status_code == 201 and settlement.json()["status"] == "pending" and settlement.json()["external_transfer_claimed"] is False
    assert replay.json()["id"] == settlement.json()["id"]


def test_admin_role_workflow_prevents_self_and_privilege_escalation(client):
    suffix = uuid.uuid4().hex
    organization_admin = login(client, "org-admin@aftab.test"); tenant_admin = login(client, "tenant-admin@aftab.test"); faraz = login(client, "employee@faraz.test")
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == "tenant-admin@aftab.test")); target = User(tenant_id=admin.tenant_id, email=f"role-target-{suffix}@aftab.test", name="کاربر نقش", role="customer"); db.add(target); db.commit(); target_id = target.id; admin_id = admin.id
    assert client.put(f"/admin/users/{target_id}/role", headers=auth(organization_admin["access_token"]), json={"role": "tenant_admin", "reason": "تلاش ارتقا"}).status_code == 403
    changed = client.put(f"/admin/users/{target_id}/role", headers=auth(tenant_admin["access_token"]), json={"role": "manager", "reason": "تغییر مصوب"})
    assert changed.status_code == 200 and changed.json()["role"] == "manager"
    assert client.put(f"/admin/users/{admin_id}/role", headers=auth(tenant_admin["access_token"]), json={"role": "employee", "reason": "خودتغییری"}).status_code == 409
    assert client.put(f"/admin/users/{target_id}/role", headers=auth(faraz["access_token"]), json={"role": "employee", "reason": "tenant دیگر"}).status_code == 403
