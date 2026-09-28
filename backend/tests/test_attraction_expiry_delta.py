import uuid
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
from test_leisure_commerce import login,auth,supplier,make_place,make_product,make_ticket_type,price_check,book

def test_attraction_cannot_bypass_ticket_or_book_closed_session(client):
    owner=login(client,'supplier@aftab.test');h=auth(owner['access_token']);sid=supplier(client,h,kind='attraction');place=make_place(client,h,sid,place_type='attraction');product=make_product(client,h,place['id'],service_type='attraction',booking_mode='TIMED_ENTRY');ticket=make_ticket_type(client,h,product['id']);now=datetime.now(timezone.utc);end=now+timedelta(minutes=2)
    slot=client.post('/supplier/experience-products/'+product['id']+'/sessions',headers=h,json={'starts_at':(now-timedelta(minutes=1)).isoformat(),'ends_at':end.isoformat(),'capacity_total':2}).json();customer=login(client,'employee@aftab.test');ch=auth(customer['access_token'])
    with SessionLocal() as db:offer=db.get(m.LeisureSession,slot['id']).offer_id
    detail=client.get('/offers/'+offer,headers=ch);assert detail.json()['booking_detail_url']=='/experience-products/'+product['id']
    assert client.post('/offers/'+offer+'/price-check',headers=ch,json={'units':1,'command_id':uuid.uuid4().hex}).status_code==409
    pc=price_check(client,ch,slot['id'],[{'ticket_type_id':ticket['id'],'quantity':1}]);assert pc.status_code==201,pc.text
    assert datetime.fromisoformat(pc.json()['expires_at'])<=end
    with SessionLocal() as db:db.get(m.LeisureSession,slot['id']).ends_at=now-timedelta(seconds=1);db.commit()
    result=book(client,ch,pc.json()['id']);assert result.status_code==409,result.text
    with SessionLocal() as db:assert db.get(m.PriceCheck,pc.json()['id']).consumed_at is None
