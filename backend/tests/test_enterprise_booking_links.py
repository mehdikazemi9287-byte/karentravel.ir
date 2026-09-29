from test_checkout_reviews_zarinpal import hotel_terms
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import json
from sqlalchemy import select
from app.main import SessionLocal,User
from app import operations as m,enterprise_models as e
from test_checkout_reviews_zarinpal import reservation_fixture,login,auth

def test_approved_request_to_owned_booking_tracking(client):
    employee,_,_,offer=reservation_fixture(client,uuid4().hex)
    admin=login(client,'org-admin@aftab.test');foreign=login(client,'employee@faraz.test')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='employee@aftab.test'));boss=db.scalar(select(User).where(User.email=='org-admin@aftab.test'))
        org=m.Organization(tenant_id=user.tenant_id,name='Mock QA enterprise tracking',status='active');db.add(org);db.flush();oid=org.id;bid=boss.id
        db.add_all([m.EmployeeAssignment(tenant_id=user.tenant_id,user_id=u.id,organization_id=oid) for u in [user,boss]]);db.commit()
    policy={'command_id':str(uuid4()),'rules':{'allowed_services':['hotel'],'approval_required':True,'approver_ids':[bid],'maximum_budget':10000000}}
    assert client.put('/enterprise/organizations/'+oid+'/policy',headers=auth(admin),json=policy).status_code==200
    data={'command_id':str(uuid4()),'use_case':'team_retreat','title':'Mock QA tracking','purpose':'QA only','origin':'Tehran','destination':'Shiraz','starts_at':(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),'ends_at':(datetime.now(timezone.utc)+timedelta(days=12)).isoformat(),'headcount':1,'services':['hotel'],'budget_amount':5000000}
    request=client.post('/enterprise/organizations/'+oid+'/requests',headers=auth(employee),json=data).json();rid=request['id'];path='/enterprise/requests/'+rid
    check=client.post('/offers/'+offer['id']+'/price-check',headers=auth(employee),json={'hotel_stay':hotel_terms()[1],'units':1,'command_id':str(uuid4())}).json()
    booking=client.post('/orchestration/bookings',headers=auth(employee),json={'price_check_id':check['id'],'command_id':str(uuid4())}).json();res=booking['id']
    body={'reservation_id':res,'command_id':str(uuid4())}
    assert client.post(path+'/bookings',headers=auth(employee),json=body).status_code==409
    assert client.post(path+'/decision',headers=auth(admin),json={'command_id':str(uuid4()),'decision':'approve','reason':'QA approval only'}).status_code==200
    assert client.get(path+'/booking-candidates',headers=auth(admin)).status_code==403
    assert client.post(path+'/bookings',headers=auth(admin),json=body).status_code==403
    assert client.get(path+'/bookings',headers=auth(foreign)).status_code==404
    assert res in [r['id'] for r in client.get(path+'/booking-candidates',headers=auth(employee)).json()]
    assert client.post(path+'/bookings',headers=auth(employee),json={**body,'reservation_id':str(uuid4())}).status_code==404
    result=client.post(path+'/bookings',headers=auth(employee),json=body);assert result.status_code==200,result.text
    assert client.post(path+'/bookings',headers=auth(employee),json=body).json()==result.json()
    assert client.post(path+'/bookings',headers=auth(employee),json={**body,'command_id':str(uuid4())}).status_code==200
    assert client.post(path+'/bookings',headers=auth(employee),json={**body,'reservation_id':str(uuid4())}).status_code==409
    view=client.get(path+'/bookings',headers=auth(admin)).json();assert len(view['items'])==1 and not view['items'][0]['customer_can_open'] and not view['items'][0]['financial_authorization']
    assert res not in [b['id'] for b in client.get(path+'/booking-candidates',headers=auth(employee)).json()]
    with SessionLocal() as db:
        assert len(db.scalars(select(e.EnterpriseBookingLink).where(e.EnterpriseBookingLink.request_id==rid)).all())==1
        assert len(db.scalars(select(e.EnterpriseRequestEvent).where(e.EnterpriseRequestEvent.request_id==rid,e.EnterpriseRequestEvent.event_type=='booking.linked')).all())==1
        assert db.get(m.Reservation,res).status==booking['status']
        assert not db.scalars(select(m.PaymentIntent).where(m.PaymentIntent.reservation_id==res)).all()
