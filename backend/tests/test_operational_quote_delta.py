import json, uuid
from sqlalchemy import select
from app.main import SessionLocal
from app import operations as models
from test_checkout_reviews_zarinpal import reservation_fixture, login, auth

def test_offer_detail_taxed_price_checkout_and_tenant_isolation(client):
    suffix=uuid.uuid4().hex
    session,_,traveller,offer=reservation_fixture(client,suffix)
    with SessionLocal() as db:
        row=db.get(models.Offer,offer['id']);row.attributes_json=json.dumps({'taxes':200000,'fees':50000,'discounts':10000,'description':'Controlled contract fixture','internal_secret':'do-not-expose'});db.commit()
    detail=client.get('/offers/'+offer['id'],headers=auth(session));assert detail.status_code==200
    assert detail.json()['amount']==2240000 and 'internal_secret' not in detail.text
    assert client.get('/offers/'+offer['id'],headers=auth(login(client,'employee@faraz.test'))).status_code==404
    changed=client.post('/offers/'+offer['id']+'/price-check',headers=auth(session),json={'units':1,'expected_final_price':2000000,'command_id':'changed-'+suffix})
    assert changed.status_code==409 and changed.json()['detail']['code']=='PRICE_CHANGED'
    checked=client.post('/offers/'+offer['id']+'/price-check',headers=auth(session),json={'units':1,'expected_final_price':2240000,'command_id':'checked-'+suffix}).json()
    booked=client.post('/orchestration/bookings',headers=auth(session),json={'price_check_id':checked['id'],'command_id':'booked-'+suffix}).json()
    checkout=client.post('/reservations/'+booked['id']+'/checkout-sessions',headers=auth(session),json={'command_id':'checkout-'+suffix}).json()
    step='/checkout-sessions/'+checkout['id']+'/steps/'
    assert client.put(step+'traveller',headers=auth(session),json={'command_id':'traveller-'+suffix,'traveller_ids':[traveller['id']]}).status_code==200
    r=client.put(step+'recheck',headers=auth(session),json={'command_id':'recheck-'+suffix})
    assert r.status_code==200 and r.json()['state']['recheck']['total_amount']==2240000

def test_external_provider_metadata_cannot_create_fake_pricecheck_or_hold(client):
    suffix=uuid.uuid4().hex
    session,_,_,offer=reservation_fixture(client,suffix)
    checked=client.post('/offers/'+offer['id']+'/price-check',headers=auth(session),json={'units':1,'command_id':'oldcheck-'+suffix}).json()
    with SessionLocal() as db:
        row=db.get(models.Offer,offer['id']);row.fulfillment_mode='provider';row.provider_key='unconfigured_vendor';db.commit()
    assert client.get('/offers/'+offer['id'],headers=auth(session)).json()['provider_required']
    r=client.post('/offers/'+offer['id']+'/price-check',headers=auth(session),json={'units':1,'command_id':'newcheck-'+suffix})
    assert r.status_code==503 and r.json()['detail']['code']=='PROVIDER_QUOTE_REQUIRED'
    r=client.post('/orchestration/bookings',headers=auth(session),json={'price_check_id':checked['id'],'command_id':'blockedhold-'+suffix})
    assert r.status_code==503 and r.json()['detail']['code']=='PROVIDER_HOLD_REQUIRED'
    with SessionLocal() as db:assert db.scalar(select(models.PriceCheck).where(models.PriceCheck.id==checked['id'])).consumed_at is None
