import uuid,json
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as models
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_train_party_quote_checkout_and_replay_ownership(client):
    suffix=uuid.uuid4().hex
    user,unused,t1,offer=reservation_fixture(client,suffix)
    with SessionLocal() as db:
        row=db.get(models.Offer,offer['id']);row.service_type='train';row.attributes_json=json.dumps({'origin':'تهران','destination':'شیراز','rail_operator':'Mock QA','train_number':'QA1','seat_class':'Mock QA','departure_time':(datetime.now(timezone.utc)+timedelta(days=20)).isoformat()});db.commit()
    path='/offers/'+offer['id']+'/price-check';key='train-check-'+suffix
    body={'units':2,'command_id':key,'train_party':{'adults':2,'children':0,'infants':0}}
    for party in [{'adults':1},{'adults':2,'children':1},{'adults':2,'infants':1}]:
        assert client.post(path,headers=auth(user),json={**body,'train_party':party}).status_code==422
    checked=client.post(path,headers=auth(user),json=body);assert checked.status_code==201,checked.text
    assert checked.json()['amount']==4_000_000
    assert client.post(path,headers=auth(user),json=body).json()['id']==checked.json()['id']
    other=login(client,'supplier@aftab.test')
    assert client.post(path,headers=auth(other),json=body).status_code==404
    r=client.post('/orchestration/bookings',headers=auth(user),json={'price_check_id':checked.json()['id'],'command_id':'train-book-'+suffix});assert r.status_code==201,r.text
    assert r.json()['price_snapshot']['units']==2
    checkout=client.post('/reservations/'+r.json()['id']+'/checkout-sessions',headers=auth(user),json={'command_id':'train-checkout-'+suffix}).json()
    step='/checkout-sessions/'+checkout['id']+'/steps/traveller'
    for ids in [[t1['id']],[t1['id'],t1['id']]]:
        assert client.put(step,headers=auth(user),json={'command_id':str(uuid.uuid4()),'traveller_ids':ids}).status_code==422
    t2=client.post('/me/travellers',headers=auth(user),json={'full_name':'Mock second adult'}).json()
    payload={'command_id':'train-travellers-'+suffix,'traveller_ids':[t1['id'],t2['id']]}
    ok=client.put(step,headers=auth(user),json=payload);assert ok.status_code==200,ok.text
    assert client.put(step,headers=auth(user),json=payload).json()==ok.json()
    assert len(ok.json()['state']['traveller_ids'])==2
