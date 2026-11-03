"""Organization receivables (سازمان‌ها و مطالبات).

What an organization owes is built only from real records:
- invoiced: invoices of reservations linked to the organization's approved requests (same basis as the
  organization statement), excluding cancelled/void invoices;
- settled: payments received from the organization, recorded here by finance (each also posted to the
  treasury book as a receivable credit for that organization).
Settlements are allocated to the oldest invoices first (FIFO). Each invoice is due `payment_terms_days`
after it was issued; ageing buckets are computed from that due date. Terms are mandatory per organization:
an organization without terms is listed as "terms missing" instead of using an invented default.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import enterprise_models as e
from . import operations as m
from .database import Base
from .operations import OperationalMixin

BUCKETS = (("not_due", "سررسید نشده"), ("d1_30", "۱ تا ۳۰ روز"), ("d31_60", "۳۱ تا ۶۰ روز"), ("d61_90", "۶۱ تا ۹۰ روز"), ("d90_plus", "بیش از ۹۰ روز"))
CLOSED_INVOICE = ("cancelled", "void", "voided", "refunded")


class OrgReceivableTerms(OperationalMixin, Base):
    __tablename__ = "org_receivable_terms"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer)
    contact_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    contact_mobile: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "organization_id", name="uq_org_terms_org"),)


class OrgSettlement(OperationalMixin, Base):
    __tablename__ = "org_settlements"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    paid_on: Mapped[str] = mapped_column(String(10))
    method: Mapped[str] = mapped_column(String(16))  # bank | cheque | cash | offset
    reference: Mapped[str] = mapped_column(String(80))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treasury_entry_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    registered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "organization_id", "reference", name="uq_org_settlement_ref"),)


class TermsIn(BaseModel):
    payment_terms_days: int = Field(ge=0, le=365)
    contact_name: Optional[str] = Field(default=None, max_length=120)
    contact_mobile: Optional[str] = Field(default=None, max_length=16)
    note: Optional[str] = Field(default=None, max_length=1000)


class SettlementIn(BaseModel):
    amount: int = Field(gt=0, le=10**15)
    currency: str = Field(default="IRR", pattern="^[A-Z]{3}$")
    paid_on: str
    method: str = Field(pattern="^(bank|cheque|cash|offset)$")
    reference: str = Field(min_length=2, max_length=80)
    note: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("paid_on")
    @classmethod
    def _d(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("تاریخ با قالب YYYY-MM-DD لازم است")
        date.fromisoformat(v)
        return v


def _invoices(db: Session, tenant_id: int, org_id: Optional[str] = None):
    s = (select(m.Invoice, m.Reservation.booking_reference, e.EnterpriseRequest.organization_id)
         .join(m.Reservation, m.Reservation.id == m.Invoice.reservation_id)
         .join(e.EnterpriseBookingLink, e.EnterpriseBookingLink.reservation_id == m.Reservation.id)
         .join(e.EnterpriseRequest, e.EnterpriseRequest.id == e.EnterpriseBookingLink.request_id)
         .where(m.Invoice.tenant_id == tenant_id, m.Reservation.tenant_id == tenant_id, e.EnterpriseBookingLink.tenant_id == tenant_id,
                e.EnterpriseRequest.tenant_id == tenant_id, m.Invoice.status.not_in(CLOSED_INVOICE)))
    if org_id:
        s = s.where(e.EnterpriseRequest.organization_id == org_id)
    return db.execute(s.order_by(m.Invoice.issued_at, m.Invoice.id)).all()


def _aware(d: Optional[datetime]) -> Optional[datetime]:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def age_invoices(invoices: list[dict], settled: int, today: date, terms_days: Optional[int]) -> tuple[list[dict], dict[str, int]]:
    """FIFO allocation of `settled` to invoices (oldest first) and ageing of the remainder by due date."""
    buckets = {k: 0 for k, _ in BUCKETS}
    left = settled
    out = []
    for inv in sorted(invoices, key=lambda x: (x["issued_on"], x["invoice_number"])):
        paid = min(left, inv["total"])
        left -= paid
        open_amount = inv["total"] - paid
        due = (date.fromisoformat(inv["issued_on"]) + timedelta(days=terms_days)) if terms_days is not None else None
        late = (today - due).days if due else None
        if open_amount > 0 and due is not None:
            key = "not_due" if late <= 0 else "d1_30" if late <= 30 else "d31_60" if late <= 60 else "d61_90" if late <= 90 else "d90_plus"
            buckets[key] += open_amount
        out.append({**inv, "paid": paid, "open": open_amount, "due_on": due.isoformat() if due else None,
                    "days_overdue": max(0, late) if (late is not None and open_amount > 0) else 0})
    return out, buckets


def receivables_router(get_db, current_user, role_has_permission, User, audit=None):
    api = APIRouter(tags=["receivables"])

    def finance_read(user=Depends(current_user)):
        if not (role_has_permission(user.role, "ledger:read") or role_has_permission(user.role, "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مالی لازم است")
        return user

    def finance_write(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("reconciliation:manage", "tenant:manage", "platform:manage")):
            raise HTTPException(status_code=403, detail="مجوز ثبت مالی لازم است")
        return user

    def _org(db: Session, tenant_id: int, org_id: str) -> m.Organization:
        org = db.scalar(select(m.Organization).where(m.Organization.id == org_id, m.Organization.tenant_id == tenant_id))
        if org is None:
            raise HTTPException(status_code=404, detail="سازمان یافت نشد")
        return org

    def _summary(db: Session, tenant_id: int, org: m.Organization, today: date, with_items: bool = False) -> dict:
        terms = db.scalar(select(OrgReceivableTerms).where(OrgReceivableTerms.tenant_id == tenant_id, OrgReceivableTerms.organization_id == org.id))
        invs = [{"invoice_number": inv.invoice_number, "booking_reference": ref, "total": int(inv.total_amount), "currency": inv.currency,
                 "issued_on": (_aware(inv.issued_at) or datetime.now(timezone.utc)).date().isoformat(), "status": inv.status}
                for inv, ref, _ in _invoices(db, tenant_id, org.id)]
        invs_irr = [i for i in invs if i["currency"] == "IRR"]
        settled = int(db.scalar(select(func.coalesce(func.sum(OrgSettlement.amount), 0)).where(
            OrgSettlement.tenant_id == tenant_id, OrgSettlement.organization_id == org.id, OrgSettlement.currency == "IRR")) or 0)
        items, buckets = age_invoices(invs_irr, settled, today, terms.payment_terms_days if terms else None)
        invoiced = sum(i["total"] for i in invs_irr)
        credit = []
        for acc in db.scalars(select(m.CreditAccount).where(m.CreditAccount.tenant_id == tenant_id, m.CreditAccount.organization_id == org.id)).all():
            credit.append({"id": acc.id, "currency": acc.currency, **m.credit_balances(db, tenant_id=tenant_id, credit_account_id=acc.id)})
        out = {"organization_id": org.id, "name": org.name, "status": org.status, "terms_days": terms.payment_terms_days if terms else None,
               "terms_missing": terms is None, "contact_name": terms.contact_name if terms else None, "contact_mobile": terms.contact_mobile if terms else None,
               "invoiced": invoiced, "settled": settled, "outstanding": invoiced - settled, "overdue": sum(v for k, v in buckets.items() if k != "not_due"),
               "buckets": buckets, "invoices": len(invs_irr), "other_currency_invoices": len(invs) - len(invs_irr), "credit": credit,
               "oldest_overdue_days": max((i["days_overdue"] for i in items), default=0)}
        if with_items:
            out["items"] = items
            out["settlements"] = [{"id": s.id, "amount": s.amount, "currency": s.currency, "paid_on": s.paid_on, "method": s.method, "reference": s.reference,
                                   "note": s.note, "posted": s.treasury_entry_id is not None}
                                  for s in db.scalars(select(OrgSettlement).where(OrgSettlement.tenant_id == tenant_id, OrgSettlement.organization_id == org.id)
                                                      .order_by(OrgSettlement.paid_on.desc(), OrgSettlement.created_at.desc())).all()]
        return out

    @api.get("/receivables/organizations")
    def list_orgs(as_of: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"), user=Depends(finance_read), db: Session = Depends(get_db)):
        today = date.fromisoformat(as_of) if as_of else datetime.now(timezone.utc).date()
        rows = [_summary(db, user.tenant_id, o, today) for o in db.scalars(select(m.Organization).where(m.Organization.tenant_id == user.tenant_id).order_by(m.Organization.name)).all()]
        rows.sort(key=lambda r: (-r["overdue"], -r["outstanding"]))
        totals = {k: sum(r["buckets"][k] for r in rows) for k, _ in BUCKETS}
        return {"as_of": today.isoformat(), "buckets": [{"key": k, "label": l} for k, l in BUCKETS], "totals": totals,
                "outstanding": sum(r["outstanding"] for r in rows), "terms_missing": sum(1 for r in rows if r["terms_missing"]), "items": rows}

    @api.get("/receivables/organizations/{org_id}")
    def org_detail(org_id: str, as_of: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"), user=Depends(finance_read), db: Session = Depends(get_db)):
        today = date.fromisoformat(as_of) if as_of else datetime.now(timezone.utc).date()
        return _summary(db, user.tenant_id, _org(db, user.tenant_id, org_id), today, with_items=True)

    @api.put("/receivables/organizations/{org_id}/terms")
    def put_terms(org_id: str, data: TermsIn, user=Depends(finance_write), db: Session = Depends(get_db)):
        _org(db, user.tenant_id, org_id)
        row = db.scalar(select(OrgReceivableTerms).where(OrgReceivableTerms.tenant_id == user.tenant_id, OrgReceivableTerms.organization_id == org_id))
        if row is None:
            row = OrgReceivableTerms(tenant_id=user.tenant_id, organization_id=org_id, payment_terms_days=data.payment_terms_days)
            db.add(row)
        row.payment_terms_days, row.contact_name, row.contact_mobile, row.note = data.payment_terms_days, data.contact_name, data.contact_mobile, data.note
        if audit:
            audit(db, user, "receivables.terms.saved", "organization", {"organization_id": org_id, "payment_terms_days": data.payment_terms_days})
        db.commit()
        return {"organization_id": org_id, "payment_terms_days": row.payment_terms_days}

    @api.post("/receivables/organizations/{org_id}/settlements", status_code=201)
    def add_settlement(org_id: str, data: SettlementIn, user=Depends(finance_write), db: Session = Depends(get_db)):
        org = _org(db, user.tenant_id, org_id)
        if db.scalar(select(OrgSettlement.id).where(OrgSettlement.tenant_id == user.tenant_id, OrgSettlement.organization_id == org_id, OrgSettlement.reference == data.reference.strip())):
            raise HTTPException(status_code=409, detail="این شماره‌ی پیگیری قبلاً برای همین سازمان ثبت شده است")
        if date.fromisoformat(data.paid_on) > datetime.now(timezone.utc).date() + timedelta(days=1):
            raise HTTPException(status_code=422, detail="تاریخ پرداخت در آینده است")
        row = OrgSettlement(tenant_id=user.tenant_id, organization_id=org_id, amount=data.amount, currency=data.currency, paid_on=data.paid_on,
                            method=data.method, reference=data.reference.strip(), note=data.note, registered_by=user.id)
        db.add(row)
        db.flush()
        from .commerce import post_treasury
        entry = post_treasury(db, tenant_id=user.tenant_id, command_id=f"org-settlement:{row.id}", counterparty_type="organization", counterparty_ref=org_id,
                              counterparty_name=org.name, account_type="receivable", operation="settlement", credit=data.amount, currency=data.currency,
                              registered_by=user.id, tracking_no=row.reference, operation_date=data.paid_on,
                              description=f"وصول مطالبات سازمان {org.name} ({ {'bank': 'بانک', 'cheque': 'چک', 'cash': 'نقد', 'offset': 'تهاتر'}[data.method] })")
        row.treasury_entry_id = entry.id
        if audit:
            audit(db, user, "receivables.settlement.recorded", "organization", {"organization_id": org_id, "amount": data.amount, "reference": row.reference})
        db.commit()
        return {"id": row.id, "treasury_entry_id": entry.id, "amount": row.amount}

    return api
