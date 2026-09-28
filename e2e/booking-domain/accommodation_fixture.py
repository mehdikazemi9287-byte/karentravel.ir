import json,uuid,httpx
from pathlib import Path
from datetime import datetime,timedelta,timezone
from app.main import SessionLocal
from app import operations as m
assert 'sqlite' in str(SessionLocal.kw['bind'].url), 'QA fixture requires isolated SQLite'
c=httpx.Client(base_url='http://127.0.0.1:8000');s=c.post('/auth/dev-login',json={'email':'supplier@aftab.test'}).json();h={'Authorization':'Bearer '+s['access_token']}
f=json.loads(Path('/qa/fixtures.json').read_text())
with SessionLocal() as db:
 o=db.get(m.Offer,f['offer']);sid=o.supplier_id;policy=json.loads(o.policy_json)
now=datetime.now(timezone.utc);start=now+timedelta(days=59);title='Mock QA Villa '+uuid.uuid4().hex[:6]
r=c.post('/supplier/vacation-properties',headers=h,json={'supplier_id':sid,'title':title,'slug':'qa-'+uuid.uuid4().hex,'city':'رامسر','property_type':'pool_property','booking_mode':'REQUEST_TO_BOOK','capacity':4,'bedrooms':2,'details':{'description':'صرفاً دادهٔ آزمون ایزوله؛ قابل فروش نیست','cancellation_policy':policy}});r.raise_for_status();prop=r.json()
r=c.post('/supplier/vacation-properties/'+prop['id']+'/units',headers=h,json={'title':'Mock QA Unit','capacity':4,'available_units':5,'nightly_price':1000000,'pricing':{'base_capacity':1,'extra_guest_price':100000,'cleaning_fee':200000,'service_fee':50000,'calendar':{(start+timedelta(days=3)).date().isoformat():{'status':'UNAVAILABLE'},start.date().isoformat():{'nightly_price':1200000,'minimum_stay':2}}}});r.raise_for_status()
Path('/qa/marketplace-host-fixture.json').write_text(json.dumps({'property':prop['id'],'unit':r.json()['id'],'depart':start.date().isoformat(),'return':(start+timedelta(days=2)).date().isoformat(),'title':title+' — Mock QA Unit'}));print('Accommodation fixture created only in QA SQLite')
