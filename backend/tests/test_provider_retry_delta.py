"""No network: prove mutation retries cannot duplicate external effects."""
import io,json
from urllib.error import HTTPError
import pytest
from app.providers import ProviderContext, ResilientAdapter, RetryPolicy
from app.grs_adapter import GRSHttpTransport, GRSAdapter
from app.grs_contract import GRSConfig
class Adapter:
    key='hotel';mode='sandbox';timeout_seconds=1;retry_policy=RetryPolicy(max_attempts=3,initial_backoff_seconds=0,max_backoff_seconds=0)
    def __init__(self):self.calls=0
    def execute(self,*args):self.calls+=1;raise TimeoutError('ambiguous result')
@pytest.mark.parametrize('operation',['reserve','book','initiate','cancel','send_otp','extend_hold'])
def test_mutation_unknown_outcome_is_not_blindly_retried(operation):
    adapter=Adapter();result=ResilientAdapter(adapter).execute(operation,{},ProviderContext(1,'test','test'))
    assert not result['ok'] and adapter.calls==1

def test_grs_http_error_preserves_authentication_taxonomy(monkeypatch):
    class Opener:
        def open(self,*args,**kwargs):raise HTTPError('https://provider.test/v1/cities',401,'Unauthorized',{'Content-Type':'application/json'},io.BytesIO(b'{"code":401}'))
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    cfg=GRSConfig(mode='sandbox',base_url='https://provider.test',client_token='test-only',connect_timeout_seconds=1,read_timeout_seconds=1,money_unit='IRR',webhook_secret='')
    result=GRSAdapter(config=cfg).execute('list_cities',{},ProviderContext(1,'test','test'))
    assert result['reason']=='provider_authentication_failed' and not result['error']['retryable']
