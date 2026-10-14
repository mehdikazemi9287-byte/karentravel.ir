"""Isolated synthetic unit fixtures only. Never connects to a project database or live provider.
Run: python -m unittest discover -s tests -p test_financial_integrity_candidate.py
"""
import copy, hashlib, json, tempfile, unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app import main,operations as m,financial_integrity as f
from app.database import Base
from app.funding_references import bank_payable
from app.ecosystem_finance import financial_projection
from app.financial_amounts import FinancialInvariantError

class FinancialCandidateChecks(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://",poolclass=StaticPool,connect_args={"check_same_thread":False})
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine,expire_on_commit=False,autoflush=False)
        self.temp=tempfile.TemporaryDirectory()
        self.oldroot=f.SOURCE_ROOT;f.SOURCE_ROOT=Path(self.temp.name)
        self.db.add_all([main.Tenant(id=1,slug="qa1",name="Mock QA"),main.Tenant(id=2,slug="qa2",name="Mock Other")])
        self.user=main.User(id=10,tenant_id=1,email="mock1@fixture.invalid",name="Mock",role="customer")
        self.db.add_all([self.user,main.User(id=20,tenant_id=2,email="mock2@fixture.invalid",name="Mock Other",role="customer")])
        self.org=m.Organization(tenant_id=1,name="Mock QA",status="active")
        self.entity=m.LicensedEntity(tenant_id=1,legal_name="Mock QA entity",status="active")
        self.wallet=m.Wallet(tenant_id=1,owner_type="user",owner_reference="10",currency="IRR")
        self.db.add_all([self.org,self.entity,self.wallet]);self.db.flush()
        self.credit=m.CreditAccount(tenant_id=1,organization_id=self.org.id,currency="IRR",limit_amount=1000)
        self.foreign=m.CreditAccount(tenant_id=2,currency="IRR",limit_amount=999999)
        self.db.add_all([self.credit,self.foreign,m.EmployeeAssignment(tenant_id=1,user_id=10,organization_id=self.org.id)])
        self.db.flush()
        self.db.add(m.FinancialLedgerEntry(tenant_id=1,wallet_id=self.wallet.id,command_id="qa-allocate",entry_type="allocate",amount=1000))
        self.booking=m.Reservation(tenant_id=1,user_id=10,service_type="hotel",status="reserved",licensed_entity_id=self.entity.id,price_snapshot_json=json.dumps({"total_amount":1000,"currency":"IRR"}),policy_at_booking_json="{}",current_policy_json="{}")
        self.db.add(self.booking);self.db.flush()
        self.checkout=m.CheckoutSession(tenant_id=1,reservation_id=self.booking.id,user_id=10,command_id="qa-checkout",stage="policy",price_snapshot_hash=main._secure_hash(self.booking.price_snapshot_json),policy_snapshot_hash=main._secure_hash("{}"),state_json="{}",expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        self.db.add(self.checkout);self.db.commit()
    def tearDown(self):
        self.db.close();self.engine.dispose();f.SOURCE_ROOT=self.oldroot;self.temp.cleanup()
    def fund(self):
        return main.advance_checkout(self.checkout.id,"funding",main.CheckoutStepIn(command_id="qa-funding1",wallet_amount=300,credit_amount=200),self.user,self.db)
    def payable(self): return bank_payable(self.db,self.booking,main._secure_hash)
    def reject(self,fn):
        with self.assertRaises((FinancialInvariantError,HTTPException,ValueError)):fn()
    def source_fixture(self):
        invoice=m.Invoice(tenant_id=1,reservation_id=self.booking.id,user_id=10,invoice_number="MOCK-QA",command_id="mock-invoice",subtotal_amount=1000,total_amount=1000,currency="IRR",status="issued")
        payment=m.PaymentIntent(tenant_id=1,reservation_id=self.booking.id,user_id=10,command_id="mock-capture",amount=300,captured_amount=300,refunded_amount=0,currency="IRR",status="captured",provider_capture_reference="MOCK-ONLY")
        self.db.add_all([invoice,payment]);self.db.flush()
        contract=f.SOURCE_ROOT/"mock-contract.txt";contract.write_text("SYNTHETIC ISOLATED TEST EVIDENCE ONLY")
        data={"schema_version":1,"tenant_id":1,"contract_documents":{"MOCK-CONTRACT":{"file":contract.name,"sha256":hashlib.sha256(contract.read_bytes()).hexdigest()}},"debts":[{"reference":"MOCK-DEBT","reservation_id":self.booking.id,"licensed_entity_id":self.entity.id,"debtor_type":"customer","debtor_id":"10","creditor_type":"legal_entity","creditor_id":self.entity.id,"contract_reference":"MOCK-CONTRACT","instrument_type":"invoice","instrument_id":invoice.id,"currency":"IRR","principal":1000,"charge":1000,"due_date":"2026-12-01"}],"opening_balances":[{"debt_reference":"MOCK-DEBT","as_of":"2020-01-01","amount":0,"currency":"IRR"}],"allocations":[{"debt_reference":"MOCK-DEBT","kind":"bank_payment","reference_id":payment.id,"category":"payment","amount":300,"currency":"IRR"}]}
        file=f.SOURCE_ROOT/"mock-source.json";file.write_text(json.dumps(data))
        payload,sha=f.read_source(file.name)
        source=f.EvidenceSource(tenant_id=1,reference=file.name,sha256=sha,payload_json=f.canonical(payload),submitted_by=101,approved_by=102,status="approved")
        self.db.add(source);self.db.commit()
        return source,data,payment
    def import_fixture(self):
        source,data,payment=self.source_fixture()
        f.import_source(self.db,1,source,main.User);self.db.commit()
        debt=self.db.scalar(select(f.DebtBinding))
        return source,debt,payment
    # The twelve pre-existing allocation guards.
    def test_01_exact_holds_and_residual(self):
        self.fund();plan=json.loads(self.checkout.state_json)["funding"]
        self.assertEqual(self.payable(),500)
        for key,amount in [("wallet_reserve_id",300),("credit_reserve_id",200)]:
            self.assertEqual(self.db.get(m.FinancialLedgerEntry,plan[key]).amount,amount)
    def test_02_replay_no_duplicate_holds(self):
        first=self.fund();before=self.db.scalar(select(func.count()).select_from(m.FinancialLedgerEntry));self.assertEqual(first,self.fund());self.assertEqual(before,self.db.scalar(select(func.count()).select_from(m.FinancialLedgerEntry)))
    def test_03_bank_intent_residual(self):
        self.fund();p=main.create_payment_intent(self.booking.id,self.user,self.db,"qa-payment-1");self.assertEqual(p["amount"],500)
    def test_04_payment_reuse(self):
        self.fund();p=main.create_payment_intent(self.booking.id,self.user,self.db,"qa-payment-1");again=main.create_payment_intent(self.booking.id,self.user,self.db,"qa-payment-2");self.assertEqual(p["id"],again["id"])
    def test_05_currency_mismatch(self):
        self.booking.price_snapshot_json=json.dumps({"total_amount":1000,"currency":"USD"});self.checkout.price_snapshot_hash=main._secure_hash(self.booking.price_snapshot_json);self.db.commit();self.reject(self.fund)
    def test_06_foreign_credit_hidden(self):
        self.reject(lambda:m.credit_balances(self.db,tenant_id=1,credit_account_id=self.foreign.id))
    def test_07_tampered_hold(self):
        self.fund();p=json.loads(self.checkout.state_json)["funding"];self.db.get(m.FinancialLedgerEntry,p["wallet_reserve_id"]).amount=301;self.db.commit();self.reject(self.payable)
    def test_08_projection_no_false_owner(self):
        self.fund();p=financial_projection(self.db,1,self.booking,price_hasher=main._secure_hash)
        self.assertFalse(p["funding_allocation"]["debt_owner_verified"]);self.assertFalse(p["funding_allocation"]["payment_success_claimed"])
    def test_09_wrong_bank_amount_pre_provider(self):
        self.fund();p=main.create_payment_intent(self.booking.id,self.user,self.db,"qa-payment-1");self.db.get(m.PaymentIntent,p["id"]).amount=1000;self.db.commit();self.reject(lambda:main.initiate_payment(p["id"],self.user,self.db))
    def test_10_expired(self):
        self.fund();self.checkout.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);self.db.commit();self.reject(self.payable)
    def test_11_source_currency_changed(self):
        self.fund();self.wallet.currency="USD";self.db.commit();self.reject(self.payable)
    def test_12_released_source(self):
        self.fund();self.db.add(m.FinancialLedgerEntry(tenant_id=1,wallet_id=self.wallet.id,reservation_id=self.booking.id,command_id="qa-release",entry_type="release",amount=300));self.db.commit();self.reject(self.payable)
    def test_13_no_source_no_import(self):
        self.reject(lambda:f.read_source("missing.json"));self.assertEqual(self.db.scalar(select(func.count()).select_from(f.DebtBinding)),0)
    def test_14_verified_import_and_replay(self):
        source,debt,payment=self.import_fixture();f.import_source(self.db,1,source,main.User);self.db.commit()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(f.SourceAllocation)),1)
        view=f.debt_view(self.db,1,debt,700);self.assertEqual(view["difference"],0);self.assertEqual(view["outstanding_amount"],700);self.assertFalse(view["closing_is_confirmed"])
    def test_15_maker_checker(self):
        source,data,payment=self.source_fixture();source.approved_by=source.submitted_by;self.db.commit();self.reject(lambda:f.import_source(self.db,1,source,main.User))
    def test_16_changed_source_refused(self):
        source,data,payment=self.source_fixture();(f.SOURCE_ROOT/source.reference).write_text("{}");self.reject(lambda:f.import_source(self.db,1,source,main.User))
    def test_17_tenant_ownership_currency(self):
        source,data,payment=self.source_fixture();item=copy.deepcopy(data["debts"][0])
        for key,value in [("debtor_id","20"),("currency","USD"),("principal",999),("licensed_entity_id","unknown")]:
            altered=dict(item);altered[key]=value;self.reject(lambda:f.validate_debt(self.db,1,altered,main.User))
    def test_18_missing_opening_not_zero(self):
        source,data,payment=self.source_fixture();data["opening_balances"]=[];(f.SOURCE_ROOT/source.reference).write_text(json.dumps(data));payload,sha=f.read_source(source.reference);source.sha256=sha;source.payload_json=f.canonical(payload);self.db.commit()
        f.import_source(self.db,1,source,main.User);debt=self.db.scalar(select(f.DebtBinding));view=f.debt_view(self.db,1,debt);self.assertIsNone(view["outstanding_amount"]);self.assertEqual(view["reconciliation_status"],"BLOCKED_BY_SOURCE_DATA")
    def test_19_discrepancy_explicit(self):
        source,debt,payment=self.import_fixture();view=f.debt_view(self.db,1,debt,699);self.assertEqual(view["difference"],1);self.assertEqual(view["reconciliation_status"],"DISCREPANCY");self.assertEqual(view["audit_source"]["sha256"],source.sha256)
    def test_20_source_currency_change(self):
        source,debt,payment=self.import_fixture();payment.currency="USD";self.db.commit();view=f.debt_view(self.db,1,debt);self.assertEqual(view["reconciliation_status"],"SOURCE_CHANGED");self.assertIsNone(view["outstanding_amount"])
    def test_21_duplicate_payment_wrong_debt(self):
        source,debt,payment=self.import_fixture();data=json.loads(source.payload_json);data["allocations"][0]["amount"]=299;(f.SOURCE_ROOT/source.reference).write_text(json.dumps(data));payload,sha=f.read_source(source.reference);source.sha256=sha;source.payload_json=f.canonical(payload);self.db.commit();self.reject(lambda:f.import_source(self.db,1,source,main.User))
    def test_22_pending_settlement_not_cash(self):
        source,debt,payment=self.import_fixture();row=m.SettlementRecord(tenant_id=1,reservation_id=self.booking.id,amount=100,currency="IRR",status="pending");self.db.add(row);self.db.flush()
        self.reject(lambda:f.allocation_value(self.db,1,debt,{"kind":"supplier_settlement","reference_id":row.id,"category":"settlement","amount":100,"currency":"IRR"}))
    def test_23_unallocated_refund_detected(self):
        source,debt,payment=self.import_fixture();payment.refunded_amount=10;self.db.commit();self.assertEqual(f.debt_view(self.db,1,debt)["reconciliation_status"],"SOURCE_CHANGED")
    def test_24_audit_and_authorization_api(self):
        source,debt,payment=self.import_fixture()
        actor=SimpleNamespace(id=102,tenant_id=1,role="finance_operator")
        app=FastAPI()
        def getdb():yield self.db
        app.include_router(f.financial_integrity_router(getdb,lambda:actor,main.role_has_permission,main.User))
        path="/ecosystem/financial-integrity/debts/"+debt.id+"/reconciliation-checks"
        with TestClient(app) as client:
            body={"command_id":"qa-audit-command","observed":699,"currency":"IRR"}
            result=client.post(path,json=body);self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()["snapshot"]["difference"],1)
            self.assertEqual(client.post(path,json=body).json()["id"],result.json()["id"])
            changed=dict(body,observed=700);self.assertEqual(client.post(path,json=changed).status_code,409)
            self.assertEqual(len(client.get(path).json()["items"]),1)
            actor.tenant_id=2;self.assertEqual(client.get(path).status_code,409)
            actor.tenant_id=1;actor.role="customer";self.assertEqual(client.get(path).status_code,403)
    def test_25_integer_and_formula_integrity(self):
        self.reject(lambda:f.reconciliation(0,1.5,0,0,0,0))
        self.assertEqual(f.reconciliation(100,1000,300,50,20,100,670)["difference"],0)

    def test_26_credit_debt_owner_exact(self):
        source,data,payment=self.source_fixture()
        row=m.FinancialLedgerEntry(tenant_id=1,credit_account_id=self.credit.id,reservation_id=self.booking.id,command_id="mock-credit-capture",entry_type="capture",amount=200)
        self.db.add(row);self.db.flush()
        item=dict(data["debts"][0],instrument_type="credit_capture",instrument_id=row.id,debtor_type="organization",debtor_id=self.org.id,principal=200,charge=200)
        f.validate_debt(self.db,1,item,main.User)
        item["debtor_id"]="not-account-owner";self.reject(lambda:f.validate_debt(self.db,1,item,main.User))
    def test_27_customer_payment_cannot_settle_supplier(self):
        source,debt,payment=self.import_fixture()
        debt.instrument_type="supplier_liability"
        self.reject(lambda:f.allocation_value(self.db,1,debt,{"kind":"bank_payment","reference_id":payment.id,"category":"payment","amount":300,"currency":"IRR"}))
    def test_28_opening_cutoff_no_double_charge(self):
        source,data,payment=self.source_fixture();data["allocations"]=[]
        data["opening_balances"][0].update(as_of="2020-01-01",amount=500)
        self.db.get(m.Invoice,data["debts"][0]["instrument_id"]).issued_at=datetime(2019,1,1,tzinfo=timezone.utc)
        (f.SOURCE_ROOT/source.reference).write_text(json.dumps(data));payload,sha=f.read_source(source.reference);source.sha256=sha;source.payload_json=f.canonical(payload);self.db.commit()
        f.import_source(self.db,1,source,main.User);debt=self.db.scalar(select(f.DebtBinding));view=f.debt_view(self.db,1,debt)
        self.assertEqual(view["new_charges"],0);self.assertEqual(view["outstanding_amount"],500)
    def test_29_followup_source_reuses_debt(self):
        source,debt,payment=self.import_fixture()
        data=json.loads(source.payload_json);data["opening_balances"]=[];data["allocations"]=[]
        file=f.SOURCE_ROOT/"mock-followup.json";file.write_text(json.dumps(data));payload,sha=f.read_source(file.name)
        other=f.EvidenceSource(tenant_id=1,reference=file.name,sha256=sha,payload_json=f.canonical(payload),submitted_by=101,approved_by=102,status="approved")
        self.db.add(other);self.db.commit();f.import_source(self.db,1,other,main.User)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(f.DebtBinding)),1)
    def test_30_cash_refund_is_not_debt_waiver(self):
        source,data,payment=self.source_fixture()
        refund=m.RefundRecord(tenant_id=1,payment_intent_id=payment.id,command_id="mock-refund",amount=10,status="succeeded",provider_reference="MOCK-ONLY")
        self.db.add(refund);self.db.flush();payment.refunded_amount=10
        data["allocations"].append({"debt_reference":"MOCK-DEBT","kind":"cash_refund","reference_id":refund.id,"category":"refund","amount":10,"currency":"IRR"})
        (f.SOURCE_ROOT/source.reference).write_text(json.dumps(data));payload,sha=f.read_source(source.reference);source.sha256=sha;source.payload_json=f.canonical(payload);self.db.commit()
        f.import_source(self.db,1,source,main.User);debt=self.db.scalar(select(f.DebtBinding));view=f.debt_view(self.db,1,debt)
        self.assertEqual(view["cash_refunds"],10);self.assertEqual(view["outstanding_amount"],710)

    def test_31_duplicate_external_bank_capture(self):
        source,debt,payment=self.import_fixture()
        self.db.add(m.PaymentIntent(tenant_id=1,reservation_id=self.booking.id,user_id=10,command_id="mock-capture-duplicate",amount=300,captured_amount=300,refunded_amount=0,currency="IRR",status="captured",provider_key=payment.provider_key,provider_capture_reference=payment.provider_capture_reference));self.db.flush()
        self.assertEqual(f.debt_view(self.db,1,debt)["reconciliation_status"],"SOURCE_CHANGED")
    def test_32_future_opening_rejected(self):
        source,data,payment=self.source_fixture();data["opening_balances"][0]["as_of"]="2099-01-01"
        (f.SOURCE_ROOT/source.reference).write_text(json.dumps(data));payload,sha=f.read_source(source.reference);source.sha256=sha;source.payload_json=f.canonical(payload);self.db.commit()
        self.reject(lambda:f.import_source(self.db,1,source,main.User))

    def test_33_staging_approval_import_api(self):
        source,data,payment=self.source_fixture();data["opening_balances"]=[];data["allocations"]=[]
        file=f.SOURCE_ROOT/"mock-staging.json";file.write_text(json.dumps(data));payload,sha=f.read_source(file.name)
        actor=SimpleNamespace(id=101,tenant_id=1,role="finance_operator")
        app=FastAPI()
        def getdb():yield self.db
        app.include_router(f.financial_integrity_router(getdb,lambda:actor,main.role_has_permission,main.User))
        base="/ecosystem/financial-integrity/sources"
        with TestClient(app) as client:
            staged=client.post(base,json={"reference":file.name,"sha256":sha});self.assertEqual(staged.status_code,200,staged.text)
            id=staged.json()["id"]
            self.assertEqual(staged.json()["status"],"pending")
            self.assertEqual(client.post(base+"/"+id+"/import").status_code,409)
            self.assertEqual(client.post(base+"/"+id+"/approve").status_code,409)
            actor.id=102
            self.assertEqual(client.post(base+"/"+id+"/approve").status_code,200)
            imported=client.post(base+"/"+id+"/import");self.assertEqual(imported.status_code,200,imported.text)
            self.assertEqual(imported.json()["debts"],1)
    def test_34_contract_evidence_changed_on_read(self):
        source,debt,payment=self.import_fixture()
        (f.SOURCE_ROOT/"mock-contract.txt").write_text("CHANGED SYNTHETIC TEST CONTRACT")
        self.assertEqual(f.debt_view(self.db,1,debt)["reconciliation_status"],"SOURCE_CHANGED")

    def test_35_supplier_liability_and_duplicate_settlement(self):
        source,data,payment=self.source_fixture()
        supplier=m.Supplier(tenant_id=1,supplier_type="hotel",display_name="MOCK QA SUPPLIER",status="active")
        self.db.add(supplier);self.db.flush()
        contract=m.ProviderContract(tenant_id=1,supplier_id=supplier.id,provider_key="MOCK QA",mode="disabled")
        self.db.add(contract);self.db.flush()
        price=m.PriceBreakdown(tenant_id=1,booking_id=self.booking.id,source_contract_id=contract.id,supplier_net_rate=400,supplier_currency="IRR",supplier_net_rate_irr=400,total_selling_price=1000)
        self.booking.status="confirmed";self.booking.confirmed_at=datetime.now(timezone.utc);self.db.add(price);self.db.flush()
        item=dict(data["debts"][0],instrument_type="supplier_liability",instrument_id=price.id,debtor_type="legal_entity",debtor_id=self.entity.id,creditor_type="supplier",creditor_id=supplier.id,principal=400,charge=400)
        f.validate_debt(self.db,1,item,main.User)
        debt=f.DebtBinding(tenant_id=1,source_id=source.id,**item)
        settlement=m.SettlementRecord(tenant_id=1,supplier_id=supplier.id,reservation_id=self.booking.id,amount=400,currency="IRR",status="paid",external_reference="MOCK-TRANSFER")
        self.db.add_all([debt,settlement]);self.db.flush()
        allocation={"kind":"supplier_settlement","reference_id":settlement.id,"category":"settlement","amount":400,"currency":"IRR"}
        self.assertEqual(f.allocation_value(self.db,1,debt,allocation),400)
        self.db.add(m.SettlementRecord(tenant_id=1,supplier_id=supplier.id,reservation_id=self.booking.id,amount=400,currency="IRR",status="paid",external_reference="MOCK-TRANSFER"));self.db.flush()
        self.reject(lambda:f.allocation_value(self.db,1,debt,allocation))
    def test_36_reversed_credit_debt_refused(self):
        row=m.FinancialLedgerEntry(tenant_id=1,credit_account_id=self.credit.id,reservation_id=self.booking.id,command_id="mock-loan-capture",entry_type="capture",amount=200)
        self.db.add(row);self.db.flush()
        self.db.add(m.FinancialLedgerEntry(tenant_id=1,credit_account_id=self.credit.id,reservation_id=self.booking.id,command_id="mock-loan-reverse",entry_type="reverse_capture",amount=200,reversal_of_id=row.id));self.db.flush()
        self.reject(lambda:f.instrument(self.db,1,"credit_capture",row.id))

    def test_37_purchase_bank_payment_is_not_credit_repayment(self):
        source,debt,payment=self.import_fixture();debt.instrument_type="credit_capture"
        self.reject(lambda:f.allocation_value(self.db,1,debt,{"kind":"bank_payment","reference_id":payment.id,"category":"payment","amount":300,"currency":"IRR"}))

if __name__=="__main__":unittest.main()
