import uuid
import httpx,pytest
from test_search_v2_public import _seed_public_tenant
from test_checkout_reviews_zarinpal import login,auth

@pytest.fixture
def upstream(monkeypatch):
    _seed_public_tenant();calls=[]
    class Client:
        def __init__(self,*a,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,json,headers):
            calls.append(json)
            return httpx.Response(200,json={'conversation_id':json.get('conversation_id') or str(uuid.uuid4()),'message':{'text':'پاسخ ایزوله','data':{}},'actions':[]})
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    return calls

def test_gateway_derives_scope_and_rejects_raw_conversation(client,upstream):
    guest=client.post('/assistant/message',json={'text':'سلام','public':False,'tenant_ref':'aftab-bank'});assert guest.status_code==200
    assert upstream[-1]['public'] is True and upstream[-1]['tenant_ref'] is None
    assert client.post('/assistant/message',json={'text':'ادامه','conversation_id':str(uuid.uuid4())}).status_code==403
    user=login(client,'employee@aftab.test');r=client.post('/assistant/message',headers=auth(user),json={'text':'سلام','tenant_ref':'faraz-industries','public':False});assert r.status_code==200
    assert upstream[-1]['public'] is False and upstream[-1]['tenant_ref']=='aftab-bank'
    assert client.post('/assistant/message',headers=auth(user),json={'text':'ادامه','conversation_id':r.json()['conversation_id']}).status_code==200
    other=login(client,'supplier@aftab.test');assert client.post('/assistant/message',headers=auth(other),json={'text':'ادامه','conversation_id':r.json()['conversation_id']}).status_code==403
    assert client.post('/assistant/message',json={'text':'ادامه','conversation_id':r.json()['conversation_id']}).status_code==403

def test_guest_claim_revokes_old_capability_and_invalid_auth_never_forwards(client,upstream):
    guest=client.post('/assistant/message',json={'text':'سلام'}).json()['conversation_id'];user=login(client,'employee@aftab.test')
    claim=client.post('/assistant/message',headers=auth(user),json={'text':'ادامه','conversation_id':guest});assert claim.status_code==200 and claim.headers['cache-control']=='no-store'
    assert client.post('/assistant/message',json={'text':'ادامه','conversation_id':guest}).status_code==403
    n=len(upstream);assert client.post('/assistant/message',headers={'Authorization':'Bearer invalid'},json={'text':'سلام'}).status_code==401;assert len(upstream)==n
