"""Candidate-only QA fixtures, round 3 (labelled test rows in the throwaway candidate DB)."""
import json, sys, uuid
from datetime import datetime, timedelta, timezone
sys.path.insert(0, "/work")
from sqlalchemy import select
from app import operations as m
from app.database import SessionLocal, set_tenant_context
from app.main import User
with SessionLocal() as db:
    u = {x.email: x for x in db.scalars(select(User).where(User.email.like("%@aftab.test")))}
    tid = u["employee@aftab.test"].tenant_id; set_tenant_context(db, tid)
    agency = db.scalar(select(m.Agency).where(m.Agency.tenant_id == tid, m.Agency.display_name == "آژانس آزمون QA"))
    supplier = db.scalar(select(m.Supplier).where(m.Supplier.tenant_id == tid, m.Supplier.display_name == "تأمین‌کنندهٔ آزمون QA"))
    now, cust = datetime.now(timezone.utc), u["employee@aftab.test"].id
    if db.scalar(select(m.Offer.id).where(m.Offer.tenant_id == tid, m.Offer.title == "اقامت دو شب، اتاق دوتخته (آزمون QA)")) is None:
        db.add(m.Offer(tenant_id=tid, supplier_id=supplier.id, service_type="hotel", title="اقامت دو شب، اتاق دوتخته (آزمون QA)", amount=18000000, currency="IRR", available_units=4, status="active", valid_until=now + timedelta(days=30)))
        db.add(m.CreditAccount(tenant_id=tid, currency="IRR", limit_amount=500000000))
    for i in range(2):  # two confirmed agency bookings without a commission posting, one per QA viewport pass
        r = m.Reservation(tenant_id=tid, user_id=cust, service_type="hotel", status="confirmed", sales_channel_id=agency.sales_channel_id, confirmed_at=now, booking_reference="QA-" + uuid.uuid4().hex[:8], price_snapshot_json=json.dumps({"total_amount": 30000000, "currency": "IRR"}))
        db.add(r); db.flush()
        db.add(m.Invoice(tenant_id=tid, reservation_id=r.id, user_id=cust, invoice_number="QA-" + uuid.uuid4().hex[:10], command_id="qa-" + uuid.uuid4().hex, subtotal_amount=27500000, tax_amount=2500000, total_amount=30000000))
    db.commit(); print("fixtures2 ok")
