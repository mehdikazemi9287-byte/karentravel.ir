import json
from sqlalchemy import select,func
from pathlib import Path
from app.main import SessionLocal
from app import operations as m
assert 'sqlite' in str(SessionLocal.kw['bind'].url)
data=json.loads(Path('/qa/marketplace-host-result.json').read_text())
with SessionLocal() as db:
 for result in data['checks']:
  rid=result['reservation'];r=db.get(m.Reservation,rid)
  assert r.status=='issued'
  for cls in [m.Voucher,m.PaymentIntent]:assert db.scalar(select(func.count()).select_from(cls).where(cls.reservation_id==rid))==1
  assert db.scalar(select(func.count()).select_from(m.BookingStatusHistory).where(m.BookingStatusHistory.reservation_id==rid,m.BookingStatusHistory.to_status=='reserved'))==1
  assert db.scalar(select(m.Trip).where(m.Trip.id==r.trip_id)) is not None
print('QA persisted approval/payment/voucher/trip uniqueness PASS')
