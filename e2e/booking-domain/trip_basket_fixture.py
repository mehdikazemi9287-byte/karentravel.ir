import json,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from app.main import SessionLocal
from app import operations as m
assert 'sqlite' in str(SessionLocal.kw['bind'].url)
f=json.loads(Path('/qa/fixtures.json').read_text())
with SessionLocal() as db:
 old=db.get(m.Offer,f['offer']);o=m.Offer(tenant_id=old.tenant_id,supplier_id=old.supplier_id,service_type='hotel',title='Mock QA basket hotel '+uuid.uuid4().hex[:6],amount=1230000,currency='IRR',available_units=10,status='active',provider_key='manual_supplier',fulfillment_mode='manual_supplier',attributes_json='{}',policy_json=old.policy_json,valid_until=datetime.now(timezone.utc)+timedelta(hours=2));db.add(o);db.commit();Path('/qa/trip-basket-fixture.json').write_text(json.dumps({'offer':o.id,'title':o.title}))
print('QA-only offer prepared')
