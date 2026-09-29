import uuid,json
from datetime import datetime,timezone
from sqlalchemy import select
from app.main import SessionLocal,User
from app import operations as m
from test_leisure_commerce import login,auth,supplier,make_place,make_ticket_type,make_session,price_check,book

def test_mixed_restaurant_checkout_qr_ownership_and_single_use(client):
    owner=login(client,'supplier@aftab.test');customer=login(client,'employee@aftab.test');oh=auth(owner['access_token']);ch=auth(customer['access_token']);sid=supplier(client,oh,kind='restaurant');place=make_place(client,oh,sid,place_type='restaurant')
    policy={'verified':True,'source':'Mock QA contract','verified_at':datetime.now(timezone.utc).isoformat(),'cancellation':{'refundable':False,'description':'Mock QA no refund'}}
    product=client.post('/supplier/places/'+place['id']+'/experience-products',headers=oh,json={'service_type':'restaurant','title':'Mock QA dining','booking_mode':'SESSION_BASED','cancellation_policy':policy}).json()
    a=make_ticket_type(client,oh,product['id'],code='adult',price=500000,quota=1);b=make_ticket_type(client,oh,product['id'],code='child',price=200000);slot=make_session(client,oh,product['id'],capacity=4)
    selections=[{'ticket_type_id':a['id'],'quantity':1},{'ticket_type_id':b['id'],'quantity':1}];command=uuid.uuid4().hex;quoted=price_check(client,ch,slot['id'],selections,command_id=command);assert quoted.status_code==201
    assert price_check(client,ch,slot['id'],[selections[0]],command_id=command).status_code==409
    r=book(client,ch,quoted.json()['id']).json();traveller=client.post('/me/travellers',headers=ch,json={'full_name':'Mock QA diner'}).json();cs=client.post('/reservations/'+r['id']+'/checkout-sessions',headers=ch,json={'command_id':uuid.uuid4().hex}).json();step='/checkout-sessions/'+cs['id']+'/steps/'
    assert client.put(step+'traveller',headers=ch,json={'command_id':uuid.uuid4().hex,'traveller_ids':[traveller['id']]}).status_code==200
    checked=client.put(step+'recheck',headers=ch,json={'command_id':uuid.uuid4().hex});assert checked.status_code==200,checked.text
    assert checked.json()['reservation']['price_snapshot']['total_amount']==700000
    assert price_check(client,ch,slot['id'],[selections[0]]).status_code==409
    email='unassigned-'+uuid.uuid4().hex+'@qa.invalid'
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='employee@aftab.test'));db.add(User(tenant_id=user.tenant_id,email=email,name='Mock QA other supplier',role='supplier'));db.add(m.PaymentIntent(tenant_id=user.tenant_id,user_id=user.id,reservation_id=r['id'],command_id=uuid.uuid4().hex,amount=700000,captured_amount=700000,status='captured',currency='IRR',provider_key='mock'));db.commit()
    other=login(client,email);xh=auth(other['access_token'])
    assert client.post('/supplier/experience-products/'+product['id']+'/sessions',headers=xh,json={'starts_at':slot['starts_at'],'ends_at':slot['ends_at'],'capacity_total':1}).status_code==403
    issued=client.post('/reservations/'+r['id']+'/fulfill',headers=oh,json={'command_id':uuid.uuid4().hex,'provider_reference':'MockQA-dining','document_reference':'document://mock-qa-dining'}).json();ticket=issued['admission_ticket'];qr='/reservations/'+r['id']+'/admission-tickets/'+ticket['id']+'/qr'
    svg=client.get(qr,headers=ch);assert svg.status_code==200 and '<svg' in svg.text and 'path' in svg.text
    assert client.get(qr,headers=xh).status_code==404
    assert client.get('/admission-tickets/validate',headers=xh,params={'qr_token':ticket['qr_token']}).status_code==403
    assert client.post('/admission-tickets/redeem',headers=xh,json={'qr_token':ticket['qr_token']}).status_code==403
    validated=client.post('/admission-tickets/validate',headers=oh,json={'qr_token':ticket['qr_token']})
    assert validated.status_code==200 and validated.headers['cache-control']=='no-store'
    context=validated.json()['context'];assert context['scope']=='whole_reservation' and context['product_title']=='Mock QA dining'
    assert context['place']['name']==place['name'] and sum(i['quantity'] for i in context['items'])==2
    assert 'qr_token' not in validated.text and 'price' not in str(context)
    assert client.post('/admission-tickets/validate',headers=xh,json={'qr_token':ticket['qr_token']}).status_code==403
    assert client.post('/admission-tickets/validate',headers=ch,json={'qr_token':ticket['qr_token']}).status_code==403
    mismatch=client.post('/admission-tickets/redeem',headers=oh,json={'qr_token':ticket['qr_token'],'expected_ticket_id':str(uuid.uuid4())})
    assert mismatch.status_code==409 and mismatch.json()['detail']['code']=='TICKET_CHANGED'
    assert client.post('/admission-tickets/validate',headers=oh,json={'qr_token':ticket['qr_token']}).json()['status']=='issued'
    owned=client.get('/reservations/'+r['id']+'/admission-tickets',headers=ch).json()
    assert owned['context']['items']==context['items']
    assert client.post('/admission-tickets/redeem',headers=oh,json={'qr_token':ticket['qr_token'],'expected_ticket_id':ticket['id']}).status_code==200
    assert client.post('/admission-tickets/redeem',headers=oh,json={'qr_token':ticket['qr_token']}).status_code==409
    assert client.get(qr,headers=ch).status_code==404
    with SessionLocal() as db:
        event=db.scalar(select(m.OutboxEvent).where(m.OutboxEvent.event_type=='admission_ticket.redeemed',m.OutboxEvent.aggregate_id==ticket['id']));assert event and json.loads(event.payload_json)['actor_id']
        assert len(db.scalars(select(m.OutboxEvent).where(m.OutboxEvent.event_type=='admission_ticket.redeemed',m.OutboxEvent.aggregate_id==ticket['id'])).all())==1
