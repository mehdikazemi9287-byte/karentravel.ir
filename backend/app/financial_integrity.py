"""Evidence-backed debt ownership and opening balances; never infer a payer from membership.
All monetary values are integer minor units. An approved source is immutable and two-person checked.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import mapped_column
from .database import Base
from . import operations as m
from .financial_amounts import FinancialInvariantError, minor, currency_code

SOURCE_ROOT = Path("/financial-sources")
TABLES = ("financial_evidence_sources", "financial_debt_bindings", "financial_opening_balances", "financial_source_allocations", "financial_balance_checks")

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

class EvidenceSource(m.OperationalMixin, Base):
    __tablename__ = TABLES[0]
    reference = mapped_column(String(160), nullable=False)
    sha256 = mapped_column(String(64), nullable=False)
    payload_json = mapped_column(Text, nullable=False)
    submitted_by = mapped_column(Integer, nullable=False)
    approved_by = mapped_column(Integer, nullable=True)
    status = mapped_column(String(24), nullable=False, default="pending")
    __table_args__ = (UniqueConstraint("tenant_id", "reference"), UniqueConstraint("tenant_id", "sha256"))

class DebtBinding(m.OperationalMixin, Base):
    __tablename__ = TABLES[1]
    source_id = mapped_column(ForeignKey(TABLES[0] + ".id"), nullable=False)
    reference = mapped_column(String(160), nullable=False)
    reservation_id = mapped_column(ForeignKey("reservations.id"), nullable=False)
    licensed_entity_id = mapped_column(ForeignKey("licensed_entities.id"), nullable=False)
    debtor_type = mapped_column(String(24), nullable=False)
    debtor_id = mapped_column(String(64), nullable=False)
    creditor_type = mapped_column(String(24), nullable=False)
    creditor_id = mapped_column(String(64), nullable=False)
    contract_reference = mapped_column(String(160), nullable=False)
    instrument_type = mapped_column(String(24), nullable=False)
    instrument_id = mapped_column(String(64), nullable=False)
    currency = mapped_column(String(3), nullable=False)
    principal = mapped_column(BigInteger, nullable=False)
    charge = mapped_column(BigInteger, nullable=False)
    due_date = mapped_column(String(10), nullable=True)
    __table_args__ = (
        UniqueConstraint("tenant_id", "reference"),
        UniqueConstraint("tenant_id", "instrument_type", "instrument_id"),
        UniqueConstraint("tenant_id", "reservation_id", "debtor_type", "debtor_id", "creditor_type", "creditor_id"),
        CheckConstraint("principal >= 0 AND charge >= principal"),
        CheckConstraint("debtor_type IN ('customer','organization','legal_entity','supplier')"),
        CheckConstraint("creditor_type IN ('customer','organization','legal_entity','supplier')"),
    )

class OpeningBalance(m.OperationalMixin, Base):
    __tablename__ = TABLES[2]
    source_id = mapped_column(ForeignKey(TABLES[0] + ".id"), nullable=False)
    debt_id = mapped_column(ForeignKey(TABLES[1] + ".id"), nullable=False)
    as_of = mapped_column(String(10), nullable=False)
    amount = mapped_column(BigInteger, nullable=False)
    currency = mapped_column(String(3), nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "debt_id"), CheckConstraint("amount >= 0"))

class SourceAllocation(m.OperationalMixin, Base):
    __tablename__ = TABLES[3]
    source_id = mapped_column(ForeignKey(TABLES[0] + ".id"), nullable=False)
    debt_id = mapped_column(ForeignKey(TABLES[1] + ".id"), nullable=False)
    kind = mapped_column(String(24), nullable=False)
    reference_id = mapped_column(String(64), nullable=False)
    category = mapped_column(String(16), nullable=False)
    amount = mapped_column(BigInteger, nullable=False)
    currency = mapped_column(String(3), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "reference_id"),
        CheckConstraint("amount > 0"),
        CheckConstraint("category IN ('payment','credit','refund','settlement')"),
    )

class BalanceCheck(m.OperationalMixin, Base):
    __tablename__ = TABLES[4]
    debt_id = mapped_column(ForeignKey(TABLES[1] + ".id"), nullable=False)
    command_id = mapped_column(String(120), nullable=False)
    request_hash = mapped_column(String(64), nullable=False)
    actor_id = mapped_column(Integer, nullable=False)
    snapshot_json = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id","command_id"),)

def tenant_row(db, model, tenant, key):
    row = db.scalar(select(model).where(model.tenant_id == tenant, model.id == key))
    if row is None:
        raise FinancialInvariantError("SOURCE_REFERENCE_NOT_IN_TENANT")
    return row

def party(db, tenant, kind, key, User):
    classes = {"customer": User, "organization": m.Organization, "legal_entity": m.LicensedEntity, "supplier": m.Supplier}
    if kind not in classes:
        raise FinancialInvariantError("UNSUPPORTED_PARTY_TYPE")
    tenant_row(db, classes[kind], tenant, int(key) if kind == "customer" else key)

def instrument(db, tenant, kind, key):
    if kind == "invoice":
        row = tenant_row(db, m.Invoice, tenant, key)
        if row.status != "issued":
            raise FinancialInvariantError("INVOICE_NOT_ISSUED")
        return row.reservation_id, currency_code(row.currency), minor(row.total_amount), minor(row.total_amount)
    if kind == "installment":
        row = tenant_row(db, m.InstallmentAgreement, tenant, key)
        if row.status != "active":
            raise FinancialInvariantError("INSTALLMENT_NOT_ACTIVE")
        return row.reservation_id, currency_code(row.currency), minor(row.principal_amount), minor(row.total_payable)
    if kind == "credit_capture":
        row = tenant_row(db, m.FinancialLedgerEntry, tenant, key)
        if row.entry_type != "capture" or not row.credit_account_id or row.wallet_id:
            raise FinancialInvariantError("CREDIT_CAPTURE_REQUIRED")
        changed=db.scalar(select(m.FinancialLedgerEntry.id).where(m.FinancialLedgerEntry.tenant_id==tenant,m.FinancialLedgerEntry.reversal_of_id==row.id).limit(1))
        if changed is not None:
            raise FinancialInvariantError("REVERSED_CREDIT_CAPTURE_REQUIRES_RECONCILIATION")
        account = tenant_row(db, m.CreditAccount, tenant, row.credit_account_id)
        return row.reservation_id, currency_code(account.currency), minor(row.amount), minor(row.amount)
    if kind == "supplier_liability":
        row = tenant_row(db,m.PriceBreakdown,tenant,key)
        booking = tenant_row(db,m.Reservation,tenant,row.booking_id)
        if booking.status not in {"confirmed","issued","completed"} or not row.source_contract_id:
            raise FinancialInvariantError("CONFIRMED_CONTRACTED_SUPPLY_REQUIRED")
        tenant_row(db,m.ProviderContract,tenant,row.source_contract_id)
        from .financial_amounts import supplier_liability
        # This is cost owed to supplier, never customer selling gross.
        currency = currency_code(row.supplier_currency)
        amount = supplier_liability(row,currency)
        return row.booking_id,currency,minor(amount),minor(amount)
    raise FinancialInvariantError("UNSUPPORTED_DEBT_INSTRUMENT")

def validate_debt(db, tenant, data, User):
    required = {"reference","reservation_id","licensed_entity_id","debtor_type","debtor_id","creditor_type","creditor_id","contract_reference","instrument_type","instrument_id","currency","principal","charge","due_date"}
    if set(data) != required or not data["contract_reference"] or not data["reference"]:
        raise FinancialInvariantError("EXPLICIT_CONTRACT_AND_OWNERS_REQUIRED")
    for prefix in ("debtor", "creditor"):
        party(db, tenant, data[prefix + "_type"], data[prefix + "_id"], User)
    if (data["debtor_type"], str(data["debtor_id"])) == (data["creditor_type"], str(data["creditor_id"])):
        raise FinancialInvariantError("SELF_DEBT_FORBIDDEN")
    booking = tenant_row(db, m.Reservation, tenant, data["reservation_id"])
    tenant_row(db, m.LicensedEntity, tenant, data["licensed_entity_id"])
    if booking.licensed_entity_id != data["licensed_entity_id"]:
        raise FinancialInvariantError("LEGAL_ENTITY_MISMATCH")
    reservation, currency, principal, charge = instrument(db, tenant, data["instrument_type"], data["instrument_id"])
    if reservation != booking.id or currency_code(data["currency"]) != currency or minor(data["principal"]) != principal or minor(data["charge"]) != charge:
        raise FinancialInvariantError("DEBT_INSTRUMENT_MISMATCH")
    if data["due_date"] is not None:
        date.fromisoformat(data["due_date"])
    if data["instrument_type"] in {"invoice","installment","credit_capture"}:
        if (data["creditor_type"],str(data["creditor_id"])) != ("legal_entity",booking.licensed_entity_id):
            raise FinancialInvariantError("ISSUING_ENTITY_CREDITOR_REQUIRED")
        if data["debtor_type"] == "customer" and str(data["debtor_id"]) != str(booking.user_id):
            raise FinancialInvariantError("CUSTOMER_OWNERSHIP_MISMATCH")
        if data["debtor_type"] not in {"customer","organization"}:
            raise FinancialInvariantError("CUSTOMER_OR_ORGANIZATION_DEBTOR_REQUIRED")
    if data["instrument_type"] == "credit_capture":
        capture = tenant_row(db, m.FinancialLedgerEntry, tenant, data["instrument_id"])
        account = tenant_row(db, m.CreditAccount, tenant, capture.credit_account_id)
        owner = ("organization", str(account.organization_id)) if account.organization_id else ("customer", str(account.user_id))
        if (data["debtor_type"], str(data["debtor_id"])) != owner:
            raise FinancialInvariantError("CREDIT_ACCOUNT_OWNERSHIP_MISMATCH")
    return data

def allocation_value(db, tenant, debt, data):
    kind, key = data["kind"], data["reference_id"]
    if debt.instrument_type=="credit_capture":
        # Purchase funding is not a repayment of the resulting credit obligation.
        # Existing payment intents have no authoritative credit-repayment relation.
        raise FinancialInvariantError("CREDIT_REPAYMENT_REFERENCE_REQUIRED")
    if debt.instrument_type=="supplier_liability" and kind!="supplier_settlement" or debt.instrument_type!="supplier_liability" and kind=="supplier_settlement":
        raise FinancialInvariantError("CUSTOMER_PAYMENT_IS_NOT_SUPPLIER_SETTLEMENT")
    if kind == "bank_payment":
        row = tenant_row(db, m.PaymentIntent, tenant, key)
        if row.status not in {"captured","refunded"} or not row.provider_capture_reference:
            raise FinancialInvariantError("PAYMENT_NOT_VERIFIED_CAPTURE")
        duplicates=db.scalars(select(m.PaymentIntent.id).where(m.PaymentIntent.tenant_id==tenant,m.PaymentIntent.provider_key==row.provider_key,m.PaymentIntent.provider_capture_reference==row.provider_capture_reference,m.PaymentIntent.status.in_(["captured","refunded"]))).all()
        if len(duplicates)!=1 or minor(row.captured_amount)>minor(row.amount) or minor(row.refunded_amount)>minor(row.captured_amount):
            raise FinancialInvariantError("DUPLICATE_OR_INVALID_BANK_CAPTURE")
        booking=tenant_row(db,m.Reservation,tenant,debt.reservation_id)
        if row.user_id != booking.user_id:
            raise FinancialInvariantError("PAYMENT_OWNERSHIP_MISMATCH")
        category, amount, currency, reservation = "payment", minor(row.captured_amount), row.currency, row.reservation_id
    elif kind == "wallet_capture":
        row = tenant_row(db, m.FinancialLedgerEntry, tenant, key)
        if row.entry_type != "capture" or not row.wallet_id or row.credit_account_id:
            raise FinancialInvariantError("WALLET_CAPTURE_REQUIRED")
        wallet = tenant_row(db, m.Wallet, tenant, row.wallet_id)
        booking = tenant_row(db, m.Reservation, tenant, debt.reservation_id)
        if wallet.owner_type != "user" or str(wallet.owner_reference) != str(booking.user_id):
            raise FinancialInvariantError("WALLET_OWNERSHIP_MISMATCH")
        reversals = db.scalars(select(m.FinancialLedgerEntry).where(m.FinancialLedgerEntry.tenant_id == tenant, m.FinancialLedgerEntry.reversal_of_id == key)).all()
        if reversals:
            raise FinancialInvariantError("REVERSED_CAPTURE_REQUIRES_RECONCILIATION")
        category, amount, currency, reservation = "payment", minor(row.amount), wallet.currency, row.reservation_id
    elif kind == "supplier_settlement":
        row = tenant_row(db, m.SettlementRecord, tenant, key)
        if row.status not in {"paid","completed","settled"} or not row.external_reference or debt.creditor_type != "supplier" or debt.creditor_id != row.supplier_id:
            raise FinancialInvariantError("VERIFIED_SUPPLIER_SETTLEMENT_REQUIRED")
        duplicates=db.scalars(select(m.SettlementRecord.id).where(m.SettlementRecord.tenant_id==tenant,m.SettlementRecord.external_reference==row.external_reference,m.SettlementRecord.status.in_(["paid","completed","settled"]))).all()
        if len(duplicates)!=1:
            raise FinancialInvariantError("DUPLICATE_SETTLEMENT_EXTERNAL_REFERENCE")
        category, amount, currency, reservation = "settlement", minor(row.amount), row.currency, row.reservation_id
    elif kind == "cash_refund":
        row = tenant_row(db,m.RefundRecord,tenant,key)
        payment = tenant_row(db,m.PaymentIntent,tenant,row.payment_intent_id)
        if row.status != "succeeded" or not row.provider_reference or minor(payment.refunded_amount) < minor(row.amount):
            raise FinancialInvariantError("VERIFIED_CASH_REFUND_REQUIRED")
        linked = db.scalar(select(SourceAllocation).where(SourceAllocation.tenant_id==tenant,SourceAllocation.debt_id==debt.id,SourceAllocation.kind=="bank_payment",SourceAllocation.reference_id==payment.id))
        if linked is None:
            raise FinancialInvariantError("REFUND_PAYMENT_ALLOCATION_REQUIRED")
        category,amount,currency,reservation = "refund",minor(row.amount),payment.currency,payment.reservation_id
    else:
        # Refunds of cash increase receivables; they must not be subtracted as a debt waiver.
        # Credit notes need an authoritative issued-credit-note model before importing.
        raise FinancialInvariantError("UNSUPPORTED_FINANCIAL_SOURCE")
    if reservation != debt.reservation_id or currency_code(currency) != debt.currency or data["category"] != category or minor(data["amount"]) != amount or currency_code(data["currency"]) != debt.currency:
        raise FinancialInvariantError("ALLOCATION_SOURCE_MISMATCH")
    if amount == 0:
        raise FinancialInvariantError("ZERO_ALLOCATION_FORBIDDEN")
    return amount

def read_source(reference):
    if not reference or "/" in reference or "\\" in reference or not reference.endswith(".json"):
        raise FinancialInvariantError("SOURCE_FILENAME_REQUIRED")
    path = (SOURCE_ROOT / reference).resolve()
    if path.parent != SOURCE_ROOT.resolve() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise FinancialInvariantError("BLOCKED_BY_SOURCE_DATA")
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {"schema_version","tenant_id","contract_documents","debts","opening_balances","allocations"} or data["schema_version"] != 1:
        raise FinancialInvariantError("SOURCE_SCHEMA_INVALID")
    if not isinstance(data["contract_documents"], dict) or not all(isinstance(data[k], list) for k in ("debts","opening_balances","allocations")):
        raise FinancialInvariantError("SOURCE_SCHEMA_INVALID")
    for ref, doc in data["contract_documents"].items():
        if not isinstance(ref, str) or not isinstance(doc, dict) or set(doc) != {"file","sha256"}:
            raise FinancialInvariantError("CONTRACT_EVIDENCE_REQUIRED")
        file = (SOURCE_ROOT / doc["file"]).resolve()
        if file.parent != SOURCE_ROOT.resolve() or not file.is_file() or file.stat().st_size > 20_000_000 or hashlib.sha256(file.read_bytes()).hexdigest() != doc["sha256"]:
            raise FinancialInvariantError("CONTRACT_DOCUMENT_HASH_MISMATCH")
    return data, hashlib.sha256(raw).hexdigest()

def import_source(db, tenant, source, User):
    if source.status != "approved" or source.approved_by == source.submitted_by:
        raise FinancialInvariantError("TWO_PERSON_SOURCE_APPROVAL_REQUIRED")
    data, sha = read_source(source.reference)
    if sha != source.sha256 or canonical(data) != source.payload_json or data["tenant_id"] != tenant:
        raise FinancialInvariantError("SOURCE_CHANGED_OR_TENANT_MISMATCH")
    # One atomic transaction, serialize imports across all sources within this tenant.
    from .main import Tenant
    db.scalar(select(Tenant).where(Tenant.id == tenant).with_for_update())
    debts = {}
    for item in data["debts"]:
        validate_debt(db, tenant, item, User)
        if item["contract_reference"] not in data["contract_documents"]:
            raise FinancialInvariantError("CONTRACT_EVIDENCE_REQUIRED")
        existing = db.scalar(select(DebtBinding).where(DebtBinding.tenant_id == tenant, DebtBinding.reference == item["reference"]))
        if existing:
            if any(str(getattr(existing,k)) != str(v) for k,v in item.items()):
                raise FinancialInvariantError("DEBT_IDEMPOTENCY_CONFLICT")
            debt = existing
        else:
            debt = DebtBinding(tenant_id=tenant,source_id=source.id,**item)
            db.add(debt); db.flush()
        debts[item["reference"]] = debt
    for item in data["opening_balances"]:
        if set(item) != {"debt_reference","as_of","amount","currency"}:
            raise FinancialInvariantError("OPENING_SCHEMA_INVALID")
        debt = debts.get(item["debt_reference"])
        if not debt or currency_code(item["currency"]) != debt.currency:
            raise FinancialInvariantError("OPENING_DEBT_OR_CURRENCY_MISMATCH")
        if date.fromisoformat(item["as_of"]) >= datetime.now(timezone.utc).date():
            raise FinancialInvariantError("CLOSED_DAY_OPENING_CUTOFF_REQUIRED")
        amount = minor(item["amount"])
        old = db.scalar(select(OpeningBalance).where(OpeningBalance.tenant_id == tenant,OpeningBalance.debt_id == debt.id))
        if old:
            if old.source_id != source.id or old.amount != amount or old.as_of != item["as_of"] or old.currency != debt.currency:
                raise FinancialInvariantError("OPENING_IDEMPOTENCY_CONFLICT")
        else:
            db.add(OpeningBalance(tenant_id=tenant,source_id=source.id,debt_id=debt.id,as_of=item["as_of"],amount=amount,currency=debt.currency));db.flush()
    for item in sorted(data["allocations"],key=lambda x:x.get("kind")=="cash_refund"):
        if set(item) != {"debt_reference","kind","reference_id","category","amount","currency"}:
            raise FinancialInvariantError("ALLOCATION_SCHEMA_INVALID")
        debt = debts.get(item["debt_reference"])
        if debt is None: raise FinancialInvariantError("DEBT_REFERENCE_REQUIRED")
        allocation_value(db,tenant,debt,item)
        old = db.scalar(select(SourceAllocation).where(SourceAllocation.tenant_id == tenant,SourceAllocation.kind == item["kind"],SourceAllocation.reference_id == item["reference_id"]))
        if old:
            if old.debt_id != debt.id or old.source_id != source.id or old.amount != item["amount"] or old.category != item["category"] or old.currency != debt.currency:
                raise FinancialInvariantError("DUPLICATE_PAYMENT_OR_SETTLEMENT")
        else:
            db.add(SourceAllocation(tenant_id=tenant,source_id=source.id,debt_id=debt.id,**{k:v for k,v in item.items() if k != "debt_reference"}));db.flush()
    for debt in debts.values():
        view = debt_view(db,tenant,debt)
        if view["calculated_closing_balance"] is not None and view["calculated_closing_balance"] < 0:
            raise FinancialInvariantError("OVERPAYMENT_REQUIRES_RECONCILIATION")
    return {"debts":len(debts),"opening_balances":len(data["opening_balances"]),"allocations":len(data["allocations"]),"source_id":source.id}

def reconciliation(opening, charges, payments, credits, refunds, settlements, observed=None):
    for value in (charges,payments,credits,refunds,settlements):
        minor(value)
    if opening is None:
        return {"calculated_closing_balance":None,"observed_closing_balance":observed,"difference":None,"reconciliation_status":"BLOCKED_BY_SOURCE_DATA"}
    closing = minor(opening) + charges - payments - credits + refunds - settlements
    if observed is not None: minor(observed)
    return {"calculated_closing_balance":closing,"observed_closing_balance":observed,"difference":None if observed is None else closing-observed,"reconciliation_status":"UNVERIFIED_CLOSING" if observed is None else ("MATCHED" if closing==observed else "DISCREPANCY")}

def debt_view(db,tenant,debt,observed=None):
    source = tenant_row(db,EvidenceSource,tenant,debt.source_id)
    opening = db.scalar(select(OpeningBalance).where(OpeningBalance.tenant_id==tenant,OpeningBalance.debt_id==debt.id))
    rows = db.scalars(select(SourceAllocation).where(SourceAllocation.tenant_id==tenant,SourceAllocation.debt_id==debt.id)).all()
    totals = dict(payment=0,credit=0,refund=0,settlement=0)
    errors = []
    instrument_model={"invoice":m.Invoice,"installment":m.InstallmentAgreement,"credit_capture":m.FinancialLedgerEntry,"supplier_liability":m.PriceBreakdown}[debt.instrument_type]
    instrument_row=tenant_row(db,instrument_model,tenant,debt.instrument_id)
    cutoff=date.fromisoformat(opening.as_of) if opening else None
    effective=instrument_row.issued_at if debt.instrument_type=="invoice" else instrument_row.created_at if debt.instrument_type=="credit_capture" else None
    if debt.instrument_type=="supplier_liability":
        effective=tenant_row(db,m.Reservation,tenant,debt.reservation_id).confirmed_at
    new_charges=debt.charge if cutoff is None or effective is None or effective.date()>cutoff else 0
    if cutoff is not None and effective is None:
        errors.append("CHARGE_EFFECTIVE_DATE_REQUIRED")
    # Revalidate referenced live records on every read; source snapshots do not hide reversals.
    try:
        from .main import User
        checked_sources={source.id}
        checked_sources.update(x.source_id for x in rows)
        if opening: checked_sources.add(opening.source_id)
        for key in checked_sources:
            evidence=tenant_row(db,EvidenceSource,tenant,key)
            payload,sha=read_source(evidence.reference)
            if evidence.status!="approved" or evidence.approved_by is None or evidence.approved_by==evidence.submitted_by or sha!=evidence.sha256 or canonical(payload)!=evidence.payload_json:
                raise FinancialInvariantError("APPROVED_EVIDENCE_CHANGED")
        validate_debt(db,tenant,{k:getattr(debt,k) for k in ("reference","reservation_id","licensed_entity_id","debtor_type","debtor_id","creditor_type","creditor_id","contract_reference","instrument_type","instrument_id","currency","principal","charge","due_date")},User)
        _,cc,pp,charge = instrument(db,tenant,debt.instrument_type,debt.instrument_id)
        if cc != debt.currency or pp != debt.principal or charge != debt.charge or source.status != "approved":
            raise FinancialInvariantError("DEBT_SOURCE_CHANGED")
        for row in rows:
            allocation_value(db,tenant,debt,{"kind":row.kind,"reference_id":row.reference_id,"category":row.category,"amount":row.amount,"currency":row.currency})
            model={"bank_payment":m.PaymentIntent,"wallet_capture":m.FinancialLedgerEntry,"cash_refund":m.RefundRecord,"supplier_settlement":m.SettlementRecord}[row.kind]
            live=tenant_row(db,model,tenant,row.reference_id)
            # Existing models have no authoritative captured/paid timestamp. Do not guess
            # whether a mutable payment straddled the opening cutoff.
            if cutoff is not None and row.kind in {"bank_payment","supplier_settlement","cash_refund"} and live.created_at.date()<=cutoff:
                raise FinancialInvariantError("MOVEMENT_EFFECTIVE_DATE_REQUIRED")
            if cutoff is None or live.created_at.date()>cutoff:
                totals[row.category] += row.amount
        for allocation in rows:
            if allocation.kind == "bank_payment":
                payment=tenant_row(db,m.PaymentIntent,tenant,allocation.reference_id)
                refunded=0
                for refund_allocation in rows:
                    if refund_allocation.kind == "cash_refund":
                        refund=tenant_row(db,m.RefundRecord,tenant,refund_allocation.reference_id)
                        if refund.payment_intent_id == payment.id:
                            refunded += refund_allocation.amount
                if refunded != minor(payment.refunded_amount):
                    raise FinancialInvariantError("UNALLOCATED_OR_DUPLICATE_REFUND")
    except FinancialInvariantError as exc:
        errors.append(str(exc))
    result = reconciliation(opening.amount if opening else None,new_charges,totals["payment"],totals["credit"],totals["refund"],totals["settlement"],observed)
    if errors:
        result.update(calculated_closing_balance=None,difference=None,reconciliation_status="SOURCE_CHANGED")
    result.update(id=debt.id,debtor={"type":debt.debtor_type,"id":debt.debtor_id},creditor={"type":debt.creditor_type,"id":debt.creditor_id},legal_entity=debt.licensed_entity_id,contract_reference=debt.contract_reference,reservation=debt.reservation_id,currency=debt.currency,principal=debt.principal,new_charges=new_charges,paid_amount=totals["payment"],paid_amount_scope="known_allocations_after_opening_cutoff",credits=totals["credit"],cash_refunds=totals["refund"],settlements=totals["settlement"],opening_balance=opening.amount if opening else None,due_date=debt.due_date,status="EVIDENCE_BOUND",outstanding_amount=result["calculated_closing_balance"],audit_source={"source_id":source.id,"sha256":source.sha256,"approved_by":source.approved_by,"opening_source_id":opening.source_id if opening else None,"allocations":[{"id":r.id,"kind":r.kind,"reference":r.reference_id,"source_id":r.source_id} for r in rows]},errors=errors,formula="opening + charges - payments - credit_notes + cash_refunds - settlements",closing_is_confirmed=False,observed_is_authoritative=False)
    return result

class CheckIn(BaseModel):
    command_id: str = Field(min_length=8,max_length=120)
    observed: int = Field(ge=0,strict=True)
    currency: str = Field(pattern="^[A-Z]{3}$")

class SourceIn(BaseModel):
    reference: str = Field(min_length=6,max_length=160)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")

def financial_integrity_router(get_db,current_user,role_has_permission,User):
    api = APIRouter(prefix="/ecosystem/financial-integrity",tags=["financial-integrity"])
    def access(user,write=False):
        if not role_has_permission(user.role,"reconciliation:manage" if write else "ledger:read"):
            raise HTTPException(403,"FINANCIAL_PERMISSION_REQUIRED")
    def run(db,fn):
        try: return fn()
        except (FinancialInvariantError,ValueError,KeyError,TypeError) as exc:
            db.rollback();raise HTTPException(409,str(exc))
        except Exception as exc:
            db.rollback()
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc, IntegrityError):
                raise HTTPException(409,"FINANCIAL_UNIQUENESS_OR_REFERENCE_CONFLICT")
            raise

    @api.get("/debts")
    def debts(user=Depends(current_user),db=Depends(get_db),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=100000)):
        access(user)
        batch=db.scalars(select(DebtBinding).where(DebtBinding.tenant_id==user.tenant_id).order_by(DebtBinding.id).offset(offset).limit(limit)).all()
        return {"items":[debt_view(db,user.tenant_id,x) for x in batch],"owner_inference":False,"opening_balance_default":None}

    @api.get("/debts/{debt_id}/reconciliation")
    def reconcile(debt_id:str,observed:int|None=Query(None,ge=0),user=Depends(current_user),db=Depends(get_db)):
        access(user)
        return run(db,lambda:debt_view(db,user.tenant_id,tenant_row(db,DebtBinding,user.tenant_id,debt_id),observed))

    @api.post("/debts/{debt_id}/reconciliation-checks")
    def check(debt_id:str,body:CheckIn,user=Depends(current_user),db=Depends(get_db)):
        access(user,True)
        def work():
            debt=tenant_row(db,DebtBinding,user.tenant_id,debt_id)
            if body.currency!=debt.currency: raise FinancialInvariantError("CURRENCY_MISMATCH")
            request_hash=digest({"debt_id":debt_id,**body.model_dump()})
            old=db.scalar(select(BalanceCheck).where(BalanceCheck.tenant_id==user.tenant_id,BalanceCheck.command_id==body.command_id))
            if old:
                if old.request_hash!=request_hash: raise FinancialInvariantError("IDEMPOTENCY_CONFLICT")
                return {"id":old.id,"snapshot":json.loads(old.snapshot_json)}
            snapshot=debt_view(db,user.tenant_id,debt,body.observed)
            row=BalanceCheck(tenant_id=user.tenant_id,debt_id=debt_id,command_id=body.command_id,request_hash=request_hash,actor_id=user.id,snapshot_json=canonical(snapshot))
            db.add(row);db.flush();db.commit()
            return {"id":row.id,"snapshot":snapshot}
        return run(db,work)

    @api.get("/debts/{debt_id}/reconciliation-checks")
    def checks(debt_id:str,user=Depends(current_user),db=Depends(get_db),limit:int=Query(50,ge=1,le=100)):
        access(user)
        return run(db,lambda: {"items":[{"id":x.id,"actor_id":x.actor_id,"created_at":x.created_at,"snapshot":json.loads(x.snapshot_json)} for x in db.scalars(select(BalanceCheck).where(BalanceCheck.tenant_id==user.tenant_id,BalanceCheck.debt_id==tenant_row(db,DebtBinding,user.tenant_id,debt_id).id).order_by(BalanceCheck.created_at.desc()).limit(limit)).all()]})

    @api.post("/sources")
    def stage(body:SourceIn,user=Depends(current_user),db=Depends(get_db)):
        access(user,True)
        def work():
            data,sha=read_source(body.reference)
            if sha!=body.sha256 or data["tenant_id"]!=user.tenant_id: raise FinancialInvariantError("SOURCE_HASH_OR_TENANT_MISMATCH")
            source=db.scalar(select(EvidenceSource).where(EvidenceSource.tenant_id==user.tenant_id,EvidenceSource.reference==body.reference))
            if source:
                if source.sha256!=sha: raise FinancialInvariantError("SOURCE_IDEMPOTENCY_CONFLICT")
            else:
                source=EvidenceSource(tenant_id=user.tenant_id,reference=body.reference,sha256=sha,payload_json=canonical(data),submitted_by=user.id,status="pending");db.add(source);db.flush()
            db.commit();return {"id":source.id,"status":source.status,"sha256":sha}
        return run(db,work)

    @api.post("/sources/{source_id}/approve")
    def approve(source_id:str,user=Depends(current_user),db=Depends(get_db)):
        access(user,True)
        def work():
            source=db.scalar(select(EvidenceSource).where(EvidenceSource.tenant_id==user.tenant_id,EvidenceSource.id==source_id).with_for_update())
            if source is None: raise FinancialInvariantError("SOURCE_REFERENCE_NOT_IN_TENANT")
            if source.submitted_by==user.id: raise FinancialInvariantError("MAKER_CHECKER_REQUIRED")
            data,sha=read_source(source.reference)
            if sha!=source.sha256 or canonical(data)!=source.payload_json: raise FinancialInvariantError("SOURCE_CHANGED")
            if source.status=="pending":
                source.status="approved";source.approved_by=user.id
            db.commit();return {"id":source.id,"status":source.status,"approved_by":source.approved_by}
        return run(db,work)

    @api.post("/sources/{source_id}/import")
    def execute(source_id:str,user=Depends(current_user),db=Depends(get_db)):
        access(user,True)
        def work():
            source=tenant_row(db,EvidenceSource,user.tenant_id,source_id)
            result=import_source(db,user.tenant_id,source,User);db.commit();return result
        return run(db,work)
    return api
