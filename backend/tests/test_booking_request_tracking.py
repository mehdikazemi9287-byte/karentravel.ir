import uuid
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_request_history_is_owned_and_retries_do_not_create_another_request(client):
    user,reservation,_,_=reservation_fixture(client,uuid.uuid4().hex)
    path='/reservations/'+reservation['id']+'/service-requests'
    key=str(uuid.uuid4());h={**auth(user),'Idempotency-Key':key};body={'request_type':'cancel','reason':'Mock passenger request'}
    first=client.post(path,headers=h,json=body);assert first.status_code==202,first.text
    assert client.post(path,headers=h,json=body).json()==first.json()
    other=login(client,'supplier@aftab.test')
    assert client.post(path,headers={**auth(other),'Idempotency-Key':key},json=body).status_code==404
    assert client.get(path,headers=auth(other)).status_code==404
    assert client.post(path,headers=h,json={**body,'reason':'Different reason'}).status_code==409
    assert client.post(path,headers={**auth(user),'Idempotency-Key':str(uuid.uuid4())},json=body).status_code==409
    rows=client.get(path,headers=auth(user)).json();assert len(rows)==1;assert rows[0]['id']==first.json()['id'];assert rows[0]['status']=='submitted'
    assert client.get('/reservations/'+reservation['id'],headers=auth(user)).json()['status']=='cancel_requested'

    ops=login(client,'backoffice@aftab.test');review='/backoffice/booking-requests/'+first.json()['id']+'/review'
    assert client.get('/backoffice/booking-requests',headers=auth(user)).status_code==403
    assert client.post(review,headers=auth(user),json={}).status_code==403
    assert any(x['id']==first.json()['id'] for x in client.get('/backoffice/booking-requests',headers=auth(ops)).json()['items'])
    assert client.post(review,headers=auth(ops),json={}).json()['status']=='under_review'
    assert client.post(review,headers=auth(ops),json={}).json()['status']=='under_review'
    assert client.get(path,headers=auth(user)).json()[0]['status']=='under_review'
    assert client.post(path,headers={**auth(user),'Idempotency-Key':str(uuid.uuid4())},json=body).status_code==409
    from app.main import SessionLocal
    from app import operations as models
    from sqlalchemy import select
    with SessionLocal() as db:
        events=db.scalars(select(models.OutboxEvent).where(models.OutboxEvent.aggregate_id==reservation['id'],models.OutboxEvent.event_type=='service_request.review_started')).all()
        assert len(events)==1
        assert db.get(models.Reservation,reservation['id']).status=='cancel_requested'
