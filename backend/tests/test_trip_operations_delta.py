import uuid
from sqlalchemy import select,func
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_ops_change_reaches_owner_timeline_notification_and_audit_once(client):
    session,reservation,_,_=reservation_fixture(client,uuid.uuid4().hex)
    with SessionLocal() as db:trip_id=db.get(m.Reservation,reservation['id']).trip_id
    ops=login(client,'backoffice@aftab.test');other=login(client,'employee@faraz.test')
    url='/backoffice/trips/'+trip_id+'/changes'
    payload={'command_id':uuid.uuid4().hex,'kind':'flight','before':'Mock QA 10:00','after':'Mock QA 12:00','reason':'Mock QA schedule update','source_reference':'Mock QA reference'}
    assert client.post(url,headers=auth(session),json=payload).status_code==403
    assert client.get('/backoffice/trips',headers=auth(session)).status_code==403
    first=client.post(url,headers=auth(ops),json=payload);assert first.status_code==201,first.text
    assert client.post(url,headers=auth(ops),json=payload).json()['id']==first.json()['id']
    assert client.post(url,headers=auth(ops),json={**payload,'after':'other value'}).status_code==409
    timeline=client.get('/trips/'+trip_id+'/timeline',headers=auth(session));assert first.json()['event_id'] in [e['id'] for e in timeline.json()['events']]
    assert client.get('/trips/'+trip_id+'/timeline',headers=auth(other)).status_code==404
    notice=client.get('/me/notifications',headers=auth(session));assert 'Mock QA 12:00' in notice.text
    audit=client.get(url,headers=auth(ops)).json();assert audit[0]['source_reference']=='Mock QA reference' and audit[0]['actor_id']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(m.NotificationRecord).where(m.NotificationRecord.trip_event_id==first.json()['event_id']))==1
