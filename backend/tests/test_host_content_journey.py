import json,uuid
from sqlalchemy import select
from app.main import SessionLocal
from app import operations as m
from test_accommodation_marketplace import fixture
from test_checkout_reviews_zarinpal import auth


def test_host_content_scope_revision_replay_and_customer_projection(client):
    employee,supplier,uid,_,_=fixture(client)
    with SessionLocal() as db:
        prop=db.get(m.VacationProperty,db.get(m.VacationUnit,uid).property_id)
        pid=prop.id;original=json.loads(prop.details_json);status=prop.status
    rows=client.get('/supplier/vacation-properties',headers=auth(supplier)).json()
    row=next(r for r in rows if r['id']==pid)
    content={**row['content'],'description':'Mock QA new details','host_name':'Mock QA Host','photos':[{'url':'https://stay-images.invalid/qa.png','alt':'Mock QA'}],'amenities':['پارکینگ']}
    body={'command_id':uuid.uuid4().hex,'revision':row['revision'],'content':content};path='/supplier/vacation-properties/'+pid+'/content'
    assert client.get('/supplier/vacation-properties',headers=auth(employee)).status_code==403
    assert client.put(path,headers=auth(employee),json=body).status_code==403
    result=client.put(path,headers=auth(supplier),json=body);assert result.status_code==200,result.text
    assert client.put(path,headers=auth(supplier),json=body).json()==result.json()
    assert client.put(path,headers=auth(supplier),json={**body,'command_id':uuid.uuid4().hex}).status_code==409
    assert client.put(path,headers=auth(supplier),json={**body,'content':{**content,'host_name':'another'}}).status_code==409
    fresh={**body,'command_id':uuid.uuid4().hex,'revision':result.json()['revision']}
    for change in [{'nightly_price':1},{'booking_mode':'INSTANT_BOOKING'},{'photos':[{'url':'https://127.0.0.1/private'}]},{'photos':[{'url':'http://example.com/a'}]},{'amenities':['x'*161]}]:
        assert client.put(path,headers=auth(supplier),json={**fresh,'content':{**content,**change}}).status_code==422
    detail=client.get('/vacation-rentals/'+pid,headers=auth(employee)).json()
    assert detail['details']['host_name']=='Mock QA Host'
    assert client.get('/public/vacation-rentals/'+pid).status_code in (404,503)
    with SessionLocal() as db:
        prop=db.get(m.VacationProperty,pid);details=json.loads(prop.details_json)
        assert prop.status==status and details['cancellation_policy']==original['cancellation_policy'] and details['booking_mode']==original['booking_mode']
        assert db.get(m.VacationUnit,uid).nightly_price==1000000
        events=db.scalars(select(m.OutboxEvent).where(m.OutboxEvent.aggregate_id==pid,m.OutboxEvent.event_type=='vacation_content.changed')).all();assert len(events)==1
        assert json.loads(events[0].payload_json)['new']['host_name']=='Mock QA Host'
        old_supplier=prop.supplier_id
        other=m.Supplier(tenant_id=prop.tenant_id,supplier_type='vacation_rental',display_name='Mock unassigned',status='active');db.add(other);db.flush();prop.supplier_id=other.id;db.commit()
    assert client.put(path,headers=auth(supplier),json=body).status_code==403
    assert pid not in [r['id'] for r in client.get('/supplier/vacation-properties',headers=auth(supplier)).json()]
