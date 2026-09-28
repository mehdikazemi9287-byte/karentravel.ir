import json, uuid
from sqlalchemy import select
from app.main import SessionLocal
from app import operations as models
from test_checkout_reviews_zarinpal import login, auth


def test_human_reply_replay_has_one_message_notice_audit_and_outbox(client):
    customer=login(client,'employee@aftab.test');ops=login(client,'backoffice@aftab.test')
    case=client.post('/support/cases',headers={**auth(customer),'Idempotency-Key':str(uuid.uuid4())},json={'subject':'Mock ops retry','body':'Isolated request','case_type':'SERVICE_INQUIRY'}).json()
    path='/support/cases/'+case['id']+'/human-replies';h={**auth(ops),'Idempotency-Key':str(uuid.uuid4())};body={'body':'Mock human reply durable'}
    assert client.post(path,headers={**auth(customer),'Idempotency-Key':str(uuid.uuid4())},json=body).status_code==403
    assert client.post(path,headers=h,json={'body':'   '}).status_code==422
    first=client.post(path,headers=h,json=body);assert first.status_code==201,first.text
    assert client.post(path,headers=h,json=body).json()==first.json()
    assert client.post(path,headers=h,json={'body':'Changed reply'}).status_code==409
    with SessionLocal() as db:
        row=db.get(models.SupportCase,case['id']);assert len([e for e in json.loads(row.audit_trail_json) if e['event']=='human_replied'])==1
        assert len(db.scalars(select(models.SupportThreadMessage).where(models.SupportThreadMessage.case_id==row.id,models.SupportThreadMessage.sender_type=='human_agent')).all())==1
        assert len(db.scalars(select(models.NotificationRecord).where(models.NotificationRecord.deep_link=='/support?case='+row.id)).all())==1
        assert len(db.scalars(select(models.OutboxEvent).where(models.OutboxEvent.aggregate_id==row.id,models.OutboxEvent.event_type=='support.human_reply.created')).all())==1
        row.status='closed';db.commit()
    assert client.post(path,headers=h,json=body).json()==first.json()
    assert client.post(path,headers={**auth(ops),'Idempotency-Key':str(uuid.uuid4())},json=body).status_code==409
    assert client.post('/support/cases/'+str(uuid.uuid4())+'/human-replies',headers=h,json=body).status_code==404
