"""After-sales loop (Panels Phase 1, spec 04-panel-spec §2.1 C-03/C-04, §2.9 OPS-02/03, §2.10 FIN-02/04, §2.12 E2E-C, §3).

customer request (cancel | change | refund)  ->  ops queue (assign, review, supplier, decide)  ->  finance refund queue
(prepare by one finance user, approve by another)  ->  customer timeline with each step, the next step and its ETA.

Rules kept here:
* C-1: a customer only *requests* (submit, withdraw while `submitted`, answer a question). Every other transition needs
  `service_request:decide` (ops) or `refund:manage` (finance). One state machine (TRANSITIONS) governs all of them.
* Money is integer rial. The penalty comes from the verified cancellation policy captured at booking, or is set by ops
  by hand with a mandatory reason. A refund larger than the verified quote needs `refund:override`.
* Two-person rule on every refund payment: the finance user who prepares a payment can never approve it.
* Idempotency-Key on every money POST; the key is bound to a hash of the request, a reused key with another body is 409.
* VAT on commission (Tazheban is seller of record, AGENT model, §3 / 05-owner-legal-answers): the reversed commission,
  markup and service fee and the VAT on them are computed from the reservation's recorded PriceBreakdown and stored as
  data on a pending «برگشت از فروش» document. Nothing is sent to Moadian here; without a recorded breakdown the document
  says so instead of guessing.
* SLA hours below are default targets (owner-configurable later); an ETA is "target", never a promise from a provider.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

VAT_RATE_BPS = 1000  # 10% (1405 budget law); FIN-11 dated tax-rate table will replace this constant
VAT_RATE_SOURCE = "default_1405_10pct_pending_FIN-11"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aw(dt: Optional[datetime]) -> Optional[datetime]:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def _iso(dt: Optional[datetime]) -> Optional[str]:
    dt = _aw(dt)
    return dt.isoformat() if dt else None


# ============================================================================ state machine
class InvalidTransition(ValueError):
    pass


REQUEST_STATUSES = ("submitted", "under_review", "waiting_supplier", "needs_customer", "approved", "refund_queued",
                    "refund_paid", "closed", "rejected", "withdrawn")
OPEN_STATUSES = ("submitted", "under_review", "waiting_supplier", "needs_customer", "approved", "refund_queued", "refund_paid")
TERMINAL_STATUSES = ("closed", "rejected", "withdrawn")

# action -> (from statuses, to status, actor kind). actor kind decides who may run it (see ACTOR_PERMISSION).
TRANSITIONS: dict[str, tuple[frozenset, str, str]] = {
    "withdraw": (frozenset({"submitted"}), "withdrawn", "customer"),
    "customer_reply": (frozenset({"needs_customer"}), "under_review", "customer"),
    "start_review": (frozenset({"submitted"}), "under_review", "ops"),
    "request_supplier": (frozenset({"under_review"}), "waiting_supplier", "ops"),
    "record_supplier_response": (frozenset({"waiting_supplier"}), "under_review", "ops"),
    "need_customer": (frozenset({"under_review", "waiting_supplier"}), "needs_customer", "ops"),
    "approve": (frozenset({"under_review"}), "approved", "ops"),
    "reject": (frozenset({"submitted", "under_review", "waiting_supplier", "needs_customer"}), "rejected", "ops"),
    "close": (frozenset({"approved", "refund_paid"}), "closed", "ops"),
    "queue_refund": (frozenset({"approved"}), "refund_queued", "system"),
    "finance_return": (frozenset({"refund_queued"}), "under_review", "finance"),
    "refund_paid": (frozenset({"refund_queued"}), "refund_paid", "finance"),
}
OPS_ACTIONS = tuple(a for a, (_, _, k) in TRANSITIONS.items() if k == "ops")
ACTOR_PERMISSION = {"ops": "service_request:decide", "finance": "refund:manage"}


def next_status(current: str, action: str) -> str:
    rule = TRANSITIONS.get(action)
    if rule is None:
        raise InvalidTransition(f"unknown action {action}")
    sources, target, _ = rule
    if current not in sources:
        raise InvalidTransition(f"{action} is not allowed from {current}")
    return target


# Finance refund payment: pending_finance -> awaiting_approval (maker) -> succeeded (checker); decline / return.
REFUND_TRANSITIONS: dict[str, tuple[frozenset, str]] = {
    "prepare": (frozenset({"pending_finance"}), "awaiting_approval"),
    "approve": (frozenset({"awaiting_approval"}), "succeeded"),
    "decline": (frozenset({"awaiting_approval"}), "pending_finance"),
    "return": (frozenset({"pending_finance", "awaiting_approval"}), "returned"),
}
REFUND_OPEN = ("pending_finance", "awaiting_approval")


def next_refund_status(current: str, action: str) -> str:
    rule = REFUND_TRANSITIONS.get(action)
    if rule is None or current not in rule[0]:
        raise InvalidTransition(f"refund {action} is not allowed from {current}")
    return rule[1]


STATUS_FA = {"submitted": "ثبت‌شده", "under_review": "در حال بررسی", "waiting_supplier": "در انتظار تأمین‌کننده",
             "needs_customer": "منتظر پاسخ شما", "approved": "تأییدشده", "refund_queued": "در صف پرداخت",
             "refund_paid": "پرداخت‌شده", "closed": "بسته‌شده", "rejected": "ردشده", "withdrawn": "پس‌گرفته‌شده"}
TYPE_FA = {"cancel": "لغو", "change": "تغییر", "refund": "استرداد"}
# status -> (next step title, owner, SLA hours or None when the clock is paused/finished)
NEXT_STEP = {
    "submitted": ("شروع بررسی توسط کارشناس", "عملیات", 4),
    "under_review": ("تصمیم کارشناس دربارهٔ درخواست", "عملیات", 24),
    "waiting_supplier": ("پاسخ تأمین‌کننده", "تأمین‌کننده", 72),
    "needs_customer": ("پاسخ شما به پرسش کارشناس", "شما", None),
    "approved": ("ورود به صف پرداخت مالی", "مالی", 4),
    "refund_queued": ("پرداخت استرداد توسط مالی (دو نفر)", "مالی", 72),
    "refund_paid": ("بستن درخواست", "عملیات", 24),
}
ACTOR_FA = {"customer": "شما", "ops": "کارشناس عملیات", "finance": "کارشناس مالی", "system": "سامانه", "supplier": "تأمین‌کننده"}
EVENT_FA = {"submitted": "ثبت درخواست", "start_review": "شروع بررسی", "assign": "تخصیص به کارشناس", "request_supplier": "ارسال به تأمین‌کننده",
            "record_supplier_response": "ثبت پاسخ تأمین‌کننده", "need_customer": "پرسش از شما", "customer_reply": "پاسخ شما",
            "approve": "تأیید درخواست", "reject": "رد درخواست", "withdraw": "انصراف از درخواست", "queue_refund": "ورود به صف پرداخت",
            "finance_prepare": "آماده‌سازی پرداخت (نفر اول مالی)", "finance_decline": "برگشت به آماده‌سازی (نفر دوم مالی)",
            "finance_return": "برگشت از مالی به عملیات", "refund_paid": "پرداخت استرداد", "close": "بستن درخواست", "note": "یادداشت داخلی"}
CUSTOMER_HIDDEN_EVENTS = {"assign", "note", "finance_decline"}
METHOD_FA = {"wallet": "کیف پول کارن تراول", "bank_transfer": "واریز بانکی به شبا", "gateway": "برگشت به کارت از درگاه"}


# ============================================================================ money math (integer rial, no float)
def half_up(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator < 0:
        raise ValueError("amounts are non-negative")
    return (2 * numerator + denominator) // (2 * denominator)


def vat_of(base: int, bps: int = VAT_RATE_BPS) -> int:
    return half_up(base * bps, 10000)


def refund_amount_for(paid_remaining: int, penalty: int) -> int:
    if penalty < 0 or paid_remaining < 0 or penalty > paid_remaining:
        raise ValueError("penalty must be between zero and the paid amount")
    return paid_remaining - penalty


def vat_reversal(*, refund_amount: int, customer_total: Optional[int], service_fee: Optional[int], platform_markup: Optional[int],
                 agency_commission: Optional[int], vat_bps: int = VAT_RATE_BPS) -> dict:
    """§3 / E2E-C: VAT on our own income (commission + markup + service fee) is reversed for the part that is returned.

    The customer total is split into the fare part (supplier price incl. markup) and the service fee + its VAT. A refund
    first returns the fare part; only what is left over (e.g. carrier cancellation) returns the service fee. Commission and
    markup are reversed in proportion to the fare returned (commission on the penalty part is kept, per E2E-C).
    Returns basis="unavailable" when the reservation has no recorded breakdown: nothing is guessed."""
    if customer_total is None or customer_total <= 0:
        return {"basis": "unavailable", "reason": "price_breakdown_missing", "vat_rate_bps": vat_bps, "vat_rate_source": VAT_RATE_SOURCE}
    sf = int(service_fee or 0); markup = int(platform_markup or 0); commission = int(agency_commission or 0)
    sf_vat = vat_of(sf, vat_bps)
    fare_part = customer_total - sf - sf_vat
    if fare_part <= 0 or refund_amount > customer_total:
        return {"basis": "unavailable", "reason": "price_breakdown_inconsistent", "vat_rate_bps": vat_bps, "vat_rate_source": VAT_RATE_SOURCE}
    fare_refunded = min(refund_amount, fare_part)
    fee_refunded_total = refund_amount - fare_refunded
    service_fee_reversed = half_up(fee_refunded_total * sf, sf + sf_vat) if sf > 0 else 0
    commission_reversed = half_up(commission * fare_refunded, fare_part)
    markup_reversed = half_up(markup * fare_refunded, fare_part)
    base = commission_reversed + markup_reversed + service_fee_reversed
    return {"basis": "price_breakdown", "vat_rate_bps": vat_bps, "vat_rate_source": VAT_RATE_SOURCE, "fare_part": fare_part,
            "fare_refunded": fare_refunded, "service_fee_refunded_incl_vat": fee_refunded_total,
            "agency_commission_reversed": commission_reversed, "platform_markup_reversed": markup_reversed,
            "service_fee_reversed": service_fee_reversed, "vat_base_reversed": base, "vat_reversed": vat_of(base, vat_bps),
            "service_fee_vat_returned_to_customer": fee_refunded_total - service_fee_reversed}


# ============================================================================ tables
class ServiceRequestHandling(OperationalMixin, Base):
    """Ops/finance handling of one BookingServiceRequest (1:1): owner, SLA clock, decision, penalty and refund link."""
    __tablename__ = "service_request_handling"
    request_id: Mapped[str] = mapped_column(ForeignKey("booking_service_requests.id"), index=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    customer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    prior_reservation_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    refund_destination: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    destination_json: Mapped[str] = mapped_column(Text, default="{}")
    penalty_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    penalty_source: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    approved_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    supplier_json: Mapped[str] = mapped_column(Text, default="{}")
    refund_id: Mapped[Optional[str]] = mapped_column(ForeignKey("refund_records.id"), nullable=True, index=True)
    customer_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "request_id", name="uq_sr_handling_request"),)


class ServiceRequestEvent(OperationalMixin, Base):
    """Append-only timeline of a service request (customer-visible unless internal)."""
    __tablename__ = "service_request_events"
    request_id: Mapped[str] = mapped_column(ForeignKey("booking_service_requests.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    actor_kind: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal: Mapped[bool] = mapped_column(Boolean, default=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    command_id: Mapped[str] = mapped_column(String(160))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_sr_event_command"),)


class RefundExecution(OperationalMixin, Base):
    """Finance side of one RefundRecord created by an ops approval: destination, maker, checker, bank reference."""
    __tablename__ = "refund_executions"
    refund_id: Mapped[str] = mapped_column(ForeignKey("refund_records.id"), index=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("booking_service_requests.id"), index=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    customer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    destination: Mapped[str] = mapped_column(String(24))
    destination_json: Mapped[str] = mapped_column(Text, default="{}")
    penalty_amount: Mapped[int] = mapped_column(Integer, default=0)
    paid_total: Mapped[int] = mapped_column(Integer, default=0)
    breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    method: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    bank_reference: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    prepared_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    prepared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "refund_id", name="uq_refund_execution_refund"),)


class RefundJournalLine(OperationalMixin, Base):
    """Balanced journal lines of a refund payment (sum debit == sum credit per refund). Append-only."""
    __tablename__ = "refund_journal_lines"
    refund_id: Mapped[str] = mapped_column(ForeignKey("refund_records.id"), index=True)
    command_id: Mapped[str] = mapped_column(String(160))
    account: Mapped[str] = mapped_column(String(48))
    debit: Mapped[int] = mapped_column(Integer, default=0)
    credit: Mapped[int] = mapped_column(Integer, default=0)
    memo: Mapped[str] = mapped_column(String(240))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_refund_journal_command"),)


class TaxReturnDocument(OperationalMixin, Base):
    """Pending «برگشت از فروش» (Moadian subject RETURN) built when a refund is paid. Never marked sent here."""
    __tablename__ = "tax_return_documents"
    refund_id: Mapped[str] = mapped_column(ForeignKey("refund_records.id"), index=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    licensed_entity_id: Mapped[Optional[str]] = mapped_column(ForeignKey("licensed_entities.id"), nullable=True)
    ref_invoice_id: Mapped[Optional[str]] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16), default="RETURN")
    basis: Mapped[str] = mapped_column(String(24))
    lines_json: Mapped[str] = mapped_column(Text, default="[]")
    totals_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "refund_id", name="uq_tax_return_refund"),)


class ReconciliationLink(OperationalMixin, Base):
    """Manual link of a reconciliation discrepancy to a payment or reservation (FIN-04). active=False after unlink."""
    __tablename__ = "reconciliation_links"
    record_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_records.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(36))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    linked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    unlinked_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    unlink_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


AFTER_SALES_TABLES = ("service_request_handling", "service_request_events", "refund_executions", "refund_journal_lines",
                      "tax_return_documents", "reconciliation_links")


# ============================================================================ helpers used by main.py too
def record_event(db: Session, *, req: m.BookingServiceRequest, event_type: str, actor_kind: str, actor_id: Optional[int],
                 from_status: Optional[str] = None, to_status: Optional[str] = None, note: Optional[str] = None,
                 internal: bool = False, payload: Optional[dict] = None, command_id: Optional[str] = None) -> ServiceRequestEvent:
    ev = ServiceRequestEvent(tenant_id=req.tenant_id, request_id=req.id, event_type=event_type, from_status=from_status, to_status=to_status,
                             actor_kind=actor_kind, actor_id=actor_id, note=note, internal=internal,
                             payload_json=json.dumps(payload or {}, sort_keys=True, ensure_ascii=False),
                             command_id=(command_id or f"sr-event:{req.id}:{uuid.uuid4()}")[:160])
    db.add(ev)
    return ev


def start_handling(db: Session, *, req: m.BookingServiceRequest, reservation: m.Reservation, prior_status: str, destination: Optional[str],
                   destination_detail: dict, actor_id: int, command_id: str) -> ServiceRequestHandling:
    """Called by POST /reservations/{id}/service-requests right after the request row is created."""
    h = ServiceRequestHandling(tenant_id=req.tenant_id, request_id=req.id, reservation_id=reservation.id, customer_user_id=reservation.user_id,
                               prior_reservation_status=prior_status, refund_destination=destination,
                               destination_json=json.dumps(destination_detail, sort_keys=True, ensure_ascii=False))
    db.add(h)
    record_event(db, req=req, event_type="submitted", actor_kind="customer", actor_id=actor_id, to_status="submitted", note=req.reason,
                 payload={"request_type": req.request_type, "destination": destination}, command_id=f"sr-submit:{command_id}")
    return h


def handling_for(db: Session, req: m.BookingServiceRequest) -> ServiceRequestHandling:
    h = db.scalar(select(ServiceRequestHandling).where(ServiceRequestHandling.tenant_id == req.tenant_id, ServiceRequestHandling.request_id == req.id))
    if h is None:  # requests created before this module existed
        res = db.scalar(select(m.Reservation).where(m.Reservation.id == req.reservation_id, m.Reservation.tenant_id == req.tenant_id))
        h = ServiceRequestHandling(tenant_id=req.tenant_id, request_id=req.id, reservation_id=req.reservation_id,
                                   customer_user_id=res.user_id if res else 0, status_since=_aw(req.updated_at) or utcnow())
        db.add(h); db.flush()
    return h


def next_step(status: str, since: Optional[datetime], now: Optional[datetime] = None) -> Optional[dict]:
    rule = NEXT_STEP.get(status)
    if rule is None:
        return None
    title, owner, hours = rule
    if hours is None:
        return {"title": title, "owner": owner, "eta": None, "overdue": False, "sla_hours": None, "paused": True}
    eta = (_aw(since) or utcnow()) + timedelta(hours=hours)
    return {"title": title, "owner": owner, "eta": eta.isoformat(), "overdue": eta < (now or utcnow()), "sla_hours": hours, "paused": False}


def mask_sheba(sheba: Optional[str]) -> Optional[str]:
    if not sheba:
        return None
    s = sheba.replace(" ", "")
    return s[:4] + "•" * max(len(s) - 8, 0) + s[-4:]


def destination_options(db: Session, *, tenant_id: int, user_id: int) -> list[dict]:
    from .commerce import UserBankAccount
    bank = db.scalar(select(UserBankAccount).where(UserBankAccount.tenant_id == tenant_id, UserBankAccount.user_id == user_id))
    opts = [{"key": "wallet", "label": METHOD_FA["wallet"], "available": True, "detail": "پس از تأیید مالی، فوری در کیف پول شما قابل استفاده است."}]
    if bank is not None and bank.sheba:
        opts.append({"key": "bank_transfer", "label": METHOD_FA["bank_transfer"], "available": True,
                     "detail": f"به نام {bank.holder_name}", "sheba_masked": mask_sheba(bank.sheba), "verified": bank.status == "verified"})
    else:
        opts.append({"key": "bank_transfer", "label": METHOD_FA["bank_transfer"], "available": False,
                     "detail": "ابتدا شمارهٔ شبای خود را در «پروفایل و مسافران» ثبت کنید."})
    opts.append({"key": "gateway", "label": METHOD_FA["gateway"], "available": False,
                 "detail": "درگاه پرداخت متصل، برگشت خودکار وجه به کارت را پشتیبانی نمی‌کند."})
    return opts


def destination_snapshot(db: Session, *, tenant_id: int, user_id: int, destination: str) -> dict:
    """Validates the chosen destination; raises HTTP 409 when it is not available for this customer."""
    opt = next((o for o in destination_options(db, tenant_id=tenant_id, user_id=user_id) if o["key"] == destination), None)
    if opt is None or not opt["available"]:
        raise HTTPException(409, "این مقصد وجه برای حساب شما در دسترس نیست" + (f": {opt['detail']}" if opt else ""))
    if destination == "bank_transfer":
        from .commerce import UserBankAccount
        bank = db.scalar(select(UserBankAccount).where(UserBankAccount.tenant_id == tenant_id, UserBankAccount.user_id == user_id))
        return {"holder_name": bank.holder_name, "sheba_masked": mask_sheba(bank.sheba), "bank": bank.sheba_bank, "verified": bank.status == "verified"}
    return {}


def revert_targets() -> set[str]:
    return {"confirmed", "issued", "reserved", "awaiting_payment"}


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


# ============================================================================ API
class RequestActionIn(BaseModel):
    action: str = Field(pattern="^(start_review|request_supplier|record_supplier_response|need_customer|approve|reject|close|note)$")
    reason: Optional[str] = Field(default=None, max_length=2000)
    penalty_mode: Optional[str] = Field(default=None, pattern="^(policy|manual)$")
    penalty_amount: Optional[int] = Field(default=None, ge=0)
    carrier_cancel: bool = False
    supplier_reference: Optional[str] = Field(default=None, max_length=120)
    supplier_refundable_amount: Optional[int] = Field(default=None, ge=0)
    supplier_penalty_amount: Optional[int] = Field(default=None, ge=0)


class AssignIn(BaseModel):
    user_id: Optional[int] = Field(default=None, gt=0)


class CustomerReplyIn(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


class RefundPrepareIn(BaseModel):
    method: str = Field(pattern="^(wallet|bank_transfer|gateway)$")
    bank_reference: Optional[str] = Field(default=None, min_length=4, max_length=80)
    paid_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=1000)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class ReconLinkIn(BaseModel):
    target_type: str = Field(pattern="^(payment|reservation)$")
    target_id: str = Field(min_length=36, max_length=36)
    reason: str = Field(min_length=5, max_length=1000)


class ReconResolveIn(BaseModel):
    resolution_type: str = Field(pattern="^(refund_customer|book_reservation|gateway_fee|bank_error|duplicate|other)$")
    reason: str = Field(min_length=5, max_length=2000)


RESOLUTION_FA = {"refund_customer": "برگشت به مشتری", "book_reservation": "ثبت رزرو", "gateway_fee": "کارمزد درگاه",
                 "bank_error": "اشتباه بانک", "duplicate": "تراکنش تکراری", "other": "سایر"}


def after_sales_router(get_db, current_user, role_has_permission, User, audit, quote_fn: Callable) -> APIRouter:
    router = APIRouter(tags=["after-sales"])

    def need(permission: str):
        def guard(user=Depends(current_user)):
            if not role_has_permission(user.role, permission):
                raise HTTPException(403, "مجوز لازم برای این اقدام وجود ندارد")
            return user
        return guard

    ops_user = need("service_request:decide")
    fin_user = need("refund:manage")
    recon_user = need("reconciliation:manage")

    # ------------------------------------------------------------------ shared readers
    def _req(db: Session, tenant_id: int, request_id: str, lock: bool = False) -> m.BookingServiceRequest:
        q = select(m.BookingServiceRequest).where(m.BookingServiceRequest.id == request_id, m.BookingServiceRequest.tenant_id == tenant_id)
        row = db.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise HTTPException(404, "درخواست وجود ندارد")
        return row

    def _reservation(db: Session, tenant_id: int, reservation_id: str, lock: bool = False) -> m.Reservation:
        q = select(m.Reservation).where(m.Reservation.id == reservation_id, m.Reservation.tenant_id == tenant_id)
        row = db.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise HTTPException(404, "رزرو وجود ندارد")
        return row

    def _own_req(db: Session, user, request_id: str, lock: bool = False) -> tuple[m.BookingServiceRequest, m.Reservation]:
        req = _req(db, user.tenant_id, request_id, lock)
        res = _reservation(db, user.tenant_id, req.reservation_id)
        if res.user_id != user.id:
            raise HTTPException(404, "درخواست وجود ندارد")
        return req, res

    def _names(db: Session, ids) -> dict:
        ids = {i for i in ids if i}
        return {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}

    def _captured_payment(db: Session, res: m.Reservation, lock: bool = False) -> Optional[m.PaymentIntent]:
        q = select(m.PaymentIntent).where(m.PaymentIntent.tenant_id == res.tenant_id, m.PaymentIntent.reservation_id == res.id,
                                          m.PaymentIntent.status.in_(("captured", "refunded"))).order_by(m.PaymentIntent.created_at)
        return db.scalar(q.with_for_update() if lock else q)

    def _claimed(db: Session, payment: m.PaymentIntent) -> int:
        return int(db.scalar(select(func.coalesce(func.sum(m.RefundRecord.amount), 0)).where(
            m.RefundRecord.tenant_id == payment.tenant_id, m.RefundRecord.payment_intent_id == payment.id,
            m.RefundRecord.status.in_(("requested", "pending_review") + REFUND_OPEN))) or 0)

    def _transition(db: Session, req: m.BookingServiceRequest, h: ServiceRequestHandling, action: str, user, actor_kind: str,
                    note: Optional[str] = None, payload: Optional[dict] = None, command_id: Optional[str] = None, internal: bool = False) -> None:
        try:
            target = next_status(req.status, action)
        except InvalidTransition as exc:
            raise HTTPException(409, f"این اقدام در وضعیت «{STATUS_FA.get(req.status, req.status)}» مجاز نیست") from exc
        prev = req.status
        req.status = target
        h.status_since = utcnow()
        record_event(db, req=req, event_type=action, actor_kind=actor_kind, actor_id=getattr(user, "id", None), from_status=prev, to_status=target,
                     note=note, payload=payload, command_id=command_id, internal=internal)

    def _notify(db: Session, req: m.BookingServiceRequest, h: ServiceRequestHandling, title: str, message: str) -> None:
        db.add(m.NotificationRecord(tenant_id=req.tenant_id, user_id=h.customer_user_id, topic="service_request", title=title, message=message,
                                    deep_link=f"/account/refunds/{req.id}"))
        db.add(m.OutboxEvent(tenant_id=req.tenant_id, aggregate_type="service_request", aggregate_id=req.id, event_type=f"service_request.{req.status}",
                             payload_json=json.dumps({"request_id": req.id, "status": req.status}), correlation_id=str(uuid.uuid4()),
                             idempotency_key=f"sr-notify:{req.id}:{uuid.uuid4()}"))

    def _revert_reservation(db: Session, req: m.BookingServiceRequest, h: ServiceRequestHandling, user, key: str) -> None:
        res = _reservation(db, req.tenant_id, req.reservation_id, lock=True)
        if res.status not in {"cancel_requested", "change_requested", "refund_requested"}:
            return
        target = h.prior_reservation_status if h.prior_reservation_status in revert_targets() else "confirmed"
        try:
            m.transition_reservation(db, res, target, getattr(user, "id", None), f"{key}:revert")
        except ValueError as exc:
            raise HTTPException(409, "بازگرداندن وضعیت رزرو ممکن نیست") from exc

    def _timeline(db: Session, req: m.BookingServiceRequest, h: ServiceRequestHandling, customer_view: bool) -> dict:
        q = select(ServiceRequestEvent).where(ServiceRequestEvent.tenant_id == req.tenant_id, ServiceRequestEvent.request_id == req.id)
        if customer_view:
            q = q.where(ServiceRequestEvent.internal.is_(False), ServiceRequestEvent.event_type.notin_(CUSTOMER_HIDDEN_EVENTS))
        events = db.scalars(q.order_by(ServiceRequestEvent.created_at, ServiceRequestEvent.id)).all()
        names = {} if customer_view else _names(db, [e.actor_id for e in events])
        steps = [{"id": e.id, "type": e.event_type, "title": EVENT_FA.get(e.event_type, e.event_type), "actor_kind": e.actor_kind,
                  "actor": ACTOR_FA.get(e.actor_kind, e.actor_kind) if customer_view else (names.get(e.actor_id) or ACTOR_FA.get(e.actor_kind)),
                  "at": _iso(e.created_at), "to_status": e.to_status, "note": e.note,
                  "internal": e.internal} for e in events]
        return {"steps": steps, "next": next_step(req.status, h.status_since)}

    def _refund_view(db: Session, refund: Optional[m.RefundRecord], ex: Optional[RefundExecution], finance: bool = False) -> Optional[dict]:
        if refund is None:
            return None
        out = {"id": refund.id, "status": refund.status, "amount": refund.amount, "currency": "IRR",
               "destination": ex.destination if ex else None, "destination_label": METHOD_FA.get(ex.destination) if ex else None,
               "method": ex.method if ex else None, "bank_reference": ex.bank_reference if ex and refund.status == "succeeded" else None,
               "paid_at": _iso(ex.paid_at) if ex else None}
        if finance and ex:
            names = _names(db, [ex.prepared_by_user_id, ex.approved_by_user_id])
            out.update({"destination_detail": json.loads(ex.destination_json or "{}"), "penalty_amount": ex.penalty_amount, "paid_total": ex.paid_total,
                        "breakdown": json.loads(ex.breakdown_json or "{}"), "prepared_by": names.get(ex.prepared_by_user_id), "prepared_by_user_id": ex.prepared_by_user_id,
                        "prepared_at": _iso(ex.prepared_at), "approved_by": names.get(ex.approved_by_user_id), "approved_at": _iso(ex.approved_at),
                        "pending_bank_reference": ex.bank_reference, "note": ex.note})
        return out

    def _request_out(db: Session, req: m.BookingServiceRequest, res: m.Reservation, h: ServiceRequestHandling, customer_view: bool) -> dict:
        refund = db.get(m.RefundRecord, h.refund_id) if h.refund_id else None
        ex = db.scalar(select(RefundExecution).where(RefundExecution.tenant_id == req.tenant_id, RefundExecution.refund_id == refund.id)) if refund else None
        quote = json.loads(req.quote_snapshot_json or "{}")
        out = {"id": req.id, "request_type": req.request_type, "request_type_fa": TYPE_FA.get(req.request_type, req.request_type),
               "status": req.status, "status_fa": STATUS_FA.get(req.status, req.status), "reason": req.reason, "created_at": _iso(req.created_at),
               "reservation": {"id": res.id, "booking_reference": res.booking_reference, "service_type": res.service_type, "status": res.status},
               "quote": quote if quote.get("policy_verified") else None, "refund_destination": h.refund_destination,
               "refund_destination_label": METHOD_FA.get(h.refund_destination or ""), "penalty_amount": h.penalty_amount,
               "penalty_source": h.penalty_source, "approved_amount": h.approved_amount, "decision_reason": h.decision_reason,
               "customer_question": h.customer_question if req.status == "needs_customer" else None,
               "refund": _refund_view(db, refund, ex), "next": next_step(req.status, h.status_since),
               "can_withdraw": req.status == "submitted", "can_reply": req.status == "needs_customer"}
        if not customer_view:
            names = _names(db, [h.assigned_to_user_id, h.decided_by_user_id, h.customer_user_id])
            out.update({"assigned_to_user_id": h.assigned_to_user_id, "assigned_to": names.get(h.assigned_to_user_id),
                        "decided_by": names.get(h.decided_by_user_id), "customer_name": names.get(h.customer_user_id),
                        "supplier": json.loads(h.supplier_json or "{}"), "destination_detail": json.loads(h.destination_json or "{}")})
        return out

    # ------------------------------------------------------------------ customer
    @router.get("/reservations/{reservation_id}/after-sales/options")
    def options(reservation_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        """Cancel wizard step 2/3 (C-03a): server-computed penalty preview and the refund destinations this customer can use."""
        res = _reservation(db, user.tenant_id, reservation_id)
        if res.user_id != user.id:
            raise HTTPException(404, "رزرو در این حساب وجود ندارد")
        quote = quote_fn(res)
        payment = _captured_payment(db, res)
        paid_remaining = (payment.captured_amount - payment.refunded_amount - _claimed(db, payment)) if payment else 0
        open_req = db.scalar(select(m.BookingServiceRequest.id).where(m.BookingServiceRequest.tenant_id == user.tenant_id,
                                                                     m.BookingServiceRequest.reservation_id == res.id,
                                                                     m.BookingServiceRequest.status.in_(OPEN_STATUSES)))
        cancellable = res.status in {"reserved", "awaiting_payment", "confirmed", "issued"} and open_req is None
        why = None if cancellable else ("درخواست قبلی این رزرو هنوز باز است." if open_req else "در وضعیت فعلی رزرو، درخواست لغو یا تغییر ممکن نیست.")
        preview = None
        if quote:
            refundable = min(int(quote["refundable_amount"]), max(paid_remaining, 0)) if payment else 0
            preview = {"total_amount": quote["total_amount"], "penalty_amount": quote["penalty_amount"], "refundable_amount": refundable,
                       "paid_amount": payment.captured_amount if payment else 0, "policy_source": quote["policy_source"], "currency": "IRR",
                       "computed_at": utcnow().isoformat(), "valid_minutes": 15}
        return {"reservation_id": res.id, "booking_reference": res.booking_reference, "status": res.status, "cancellable": cancellable,
                "not_cancellable_reason": why, "open_request_id": open_req, "policy_verified": quote is not None, "preview": preview,
                "requires_review_reason": None if quote else "قوانین لغو این رزرو تأییدشده ثبت نشده است؛ جریمه را کارشناس پس از بررسی اعلام می‌کند.",
                "destinations": destination_options(db, tenant_id=user.tenant_id, user_id=user.id)}

    @router.get("/me/service-requests")
    def my_requests(status: Optional[str] = Query(default=None, pattern="^(open|closed)$"), limit: int = Query(default=50, ge=1, le=100),
                    offset: int = Query(default=0, ge=0), user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        q = select(m.BookingServiceRequest, m.Reservation).join(m.Reservation, m.Reservation.id == m.BookingServiceRequest.reservation_id).where(
            m.BookingServiceRequest.tenant_id == user.tenant_id, m.Reservation.tenant_id == user.tenant_id, m.Reservation.user_id == user.id)
        if status == "open":
            q = q.where(m.BookingServiceRequest.status.in_(OPEN_STATUSES))
        elif status == "closed":
            q = q.where(m.BookingServiceRequest.status.in_(TERMINAL_STATUSES))
        rows = db.execute(q.order_by(m.BookingServiceRequest.created_at.desc()).offset(offset).limit(limit + 1)).all()
        items = [_request_out(db, req, res, handling_for(db, req), True) for req, res in rows[:limit]]
        db.commit()
        return {"items": items, "has_more": len(rows) > limit}

    @router.get("/me/service-requests/{request_id}")
    def my_request(request_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        req, res = _own_req(db, user, request_id)
        h = handling_for(db, req)
        out = {**_request_out(db, req, res, h, True), "timeline": _timeline(db, req, h, True)}
        db.commit()
        return out

    @router.post("/me/service-requests/{request_id}/withdraw")
    def withdraw(request_id: str, user=Depends(current_user), db: Session = Depends(get_db),
                 idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
        req, res = _own_req(db, user, request_id, lock=True)
        h = handling_for(db, req)
        if req.status == "withdrawn":
            return _request_out(db, req, res, h, True)
        _transition(db, req, h, "withdraw", user, "customer", command_id=f"sr-withdraw:{req.id}")
        _revert_reservation(db, req, h, user, f"sr-withdraw:{req.id}")
        db.commit()
        return _request_out(db, req, res, h, True)

    @router.post("/me/service-requests/{request_id}/reply")
    def reply(request_id: str, data: CustomerReplyIn, user=Depends(current_user), db: Session = Depends(get_db),
              idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
        req, res = _own_req(db, user, request_id, lock=True)
        h = handling_for(db, req)
        prior = db.scalar(select(ServiceRequestEvent).where(ServiceRequestEvent.tenant_id == user.tenant_id, ServiceRequestEvent.command_id == f"sr-reply:{idempotency_key}"))
        if prior:
            if prior.request_id != req.id or prior.note != data.message.strip():
                raise HTTPException(409, "کلید تکرار برای درخواست دیگری استفاده شده است")
            return _request_out(db, req, res, h, True)
        _transition(db, req, h, "customer_reply", user, "customer", note=data.message.strip(), command_id=f"sr-reply:{idempotency_key}")
        h.customer_question = None
        db.commit()
        return _request_out(db, req, res, h, True)

    @router.get("/me/refunds")
    def my_refunds(user=Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
        rows = db.execute(select(m.RefundRecord, m.PaymentIntent).join(m.PaymentIntent, m.PaymentIntent.id == m.RefundRecord.payment_intent_id).where(
            m.RefundRecord.tenant_id == user.tenant_id, m.PaymentIntent.tenant_id == user.tenant_id, m.PaymentIntent.user_id == user.id)
            .order_by(m.RefundRecord.created_at.desc())).all()
        out = []
        for refund, payment in rows:
            ex = db.scalar(select(RefundExecution).where(RefundExecution.tenant_id == user.tenant_id, RefundExecution.refund_id == refund.id))
            view = _refund_view(db, refund, ex)
            view.update({"reservation_id": payment.reservation_id, "request_id": ex.request_id if ex else None, "created_at": _iso(refund.created_at)})
            out.append(view)
        return out

    @router.get("/me/wallets/{wallet_id}/history")
    def wallet_history(wallet_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        w = db.scalar(select(m.Wallet).where(m.Wallet.id == wallet_id, m.Wallet.tenant_id == user.tenant_id, m.Wallet.owner_type == "user",
                                             m.Wallet.owner_reference == str(user.id)))
        if w is None:
            raise HTTPException(404, "کیف پول در این حساب وجود ندارد")
        rows = db.execute(select(m.FinancialLedgerEntry, m.Reservation.booking_reference).outerjoin(
            m.Reservation, (m.Reservation.id == m.FinancialLedgerEntry.reservation_id) & (m.Reservation.tenant_id == user.tenant_id)).where(
            m.FinancialLedgerEntry.tenant_id == user.tenant_id, m.FinancialLedgerEntry.wallet_id == w.id).order_by(m.FinancialLedgerEntry.created_at.desc()).limit(200)).all()
        kind = {"allocate": "واریز", "reserve": "رزرو برای خرید", "capture": "برداشت برای خرید", "release": "آزادسازی", "reverse_capture": "برگشت خرید"}
        items = [{"id": e.id, "entry_type": e.entry_type, "label": ("استرداد" if e.command_id.startswith("refund-pay:") else kind.get(e.entry_type, e.entry_type)),
                  "amount": e.amount, "direction": "in" if e.entry_type in {"allocate", "release", "reverse_capture"} else "out",
                  "booking_reference": ref, "at": _iso(e.created_at)} for e, ref in rows]
        return {"wallet_id": w.id, "currency": w.currency, **m.wallet_balances(db, tenant_id=user.tenant_id, wallet_id=w.id), "items": items}

    @router.get("/reservations/{reservation_id}/timeline")
    def reservation_timeline(reservation_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        res = _reservation(db, user.tenant_id, reservation_id)
        if res.user_id != user.id:
            raise HTTPException(404, "رزرو در این حساب وجود ندارد")
        hist = db.scalars(select(m.BookingStatusHistory).where(m.BookingStatusHistory.tenant_id == user.tenant_id, m.BookingStatusHistory.reservation_id == res.id)
                          .order_by(m.BookingStatusHistory.created_at)).all()
        steps = [{"kind": "booking", "title": m.TRIP_STATUS_TITLES.get(h.to_status, h.to_status), "to_status": h.to_status,
                  "actor": "شما" if h.actor_id == user.id else "سامانه یا کارشناس", "at": _iso(h.created_at)} for h in hist]
        reqs = db.scalars(select(m.BookingServiceRequest).where(m.BookingServiceRequest.tenant_id == user.tenant_id, m.BookingServiceRequest.reservation_id == res.id)
                          .order_by(m.BookingServiceRequest.created_at)).all()
        requests = []
        for req in reqs:
            h = handling_for(db, req)
            requests.append({**_request_out(db, req, res, h, True), "timeline": _timeline(db, req, h, True)})
        db.commit()
        return {"reservation_id": res.id, "booking_reference": res.booking_reference, "status": res.status, "steps": steps, "requests": requests}

    # ------------------------------------------------------------------ ops (OPS-02 / OPS-03)
    @router.get("/ops/queues/service_requests")
    def ops_queue(status: Optional[str] = Query(default=None, pattern="^(open|closed|" + "|".join(REQUEST_STATUSES) + ")$"),
                  assignee: Optional[str] = Query(default=None, pattern="^(me|unassigned|any)$"), request_type: Optional[str] = Query(default=None, pattern="^(cancel|change|refund)$"),
                  limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), user=Depends(ops_user), db: Session = Depends(get_db)) -> dict:
        q = select(m.BookingServiceRequest, m.Reservation).join(m.Reservation, m.Reservation.id == m.BookingServiceRequest.reservation_id).where(
            m.BookingServiceRequest.tenant_id == user.tenant_id, m.Reservation.tenant_id == user.tenant_id)
        if status in (None, "open"):
            q = q.where(m.BookingServiceRequest.status.in_(OPEN_STATUSES))
        elif status == "closed":
            q = q.where(m.BookingServiceRequest.status.in_(TERMINAL_STATUSES))
        else:
            q = q.where(m.BookingServiceRequest.status == status)
        if request_type:
            q = q.where(m.BookingServiceRequest.request_type == request_type)
        if assignee in ("me", "unassigned"):
            q = q.join(ServiceRequestHandling, (ServiceRequestHandling.request_id == m.BookingServiceRequest.id) & (ServiceRequestHandling.tenant_id == user.tenant_id))
            q = q.where(ServiceRequestHandling.assigned_to_user_id == user.id) if assignee == "me" else q.where(ServiceRequestHandling.assigned_to_user_id.is_(None))
        rows = db.execute(q.order_by(m.BookingServiceRequest.created_at).offset(offset).limit(limit + 1)).all()
        items = []
        for req, res in rows[:limit]:
            h = handling_for(db, req)
            o = _request_out(db, req, res, h, False)
            price = json.loads(res.price_snapshot_json or "{}")
            o["amount"] = price.get("total_amount") if isinstance(price.get("total_amount"), int) else None
            o["severity"] = "HIGH" if req.request_type in ("cancel", "refund") else "MEDIUM"
            items.append(o)
        items.sort(key=lambda i: (i["next"] is None, i["next"]["eta"] if i["next"] and i["next"]["eta"] else "9999"))
        counts = dict(db.execute(select(m.BookingServiceRequest.status, func.count()).where(m.BookingServiceRequest.tenant_id == user.tenant_id)
                                 .group_by(m.BookingServiceRequest.status)).all())
        db.commit()
        return {"items": items, "has_more": len(rows) > limit, "counts": counts, "generated_at": utcnow().isoformat()}

    @router.get("/ops/service-requests/{request_id}")
    def ops_detail(request_id: str, user=Depends(ops_user), db: Session = Depends(get_db)) -> dict:
        req = _req(db, user.tenant_id, request_id)
        res = _reservation(db, user.tenant_id, req.reservation_id)
        h = handling_for(db, req)
        payment = _captured_payment(db, res)
        current = quote_fn(res)
        pb = db.scalar(select(m.PriceBreakdown).where(m.PriceBreakdown.tenant_id == user.tenant_id, m.PriceBreakdown.booking_id == res.id))
        # §3.3 ops view: customer total, supplier parts, service fee, penalty policy; never margin/commission/net revenue.
        money_view = {"customer_total": pb.total_selling_price, "supplier_amount": pb.supplier_net_rate_irr, "service_fee": pb.service_fee,
                      "taxes": {"vat": pb.vat, "airport_tax": pb.airport_tax, "i6_tax": pb.i6_tax, "red_crescent": pb.red_crescent, "other_taxes": pb.other_taxes}} if pb else None
        paid_remaining = (payment.captured_amount - payment.refunded_amount - _claimed(db, payment)) if payment else 0
        out = {**_request_out(db, req, res, h, False), "timeline": _timeline(db, req, h, False),
               "policy_at_booking": json.loads(res.policy_at_booking_json or "{}"), "current_quote": current,
               "payment": {"id": payment.id, "captured_amount": payment.captured_amount, "refunded_amount": payment.refunded_amount,
                           "refundable_remaining": max(paid_remaining, 0), "provider_reference": payment.provider_reference} if payment else None,
               "money": money_view, "can_override": role_has_permission(user.role, "refund:override"),
               "allowed_actions": [a for a in OPS_ACTIONS if req.status in TRANSITIONS[a][0]] + ["note"]}
        db.commit()
        return out

    @router.post("/ops/queues/service_requests/items/{request_id}/assign")
    def assign(request_id: str, data: AssignIn, user=Depends(ops_user), db: Session = Depends(get_db)) -> dict:
        req = _req(db, user.tenant_id, request_id, lock=True)
        if req.status in TERMINAL_STATUSES:
            raise HTTPException(409, "درخواست بسته‌شده قابل تخصیص نیست")
        h = handling_for(db, req)
        target_id = data.user_id or user.id
        target = db.scalar(select(User).where(User.id == target_id, User.tenant_id == user.tenant_id))
        if target is None or not role_has_permission(target.role, "service_request:decide"):
            raise HTTPException(422, "این کاربر کارشناس رسیدگی در این مجموعه نیست")
        if h.assigned_to_user_id != target.id:
            prev = h.assigned_to_user_id
            h.assigned_to_user_id = target.id
            record_event(db, req=req, event_type="assign", actor_kind="ops", actor_id=user.id, note=target.name, internal=True,
                         payload={"from": prev, "to": target.id})
            audit(db, user, "service_request.assign", "service_request", {"request_id": req.id, "from": prev, "to": target.id})
        db.commit()
        return {"id": req.id, "assigned_to_user_id": h.assigned_to_user_id, "assigned_to": target.name}

    @router.post("/backoffice/booking-requests/{request_id}/actions")
    def ops_action(request_id: str, data: RequestActionIn, user=Depends(ops_user), db: Session = Depends(get_db),
                   idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
        request_hash = _hash({"request_id": request_id, **data.model_dump()})
        prior = db.scalar(select(m.IdempotencyKey).where(m.IdempotencyKey.tenant_id == user.tenant_id, m.IdempotencyKey.scope == "sr.action", m.IdempotencyKey.key == idempotency_key))
        if prior:
            if prior.request_hash != request_hash:
                raise HTTPException(409, "کلید تکرار برای اقدام دیگری استفاده شده است")
            return json.loads(prior.response_json or "{}")
        req = _req(db, user.tenant_id, request_id, lock=True)
        res = _reservation(db, user.tenant_id, req.reservation_id, lock=True)
        h = handling_for(db, req)
        reason = (data.reason or "").strip() or None
        key = f"sr-action:{idempotency_key}"
        a = data.action
        if a == "note":
            if not reason:
                raise HTTPException(422, "متن یادداشت لازم است")
            record_event(db, req=req, event_type="note", actor_kind="ops", actor_id=user.id, note=reason, internal=True, command_id=key)
        elif a == "start_review":
            _transition(db, req, h, a, user, "ops", command_id=key)
            _notify(db, req, h, "بررسی درخواست شما آغاز شد", "کارشناس بررسی درخواست شما را شروع کرد؛ لغو یا استرداد هنوز تأیید نشده است.")
        elif a == "request_supplier":
            _transition(db, req, h, a, user, "ops", note=reason, payload={"supplier_reference": data.supplier_reference}, command_id=key)
            h.supplier_json = json.dumps({**json.loads(h.supplier_json or "{}"), "requested_at": utcnow().isoformat(), "reference": data.supplier_reference}, ensure_ascii=False)
            _notify(db, req, h, "درخواست شما برای تأمین‌کننده ارسال شد", "منتظر پاسخ تأمین‌کننده هستیم.")
        elif a == "record_supplier_response":
            resp = {"refundable_amount": data.supplier_refundable_amount, "penalty_amount": data.supplier_penalty_amount, "reference": data.supplier_reference,
                    "responded_at": utcnow().isoformat(), "note": reason}
            h.supplier_json = json.dumps({**json.loads(h.supplier_json or "{}"), "response": resp}, ensure_ascii=False)
            _transition(db, req, h, a, user, "ops", note=reason, payload=resp, command_id=key)
        elif a == "need_customer":
            if not reason:
                raise HTTPException(422, "متن پرسش از مشتری لازم است")
            _transition(db, req, h, a, user, "ops", note=reason, command_id=key)
            h.customer_question = reason
            _notify(db, req, h, "برای ادامهٔ درخواست، پاسخ شما لازم است", reason)
        elif a == "reject":
            if not reason or len(reason) < 5:
                raise HTTPException(422, "دلیل رد درخواست لازم است")
            if res.status in {"cancelled", "refunded"}:
                raise HTTPException(409, "رزرو قبلاً لغو شده است؛ رد درخواست ممکن نیست. با مبلغ اصلاح‌شده تأیید کنید.")
            _transition(db, req, h, a, user, "ops", note=reason, command_id=key)
            h.decision_reason, h.decided_by_user_id, h.decided_at = reason, user.id, utcnow()
            _revert_reservation(db, req, h, user, key)
            _notify(db, req, h, "درخواست شما رد شد", reason)
        elif a == "close":
            _transition(db, req, h, a, user, "ops", note=reason, command_id=key)
            _notify(db, req, h, "درخواست شما بسته شد", "پرونده‌ی این درخواست بسته شد.")
        elif a == "approve":
            _approve(db, req, res, h, data, reason, user, key)
        audit(db, user, f"service_request.{a}", "service_request", {"request_id": req.id, "status": req.status, "reason": reason})
        response = {**_request_out(db, req, res, h, False), "allowed_actions": [x for x in OPS_ACTIONS if req.status in TRANSITIONS[x][0]] + ["note"]}
        db.add(m.IdempotencyKey(tenant_id=user.tenant_id, scope="sr.action", key=idempotency_key, request_hash=request_hash, response_json=json.dumps(response, ensure_ascii=False)))
        db.commit()
        return response

    def _approve(db: Session, req, res, h, data: RequestActionIn, reason, user, key) -> None:
        if req.request_type == "change":
            _transition(db, req, h, "approve", user, "ops", note=reason, command_id=key)
            h.decision_reason, h.decided_by_user_id, h.decided_at = reason, user.id, utcnow()
            if res.status == "change_requested":
                m.transition_reservation(db, res, "changed", user.id, f"{key}:changed")
            _notify(db, req, h, "درخواست تغییر شما تأیید شد", reason or "تغییر رزرو ثبت شد.")
            return
        quote = quote_fn(res)
        mode = data.penalty_mode or ("policy" if quote else None)
        if mode is None:
            raise HTTPException(422, "قوانین لغو تأییدشده ندارد؛ جریمه را دستی و با دلیل وارد کنید")
        payment = _captured_payment(db, res, lock=True)
        paid_remaining = max((payment.captured_amount - payment.refunded_amount - _claimed(db, payment)) if payment else 0, 0)
        if mode == "policy":
            if quote is None:
                raise HTTPException(409, "قوانین لغو این رزرو تأییدشده نیست؛ حالت دستی با دلیل را انتخاب کنید")
            refund_amount = min(int(quote["refundable_amount"]), paid_remaining)
            penalty = paid_remaining - refund_amount
        else:
            if data.penalty_amount is None or not reason or len(reason) < 5:
                raise HTTPException(422, "در حالت دستی مبلغ جریمه و دلیل لازم است")
            try:
                refund_amount = refund_amount_for(paid_remaining, data.penalty_amount)
            except ValueError as exc:
                raise HTTPException(422, "جریمه باید بین صفر و مبلغ پرداخت‌شده باشد") from exc
            penalty = data.penalty_amount
            ceiling = int(quote["refundable_amount"]) if quote else None
            if (ceiling is None or refund_amount > ceiling) and refund_amount > 0 and not role_has_permission(user.role, "refund:override"):
                raise HTTPException(403, "مبلغ استرداد بیشتر از محاسبهٔ قوانین تأییدشده است و تأیید سرپرست (refund:override) لازم دارد")
        _transition(db, req, h, "approve", user, "ops", note=reason, payload={"penalty_mode": mode, "penalty_amount": penalty, "refund_amount": refund_amount}, command_id=key)
        h.penalty_amount, h.penalty_source, h.approved_amount = penalty, "verified_policy" if mode == "policy" else "manual", refund_amount
        h.decision_reason, h.decided_by_user_id, h.decided_at = reason, user.id, utcnow()
        if req.request_type == "cancel" and res.status == "cancel_requested":
            m.transition_reservation(db, res, "cancelled", user.id, f"{key}:cancelled")
        if refund_amount <= 0 or payment is None:
            _notify(db, req, h, "درخواست شما تأیید شد", "طبق قوانین لغو، مبلغی برای استرداد باقی نمی‌ماند." if payment else "پرداختی برای استرداد ثبت نشده است.")
            return
        pb = db.scalar(select(m.PriceBreakdown).where(m.PriceBreakdown.tenant_id == req.tenant_id, m.PriceBreakdown.booking_id == res.id))
        breakdown = vat_reversal(refund_amount=refund_amount, customer_total=pb.total_selling_price if pb else None, service_fee=pb.service_fee if pb else None,
                                 platform_markup=pb.platform_markup if pb else None, agency_commission=pb.supplier_commission if pb else None)
        breakdown["carrier_cancel"] = data.carrier_cancel
        refund = m.RefundRecord(tenant_id=req.tenant_id, payment_intent_id=payment.id, command_id=f"sr-refund:{req.id}:{uuid.uuid4()}", amount=refund_amount, status="pending_finance")
        db.add(refund); db.flush()
        db.add(RefundExecution(tenant_id=req.tenant_id, refund_id=refund.id, request_id=req.id, reservation_id=res.id, customer_user_id=h.customer_user_id,
                               destination=h.refund_destination or "wallet", destination_json=h.destination_json or "{}", penalty_amount=penalty,
                               paid_total=paid_remaining, breakdown_json=json.dumps(breakdown, sort_keys=True)))
        h.refund_id = refund.id
        _transition(db, req, h, "queue_refund", None, "system", payload={"refund_id": refund.id, "amount": refund_amount}, command_id=f"{key}:queue")
        _notify(db, req, h, "درخواست شما تأیید شد و به صف پرداخت رفت", f"مبلغ {refund_amount:,} ریال پس از تأیید دو کارشناس مالی پرداخت می‌شود.")

    # ------------------------------------------------------------------ finance (FIN-02 / FIN-02a)
    def _refund_row(db: Session, tenant_id: int, refund_id: str, lock: bool = False) -> tuple[m.RefundRecord, RefundExecution]:
        q = select(m.RefundRecord).where(m.RefundRecord.id == refund_id, m.RefundRecord.tenant_id == tenant_id)
        refund = db.scalar(q.with_for_update() if lock else q)
        ex = db.scalar(select(RefundExecution).where(RefundExecution.tenant_id == tenant_id, RefundExecution.refund_id == refund_id)) if refund else None
        if refund is None or ex is None:
            raise HTTPException(404, "استرداد در صف مالی وجود ندارد")
        return refund, ex

    def _fin_out(db: Session, refund: m.RefundRecord, ex: RefundExecution, detail: bool = False) -> dict:
        res = db.get(m.Reservation, ex.reservation_id)
        names = _names(db, [ex.customer_user_id])
        req = db.get(m.BookingServiceRequest, ex.request_id)
        h = handling_for(db, req)
        o = {**_refund_view(db, refund, ex, finance=True), "request_id": ex.request_id, "request_type": req.request_type,
             "booking_reference": res.booking_reference if res else None, "reservation_id": ex.reservation_id,
             "customer_name": names.get(ex.customer_user_id), "created_at": _iso(refund.created_at),
             "approved_by_ops": _names(db, [h.decided_by_user_id]).get(h.decided_by_user_id), "penalty_source": h.penalty_source,
             "age_hours": int((utcnow() - (_aw(refund.created_at) or utcnow())).total_seconds() // 3600)}
        if detail:
            o["journal"] = [{"account": j.account, "debit": j.debit, "credit": j.credit, "memo": j.memo} for j in db.scalars(
                select(RefundJournalLine).where(RefundJournalLine.tenant_id == refund.tenant_id, RefundJournalLine.refund_id == refund.id).order_by(RefundJournalLine.created_at, RefundJournalLine.id)).all()]
            doc = db.scalar(select(TaxReturnDocument).where(TaxReturnDocument.tenant_id == refund.tenant_id, TaxReturnDocument.refund_id == refund.id))
            o["tax_document"] = {"id": doc.id, "subject": doc.subject, "basis": doc.basis, "status": doc.status, "lines": json.loads(doc.lines_json),
                                 "totals": json.loads(doc.totals_json), "due_at": _iso(doc.due_at)} if doc else None
            o["timeline"] = _timeline(db, req, h, False)
            o["dual_control"] = {"rule": "two_person_always", "maker_cannot_approve": True}
        return o

    @router.get("/finance/refunds")
    def fin_queue(status: Optional[str] = Query(default="open", pattern="^(open|pending_finance|awaiting_approval|succeeded|returned|all)$"),
                  limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), user=Depends(fin_user), db: Session = Depends(get_db)) -> dict:
        q = select(m.RefundRecord).join(RefundExecution, (RefundExecution.refund_id == m.RefundRecord.id) & (RefundExecution.tenant_id == user.tenant_id)).where(
            m.RefundRecord.tenant_id == user.tenant_id)
        if status == "open":
            q = q.where(m.RefundRecord.status.in_(REFUND_OPEN))
        elif status != "all":
            q = q.where(m.RefundRecord.status == status)
        rows = db.scalars(q.order_by(m.RefundRecord.created_at).offset(offset).limit(limit + 1)).all()
        items = []
        for refund in rows[:limit]:
            _, ex = _refund_row(db, user.tenant_id, refund.id)
            items.append(_fin_out(db, refund, ex))
        totals = db.execute(select(m.RefundRecord.status, func.count(), func.coalesce(func.sum(m.RefundRecord.amount), 0)).join(
            RefundExecution, (RefundExecution.refund_id == m.RefundRecord.id) & (RefundExecution.tenant_id == user.tenant_id)).where(
            m.RefundRecord.tenant_id == user.tenant_id).group_by(m.RefundRecord.status)).all()
        db.commit()
        return {"items": items, "has_more": len(rows) > limit, "summary": {s: {"count": c, "amount": int(a)} for s, c, a in totals}, "me": user.id}

    @router.get("/finance/refunds/{refund_id}")
    def fin_detail(refund_id: str, user=Depends(fin_user), db: Session = Depends(get_db)) -> dict:
        refund, ex = _refund_row(db, user.tenant_id, refund_id)
        out = _fin_out(db, refund, ex, detail=True)
        out["can_approve"] = refund.status == "awaiting_approval" and ex.prepared_by_user_id != user.id
        out["destinations"] = destination_options(db, tenant_id=user.tenant_id, user_id=ex.customer_user_id)
        db.commit()
        return out

    def _idem(db: Session, user, scope: str, key: str, payload: dict):
        h = _hash(payload)
        prior = db.scalar(select(m.IdempotencyKey).where(m.IdempotencyKey.tenant_id == user.tenant_id, m.IdempotencyKey.scope == scope, m.IdempotencyKey.key == key))
        if prior:
            if prior.request_hash != h:
                raise HTTPException(409, "کلید تکرار برای درخواست دیگری استفاده شده است")
            return h, json.loads(prior.response_json or "{}")
        return h, None

    def _remember(db: Session, user, scope: str, key: str, h: str, response: dict) -> None:
        db.add(m.IdempotencyKey(tenant_id=user.tenant_id, scope=scope, key=key, request_hash=h, response_json=json.dumps(response, ensure_ascii=False, default=str)))

    def _fin_event(db: Session, ex: RefundExecution, event_type: str, user, note: Optional[str], internal: bool = False, payload: Optional[dict] = None, key: Optional[str] = None):
        req = db.get(m.BookingServiceRequest, ex.request_id)
        record_event(db, req=req, event_type=event_type, actor_kind="finance", actor_id=user.id, note=note, internal=internal, payload=payload, command_id=key)

    @router.post("/finance/refunds/{refund_id}/execute")
    def fin_prepare(refund_id: str, data: RefundPrepareIn, user=Depends(fin_user), db: Session = Depends(get_db),
                    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
        """Maker: chooses the method and records the payment details. Money moves only when another finance user approves."""
        h, prior = _idem(db, user, "refund.prepare", idempotency_key, {"refund_id": refund_id, **data.model_dump(mode="json")})
        if prior is not None:
            return prior
        refund, ex = _refund_row(db, user.tenant_id, refund_id, lock=True)
        if data.method == "gateway":
            raise HTTPException(409, "برگشت وجه از درگاه پشتیبانی نمی‌شود؛ کیف پول یا واریز بانکی را انتخاب کنید")
        if data.method == "bank_transfer":
            if not data.bank_reference:
                raise HTTPException(422, "برای واریز بانکی، کد پیگیری پایا/ساتنا لازم است")
            if not json.loads(ex.destination_json or "{}").get("sheba_masked"):
                snap = destination_snapshot(db, tenant_id=user.tenant_id, user_id=ex.customer_user_id, destination="bank_transfer")
                ex.destination_json = json.dumps(snap, ensure_ascii=False)
        try:
            refund.status = next_refund_status(refund.status, "prepare")
        except InvalidTransition as exc:
            raise HTTPException(409, "این استرداد در وضعیت قابل آماده‌سازی نیست") from exc
        ex.method, ex.bank_reference, ex.note = data.method, data.bank_reference, data.note
        ex.paid_at = _aw(data.paid_at) if data.method == "bank_transfer" else None
        ex.destination = data.method
        ex.prepared_by_user_id, ex.prepared_at = user.id, utcnow()
        ex.approved_by_user_id = ex.approved_at = None
        _fin_event(db, ex, "finance_prepare", user, data.note, payload={"method": data.method}, key=f"refund-prepare:{idempotency_key}")
        audit(db, user, "refund.prepare", "refund", {"refund_id": refund.id, "method": data.method, "amount": refund.amount})
        response = _fin_out(db, refund, ex)
        _remember(db, user, "refund.prepare", idempotency_key, h, response)
        db.commit()
        return response

    @router.post("/finance/refunds/{refund_id}/approve")
    def fin_approve(refund_id: str, user=Depends(fin_user), db: Session = Depends(get_db),
                    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
        """Checker: a different finance user approves; the payment is posted once (wallet credit or bank record + journal)."""
        h, prior = _idem(db, user, "refund.approve", idempotency_key, {"refund_id": refund_id})
        if prior is not None:
            return prior
        refund, ex = _refund_row(db, user.tenant_id, refund_id, lock=True)
        if refund.status == "awaiting_approval" and ex.prepared_by_user_id == user.id:
            raise HTTPException(403, "آماده‌کنندهٔ پرداخت نمی‌تواند همان پرداخت را تأیید کند؛ نفر دوم مالی لازم است")
        try:
            refund.status = next_refund_status(refund.status, "approve")
        except InvalidTransition as exc:
            raise HTTPException(409, "این استرداد منتظر تأیید نفر دوم نیست") from exc
        payment = db.scalar(select(m.PaymentIntent).where(m.PaymentIntent.id == refund.payment_intent_id, m.PaymentIntent.tenant_id == user.tenant_id).with_for_update())
        if payment is None or payment.refunded_amount + refund.amount > payment.captured_amount:
            raise HTTPException(409, "مبلغ استرداد از مبلغ پرداخت‌شده بیشتر است")
        now = utcnow()
        pay_key = f"refund-pay:{refund.id}"
        if ex.method == "wallet":
            wallet = db.scalar(select(m.Wallet).where(m.Wallet.tenant_id == user.tenant_id, m.Wallet.owner_type == "user",
                                                      m.Wallet.owner_reference == str(ex.customer_user_id), m.Wallet.currency == "IRR").with_for_update())
            if wallet is None:
                wallet = m.Wallet(tenant_id=user.tenant_id, owner_type="user", owner_reference=str(ex.customer_user_id), currency="IRR"); db.add(wallet); db.flush()
            entry = m.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=wallet.id, command_id=pay_key[:80], entry_type="allocate", amount=refund.amount, reservation_id=ex.reservation_id)
            refund.provider_reference = f"wallet:{entry.id}"
            ex.paid_at = now
            credit_account = "customer_wallets"
        else:
            refund.provider_reference = ex.bank_reference
            ex.paid_at = ex.paid_at or now
            credit_account = "bank"
        db.add_all([
            RefundJournalLine(tenant_id=user.tenant_id, refund_id=refund.id, command_id=f"{pay_key}:dr", account="customer_refunds", debit=refund.amount, credit=0,
                              memo=f"استرداد رزرو {ex.reservation_id}"),
            RefundJournalLine(tenant_id=user.tenant_id, refund_id=refund.id, command_id=f"{pay_key}:cr", account=credit_account, debit=0, credit=refund.amount,
                              memo=METHOD_FA.get(ex.method or "", ex.method or "")),
        ])
        payment.refunded_amount += refund.amount
        if payment.refunded_amount >= payment.captured_amount:
            payment.status = "refunded"
        ex.approved_by_user_id, ex.approved_at = user.id, now
        res = _reservation(db, user.tenant_id, ex.reservation_id, lock=True)
        if res.status in {"cancelled", "refund_requested"}:
            m.transition_reservation(db, res, "refunded", user.id, f"{pay_key}:refunded")
        breakdown = json.loads(ex.breakdown_json or "{}")
        lines = []
        if breakdown.get("basis") == "price_breakdown":
            for code, field in (("AGENCY_COMMISSION", "agency_commission_reversed"), ("PLATFORM_MARKUP", "platform_markup_reversed"), ("SERVICE_FEE", "service_fee_reversed")):
                base = int(breakdown.get(field) or 0)
                if base:
                    lines.append({"code": code, "base_reversed_irr": base, "vat_bps": breakdown["vat_rate_bps"], "vat_irr": vat_of(base, breakdown["vat_rate_bps"])})
        invoice = db.scalar(select(m.Invoice).where(m.Invoice.tenant_id == user.tenant_id, m.Invoice.reservation_id == ex.reservation_id))
        db.add(TaxReturnDocument(tenant_id=user.tenant_id, refund_id=refund.id, reservation_id=ex.reservation_id, licensed_entity_id=res.licensed_entity_id,
                                 ref_invoice_id=invoice.id if invoice else None, basis=breakdown.get("basis", "unavailable"), lines_json=json.dumps(lines),
                                 totals_json=json.dumps({"refund_amount": refund.amount, "vat_base_reversed": breakdown.get("vat_base_reversed"),
                                                         "vat_reversed": breakdown.get("vat_reversed"), "vat_rate_source": breakdown.get("vat_rate_source"),
                                                         "reason": breakdown.get("reason")}),
                                 status="PENDING", due_at=now + timedelta(days=12)))
        req = db.get(m.BookingServiceRequest, ex.request_id)
        hd = handling_for(db, req)
        _transition(db, req, hd, "refund_paid", user, "finance", payload={"refund_id": refund.id, "method": ex.method, "bank_reference": refund.provider_reference if ex.method == "bank_transfer" else None},
                    command_id=f"{pay_key}:event")
        _notify(db, req, hd, "استرداد شما پرداخت شد",
                f"مبلغ {refund.amount:,} ریال " + ("به کیف پول شما واریز شد." if ex.method == "wallet" else f"به حساب بانکی شما واریز شد؛ کد پیگیری: {ex.bank_reference}"))
        db.add(m.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="refund", aggregate_id=refund.id, event_type="refund.succeeded",
                             payload_json=json.dumps({"refund_id": refund.id, "method": ex.method, "amount": refund.amount}), correlation_id=str(uuid.uuid4()), idempotency_key=pay_key))
        audit(db, user, "refund.approve", "refund", {"refund_id": refund.id, "method": ex.method, "amount": refund.amount, "maker": ex.prepared_by_user_id})
        response = _fin_out(db, refund, ex)
        _remember(db, user, "refund.approve", idempotency_key, h, response)
        db.commit()
        return response

    @router.post("/finance/refunds/{refund_id}/decline")
    def fin_decline(refund_id: str, data: ReasonIn, user=Depends(fin_user), db: Session = Depends(get_db)) -> dict:
        refund, ex = _refund_row(db, user.tenant_id, refund_id, lock=True)
        if refund.status == "awaiting_approval" and ex.prepared_by_user_id == user.id:
            raise HTTPException(403, "تصمیم نفر دوم با کاربر دیگری است")
        try:
            refund.status = next_refund_status(refund.status, "decline")
        except InvalidTransition as exc:
            raise HTTPException(409, "این استرداد منتظر تأیید نفر دوم نیست") from exc
        ex.method = ex.bank_reference = ex.paid_at = None
        ex.prepared_by_user_id = ex.prepared_at = None
        _fin_event(db, ex, "finance_decline", user, data.reason, internal=True)
        audit(db, user, "refund.decline", "refund", {"refund_id": refund.id, "reason": data.reason})
        db.commit()
        return _fin_out(db, refund, ex)

    @router.post("/finance/refunds/{refund_id}/return")
    def fin_return(refund_id: str, data: ReasonIn, user=Depends(fin_user), db: Session = Depends(get_db)) -> dict:
        refund, ex = _refund_row(db, user.tenant_id, refund_id, lock=True)
        try:
            refund.status = next_refund_status(refund.status, "return")
        except InvalidTransition as exc:
            raise HTTPException(409, "این استرداد قابل برگشت به عملیات نیست") from exc
        req = _req(db, user.tenant_id, ex.request_id, lock=True)
        hd = handling_for(db, req)
        _transition(db, req, hd, "finance_return", user, "finance", note=data.reason)
        hd.refund_id = None
        audit(db, user, "refund.return", "refund", {"refund_id": refund.id, "reason": data.reason})
        db.commit()
        return _fin_out(db, refund, ex)

    # ------------------------------------------------------------------ reconciliation actions (FIN-04)
    def _recon(db: Session, tenant_id: int, record_id: str) -> m.ReconciliationRecord:
        row = db.scalar(select(m.ReconciliationRecord).where(m.ReconciliationRecord.id == record_id, m.ReconciliationRecord.tenant_id == tenant_id).with_for_update())
        if row is None:
            raise HTTPException(404, "رکورد تطبیق در این مجموعه وجود ندارد")
        return row

    def _trail(row: m.ReconciliationRecord, entry: dict) -> None:
        trail = json.loads(row.audit_trail_json or "[]"); trail.append(entry); row.audit_trail_json = json.dumps(trail, ensure_ascii=False)

    def _recon_out(db: Session, row: m.ReconciliationRecord) -> dict:
        link = db.scalar(select(ReconciliationLink).where(ReconciliationLink.tenant_id == row.tenant_id, ReconciliationLink.record_id == row.id, ReconciliationLink.active.is_(True)))
        return {"id": row.id, "source_type": row.source_type, "source_id": row.source_id, "external_reference": row.external_reference,
                "external_amount": row.external_amount, "currency": row.currency, "status": row.status, "discrepancy_reason": row.discrepancy_reason,
                "resolution_note": row.resolution_note, "matched_at": _iso(row.matched_at), "resolved_at": _iso(row.resolved_at),
                "audit_trail": json.loads(row.audit_trail_json or "[]"),
                "link": {"target_type": link.target_type, "target_id": link.target_id, "reason": link.reason, "linked_at": _iso(link.created_at)} if link else None}

    @router.get("/finance/reconciliation/records")
    def recon_records(status: Optional[str] = Query(default=None, pattern="^(UNMATCHED|MATCHED|DISPUTED|RESOLVED)$"), user=Depends(recon_user), db: Session = Depends(get_db)) -> dict:
        q = select(m.ReconciliationRecord).where(m.ReconciliationRecord.tenant_id == user.tenant_id)
        if status:
            q = q.where(m.ReconciliationRecord.status == status)
        rows = db.scalars(q.order_by(m.ReconciliationRecord.created_at.desc()).limit(200)).all()
        counts = dict(db.execute(select(m.ReconciliationRecord.status, func.count()).where(m.ReconciliationRecord.tenant_id == user.tenant_id).group_by(m.ReconciliationRecord.status)).all())
        return {"items": [_recon_out(db, r) for r in rows], "counts": counts}

    @router.post("/finance/reconciliation/{record_id}/link")
    def recon_link(record_id: str, data: ReconLinkIn, user=Depends(recon_user), db: Session = Depends(get_db)) -> dict:
        row = _recon(db, user.tenant_id, record_id)
        if row.status not in ("DISPUTED", "UNMATCHED"):
            raise HTTPException(409, "فقط مغایرت باز قابل تطبیق دستی است")
        if db.scalar(select(ReconciliationLink.id).where(ReconciliationLink.tenant_id == user.tenant_id, ReconciliationLink.record_id == row.id, ReconciliationLink.active.is_(True))):
            raise HTTPException(409, "این مغایرت قبلاً به منبعی وصل شده است؛ ابتدا اتصال را بردارید")
        if data.target_type == "payment":
            target = db.scalar(select(m.PaymentIntent).where(m.PaymentIntent.id == data.target_id, m.PaymentIntent.tenant_id == user.tenant_id))
            amount = target.captured_amount if target else None
        else:
            target = db.scalar(select(m.Reservation).where(m.Reservation.id == data.target_id, m.Reservation.tenant_id == user.tenant_id))
            snap = json.loads(target.price_snapshot_json or "{}") if target else {}
            amount = snap.get("total_amount") if isinstance(snap.get("total_amount"), int) else None
        if target is None:
            raise HTTPException(404, "پرداخت یا رزرو در این مجموعه وجود ندارد")
        now = utcnow()
        db.add(ReconciliationLink(tenant_id=user.tenant_id, record_id=row.id, target_type=data.target_type, target_id=data.target_id, linked_by_user_id=user.id, reason=data.reason))
        matched = amount is not None and amount == row.external_amount
        prev = row.status
        row.status = "MATCHED" if matched else "DISPUTED"
        row.matched_at = now if matched else row.matched_at
        if not matched:
            row.discrepancy_reason = f"linked {data.target_type} amount {amount}, observed {row.external_amount} {row.currency}"
        _trail(row, {"event": "linked", "actor_id": user.id, "at": now.isoformat(), "target_type": data.target_type, "target_id": data.target_id,
                     "reason": data.reason, "from": prev, "to": row.status})
        audit(db, user, "reconciliation.link", "reconciliation", {"record_id": row.id, "target_type": data.target_type, "target_id": data.target_id, "status": row.status})
        db.commit()
        return _recon_out(db, row)

    @router.post("/finance/reconciliation/{record_id}/unlink")
    def recon_unlink(record_id: str, data: ReasonIn, user=Depends(recon_user), db: Session = Depends(get_db)) -> dict:
        row = _recon(db, user.tenant_id, record_id)
        link = db.scalar(select(ReconciliationLink).where(ReconciliationLink.tenant_id == user.tenant_id, ReconciliationLink.record_id == row.id, ReconciliationLink.active.is_(True)).with_for_update())
        if link is None:
            raise HTTPException(409, "اتصال فعالی برای برداشتن وجود ندارد")
        if row.status == "RESOLVED":
            raise HTTPException(409, "مغایرت حل‌شده قابل تغییر نیست")
        now = utcnow()
        link.active, link.unlinked_by_user_id, link.unlink_reason = False, user.id, data.reason
        prev = row.status
        row.status, row.matched_at = "DISPUTED", None
        row.discrepancy_reason = row.discrepancy_reason or "manual link removed"
        _trail(row, {"event": "unlinked", "actor_id": user.id, "at": now.isoformat(), "reason": data.reason, "from": prev, "to": row.status})
        audit(db, user, "reconciliation.unlink", "reconciliation", {"record_id": row.id, "reason": data.reason})
        db.commit()
        return _recon_out(db, row)

    @router.post("/finance/reconciliation/{record_id}/resolution")
    def recon_resolve(record_id: str, data: ReconResolveIn, user=Depends(recon_user), db: Session = Depends(get_db)) -> dict:
        row = _recon(db, user.tenant_id, record_id)
        if row.status != "DISPUTED":
            raise HTTPException(409, "فقط مغایرت باز قابل حل است")
        now = utcnow()
        row.status, row.resolved_by_user_id, row.resolved_at = "RESOLVED", user.id, now
        row.resolution_note = f"{RESOLUTION_FA[data.resolution_type]}: {data.reason.strip()}"
        _trail(row, {"event": "resolved", "actor_id": user.id, "at": now.isoformat(), "resolution_type": data.resolution_type, "note": data.reason.strip()})
        audit(db, user, "reconciliation.resolve", "reconciliation", {"record_id": row.id, "resolution_type": data.resolution_type, "reason": data.reason})
        db.add(m.OutboxEvent(tenant_id=user.tenant_id, aggregate_type="reconciliation", aggregate_id=row.id, event_type="reconciliation.resolved",
                             payload_json=json.dumps({"resolution_type": data.resolution_type}), correlation_id=str(uuid.uuid4()), idempotency_key=f"recon-resolve:{row.id}"))
        db.commit()
        return _recon_out(db, row)

    return router
