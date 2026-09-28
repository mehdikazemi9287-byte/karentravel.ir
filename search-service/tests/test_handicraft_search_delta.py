import uuid
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from app.main import app
from app import orchestrator

def test_handicraft_http_search_enforces_city_and_pickup_contract(monkeypatch):
    now=datetime.now(timezone.utc);start=now+timedelta(days=4);title='Mock QA Transport '+uuid.uuid4().hex
    attrs={k:'Mock QA' for k in ['city','sku','artisan_name','craft_origin','material','pickup_address','pickup_hours','authenticity_terms','care_instructions']};attrs.update(delivery_mode='pickup',city='تهران')
    row={'id':'mock-qa-guide','service_type':'handicraft','title':title,'amount':1000000,'currency':'IRR','available_units':1,'provider_key':'manual_supplier','fulfillment_mode':'manual_supplier','valid_until':(now+timedelta(days=1)).isoformat(),'updated_at':now.isoformat(),'policy':{'verified':True,'cancellation':{'refundable':False}},'attributes':attrs}
    monkeypatch.setattr(orchestrator,'fan_out',lambda req:({'handicraft':[row]},[{'provider':'manual_supplier','status':'available','vertical':'handicraft','offer_count':1}]))
    payload={'verticals':['handicraft'],'destination':'تهران','query':title,'public':False,'tenant_ref':'mock-qa'}
    with TestClient(app) as c:
        r=c.post('/v1/search',json=payload);assert r.status_code==200 and len(r.json()['entities'])==1
        assert c.post('/v1/search',json={**payload,'destination':'تبریز'}).json()['entities']==[]
        row['attributes']['delivery_mode']='shipping'
        assert c.post('/v1/search',json={**payload,'query':title+' changed'}).json()['entities']==[]
