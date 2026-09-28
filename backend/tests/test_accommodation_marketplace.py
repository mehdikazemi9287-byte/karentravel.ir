import json,uuid
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth


def fixture(client,units=2):
    employee,_,_,offer=reservation_fixture(client,uuid.uuid4().hex)
    supplier=login(client,'supplier@aftab.test')
    with SessionLocal() as db:
        o=db.get(m.Offer,offer['id']);sid=o.supplier_id;policy=json.loads(o.policy_json)
    prop=client.post('/supplier/vacation-properties',headers=auth(supplier),json={'supplier_id':sid,'title':'Mock QA Marketplace','slug':'qa-'+uuid.uuid4().hex,'city':'رامسر','property_type':'pool_property','capacity':4,'bedrooms':2,'details':{'cancellation_policy':policy}})
    assert prop.status_code==201,prop.text
    url='/supplier/vacation-properties/'+prop.json()['id']+'/units'
    body={'title':'Mock QA Unit','capacity':4,'available_units':units,'nightly_price':1000000,'pricing':{'base_capacity':2,'extra_guest_price':100000,'cleaning_fee':200000,'service_fee':50000}}
    unit=client.post(url,headers=auth(supplier),json=body);assert unit.status_code==201,unit.text
    return employee,supplier,unit.json()['id'],url,body


def test_calendar_pricing_overlap_and_supplier_audit(client):
    employee,supplier,uid,_,_=fixture(client)
    day=(datetime.now(timezone.utc)+timedelta(days=20)).replace(hour=12,minute=0,second=0,microsecond=0)
    def dates(a,b):return {'check_in':(day+timedelta(days=a)).isoformat(),'check_out':(day+timedelta(days=b)).isoformat(),'guests':3}
    base='/vacation-units/'+uid
    # Two disjoint holds in two-unit inventory still allow a stay spanning both.
    for a,b in [(0,1),(1,2)]:
        r=client.post(base+'/reservations',headers=auth(employee),json={**dates(a,b),'command_id':uuid.uuid4().hex});assert r.status_code==201,r.text
    q=client.get(base+'/quote',headers=auth(employee),params=dates(0,2));assert q.status_code==200,q.text
    assert q.json()['total_amount']==2450000
    assert q.json()['price_components']=={'accommodation':2000000,'extra_guests':200000,'cleaning':200000,'service':50000}
    r=client.post(base+'/reservations',headers=auth(employee),json={**dates(0,2),'command_id':uuid.uuid4().hex,'expected_total_amount':2450000});assert r.status_code==201,r.text
    cal=client.get(base+'/calendar',headers=auth(employee),params={'start':day.isoformat(),'days':3}).json()
    assert [d['state'] for d in cal['days']]==['SOLD_OUT','SOLD_OUT','AVAILABLE']
    change={'command_id':uuid.uuid4().hex,'pricing':{'calendar':{(day+timedelta(days=3)).date().isoformat():{'status':'UNAVAILABLE'},(day+timedelta(days=4)).date().isoformat():{'nightly_price':2000000,'minimum_stay':2}}}}
    endpoint='/supplier/vacation-units/'+uid+'/rates'
    assert client.put(endpoint,headers=auth(employee),json=change).status_code==403
    response=client.put(endpoint,headers=auth(supplier),json=change);assert response.status_code==200,response.text
    assert client.put(endpoint,headers=auth(supplier),json=change).json()==response.json()
    assert client.put(endpoint,headers=auth(supplier),json={**change,'pricing':{}}).status_code==409
    assert client.get(base+'/quote',headers=auth(employee),params=dates(3,4)).status_code==422
    assert client.get(base+'/quote',headers=auth(employee),params=dates(4,5)).status_code==422
    assert client.get(base+'/quote',headers=auth(employee),params=dates(4,6)).json()['total_amount']==3000000
    with SessionLocal() as db:
        assert db.get(m.Reservation,r.json()['reservation_id']).price_snapshot_json.find('2450000')!=-1
        events=db.scalars(select(m.OutboxEvent).where(m.OutboxEvent.aggregate_id==uid,m.OutboxEvent.event_type=='vacation_rates.changed')).all()
        assert len(events)==1 and json.loads(events[0].payload_json)['old']['cleaning_fee']==200000


def test_invalid_calendar_and_fee_configuration_rejected(client):
    _,supplier,_,url,body=fixture(client)
    for pricing in [{'calendar':{'not-a-date':{}}},{'cleaning_fee':-1},{'base_capacity':5},{'extra_guest_price':100},{'seasonal_rates':[{'start':'02-31','end':'03-01','nightly_price':10}]},{'calendar':{'2030-01-01':{'status':'REQUEST'}}}]:
        assert client.post(url,headers=auth(supplier),json={**body,'pricing':pricing}).status_code==422


def test_transition_key_cannot_silently_target_another_reservation(client):
    employee,_,_,offer=reservation_fixture(client,uuid.uuid4().hex)
    with SessionLocal() as db:
        tenant=db.get(m.Offer,offer['id']).tenant_id
        from app.main import User
        user=db.scalar(select(User).where(User.email=='employee@aftab.test'))
        a=m.Reservation(tenant_id=tenant,user_id=user.id,service_type='hotel');b=m.Reservation(tenant_id=tenant,user_id=user.id,service_type='hotel');db.add_all([a,b]);db.flush()
        key=uuid.uuid4().hex;m.transition_reservation(db,a,'pending',user.id,key);db.flush()
        import pytest
        with pytest.raises(ValueError,match='different payload'):m.transition_reservation(db,b,'pending',user.id,key)
        assert b.status=='draft'


def test_request_to_book_requires_host_recheck_and_is_idempotent(client):
    employee,supplier,uid,_,_=fixture(client,units=1)
    with SessionLocal() as db:
        u=db.get(m.VacationUnit,uid);p=db.get(m.VacationProperty,u.property_id)
        details=json.loads(p.details_json);details['booking_mode']='REQUEST_TO_BOOK';p.details_json=json.dumps(details);db.commit()
    start=datetime.now(timezone.utc)+timedelta(days=30)
    body={'check_in':start.isoformat(),'check_out':(start+timedelta(days=2)).isoformat(),'guests':2,'command_id':uuid.uuid4().hex}
    a=client.post('/vacation-units/'+uid+'/reservations',headers=auth(employee),json=body);assert a.status_code==201,a.text
    a=a.json();rid=a['reservation_id'];assert a['status']=='requested' and not a['payment_required'] and '/manage-booking/' in a['checkout_url']
    assert client.post('/vacation-units/'+uid+'/reservations',headers=auth(employee),json=body).json()['reservation_id']==rid
    assert client.post('/reservations/'+rid+'/payment-intents',headers={**auth(employee),'Idempotency-Key':uuid.uuid4().hex}).status_code==409
    assert client.post('/reservations/'+rid+'/checkout-sessions',headers=auth(employee),json={'command_id':uuid.uuid4().hex}).status_code==409
    b=client.post('/vacation-units/'+uid+'/reservations',headers=auth(employee),json={**body,'command_id':uuid.uuid4().hex}).json()
    decision={'action':'accept','reason':'Mock QA host acceptance','command_id':uuid.uuid4().hex}
    endpoint='/reservations/'+rid+'/accommodation-decision'
    assert client.post(endpoint,headers=auth(employee),json=decision).status_code==403
    accepted=client.post(endpoint,headers=auth(supplier),json=decision);assert accepted.status_code==200,accepted.text
    assert accepted.json()['status']=='reserved'
    assert client.post(endpoint,headers=auth(supplier),json=decision).json()==accepted.json()
    assert client.post(endpoint,headers=auth(supplier),json={**decision,'action':'reject'}).status_code==409
    assert client.post('/reservations/'+b['reservation_id']+'/accommodation-decision',headers=auth(supplier),json={**decision,'command_id':uuid.uuid4().hex}).status_code==409
    assert client.post('/reservations/'+rid+'/checkout-sessions',headers=auth(employee),json={'command_id':uuid.uuid4().hex}).status_code==201
    withdraw={'action':'withdraw','reason':'Mock QA withdrawal','command_id':uuid.uuid4().hex}
    endpoint='/reservations/'+b['reservation_id']+'/accommodation-decision'
    assert client.post(endpoint,headers=auth(supplier),json=withdraw).status_code==403
    assert client.post(endpoint,headers=auth(employee),json=withdraw).json()['status']=='cancelled'
    with SessionLocal() as db:
        histories=db.scalars(select(m.BookingStatusHistory).where(m.BookingStatusHistory.reservation_id==rid)).all()
        assert [h.to_status for h in histories]==['booking_pending','reserved']
        assert histories[-1].reason=='Mock QA host acceptance'
        assert db.scalar(select(m.Voucher).where(m.Voucher.reservation_id==rid)) is None
        assert db.scalar(select(m.PaymentIntent).where(m.PaymentIntent.reservation_id==rid)) is None
        reservation=db.get(m.Reservation,rid)
        amount=json.loads(reservation.price_snapshot_json)["total_amount"]
        db.add(m.PaymentIntent(tenant_id=reservation.tenant_id,reservation_id=rid,user_id=reservation.user_id,command_id=uuid.uuid4().hex,amount=amount,currency="IRR",status="captured",captured_amount=amount));db.commit()
    issued=client.post('/reservations/'+rid+'/fulfill',headers=auth(supplier),json={'command_id':uuid.uuid4().hex,'provider_reference':'Mock-QA-host-confirmation','document_reference':'document://mock-qa-stay'})
    assert issued.status_code==200,issued.text
    with SessionLocal() as db:
        assert db.scalar(select(m.VacationReservation).where(m.VacationReservation.reservation_id==rid)).status=='confirmed'



def test_host_cannot_accept_changed_price_and_can_reject(client):
    employee,supplier,uid,_,_=fixture(client)
    with SessionLocal() as db:
        u=db.get(m.VacationUnit,uid);p=db.get(m.VacationProperty,u.property_id)
        d=json.loads(p.details_json);d['booking_mode']='REQUEST_TO_BOOK';p.details_json=json.dumps(d);db.commit()
    start=datetime.now(timezone.utc)+timedelta(days=35)
    r=client.post('/vacation-units/'+uid+'/reservations',headers=auth(employee),json={'check_in':start.isoformat(),'check_out':(start+timedelta(days=2)).isoformat(),'guests':2,'command_id':uuid.uuid4().hex}).json()
    with SessionLocal() as db:db.get(m.VacationUnit,uid).nightly_price+=100;db.commit()
    endpoint='/reservations/'+r['reservation_id']+'/accommodation-decision'
    assert client.post(endpoint,headers=auth(supplier),json={'action':'accept','reason':'Mock QA acceptance','command_id':uuid.uuid4().hex}).status_code==409
    assert client.post(endpoint,headers=auth(supplier),json={'action':'reject','reason':'Mock QA price changed','command_id':uuid.uuid4().hex}).json()['status']=='failed'


def test_discovery_filters_and_pagination_are_catalog_not_availability(client):
    employee,_,uid,_,_=fixture(client)
    with SessionLocal() as db:pid=db.get(m.VacationUnit,uid).property_id
    r=client.get('/vacation-rentals',headers=auth(employee),params={'city':'رامسر','property_type':'pool_property','guests':4,'limit':1})
    assert r.status_code==200 and r.json()[0]['id']==pid
    assert client.get('/vacation-rentals',headers=auth(employee),params={'property_type':'pool_property','guests':5}).json()==[]
    assert client.get('/vacation-rentals',headers=auth(employee),params={'property_type':'fake'}).status_code==422
    assert client.get('/vacation-rentals',headers=auth(employee),params={'limit':101}).status_code==422
