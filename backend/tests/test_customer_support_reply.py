import json,uuid
from app.main import SessionLocal
from app import operations as models
from test_checkout_reviews_zarinpal import login,auth


def test_customer_case_reply_is_owned_atomic_and_replayable(client):
    user=login(client,'employee@aftab.test');other=login(client,'supplier@aftab.test');ops=login(client,'backoffice@aftab.test')
    h={**auth(user),'Idempotency-Key':str(uuid.uuid4())}
    c=client.post('/support/cases',headers=h,json={'subject':'Mock reply test','body':'isolated inquiry','case_type':'SERVICE_INQUIRY'}).json();path='/support/cases/'+c['id']
    assert client.get(path,headers=auth(other)).status_code==404
    assert client.get(path,headers=auth(ops)).status_code==200
    reply=path+'/customer-replies';payload={'body':'Mock additional details'}
    assert client.post(reply,headers={**auth(other),'Idempotency-Key':str(uuid.uuid4())},json=payload).status_code==404
    first=client.post(reply,headers=h,json=payload);assert first.status_code==201,first.text
    assert client.post(reply,headers=h,json=payload).json()['id']==first.json()['id']
    assert client.post(reply,headers=h,json={'body':'Different message'}).status_code==409
    with SessionLocal() as db:
        row=db.get(models.SupportCase,c['id']);assert len([x for x in json.loads(row.audit_trail_json) if x['event']=='customer_replied'])==1
        row.status='closed';db.commit()
    assert client.post(reply,headers=h,json=payload).json()['id']==first.json()['id']
    assert client.post(reply,headers={**h,'Idempotency-Key':str(uuid.uuid4())},json=payload).status_code==409
    detail=client.get(path,headers=auth(user)).json();assert len(detail['messages'])==2
    assert detail['messages'][-1]['sender_type']=='customer'
