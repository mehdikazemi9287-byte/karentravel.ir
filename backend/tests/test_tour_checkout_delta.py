import uuid,json
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_tour_quote_checkout_and_expired_capacity_release(client):
    employee,_,traveller,offer=reservation_fixture(client,uuid.uuid4().hex);supplier=login(client,'supplier@aftab.test')
    with SessionLocal() as db:
        o=db.get(m.Offer,offer['id']);sid=o.supplier_id;policy=json.loads(o.policy_json)
    tour=client.post('/supplier/tours',headers=auth(supplier),json={'supplier_id':sid,'title':'Mock QA Tour','slug':'qa-'+uuid.uuid4().hex,'origin':'تهران','destination':'شیراز','tour_type':'cultural','details':{'cancellation_policy':policy}}).json();now=datetime.now(timezone.utc)
    departure=client.post('/supplier/tours/'+tour['id']+'/departures',headers=auth(supplier),json={'starts_at':(now+timedelta(days=10)).isoformat(),'ends_at':(now+timedelta(days=12)).isoformat(),'booking_deadline':(now+timedelta(days=9)).isoformat(),'capacity':3,'base_price':1000000,'pricing':{'single_surcharge':200000}}).json();did=departure['id'];url='/tour-departures/'+did
    quote=client.get(url+'/quote?travellers=2&room_type=single',headers=auth(employee));assert quote.status_code==200 and quote.json()['total_amount']==2400000
    payload={'travellers':2,'room_type':'single','expected_total_amount':2000000,'command_id':uuid.uuid4().hex}
    assert client.post(url+'/reservations',headers=auth(employee),json=payload).status_code==409
    payload['expected_total_amount']=2400000;r=client.post(url+'/reservations',headers=auth(employee),json=payload);assert r.status_code==201,r.text;r=r.json()
    assert client.post(url+'/reservations',headers=auth(employee),json=payload).json()['reservation_id']==r['reservation_id']
    assert client.post(url+'/reservations',headers=auth(employee),json={**payload,'travellers':1}).status_code==409
    checkout=client.post('/reservations/'+r['reservation_id']+'/checkout-sessions',headers=auth(employee),json={'command_id':uuid.uuid4().hex}).json()
    second=client.post('/me/travellers',headers=auth(employee),json={'full_name':'Mock QA Tour passenger'}).json();step='/checkout-sessions/'+checkout['id']+'/steps/'
    assert client.put(step+'traveller',headers=auth(employee),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id'],second['id']]}).status_code==200
    check=client.put(step+'recheck',headers=auth(employee),json={'command_id':uuid.uuid4().hex});assert check.status_code==200,check.text
    assert client.put(step+'policy',headers=auth(employee),json={'command_id':uuid.uuid4().hex,'acknowledged':True}).status_code==200
    with SessionLocal() as db:
        db.get(m.Reservation,r['reservation_id']).updated_at=now-timedelta(minutes=40);db.commit();assert r['reservation_id'] in m.sweep_expired_reservations(db,now=now);assert db.get(m.TourDeparture,did).remaining==3;assert db.get(m.TourReservation,r['id']).status=='expired';assert m.sweep_expired_reservations(db,now=now)==[]

def test_supplier_fulfillment_ownership_before_issue_and_replay(client):
    from sqlalchemy import select
    from app.main import User
    employee,reservation,_,offer=reservation_fixture(client,uuid.uuid4().hex)
    owner=login(client,'supplier@aftab.test');email='other-supplier-'+uuid.uuid4().hex+'@qa.invalid'
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='employee@aftab.test'))
        db.add(User(tenant_id=user.tenant_id,email=email,name='Mock QA other supplier',role='supplier'))
        r=db.get(m.Reservation,reservation['id'])
        db.add(m.PaymentIntent(tenant_id=user.tenant_id,user_id=user.id,reservation_id=r.id,command_id=uuid.uuid4().hex,amount=2000000,captured_amount=2000000,status='captured',currency='IRR',provider_key='mock'))
        db.commit()
    other=login(client,email);url='/reservations/'+reservation['id']+'/fulfill';payload={'command_id':uuid.uuid4().hex,'provider_reference':'MockQA-confirmed','document_reference':'document://mock-qa-only'}
    assert client.get('/reservations/'+reservation['id']+'/voucher',headers=auth(employee)).status_code==409
    assert reservation['id'] in client.get('/supplier/reservations/ready',headers=auth(owner)).text
    assert reservation['id'] not in client.get('/supplier/reservations/ready',headers=auth(other)).text
    assert client.post(url,headers=auth(other),json=payload).status_code==403
    r=client.post(url,headers=auth(owner),json=payload);assert r.status_code==200,r.text
    assert r.json()['voucher']['status']=='issued'
    assert client.post(url,headers=auth(other),json=payload).status_code==403
    assert client.post(url,headers=auth(owner),json=payload).json()['voucher']['id']==r.json()['voucher']['id']

    with SessionLocal() as db:
        item=db.scalar(select(m.BookingItem).where(m.BookingItem.reservation_id==reservation['id']));snapshot=json.loads(item.snapshot_json);snapshot['title']='<script>alert(1)</script>';item.snapshot_json=json.dumps(snapshot);db.commit()
    document=client.get('/reservations/'+reservation['id']+'/voucher',headers=auth(employee))
    assert document.status_code==200 and '<script>' not in document.text and '&lt;script&gt;' in document.text
    assert document.headers['cache-control']=='no-store'
