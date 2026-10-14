import uuid,json
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth


def test_plan_recheck_persists_each_item_without_substitution_or_purchase(client):
    employee,_,_,offer=reservation_fixture(client,uuid.uuid4().hex)
    plan=client.post('/itineraries',headers=auth(employee),json={'title':'Mock QA multi-service plan','command_id':uuid.uuid4().hex}).json();pid=plan['id']
    body={'offer_id':offer['id'],'service_type':'hotel','title':'Mock QA hotel','day_number':1,'position':1,'command_id':uuid.uuid4().hex}
    r=client.post('/itineraries/'+pid+'/items',headers=auth(employee),json=body);assert r.status_code==201,r.text
    assert client.post('/itineraries/'+pid+'/items',headers=auth(employee),json={**body,'title':'Different item'}).status_code==409
    client.post('/itineraries/'+pid+'/items',headers=auth(employee),json={'service_type':'train','title':'Customer train plan','day_number':1,'position':2,'command_id':uuid.uuid4().hex})
    endpoint='/itineraries/'+pid+'/recheck';command={'command_id':uuid.uuid4().hex}
    result=client.post(endpoint,headers=auth(employee),json=command);assert result.status_code==200,result.text
    states={i['offer_id']:i['availability_state'] for i in result.json()['items']};assert states=={offer['id']:'DETAILS_REQUIRED',None:'NEEDS_SELECTION'}
    with SessionLocal() as db:
        events=db.scalar(select(func.count()).select_from(m.OutboxEvent).where(m.OutboxEvent.aggregate_id==pid,m.OutboxEvent.event_type=='itinerary.item.rechecked'));assert events==2
        o=db.get(m.Offer,offer['id']);original=o.amount;o.amount+=123;db.commit()
    # Exact retry reuses the previously checked item commands, never emits another audit event.
    assert client.post(endpoint,headers=auth(employee),json=command).status_code==200
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(m.OutboxEvent).where(m.OutboxEvent.aggregate_id==pid,m.OutboxEvent.event_type=='itinerary.item.rechecked'))==2
    changed=next(i for i in client.post(endpoint,headers=auth(employee),json={'command_id':uuid.uuid4().hex}).json()['items'] if i['offer_id']==offer['id'])
    assert changed['availability_state']=='PRICE_CHANGED' and changed['snapshot']['amount']==original and changed['snapshot']['latest_check']['amount']==original+123
    with SessionLocal() as db:db.get(m.Offer,offer['id']).valid_until=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    expired=next(i for i in client.post(endpoint,headers=auth(employee),json={'command_id':uuid.uuid4().hex}).json()['items'] if i['offer_id']==offer['id']);assert expired['availability_state']=='EXPIRED'
    assert expired['offer_id']==offer['id']
    assert client.post(endpoint,headers=auth(login(client,'supplier@aftab.test')),json={'command_id':uuid.uuid4().hex}).status_code==404
