import uuid
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as models
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth
from test_leisure_commerce import supplier,make_place,make_product,make_ticket_type,make_session


def test_booking_retry_is_same_owner_not_only_same_tenant(client):
    suffix=uuid.uuid4().hex
    employee,reservation,_,_=reservation_fixture(client,suffix)
    with SessionLocal() as db:
        price_check_id=db.get(models.Reservation,reservation['id']).price_check_id
    body={'price_check_id':price_check_id,'command_id':'checkout-booking-'+suffix}
    replay=client.post('/orchestration/bookings',headers=auth(employee),json=body)
    assert replay.status_code==201 and replay.json()['id']==reservation['id']
    other=login(client,'supplier@aftab.test')
    assert client.post('/orchestration/bookings',headers=auth(other),json=body).status_code==404


def test_restaurant_detail_filters_the_same_tehran_calendar_day(client):
    s=login(client,'supplier@aftab.test');h=auth(s)
    sid=supplier(client,h,'restaurant');place=make_place(client,h,sid,'restaurant');product=make_product(client,h,place['id'],'restaurant');make_ticket_type(client,h,product['id']);slot=make_session(client,h,product['id'])
    day=(datetime.now(timezone.utc)+timedelta(days=8)).date()
    starts=datetime.combine(day,datetime.min.time(),tzinfo=timezone(timedelta(hours=3,minutes=30)))+timedelta(minutes=30)
    with SessionLocal() as db:
        row=db.get(models.LeisureSession,slot['id']);row.starts_at=starts.astimezone(timezone.utc);row.ends_at=(starts+timedelta(hours=2)).astimezone(timezone.utc);db.commit()
    customer=login(client,'employee@aftab.test')
    path='/experience-products/'+product['id']+'?date='
    assert [r['id'] for r in client.get(path+day.isoformat(),headers=auth(customer)).json()['sessions']]==[slot['id']]
    assert client.get(path+(day-timedelta(days=1)).isoformat(),headers=auth(customer)).json()['sessions']==[]
