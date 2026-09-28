import json,uuid
from sqlalchemy import select,func
from app.main import SessionLocal,User
from app import operations as m
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_partner_retries_do_not_duplicate_rows_or_override_payload(client):
    employee,_,_,offer=reservation_fixture(client,uuid.uuid4().hex)
    agency=login(client,'agency@aftab.test');key=uuid.uuid4().hex;payload={'display_name':'Mock QA agency','markup_bps':0,'commission_bps':0};headers={**auth(agency),'Idempotency-Key':key}
    first=client.post('/agency/sub-agencies',headers=headers,json=payload);assert first.status_code==201
    assert client.post('/agency/sub-agencies',headers=headers,json=payload).json()['id']==first.json()['id']
    assert client.post('/agency/sub-agencies',headers=headers,json={**payload,'display_name':'changed'}).status_code==409
    assert client.post('/agency/sub-agencies',headers=auth(employee),json=payload).status_code==403
    with SessionLocal() as db:
        row=db.get(m.Offer,offer['id']);payload={'supplier_id':row.supplier_id,'service_type':'hotel','title':'Mock QA retry offer','amount':10000,'available_units':2,'valid_minutes':60,'policy':json.loads(row.policy_json),'attributes':{},'fulfillment_mode':'manual_supplier','provider_key':'manual_supplier'}
    supplier=login(client,'supplier@aftab.test');headers={**auth(supplier),'Idempotency-Key':uuid.uuid4().hex}
    first=client.post('/supplier/offers',headers=headers,json=payload);assert first.status_code==201
    assert client.post('/supplier/offers',headers=headers,json=payload).json()['id']==first.json()['id']
    assert client.post('/supplier/offers',headers=headers,json={**payload,'amount':20000}).status_code==409


def test_organization_structure_retry_conflict_and_permission(client):
    email='org-'+uuid.uuid4().hex+'@qa.invalid'
    with SessionLocal() as db:
        owner=db.scalar(select(User).where(User.email=='employee@aftab.test'));org=m.Organization(tenant_id=owner.tenant_id,name='Mock QA organization');db.add(org);db.add(User(tenant_id=owner.tenant_id,email=email,name='Mock QA org admin',role='organization_admin'));db.commit();oid=org.id
    admin=login(client,email);employee=login(client,'employee@aftab.test');faraz=login(client,'employee@faraz.test')
    for endpoint in ['departments','cost-centers']:
        url='/organizations/'+oid+'/'+endpoint;payload={'name':'Mock QA unit','code':'QA-'+uuid.uuid4().hex,'budget_amount':0}
        assert client.post(url,headers=auth(employee),json=payload).status_code==403
        first=client.post(url,headers=auth(admin),json=payload);assert first.status_code==201
        assert client.post(url,headers=auth(admin),json=payload).json()['id']==first.json()['id']
        assert client.post(url,headers=auth(admin),json={**payload,'name':'changed'}).status_code==409
