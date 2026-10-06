"""Candidate-only QA fixtures (clearly labelled test rows in the throwaway candidate DB). Never run against production."""
import json, sys, uuid
from datetime import datetime, timezone
sys.path.insert(0, "/work")
from sqlalchemy import select
from app import operations as m
from app.database import SessionLocal, set_tenant_context
from app.main import User
with SessionLocal() as db:
    u = {x.email: x for x in db.scalars(select(User).where(User.email.like("%@aftab.test")))}
    tid = u["employee@aftab.test"].tenant_id; set_tenant_context(db, tid)
    if db.scalar(select(m.Agency.id).where(m.Agency.tenant_id == tid, m.Agency.display_name == "آژانس آزمون QA")):
        print("fixtures already present"); sys.exit(0)
    entity = db.scalar(select(m.LicensedEntity).where(m.LicensedEntity.tenant_id == tid)) or m.LicensedEntity(tenant_id=tid, legal_name="نهاد آزمون QA"); db.add(entity); db.flush()
    channel = m.SalesChannel(tenant_id=tid, name="qa-agency-channel", channel_type="AGENCY", licensed_entity_id=entity.id); db.add(channel); db.flush()
    agency, empty_agency = m.Agency(tenant_id=tid, display_name="آژانس آزمون QA", commission_bps=500, markup_bps=200, sales_channel_id=channel.id), m.Agency(tenant_id=tid, display_name="آژانس بدون کانال (آزمون QA)")
    db.add_all([agency, empty_agency]); db.flush()
    db.add_all([m.AgencyMembership(tenant_id=tid, user_id=u["agency@aftab.test"].id, agency_id=a.id) for a in (agency, empty_agency)])
    now, cust = datetime.now(timezone.utc), u["employee@aftab.test"].id
    r1 = m.Reservation(tenant_id=tid, user_id=cust, service_type="hotel", status="confirmed", sales_channel_id=channel.id, confirmed_at=now, booking_reference="QA-" + uuid.uuid4().hex[:8], price_snapshot_json=json.dumps({"total_amount": 24000000, "currency": "IRR"}))
    r2 = m.Reservation(tenant_id=tid, user_id=cust, service_type="tour", status="reserved", sales_channel_id=channel.id, booking_reference="QA-" + uuid.uuid4().hex[:8], price_snapshot_json=json.dumps({"total_amount": 9000000, "currency": "IRR"}))
    db.add_all([r1, r2]); db.flush()
    pay = m.PaymentIntent(tenant_id=tid, reservation_id=r1.id, user_id=cust, command_id="qa-" + uuid.uuid4().hex, amount=24000000, status="captured", captured_amount=24000000, provider_key="qa-test"); db.add(pay); db.flush()
    supplier = m.Supplier(tenant_id=tid, supplier_type="hotel", display_name="تأمین‌کنندهٔ آزمون QA"); db.add(supplier); db.flush()
    db.add_all([m.SupplierMembership(tenant_id=tid, user_id=u["supplier@aftab.test"].id, supplier_id=supplier.id), m.ProviderContract(tenant_id=tid, supplier_id=supplier.id, provider_key="grs", mode="disabled"),
                m.SettlementRecord(tenant_id=tid, supplier_id=supplier.id, reservation_id=r1.id, amount=20000000, status="pending"),
                m.Invoice(tenant_id=tid, reservation_id=r1.id, user_id=cust, invoice_number="QA-" + uuid.uuid4().hex[:10], command_id="qa-" + uuid.uuid4().hex, subtotal_amount=22000000, tax_amount=2000000, total_amount=24000000)])
    trip = db.scalar(select(m.Trip).where(m.Trip.tenant_id == tid, m.Trip.title.like("سفر شیراز%")))
    case = m.SupportCase(tenant_id=tid, user_id=cust, trip_id=trip.id if trip else None, reservation_id=r1.id, subject="پرسش دربارهٔ تغییر پرواز (آزمون QA)", command_id="qa-" + uuid.uuid4().hex); db.add(case); db.flush()
    db.add(m.SupportThreadMessage(tenant_id=tid, case_id=case.id, sender_type="customer", sender_user_id=cust, body="آیا ساعت پرواز من تغییر کرده است؟"))
    db.commit(); print("fixtures created", agency.id, case.id)
