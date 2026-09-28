from datetime import datetime,timedelta,timezone
import uuid
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture

def test_reaper_preserves_legacy_paid_and_ambiguous_holds(client):
    now=datetime.now(timezone.utc);ids=[]
    for status in ['legacy','created','initiated','captured']:
        session,row,_,_=reservation_fixture(client,uuid.uuid4().hex)
        with SessionLocal() as db:
            r=db.get(m.Reservation,row['id']);r.created_at=now-timedelta(hours=3 if status=='legacy' else 1);r.updated_at=now-timedelta(minutes=40)
            if status!='legacy':db.add(m.PaymentIntent(tenant_id=r.tenant_id,user_id=r.user_id,reservation_id=r.id,command_id=uuid.uuid4().hex,amount=2000000,currency='IRR',status=status,captured_amount=2000000 if status=='captured' else 0))
            db.commit();ids.append(r.id)
    with SessionLocal() as db:
        expired=m.sweep_expired_reservations(db,now=now,not_before=now-timedelta(hours=2))
        assert ids[1] in expired
        assert all(i not in expired for i in [ids[0],ids[2],ids[3]])
        assert all(db.get(m.Reservation,i).status=='reserved' for i in [ids[0],ids[2],ids[3]])
        assert m.sweep_expired_reservations(db,now=now,not_before=now-timedelta(hours=2))==[]

        for i in ids:
            db.get(m.Reservation,i).updated_at=now
        db.commit()
