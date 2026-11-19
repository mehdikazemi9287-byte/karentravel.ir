"""VandaPay adapter + return/webhook: isolated DB, fake transport, no real money moves."""
import json, time, uuid
from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy import select, func
from app import operations as models, providers
from app.main import SessionLocal, User, JWT_SECRET, JWT_ISSUER
from app.providers import VandaPayAdapter, ProviderContext, vandapay_webhook_event
from test_checkout_reviews_zarinpal import reservation_fixture, auth, login

KEY = "sk_test_" + "a" * 24


class FakeVandaPay:
    def __init__(self, status="succeeded", amount=2000000):
        self.status = status; self.amount = amount; self.calls = []; self.order_ref = None
    def request(self, method, url, headers, payload, timeout):
        self.calls.append((method, url, dict(headers), payload))
        assert headers["Authorization"] == "Bearer " + KEY
        if method == "POST" and url.endswith("/payment_intents"):
            self.order_ref = payload["order_ref"]
            return 201, {"id": "pi_test_123456", "status": "created", "amount": payload["amount"], "checkout_url": "https://pay.vandapay.ir/c/abc", "order_ref": payload["order_ref"]}
        if method == "GET":
            return 200, {"id": url.rsplit("/", 1)[1], "status": self.status, "amount": self.amount, "order_ref": self.order_ref}
        return 404, {}


def adapter(transport, mode="test", key=KEY):
    return VandaPayAdapter(mode=mode, secret_key=key, base_url="https://api.vandapay.test/api/v1", return_url="https://karentravel.test/api/payments/vandapay/return", transport=transport)


def test_adapter_fails_closed_without_valid_config():
    ctx = ProviderContext(tenant_id=1, correlation_id="c", idempotency_key="k")
    assert adapter(FakeVandaPay(), key="").health().status == "configuration_error"
    assert adapter(FakeVandaPay(), mode="live").health().status == "configuration_error"  # test key in live mode
    assert adapter(FakeVandaPay(), key="sk_live_" + "b" * 20).execute("initiate", {"amount": 10, "currency": "IRR", "payment_intent_id": "x"}, ctx)["ok"] is False
    bad = VandaPayAdapter(mode="test", secret_key=KEY, base_url="http://insecure.test", return_url="https://k.test/r", transport=FakeVandaPay())
    assert bad.health().status == "configuration_error"


def test_initiate_and_verify_rules():
    t = FakeVandaPay(); a = adapter(t); ctx = ProviderContext(tenant_id=7, correlation_id="c", idempotency_key="idem-1")
    r = a.execute("initiate", {"amount": 2000000, "currency": "IRR", "payment_intent_id": "pay-1", "callback_state": "STATE"}, ctx)
    assert r["ok"] and r["redirect_url"].startswith("https://") and r["authority"] == "pi_test_123456"
    body = t.calls[0][3]; assert body["order_ref"] == "pay-1" and body["return_url"].endswith("?state=STATE") and t.calls[0][2]["Idempotency-Key"] == "idem-1"
    assert a.execute("verify", {"amount": 2000000, "currency": "IRR", "payment_intent_id": "pay-1", "authority": "pi_test_123456"}, ctx)["status"] == "verified"
    t.amount = 1  # amount tampering must not verify
    assert a.execute("verify", {"amount": 2000000, "currency": "IRR", "payment_intent_id": "pay-1", "authority": "pi_test_123456"}, ctx)["ok"] is False
    t.amount = 2000000; t.status = "processing"
    assert a.execute("verify", {"amount": 2000000, "currency": "IRR", "payment_intent_id": "pay-1", "authority": "pi_test_123456"}, ctx)["status"] == "pending"


def test_webhook_signature():
    body = json.dumps({"id": "evt_1", "type": "payment_intent.succeeded", "data": {"id": "pi_1"}}).encode()
    import hmac, hashlib
    ts = int(time.time()); sig = hmac.new(b"whsec", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert vandapay_webhook_event(body, f"t={ts},v1={sig}", "whsec")["id"] == "evt_1"
    for header in (f"t={ts},v1={'0'*64}", f"t={ts-1000},v1={sig}", "garbage", None):
        try: vandapay_webhook_event(body, header, "whsec"); assert False
        except ValueError: pass


def setup_intent(client, monkeypatch, transport):
    suffix = uuid.uuid4().hex
    session, reservation, _, _ = reservation_fixture(client, suffix)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == 'employee@aftab.test'))
        row = models.PaymentIntent(tenant_id=user.tenant_id, reservation_id=reservation['id'], user_id=user.id, command_id='vp-' + suffix, amount=2000000, currency='IRR', status='initiated', provider_key='vandapay', provider_authority='pi_test_' + suffix[:10])
        db.add(row); db.commit(); payment_id = row.id; tenant_id = user.tenant_id
        now = datetime.now(timezone.utc)
        token = jwt.encode({'iss': JWT_ISSUER, 'aud': 'karenseir-vandapay-callback', 'tenant_id': user.tenant_id, 'payment_intent_id': row.id, 'user_id': user.id, 'amount': row.amount, 'exp': now + timedelta(minutes=5), 'iat': now, 'jti': suffix}, JWT_SECRET, algorithm='HS256')
    transport.order_ref = payment_id
    monkeypatch.setitem(providers.ADAPTERS, 'payment', adapter(transport))
    monkeypatch.setenv('PUBLIC_WEB_URL', 'https://web.example.test')
    return session, payment_id, tenant_id, 'pi_test_' + suffix[:10], f'/payments/vandapay/return?state={token}'


def test_return_captures_only_after_server_side_success_and_is_idempotent(client, monkeypatch):
    t = FakeVandaPay()
    session, payment_id, _, _, url = setup_intent(client, monkeypatch, t)
    r = client.get(url, headers={'Accept': 'text/html'}, follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == 'https://web.example.test/payments/' + payment_id and 'state=' not in r.headers['location']
    data = client.get('/payments/' + payment_id, headers=auth(session)).json()
    assert data['status'] == 'captured' and data['receipt_reference'].startswith('pi_test_') and data['reservation_status'] != 'issued'
    assert client.get(url).json()['status'] == 'duplicate'
    assert client.post('/payments/' + payment_id + '/verify', headers=auth(session)).json()['status'] == 'captured'
    other = login(client, 'supplier@aftab.test')
    assert client.post('/payments/' + payment_id + '/verify', headers=auth(other)).status_code == 404
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(models.PaymentEvent).where(models.PaymentEvent.payment_intent_id == payment_id)) == 1


def test_pending_and_failed_do_not_capture(client, monkeypatch):
    t = FakeVandaPay(status="processing")
    session, payment_id, _, _, url = setup_intent(client, monkeypatch, t)
    assert client.get(url).json()['status'] == 'pending'
    assert client.get('/payments/' + payment_id, headers=auth(session)).json()['status'] == 'initiated'
    t.status = "failed"
    assert client.get(url).json()['status'] == 'cancelled'
    assert client.get('/payments/' + payment_id, headers=auth(session)).json()['status'] == 'failed'


def test_webhook_requires_signature_and_reverifies(client, monkeypatch):
    import hmac, hashlib
    t = FakeVandaPay()
    session, payment_id, tenant_id, authority, _ = setup_intent(client, monkeypatch, t)
    monkeypatch.setenv('VANDAPAY_MODE', 'test'); monkeypatch.setenv('VANDAPAY_WEBHOOK_SECRET', 'whsec_test')
    body = json.dumps({"id": "evt_" + authority, "type": "payment_intent.succeeded", "data": {"id": authority, "status": "succeeded", "metadata": {"tenant_id": tenant_id, "karenseir_payment_intent_id": payment_id}}}).encode()
    assert client.post('/payments/vandapay/webhook', content=body, headers={'VandaPay-Signature': 't=1,v1=00'}).status_code == 400
    ts = int(time.time()); sig = hmac.new(b'whsec_test', f'{ts}.'.encode() + body, hashlib.sha256).hexdigest()
    r = client.post('/payments/vandapay/webhook', content=body, headers={'VandaPay-Signature': f't={ts},v1={sig}', 'Content-Type': 'application/json'})
    assert r.status_code == 200 and r.json()['payment_status'] == 'captured'
    assert any(c[0] == 'GET' for c in t.calls)  # outcome re-read from VandaPay, not trusted from the event
