"""API -> isolated DB with explicitly mocked gateway; no financial transaction."""
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy import select, func
from app import operations as models, providers
from app.main import SessionLocal, User, JWT_SECRET, JWT_ISSUER
from test_checkout_reviews_zarinpal import reservation_fixture, auth, login, FakeZarinPalTransport
from app.providers import ZarinPalAdapter

def setup_payment(client,monkeypatch):
    suffix=uuid.uuid4().hex
    session,reservation,_,_=reservation_fixture(client,suffix)
    authority='A'+suffix+'777'
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='employee@aftab.test'))
        row=models.PaymentIntent(tenant_id=user.tenant_id,reservation_id=reservation['id'],user_id=user.id,command_id='return-'+suffix,amount=2000000,currency='IRR',status='initiated',provider_key='zarinpal',provider_authority=authority)
        db.add(row);db.commit();payment_id=row.id
        now=datetime.now(timezone.utc)
        token=jwt.encode({'iss':JWT_ISSUER,'aud':'karenseir-zarinpal-callback','tenant_id':user.tenant_id,'payment_intent_id':row.id,'user_id':user.id,'amount':row.amount,'exp':now+timedelta(minutes=5),'iat':now,'jti':suffix},JWT_SECRET,algorithm='HS256')
    transport=FakeZarinPalTransport()
    monkeypatch.setitem(providers.ADAPTERS,'payment',ZarinPalAdapter(mode='sandbox',merchant_id='12345678-1234-1234-1234-123456789012',callback_url='https://api.example.test/payments/zarinpal/callback',transport=transport))
    monkeypatch.setenv('PUBLIC_WEB_URL','https://web.example.test')
    return session,payment_id,f'/payments/zarinpal/callback?state={token}&Authority={authority}',transport

def test_browser_return_is_authenticated_database_status_not_query_success(client,monkeypatch):
    session,payment_id,url,transport=setup_payment(client,monkeypatch)
    r=client.get(url+'&Status=OK',headers={'Accept':'text/html'},follow_redirects=False)
    assert r.status_code==303 and r.headers['location']=='https://web.example.test/payments/'+payment_id
    assert r.headers['cache-control']=='no-store' and 'state=' not in r.headers['location']
    assert client.get('/payments/'+payment_id).status_code==401
    data=client.get('/payments/'+payment_id,headers=auth(session)).json()
    assert data['status']=='captured' and data['receipt_reference']=='987654321'
    assert not data['voucher_available'] and data['reservation_status']!='issued'
    other=login(client,'supplier@aftab.test')
    assert client.get('/payments/'+payment_id,headers=auth(other)).status_code==404
    assert client.post('/payments/'+payment_id+'/verify',headers=auth(other)).status_code==404
    assert client.get(url+'&Status=NOK').json()['status']=='duplicate'
    assert client.post('/payments/'+payment_id+'/verify',headers=auth(session)).json()['status']=='captured'
    assert len(transport.calls)==1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(models.PaymentEvent).where(models.PaymentEvent.payment_intent_id==payment_id))==1

def test_verification_failure_is_recoverable_without_new_charge(client,monkeypatch):
    session,payment_id,url,transport=setup_payment(client,monkeypatch)
    class Unavailable:
        def execute(self,*args):return {'ok':False}
    adapter=providers.ADAPTERS['payment'];monkeypatch.setitem(providers.ADAPTERS,'payment',Unavailable())
    r=client.get(url+'&Status=OK',headers={'Accept':'text/html'},follow_redirects=False)
    assert r.status_code==303
    assert client.get('/payments/'+payment_id,headers=auth(session)).json()['status']=='initiated'
    assert client.post('/payments/'+payment_id+'/verify',headers=auth(session)).status_code==502
    monkeypatch.setitem(providers.ADAPTERS,'payment',adapter)
    assert client.post('/payments/'+payment_id+'/verify',headers=auth(session)).json()['status']=='captured'
    assert len(transport.calls)==1 and transport.calls[0][0].endswith('/verify.json')

def test_cancelled_callback_does_not_capture_or_verify(client,monkeypatch):
    session,payment_id,url,transport=setup_payment(client,monkeypatch)
    assert client.get(url+'&Status=NOK',headers={'Accept':'text/html'},follow_redirects=False).status_code==303
    assert client.get('/payments/'+payment_id,headers=auth(session)).json()['status']=='failed'
    assert not transport.calls

def test_untrusted_web_origin_cannot_receive_callback_state(client,monkeypatch):
    _,_,url,_=setup_payment(client,monkeypatch)
    monkeypatch.setenv('PUBLIC_WEB_URL','https://web.example.test@attacker.test/path')
    r=client.get(url+'&Status=NOK',headers={'Accept':'text/html'},follow_redirects=False)
    assert r.status_code==200 and 'location' not in r.headers


def test_cancel_signal_can_be_reconciled_if_provider_later_confirms_paid(client,monkeypatch):
    session,payment_id,url,transport=setup_payment(client,monkeypatch)
    assert client.get(url+'&Status=NOK').json()['payment_status']=='failed'
    result=client.post('/payments/'+payment_id+'/verify',headers=auth(session))
    assert result.status_code==200 and result.json()['status']=='captured'
    assert client.get(url+'&Status=NOK').json()['status']=='duplicate'
    assert client.post('/payments/'+payment_id+'/verify',headers=auth(session)).json()['status']=='captured'
    assert len(transport.calls)==1
