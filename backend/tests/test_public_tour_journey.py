import json,uuid
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth
from test_search_v2_public import _seed_public_tenant


def test_tour_room_contract_deadline_and_public_projection(client):
    employee,_,_,offer=reservation_fixture(client,uuid.uuid4().hex)
    supplier=login(client,'supplier@aftab.test');now=datetime.now(timezone.utc)
    with SessionLocal() as db:sid=db.get(m.Offer,offer['id']).supplier_id
    data={'supplier_id':sid,'title':'Mock QA Tour','slug':'qa-'+uuid.uuid4().hex,'origin':'تهران','destination':'شیراز','tour_type':'cultural','details':{'description':'Mock QA','itinerary':[{'title':'Mock day','internal_note':'private'}],'private_contract':'hidden'}}
    tour=client.post('/supplier/tours',headers=auth(supplier),json=data).json();tid=tour['id']
    dates={'starts_at':(now+timedelta(days=10)).isoformat(),'ends_at':(now+timedelta(days=12)).isoformat(),'booking_deadline':(now+timedelta(days=9)).isoformat(),'capacity':5,'base_price':1000000,'pricing':{'single_surcharge':200000,'triple_surcharge':False}}
    departure=client.post('/supplier/tours/'+tid+'/departures',headers=auth(supplier),json=dates).json();did=departure['id']
    detail=client.get('/tour-products/'+tid,headers=auth(employee)).json()
    assert detail['departures'][0]['available_room_types']==['double','single']
    url='/tour-departures/'+did
    for room in ['triple','extra_bed']:
        assert client.get(url+'/quote',headers=auth(employee),params={'room_type':room}).status_code==409
        assert client.post(url+'/reservations',headers=auth(employee),json={'travellers':1,'room_type':room,'command_id':uuid.uuid4().hex}).status_code==409
    assert client.get(url+'/quote?travellers=2&room_type=single',headers=auth(employee)).json()['total_amount']==2400000
    with SessionLocal() as db:
        d=db.get(m.TourDeparture,did);d.pricing_json=json.dumps({'triple_surcharge':0});db.commit()
    assert client.get(url+'/quote?travellers=2&room_type=triple',headers=auth(employee)).json()['total_amount']==2000000
    with SessionLocal() as db:db.get(m.TourDeparture,did).booking_deadline=now-timedelta(seconds=1);db.commit()
    assert client.get('/tour-products/'+tid,headers=auth(employee)).json()['departures']==[]
    assert client.get(url+'/quote',headers=auth(employee)).status_code==409
    tenant=_seed_public_tenant()
    assert client.get('/public/tour-products/'+tid).status_code==404
    with SessionLocal() as db:
        s=m.Supplier(tenant_id=tenant,supplier_type='tour',display_name='Mock QA public',status='active');db.add(s);db.flush()
        t=m.TourProduct(tenant_id=tenant,supplier_id=s.id,title='Mock QA public tour',slug=uuid.uuid4().hex,origin='تهران',destination='شیراز',tour_type='cultural',status='published',details_json=json.dumps(data['details']));db.add(t);db.flush();public_id=t.id
        db.add(m.TourDeparture(tenant_id=tenant,tour_id=t.id,starts_at=now+timedelta(days=10),ends_at=now+timedelta(days=12),booking_deadline=now+timedelta(days=9),capacity=5,remaining=5,base_price=1000000));db.commit()
    public=client.get('/public/tour-products/'+public_id).json()
    assert public['account_recheck_required'] and 'base_price' not in str(public) and 'private' not in str(public)
    assert set(public['departures'][0])=={'id','starts_at','ends_at'}
    assert [r['id'] for r in client.get('/public/tour-products').json()]==[public_id]
    assert client.get('/tour-products/'+public_id,headers=auth(employee)).status_code==404
