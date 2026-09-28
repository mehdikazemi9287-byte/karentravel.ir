import json
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from app.main import SessionLocal,User
from app.operations import TourProduct,TourDeparture,Supplier


def test_tour_filter_uses_tehran_day_capacity_deadline_and_tenant(client):
    token=client.post('/auth/dev-login',json={'email':'employee@aftab.test'}).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    now=datetime.now(timezone.utc);day=(now+timedelta(days=60)).date()
    starts=datetime.combine(day,datetime.min.time(),tzinfo=timezone(timedelta(hours=3,minutes=30)))+timedelta(minutes=30)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='employee@aftab.test'))
        supplier=Supplier(tenant_id=user.tenant_id,supplier_type='tour',display_name='Mock isolated tour supplier',status='active');db.add(supplier);db.flush()
        tour=TourProduct(tenant_id=user.tenant_id,supplier_id=supplier.id,title='Mock date boundary tour',slug='mock-filter-tour',origin='تهران',destination='شیراز',tour_type='cultural',status='published',details_json='{}');db.add(tour);db.flush()
        departure=TourDeparture(tenant_id=user.tenant_id,tour_id=tour.id,starts_at=starts.astimezone(timezone.utc),ends_at=(starts+timedelta(days=2)).astimezone(timezone.utc),booking_deadline=now+timedelta(days=50),capacity=2,remaining=2,base_price=1000000,status='active',pricing_json='{}');db.add(departure);db.commit();tid=tour.id;did=departure.id
    path='/tour-products?destination='+ 'شیراز'+'&depart='+day.isoformat()
    assert tid in [x['id'] for x in client.get(path+'&travellers=2',headers=headers).json()]
    assert tid not in [x['id'] for x in client.get(path+'&travellers=3',headers=headers).json()]
    assert tid not in [x['id'] for x in client.get('/tour-products?depart='+(day-timedelta(days=1)).isoformat(),headers=headers).json()]
    assert client.get(path+'&travellers=0',headers=headers).status_code==422
    other=client.post('/auth/dev-login',json={'email':'employee@faraz.test'}).json()['access_token']
    assert tid not in [x['id'] for x in client.get(path+'&travellers=1',headers={'Authorization':'Bearer '+other}).json()]
    with SessionLocal() as db:
        departure=db.get(TourDeparture,did);departure.booking_deadline=now-timedelta(minutes=1);db.commit()
    assert tid not in [x['id'] for x in client.get(path+'&travellers=1',headers=headers).json()]
