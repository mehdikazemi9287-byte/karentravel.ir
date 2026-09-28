import json,uuid
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,auth,login

def test_guide_contract_and_group_capacity(client):
    customer,_,traveller,offer=reservation_fixture(client,uuid.uuid4().hex);now=datetime.now(timezone.utc)
    attrs={k:'Mock QA' for k in ['city','guide_name','languages','meeting_point','inclusions','exclusions']};attrs.update(group_capacity='1',departure_time=(now+timedelta(days=3)).isoformat(),arrival_time=(now+timedelta(days=3,hours=2)).isoformat())
    with SessionLocal() as db:
        row=db.get(m.Offer,offer['id']);row.service_type='travel_guide';row.attributes_json=json.dumps(attrs);db.commit();sid=row.supplier_id;policy=json.loads(row.policy_json)
    invalid={'supplier_id':sid,'service_type':'travel_guide','title':'Mock QA Guide','amount':1000000,'available_units':1,'valid_minutes':60,'policy':policy,'attributes':{**attrs,'languages':''},'fulfillment_mode':'manual_supplier','provider_key':'manual_supplier'}
    assert client.post('/supplier/offers',headers=auth(login(client,'supplier@aftab.test')),json=invalid).status_code==409
    assert client.get('/offers/'+offer['id'],headers=auth(customer)).json()['attributes']['languages']=='Mock QA'
    pc=client.post('/offers/'+offer['id']+'/price-check',headers=auth(customer),json={'units':1,'command_id':uuid.uuid4().hex}).json();r=client.post('/orchestration/bookings',headers=auth(customer),json={'price_check_id':pc['id'],'command_id':uuid.uuid4().hex}).json();cs=client.post('/reservations/'+r['id']+'/checkout-sessions',headers=auth(customer),json={'command_id':uuid.uuid4().hex}).json();step='/checkout-sessions/'+cs['id']+'/steps/'
    second=client.post('/me/travellers',headers=auth(customer),json={'full_name':'Mock QA second'}).json()
    assert client.put(step+'traveller',headers=auth(customer),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id'],second['id']]}).status_code==422
    assert client.put(step+'traveller',headers=auth(customer),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id']]}).status_code==200
    assert client.put(step+'recheck',headers=auth(customer),json={'command_id':uuid.uuid4().hex}).status_code==200
    with SessionLocal() as db:
        booking=db.get(m.Reservation,r['id']);assert db.get(m.Trip,booking.trip_id).starts_at is not None
