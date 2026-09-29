import json
import uuid
from app.main import SessionLocal
from app import operations as m
from test_accommodation_marketplace import fixture
from test_checkout_reviews_zarinpal import auth
from test_search_v2_public import _seed_public_tenant


def test_public_stay_catalog_never_exposes_private_inventory_or_rates(client):
    employee, _, uid, _, _ = fixture(client)
    with SessionLocal() as db:
        private = db.get(m.VacationUnit, uid).property_id
    # No fallback to any seeded corporate inventory.
    assert client.get('/public/vacation-rentals').status_code == 503
    tenant_id = _seed_public_tenant()
    assert client.get('/public/vacation-rentals').json() == []
    assert client.get('/public/vacation-rentals/'+private).status_code == 404
    with SessionLocal() as db:
        supplier = m.Supplier(tenant_id=tenant_id,supplier_type='vacation_rental',display_name='Mock QA public',status='active')
        db.add(supplier);db.flush()
        prop = m.VacationProperty(tenant_id=tenant_id,supplier_id=supplier.id,title='Mock QA public stay',slug=uuid.uuid4().hex,city='رامسر',property_type='villa',capacity=4,bedrooms=2,status='published',details_json=json.dumps({'description':'Mock QA only','host_name':'Mock QA host','photos':[{'url':'https://example.com/qa.jpg','alt':'Mock QA','private':'excluded'}],'amenities':['پارکینگ'],'private_contract':'never-public','nightly_price':42}))
        db.add(prop);db.flush();pid=prop.id
        db.add(m.VacationUnit(tenant_id=tenant_id,property_id=pid,title='Mock QA unit',capacity=4,available_units=2,nightly_price=1230000));db.commit()
    result = client.get('/public/vacation-rentals',params={'city':'رامسر','guests':2})
    assert result.status_code==200 and [r['id'] for r in result.json()]==[pid]
    detail = client.get('/public/vacation-rentals/'+pid).json()
    assert detail['account_recheck_required'] and detail['details']['host_name']=='Mock QA host'
    assert set(detail['units'][0])=={'id','title','capacity'}
    assert 'private_contract' not in str(detail) and 'nightly_price' not in str(detail) and 'available_units' not in str(detail)
    assert 'private' not in detail['details']['photos'][0]
    assert client.get('/vacation-rentals/'+pid,headers=auth(employee)).status_code==404
    assert client.get('/public/vacation-rentals',params={'guests':5}).json()==[]
    assert client.get('/public/vacation-rentals',params={'property_type':'fake'}).status_code==422
    with SessionLocal() as db:
        db.get(m.VacationProperty,pid).status='draft';db.commit()
    assert client.get('/public/vacation-rentals/'+pid).status_code==404
