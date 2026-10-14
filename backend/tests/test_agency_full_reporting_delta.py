"""Synthetic boundary fixtures: more than 500 bookings and same-tenant peer isolation."""
import json
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import select, delete
from app.main import SessionLocal, User
from app import operations as m

def login(client,email):
    token=client.post("/auth/dev-login",json={"email":email}).json()["access_token"]
    return {"Authorization":"Bearer "+token}

def test_full_agency_reporting_does_not_share_the_visible_booking_limit(client):
    headers=login(client,"agency@aftab.test")
    suffix=uuid4().hex;agencies=[];channels=[];reservation_ids=[]
    with SessionLocal() as db:
        actor=db.scalar(select(User).where(User.email=="agency@aftab.test"))
        customer=db.scalar(select(User).where(User.email=="employee@aftab.test"))
        license=m.LicensedEntity(tenant_id=actor.tenant_id,legal_name="Mock QA "+suffix);db.add(license);db.flush();license_id=license.id
        for index in range(2):
            channel=m.SalesChannel(tenant_id=actor.tenant_id,name=f"Mock QA {suffix}-{index}",licensed_entity_id=license.id)
            db.add(channel);db.flush();channels.append(channel.id)
            agency=m.Agency(tenant_id=actor.tenant_id,display_name=f"Mock QA {suffix}-{index}",status="active",commission_bps=1000,sales_channel_id=channel.id)
            db.add(agency);db.flush();agencies.append(agency.id)
            if index==0:db.add(m.AgencyMembership(tenant_id=actor.tenant_id,user_id=actor.id,agency_id=agency.id))
        for index in range(503):
            amount,currency=(200,"USD") if index==501 else ((99999,"IRR") if index==502 else (100,"IRR"))
            row=m.Reservation(tenant_id=actor.tenant_id,user_id=customer.id,sales_channel_id=channels[1 if index==502 else 0],service_type="hotel",status="confirmed",
                              confirmed_at=datetime.now(timezone.utc),price_snapshot_json=json.dumps({"total_amount":amount,"currency":currency}),policy_at_booking_json="{}",current_policy_json="{}")
            if index==0:row.created_at=datetime(2020,1,1,tzinfo=timezone.utc)
            db.add(row);db.flush();reservation_ids.append(row.id)
        settlement=m.SettlementRecord(tenant_id=actor.tenant_id,reservation_id=reservation_ids[0],amount=100,currency="IRR");db.add(settlement);db.flush();settlement_id=settlement.id
        db.commit()
    try:
        base="/agency/"+agencies[0]
        assert len(client.get(base+"/bookings",headers=headers).json()["items"])==500
        report=client.get(base+"/report",headers=headers).json()
        assert report["bookings"]==502 and report["by_status"]=={"confirmed":502}
        assert {x["currency"]:x["amount"] for x in report["confirmed_sales"]}=={"IRR":50100,"USD":200}
        customers=client.get(base+"/customers",headers=headers).json()["items"]
        assert len(customers)==1 and customers[0]["bookings"]==502
        commissions=client.get(base+"/commissions",headers=headers).json()
        assert len(commissions["items"])==500
        assert {x["currency"]:x["commission_amount"] for x in commissions["totals"]}=={"IRR":5010,"USD":20}
        assert settlement_id in {s["id"] for s in client.get(base+"/settlements",headers=headers).json()["items"]}
        dashboard=client.get("/agency/dashboard",headers=headers).json()["agencies"]
        assert agencies[0] in {a["id"] for a in dashboard} and agencies[1] not in {a["id"] for a in dashboard}
        assert client.put("/agency/agencies/"+agencies[1],headers=headers,json={"commission_bps":9999}).status_code==404
        assert client.post("/agency/sub-agencies",headers=headers,json={"display_name":"Mock forbidden child","parent_agency_id":agencies[1],"markup_bps":0,"commission_bps":0}).status_code==404
        assert client.get("/agency/"+agencies[1]+"/report",headers=headers).status_code==404
    finally:
        with SessionLocal() as db:
            db.execute(delete(m.SettlementRecord).where(m.SettlementRecord.reservation_id.in_(reservation_ids)))
            db.execute(delete(m.Reservation).where(m.Reservation.id.in_(reservation_ids)))
            db.execute(delete(m.AgencyMembership).where(m.AgencyMembership.agency_id.in_(agencies)))
            db.execute(delete(m.Agency).where(m.Agency.id.in_(agencies)))
            db.execute(delete(m.SalesChannel).where(m.SalesChannel.id.in_(channels)))
            db.execute(delete(m.LicensedEntity).where(m.LicensedEntity.id==license_id));db.commit()

def test_new_agency_creator_gets_membership_and_own_edit_access(client):
    headers=login(client,"agency@aftab.test")
    created=client.post("/agency/sub-agencies",headers=headers,json={"display_name":"Mock own agency "+uuid4().hex,"commission_bps":500,"markup_bps":0})
    assert created.status_code==201
    aid=created.json()["id"]
    assert aid in {a["id"] for a in client.get("/agency/workspace",headers=headers).json()["agencies"]}
    assert client.put("/agency/agencies/"+aid,headers=headers,json={"markup_bps":200}).status_code==200
