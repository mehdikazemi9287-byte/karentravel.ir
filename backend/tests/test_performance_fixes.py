"""Synthetic data in the isolated test database only; query-count regressions."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import event
from app.main import SessionLocal, Tenant, User, engine, list_destinations, support_cases
from app.operations import Destination, Offer, Supplier, SupportCase, SupportThreadMessage
from app.public_autocomplete_cache import PublicAutocompleteCache

@pytest.fixture()
def scoped():
    with SessionLocal() as db:
        tag=uuid.uuid4().hex
        tenants=[Tenant(slug=f'perf-{tag}-{i}',name='[TEST]') for i in range(2)]
        db.add_all(tenants);db.flush()
        users=[User(tenant_id=t.id,email=f'{tag}-{i}@test.invalid',name='[TEST]',role='employee') for i,t in enumerate(tenants)]
        db.add_all(users);db.flush()
        yield db,tenants,users
        db.rollback()

def count_selects(run):
    statements=[]
    def capture(conn,cursor,statement,params,context,many):
        if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
    event.listen(engine,'before_cursor_execute',capture)
    try:return run(),statements
    finally:event.remove(engine,'before_cursor_execute',capture)

@pytest.mark.parametrize('size',[1,25])
def test_destination_query_budget_and_tenant_filter(scoped,size):
    db,tenants,users=scoped
    for tenant in tenants:
        supplier=Supplier(tenant_id=tenant.id,supplier_type='hotel',display_name='[TEST]');db.add(supplier);db.flush()
        for i in range(size):
            db.add(Destination(tenant_id=tenant.id,kind='city',name_fa='[TEST]',slug=f'd{i}'))
            db.add(Offer(tenant_id=tenant.id,supplier_id=supplier.id,service_type='hotel',title='[TEST]',amount=1,attributes_json=json.dumps({'destination_slug':f'd{i}'}),valid_until=datetime.now(timezone.utc)+timedelta(hours=1)))
        db.add(Offer(tenant_id=tenant.id,supplier_id=supplier.id,service_type='flight',title='[TEST expired]',amount=1,attributes_json='{"destination_slug":"d0"}',valid_until=datetime.now(timezone.utc)-timedelta(hours=1)))
    db.flush();user=SimpleNamespace(tenant_id=tenants[0].id)
    result,queries=count_selects(lambda:list_destinations(user=user,db=db))
    assert len(result)==size
    assert all(r['service_counts']=={'hotel':1} for r in result)
    assert len(queries)==2
    assert 'offers.amount' not in queries[-1]

@pytest.mark.parametrize('size',[1,25])
def test_support_query_budget_and_customer_isolation(scoped,size):
    db,tenants,users=scoped
    other=User(tenant_id=tenants[0].id,email=f'{uuid.uuid4().hex}@test.invalid',name='[TEST]',role='employee');db.add(other);db.flush()
    for user in [*users,other]:
        for i in range(size):
            case=SupportCase(tenant_id=user.tenant_id,user_id=user.id,subject='[TEST]',command_id=f'{user.id}-{i}');db.add(case);db.flush()
            db.add(SupportThreadMessage(tenant_id=user.tenant_id,case_id=case.id,sender_type='customer',body=f'owned-by-{user.id}'))
    db.flush();user=SimpleNamespace(id=users[0].id,tenant_id=tenants[0].id,role='employee')
    result,queries=count_selects(lambda:support_cases(user=user,db=db))
    assert len(result)==size and len(queries)==2
    assert all(r['messages'][0]['body']==f'owned-by-{user.id}' for r in result)

def test_local_cache_ttl_version_isolation_and_copy():
    now=[0];calls=[];cache=PublicAutocompleteCache(ttl=5,capacity=2,clock=lambda:now[0])
    def compute():calls.append(1);return [{'id':1}]
    cache.get('q','v1',compute)[0]['id']=99
    assert cache.get('q','v1',compute)==[{'id':1}] and len(calls)==1
    cache.get('q','v2',compute);assert len(calls)==2
    now[0]=6;cache.get('q','v1',compute);assert len(calls)==3
    cache.get('b','v1',compute);cache.get('c','v1',compute);assert len(cache._local)==2

def test_redis_write_hit_ttl_and_safe_outage():
    class FakeRedis:
        def __init__(self):self.values={};self.ttls={};self.gets=0;self.fail=False
        def get(self,k):
            self.gets+=1
            if self.fail:raise TimeoutError()
            return self.values.get(k)
        def ttl(self,k):return self.ttls.get(k,-2)
        def setex(self,k,ttl,v):self.values[k]=v;self.ttls[k]=ttl
    redis=FakeRedis();clock=[0]
    first=PublicAutocompleteCache(redis,clock=lambda:clock[0]);first.get('q','v1',lambda:[{'id':1}])
    second=PublicAutocompleteCache(redis,clock=lambda:clock[0]);assert second.get('q','v1',lambda:pytest.fail('should hit Redis'))==[{'id':1}]
    assert list(redis.ttls.values())==[300]
    redis.fail=True;second.get('x','v1',lambda:[]);n=redis.gets;second.get('y','v1',lambda:[]);assert redis.gets==n

def test_public_autocomplete_cache_route_preserves_query_and_bounds(client,monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,'public_autocomplete_cache',PublicAutocompleteCache())
    original=main._match_score
    calls=[]
    def counted(*args):calls.append(1);return original(*args)
    monkeypatch.setattr(main,'_match_score',counted)
    first=client.get('/search/autocomplete/public',params={'q':'تهران'})
    count=len(calls)
    second=client.get('/search/autocomplete/public',params={'q':'  تهران  '})
    assert first.status_code==200 and second.status_code==200 and len(calls)==count
    assert second.json()['query']=='  تهران  ' and second.json()['tenant_data_included'] is False
    assert first.json()['suggestions']==second.json()['suggestions']
    assert client.get('/search/autocomplete/public',params={'q':'a'*201}).status_code==422
