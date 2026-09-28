import json,uuid
from sqlalchemy import select,func
from app import providers,operations as m
from app.main import SessionLocal
from app.providers import ProviderHealth
from test_checkout_reviews_zarinpal import reservation_fixture,auth

class Transport:
    def __init__(self,fail=False): self.calls=0; self.fail=fail
    def health(self): return ProviderHealth(status='configured_not_verified',mode='isolated',detail='No financial transaction')
    def execute(self,operation,payload,context):
        self.calls+=1
        if self.fail: raise TimeoutError('SECRET-SHOULD-NOT-APPEAR')
        return {'ok':True,'authority':'A'*36,'redirect_url':'https://gateway.invalid/intercept-only'}

def payment(client):
    user,r,_,_=reservation_fixture(client,uuid.uuid4().hex)
    response=client.post('/reservations/'+r['id']+'/payment-intents',headers={**auth(user),'Idempotency-Key':uuid.uuid4().hex});assert response.status_code==201
    return user,r,response.json()

def test_distinct_keys_and_checkout_reuse_one_server_amount(client):
    user,r,p=payment(client)
    again=client.post('/reservations/'+r['id']+'/payment-intents',headers={**auth(user),'Idempotency-Key':uuid.uuid4().hex},json={'amount':1});assert again.json()['id']==p['id'] and again.json()['amount']==2000000
    checkout=client.post('/reservations/'+r['id']+'/checkout-sessions',headers=auth(user),json={'command_id':uuid.uuid4().hex}).json()
    with SessionLocal() as db:
        row=db.get(m.CheckoutSession,checkout['id']);row.stage='invoice';row.state_json=json.dumps({'funding':{'payable_amount':2000000}});db.commit()
    result=client.put('/checkout-sessions/'+checkout['id']+'/steps/payment',headers=auth(user),json={'command_id':uuid.uuid4().hex});assert result.status_code==200 and result.json()['payment_intent_id']==p['id']
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(m.PaymentIntent).where(m.PaymentIntent.reservation_id==r['id']))==1

def test_initiation_retry_returns_same_redirect_without_resend(client,monkeypatch):
    user,_,p=payment(client);adapter=Transport();monkeypatch.setitem(providers.ADAPTERS,'payment',adapter)
    a=client.post('/payments/'+p['id']+'/initiate',headers=auth(user));b=client.post('/payments/'+p['id']+'/initiate',headers=auth(user))
    assert a.status_code==b.status_code==202 and a.json()==b.json() and adapter.calls==1

def test_ambiguous_timeout_persists_attempt_and_redacts_exception(client,monkeypatch,caplog):
    user,_,p=payment(client);adapter=Transport(True);monkeypatch.setitem(providers.ADAPTERS,'payment',adapter)
    assert client.post('/payments/'+p['id']+'/initiate',headers=auth(user)).status_code==503
    assert client.post('/payments/'+p['id']+'/initiate',headers=auth(user)).status_code==409
    assert adapter.calls==1 and 'SECRET-SHOULD-NOT-APPEAR' not in caplog.text
    with SessionLocal() as db:assert db.scalar(select(m.IdempotencyKey).where(m.IdempotencyKey.scope=='payment.initiate',m.IdempotencyKey.key==p['id'])) is not None

def test_disabled_provider_does_not_consume_attempt(client,monkeypatch):
    user,_,p=payment(client);monkeypatch.setitem(providers.ADAPTERS,'payment',providers.DisabledMockAdapter('payment',mode='disabled'))
    assert client.post('/payments/'+p['id']+'/initiate',headers=auth(user)).status_code==503
    with SessionLocal() as db: assert db.scalar(select(m.IdempotencyKey).where(m.IdempotencyKey.scope=='payment.initiate',m.IdempotencyKey.key==p['id'])) is None
