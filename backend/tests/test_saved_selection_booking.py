from test_checkout_reviews_zarinpal import hotel_terms
import json,uuid
from sqlalchemy import select
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_saved_selection_booking_scope_replay_and_tracking(client):
    user,_,_,offer=reservation_fixture(client,uuid.uuid4().hex)
    trip=client.post('/saved-trips',headers=auth(user),json={'title':'Mock QA saved booking','command_id':uuid.uuid4().hex}).json()
    path='/saved-trips/'+trip['id']+'/items'
    item_body={'offer_id':offer['id'],'service_type':'hotel','source_reference':'Mock QA hotel','state':'basket','selection':{'adults':'1','rooms':'1','depart':hotel_terms()[1]['check_in'],'return':hotel_terms()[1]['check_out']},'command_id':uuid.uuid4().hex}
    result=client.post(path,headers=auth(user),json=item_body);assert result.status_code==201,result.text
    item=result.json()['items'][0]
    assert item['snapshot']['selection']==item_body['selection'] and not item['snapshot']['authoritative']
    alias={**item_body,'command_id':uuid.uuid4().hex}
    duplicate=client.post(path,headers=auth(user),json=alias);assert len(duplicate.json()['items'])==1
    assert client.post(path,headers=auth(user),json={**alias,'selection':{'adults':'4'}}).status_code==409
    assert client.post(path,headers=auth(user),json={**item_body,'selection':{'adults':'3'}}).status_code==409
    assert client.post(path,headers=auth(user),json={**item_body,'command_id':uuid.uuid4().hex,'selection':{'redirect':'http://internal'}}).status_code==422
    q=client.post('/offers/'+offer['id']+'/price-check',headers=auth(user),json={'hotel_stay':hotel_terms()[1],'units':1,'command_id':uuid.uuid4().hex}).json()
    payload={'price_check_id':q['id'],'command_id':uuid.uuid4().hex,'saved_item_id':item['id']}
    assert client.post('/orchestration/bookings',headers=auth(login(client,'supplier@aftab.test')),json=payload).status_code==404
    with SessionLocal() as db:
        saved=db.get(m.SavedTripItem,item['id']);saved.offer_id=None;db.commit()
    assert client.post('/orchestration/bookings',headers=auth(user),json=payload).status_code==409
    with SessionLocal() as db:db.get(m.SavedTripItem,item['id']).offer_id=offer['id'];db.commit()
    booked=client.post('/orchestration/bookings',headers=auth(user),json=payload);assert booked.status_code==201,booked.text
    assert client.post('/orchestration/bookings',headers=auth(user),json=payload).json()==booked.json()
    assert client.post('/orchestration/bookings',headers=auth(user),json={**payload,'saved_item_id':None}).status_code==409
    q2=client.post('/offers/'+offer['id']+'/price-check',headers=auth(user),json={'hotel_stay':hotel_terms()[1],'units':1,'command_id':uuid.uuid4().hex}).json()
    assert client.post('/orchestration/bookings',headers=auth(user),json={**payload,'command_id':uuid.uuid4().hex,'price_check_id':q2['id']}).status_code==409
    saved=client.get('/me/saved-trips',headers=auth(user)).json()[0]['items'][0]
    assert saved['snapshot']['reservation_id']==booked.json()['id']
    assert client.get('/trips/'+saved['snapshot']['trip_id']+'/timeline',headers=auth(user)).status_code==200
    with SessionLocal() as db:
        events=db.scalars(select(m.OutboxEvent).where(m.OutboxEvent.aggregate_id==trip['id'],m.OutboxEvent.event_type=='saved_trip.item.booked')).all();assert len(events)==1
        assert db.get(m.PriceCheck,q2['id']).consumed_at is None
