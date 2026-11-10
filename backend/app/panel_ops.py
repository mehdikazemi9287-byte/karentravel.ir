"""Panels Phase 1 (rest): capabilities, the role-aware «امروز» worklist, configurable SLA and dated tax rates (admin),
failed payments, change-price proposals, saved passengers of an organization/agency, gateway settlement file import and
bank payout batch files. Spec: docs/product/panels/04-panel-spec.md §1.2, §1.4, §2.9, §2.10; decisions in
docs/product/panels/07-phase1-rest-security.md.

Rules kept here
* Nothing is invented: every count and amount comes from an existing row. A source that has no data says so.
* Money is integer rial. A change of price is a *proposal*: ops proposes, a finance user or the tenant manager approves
  it through maker-checker (`approvals.py`, kind `reservation.price_change`), then the customer must accept it. No step
  charges, refunds or edits the paid amount; the accepted difference is recorded for finance to collect or refund.
* Settlement import parses a CSV the finance user uploads and matches it to payments; it never calls a gateway and
  never changes a payment's status. Bank payout batches only produce a file after a second finance user approves; no
  bank is called and no refund is marked paid by the batch.
* Lists of passengers never carry a full national code or passport number (masked to the last 4 digits).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import after_sales as asl
from . import approvals
from . import operations as m
from . import traveller_identity as ti
from .database import Base
from .operations import OperationalMixin

PHASE1_REST_TABLES = ("ops_sla_policies", "tax_rate_periods", "price_change_proposals", "scoped_travellers",
                      "settlement_imports", "settlement_import_lines", "bank_payout_batches", "bank_payout_items")
APPEND_ONLY = ("settlement_import_lines", "bank_payout_items")

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
ORG_MANAGER_ROLES = ("manager", "welfare_manager", "organization_admin")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aw(dt: Optional[datetime]) -> Optional[datetime]:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def _iso(v) -> Optional[str]:
    if v is None:
        return None
    return _aw(v).isoformat() if isinstance(v, datetime) else v.isoformat()


def latin(value: Optional[str]) -> str:
    return (value or "").translate(_DIGITS).strip()


# ============================================================================ models
class PriceChangeProposal(OperationalMixin, Base):
    """Ops proposal to change a reservation's price. pending_approval -> awaiting_customer -> accepted | declined;
    rejected (by the checker) or withdrawn. The reservation itself is never edited here."""
    __tablename__ = "price_change_proposals"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    customer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    proposed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    current_total: Mapped[int] = mapped_column(Integer)
    proposed_total: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="pending_approval", index=True)
    approval_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    customer_decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_price_change_command"),)


class ScopedTraveller(OperationalMixin, Base):
    """A saved passenger that belongs to an organization or an agency (not to one user's own list)."""
    __tablename__ = "scoped_travellers"
    scope_type: Mapped[str] = mapped_column(String(16))  # organization | agency
    scope_id: Mapped[str] = mapped_column(String(36), index=True)
    traveller_id: Mapped[str] = mapped_column(ForeignKey("travellers.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("tenant_id", "scope_type", "scope_id", "traveller_id", name="uq_scoped_traveller"),)


class SettlementImport(OperationalMixin, Base):
    """One uploaded gateway settlement file. The same file (same SHA-256) is imported once."""
    __tablename__ = "settlement_imports"
    provider: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(160))
    file_sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    unmatched_count: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("tenant_id", "file_sha256", name="uq_settlement_import_file"),)


class SettlementImportLine(OperationalMixin, Base):
    __tablename__ = "settlement_import_lines"
    import_id: Mapped[str] = mapped_column(ForeignKey("settlement_imports.id"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(160), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    settled_on: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    match_status: Mapped[str] = mapped_column(String(20), index=True)  # matched | amount_mismatch | not_captured | unmatched | duplicate
    payment_intent_id: Mapped[Optional[str]] = mapped_column(ForeignKey("payment_intents.id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)


class BankPayoutBatch(OperationalMixin, Base):
    """A batch bank transfer file for approved bank-transfer refunds. draft is never stored: created = pending_approval;
    approved (file generated) | rejected. The file is produced only after a second finance user approves."""
    __tablename__ = "bank_payout_batches"
    status: Mapped[str] = mapped_column(String(20), default="pending_approval", index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approval_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    file_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    command_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_bank_batch_command"),)


class BankPayoutItem(OperationalMixin, Base):
    __tablename__ = "bank_payout_items"
    batch_id: Mapped[str] = mapped_column(ForeignKey("bank_payout_batches.id"), index=True)
    refund_id: Mapped[str] = mapped_column(ForeignKey("refund_records.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    holder_name: Mapped[str] = mapped_column(String(160))
    sheba_masked: Mapped[str] = mapped_column(String(40))


# ============================================================================ pure helpers (tested directly)
def parse_settlement_csv(text: str, max_rows: int = 5000) -> tuple[list[dict], list[dict]]:
    """CSV with a header row containing `reference` and `amount` (rial, integer); optional `settled_on`. Persian
    digits and thousands separators are accepted. Returns (rows, errors); a file with any error is not imported."""
    text = (text or "").lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    if "reference" not in headers or "amount" not in headers:
        return [], [{"line": 1, "column": "header", "message": "سطر اول باید ستون‌های reference و amount را داشته باشد"}]
    rows, errors = [], []
    for i, raw in enumerate(reader, start=2):
        rec = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
        if not any(str(v).strip() for v in rec.values()):
            continue
        if len(rows) >= max_rows:
            errors.append({"line": i, "column": "-", "message": f"حداکثر {max_rows} ردیف در هر فایل"})
            break
        ref = latin(rec.get("reference"))
        amount_txt = re.sub(r"[,\s٬،]", "", latin(rec.get("amount")))
        if not ref or len(ref) > 160:
            errors.append({"line": i, "column": "reference", "message": "شناسهٔ تراکنش خالی یا بیش از حد بلند است"})
            continue
        if not re.fullmatch(r"\d{1,13}", amount_txt) or int(amount_txt) <= 0:
            errors.append({"line": i, "column": "amount", "message": "مبلغ باید عدد صحیح مثبت به ریال باشد"})
            continue
        rows.append({"line": i, "reference": ref, "amount": int(amount_txt), "settled_on": latin(rec.get("settled_on"))[:32] or None})
    if not rows and not errors:
        errors.append({"line": 2, "column": "-", "message": "فایل هیچ ردیفی ندارد"})
    return rows, errors


def bank_file_csv(batch_id: str, items: list[dict]) -> str:
    """Generic bank batch CSV (row, IBAN, holder, amount in rial, payment id). The exact layout of a bank's own format
    (e.g. a PAYA group file) is a later adapter; nothing here is sent to a bank."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["row", "sheba", "holder_name", "amount_irr", "payment_id", "description"])
    for n, it in enumerate(items, start=1):
        w.writerow([n, it["sheba"], it["holder_name"], it["amount"], it["refund_id"], f"refund {batch_id[:8]}"])
    return out.getvalue()


# ============================================================================ inputs
class SlaIn(BaseModel):
    request_type: str = Field(pattern="^(cancel|change|refund)$")
    status: str = Field(min_length=3, max_length=32)
    minutes: int = Field(ge=asl.SLA_MINUTES_RANGE[0], le=asl.SLA_MINUTES_RANGE[1])
    reason: str = Field(min_length=5, max_length=300)


class SlaResetIn(BaseModel):
    request_type: str = Field(pattern="^(cancel|change|refund)$")
    status: str = Field(min_length=3, max_length=32)
    reason: str = Field(min_length=5, max_length=300)


class TaxRateIn(BaseModel):
    tax_type: str = Field(default="VAT", pattern="^VAT$")
    code: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9\-_.]+$")
    rate_bps: int = Field(ge=0, le=5000)
    effective_from: date
    effective_to: Optional[date] = None
    legal_reference: str = Field(min_length=5, max_length=300)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class PriceChangeIn(BaseModel):
    reservation_id: str = Field(min_length=36, max_length=36)
    proposed_total: int = Field(gt=0, le=10**12)
    reason: str = Field(min_length=10, max_length=500)


class CustomerDecisionIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=300)


class PassengerIn(ti.IdentityFields):
    full_name: str = Field(min_length=3, max_length=160)


class SettlementIn(BaseModel):
    provider: str = Field(default="zarinpal", pattern="^[a-z0-9_]{2,40}$")
    filename: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=10, max_length=2_000_000)
    dry_run: bool = False


class BankBatchIn(BaseModel):
    refund_ids: list[str] = Field(min_length=1, max_length=500)
    note: Optional[str] = Field(default=None, max_length=300)


# ============================================================================ router
def panel_ops_router(get_db, current_user, role_has_permission, User, audit: Callable, role_permissions: dict) -> APIRouter:
    api = APIRouter(tags=["panels-phase1-rest"])

    def has(user, *perms: str) -> bool:
        return any(role_has_permission(user.role, p) for p in perms)

    def need(*perms: str, not_roles: tuple = ()):
        def guard(user=Depends(current_user)):
            if user.role in not_roles or not has(user, *perms):
                raise HTTPException(403, "مجوز لازم برای این بخش وجود ندارد")
            return user
        return guard

    tenant_admin = need("tenant:manage")
    finance_read = need("ledger:read", "reconciliation:manage", "tenant:manage")
    recon_user = need("reconciliation:manage")
    refund_user = need("refund:manage")
    ops_user = need("service_request:decide")
    sla_reader = need("service_request:decide", "tenant:manage")

    def _names(db: Session, ids) -> dict:
        ids = {i for i in ids if i}
        return {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}

    # ------------------------------------------------------------------ /me/capabilities (§1.2)
    all_perms = sorted({p for perms in role_permissions.values() for p in perms} - {"platform:manage"})

    @api.get("/me/capabilities")
    def capabilities(user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        """What the signed-in user may do, from the same RBAC table (`security.ROLE_PERMISSIONS`) the API enforces,
        plus the user's organization / agency / supplier memberships. A usability answer; every endpoint still checks."""
        own = sorted(role_permissions.get(user.role, frozenset()))
        effective = all_perms + ["platform:manage"] if "platform:manage" in own else own
        orgs = db.execute(select(m.Organization.id, m.Organization.name).join(m.EmployeeAssignment, m.EmployeeAssignment.organization_id == m.Organization.id)
                          .where(m.EmployeeAssignment.tenant_id == user.tenant_id, m.EmployeeAssignment.user_id == user.id, m.Organization.tenant_id == user.tenant_id)).all()
        agencies = db.execute(select(m.Agency.id, m.Agency.display_name, m.AgencyMembership.agency_role).join(m.AgencyMembership, m.AgencyMembership.agency_id == m.Agency.id)
                              .where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.user_id == user.id, m.Agency.tenant_id == user.tenant_id)).all()
        suppliers = db.execute(select(m.Supplier.id, m.Supplier.display_name, m.SupplierMembership.role).join(m.SupplierMembership, m.SupplierMembership.supplier_id == m.Supplier.id)
                               .where(m.SupplierMembership.tenant_id == user.tenant_id, m.SupplierMembership.user_id == user.id, m.Supplier.tenant_id == user.tenant_id)).all()
        from .charter_blocks import domestic_charter_sale_enabled
        from .main import Tenant
        tenant = db.get(Tenant, user.tenant_id)
        return {"user_id": user.id, "role": user.role, "permissions": effective,
                "memberships": {"organizations": [{"id": i, "name": n} for i, n in orgs],
                                "agencies": [{"id": i, "name": n, "role": r or "owner"} for i, n, r in agencies],
                                "suppliers": [{"id": i, "name": n, "role": r} for i, n, r in suppliers]},
                "feature_flags": {"charter_domestic_sale": domestic_charter_sale_enabled()},
                "tenant": {"slug": tenant.slug if tenant else None, "name": tenant.name if tenant else None},
                "source": "security.ROLE_PERMISSIONS", "cache_seconds": 60}

    # ------------------------------------------------------------------ /panel/today (§1.4)
    def _item(key: str, level: str, count: int, label: str, href: str, oldest: Optional[datetime] = None, due: Optional[datetime] = None) -> dict:
        return {"key": key, "level": level, "count": int(count), "label": label, "href": href, "oldest_at": _iso(oldest), "sla_due_at": _iso(due)}

    @api.get("/panel/today")
    def today(user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        """Role-aware worklist: only counters taken from existing rows, only for queues the viewer may work on."""
        t, now, items = user.tenant_id, utcnow(), []
        if has(user, "service_request:decide"):
            overrides = asl.sla_overrides(db, t)
            reqs = db.scalars(select(m.BookingServiceRequest).where(m.BookingServiceRequest.tenant_id == t, m.BookingServiceRequest.status.in_(asl.OPEN_STATUSES))).all()
            handling = {h.request_id: h for h in db.scalars(select(asl.ServiceRequestHandling).where(asl.ServiceRequestHandling.tenant_id == t,
                                                                                                     asl.ServiceRequestHandling.request_id.in_([r.id for r in reqs]))).all()} if reqs else {}
            ops_side = [r for r in reqs if r.status in ("submitted", "under_review", "waiting_supplier", "refund_paid")]
            overdue, mine, earliest_due = [], 0, None
            for r in ops_side:
                h = handling.get(r.id)
                nxt = asl.next_step(r.status, h.status_since if h else r.updated_at, now, overrides.get((r.request_type, r.status)))
                if h and h.assigned_to_user_id == user.id:
                    mine += 1
                if nxt and nxt["eta"]:
                    due = datetime.fromisoformat(nxt["eta"])
                    if nxt["overdue"]:
                        overdue.append(due)
                    elif earliest_due is None or due < earliest_due:
                        earliest_due = due
            if overdue:
                items.append(_item("ops.sla_breached", "bad", len(overdue), "درخواست با SLA گذشته", "/backoffice/queues/service_requests", due=min(overdue)))
            if ops_side:
                items.append(_item("ops.open_requests", "warn", len(ops_side), "درخواست باز در صف عملیات", "/backoffice/queues/service_requests",
                                   oldest=min(_aw(r.created_at) for r in ops_side), due=earliest_due))
            if mine:
                items.append(_item("ops.assigned_to_me", "info", mine, "درخواست تخصیص‌یافته به شما", "/backoffice/queues/service_requests"))
            pc = db.scalar(select(func.count()).select_from(PriceChangeProposal).where(PriceChangeProposal.tenant_id == t, PriceChangeProposal.status == "awaiting_customer")) or 0
            if pc:
                items.append(_item("ops.price_change_waiting_customer", "info", pc, "پیشنهاد تغییر قیمت منتظر پاسخ مشتری", "/backoffice/price-changes"))
        if has(user, "refund:manage"):
            rows = db.execute(select(m.RefundRecord.status, asl.RefundExecution.prepared_by_user_id, m.RefundRecord.created_at).join(
                asl.RefundExecution, (asl.RefundExecution.refund_id == m.RefundRecord.id) & (asl.RefundExecution.tenant_id == t)).where(
                m.RefundRecord.tenant_id == t, m.RefundRecord.status.in_(asl.REFUND_OPEN))).all()
            to_prepare = [c for s, _, c in rows if s == "pending_finance"]
            to_approve = [c for s, p, c in rows if s == "awaiting_approval" and p != user.id]
            if to_approve:
                items.append(_item("finance.refunds_second_approval", "warn", len(to_approve), "استرداد منتظر تأیید نفر دوم", "/finance/refunds", oldest=min(_aw(c) for c in to_approve)))
            if to_prepare:
                items.append(_item("finance.refunds_to_prepare", "warn", len(to_prepare), "استرداد منتظر آماده‌سازی پرداخت", "/finance/refunds", oldest=min(_aw(c) for c in to_prepare)))
        if has(user, "reconciliation:manage", "ledger:read"):
            since = now - timedelta(days=7)
            failed = db.scalar(select(func.count()).select_from(m.PaymentIntent).where(m.PaymentIntent.tenant_id == t, m.PaymentIntent.status == "failed", m.PaymentIntent.updated_at >= since)) or 0
            if failed:
                items.append(_item("finance.failed_payments_7d", "info", failed, "پرداخت ناموفق در ۷ روز اخیر", "/finance/failed-payments"))
        if has(user, "reconciliation:manage"):
            open_recon = db.scalar(select(func.count()).select_from(m.ReconciliationRecord).where(m.ReconciliationRecord.tenant_id == t, m.ReconciliationRecord.status.in_(("UNMATCHED", "DISPUTED")))) or 0
            if open_recon:
                items.append(_item("finance.reconciliation_open", "warn", open_recon, "مغایرت باز تطبیق درگاه", "/finance/reconciliation"))
        pending = [r for r in approvals.list_requests(db, user=user, status="pending", audit=audit) if r.get("can_decide")]
        if pending:
            items.append(_item("approvals.pending_for_me", "warn", len(pending), "درخواست منتظر تأیید شما (دو نفره)", "/finance/approvals",
                               oldest=min(datetime.fromisoformat(r["created_at"]) for r in pending if r.get("created_at")) if any(r.get("created_at") for r in pending) else None))
        if has(user, "license:verify"):
            from .agency_b2b import AgencyProfile
            k = db.scalar(select(func.count()).select_from(AgencyProfile).where(AgencyProfile.tenant_id == t, AgencyProfile.kyc_status == "submitted")) or 0
            if k:
                items.append(_item("ops.agency_kyc", "warn", k, "آژانس منتظر احراز", "/backoffice/agencies"))
        if has(user, "inventory:publish"):
            from .charter_blocks import CharterBlock
            c = db.scalar(select(func.count()).select_from(CharterBlock).where(CharterBlock.tenant_id == t, CharterBlock.status == "submitted")) or 0
            if c:
                items.append(_item("ops.charter_review", "warn", c, "بلوک چارتر منتظر بازبینی", "/backoffice/charter-blocks"))
        # every signed-in user: what waits for *them* as a customer
        needs_reply = db.scalar(select(func.count()).select_from(m.BookingServiceRequest).join(m.Reservation, m.Reservation.id == m.BookingServiceRequest.reservation_id).where(
            m.BookingServiceRequest.tenant_id == t, m.Reservation.tenant_id == t, m.Reservation.user_id == user.id, m.BookingServiceRequest.status == "needs_customer")) or 0
        if needs_reply:
            items.append(_item("me.service_request_reply", "warn", needs_reply, "درخواست منتظر پاسخ شما", "/account/refunds"))
        price_offers = db.scalar(select(func.count()).select_from(PriceChangeProposal).where(PriceChangeProposal.tenant_id == t, PriceChangeProposal.customer_user_id == user.id,
                                                                                           PriceChangeProposal.status == "awaiting_customer")) or 0
        if price_offers:
            items.append(_item("me.price_change", "warn", price_offers, "تغییر قیمت منتظر تأیید شما", "/account/price-changes"))
        order = {"bad": 0, "warn": 1, "info": 2}
        items.sort(key=lambda i: (order[i["level"]], -(i["count"])))
        db.commit()
        return {"items": items, "approvals": pending[:20], "generated_at": now.isoformat(), "role": user.role}

    # ------------------------------------------------------------------ configurable SLA
    def _sla_table(db: Session, tenant_id: int) -> list[dict]:
        rows = {(r.request_type, r.status): r for r in db.scalars(select(asl.OpsSlaPolicy).where(asl.OpsSlaPolicy.tenant_id == tenant_id)).all()}
        names = _names(db, [r.updated_by_user_id for r in rows.values()])
        out = []
        for rt in asl.SLA_REQUEST_TYPES:
            for st in asl.SLA_STATUSES:
                title, owner, hours = asl.NEXT_STEP[st]
                r = rows.get((rt, st))
                out.append({"request_type": rt, "request_type_fa": asl.TYPE_FA[rt], "status": st, "status_fa": asl.STATUS_FA.get(st, st), "step": title, "owner": owner,
                            "default_minutes": hours * 60, "minutes": r.minutes if r else hours * 60, "source": "tenant" if r else "default",
                            "reason": r.reason if r else None, "updated_by": names.get(r.updated_by_user_id) if r else None, "updated_at": _iso(r.updated_at) if r else None})
        return out

    @api.get("/ops/sla-policies")
    def sla_list(user=Depends(sla_reader), db: Session = Depends(get_db)) -> dict:
        return {"items": _sla_table(db, user.tenant_id), "range_minutes": list(asl.SLA_MINUTES_RANGE)}

    @api.put("/admin/sla-policies")
    def sla_set(data: SlaIn, user=Depends(tenant_admin), db: Session = Depends(get_db)) -> dict:
        if data.status not in asl.SLA_STATUSES:
            raise HTTPException(422, "برای این وضعیت SLA تعریف نمی‌شود (ساعت آن متوقف است یا وضعیت پایانی است)")
        row = db.scalar(select(asl.OpsSlaPolicy).where(asl.OpsSlaPolicy.tenant_id == user.tenant_id, asl.OpsSlaPolicy.request_type == data.request_type,
                                                       asl.OpsSlaPolicy.status == data.status).with_for_update())
        before = row.minutes if row else asl.NEXT_STEP[data.status][2] * 60
        if row is None:
            row = asl.OpsSlaPolicy(tenant_id=user.tenant_id, request_type=data.request_type, status=data.status, minutes=data.minutes, reason=data.reason, updated_by_user_id=user.id)
            db.add(row)
        else:
            row.minutes, row.reason, row.updated_by_user_id = data.minutes, data.reason, user.id
        audit(db, user, "ops.sla.updated", "ops_sla_policy", {"request_type": data.request_type, "status": data.status, "before_minutes": before, "after_minutes": data.minutes, "reason": data.reason})
        db.commit()
        return {"items": _sla_table(db, user.tenant_id)}

    @api.post("/admin/sla-policies/reset")
    def sla_reset(data: SlaResetIn, user=Depends(tenant_admin), db: Session = Depends(get_db)) -> dict:
        row = db.scalar(select(asl.OpsSlaPolicy).where(asl.OpsSlaPolicy.tenant_id == user.tenant_id, asl.OpsSlaPolicy.request_type == data.request_type, asl.OpsSlaPolicy.status == data.status))
        if row is None:
            raise HTTPException(404, "برای این مورد مقدار اختصاصی ثبت نشده است")
        audit(db, user, "ops.sla.reset", "ops_sla_policy", {"request_type": data.request_type, "status": data.status, "before_minutes": row.minutes, "reason": data.reason})
        db.delete(row)
        db.commit()
        return {"items": _sla_table(db, user.tenant_id)}

    # ------------------------------------------------------------------ dated tax rates (FIN-11)
    from .agency_b2b import VAT_RATE_SCHEDULE, TaxRatePeriod, vat_rate_on

    def _tax_out(db: Session, tenant_id: int) -> dict:
        rows = db.scalars(select(TaxRatePeriod).where(TaxRatePeriod.tenant_id == tenant_id).order_by(TaxRatePeriod.effective_from, TaxRatePeriod.created_at)).all()
        names = _names(db, [r.created_by_user_id for r in rows] + [r.retired_by_user_id for r in rows])
        active = [r for r in rows if r.status == "active"]
        try:
            today_rate = vat_rate_on(utcnow().date(), db, tenant_id)
            current = {"id": today_rate.id, "rate_bps": today_rate.rate_bps, "legal_reference": today_rate.legal_reference}
        except LookupError:
            current = None
        return {"source": "table" if active else "code_default", "current": current,
                "items": [{"id": r.id, "tax_type": r.tax_type, "code": r.code, "rate_bps": r.rate_bps, "effective_from": _iso(r.effective_from), "effective_to": _iso(r.effective_to),
                           "legal_reference": r.legal_reference, "status": r.status, "created_by": names.get(r.created_by_user_id), "created_at": _iso(r.created_at),
                           "retired_by": names.get(r.retired_by_user_id), "retire_reason": r.retire_reason} for r in rows],
                "code_default": [{"code": c, "rate_bps": b, "effective_from": s.isoformat(), "effective_to": e.isoformat() if e else None, "legal_reference": ref}
                                 for c, s, e, b, ref in VAT_RATE_SCHEDULE]}

    @api.get("/finance/tax-rates")
    def tax_list(user=Depends(finance_read), db: Session = Depends(get_db)) -> dict:
        return _tax_out(db, user.tenant_id)

    @api.post("/admin/tax-rates", status_code=201)
    def tax_add(data: TaxRateIn, user=Depends(tenant_admin), db: Session = Depends(get_db)) -> dict:
        if data.effective_to is not None and data.effective_to < data.effective_from:
            raise HTTPException(422, "تاریخ پایان نباید پیش از تاریخ شروع باشد")
        far = date(9999, 12, 31)
        for r in db.scalars(select(TaxRatePeriod).where(TaxRatePeriod.tenant_id == user.tenant_id, TaxRatePeriod.tax_type == data.tax_type, TaxRatePeriod.status == "active").with_for_update()).all():
            if r.effective_from <= (data.effective_to or far) and data.effective_from <= (r.effective_to or far):
                raise HTTPException(409, f"این بازه با نرخ فعال «{r.code}» هم‌پوشانی دارد؛ ابتدا آن را بازنشسته کنید یا تاریخ پایان را درست کنید")
        row = TaxRatePeriod(tenant_id=user.tenant_id, **data.model_dump(), status="active", created_by_user_id=user.id)
        db.add(row); db.flush()
        audit(db, user, "tax_rate.created", "tax_rate", {"id": row.id, **data.model_dump(mode="json")})
        db.commit()
        return _tax_out(db, user.tenant_id)

    @api.post("/admin/tax-rates/{rate_id}/retire")
    def tax_retire(rate_id: str, data: ReasonIn, user=Depends(tenant_admin), db: Session = Depends(get_db)) -> dict:
        row = db.scalar(select(TaxRatePeriod).where(TaxRatePeriod.id == rate_id, TaxRatePeriod.tenant_id == user.tenant_id).with_for_update())
        if row is None:
            raise HTTPException(404, "نرخ یافت نشد")
        if row.status != "active":
            raise HTTPException(409, "این نرخ قبلاً بازنشسته شده است")
        row.status, row.retired_by_user_id, row.retire_reason = "retired", user.id, data.reason
        audit(db, user, "tax_rate.retired", "tax_rate", {"id": row.id, "code": row.code, "reason": data.reason})
        db.commit()
        return _tax_out(db, user.tenant_id)

    # ------------------------------------------------------------------ failed payments (finance)
    @api.get("/finance/payments/failed")
    def failed_payments(days: int = Query(default=30, ge=1, le=180), include_abandoned: bool = True, user=Depends(finance_read), db: Session = Depends(get_db)) -> dict:
        """Payment intents the gateway refused or the customer cancelled, plus (optionally) ones started over an hour ago
        that never came back. Read-only; retrying is the customer's own checkout."""
        now, t = utcnow(), user.tenant_id
        statuses = ["failed"] + (["initiated", "created"] if include_abandoned else [])
        rows = db.execute(select(m.PaymentIntent, m.Reservation).join(m.Reservation, m.Reservation.id == m.PaymentIntent.reservation_id).where(
            m.PaymentIntent.tenant_id == t, m.Reservation.tenant_id == t, m.PaymentIntent.status.in_(statuses), m.PaymentIntent.updated_at >= now - timedelta(days=days))
            .order_by(m.PaymentIntent.updated_at.desc()).limit(300)).all()
        names = _names(db, [p.user_id for p, _ in rows])
        items = []
        for p, r in rows:
            if p.status in ("initiated", "created") and _aw(p.updated_at) > now - timedelta(hours=1):
                continue  # still in progress
            last = db.scalar(select(m.PaymentEvent.event_type).where(m.PaymentEvent.tenant_id == t, m.PaymentEvent.payment_intent_id == p.id).order_by(m.PaymentEvent.created_at.desc()).limit(1))
            later_paid = db.scalar(select(func.count()).select_from(m.PaymentIntent).where(m.PaymentIntent.tenant_id == t, m.PaymentIntent.reservation_id == r.id, m.PaymentIntent.status == "captured")) or 0
            items.append({"id": p.id, "status": "failed" if p.status == "failed" else "abandoned", "amount": p.amount, "currency": p.currency, "provider": p.provider_key,
                          "authority": p.provider_authority, "last_event": last, "updated_at": _iso(p.updated_at), "customer": names.get(p.user_id),
                          "reservation": {"id": r.id, "booking_reference": r.booking_reference, "service_type": r.service_type, "status": r.status},
                          "later_paid": bool(later_paid)})
        summary = {"failed": sum(1 for i in items if i["status"] == "failed"), "abandoned": sum(1 for i in items if i["status"] == "abandoned"),
                   "failed_amount": sum(i["amount"] for i in items if i["status"] == "failed"), "recovered": sum(1 for i in items if i["later_paid"])}
        return {"items": items, "summary": summary, "days": days, "generated_at": now.isoformat()}

    # ------------------------------------------------------------------ change-price proposals
    def _proposal_out(db: Session, p: PriceChangeProposal, staff: bool) -> dict:
        r = db.get(m.Reservation, p.reservation_id)
        out = {"id": p.id, "status": p.status, "current_total": p.current_total, "proposed_total": p.proposed_total, "difference": p.proposed_total - p.current_total,
               "currency": p.currency, "reason": p.reason, "created_at": _iso(p.created_at), "customer_decided_at": _iso(p.customer_decided_at), "customer_note": p.customer_note,
               "reservation": {"id": r.id, "booking_reference": r.booking_reference, "service_type": r.service_type, "status": r.status} if r else None,
               "settlement": ("collect_difference" if p.proposed_total > p.current_total else "refund_difference") if p.status == "accepted" else None}
        if staff:
            names = _names(db, [p.proposed_by_user_id, p.approved_by_user_id, p.customer_user_id])
            out.update({"proposed_by": names.get(p.proposed_by_user_id), "proposed_by_user_id": p.proposed_by_user_id, "approved_by": names.get(p.approved_by_user_id),
                        "customer": names.get(p.customer_user_id), "approval_request_id": p.approval_request_id})
        return out

    def _execute_price_change(db: Session, request, payload: dict, checker) -> dict:
        p = db.scalar(select(PriceChangeProposal).where(PriceChangeProposal.id == payload["proposal_id"], PriceChangeProposal.tenant_id == checker.tenant_id).with_for_update())
        if p is None:
            raise approvals.MakerCheckerError(404, "پیشنهاد یافت نشد")
        if p.status != "pending_approval":
            raise ValueError("این پیشنهاد دیگر در انتظار تأیید نیست")
        if checker.id == p.customer_user_id:
            raise approvals.MakerCheckerError(403, "تأیید تغییر قیمت رزرو خودتان مجاز نیست")
        p.status, p.approved_by_user_id = "awaiting_customer", checker.id
        db.add(m.NotificationRecord(tenant_id=p.tenant_id, user_id=p.customer_user_id, topic="price_change", title="پیشنهاد تغییر قیمت رزرو",
                                    message="مبلغ رزرو شما نیاز به تغییر دارد. تا تأیید شما هیچ مبلغی کسر یا پرداخت نمی‌شود.", deep_link="/account/price-changes"))
        db.add(m.OutboxEvent(tenant_id=p.tenant_id, aggregate_type="price_change", aggregate_id=p.id, event_type="price_change.awaiting_customer",
                             payload_json=json.dumps({"proposal_id": p.id}), correlation_id=str(uuid.uuid4()), idempotency_key=f"price-change:{p.id}:approved"))
        audit(db, checker, "price_change.approved", "price_change", {"proposal_id": p.id, "maker_user_id": request.maker_user_id})
        return {"proposal_id": p.id, "status": p.status}

    approvals.register("reservation.price_change", can_check=lambda actor, payload: role_has_permission(actor.role, "refund:manage") or role_has_permission(actor.role, "tenant:manage"),
                       execute=_execute_price_change, label="تغییر قیمت رزرو")

    @api.post("/ops/price-changes", status_code=201)
    def propose(data: PriceChangeIn, user=Depends(ops_user), db: Session = Depends(get_db),
                idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
        prior = db.scalar(select(PriceChangeProposal).where(PriceChangeProposal.tenant_id == user.tenant_id, PriceChangeProposal.command_id == idempotency_key))
        if prior is not None:
            if (prior.reservation_id, prior.proposed_total, prior.reason, prior.proposed_by_user_id) != (data.reservation_id, data.proposed_total, data.reason, user.id):
                raise HTTPException(409, "این شناسهٔ درخواست قبلاً با محتوای دیگری ثبت شده است")
            return _proposal_out(db, prior, True)
        r = db.scalar(select(m.Reservation).where(m.Reservation.id == data.reservation_id, m.Reservation.tenant_id == user.tenant_id).with_for_update())
        if r is None:
            raise HTTPException(404, "رزرو در این مجموعه وجود ندارد")
        if r.status not in ("reserved", "awaiting_payment", "confirmed", "issued"):
            raise HTTPException(409, "برای رزرو در این وضعیت پیشنهاد تغییر قیمت ثبت نمی‌شود")
        snap = json.loads(r.price_snapshot_json or "{}")
        current = snap.get("total_amount")
        if not isinstance(current, int):
            raise HTTPException(409, "مبلغ ثبت‌شدهٔ این رزرو در دسترس نیست؛ پیشنهاد بدون مبنای قیمت ثبت نمی‌شود")
        if (snap.get("currency") or "IRR") != "IRR":
            raise HTTPException(409, "تغییر قیمت فقط برای رزرو ریالی پشتیبانی می‌شود")
        if data.proposed_total == current:
            raise HTTPException(422, "مبلغ پیشنهادی با مبلغ فعلی برابر است")
        if r.user_id == user.id:
            raise HTTPException(403, "پیشنهاد تغییر قیمت برای رزرو خودتان مجاز نیست")
        if db.scalar(select(PriceChangeProposal.id).where(PriceChangeProposal.tenant_id == user.tenant_id, PriceChangeProposal.reservation_id == r.id,
                                                          PriceChangeProposal.status.in_(("pending_approval", "awaiting_customer")))):
            raise HTTPException(409, "برای این رزرو یک پیشنهاد باز وجود دارد")
        p = PriceChangeProposal(tenant_id=user.tenant_id, reservation_id=r.id, customer_user_id=r.user_id, proposed_by_user_id=user.id, current_total=current,
                                proposed_total=data.proposed_total, reason=data.reason, command_id=idempotency_key)
        db.add(p); db.flush()
        try:
            row = approvals.create_request(db, user=user, kind="reservation.price_change", payload={"proposal_id": p.id}, idempotency_key=f"pc:{p.id}",
                                           summary=f"تغییر قیمت رزرو {r.booking_reference or r.id[:8]}: {current:,} ← {data.proposed_total:,} ریال",
                                           amount=abs(data.proposed_total - current), target_ref=f"reservation:{r.id}", audit=audit)
        except approvals.MakerCheckerError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc
        p.approval_request_id = row.id
        audit(db, user, "price_change.proposed", "price_change", {"proposal_id": p.id, "reservation_id": r.id, "current_total": current, "proposed_total": data.proposed_total})
        db.commit()
        return _proposal_out(db, p, True)

    @api.get("/ops/price-changes")
    def proposals(status: Optional[str] = Query(default=None, pattern="^(pending_approval|awaiting_customer|accepted|declined|rejected|withdrawn)$"),
                  user=Depends(need("service_request:decide", "refund:manage", "tenant:manage")), db: Session = Depends(get_db)) -> dict:
        q = select(PriceChangeProposal).where(PriceChangeProposal.tenant_id == user.tenant_id)
        if status:
            q = q.where(PriceChangeProposal.status == status)
        rows = db.scalars(q.order_by(PriceChangeProposal.created_at.desc()).limit(200)).all()
        _sync_rejected(db, user.tenant_id, rows)
        return {"items": [_proposal_out(db, p, True) for p in rows]}

    def _sync_rejected(db: Session, tenant_id: int, rows) -> None:
        """A checker's rejection (or expiry) of the maker-checker request closes the proposal."""
        changed = False
        for p in rows:
            if p.status == "pending_approval" and p.approval_request_id:
                req = db.get(approvals.MakerCheckerRequest, p.approval_request_id)
                if req is not None and req.status in ("rejected", "expired"):
                    p.status, changed = "rejected", True
        if changed:
            db.commit()

    @api.post("/ops/price-changes/{proposal_id}/withdraw")
    def withdraw(proposal_id: str, data: ReasonIn, user=Depends(ops_user), db: Session = Depends(get_db)) -> dict:
        p = db.scalar(select(PriceChangeProposal).where(PriceChangeProposal.id == proposal_id, PriceChangeProposal.tenant_id == user.tenant_id).with_for_update())
        if p is None:
            raise HTTPException(404, "پیشنهاد یافت نشد")
        if p.status not in ("pending_approval", "awaiting_customer"):
            raise HTTPException(409, "این پیشنهاد دیگر قابل پس‌گرفتن نیست")
        if p.status == "pending_approval" and p.approval_request_id:
            req = db.get(approvals.MakerCheckerRequest, p.approval_request_id)
            if req is not None and req.status == "pending":
                req.status, req.decided_at, req.decision_note = "rejected", utcnow(), f"withdrawn by maker: {data.reason}"[:500]
        p.status = "withdrawn"
        audit(db, user, "price_change.withdrawn", "price_change", {"proposal_id": p.id, "reason": data.reason})
        db.commit()
        return _proposal_out(db, p, True)

    @api.get("/me/price-changes")
    def my_proposals(user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        rows = db.scalars(select(PriceChangeProposal).where(PriceChangeProposal.tenant_id == user.tenant_id, PriceChangeProposal.customer_user_id == user.id,
                                                            PriceChangeProposal.status.in_(("awaiting_customer", "accepted", "declined"))).order_by(PriceChangeProposal.created_at.desc()).limit(100)).all()
        return {"items": [_proposal_out(db, p, False) for p in rows]}

    def _customer_decide(db: Session, user, proposal_id: str, accept: bool, note: Optional[str]) -> dict:
        p = db.scalar(select(PriceChangeProposal).where(PriceChangeProposal.id == proposal_id, PriceChangeProposal.tenant_id == user.tenant_id,
                                                        PriceChangeProposal.customer_user_id == user.id).with_for_update())
        if p is None or p.status == "pending_approval":
            raise HTTPException(404, "پیشنهادی با این مشخصات برای شما وجود ندارد")
        target = "accepted" if accept else "declined"
        if p.status == target:
            return _proposal_out(db, p, False)  # same answer again
        if p.status != "awaiting_customer":
            raise HTTPException(409, "این پیشنهاد دیگر منتظر پاسخ شما نیست")
        p.status, p.customer_decided_at, p.customer_note = target, utcnow(), note
        db.add(m.OutboxEvent(tenant_id=p.tenant_id, aggregate_type="price_change", aggregate_id=p.id, event_type=f"price_change.{target}",
                             payload_json=json.dumps({"proposal_id": p.id, "difference": p.proposed_total - p.current_total}), correlation_id=str(uuid.uuid4()),
                             idempotency_key=f"price-change:{p.id}:{target}"))
        audit(db, user, f"price_change.customer_{target}", "price_change", {"proposal_id": p.id, "difference": p.proposed_total - p.current_total})
        db.commit()
        return _proposal_out(db, p, False)

    @api.post("/me/price-changes/{proposal_id}/accept")
    def accept(proposal_id: str, data: CustomerDecisionIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        return _customer_decide(db, user, proposal_id, True, data.note)

    @api.post("/me/price-changes/{proposal_id}/decline")
    def decline(proposal_id: str, data: CustomerDecisionIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        return _customer_decide(db, user, proposal_id, False, data.note)

    # ------------------------------------------------------------------ passengers of an organization / agency
    def _scope_access(db: Session, user, scope_type: str, scope_id: str) -> None:
        if scope_type == "organization":
            org = db.scalar(select(m.Organization).where(m.Organization.id == scope_id, m.Organization.tenant_id == user.tenant_id))
            if org is None:
                raise HTTPException(404, "سازمان در دسترس این حساب نیست")
            if has(user, "tenant:manage"):
                return
            member = db.scalar(select(m.EmployeeAssignment.id).where(m.EmployeeAssignment.tenant_id == user.tenant_id, m.EmployeeAssignment.organization_id == org.id,
                                                                     m.EmployeeAssignment.user_id == user.id))
            if member is None or user.role not in ORG_MANAGER_ROLES:
                raise HTTPException(404, "سازمان در دسترس این حساب نیست")
            return
        if scope_type == "agency":
            from .agency_b2b import agency_membership
            agency_membership(db, scope_id, user, role_has_permission)
            return
        raise HTTPException(404, "بخش یافت نشد")

    def _scoped(db: Session, user, scope_type: str, scope_id: str, traveller_id: str, lock: bool = False) -> m.Traveller:
        q = select(m.Traveller).join(ScopedTraveller, ScopedTraveller.traveller_id == m.Traveller.id).where(
            ScopedTraveller.tenant_id == user.tenant_id, ScopedTraveller.scope_type == scope_type, ScopedTraveller.scope_id == scope_id,
            m.Traveller.id == traveller_id, m.Traveller.tenant_id == user.tenant_id)
        t = db.scalar(q.with_for_update() if lock else q)
        if t is None:
            raise HTTPException(404, "مسافر در این بخش وجود ندارد")
        return t

    SCOPE = "{scope_type}"

    @api.get(f"/scopes/{SCOPE}/{{scope_id}}/passengers")
    def passengers(scope_type: str, scope_id: str, q: Optional[str] = Query(default=None, max_length=80), user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        _scope_access(db, user, scope_type, scope_id)
        s = select(m.Traveller).join(ScopedTraveller, ScopedTraveller.traveller_id == m.Traveller.id).where(
            ScopedTraveller.tenant_id == user.tenant_id, ScopedTraveller.scope_type == scope_type, ScopedTraveller.scope_id == scope_id, m.Traveller.tenant_id == user.tenant_id)
        if q:
            s = s.where(m.Traveller.full_name.contains(q.strip(), autoescape=True))
        rows = db.scalars(s.order_by(m.Traveller.full_name).limit(500)).all()
        ids = ti.identities_for(db, user.tenant_id, [r.id for r in rows])
        return {"items": [ti.traveller_output(r, ids.get(r.id)) for r in rows], "masked": True}

    @api.post(f"/scopes/{SCOPE}/{{scope_id}}/passengers", status_code=201)
    def add_passenger(scope_type: str, scope_id: str, data: PassengerIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        _scope_access(db, user, scope_type, scope_id)
        t = m.Traveller(tenant_id=user.tenant_id, user_id=None, full_name=data.full_name.strip())
        db.add(t); db.flush()
        ident = ti.apply_identity(db, t, data)
        db.add(ScopedTraveller(tenant_id=user.tenant_id, scope_type=scope_type, scope_id=scope_id, traveller_id=t.id, created_by_user_id=user.id))
        audit(db, user, "scoped_traveller.created", "traveller", {"scope_type": scope_type, "scope_id": scope_id, "traveller_id": t.id})
        db.commit()
        return ti.traveller_output(t, ident)

    @api.put(f"/scopes/{SCOPE}/{{scope_id}}/passengers/{{traveller_id}}")
    def edit_passenger(scope_type: str, scope_id: str, traveller_id: str, data: PassengerIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        _scope_access(db, user, scope_type, scope_id)
        t = _scoped(db, user, scope_type, scope_id, traveller_id, lock=True)
        t.full_name = data.full_name.strip()
        ident = ti.apply_identity(db, t, data)
        audit(db, user, "scoped_traveller.updated", "traveller", {"scope_type": scope_type, "scope_id": scope_id, "traveller_id": t.id, "fields": sorted(data.model_fields_set)})
        db.commit()
        return ti.traveller_output(t, ident)

    @api.get(f"/scopes/{SCOPE}/{{scope_id}}/passengers/{{traveller_id}}/identity")
    def passenger_identity(scope_type: str, scope_id: str, traveller_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        """Full numbers for the edit form only; every read is audited."""
        _scope_access(db, user, scope_type, scope_id)
        t = _scoped(db, user, scope_type, scope_id, traveller_id)
        audit(db, user, "scoped_traveller.identity_read", "traveller", {"scope_type": scope_type, "scope_id": scope_id, "traveller_id": t.id})
        db.commit()
        return {"id": t.id, "full_name": t.full_name, **ti.full(ti.identities_for(db, user.tenant_id, [t.id]).get(t.id))}

    @api.post(f"/scopes/{SCOPE}/{{scope_id}}/passengers/{{traveller_id}}/remove")
    def remove_passenger(scope_type: str, scope_id: str, traveller_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        _scope_access(db, user, scope_type, scope_id)
        t = _scoped(db, user, scope_type, scope_id, traveller_id)
        link = db.scalar(select(ScopedTraveller).where(ScopedTraveller.tenant_id == user.tenant_id, ScopedTraveller.scope_type == scope_type,
                                                       ScopedTraveller.scope_id == scope_id, ScopedTraveller.traveller_id == t.id))
        db.delete(link)  # the traveller row stays: past reservations keep their passenger
        audit(db, user, "scoped_traveller.removed", "traveller", {"scope_type": scope_type, "scope_id": scope_id, "traveller_id": t.id})
        db.commit()
        return {"removed": t.id}

    # ------------------------------------------------------------------ gateway settlement file import
    def _match(db: Session, tenant_id: int, rows: list[dict]) -> list[dict]:
        seen, out = set(), []
        for r in rows:
            ref = r["reference"]
            if ref in seen:
                out.append({**r, "match_status": "duplicate", "payment_intent_id": None, "note": "شناسهٔ تکراری در همین فایل"})
                continue
            seen.add(ref)
            p = db.scalar(select(m.PaymentIntent).where(m.PaymentIntent.tenant_id == tenant_id, (m.PaymentIntent.provider_authority == ref)
                                                        | (m.PaymentIntent.provider_reference == ref) | (m.PaymentIntent.provider_capture_reference == ref)).limit(1))
            if p is None:
                out.append({**r, "match_status": "unmatched", "payment_intent_id": None, "note": "پرداختی با این شناسه در سامانه نیست"})
            elif p.status not in ("captured", "refunded"):
                out.append({**r, "match_status": "not_captured", "payment_intent_id": p.id, "note": f"وضعیت پرداخت در سامانه: {p.status}"})
            elif p.captured_amount != r["amount"]:
                out.append({**r, "match_status": "amount_mismatch", "payment_intent_id": p.id, "note": f"مبلغ ثبت‌شده در سامانه {p.captured_amount:,} ریال"})
            else:
                out.append({**r, "match_status": "matched", "payment_intent_id": p.id, "note": None})
        return out

    def _import_out(db: Session, imp: SettlementImport, lines: bool = True) -> dict:
        out = {"id": imp.id, "provider": imp.provider, "filename": imp.filename, "row_count": imp.row_count, "matched_count": imp.matched_count,
               "unmatched_count": imp.unmatched_count, "total_amount": imp.total_amount, "created_at": _iso(imp.created_at),
               "uploaded_by": _names(db, [imp.uploaded_by_user_id]).get(imp.uploaded_by_user_id)}
        if lines:
            rows = db.scalars(select(SettlementImportLine).where(SettlementImportLine.tenant_id == imp.tenant_id, SettlementImportLine.import_id == imp.id).order_by(SettlementImportLine.line_no)).all()
            out["lines"] = [{"line": r.line_no, "reference": r.reference, "amount": r.amount, "settled_on": r.settled_on, "match_status": r.match_status,
                             "payment_intent_id": r.payment_intent_id, "note": r.note} for r in rows]
        return out

    @api.post("/finance/settlement-imports", status_code=201)
    def import_settlement(data: SettlementIn, user=Depends(recon_user), db: Session = Depends(get_db)) -> dict:
        digest = hashlib.sha256(data.content.encode("utf-8")).hexdigest()
        rows, errors = parse_settlement_csv(data.content)
        if errors:
            raise HTTPException(422, {"code": "SETTLEMENT_FILE_INVALID", "message": "فایل ایراد دارد؛ هیچ ردیفی ثبت نشد", "errors": errors[:50]})
        matched = _match(db, user.tenant_id, rows)
        if data.dry_run:
            return {"dry_run": True, "row_count": len(matched), "lines": matched,
                    "matched_count": sum(1 for r in matched if r["match_status"] == "matched")}
        prior = db.scalar(select(SettlementImport).where(SettlementImport.tenant_id == user.tenant_id, SettlementImport.file_sha256 == digest))
        if prior is not None:
            return {**_import_out(db, prior), "duplicate_file": True}
        imp = SettlementImport(tenant_id=user.tenant_id, provider=data.provider, filename=data.filename, file_sha256=digest, uploaded_by_user_id=user.id,
                               row_count=len(matched), matched_count=sum(1 for r in matched if r["match_status"] == "matched"),
                               unmatched_count=sum(1 for r in matched if r["match_status"] != "matched"), total_amount=sum(r["amount"] for r in matched))
        db.add(imp); db.flush()
        for r in matched:
            db.add(SettlementImportLine(tenant_id=user.tenant_id, import_id=imp.id, line_no=r["line"], reference=r["reference"], amount=r["amount"],
                                        settled_on=r["settled_on"], match_status=r["match_status"], payment_intent_id=r["payment_intent_id"], note=r["note"]))
        audit(db, user, "settlement_import.created", "settlement_import", {"id": imp.id, "rows": imp.row_count, "matched": imp.matched_count, "sha256": digest})
        db.commit()
        return _import_out(db, imp)

    @api.get("/finance/settlement-imports")
    def imports(user=Depends(recon_user), db: Session = Depends(get_db)) -> dict:
        rows = db.scalars(select(SettlementImport).where(SettlementImport.tenant_id == user.tenant_id).order_by(SettlementImport.created_at.desc()).limit(100)).all()
        return {"items": [_import_out(db, r, lines=False) for r in rows]}

    @api.get("/finance/settlement-imports/{import_id}")
    def import_detail(import_id: str, user=Depends(recon_user), db: Session = Depends(get_db)) -> dict:
        imp = db.scalar(select(SettlementImport).where(SettlementImport.id == import_id, SettlementImport.tenant_id == user.tenant_id))
        if imp is None:
            raise HTTPException(404, "فایل تسویه یافت نشد")
        return _import_out(db, imp)

    # ------------------------------------------------------------------ bank payout batch (file only, two-person)
    def _payable_refunds(db: Session, tenant_id: int, ids: Optional[list[str]] = None):
        """Bank-transfer refunds approved by ops and waiting for finance, not already in an open or approved batch."""
        taken = select(BankPayoutItem.refund_id).join(BankPayoutBatch, BankPayoutBatch.id == BankPayoutItem.batch_id).where(
            BankPayoutItem.tenant_id == tenant_id, BankPayoutBatch.tenant_id == tenant_id, BankPayoutBatch.status.in_(("pending_approval", "approved")))
        q = select(m.RefundRecord, asl.RefundExecution).join(asl.RefundExecution, (asl.RefundExecution.refund_id == m.RefundRecord.id) & (asl.RefundExecution.tenant_id == tenant_id)).where(
            m.RefundRecord.tenant_id == tenant_id, m.RefundRecord.status == "pending_finance", asl.RefundExecution.destination == "bank_transfer", m.RefundRecord.id.notin_(taken))
        if ids is not None:
            q = q.where(m.RefundRecord.id.in_(ids))
        return db.execute(q.order_by(m.RefundRecord.created_at)).all()

    def _bank(db: Session, tenant_id: int, user_id: int):
        from .commerce import UserBankAccount
        return db.scalar(select(UserBankAccount).where(UserBankAccount.tenant_id == tenant_id, UserBankAccount.user_id == user_id))

    def _batch_out(db: Session, b: BankPayoutBatch) -> dict:
        items = db.scalars(select(BankPayoutItem).where(BankPayoutItem.tenant_id == b.tenant_id, BankPayoutItem.batch_id == b.id)).all()
        names = _names(db, [b.created_by_user_id, b.approved_by_user_id])
        return {"id": b.id, "status": b.status, "item_count": b.item_count, "total_amount": b.total_amount, "note": b.note, "created_at": _iso(b.created_at),
                "created_by": names.get(b.created_by_user_id), "created_by_user_id": b.created_by_user_id, "approved_by": names.get(b.approved_by_user_id),
                "approval_request_id": b.approval_request_id, "file_name": b.file_name, "file_sha256": b.file_sha256, "file_ready": bool(b.file_text),
                "items": [{"refund_id": i.refund_id, "amount": i.amount, "holder_name": i.holder_name, "sheba_masked": i.sheba_masked} for i in items]}

    def _execute_bank_batch(db: Session, request, payload: dict, checker) -> dict:
        b = db.scalar(select(BankPayoutBatch).where(BankPayoutBatch.id == payload["batch_id"], BankPayoutBatch.tenant_id == checker.tenant_id).with_for_update())
        if b is None:
            raise approvals.MakerCheckerError(404, "دستهٔ پرداخت یافت نشد")
        if b.status != "pending_approval":
            raise ValueError("این دسته دیگر در انتظار تأیید نیست")
        items = db.scalars(select(BankPayoutItem).where(BankPayoutItem.tenant_id == b.tenant_id, BankPayoutItem.batch_id == b.id)).all()
        rows = []
        for it in items:
            refund = db.get(m.RefundRecord, it.refund_id)
            ex = db.scalar(select(asl.RefundExecution).where(asl.RefundExecution.tenant_id == b.tenant_id, asl.RefundExecution.refund_id == it.refund_id))
            if refund is None or ex is None or refund.status != "pending_finance" or refund.amount != it.amount:
                raise ValueError("وضعیت یا مبلغ یکی از استردادها پس از ساخت دسته تغییر کرده است؛ دستهٔ تازه بسازید")
            bank = _bank(db, b.tenant_id, ex.customer_user_id)
            if bank is None or not bank.sheba:
                raise ValueError("شبای یکی از مشتریان در دسترس نیست؛ دستهٔ تازه بسازید")
            rows.append({"sheba": bank.sheba, "holder_name": bank.holder_name, "amount": it.amount, "refund_id": it.refund_id})
        text = bank_file_csv(b.id, rows)
        b.file_text, b.file_sha256 = text, hashlib.sha256(text.encode("utf-8")).hexdigest()
        b.file_name = f"karentravel-payout-{b.id[:8]}.csv"
        b.status, b.approved_by_user_id = "approved", checker.id
        audit(db, checker, "bank_batch.approved", "bank_batch", {"batch_id": b.id, "items": len(rows), "total": b.total_amount, "file_sha256": b.file_sha256,
                                                                   "maker_user_id": request.maker_user_id})
        return {"batch_id": b.id, "status": b.status, "file_sha256": b.file_sha256}

    approvals.register("finance.bank_batch", can_check=lambda actor, payload: role_has_permission(actor.role, "refund:manage"),
                       execute=_execute_bank_batch, label="فایل پرداخت گروهی بانکی")

    @api.get("/finance/bank-batches/candidates")
    def batch_candidates(user=Depends(refund_user), db: Session = Depends(get_db)) -> dict:
        out = []
        for refund, ex in _payable_refunds(db, user.tenant_id):
            snap = json.loads(ex.destination_json or "{}")
            bank = _bank(db, user.tenant_id, ex.customer_user_id)
            out.append({"refund_id": refund.id, "amount": refund.amount, "holder_name": (bank.holder_name if bank else None) or snap.get("holder_name"),
                        "sheba_masked": asl.mask_sheba(bank.sheba) if bank and bank.sheba else snap.get("sheba_masked"), "has_sheba": bool(bank and bank.sheba),
                        "created_at": _iso(refund.created_at)})
        return {"items": out}

    @api.get("/finance/bank-batches")
    def batches(user=Depends(refund_user), db: Session = Depends(get_db)) -> dict:
        rows = db.scalars(select(BankPayoutBatch).where(BankPayoutBatch.tenant_id == user.tenant_id).order_by(BankPayoutBatch.created_at.desc()).limit(100)).all()
        for b in rows:
            if b.status == "pending_approval" and b.approval_request_id:
                req = db.get(approvals.MakerCheckerRequest, b.approval_request_id)
                if req is not None and req.status in ("rejected", "expired"):
                    b.status = "rejected"
        db.commit()
        return {"items": [_batch_out(db, b) for b in rows], "me": user.id}

    @api.post("/finance/bank-batches", status_code=201)
    def create_batch(data: BankBatchIn, user=Depends(refund_user), db: Session = Depends(get_db),
                     idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
        prior = db.scalar(select(BankPayoutBatch).where(BankPayoutBatch.tenant_id == user.tenant_id, BankPayoutBatch.command_id == idempotency_key))
        if prior is not None:
            same = sorted(i.refund_id for i in db.scalars(select(BankPayoutItem).where(BankPayoutItem.tenant_id == user.tenant_id, BankPayoutItem.batch_id == prior.id)).all())
            if same != sorted(set(data.refund_ids)) or prior.created_by_user_id != user.id:
                raise HTTPException(409, "این شناسهٔ درخواست قبلاً با محتوای دیگری ثبت شده است")
            return _batch_out(db, prior)
        ids = sorted(set(data.refund_ids))
        rows = _payable_refunds(db, user.tenant_id, ids)
        if len(rows) != len(ids):
            raise HTTPException(409, "برخی استردادها برای پرداخت بانکی آماده نیستند یا در دستهٔ دیگری هستند")
        b = BankPayoutBatch(tenant_id=user.tenant_id, created_by_user_id=user.id, item_count=len(rows), total_amount=sum(r.amount for r, _ in rows), note=data.note, command_id=idempotency_key)
        db.add(b); db.flush()
        for refund, ex in rows:
            bank = _bank(db, user.tenant_id, ex.customer_user_id)
            if bank is None or not bank.sheba:
                raise HTTPException(409, "برای یکی از استردادها شبای مشتری ثبت نشده است")
            db.add(BankPayoutItem(tenant_id=user.tenant_id, batch_id=b.id, refund_id=refund.id, amount=refund.amount, holder_name=bank.holder_name or "—", sheba_masked=asl.mask_sheba(bank.sheba)))
        try:
            req = approvals.create_request(db, user=user, kind="finance.bank_batch", payload={"batch_id": b.id}, idempotency_key=f"bank-batch:{b.id}",
                                           summary=f"پرداخت گروهی بانکی: {len(rows)} مورد، {b.total_amount:,} ریال", amount=b.total_amount, target_ref=f"bank_batch:{b.id}", audit=audit)
        except approvals.MakerCheckerError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc
        b.approval_request_id = req.id
        audit(db, user, "bank_batch.created", "bank_batch", {"batch_id": b.id, "items": len(rows), "total": b.total_amount})
        db.commit()
        return _batch_out(db, b)

    @api.get("/finance/bank-batches/{batch_id}/file")
    def batch_file(batch_id: str, user=Depends(refund_user), db: Session = Depends(get_db)) -> Response:
        b = db.scalar(select(BankPayoutBatch).where(BankPayoutBatch.id == batch_id, BankPayoutBatch.tenant_id == user.tenant_id))
        if b is None:
            raise HTTPException(404, "دستهٔ پرداخت یافت نشد")
        if b.status != "approved" or not b.file_text:
            raise HTTPException(409, "فایل فقط پس از تأیید نفر دوم ساخته می‌شود")
        audit(db, user, "bank_batch.file_downloaded", "bank_batch", {"batch_id": b.id, "file_sha256": b.file_sha256})
        db.commit()
        return Response(content=b.file_text, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{b.file_name}"', "Cache-Control": "no-store", "X-File-SHA256": b.file_sha256 or ""})

    return api
