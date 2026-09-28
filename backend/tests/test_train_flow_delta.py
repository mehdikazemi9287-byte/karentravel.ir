import json,uuid
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,auth,login

def test_train_schedule_and_one_traveller_per_seat(client):
    session,_,traveller,offer=reservation_fixture(client,uuid.uuid4().hex)
    attrs={'origin':'تهران','destination':'مشهد','departure_time':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'rail_operator':'Mock QA rail','train_number':'123','seat_class':'Mock QA seat'}
    with SessionLocal() as db:
        row=db.get(m.Offer,offer['id']);row.service_type='train';row.attributes_json=json.dumps(attrs);db.commit();supplier_id=row.supplier_id;policy=json.loads(row.policy_json)
    invalid=client.post('/supplier/offers',headers=auth(login(client,'supplier@aftab.test')),json={'supplier_id':supplier_id,'service_type':'train','title':'Mock QA invalid','amount':1000,'available_units':1,'valid_minutes':60,'policy':policy,'attributes':{},'fulfillment_mode':'manual_supplier','provider_key':'manual_supplier'})
    assert invalid.status_code==409
    check=client.post('/offers/'+offer['id']+'/price-check',headers=auth(session),json={'units':2,'command_id':uuid.uuid4().hex}).json()
    booking=client.post('/orchestration/bookings',headers=auth(session),json={'price_check_id':check['id'],'command_id':uuid.uuid4().hex}).json()
    checkout=client.post('/reservations/'+booking['id']+'/checkout-sessions',headers=auth(session),json={'command_id':uuid.uuid4().hex}).json();url='/checkout-sessions/'+checkout['id']+'/steps/traveller'
    assert client.put(url,headers=auth(session),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id']]}).status_code==422
    second=client.post('/me/travellers',headers=auth(session),json={'full_name':'Mock QA second passenger'}).json()
    assert client.put(url,headers=auth(session),json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id'],second['id']]}).status_code==200
    with SessionLocal() as db:
        row=db.get(m.Offer,offer['id']);attrs['departure_time']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat();row.attributes_json=json.dumps(attrs);db.commit()
    assert client.post('/offers/'+offer['id']+'/price-check',headers=auth(session),json={'units':1,'command_id':uuid.uuid4().hex}).status_code==409
    assert client.put('/checkout-sessions/'+checkout['id']+'/steps/recheck',headers=auth(session),json={'command_id':uuid.uuid4().hex}).status_code==409
