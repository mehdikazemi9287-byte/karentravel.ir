from datetime import datetime,timedelta,timezone
from dataclasses import replace
from app.domain import SearchRequest
from app.engine import assemble

def test_train_route_date_and_actual_future_departure_are_required():
    now=datetime.now(timezone.utc);departure=now+timedelta(days=2)
    row={'id':'mock-qa-train','service_type':'train','title':'Mock QA train مشهد','amount':1000000,'currency':'IRR','available_units':3,'provider_key':'manual_supplier','fulfillment_mode':'manual_supplier','valid_until':(now+timedelta(days=3)).isoformat(),'updated_at':now.isoformat(),'policy':{'verified':True,'cancellation':{'refundable':False}},'attributes':{'origin':'تهران','destination':'مشهد','departure_time':departure.isoformat(),'rail_operator':'Mock QA','train_number':'123','seat_class':'Mock QA'}}
    req=SearchRequest(verticals=('train',),origin='تهران',destination='مشهد',filters={'depart':departure.date().isoformat()},public=False)
    def results(r,offer=row):return assemble(r,{'train':[offer]},[],0)['entities']
    assert len(results(req))==1
    for wrong in [replace(req,origin='تبریز'),replace(req,destination='قم'),replace(req,filters={}),replace(req,filters={'depart':now.date().isoformat()})]:assert results(wrong)==[]
    for bad in ['', 'not-a-date', (now-timedelta(days=1)).isoformat(), departure.replace(tzinfo=None).isoformat()]:assert results(req,{**row,'attributes':{**row['attributes'],'departure_time':bad}})==[]
