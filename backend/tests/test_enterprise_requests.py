from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select
from app.main import SessionLocal, User
from app.operations import Organization, EmployeeAssignment
from app.enterprise import evaluate


def command(**data):
    return {'command_id':str(uuid4()), **data}


def test_request_policy_approval_privacy_and_replay(client):
    def login(email):
        return {'Authorization':'Bearer '+client.post('/auth/dev-login',json={'email':email}).json()['access_token']}
    employee=login('employee@aftab.test'); admin=login('org-admin@aftab.test'); outsider=login('employee@faraz.test')
    with SessionLocal() as db:
        users={u.email:u for u in db.scalars(select(User)).all()}
        emp=users['employee@aftab.test']; boss=users['org-admin@aftab.test']
        org=Organization(tenant_id=emp.tenant_id,name='Isolated enterprise QA',status='active');db.add(org);db.flush()
        oid=org.id;bid=boss.id
        db.add_all([EmployeeAssignment(tenant_id=emp.tenant_id,user_id=u.id,organization_id=oid) for u in [emp,boss]]);db.commit()
    base='/enterprise/organizations/'+oid
    policy=command(rules={'allowed_services':['hotel'],'approval_required':True,'approver_ids':[bid],'maximum_budget':1000})
    r=client.put(base+'/policy',headers=admin,json=policy);assert r.status_code==200,r.text
    assert client.put(base+'/policy',headers=employee,json=command(rules=policy['rules'])).status_code==403
    data=command(use_case='team_retreat',title='Team travel',purpose='Team meeting',origin='Tehran',destination='Shiraz',starts_at=(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),ends_at=(datetime.now(timezone.utc)+timedelta(days=12)).isoformat(),headcount=1,services=['hotel'],budget_amount=900)
    r=client.post(base+'/requests',headers=employee,json=data);assert r.status_code==201,r.text
    rid=r.json()['id'];assert r.json()['status']=='approval_required'
    assert client.post(base+'/requests',headers=employee,json=data).json()['id']==rid
    assert client.post(base+'/requests',headers=employee,json={**data,'budget_amount':800}).status_code==409
    assert client.get('/enterprise/requests/'+rid,headers=outsider).status_code==404
    decision=command(decision='approve',reason='Policy checked')
    assert client.post('/enterprise/requests/'+rid+'/decision',headers=employee,json=decision).status_code==403
    r=client.post('/enterprise/requests/'+rid+'/decision',headers=admin,json=decision);assert r.status_code==200,r.text
    assert r.json()['status']=='approved' and r.json()['booking_created'] is False
    assert client.post('/enterprise/requests/'+rid+'/decision',headers=admin,json=decision).json()==r.json()
    detail=client.get('/enterprise/requests/'+rid,headers=employee).json()
    assert len(detail['events'])==2 and detail['financial_methods_enabled']==[]


def test_policy_four_outcomes():
    req={'services':['hotel'],'destination':'Shiraz','budget_amount':100,'starts_at':(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),'ends_at':(datetime.now(timezone.utc)+timedelta(days=12)).isoformat()}
    rules={'allowed_services':['hotel'],'approval_required':False,'maximum_budget':200}
    assert evaluate(rules,req)['result']=='IN_POLICY'
    assert evaluate({**rules,'approval_required':True},req)['result']=='APPROVAL_REQUIRED'
    assert evaluate({**rules,'maximum_budget':50},req)['result']=='OUT_OF_POLICY'
    assert evaluate({**rules,'allowed_services':['flight']},req)['result']=='NOT_ALLOWED'


def test_campaign_draft_server_total_privacy_and_no_liability(client):
    from app.operations import FinancialLedgerEntry
    from sqlalchemy import func
    def login(email):
        return {'Authorization':'Bearer '+client.post('/auth/dev-login',json={'email':email}).json()['access_token']}
    admin=login('org-admin@aftab.test');employee=login('employee@aftab.test')
    with SessionLocal() as db:
        boss=db.scalar(select(User).where(User.email=='org-admin@aftab.test'))
        emp=db.scalar(select(User).where(User.email=='employee@aftab.test'))
        org=Organization(tenant_id=boss.tenant_id,name='Campaign QA',status='active');db.add(org);db.flush();oid=org.id
        db.add_all([EmployeeAssignment(tenant_id=boss.tenant_id,user_id=u.id,organization_id=oid) for u in [boss,emp]])
        ids=[boss.id,emp.id];before=db.scalar(select(func.count()).select_from(FinancialLedgerEntry));db.commit()
    url='/enterprise/organizations/'+oid+'/campaigns'
    payload=command(name='Nowruz campaign',product_type='EMPLOYEE_BENEFIT',amount_per_recipient=30000000,recipient_ids=ids,valid_from=datetime.now(timezone.utc).isoformat(),valid_until=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(),services=['hotel'],maximum_contribution=30000000)
    r=client.post(url,headers=admin,json=payload);assert r.status_code==201,r.text
    assert r.json()['proposed_total']==60000000 and r.json()['spendable_amount']==0 and r.json()['status']=='DRAFT'
    assert client.post(url,headers=admin,json=payload).json()==r.json()
    assert client.get(url,headers=employee).status_code==403
    assert client.post(url,headers=employee,json=payload).status_code==403
    assert client.post(url,headers=admin,json={**payload,'command_id':str(uuid4()),'recipient_ids':[ids[0],ids[0]]}).status_code==422
    assert client.post(url,headers=admin,json={**payload,'command_id':str(uuid4()),'recipient_ids':[999999]}).status_code==422
    assert client.post(url,headers=admin,json={**payload,'command_id':str(uuid4()),'proposed_total':1}).status_code==422
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(FinancialLedgerEntry))==before


def test_invited_supplier_quotes_revision_selection_and_privacy(client):
    from app.operations import Supplier,SupplierMembership
    def login(email):return {'Authorization':'Bearer '+client.post('/auth/dev-login',json={'email':email}).json()['access_token']}
    admin=login('org-admin@aftab.test');employee=login('employee@aftab.test');supplier=login('supplier@aftab.test')
    with SessionLocal() as db:
        boss=db.scalar(select(User).where(User.email=='org-admin@aftab.test'));emp=db.scalar(select(User).where(User.email=='employee@aftab.test'));vendor=db.scalar(select(User).where(User.email=='supplier@aftab.test'))
        org=Organization(tenant_id=boss.tenant_id,name='RFQ QA',status='active');sp=Supplier(tenant_id=boss.tenant_id,supplier_type='hotel',display_name='QA supplier',status='active');db.add_all([org,sp]);db.flush();oid=org.id;sid=sp.id
        db.add_all([EmployeeAssignment(tenant_id=boss.tenant_id,user_id=u.id,organization_id=oid) for u in [boss,emp]])
        db.add(SupplierMembership(tenant_id=boss.tenant_id,user_id=vendor.id,supplier_id=sid));db.commit()
    base='/enterprise/organizations/'+oid
    assert client.put(base+'/policy',headers=admin,json=command(rules={'allowed_services':['hotel'],'approval_required':False,'maximum_budget':1000})).status_code==200
    data=command(use_case='team_retreat',title='Private title',purpose='Private purpose',notes='Private notes',origin='Tehran',destination='Shiraz',starts_at=(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),ends_at=(datetime.now(timezone.utc)+timedelta(days=12)).isoformat(),headcount=1,services=['hotel'],budget_amount=900)
    r=client.post(base+'/requests',headers=employee,json=data);assert r.status_code==201,r.text
    rid=r.json()['id'];url='/enterprise/requests/'+rid
    quote=command(supplier_id=sid,amount=800,valid_until=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),terms='Isolated test terms only')
    assert client.post(url+'/quotes',headers=supplier,json=quote).status_code==404
    assert client.post(url+'/invitations',headers=admin,json=command(supplier_id=sid)).status_code==200
    rfqs=client.get('/enterprise/supplier/rfqs',headers=supplier).json();own=next(x for x in rfqs if x['id']==rid)
    assert 'budget_amount' not in own['requirements'] and 'traveler_user_ids' not in own['requirements'] and 'Private' not in str(own)
    assert client.get(url,headers=supplier).status_code==403
    q=client.post(url+'/quotes',headers=supplier,json=quote);assert q.status_code==201,q.text
    assert client.post(url+'/quotes',headers=supplier,json=quote).json()==q.json()
    q2=client.post(url+'/quotes',headers=supplier,json={**quote,'command_id':str(uuid4()),'amount':750});assert q2.status_code==201,q2.text
    assert client.post(url+'/selection',headers=admin,json=command(quote_id=q.json()['id'])).status_code==409
    chosen=client.post(url+'/selection',headers=admin,json=command(quote_id=q2.json()['id']));assert chosen.status_code==200,chosen.text
    assert chosen.json()['status']=='quote_selected' and not chosen.json()['booking_created']
