import uuid,json
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_accommodation_quote_recheck_replay_ownership_and_release(client):
    from sqlalchemy import select
    from app.main import User
    employee,_,traveller,offer=reservation_fixture(client,uuid.uuid4().hex);supplier=login(client,'supplier@aftab.test');now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        o=db.get(m.Offer,offer['id']);sid=o.supplier_id;policy=json.loads(o.policy_json)
        user=db.scalar(select(User).where(User.email=='employee@aftab.test'));email='unassigned-'+uuid.uuid4().hex+'@qa.invalid';db.add(User(tenant_id=user.tenant_id,email=email,name='Mock QA',role='supplier'));db.commit()
    prop=client.post('/supplier/vacation-properties',headers=auth(supplier),json={'supplier_id':sid,'title':'Mock QA Accommodation','slug':'qa-'+uuid.uuid4().hex,'city':'رامسر','property_type':'villa','capacity':4,'bedrooms':2,'details':{'cancellation_policy':policy}}).json()
    unitbody={'title':'Mock QA Unit','capacity':4,'available_units':1,'nightly_price':1000000}
    assert client.post('/supplier/vacation-properties/'+prop['id']+'/units',headers=auth(login(client,email)),json=unitbody).status_code==403
    unit=client.post('/supplier/vacation-properties/'+prop['id']+'/units',headers=auth(supplier),json=unitbody).json();url='/vacation-units/'+unit['id'];dates={'check_in':(now+timedelta(days=10)).isoformat(),'check_out':(now+timedelta(days=12)).isoformat(),'guests':2}
    quote=client.get(url+'/quote',headers=auth(employee),params=dates);assert quote.status_code==200 and quote.json()['total_amount']==2000000
    payload={**dates,'command_id':uuid.uuid4().hex,'expected_total_amount':1000000};assert client.post(url+'/reservations',headers=auth(employee),json=payload).status_code==409
    payload['expected_total_amount']=2000000;r=client.post(url+'/reservations',headers=auth(employee),json=payload);assert r.status_code==201,r.text;r=r.json()
    assert client.post(url+'/reservations',headers=auth(employee),json=payload).json()['reservation_id']==r['reservation_id']
    assert client.post(url+'/reservations',headers=auth(employee),json={**payload,'guests':3}).status_code==409
    assert client.get(url+'/quote',headers=auth(employee),params=dates).status_code==409
    session=client.post('/reservations/'+r['reservation_id']+'/checkout-sessions',headers=auth(employee),json={'command_id':uuid.uuid4().hex}).json();step='/checkout-sessions/'+session['id']+'/steps/'
    assert client.put(step+'traveller',headers=auth(employee),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id']]}).status_code==200
    check=client.put(step+'recheck',headers=auth(employee),json={'command_id':uuid.uuid4().hex});assert check.status_code==200,check.text
    assert client.put(step+'policy',headers=auth(employee),json={'command_id':uuid.uuid4().hex,'acknowledged':True}).status_code==200
    with SessionLocal() as db:
        db.get(m.Reservation,r['reservation_id']).updated_at=now-timedelta(minutes=40);db.commit();assert r['reservation_id'] in m.sweep_expired_reservations(db,now=now);assert db.get(m.VacationReservation,r['id']).status=='expired'
    assert client.get(url+'/quote',headers=auth(employee),params=dates).status_code==200
