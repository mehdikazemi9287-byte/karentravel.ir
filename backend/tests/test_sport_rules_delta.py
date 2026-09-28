import json,uuid
from datetime import datetime,timezone
from app.main import SessionLocal
from app import operations as m
from test_leisure_commerce import login,auth,supplier,make_place,make_ticket_type,make_session,price_check,book

def test_sport_entry_rules_are_frozen_and_visible_in_checkout(client):
    owner=login(client,'supplier@aftab.test');h=auth(owner['access_token']);sid=supplier(client,h);place=make_place(client,h,sid)
    policy={'verified':True,'source':'Mock QA contract','verified_at':datetime.now(timezone.utc).isoformat(),'cancellation':{'refundable':False}}
    product=client.post('/supplier/places/'+place['id']+'/experience-products',headers=h,json={'service_type':'pool_sport','title':'Mock QA sport','booking_mode':'SESSION_BASED','cancellation_policy':policy,'restrictions':{'entry_rules':['Mock QA product rule']}}).json();ticket=make_ticket_type(client,h,product['id']);slot=make_session(client,h,product['id'])
    with SessionLocal() as db:db.get(m.LeisureSession,slot['id']).restrictions_json=json.dumps({'entry_rules':['Mock QA session rule']});db.commit()
    customer=login(client,'employee@aftab.test');ch=auth(customer['access_token']);pc=price_check(client,ch,slot['id'],[{'ticket_type_id':ticket['id'],'quantity':1}]).json();r=book(client,ch,pc['id']).json()
    with SessionLocal() as db:db.get(m.ExperienceProduct,product['id']).restrictions_json=json.dumps({'entry_rules':['Mock QA changed after booking']});db.commit()
    cs=client.post('/reservations/'+r['id']+'/checkout-sessions',headers=ch,json={'command_id':uuid.uuid4().hex});assert cs.status_code==201,cs.text
    assert cs.json()['reservation']['policy_at_booking']['entry_requirements']==['Mock QA product rule','Mock QA session rule']
