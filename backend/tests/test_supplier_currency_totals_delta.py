"""Synthetic >200 multi-currency settlements; never combine currencies into IRR."""
from uuid import uuid4
from sqlalchemy import select, delete
from app.main import SessionLocal, User
from app import operations as m

def test_supplier_dashboard_keeps_each_currency_and_excludes_unassigned_supplier(client):
    token=client.post("/auth/dev-login",json={"email":"supplier@aftab.test"}).json()["access_token"]
    headers={"Authorization":"Bearer "+token};ids=[];settlements=[]
    initial=client.get("/supplier/dashboard",headers=headers).json()["settlements"]
    initial_totals={r["currency"]:r["amount"] for r in initial["totals"]}
    initial_groups={(r["status"],r["currency"]):r["amount"] for r in client.get("/supplier/settlements",headers=headers).json()["totals"]}
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=="supplier@aftab.test"))
        for index in range(2):
            supplier=m.Supplier(tenant_id=user.tenant_id,supplier_type="hotel",display_name="Mock currency "+uuid4().hex,status="active")
            db.add(supplier);db.flush();ids.append(supplier.id)
            if index==0:db.add(m.SupplierMembership(tenant_id=user.tenant_id,user_id=user.id,supplier_id=supplier.id))
        values=[(ids[0],"IRR",1)]*205+[(ids[0],"USD",10),(ids[1],"IRR",99999)]
        for supplier,currency,amount in values:
            row=m.SettlementRecord(tenant_id=user.tenant_id,supplier_id=supplier,currency=currency,amount=amount,status="pending")
            db.add(row);db.flush();settlements.append(row.id)
        db.commit()
    try:
        result=client.get("/supplier/dashboard",headers=headers)
        assert result.status_code==200
        body=result.json()["settlements"]
        assert body["amount"] is None and body["currency"] is None and body["count"]==initial["count"]+206
        expected=dict(initial_totals);expected["IRR"]=expected.get("IRR",0)+205;expected["USD"]=expected.get("USD",0)+10
        assert {t["currency"]:t["amount"] for t in body["totals"]}==expected
        assert ids[1] not in {s["id"] for s in result.json()["supplier_records"]}
        report=client.get("/supplier/settlements",headers=headers).json()
        assert len(report["items"])==200
        groups=dict(initial_groups);groups[("pending","IRR")]=groups.get(("pending","IRR"),0)+205;groups[("pending","USD")]=groups.get(("pending","USD"),0)+10
        assert {(t["status"],t["currency"]):t["amount"] for t in report["totals"]}==groups
    finally:
        with SessionLocal() as db:
            db.execute(delete(m.SettlementRecord).where(m.SettlementRecord.id.in_(settlements)))
            db.execute(delete(m.SupplierMembership).where(m.SupplierMembership.supplier_id.in_(ids)))
            db.execute(delete(m.Supplier).where(m.Supplier.id.in_(ids)));db.commit()
