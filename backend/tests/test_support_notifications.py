import uuid
from sqlalchemy import select
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import login,auth


def test_support_reply_creates_only_inapp_notice_and_owned_read_is_idempotent(client):
    user=login(client,'employee@aftab.test');other=login(client,'supplier@aftab.test');ops=login(client,'backoffice@aftab.test')
    case=client.post('/support/cases',headers={**auth(user),'Idempotency-Key':str(uuid.uuid4())},json={'subject':'Mock notice case '+uuid.uuid4().hex,'body':'isolated request','case_type':'SERVICE_INQUIRY'}).json()
    reply=client.post('/support/cases/'+case['id']+'/human-replies',headers=auth(ops),json={'body':'Mock human response'})
    assert reply.status_code==201,reply.text
    notices=client.get('/me/notifications',headers=auth(user)).json();matching=[n for n in notices if n['deep_link']=='/support?case='+case['id']]
    assert len(matching)==1;notice=matching[0]
    assert notice['title']=='پاسخ تازهٔ پشتیبانی' and case['subject'] in notice['message']
    with SessionLocal() as db:
        attempts=db.scalars(select(m.NotificationDeliveryAttempt).where(m.NotificationDeliveryAttempt.notification_id==notice['id'])).all()
        assert {a.channel for a in attempts}=={'web','app'}
        assert all(a.status=='delivered' for a in attempts)
        event=db.scalar(select(m.NotificationEvent).where(m.NotificationEvent.dedupe_key=='support-reply:'+reply.json()['id']))
        assert db.scalar(select(m.OutboxEvent.id).where(m.OutboxEvent.aggregate_type=='notification',m.OutboxEvent.aggregate_id==event.id)) is None
        assert m.emit_notification_event(db,tenant_id=event.tenant_id,event_type=event.event_type,recipient_user_id=event.recipient_user_id,payload={},dedupe_key=event.dedupe_key,channels=('web','app')).id==event.id
    path='/me/notifications/'+notice['id']+'/read'
    assert client.post(path,headers=auth(other),json={}).status_code==404
    for _ in range(2):assert client.post(path,headers=auth(user),json={}).json()['status']=='read'
    assert next(n for n in client.get('/me/notifications',headers=auth(user)).json() if n['id']==notice['id'])['status']=='read'


def test_worker_does_not_erase_read_acknowledgement():
    import json
    from app.outbox_worker import process_batch
    class IsolatedPublish:
        def execute(self,*args,**kwargs):return {"ok":True}
    with SessionLocal() as db:
        row=m.NotificationRecord(tenant_id=1,user_id=1,topic='account_activity',title='Mock read race guard',message='isolated worker test',status='read');db.add(row);db.flush();nid=row.id
        db.add(m.OutboxEvent(tenant_id=1,aggregate_type='notification',aggregate_id=nid,event_type='notification.qa_read_guard',payload_json=json.dumps({'notification_id':nid})));db.commit()
    process_batch(limit=1000,adapter=IsolatedPublish())
    with SessionLocal() as db:assert db.get(m.NotificationRecord,nid).status=='read'
