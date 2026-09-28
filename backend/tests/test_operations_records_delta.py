import uuid
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_ops_records_are_tenant_scoped_permissioned_and_paginated(client):
    session,reservation,_,_=reservation_fixture(client,uuid.uuid4().hex)
    from sqlalchemy import select
    from app.main import SessionLocal,User,Tenant
    email='ops-'+uuid.uuid4().hex+'@qa.invalid'
    with SessionLocal() as db:
        tenant=db.scalar(select(User).where(User.email=='employee@faraz.test'));db.add(User(tenant_id=tenant.tenant_id,email=email,name='Mock QA Ops',role='backoffice_expert'));db.commit()
    ops=login(client,'backoffice@aftab.test');other=login(client,email)
    assert client.get('/backoffice/records/bookings',headers=auth(session)).status_code==403
    bookings=client.get('/backoffice/records/bookings?limit=1',headers=auth(ops));assert bookings.status_code==200
    assert len(bookings.json()['items'])==1 and bookings.json()['items'][0]['id']==reservation['id']
    assert reservation['id'] not in client.get('/backoffice/records/bookings',headers=auth(other)).text
    for section in ['customers','trips','payments','refunds','suppliers','support','changes','notifications','audit']:
        r=client.get('/backoffice/records/'+section,headers=auth(ops));assert r.status_code==200,(section,r.text)
        assert 'payload_json' not in r.text and 'password_hash' not in r.text and 'mobile_e164' not in r.text
    assert client.get('/backoffice/records/unknown',headers=auth(ops)).status_code==404
    assert client.get('/backoffice/records/bookings?limit=10000',headers=auth(ops)).status_code==422
