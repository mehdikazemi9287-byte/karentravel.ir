"""Organization receivables: invoices from linked bookings, FIFO settlements, ageing by mandatory terms, treasury posting, isolation."""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import enterprise_models as e
from app import operations as m
from app.commerce import TreasuryEntry
from app.main import SessionLocal, User
from app.receivables import age_invoices


def _h(client, email):
    r = client.post("/auth/dev-login", json={"email": email})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_fifo_ageing():
    today = date(2026, 6, 30)
    invs = [{"invoice_number": "A", "total": 100, "issued_on": "2026-03-01"}, {"invoice_number": "B", "total": 50, "issued_on": "2026-06-20"}]
    items, b = age_invoices(invs, 60, today, 30)
    assert items[0]["paid"] == 60 and items[0]["open"] == 40 and items[0]["days_overdue"] == 91 and b["d90_plus"] == 40
    assert items[1]["open"] == 50 and b["not_due"] == 50
    _, b2 = age_invoices(invs, 0, today, None)  # terms missing -> nothing aged
    assert sum(b2.values()) == 0


def _fixture(amounts_days):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "employee@aftab.test"))
        org = m.Organization(tenant_id=user.tenant_id, name="سازمان مطالبات " + uuid.uuid4().hex[:5], status="active")
        db.add(org); db.flush()
        req = e.EnterpriseRequest(tenant_id=user.tenant_id, organization_id=org.id, requester_id=user.id, use_case="hotel", title="سفر کاری",
                                  status="approved", requirements_json="{}", policy_snapshot_json="{}", policy_result="allowed")
        db.add(req); db.flush()
        for amount, days_ago in amounts_days:
            res = m.Reservation(tenant_id=user.tenant_id, user_id=user.id, service_type="hotel", status="confirmed", booking_reference="RC-" + uuid.uuid4().hex[:8],
                                price_snapshot_json="{}", policy_at_booking_json="{}", current_policy_json="{}")
            db.add(res); db.flush()
            db.add(e.EnterpriseBookingLink(tenant_id=user.tenant_id, request_id=req.id, reservation_id=res.id, linked_by=user.id))
            n = "RC-" + uuid.uuid4().hex[:10]
            db.add(m.Invoice(tenant_id=user.tenant_id, user_id=user.id, reservation_id=res.id, invoice_number=n, command_id=n, subtotal_amount=amount,
                             tax_amount=0, total_amount=amount, currency="IRR", issued_at=datetime.now(timezone.utc) - timedelta(days=days_ago)))
        db.commit()
        return org.id


def test_receivables_flow(client):
    fin = _h(client, "finance@aftab.test")
    admin = _h(client, "tenant-admin@aftab.test")
    org = _fixture([(10_000_000, 75), (4_000_000, 5)])
    assert client.get("/receivables/organizations", headers=_h(client, "employee@aftab.test")).status_code == 403
    d = client.get(f"/receivables/organizations/{org}", headers=fin).json()
    assert d["terms_missing"] and d["invoiced"] == 14_000_000 and d["outstanding"] == 14_000_000 and d["overdue"] == 0
    assert client.put(f"/receivables/organizations/{org}/terms", json={"payment_terms_days": 30}, headers=_h(client, "backoffice@aftab.test")).status_code == 403
    assert client.put(f"/receivables/organizations/{org}/terms", json={"payment_terms_days": 30, "contact_name": "واحد مالی"}, headers=admin).status_code == 200
    d = client.get(f"/receivables/organizations/{org}", headers=fin).json()
    assert d["buckets"]["d31_60"] == 10_000_000 and d["buckets"]["not_due"] == 4_000_000 and d["oldest_overdue_days"] == 45
    today = date.today().isoformat()
    s = client.post(f"/receivables/organizations/{org}/settlements", json={"amount": 12_000_000, "paid_on": today, "method": "bank", "reference": "TRX-" + org[:6]}, headers=admin)
    assert s.status_code == 201, s.text
    assert client.post(f"/receivables/organizations/{org}/settlements", json={"amount": 1, "paid_on": today, "method": "bank", "reference": "TRX-" + org[:6]}, headers=admin).status_code == 409
    assert client.post(f"/receivables/organizations/{org}/settlements", json={"amount": 1, "paid_on": "2099-01-01", "method": "bank", "reference": "FUT"}, headers=admin).status_code == 422
    d = client.get(f"/receivables/organizations/{org}", headers=fin).json()
    assert d["settled"] == 12_000_000 and d["outstanding"] == 2_000_000 and d["overdue"] == 0 and d["buckets"]["not_due"] == 2_000_000
    assert d["items"][0]["paid"] == 10_000_000 and d["items"][1]["open"] == 2_000_000 and d["settlements"][0]["posted"]
    with SessionLocal() as db:
        entry = db.get(TreasuryEntry, s.json()["treasury_entry_id"])
        assert entry.account_type == "receivable" and entry.counterparty_type == "organization" and entry.counterparty_ref == org and entry.credit == 12_000_000
    lst = client.get("/receivables/organizations", headers=fin).json()
    assert any(i["organization_id"] == org and i["outstanding"] == 2_000_000 for i in lst["items"])
    with SessionLocal() as db:
        otid = db.scalar(select(User.tenant_id).where(User.email == "employee@faraz.test"))
        oemail = f"rc-fin-{uuid.uuid4().hex[:6]}@faraz.test"
        db.add(User(tenant_id=otid, email=oemail, name="مالی فراز", role="tenant_admin"))
        db.commit()
    other = _h(client, oemail)
    assert client.get(f"/receivables/organizations/{org}", headers=other).status_code == 404
    assert client.post(f"/receivables/organizations/{org}/settlements", json={"amount": 1, "paid_on": today, "method": "bank", "reference": "X1"}, headers=other).status_code == 404
