"""Enterprise request/policy/approval/RFQ. No booking or financial success is invented."""
import hashlib,json
from datetime import datetime,timezone
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from . import operations as m
from . import enterprise_models as e

USE_CASES=('business_travel','workforce_accommodation','relocation','team_retreat','incentive','organizational_guests','employee_welfare','organizational_event','travel_credit')
SERVICES=('flight','hotel','train','tour','vacation_rental','car_rental','restaurant','event_hall','pool_sport','attraction','travel_guide','tourist_transportation')
PERMISSIONS={'requests.read_all','requests.on_behalf','requests.approve','policy.manage','roles.manage','rfq.manage','benefits.manage'}

def aware(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid')
    command_id:str=Field(min_length=8,max_length=120)

class PolicyRules(BaseModel):
    model_config=ConfigDict(extra='forbid')
    allowed_services:list[str]=Field(min_length=1,max_length=20)
    maximum_budget:int|None=Field(default=None,gt=0,le=10**15)
    maximum_days:int=Field(default=365,ge=1,le=730)
    minimum_advance_days:int=Field(default=0,ge=0,le=365)
    allowed_destinations:list[str]=Field(default_factory=list,max_length=100)
    approver_ids:list[int]=Field(default_factory=list,max_length=8)
    approval_required:bool=True

class PolicyIn(Command): rules:PolicyRules
class GrantIn(Command): user_id:int;permissions:list[str]=Field(max_length=7)
class RequestIn(Command):
    use_case:str
    title:str=Field(min_length=3,max_length=200)
    purpose:str=Field(min_length=3,max_length=2000)
    origin:str=Field(min_length=2,max_length=120)
    destination:str=Field(min_length=2,max_length=120)
    starts_at:datetime
    ends_at:datetime
    headcount:int=Field(ge=1,le=10000)
    services:list[str]=Field(min_length=1,max_length=20)
    budget_amount:int=Field(gt=0,le=10**15)
    traveler_user_ids:list[int]=Field(default_factory=list,max_length=1000)
    department_id:str|None=None
    cost_center_id:str|None=None
    notes:str=Field(default='',max_length=4000)
class DecisionIn(Command): decision:Literal['approve','reject'];reason:str=Field(min_length=3,max_length=500)
class InviteIn(Command): supplier_id:str
class QuoteIn(Command):
    supplier_id:str
    amount:int=Field(gt=0,le=10**15)
    valid_until:datetime
    terms:str=Field(min_length=10,max_length=8000)
class SelectIn(Command):quote_id:str

class CampaignIn(Command):
    name:str=Field(min_length=3,max_length=200)
    product_type:Literal['ORGANIZATION_GIFT_CARD','TRAVEL_CREDIT','EMPLOYEE_BENEFIT','CAMPAIGN_CREDIT','SERVICE_SPECIFIC_CREDIT','DESTINATION_SPECIFIC_CREDIT']
    amount_per_recipient:int=Field(gt=0,le=10**12)
    recipient_ids:list[int]=Field(min_length=1,max_length=10000)
    valid_from:datetime
    valid_until:datetime
    services:list[str]=Field(min_length=1,max_length=20)
    destinations:list[str]=Field(default_factory=list,max_length=100)
    minimum_spend:int=Field(default=0,ge=0,le=10**15)
    maximum_contribution:int=Field(gt=0,le=10**12)
    partial_consumption:bool=False
    message:str=Field(default='',max_length=1000)
    occasion:str=Field(default='',max_length=100)

def evaluate(rules,requirements):
    if not rules:return {'result':'APPROVAL_REQUIRED','reasons':['سیاست سازمانی هنوز تنظیم نشده است']}
    reasons=[]
    if not set(requirements['services'])<=set(rules['allowed_services']):return {'result':'NOT_ALLOWED','reasons':['یکی از خدمات طبق سیاست سازمان مجاز نیست']}
    if rules.get('allowed_destinations') and requirements['destination'] not in rules['allowed_destinations']:return {'result':'NOT_ALLOWED','reasons':['مقصد طبق سیاست سازمان مجاز نیست']}
    if rules.get('maximum_budget') and requirements['budget_amount']>rules['maximum_budget']:reasons.append('بودجهٔ درخواست بیش از سقف سیاست است')
    start=aware(datetime.fromisoformat(requirements['starts_at']));end=aware(datetime.fromisoformat(requirements['ends_at']))
    if (end-start).total_seconds()>rules.get('maximum_days',365)*86400:reasons.append('مدت سفر بیش از سیاست است')
    if (start.date()-datetime.now(timezone.utc).date()).days<rules.get('minimum_advance_days',0):reasons.append('فاصله تا شروع سفر کمتر از سیاست است')
    return {'result':'OUT_OF_POLICY' if reasons else 'APPROVAL_REQUIRED' if rules.get('approval_required',True) else 'IN_POLICY','reasons':reasons}


class BookingLinkIn(BaseModel):
    reservation_id:str=Field(min_length=36,max_length=36)
    command_id:str=Field(min_length=8,max_length=120)

def router(current_user,get_db,User):
    api=APIRouter(prefix='/enterprise',tags=['enterprise'])
    def membership(db,user,org):
        return db.scalar(select(m.EmployeeAssignment).where(m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.user_id==user.id,m.EmployeeAssignment.organization_id==org))
    def permissions(db,user,org):
        if not membership(db,user,org):raise HTTPException(403,'عضویت در این سازمان تأیید نشده است')
        if user.role=='organization_admin':return PERMISSIONS
        grant=db.scalar(select(e.EnterpriseGrant).where(e.EnterpriseGrant.tenant_id==user.tenant_id,e.EnterpriseGrant.organization_id==org,e.EnterpriseGrant.user_id==user.id))
        return set(json.loads(grant.permissions_json)) if grant else set()
    def require(db,user,org,permission):
        if permission not in permissions(db,user,org):raise HTTPException(403,'مجوز سازمانی این عملیات را ندارید')
    def org_lock(db,user,org):
        row=db.scalar(select(m.Organization).where(m.Organization.tenant_id==user.tenant_id,m.Organization.id==org,m.Organization.status=='active').with_for_update())
        if row is None:raise HTTPException(404,'سازمان فعال وجود ندارد')
        return row
    def replay(db,user,scope,body):
        row=db.scalar(select(m.IdempotencyKey).where(m.IdempotencyKey.tenant_id==user.tenant_id,m.IdempotencyKey.scope==scope,m.IdempotencyKey.key==body['command_id']))
        if row:
            if row.request_hash!=digest(body):raise HTTPException(409,'کلید تکرار با درخواست قبلی متفاوت است')
            return json.loads(row.response_json)
    def finish(db,user,scope,body,result,org,kind,request_id=None,detail=None):
        db.add(m.IdempotencyKey(tenant_id=user.tenant_id,scope=scope,key=body['command_id'],request_hash=digest(body),response_json=json.dumps(result)))
        key=digest([scope,body['command_id']])
        db.add(e.EnterpriseRequestEvent(tenant_id=user.tenant_id,organization_id=org,request_id=request_id,actor_id=user.id,event_type=kind,detail_json=json.dumps(detail or result,ensure_ascii=False),command_key=key))
        db.add(m.OutboxEvent(tenant_id=user.tenant_id,aggregate_type='enterprise_request',aggregate_id=request_id or org,event_type='enterprise.'+kind,payload_json=json.dumps({'request_id':request_id,'organization_id':org,'actor_id':user.id}),idempotency_key=key))
        db.commit();return result
    def get_request(db,user,rid,all_required=False):
        row=db.scalar(select(e.EnterpriseRequest).where(e.EnterpriseRequest.tenant_id==user.tenant_id,e.EnterpriseRequest.id==rid).with_for_update())
        if row is None:raise HTTPException(404,'درخواست وجود ندارد')
        perms=permissions(db,user,row.organization_id)
        if all_required and 'rfq.manage' not in perms:raise HTTPException(403,'مجوز مدیریت استعلام ندارید')
        snapshot=json.loads(row.policy_snapshot_json)
        if row.requester_id!=user.id and not ({'requests.read_all'}&perms) and not ('requests.approve' in perms and user.id in snapshot.get('approver_ids',[])):raise HTTPException(403,'این درخواست در محدودهٔ دسترسی شما نیست')
        return row
    def output(row):
        snapshot=json.loads(row.policy_snapshot_json)
        return {'id':row.id,'organization_id':row.organization_id,'requester_id':row.requester_id,'title':row.title,'use_case':row.use_case,'status':row.status,'requirements':json.loads(row.requirements_json),'policy_result':row.policy_result,'policy_reasons':snapshot.get('reasons',[]),'policy_version':snapshot.get('version'),'current_step':row.current_step,'approver_ids':snapshot.get('approver_ids',[]),'selected_quote_id':row.selected_quote_id,'financial_methods_enabled':[],'booking_created':False}
    def supplier_scope(db,user):return set(db.scalars(select(m.SupplierMembership.supplier_id).where(m.SupplierMembership.tenant_id==user.tenant_id,m.SupplierMembership.user_id==user.id)).all())
    def quote_output(q):return {'id':q.id,'supplier_id':q.supplier_id,'revision':q.revision,'amount':q.amount,'currency':q.currency,'terms':q.terms,'valid_until':q.valid_until.isoformat()}

    def booking_rows(db,user,row):
        pairs=db.execute(select(e.EnterpriseBookingLink,m.Reservation).join(m.Reservation,m.Reservation.id==e.EnterpriseBookingLink.reservation_id).where(e.EnterpriseBookingLink.tenant_id==user.tenant_id,e.EnterpriseBookingLink.request_id==row.id,m.Reservation.tenant_id==user.tenant_id)).all()
        return [{"id":link.id,"reservation_id":booking.id,"booking_reference":booking.booking_reference,"status":booking.status,"service_type":booking.service_type,"customer_can_open":booking.user_id==user.id,"financial_authorization":False} for link,booking in pairs]

    @api.get('/requests/{rid}/bookings')
    def request_bookings(rid:str,user=Depends(current_user),db:Session=Depends(get_db)):
        row=get_request(db,user,rid)
        return {"items":booking_rows(db,user,row),"can_link":row.requester_id==user.id and row.status=='approved',"requirements":json.loads(row.requirements_json)}

    @api.get('/requests/{rid}/booking-candidates')
    def booking_candidates(rid:str,user=Depends(current_user),db:Session=Depends(get_db)):
        row=get_request(db,user,rid)
        if row.requester_id!=user.id or row.status!='approved':raise HTTPException(403,'فقط درخواست‌کنندهٔ درخواست تأییدشده می‌تواند رزرو خود را انتخاب کند')
        linked=select(e.EnterpriseBookingLink.reservation_id).where(e.EnterpriseBookingLink.tenant_id==user.tenant_id)
        bookings=db.scalars(select(m.Reservation).where(m.Reservation.tenant_id==user.tenant_id,m.Reservation.user_id==user.id,m.Reservation.service_type.in_(json.loads(row.requirements_json)['services']),m.Reservation.status.in_(['reserved','pending','confirmed','issued']),m.Reservation.id.not_in(linked)).order_by(m.Reservation.created_at.desc()).limit(100)).all()
        return [{"id":b.id,"booking_reference":b.booking_reference,"status":b.status,"service_type":b.service_type} for b in bookings]

    @api.post('/requests/{rid}/bookings')
    def link_booking(rid:str,data:BookingLinkIn,user=Depends(current_user),db:Session=Depends(get_db)):
        row=get_request(db,user,rid)
        if row.requester_id!=user.id or not membership(db,user,row.organization_id):raise HTTPException(403,'اتصال رزرو فقط توسط درخواست‌کنندهٔ عضو سازمان انجام می‌شود')
        body={**data.model_dump(),'request_id':rid,'actor':user.id}
        prior=replay(db,user,'enterprise.booking.link',body)
        if prior:return prior
        if row.status!='approved':raise HTTPException(409,'درخواست هنوز تأیید نشده است')
        booking=db.scalar(select(m.Reservation).where(m.Reservation.tenant_id==user.tenant_id,m.Reservation.id==data.reservation_id,m.Reservation.user_id==user.id).with_for_update())
        if booking is None:raise HTTPException(404,'رزرو متعلق به شما در دسترس نیست')
        existing=db.scalar(select(e.EnterpriseBookingLink).where(e.EnterpriseBookingLink.tenant_id==user.tenant_id,e.EnterpriseBookingLink.reservation_id==booking.id))
        if existing:
            if existing.request_id!=rid:raise HTTPException(409,'این رزرو به درخواست دیگری متصل است')
            result={"items":booking_rows(db,user,row),"financial_authorization":False}
            db.add(m.IdempotencyKey(tenant_id=user.tenant_id,scope="enterprise.booking.link",key=body["command_id"],request_hash=digest(body),response_json=json.dumps(result)));db.commit();return result
        if booking.status not in ['reserved','pending','confirmed','issued'] or booking.service_type not in json.loads(row.requirements_json)['services']:raise HTTPException(409,'وضعیت یا نوع خدمت رزرو با این درخواست سازگار نیست')
        link=e.EnterpriseBookingLink(tenant_id=user.tenant_id,request_id=rid,reservation_id=booking.id,linked_by=user.id);db.add(link);db.flush()
        trip=m.ensure_trip_for_reservation(db,booking,title=row.title,destination=json.loads(row.requirements_json).get('destination'))
        m.record_trip_event(db,tenant_id=user.tenant_id,trip_id=trip.id,reservation_id=booking.id,event_key='enterprise-link:'+link.id,event_type='enterprise.request.linked',source='system',title='رزرو به درخواست سازمانی مرتبط شد',message='این ارتباط برای پیگیری است و به معنای تأیید پرداخت سازمان نیست.',deep_link='/organization/requests')
        return finish(db,user,'enterprise.booking.link',body,{"items":booking_rows(db,user,row),"financial_authorization":False},row.organization_id,'booking.linked',rid,{"reservation_id":booking.id})

    @api.get('/context')
    def context(user=Depends(current_user),db:Session=Depends(get_db)):
        assignments=db.scalars(select(m.EmployeeAssignment).where(m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.user_id==user.id)).all();rows=[]
        for a in assignments:
            org=db.scalar(select(m.Organization).where(m.Organization.id==a.organization_id,m.Organization.tenant_id==user.tenant_id,m.Organization.status=='active'))
            if org:rows.append({'id':org.id,'name':org.name,'permissions':sorted(permissions(db,user,org.id))})
        return {'organizations':rows,'use_cases':USE_CASES,'services':SERVICES}

    @api.get('/organizations/{org}/members')
    def members(org:str,user=Depends(current_user),db:Session=Depends(get_db)):
        perms=permissions(db,user,org)
        if not ({'roles.manage','policy.manage','requests.on_behalf','benefits.manage'}&perms):raise HTTPException(403,'مجوز مشاهدهٔ فهرست کارکنان ندارید')
        users=db.scalars(select(User).join(m.EmployeeAssignment,m.EmployeeAssignment.user_id==User.id).where(User.tenant_id==user.tenant_id,m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.organization_id==org)).all()
        return [{'id':u.id,'name':u.name,'email':u.email,'role':u.role} for u in users]

    @api.put('/organizations/{org}/grants')
    def grants(org:str,data:GrantIn,user=Depends(current_user),db:Session=Depends(get_db)):
        require(db,user,org,'roles.manage');org_lock(db,user,org)
        body={**data.model_dump(),'org':org,'actor':user.id};prior=replay(db,user,'enterprise.grant',body)
        if prior:return prior
        if not set(data.permissions)<=PERMISSIONS or not db.scalar(select(m.EmployeeAssignment.id).where(m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.organization_id==org,m.EmployeeAssignment.user_id==data.user_id)):raise HTTPException(422,'عضو یا مجوزها معتبر نیستند')
        row=db.scalar(select(e.EnterpriseGrant).where(e.EnterpriseGrant.tenant_id==user.tenant_id,e.EnterpriseGrant.organization_id==org,e.EnterpriseGrant.user_id==data.user_id))
        old=json.loads(row.permissions_json) if row else []
        if row is None:row=e.EnterpriseGrant(tenant_id=user.tenant_id,organization_id=org,user_id=data.user_id);db.add(row)
        row.permissions_json=json.dumps(sorted(set(data.permissions)))
        return finish(db,user,'enterprise.grant',body,{'user_id':data.user_id,'permissions':sorted(set(data.permissions))},org,'grant.changed',detail={'user_id':data.user_id,'old':old,'new':data.permissions})

    @api.put('/organizations/{org}/policy')
    def policy(org:str,data:PolicyIn,user=Depends(current_user),db:Session=Depends(get_db)):
        require(db,user,org,'policy.manage');org_lock(db,user,org)
        body={**data.model_dump(mode='json'),'org':org,'actor':user.id};prior=replay(db,user,'enterprise.policy',body)
        if prior:return prior
        rules=data.rules.model_dump()
        if not set(rules['allowed_services'])<=set(SERVICES) or len(set(rules['approver_ids']))!=len(rules['approver_ids']):raise HTTPException(422,'قواعد سیاست معتبر نیستند')
        for uid in rules['approver_ids']:
            approver=db.scalar(select(User).where(User.tenant_id==user.tenant_id,User.id==uid))
            if approver is None or 'requests.approve' not in permissions(db,approver,org):raise HTTPException(422,'تأییدکننده باید عضو دارای مجوز تأیید باشد')
        if rules['approval_required'] and not rules['approver_ids']:raise HTTPException(422,'حداقل یک تأییدکننده لازم است')
        version=(db.scalar(select(func.max(e.EnterprisePolicy.version)).where(e.EnterprisePolicy.tenant_id==user.tenant_id,e.EnterprisePolicy.organization_id==org)) or 0)+1
        db.add(e.EnterprisePolicy(tenant_id=user.tenant_id,organization_id=org,version=version,rules_json=json.dumps(rules)))
        return finish(db,user,'enterprise.policy',body,{'version':version,'rules':rules},org,'policy.changed')

    @api.post('/organizations/{org}/requests',status_code=201)
    def create(org:str,data:RequestIn,user=Depends(current_user),db:Session=Depends(get_db)):
        perms=permissions(db,user,org);org_lock(db,user,org)
        body={**data.model_dump(mode='json'),'org':org,'actor':user.id};prior=replay(db,user,'enterprise.request',body)
        if prior:return prior
        if data.use_case not in USE_CASES or not set(data.services)<=set(SERVICES):raise HTTPException(422,'نوع درخواست یا خدمات معتبر نیست')
        if aware(data.starts_at)<=datetime.now(timezone.utc) or aware(data.ends_at)<=aware(data.starts_at):raise HTTPException(422,'بازهٔ سفر معتبر نیست')
        people=set(data.traveler_user_ids or [user.id])
        if len(people)>data.headcount or (people!={user.id} and 'requests.on_behalf' not in perms):raise HTTPException(403,'مجوز درخواست به نمایندگی از دیگران ندارید')
        assigned=set(db.scalars(select(m.EmployeeAssignment.user_id).where(m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.organization_id==org,m.EmployeeAssignment.user_id.in_(people))).all())
        if assigned!=people:raise HTTPException(422,'مسافران انتخاب‌شده عضو سازمان نیستند')
        own=membership(db,user,org)
        for field,model in [('department_id',m.Department),('cost_center_id',m.CostCenter)]:
            value=getattr(data,field)
            if value and (db.scalar(select(model.id).where(model.id==value,model.tenant_id==user.tenant_id,model.organization_id==org)) is None or ('requests.on_behalf' not in perms and value!=getattr(own,field))):raise HTTPException(403,'واحد سازمانی در محدودهٔ دسترسی شما نیست')
        policy=db.scalar(select(e.EnterprisePolicy).where(e.EnterprisePolicy.tenant_id==user.tenant_id,e.EnterprisePolicy.organization_id==org).order_by(e.EnterprisePolicy.version.desc()))
        rules=json.loads(policy.rules_json) if policy else {};requirements=data.model_dump(mode='json',exclude={'command_id','title','use_case'});requirements['traveler_user_ids']=sorted(people)
        result=evaluate(rules,requirements);approvers=rules.get('approver_ids',[])
        if user.id in approvers:raise HTTPException(422,'درخواست‌دهنده نمی‌تواند تأییدکنندهٔ درخواست خودش باشد')
        status='policy_required' if policy is None or (result['result']=='OUT_OF_POLICY' and not approvers) else 'not_allowed' if result['result']=='NOT_ALLOWED' else 'approved' if result['result']=='IN_POLICY' else 'approval_required'
        row=e.EnterpriseRequest(tenant_id=user.tenant_id,organization_id=org,requester_id=user.id,use_case=data.use_case,title=data.title,status=status,requirements_json=json.dumps(requirements,ensure_ascii=False),policy_snapshot_json=json.dumps({**result,'version':policy.version if policy else None,'rules':rules,'approver_ids':approvers}),policy_result=result['result']);db.add(row);db.flush()
        return finish(db,user,'enterprise.request',body,output(row),org,'request.created',row.id,{'status':status,'policy_result':result['result']})

    @api.get('/requests')
    def requests(org:str,user=Depends(current_user),db:Session=Depends(get_db)):
        perms=permissions(db,user,org);rows=db.scalars(select(e.EnterpriseRequest).where(e.EnterpriseRequest.tenant_id==user.tenant_id,e.EnterpriseRequest.organization_id==org).order_by(e.EnterpriseRequest.created_at.desc()).limit(200)).all()
        return [output(r) for r in rows if r.requester_id==user.id or 'requests.read_all' in perms or ('requests.approve' in perms and user.id in json.loads(r.policy_snapshot_json).get('approver_ids',[]))]

    @api.get('/requests/{rid}')
    def detail(rid:str,user=Depends(current_user),db:Session=Depends(get_db)):
        row=get_request(db,user,rid)
        events=db.scalars(select(e.EnterpriseRequestEvent).where(e.EnterpriseRequestEvent.tenant_id==user.tenant_id,e.EnterpriseRequestEvent.request_id==row.id).order_by(e.EnterpriseRequestEvent.created_at)).all()
        quotes=db.scalars(select(e.EnterpriseQuote).where(e.EnterpriseQuote.tenant_id==user.tenant_id,e.EnterpriseQuote.request_id==row.id).order_by(e.EnterpriseQuote.created_at)).all()
        return {**output(row),'events':[{'type':a.event_type,'at':a.created_at.isoformat(),'detail':json.loads(a.detail_json)} for a in events],'quotes':[quote_output(q) for q in quotes]}

    @api.post('/requests/{rid}/decision')
    def decision(rid:str,data:DecisionIn,user=Depends(current_user),db:Session=Depends(get_db)):
        row=get_request(db,user,rid);require(db,user,row.organization_id,'requests.approve')
        body={**data.model_dump(),'rid':rid,'actor':user.id};prior=replay(db,user,'enterprise.decision',body)
        if prior:return prior
        snapshot=json.loads(row.policy_snapshot_json);approvers=snapshot.get('approver_ids',[])
        if row.status!='approval_required' or row.requester_id==user.id or row.current_step>=len(approvers) or approvers[row.current_step]!=user.id:raise HTTPException(409,'ترتیب یا مجوز تأیید معتبر نیست')
        before=row.status
        if data.decision=='reject':row.status='rejected'
        else:
            if row.selected_quote_id:
                q=db.scalar(select(e.EnterpriseQuote).where(e.EnterpriseQuote.id==row.selected_quote_id,e.EnterpriseQuote.tenant_id==user.tenant_id,e.EnterpriseQuote.request_id==row.id))
                if q is None or aware(q.valid_until)<=datetime.now(timezone.utc):raise HTTPException(409,'اعتبار پیشنهاد پایان یافته است؛ درخواست را پس بگیرید و استعلام تازه بگیرید')
            row.current_step+=1
            if row.current_step==len(approvers):row.status='quote_selected' if row.selected_quote_id else 'approved'
        return finish(db,user,'enterprise.decision',body,output(row),row.organization_id,'approval.'+data.decision,row.id,{'old':before,'new':row.status,'step':row.current_step,'reason':data.reason})

    @api.post('/requests/{rid}/withdraw')
    def withdraw(rid:str,data:Command,user=Depends(current_user),db:Session=Depends(get_db)):
        row=get_request(db,user,rid)
        if row.requester_id!=user.id:raise HTTPException(403,'فقط درخواست‌دهنده می‌تواند انصراف دهد')
        body={**data.model_dump(),'rid':rid,'actor':user.id};prior=replay(db,user,'enterprise.withdraw',body)
        if prior:return prior
        if row.status in ('withdrawn','closed'):raise HTTPException(409,'درخواست بسته شده است')
        old=row.status;row.status='withdrawn'
        return finish(db,user,'enterprise.withdraw',body,output(row),row.organization_id,'request.withdrawn',rid,{'old':old,'new':row.status})

    @api.post('/requests/{rid}/invitations')
    def invite(rid:str,data:InviteIn,user=Depends(current_user),db:Session=Depends(get_db)):
        row=get_request(db,user,rid,True);body={**data.model_dump(),'rid':rid,'actor':user.id};prior=replay(db,user,'enterprise.invite',body)
        if prior:return prior
        if row.status not in ('approved','rfq_open','quoted'):raise HTTPException(409,'درخواست هنوز مجوز استعلام ندارد')
        supplier=db.scalar(select(m.Supplier).where(m.Supplier.id==data.supplier_id,m.Supplier.tenant_id==user.tenant_id,m.Supplier.status=='active'))
        if supplier is None:raise HTTPException(422,'تأمین‌کنندهٔ فعال وجود ندارد')
        prior_invite=db.scalar(select(e.EnterpriseInvitation).where(e.EnterpriseInvitation.tenant_id==user.tenant_id,e.EnterpriseInvitation.request_id==rid,e.EnterpriseInvitation.supplier_id==supplier.id))
        if prior_invite is None:db.add(e.EnterpriseInvitation(tenant_id=user.tenant_id,request_id=rid,supplier_id=supplier.id))
        if row.status=='approved':row.status='rfq_open'
        return finish(db,user,'enterprise.invite',body,{'status':row.status,'supplier_id':supplier.id},row.organization_id,'rfq.invited',rid)

    @api.get('/supplier/rfqs')
    def rfqs(user=Depends(current_user),db:Session=Depends(get_db)):
        rows=db.execute(select(e.EnterpriseRequest,e.EnterpriseInvitation.supplier_id).join(e.EnterpriseInvitation,e.EnterpriseInvitation.request_id==e.EnterpriseRequest.id).where(e.EnterpriseRequest.tenant_id==user.tenant_id,e.EnterpriseInvitation.tenant_id==user.tenant_id,e.EnterpriseInvitation.supplier_id.in_(supplier_scope(db,user)),e.EnterpriseRequest.status.in_(('rfq_open','quoted')))).all()
        result=[]
        for r,sid in rows:
            req=json.loads(r.requirements_json);result.append({'id':r.id,'supplier_id':sid,'use_case':r.use_case,'requirements':{k:req[k] for k in ('origin','destination','starts_at','ends_at','headcount','services')}})
        return result

    @api.post('/requests/{rid}/quotes',status_code=201)
    def quote(rid:str,data:QuoteIn,user=Depends(current_user),db:Session=Depends(get_db)):
        if data.supplier_id not in supplier_scope(db,user):raise HTTPException(403,'مجوز این تأمین‌کننده را ندارید')
        row=db.scalar(select(e.EnterpriseRequest).where(e.EnterpriseRequest.tenant_id==user.tenant_id,e.EnterpriseRequest.id==rid).with_for_update())
        invitation=db.scalar(select(e.EnterpriseInvitation).where(e.EnterpriseInvitation.tenant_id==user.tenant_id,e.EnterpriseInvitation.request_id==rid,e.EnterpriseInvitation.supplier_id==data.supplier_id))
        if row is None or invitation is None:raise HTTPException(404,'استعلام واگذارشده وجود ندارد')
        body={**data.model_dump(mode='json'),'rid':rid,'actor':user.id};prior=replay(db,user,'enterprise.quote',body)
        if prior:return prior
        if row.status not in ('rfq_open','quoted') or aware(data.valid_until)<=datetime.now(timezone.utc):raise HTTPException(409,'استعلام یا اعتبار پیشنهاد معتبر نیست')
        revision=(db.scalar(select(func.max(e.EnterpriseQuote.revision)).where(e.EnterpriseQuote.tenant_id==user.tenant_id,e.EnterpriseQuote.request_id==rid,e.EnterpriseQuote.supplier_id==data.supplier_id)) or 0)+1
        q=e.EnterpriseQuote(tenant_id=user.tenant_id,request_id=rid,supplier_id=data.supplier_id,revision=revision,amount=data.amount,terms=data.terms,valid_until=data.valid_until);db.add(q);row.status='quoted';db.flush()
        return finish(db,user,'enterprise.quote',body,quote_output(q),row.organization_id,'quote.received',rid,{'quote_id':q.id,'revision':revision})

    @api.post('/requests/{rid}/selection')
    def selection(rid:str,data:SelectIn,user=Depends(current_user),db:Session=Depends(get_db)):
        row=get_request(db,user,rid,True);body={**data.model_dump(),'rid':rid,'actor':user.id};prior=replay(db,user,'enterprise.select',body)
        if prior:return prior
        q=db.scalar(select(e.EnterpriseQuote).where(e.EnterpriseQuote.tenant_id==user.tenant_id,e.EnterpriseQuote.request_id==rid,e.EnterpriseQuote.id==data.quote_id))
        if row.status!='quoted' or q is None or aware(q.valid_until)<=datetime.now(timezone.utc):raise HTTPException(409,'پیشنهاد قابل انتخاب نیست')
        latest=db.scalar(select(func.max(e.EnterpriseQuote.revision)).where(e.EnterpriseQuote.tenant_id==user.tenant_id,e.EnterpriseQuote.request_id==rid,e.EnterpriseQuote.supplier_id==q.supplier_id))
        if q.revision!=latest:raise HTTPException(409,'نسخهٔ جدیدتر پیشنهاد را بررسی کنید')
        snapshot=json.loads(row.policy_snapshot_json);req=json.loads(row.requirements_json);result=evaluate(snapshot.get('rules',{}),{**req,'budget_amount':q.amount})
        if result['result']=='NOT_ALLOWED' or (result['result']=='OUT_OF_POLICY' and not snapshot.get('approver_ids')):raise HTTPException(409,'مبلغ یا خدمت طبق سیاست قابل انتخاب نیست')
        row.selected_quote_id=q.id;row.policy_result=result['result'];row.policy_snapshot_json=json.dumps({**snapshot,**result});row.current_step=0;row.status='quote_selected' if result['result']=='IN_POLICY' else 'approval_required'
        return finish(db,user,'enterprise.select',body,output(row),row.organization_id,'quote.selected',rid,{'quote_id':q.id,'amount':q.amount,'status':row.status,'contract_created':False,'payment_initiated':False})
    def campaign_output(row):
        return {'id':row.id,'name':row.name,'product_type':row.product_type,'status':row.status,
                'amount_per_recipient':row.amount_per_recipient,'proposed_total':row.proposed_total,
                'recipient_count':len(json.loads(row.recipient_ids_json)),'currency':row.currency,
                'valid_from':row.valid_from.isoformat(),'valid_until':row.valid_until.isoformat(),
                'rules':json.loads(row.rules_json),'personalization':json.loads(row.personalization_json),
                'funded_amount':0,'issued_amount':0,'spendable_amount':0}

    @api.post('/organizations/{org}/campaigns',status_code=201)
    def campaign_create(org:str,data:CampaignIn,user=Depends(current_user),db:Session=Depends(get_db)):
        require(db,user,org,'benefits.manage');org_lock(db,user,org)
        body={**data.model_dump(mode='json'),'actor':user.id,'org':org}
        prior=replay(db,user,'enterprise.campaign',body)
        if prior:return prior
        recipients=set(data.recipient_ids)
        if len(recipients)!=len(data.recipient_ids):raise HTTPException(422,'فهرست دریافت‌کنندگان تکراری است')
        if len(recipients)*data.amount_per_recipient>10**15:raise HTTPException(422,'جمع پیشنهادی بیش از سقف ثبت پیش‌نویس است')
        if aware(data.valid_until)<=max(aware(data.valid_from),datetime.now(timezone.utc)):raise HTTPException(422,'بازهٔ اعتبار معتبر نیست')
        if not set(data.services)<=set(SERVICES):raise HTTPException(422,'خدمت معتبر نیست')
        if data.maximum_contribution>data.amount_per_recipient:raise HTTPException(422,'سقف مشارکت بیش از اعتبار پیشنهادی است')
        if data.product_type=='DESTINATION_SPECIFIC_CREDIT' and not data.destinations:raise HTTPException(422,'مقصدهای مجاز را تعیین کنید')
        assigned=set(db.scalars(select(m.EmployeeAssignment.user_id).where(m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.organization_id==org,m.EmployeeAssignment.user_id.in_(recipients))).all())
        if assigned!=recipients:raise HTTPException(422,'همهٔ دریافت‌کنندگان باید عضو همین سازمان باشند')
        rules={k:getattr(data,k) for k in ('services','destinations','minimum_spend','maximum_contribution','partial_consumption')}
        rules['stacking_allowed']=False
        row=e.BenefitCampaign(tenant_id=user.tenant_id,organization_id=org,created_by=user.id,name=data.name,
            product_type=data.product_type,amount_per_recipient=data.amount_per_recipient,
            proposed_total=len(recipients)*data.amount_per_recipient,recipient_ids_json=json.dumps(sorted(recipients)),
            rules_json=json.dumps(rules),personalization_json=json.dumps({'message':data.message,'occasion':data.occasion},ensure_ascii=False),
            valid_from=aware(data.valid_from),valid_until=aware(data.valid_until))
        db.add(row);db.flush()
        return finish(db,user,'enterprise.campaign',body,campaign_output(row),org,'campaign.drafted',detail={'campaign_id':row.id,'recipients':len(recipients),'proposed_total':row.proposed_total,'liability_activated':False})

    @api.get('/organizations/{org}/campaigns')
    def campaigns(org:str,user=Depends(current_user),db:Session=Depends(get_db)):
        require(db,user,org,'benefits.manage')
        rows=db.scalars(select(e.BenefitCampaign).where(e.BenefitCampaign.tenant_id==user.tenant_id,e.BenefitCampaign.organization_id==org).order_by(e.BenefitCampaign.created_at.desc()).limit(200)).all()
        return [campaign_output(row) for row in rows]

    # ---- organization administration for the organization panel: which organizations exist, who belongs, the policy in force, real counts
    TENANT_ADMINS=('tenant_admin','platform_admin')
    class OrgIn(BaseModel):
        model_config=ConfigDict(extra='forbid')
        name:str=Field(min_length=2,max_length=160)
    class MemberIn(BaseModel):
        model_config=ConfigDict(extra='forbid')
        email:str=Field(min_length=5,max_length=200)
    def org_row(db,user,org):
        row=db.scalar(select(m.Organization).where(m.Organization.tenant_id==user.tenant_id,m.Organization.id==org))
        if row is None:raise HTTPException(404,'سازمان پیدا نشد')
        return row
    def manage_members(db,user,org):
        if user.role in TENANT_ADMINS:org_row(db,user,org)
        else:require(db,user,org,'roles.manage')
    def member_list(db,user,org):
        users=db.scalars(select(User).join(m.EmployeeAssignment,m.EmployeeAssignment.user_id==User.id).where(User.tenant_id==user.tenant_id,m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.organization_id==org).order_by(User.name)).all()
        return [{'id':u.id,'name':u.name,'email':u.email,'role':u.role} for u in users]
    @api.get('/organizations')
    def organizations(user=Depends(current_user),db:Session=Depends(get_db)):
        if user.role not in TENANT_ADMINS:raise HTTPException(403,'فهرست همهٔ سازمان‌ها فقط برای مدیر مجموعه است')
        counts=dict(db.execute(select(m.EmployeeAssignment.organization_id,func.count()).where(m.EmployeeAssignment.tenant_id==user.tenant_id).group_by(m.EmployeeAssignment.organization_id)).all())
        rows=db.scalars(select(m.Organization).where(m.Organization.tenant_id==user.tenant_id).order_by(m.Organization.name)).all()
        return [{'id':r.id,'name':r.name,'status':r.status,'members':counts.get(r.id,0)} for r in rows]
    @api.post('/organizations',status_code=201)
    def create_organization(data:OrgIn,user=Depends(current_user),db:Session=Depends(get_db)):
        if user.role not in TENANT_ADMINS:raise HTTPException(403,'ایجاد سازمان فقط برای مدیر مجموعه است')
        name=' '.join(data.name.split())
        if db.scalar(select(m.Organization.id).where(m.Organization.tenant_id==user.tenant_id,m.Organization.name==name)):raise HTTPException(409,'سازمانی با این نام وجود دارد')
        row=m.Organization(tenant_id=user.tenant_id,name=name,status='active');db.add(row);db.commit()
        return {'id':row.id,'name':row.name,'status':row.status,'members':0}
    @api.post('/organizations/{org}/members',status_code=201)
    def add_member(org:str,data:MemberIn,user=Depends(current_user),db:Session=Depends(get_db)):
        manage_members(db,user,org);org_lock(db,user,org)
        target=db.scalar(select(User).where(User.tenant_id==user.tenant_id,func.lower(User.email)==data.email.strip().lower()))
        if target is None:raise HTTPException(404,'کاربری با این ایمیل در این مجموعه ثبت نشده است')
        if db.scalar(select(m.EmployeeAssignment.id).where(m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.user_id==target.id,m.EmployeeAssignment.organization_id==org)) is None:
            db.add(m.EmployeeAssignment(tenant_id=user.tenant_id,user_id=target.id,organization_id=org));db.commit()
        return member_list(db,user,org)
    @api.post('/organizations/{org}/members/{uid}/remove')
    def remove_member(org:str,uid:int,user=Depends(current_user),db:Session=Depends(get_db)):
        manage_members(db,user,org)
        if uid==user.id:raise HTTPException(409,'نمی‌توانید عضویت خودتان را حذف کنید')
        row=db.scalar(select(m.EmployeeAssignment).where(m.EmployeeAssignment.tenant_id==user.tenant_id,m.EmployeeAssignment.user_id==uid,m.EmployeeAssignment.organization_id==org))
        if row is None:raise HTTPException(404,'این کاربر عضو سازمان نیست')
        grant=db.scalar(select(e.EnterpriseGrant).where(e.EnterpriseGrant.tenant_id==user.tenant_id,e.EnterpriseGrant.organization_id==org,e.EnterpriseGrant.user_id==uid))
        if grant is not None:db.delete(grant)
        db.delete(row);db.commit()
        return member_list(db,user,org)
    @api.get('/organizations/{org}/policy')
    def current_policy(org:str,user=Depends(current_user),db:Session=Depends(get_db)):
        permissions(db,user,org)
        row=db.scalar(select(e.EnterprisePolicy).where(e.EnterprisePolicy.tenant_id==user.tenant_id,e.EnterprisePolicy.organization_id==org).order_by(e.EnterprisePolicy.version.desc()))
        return {'version':row.version,'rules':json.loads(row.rules_json)} if row else {'version':None,'rules':None}
    @api.get('/organizations/{org}/summary')
    def summary(org:str,user=Depends(current_user),db:Session=Depends(get_db)):
        """Counts taken from the records themselves. No amount is estimated: money figures live in the credit and invoice records."""
        perms=permissions(db,user,org)
        if not ({'requests.read_all','policy.manage','roles.manage'}&perms):raise HTTPException(403,'مجوز مشاهدهٔ گزارش سازمان ندارید')
        t=user.tenant_id;R=e.EnterpriseRequest
        by_status=dict(db.execute(select(R.status,func.count()).where(R.tenant_id==t,R.organization_id==org).group_by(R.status)).all())
        by_use=dict(db.execute(select(R.use_case,func.count()).where(R.tenant_id==t,R.organization_id==org).group_by(R.use_case)).all())
        by_policy=dict(db.execute(select(R.policy_result,func.count()).where(R.tenant_id==t,R.organization_id==org).group_by(R.policy_result)).all())
        linked=db.scalar(select(func.count()).select_from(e.EnterpriseBookingLink).join(R,R.id==e.EnterpriseBookingLink.request_id).where(e.EnterpriseBookingLink.tenant_id==t,R.organization_id==org))
        return {'organization':{'id':org,'name':org_row(db,user,org).name},'members':db.scalar(select(func.count()).select_from(m.EmployeeAssignment).where(m.EmployeeAssignment.tenant_id==t,m.EmployeeAssignment.organization_id==org)),
                'departments':db.scalar(select(func.count()).select_from(m.Department).where(m.Department.tenant_id==t,m.Department.organization_id==org)),'cost_centers':db.scalar(select(func.count()).select_from(m.CostCenter).where(m.CostCenter.tenant_id==t,m.CostCenter.organization_id==org)),
                'requests':{'total':sum(by_status.values()),'by_status':by_status,'by_use_case':by_use,'by_policy_result':by_policy},'linked_bookings':linked,
                'credit_accounts':db.scalar(select(func.count()).select_from(m.CreditAccount).where(m.CreditAccount.tenant_id==t,m.CreditAccount.organization_id==org))}

    return api
