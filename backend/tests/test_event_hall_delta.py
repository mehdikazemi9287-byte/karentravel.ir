from datetime import datetime,timedelta,timezone
from test_leisure_commerce import login,auth,supplier,make_place,make_product,make_ticket_type

def test_whole_venue_exclusivity_and_inquiry_cannot_charge(client):
    owner=login(client,'supplier@aftab.test');h=auth(owner['access_token']);sid=supplier(client,h,kind='event_hall');place=make_place(client,h,sid,place_type='event_hall');product=make_product(client,h,place['id'],service_type='event_hall',booking_mode='FIXED_PACKAGE');now=datetime.now(timezone.utc);payload={'starts_at':(now+timedelta(days=2)).isoformat(),'ends_at':(now+timedelta(days=2,hours=3)).isoformat(),'capacity_total':1};url='/supplier/experience-products/'+product['id']+'/sessions'
    assert client.post(url,headers=h,json={**payload,'capacity_total':2}).status_code==422
    assert client.post(url,headers=h,json=payload).status_code==201
    assert client.post(url,headers=h,json=payload).status_code==409
    adjacent={**payload,'starts_at':payload['ends_at'],'ends_at':(now+timedelta(days=2,hours=6)).isoformat()};assert client.post(url,headers=h,json=adjacent).status_code==201
    inquiry=make_product(client,h,place['id'],service_type='event_hall',booking_mode='VENUE_INQUIRY');ticket=make_ticket_type(client,h,inquiry['id']);session=client.post('/supplier/experience-products/'+inquiry['id']+'/sessions',headers=h,json={**payload,'starts_at':(now+timedelta(days=5)).isoformat(),'ends_at':(now+timedelta(days=6)).isoformat()}).json()
    user=login(client,'employee@aftab.test');r=client.post('/leisure-sessions/'+session['id']+'/price-check',headers=auth(user['access_token']),json={'command_id':'mock-qa-venue-inquiry','selections':[{'ticket_type_id':ticket['id'],'quantity':1}]});assert r.status_code==409 and 'استعلام' in r.text
