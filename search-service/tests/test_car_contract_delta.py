from datetime import datetime,timedelta,timezone
from dataclasses import replace
from app.domain import SearchRequest
from app.engine import assemble

def test_car_dates_and_terms_are_required():
    now=datetime.now(timezone.utc);start=now+timedelta(days=4);end=start+timedelta(days=2)
    attrs={k:'Mock QA' for k in ['vehicle_class','pickup_location','return_location','deposit_terms','license_terms','insurance_terms','mileage_terms']};attrs.update(city='شیراز',rental_start=start.isoformat(),rental_end=end.isoformat())
    row={'id':'mock-qa-car','service_type':'car_rental','title':'Mock QA Car شیراز','amount':1000000,'currency':'IRR','available_units':1,'provider_key':'manual_supplier','fulfillment_mode':'manual_supplier','valid_until':(now+timedelta(days=1)).isoformat(),'updated_at':now.isoformat(),'policy':{'verified':True,'cancellation':{'refundable':False}},'attributes':attrs}
    req=SearchRequest(verticals=('car_rental',),destination='شیراز',filters={'depart':start.date().isoformat(),'return':end.date().isoformat()},public=False)
    def results(request,r=row):return assemble(request,{'car_rental':[r]},[],0)['entities']
    assert len(results(req))==1
    assert results(replace(req,filters={}))==[]
    assert results(replace(req,filters={'depart':end.date().isoformat(),'return':end.date().isoformat()}))==[]
    assert results(req,{**row,'attributes':{**attrs,'insurance_terms':''}})==[]
