import json,uuid
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,auth,login

def test_car_allotment_requires_terms_and_future_period_and_rechecks(client):
    session,_,traveller,offer=reservation_fixture(client,uuid.uuid4().hex);now=datetime.now(timezone.utc)
    attrs={k:'Mock QA contract' for k in ['city','vehicle_class','pickup_location','return_location','deposit_terms','license_terms','insurance_terms','mileage_terms']};attrs.update(rental_start=(now+timedelta(days=3)).isoformat(),rental_end=(now+timedelta(days=5)).isoformat())
    with SessionLocal() as db:
        row=db.get(m.Offer,offer['id']);row.service_type='car_rental';row.attributes_json=json.dumps(attrs);db.commit();sid=row.supplier_id;policy=json.loads(row.policy_json)
    payload={'supplier_id':sid,'service_type':'car_rental','title':'Mock QA Car','amount':1000000,'available_units':1,'valid_minutes':60,'policy':policy,'attributes':{**attrs,'license_terms':''},'fulfillment_mode':'manual_supplier','provider_key':'manual_supplier'}
    assert client.post('/supplier/offers',headers=auth(login(client,'supplier@aftab.test')),json=payload).status_code==409
    detail=client.get('/offers/'+offer['id'],headers=auth(session));assert detail.json()['attributes']['deposit_terms']==attrs['deposit_terms']
    check=client.post('/offers/'+offer['id']+'/price-check',headers=auth(session),json={'units':1,'command_id':uuid.uuid4().hex}).json();booking=client.post('/orchestration/bookings',headers=auth(session),json={'price_check_id':check['id'],'command_id':uuid.uuid4().hex}).json();checkout=client.post('/reservations/'+booking['id']+'/checkout-sessions',headers=auth(session),json={'command_id':uuid.uuid4().hex}).json();url='/checkout-sessions/'+checkout['id']+'/steps/'
    assert client.put(url+'traveller',headers=auth(session),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id']]}).status_code==200
    assert client.put(url+'recheck',headers=auth(session),json={'command_id':uuid.uuid4().hex}).status_code==200
    with SessionLocal() as db:
        row=db.get(m.Offer,offer['id']);attrs['rental_start']=(now-timedelta(hours=1)).isoformat();row.attributes_json=json.dumps(attrs);db.commit()
    assert client.post('/offers/'+offer['id']+'/price-check',headers=auth(session),json={'units':1,'command_id':uuid.uuid4().hex}).status_code==409
