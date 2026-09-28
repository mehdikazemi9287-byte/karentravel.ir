from datetime import datetime,timedelta,timezone
from dataclasses import replace
from app.domain import SearchRequest
from app.engine import assemble


def test_leisure_date_matches_tehran_day_for_restaurant_and_related_verticals():
    now=datetime.now(timezone.utc);day=(now+timedelta(days=7)).date()
    start=datetime.combine(day,datetime.min.time(),tzinfo=timezone(timedelta(hours=3,minutes=30)))+timedelta(minutes=30)
    for vertical in ['restaurant','event_hall','pool_sport','attraction']:
        row={'id':'mock-qa-'+vertical,'service_type':vertical,'title':'Mock QA شیراز','amount':200000,'currency':'IRR','available_units':2,'provider_key':'manual_supplier','fulfillment_mode':'manual_supplier','valid_until':(now+timedelta(days=1)).isoformat(),'updated_at':now.isoformat(),'policy':{'verified':True,'cancellation':{'refundable':False}},'attributes':{'city':'شیراز','leisure_product_id':'mock-qa-product','session_starts_at':start.astimezone(timezone.utc).isoformat()}}
        req=SearchRequest(verticals=(vertical,),destination='شیراز',filters={'depart':day.isoformat()},public=False)
        def result(request,offer=row):return assemble(request,{vertical:[offer]},[],0)['entities']
        assert len(result(req))==1
        assert result(replace(req,filters={'depart':(day-timedelta(days=1)).isoformat()}))==[]
        assert result(req,{**row,'attributes':{**row['attributes'],'session_starts_at':'invalid'}})==[]
