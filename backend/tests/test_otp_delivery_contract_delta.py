"""Controlled HTTP fixtures only; no live SMS is sent."""
import json
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
import pytest
from app.kavenegar_adapter import KavenegarSmsOtpProvider, normalize_iranian_mobile
from app.providers import ProviderContext, ResilientAdapter

CTX=ProviderContext(tenant_id=1,correlation_id='isolated-otp',idempotency_key='isolated-otp')
PAYLOAD={'destination_reference':'09123456789','code':'123456'}
class Response:
    def __init__(self,body):self.body=body
    def read(self):return json.dumps(self.body).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass

def provider():return KavenegarSmsOtpProvider(api_key='controlled-test-key',template='controlled-template')

@pytest.mark.parametrize('body',[{},[],{'return':[]},{'return':{'status':200}}, {'return':{'status':200},'entries':[]},{'return':{'status':200},'entries':[None]},{'return':{'status':200},'entries':[{'messageid':None}]},{'return':{'status':200},'entries':[{'messageid':0}]},{'return':{'status':200},'entries':[{'messageid':True}]}])
def test_incomplete_success_is_not_delivery(monkeypatch,body):
    monkeypatch.setattr('app.kavenegar_adapter.urlopen',lambda *a,**k:Response(body))
    assert provider().execute('send_otp',PAYLOAD,CTX)['ok'] is False

def test_post_body_keeps_code_and_phone_out_of_url(monkeypatch):
    calls=[]
    def send(request,**kwargs):
        calls.append(request)
        return Response({'return':{'status':200},'entries':[{'messageid':123456789}]})
    monkeypatch.setattr('app.kavenegar_adapter.urlopen',send)
    result=provider().execute('send_otp',PAYLOAD,CTX)
    assert result['ok'] and result['reference']=='123456789'
    assert calls[0].method=='POST' and not urlsplit(calls[0].full_url).query
    assert parse_qs(calls[0].data.decode())['token']==['123456']

@pytest.mark.parametrize('status,reason',[(404,'unknown_method'),(405,'method_not_allowed'),(418,'insufficient_credit'),(424,'template_unavailable'),(426,'account_service_unavailable')])
def test_precise_provider_error_without_echoing_secrets(monkeypatch,status,reason):
    monkeypatch.setattr('app.kavenegar_adapter.urlopen',lambda *a,**k:Response({'return':{'status':status,'message':'controlled-test-key 123456 09123456789'}}))
    result=provider().execute('send_otp',PAYLOAD,CTX)
    assert result['reason']==reason
    assert all(s not in json.dumps(result) for s in ['controlled-test-key','123456','09123456789'])

def test_ambiguous_timeout_does_not_send_twice(monkeypatch):
    calls=[]
    def fail(*args,**kwargs):calls.append(1);raise TimeoutError()
    monkeypatch.setattr('app.kavenegar_adapter.urlopen',fail)
    assert ResilientAdapter(provider()).execute('send_otp',PAYLOAD,CTX)['ok'] is False
    assert len(calls)==1

def test_urlerror_does_not_leak_secret(monkeypatch):
    def fail(*args,**kwargs):raise URLError('controlled-test-key 123456')
    monkeypatch.setattr('app.kavenegar_adapter.urlopen',fail)
    result=provider().execute('send_otp',PAYLOAD,CTX)
    assert 'controlled-test-key' not in json.dumps(result) and '123456' not in json.dumps(result)

@pytest.mark.parametrize('value',['۰۹۱۲۳۴۵۶۷۸۹','٠٩١٢٣٤٥٦٧٨٩'])
def test_phone_digits_are_canonical(value):assert normalize_iranian_mobile(value)=='989123456789'
