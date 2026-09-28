import uuid
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from app.main import app
from app import orchestrator

def test_event_hall_search_accepts_real_pool_and_returns_product_link(monkeypatch):
    now=datetime.now(timezone.utc);title='Mock QA Hall '+uuid.uuid4().hex
    row={'id':'mock-qa-event_hall','service_type':'event_hall','title':title,'amount':200000,'currency':'IRR','available_units':2,'provider_key':'manual_supplier','fulfillment_mode':'manual_supplier','valid_until':(now+timedelta(days=1)).isoformat(),'updated_at':now.isoformat(),'policy':{'verified':True,'cancellation':{'refundable':False}},'attributes':{'city':'شیراز','leisure_product_id':'mock-qa-product','session_starts_at':(now+timedelta(hours=2)).isoformat()}}
    monkeypatch.setattr(orchestrator,'fan_out',lambda req:({'event_hall':[row]},[{'provider':'manual_supplier','status':'available','vertical':'event_hall','offer_count':1}]))
    with TestClient(app) as c:
        r=c.post('/v1/search',json={'verticals':['event_hall'],'destination':'شیراز','query':title,'public':False,'tenant_ref':'mock-qa'})
        wrong=c.post('/v1/search',json={'verticals':['event_hall'],'destination':'شیراز','query':title,'public':False,'tenant_ref':'mock-qa','filters':{'depart':(now+timedelta(days=7)).date().isoformat()}})
    assert wrong.status_code==200 and wrong.json()['entities']==[]
    assert r.status_code==200,r.text
    assert r.json()['entities'][0]['best_offer']['attributes']['leisure_product_id']=='mock-qa-product'
