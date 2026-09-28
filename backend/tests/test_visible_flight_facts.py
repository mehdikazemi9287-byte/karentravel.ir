import json
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from app.main import SessionLocal,User
from app.operations import Offer,Supplier


def test_flight_detail_exposes_supplied_facts_without_secrets_or_invented_stops(client):
    token=client.post('/auth/dev-login',json={'email':'employee@aftab.test'}).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='employee@aftab.test'))
        supplier=Supplier(tenant_id=user.tenant_id,supplier_type='flight',display_name='Mock isolated supplier',status='active');db.add(supplier);db.flush()
        attrs={'flight_number':'QA100','cabin':'economy','duration':'01:30','fare_rules':'Isolated terms','provider_token':'never-expose-this','internal_url':'http://private.invalid'}
        offer=Offer(tenant_id=user.tenant_id,supplier_id=supplier.id,service_type='flight',title='Mock flight detail',amount=100000,available_units=3,attributes_json=json.dumps(attrs),valid_until=datetime.now(timezone.utc)+timedelta(hours=1));db.add(offer);db.commit();oid=offer.id
    response=client.get('/offers/'+oid,headers=headers);assert response.status_code==200
    facts=response.json()['attributes'];assert facts['flight_number']=='QA100' and facts['cabin']=='economy' and facts['duration']=='01:30'
    assert 'stops' not in facts and 'provider_token' not in facts and 'internal_url' not in facts
    with SessionLocal() as db:
        offer=db.get(Offer,oid);offer.attributes_json=json.dumps({**attrs,'stops':0});db.commit()
    assert client.get('/offers/'+oid,headers=headers).json()['attributes']['stops']==0
    other=client.post('/auth/dev-login',json={'email':'employee@faraz.test'}).json()['access_token']
    assert client.get('/offers/'+oid,headers={'Authorization':'Bearer '+other}).status_code==404
