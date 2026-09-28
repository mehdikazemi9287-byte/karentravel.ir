import uuid
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from app.main import app
from app import orchestrator

def test_guide_http_search_enforces_date_and_group_capacity(monkeypatch):
    now=datetime.now(timezone.utc);start=now+timedelta(days=4);title='Mock QA Guide '+uuid.uuid4().hex
    attrs={k:'Mock QA' for k in ['guide_name','languages','meeting_point','inclusions','exclusions']};attrs.update(city='شیراز',group_capacity='1',departure_time=start.isoformat(),arrival_time=(start+timedelta(hours=2)).isoformat())
    row={'id':'mock-qa-guide','service_type':'travel_guide','title':title,'amount':1000000,'currency':'IRR','available_units':1,'provider_key':'manual_supplier','fulfillment_mode':'manual_supplier','valid_until':(now+timedelta(days=1)).isoformat(),'updated_at':now.isoformat(),'policy':{'verified':True,'cancellation':{'refundable':False}},'attributes':attrs}
    monkeypatch.setattr(orchestrator,'fan_out',lambda req:({'travel_guide':[row]},[{'provider':'manual_supplier','status':'available','vertical':'travel_guide','offer_count':1}]))
    payload={'verticals':['travel_guide'],'destination':'شیراز','query':title,'public':False,'tenant_ref':'mock-qa','filters':{'depart':start.date().isoformat()}}
    with TestClient(app) as c:
        r=c.post('/v1/search',json=payload);assert r.status_code==200 and len(r.json()['entities'])==1
        assert c.post('/v1/search',json={**payload,'travellers':2}).json()['entities']==[]
        assert c.post('/v1/search',json={**payload,'filters':{}}).json()['entities']==[]
