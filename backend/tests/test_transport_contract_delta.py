import json,uuid
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,auth,login

def test_transport_contract_seats_and_pickup_voucher(client):
    customer,_,traveller,offer=reservation_fixture(client,uuid.uuid4().hex);now=datetime.now(timezone.utc)
    attrs={k:'Mock QA' for k in ['origin','destination','transport_operator','vehicle_class','pickup_point','dropoff_point','luggage_terms','accessibility_terms']};attrs.update(seats_per_vehicle='1',origin='تهران',destination='شیراز',pickup_point='Mock QA pickup',dropoff_point='Mock QA dropoff',departure_time=(now+timedelta(days=3)).isoformat(),arrival_time=(now+timedelta(days=3,hours=2)).isoformat())
    with SessionLocal() as db:
        row=db.get(m.Offer,offer['id']);row.service_type='tourist_transportation';row.attributes_json=json.dumps(attrs);db.commit();sid=row.supplier_id;policy=json.loads(row.policy_json)
    invalid={'supplier_id':sid,'service_type':'tourist_transportation','title':'Mock QA Transport','amount':1000000,'available_units':1,'valid_minutes':60,'policy':policy,'attributes':{**attrs,'luggage_terms':''},'fulfillment_mode':'manual_supplier','provider_key':'manual_supplier'}
    assert client.post('/supplier/offers',headers=auth(login(client,'supplier@aftab.test')),json=invalid).status_code==409
    assert client.get('/offers/'+offer['id'],headers=auth(customer)).json()['attributes']['luggage_terms']=='Mock QA'
    pc=client.post('/offers/'+offer['id']+'/price-check',headers=auth(customer),json={'units':1,'command_id':uuid.uuid4().hex}).json();r=client.post('/orchestration/bookings',headers=auth(customer),json={'price_check_id':pc['id'],'command_id':uuid.uuid4().hex}).json();cs=client.post('/reservations/'+r['id']+'/checkout-sessions',headers=auth(customer),json={'command_id':uuid.uuid4().hex}).json();step='/checkout-sessions/'+cs['id']+'/steps/'
    second=client.post('/me/travellers',headers=auth(customer),json={'full_name':'Mock QA second'}).json()
    assert client.put(step+'traveller',headers=auth(customer),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id'],second['id']]}).status_code==422
    assert client.put(step+'traveller',headers=auth(customer),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id']]}).status_code==200
    assert client.put(step+'recheck',headers=auth(customer),json={'command_id':uuid.uuid4().hex}).status_code==200
    with SessionLocal() as db:
        booking=db.get(m.Reservation,r['id']);assert db.get(m.Trip,booking.trip_id).starts_at is not None

    with SessionLocal() as db:
        booking=db.get(m.Reservation,r['id']);assert db.get(m.Trip,booking.trip_id).origin=='تهران';db.add(m.PaymentIntent(tenant_id=booking.tenant_id,user_id=booking.user_id,reservation_id=booking.id,command_id=uuid.uuid4().hex,amount=pc['amount'],captured_amount=pc['amount'],currency='IRR',provider_key='mock',status='captured'));db.commit()
    issued=client.post('/reservations/'+r['id']+'/fulfill',headers=auth(login(client,'supplier@aftab.test')),json={'command_id':uuid.uuid4().hex,'provider_reference':'MockQA-transport','document_reference':'document://mock-qa-transport'});assert issued.status_code==200,issued.text
    document=client.get('/reservations/'+r['id']+'/voucher',headers=auth(customer));assert document.status_code==200 and 'Mock QA pickup' in document.text and 'Mock QA dropoff' in document.text
