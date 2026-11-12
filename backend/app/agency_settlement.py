"""Panels Phase 2b — agency periodic settlement (AG-17/AG-18/FIN-05), disputes on statement lines, refund to agency credit.

Statement (one per agency per period, `agency_settlements` + append-only `agency_settlement_lines`)
* Boundaries are timestamps, not only dates: a statement covers the agency ledger entries after the previous statement's
  `cutoff_at` up to its own `cutoff_at` (end of `period_end` in Asia/Tehran, or the moment of generation when the period
  ends today). Nothing falls between two statements and nothing is counted twice.
* Every line is a signed integer rial **from the platform's side: positive = the agency owes, negative = the platform owes**.
    OPENING      −(account balance at the start)            the money the agency already had (or owed) when the period began
    movements    −sign × entry for every balance-moving agency ledger entry in the period: SALE (CAPTURE, +), REFUND (credit back, −),
                 PAYMENT (TOPUP, −), DECREASE (+), and the postings of the previous settlement (commission, adjustments, payment)
    COMMISSION   −commission of each sale in the period (contract rate captured on the booking line)
    VAT          −VAT on that commission only — never on the fare — at the rate of the sale date from the dated tax table
                 (`agency_b2b.vat_rate_on`, FIN-11 table first); a date without a rate is an error, nothing is guessed
    COMMISSION_REVERSAL / VAT_REVERSAL  + the share of commission (and its VAT) of a sale refunded to the agency credit in the period
                 (commission on a kept penalty is not reversed, as in E2E-C)
    ADJUSTMENT   signed, only added after issue, only through maker-checker
  net = Σ lines = −(closing balance + period commission incl. VAT − reversals) + adjustments.
* Status: draft → issued (maker-checker `agency.settlement_issue`) → accepted (agency owner) | disputed (agency owner, on a
  line) → issued again when every dispute is closed → settled (maker-checker `agency.settlement_settle`). Two different
  finance users (`settlement:manage`) are always needed for issue, settle and every adjustment.
* Immutable once issued: lines are never updated or deleted (DB grant: SELECT, INSERT); a correction is a new ADJUSTMENT line.
* Settling posts to the agency ledger: COMMISSION (+) or COMM_REVERSAL (−) for the period's commission, ADJ_CREDIT / ADJ_DEBIT
  for the adjustments and, when the agency owes (net > 0), SETTLE_IN for its bank payment (reference required). After that
  the period's credit use is restored; a negative net stays in the agency account as its credit. Nothing is sent to a bank.

Refund to agency credit (`agency_credit_refunds`, maker-checker `agency.credit_refund`, checker = `refund:manage`)
* For a booking the agency paid from its account (agency_b2b booking line). Created by ops when approving a cancel/refund
  request, by a charter cancellation, or by the agency answering a charter schedule change. One REFUND ledger entry per
  approval (idempotency key `mc:<request id>`); the total credited back for a booking line can never exceed its net.
* The credit back appears as a REFUND line (and the matching commission/VAT reversal) in the next statement.
Notifications go to the in-app notification table and the outbox only; nothing is sent by SMS here.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import approvals
from . import operations as m
from .agency_b2b import (AgencyAccount, AgencyBookingLine, AgencyLedgerEntry, _entry, _prior, account_for, agency_membership, bps_of, half_up,
                         vat_rate_on)
from .database import Base
from .operations import OperationalMixin

TEHRAN = ZoneInfo("Asia/Tehran")

# Balance effect of each agency ledger entry type (+ raises the agency balance). HOLD/RELEASE/LIMIT_CHANGE move no balance.
LEDGER_SIGN = {"TOPUP": 1, "DECREASE": -1, "CAPTURE": -1, "REFUND": 1, "COMMISSION": 1, "COMM_REVERSAL": -1, "ADJ_CREDIT": 1, "ADJ_DEBIT": -1, "SETTLE_IN": 1}
MOVEMENT_LINE = {"CAPTURE": "SALE", "REFUND": "REFUND", "TOPUP": "PAYMENT", "DECREASE": "DECREASE", "COMMISSION": "COMMISSION_CREDITED",
                 "COMM_REVERSAL": "COMMISSION_DEBITED", "ADJ_CREDIT": "ADJUSTMENT_POSTED", "ADJ_DEBIT": "ADJUSTMENT_POSTED", "SETTLE_IN": "SETTLEMENT_PAYMENT"}
LINE_FA = {"OPENING": "ماندهٔ ابتدای دوره", "SALE": "فروش با حساب آژانس", "REFUND": "بازگشت به اعتبار آژانس (استرداد)", "PAYMENT": "واریز آژانس",
           "DECREASE": "کاهش حساب", "COMMISSION_CREDITED": "کمیسیون تسویهٔ قبلی", "COMMISSION_DEBITED": "برگشت کمیسیون تسویهٔ قبلی",
           "ADJUSTMENT_POSTED": "اصلاحیهٔ ثبت‌شده در حساب", "SETTLEMENT_PAYMENT": "پرداخت تسویهٔ قبلی", "COMMISSION": "کمیسیون آژانس",
           "VAT": "ارزش افزودهٔ کمیسیون", "COMMISSION_REVERSAL": "برگشت کمیسیون (استرداد)", "VAT_REVERSAL": "برگشت ارزش افزودهٔ کمیسیون", "ADJUSTMENT": "اصلاحیه"}
STATUS_FA = {"draft": "پیش‌نویس", "issued": "صادرشده", "accepted": "پذیرفته‌شده", "disputed": "دارای اعتراض", "settled": "تسویه‌شده", "superseded": "جایگزین‌شده"}
OPEN_STATUSES = ("draft", "issued", "accepted", "disputed")
DISPUTE_FA = {"open": "باز", "adjustment_pending": "اصلاحیه در انتظار تأیید نفر دوم", "accepted": "پذیرفته‌شده", "rejected": "ردشده"}
REFUND_FA = {"pending_approval": "در انتظار تأیید مالی", "executed": "به اعتبار آژانس برگشت", "rejected": "رد شد", "expired": "مهلت تأیید گذشت"}
REFUND_SOURCES = ("service_request", "charter_cancel", "charter_change")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aw(dt: Optional[datetime]) -> Optional[datetime]:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def _iso(v) -> Optional[str]:
    if isinstance(v, datetime):
        return _aw(v).isoformat()
    return v.isoformat() if v is not None else None


def tehran_day(dt: datetime) -> date:
    return _aw(dt).astimezone(TEHRAN).date()


# ------------------------------------------------------------------------------------------------ models
class AgencySettlement(OperationalMixin, Base):
    __tablename__ = "agency_settlements"
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    statement_no: Mapped[str] = mapped_column(String(40))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    from_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # exclusive; None = account start
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # inclusive
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    opening_balance_irr: Mapped[int] = mapped_column(Integer, default=0)
    closing_balance_irr: Mapped[int] = mapped_column(Integer, default=0)
    net_irr: Mapped[int] = mapped_column(Integer, default=0)
    totals_json: Mapped[str] = mapped_column(Text, default="{}")
    issue_mc_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    settle_mc_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    settle_reference: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("tenant_id", "statement_no", name="uq_agency_settlement_no"),)


class AgencySettlementLine(OperationalMixin, Base):
    """Append-only. amount_irr > 0: the agency owes; < 0: the platform owes."""
    __tablename__ = "agency_settlement_lines"
    settlement_id: Mapped[str] = mapped_column(ForeignKey("agency_settlements.id"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    line_type: Mapped[str] = mapped_column(String(24))
    amount_irr: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(300), default="")
    booking_line_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    ledger_entry_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    vat_rate_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    vat_rate_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dispute_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    mc_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "settlement_id", "line_no", name="uq_agency_settlement_line_no"),)


class AgencySettlementDispute(OperationalMixin, Base):
    __tablename__ = "agency_settlement_disputes"
    settlement_id: Mapped[str] = mapped_column(ForeignKey("agency_settlements.id"), index=True)
    line_id: Mapped[str] = mapped_column(ForeignKey("agency_settlement_lines.id"), index=True)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    claimed_amount_irr: Mapped[int] = mapped_column(Integer)  # correction the agency claims in its favour
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    adjustment_amount_irr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mc_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    opened_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AgencySettlementEvent(OperationalMixin, Base):
    """Append-only timeline of a statement and its disputes."""
    __tablename__ = "agency_settlement_events"
    settlement_id: Mapped[str] = mapped_column(ForeignKey("agency_settlements.id"), index=True)
    dispute_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    actor_kind: Mapped[str] = mapped_column(String(16))  # agency | finance | system
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    command_id: Mapped[str] = mapped_column(String(160))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_agency_settlement_event_command"),)


class AgencyCreditRefund(OperationalMixin, Base):
    __tablename__ = "agency_credit_refunds"
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    booking_line_id: Mapped[str] = mapped_column(ForeignKey("agency_booking_lines.id"), index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    service_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    charter_notice_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(24))
    amount_irr: Mapped[int] = mapped_column(Integer)
    penalty_irr: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending_approval", index=True)
    mc_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    ledger_entry_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_agency_credit_refund_key"),)


TABLES = ("agency_settlements", "agency_settlement_lines", "agency_settlement_disputes", "agency_settlement_events", "agency_credit_refunds")
APPEND_ONLY = ("agency_settlement_lines", "agency_settlement_events")


# ------------------------------------------------------------------------------------------------ ledger posting
def post_entry(db: Session, acc: AgencyAccount, entry_type: str, amount: int, *, key: str, user_id: Optional[int], **extra) -> AgencyLedgerEntry:
    """Balance-moving entry decided by a finance approval (no credit check: the approval is the authority). Idempotent by key."""
    prior = _prior(db, acc.tenant_id, key)
    if prior is not None:
        return prior
    if amount <= 0 or entry_type not in LEDGER_SIGN:
        raise ValueError("مبلغ یا نوع حرکت نامعتبر است")
    db.execute(update(AgencyAccount).where(AgencyAccount.id == acc.id, AgencyAccount.tenant_id == acc.tenant_id)
               .values(balance_irr=AgencyAccount.balance_irr + LEDGER_SIGN[entry_type] * amount, version=AgencyAccount.version + 1)
               .execution_options(synchronize_session=False))
    return _entry(db, acc, entry_type, amount, key, user_id, **extra)


def owners_of(db: Session, tenant_id: int, agency_id: str) -> list[int]:
    return list(db.scalars(select(m.AgencyMembership.user_id).where(m.AgencyMembership.tenant_id == tenant_id, m.AgencyMembership.agency_id == agency_id,
                                                                     m.AgencyMembership.agency_role == "owner")))


def notify_agency(db: Session, tenant_id: int, agency_id: str, *, title: str, message: str, link: str, event_type: str, aggregate_type: str,
                  aggregate_id: str, key: str, payload: Optional[dict] = None) -> None:
    """In-app notification for every agency owner + one outbox event. No SMS is sent from here."""
    for uid in owners_of(db, tenant_id, agency_id):
        db.add(m.NotificationRecord(tenant_id=tenant_id, user_id=uid, topic="agency", title=title[:200], message=message, deep_link=link))
    db.add(m.OutboxEvent(tenant_id=tenant_id, aggregate_type=aggregate_type, aggregate_id=aggregate_id, event_type=event_type,
                         payload_json=json.dumps({"agency_id": agency_id, **(payload or {})}, ensure_ascii=False, default=str),
                         correlation_id=str(uuid.uuid4()), idempotency_key=key[:120]))


# ------------------------------------------------------------------------------------------------ refund to agency credit
def credit_line_for_reservation(db: Session, tenant_id: int, reservation_id: str) -> Optional[AgencyBookingLine]:
    return db.scalar(select(AgencyBookingLine).where(AgencyBookingLine.tenant_id == tenant_id, AgencyBookingLine.reservation_id == reservation_id,
                                                     AgencyBookingLine.status == "captured"))


def sync_refund_status(db: Session, row: AgencyCreditRefund) -> AgencyCreditRefund:
    """A rejected or expired approval leaves the refund un-executed: mirror that on the row (lazily, like approvals.py)."""
    if row.status == "pending_approval" and row.mc_request_id:
        mc = db.get(approvals.MakerCheckerRequest, row.mc_request_id)
        if mc is not None and mc.status == "pending" and _aw(mc.expires_at) <= utcnow():
            mc.status, mc.decided_at = "expired", utcnow()
        if mc is not None and mc.status in ("rejected", "expired"):
            row.status = mc.status
    return row


def credit_committed(db: Session, line: AgencyBookingLine) -> int:
    rows = db.scalars(select(AgencyCreditRefund).where(AgencyCreditRefund.tenant_id == line.tenant_id, AgencyCreditRefund.booking_line_id == line.id)).all()
    return sum(r.amount_irr for r in rows if sync_refund_status(db, r).status in ("pending_approval", "executed"))


def credit_remaining(db: Session, line: AgencyBookingLine) -> int:
    return max(0, line.net_irr - credit_committed(db, line))


def queue_credit_refund(db: Session, *, user, line: AgencyBookingLine, amount: int, penalty: int, source: str, key: str, audit: Callable,
                        service_request_id: Optional[str] = None, charter_notice_id: Optional[str] = None, note: Optional[str] = None) -> AgencyCreditRefund:
    """Creates the refund row and its maker-checker request. Nothing is credited until a finance user (≠ maker) approves."""
    prior = db.scalar(select(AgencyCreditRefund).where(AgencyCreditRefund.tenant_id == line.tenant_id, AgencyCreditRefund.idempotency_key == key[:160]))
    if prior is not None:
        return prior
    if source not in REFUND_SOURCES or amount <= 0:
        raise ValueError("مبلغ بازگشت به اعتبار نامعتبر است")
    if amount > credit_remaining(db, line):
        raise ValueError("مبلغ بازگشت از باقی‌ماندهٔ قابل برگشت این رزرو بیشتر است")
    row = AgencyCreditRefund(tenant_id=line.tenant_id, agency_id=line.agency_id, booking_line_id=line.id, reservation_id=line.reservation_id,
                             service_request_id=service_request_id, charter_notice_id=charter_notice_id, source=source, amount_irr=amount, penalty_irr=penalty,
                             status="pending_approval", note=(note or None) and note[:300], idempotency_key=key[:160], created_by_user_id=user.id)
    db.add(row)
    db.flush()
    _request_credit_refund(db, row, user, audit)
    audit(db, user, "agency.credit_refund.requested", "agency_b2b", {"agency_id": line.agency_id, "credit_refund_id": row.id, "amount_irr": amount, "source": source})
    return row


def _request_credit_refund(db: Session, row: AgencyCreditRefund, user, audit: Callable) -> None:
    agency = db.get(m.Agency, row.agency_id)
    mc = approvals.create_request(db, user=user, kind="agency.credit_refund", idempotency_key=f"acr:{row.id}:{uuid.uuid4().hex[:8]}",
                                  payload={"credit_refund_id": row.id, "agency_id": row.agency_id, "booking_line_id": row.booking_line_id, "amount_irr": row.amount_irr,
                                           "source": row.source},
                                  summary=f"بازگشت به اعتبار {agency.display_name if agency else 'آژانس'}", amount=row.amount_irr, target_ref=f"agency:{row.agency_id}", audit=audit)
    row.mc_request_id, row.status = mc.id, "pending_approval"


def _execute_credit_refund(db: Session, request, payload: dict, checker) -> dict:
    from . import after_sales as A  # lazy: after_sales imports this module lazily too
    row = db.scalar(select(AgencyCreditRefund).where(AgencyCreditRefund.id == payload["credit_refund_id"], AgencyCreditRefund.tenant_id == request.tenant_id).with_for_update())
    if row is None:
        raise ValueError("ردیف بازگشت به اعتبار یافت نشد")
    if row.status == "executed":
        return {"ledger_entry_id": row.ledger_entry_id}
    line = db.get(AgencyBookingLine, row.booking_line_id)
    others = sum(r.amount_irr for r in db.scalars(select(AgencyCreditRefund).where(AgencyCreditRefund.tenant_id == row.tenant_id,
                                                                                    AgencyCreditRefund.booking_line_id == row.booking_line_id,
                                                                                    AgencyCreditRefund.status == "executed", AgencyCreditRefund.id != row.id)))
    if others + row.amount_irr > line.net_irr:
        raise ValueError("جمع بازگشت به اعتبار از مبلغ خرید این رزرو بیشتر می‌شود")
    acc = account_for(db, row.tenant_id, row.agency_id, create=True)
    res = db.get(m.Reservation, row.reservation_id) if row.reservation_id else None
    e = post_entry(db, acc, "REFUND", row.amount_irr, key=f"mc:{request.id}", user_id=checker.id, mc_request_id=request.id, booking_line_id=line.id,
                   reservation_id=row.reservation_id, reference=res.booking_reference if res else None, note=f"بازگشت به اعتبار آژانس ({row.source})")
    row.status, row.ledger_entry_id, row.executed_at, row.mc_request_id = "executed", e.id, utcnow(), request.id
    if row.service_request_id:
        req = db.scalar(select(m.BookingServiceRequest).where(m.BookingServiceRequest.id == row.service_request_id, m.BookingServiceRequest.tenant_id == row.tenant_id).with_for_update())
        if req is not None and req.status == "refund_queued":
            h = A.handling_for(db, req)
            prev, req.status = req.status, A.next_status(req.status, "refund_paid")
            h.status_since = utcnow()
            A.record_event(db, req=req, event_type="refund_paid", actor_kind="finance", actor_id=checker.id, from_status=prev, to_status=req.status,
                           payload={"credit_refund_id": row.id, "method": "agency_credit", "amount": row.amount_irr}, command_id=f"acr-paid:{row.id}")
            db.add(m.NotificationRecord(tenant_id=req.tenant_id, user_id=h.customer_user_id, topic="service_request", title="استرداد به اعتبار آژانس برگشت",
                                        message=f"مبلغ {row.amount_irr:,} ریال به اعتبار آژانس برگشت.", deep_link=f"/account/refunds/{req.id}"))
    if res is not None:
        _walk_to_refunded(db, res, checker.id, f"acr:{row.id}")
    notify_agency(db, row.tenant_id, row.agency_id, title="بازگشت مبلغ به اعتبار آژانس", message=f"مبلغ {row.amount_irr:,} ریال به حساب آژانس برگشت و در صورت تسویهٔ بعدی می‌آید.",
                  link="/agency/credit", event_type="agency.credit_refund.executed", aggregate_type="agency_credit_refund", aggregate_id=row.id,
                  key=f"acr-exec:{row.id}", payload={"amount_irr": row.amount_irr, "ledger_entry_id": e.id})
    return {"ledger_entry_id": e.id, "balance_after": e.balance_after, "credit_refund_id": row.id}


def _walk_to_refunded(db: Session, res: m.Reservation, actor_id: int, key: str) -> None:
    """confirmed/issued → cancel_requested → cancelled → refunded, refund_requested → refunded, through the normal transition table."""
    paths = {"confirmed": ("cancel_requested", "cancelled", "refunded"), "issued": ("cancel_requested", "cancelled", "refunded"),
             "cancel_requested": ("cancelled", "refunded"), "cancelled": ("refunded",), "refund_requested": ("refunded",)}
    for target in paths.get(res.status, ()):
        m.transition_reservation(db, res, target, actor_id, f"{key}:{target}")


def refund_out(db: Session, r: AgencyCreditRefund) -> dict:
    sync_refund_status(db, r)
    res = db.get(m.Reservation, r.reservation_id) if r.reservation_id else None
    return {"id": r.id, "agency_id": r.agency_id, "booking_line_id": r.booking_line_id, "reservation_id": r.reservation_id,
            "booking_reference": res.booking_reference if res else None, "service_request_id": r.service_request_id, "charter_notice_id": r.charter_notice_id,
            "source": r.source, "amount_irr": r.amount_irr, "penalty_irr": r.penalty_irr, "status": r.status, "status_label": REFUND_FA.get(r.status, r.status),
            "mc_request_id": r.mc_request_id, "ledger_entry_id": r.ledger_entry_id, "executed_at": _iso(r.executed_at), "created_at": _iso(r.created_at)}


# ------------------------------------------------------------------------------------------------ statement computation (pure on loaded rows)
def tehran_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=TEHRAN).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def build_lines(db: Session, tenant_id: int, agency_id: str, from_at: Optional[datetime], cutoff_at: datetime) -> tuple[list[dict], int, int]:
    """(lines, opening balance, closing balance). Raises LookupError when a sale date has no VAT rate."""
    acc = account_for(db, tenant_id, agency_id)
    entries = db.scalars(select(AgencyLedgerEntry).where(AgencyLedgerEntry.tenant_id == tenant_id, AgencyLedgerEntry.agency_id == agency_id)
                         .order_by(AgencyLedgerEntry.created_at, AgencyLedgerEntry.id).limit(100_000)).all() if acc else []
    before = [e for e in entries if from_at is not None and _aw(e.created_at) <= _aw(from_at)]
    inside = [e for e in entries if (from_at is None or _aw(e.created_at) > _aw(from_at)) and _aw(e.created_at) <= _aw(cutoff_at)]
    opening = sum(LEDGER_SIGN.get(e.entry_type, 0) * e.amount_irr for e in before)
    closing = opening + sum(LEDGER_SIGN.get(e.entry_type, 0) * e.amount_irr for e in inside)
    lines: list[dict] = [{"line_type": "OPENING", "amount_irr": -opening, "description": LINE_FA["OPENING"], "occurred_at": from_at}]
    booking_ids = {e.booking_line_id for e in inside if e.booking_line_id}
    blines = {b.id: b for b in db.scalars(select(AgencyBookingLine).where(AgencyBookingLine.tenant_id == tenant_id, AgencyBookingLine.id.in_(booking_ids)))} if booking_ids else {}
    refs = {r.id: r.booking_reference for r in db.scalars(select(m.Reservation).where(m.Reservation.tenant_id == tenant_id, m.Reservation.id.in_(
        {e.reservation_id for e in inside if e.reservation_id})))} if inside else {}
    for e in inside:
        sign = LEDGER_SIGN.get(e.entry_type, 0)
        if not sign:
            continue
        ref = refs.get(e.reservation_id) or e.reference
        kind = MOVEMENT_LINE[e.entry_type]
        lines.append({"line_type": kind, "amount_irr": -sign * e.amount_irr, "description": f"{LINE_FA[kind]}{' · ' + ref if ref else ''}", "ledger_entry_id": e.id,
                      "booking_line_id": e.booking_line_id, "reservation_id": e.reservation_id, "occurred_at": e.created_at})
        b = blines.get(e.booking_line_id) if e.booking_line_id else None
        if b is None or e.entry_type not in ("CAPTURE", "REFUND"):
            continue
        rate = vat_rate_on(tehran_day(b.created_at), db, tenant_id)  # dated table at the SALE date
        if e.entry_type == "CAPTURE":
            commission = b.commission_irr
            label = ""
        else:
            commission = half_up(b.commission_irr * e.amount_irr, b.net_irr) if b.net_irr else 0
            label = "_REVERSAL"
        vat = bps_of(commission, rate.rate_bps)
        sgn = -1 if e.entry_type == "CAPTURE" else 1
        if commission:
            lines.append({"line_type": f"COMMISSION{label}", "amount_irr": sgn * commission, "description": f"{LINE_FA['COMMISSION' + label]}{' · ' + ref if ref else ''} ({b.commission_bps} bps)",
                          "booking_line_id": b.id, "reservation_id": b.reservation_id, "ledger_entry_id": e.id, "occurred_at": e.created_at})
        if vat:
            lines.append({"line_type": f"VAT{label}", "amount_irr": sgn * vat, "description": f"{LINE_FA['VAT' + label]}{' · ' + ref if ref else ''} ({rate.rate_bps / 100:g}٪)",
                          "booking_line_id": b.id, "reservation_id": b.reservation_id, "ledger_entry_id": e.id, "vat_rate_id": rate.id, "vat_rate_bps": rate.rate_bps,
                          "occurred_at": e.created_at})
    return lines, opening, closing


def totals_of(lines) -> dict:
    def s(*types):
        return sum((x["amount_irr"] if isinstance(x, dict) else x.amount_irr) for x in lines if (x["line_type"] if isinstance(x, dict) else x.line_type) in types)
    t = {"opening_owed_irr": s("OPENING"), "sales_irr": s("SALE"), "refunds_irr": s("REFUND"), "payments_irr": s("PAYMENT", "DECREASE"),
         "previous_settlement_irr": s("COMMISSION_CREDITED", "COMMISSION_DEBITED", "ADJUSTMENT_POSTED", "SETTLEMENT_PAYMENT"),
         "commission_irr": s("COMMISSION", "COMMISSION_REVERSAL"), "vat_irr": s("VAT", "VAT_REVERSAL"), "adjustments_irr": s("ADJUSTMENT")}
    t["net_irr"] = sum(v for v in t.values())
    return t


# ------------------------------------------------------------------------------------------------ schemas
class Strict(BaseModel):
    model_config = {"extra": "forbid"}


class DraftIn(Strict):
    agency_id: str = Field(min_length=36, max_length=36)
    period_start: date
    period_end: date


class SettleIn(Strict):
    bank_reference: Optional[str] = Field(default=None, min_length=4, max_length=80)
    paid_on: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=300)


class AdjustmentIn(Strict):
    amount_irr: int = Field(ge=-(10**12), le=10**12)  # > 0 the agency owes more; < 0 in the agency's favour
    reason: str = Field(min_length=5, max_length=300)


class DisputeIn(Strict):
    line_id: str = Field(min_length=36, max_length=36)
    reason: str = Field(min_length=5, max_length=2000)
    claimed_amount_irr: int = Field(ge=0, le=10**12)


class ResolveIn(Strict):
    decision: str = Field(pattern="^(accept|reject)$")
    adjustment_amount_irr: Optional[int] = Field(default=None, ge=0, le=10**12)
    reason: str = Field(min_length=5, max_length=2000)


class NoteIn(Strict):
    note: Optional[str] = Field(default=None, max_length=500)


# ------------------------------------------------------------------------------------------------ router
def agency_settlement_router(get_db, current_user, role_has_permission, User, audit: Callable) -> APIRouter:
    api = APIRouter(tags=["agency-settlement"])

    def can_settle(actor, _payload) -> bool:
        return role_has_permission(actor.role, "settlement:manage")

    approvals.register("agency.settlement_issue", can_check=can_settle, execute=lambda db, r, p, c: _exec_issue(db, r, p, c), label="صدور صورت تسویهٔ آژانس")
    approvals.register("agency.settlement_settle", can_check=can_settle, execute=lambda db, r, p, c: _exec_settle(db, r, p, c), label="تسویهٔ صورت آژانس")
    approvals.register("agency.settlement_adjustment", can_check=can_settle, execute=lambda db, r, p, c: _exec_adjust(db, r, p, c), label="اصلاحیهٔ صورت تسویهٔ آژانس")
    approvals.register("agency.credit_refund", can_check=lambda actor, _p: role_has_permission(actor.role, "refund:manage"), execute=_execute_credit_refund,
                       label="بازگشت به اعتبار آژانس")

    # ---- shared ---------------------------------------------------------------------------------------------------
    def event(db: Session, st: AgencySettlement, event_type: str, actor_kind: str, actor_id: Optional[int], note: Optional[str] = None,
              dispute_id: Optional[str] = None, payload: Optional[dict] = None, key: Optional[str] = None) -> None:
        db.add(AgencySettlementEvent(tenant_id=st.tenant_id, settlement_id=st.id, dispute_id=dispute_id, event_type=event_type, actor_kind=actor_kind,
                                     actor_id=actor_id, note=note, payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
                                     command_id=(key or f"ase:{st.id}:{uuid.uuid4()}")[:160]))

    def statement(db: Session, tenant_id: int, sid: str, agency_id: Optional[str] = None, lock: bool = False) -> AgencySettlement:
        q = select(AgencySettlement).where(AgencySettlement.id == sid, AgencySettlement.tenant_id == tenant_id)
        if agency_id is not None:
            q = q.where(AgencySettlement.agency_id == agency_id, AgencySettlement.status != "draft")  # the agency sees only issued statements
        row = db.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise HTTPException(status_code=404, detail="صورت تسویه یافت نشد")
        return row

    def lines_of(db: Session, st: AgencySettlement) -> list[AgencySettlementLine]:
        return db.scalars(select(AgencySettlementLine).where(AgencySettlementLine.tenant_id == st.tenant_id, AgencySettlementLine.settlement_id == st.id)
                          .order_by(AgencySettlementLine.line_no)).all()

    def recompute(db: Session, st: AgencySettlement) -> dict:
        t = totals_of(lines_of(db, st))
        st.totals_json, st.net_irr = json.dumps(t), t["net_irr"]
        return t

    def mc_status(db: Session, mc_id: Optional[str]) -> Optional[str]:
        if not mc_id:
            return None
        row = db.get(approvals.MakerCheckerRequest, mc_id)
        if row is not None and row.status == "pending" and _aw(row.expires_at) <= utcnow():
            row.status, row.decided_at = "expired", utcnow()
        return row.status if row else None

    def disputes_of(db: Session, st: AgencySettlement) -> list[AgencySettlementDispute]:
        rows = db.scalars(select(AgencySettlementDispute).where(AgencySettlementDispute.tenant_id == st.tenant_id, AgencySettlementDispute.settlement_id == st.id)
                          .order_by(AgencySettlementDispute.created_at)).all()
        for d in rows:  # an adjustment approval that was rejected/expired puts the dispute back to open
            if d.status == "adjustment_pending" and mc_status(db, d.mc_request_id) in ("rejected", "expired"):
                d.status = "open"
        return rows

    def names(db: Session, ids) -> dict:
        ids = {i for i in ids if i}
        return {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}

    def st_out(db: Session, st: AgencySettlement, *, detail: bool = False, agency_view: bool = False) -> dict:
        agency = db.get(m.Agency, st.agency_id)
        t = json.loads(st.totals_json or "{}")
        out = {"id": st.id, "statement_no": st.statement_no, "agency_id": st.agency_id, "agency_name": agency.display_name if agency else None,
               "period_start": _iso(st.period_start), "period_end": _iso(st.period_end), "from_at": _iso(st.from_at), "cutoff_at": _iso(st.cutoff_at),
               "status": st.status, "status_label": STATUS_FA.get(st.status, st.status), "net_irr": st.net_irr, "totals": t,
               "direction": "agency_pays" if st.net_irr > 0 else ("platform_owes" if st.net_irr < 0 else "zero"),
               "opening_balance_irr": st.opening_balance_irr, "closing_balance_irr": st.closing_balance_irr,
               "issued_at": _iso(st.issued_at), "accepted_at": _iso(st.accepted_at), "settled_at": _iso(st.settled_at), "settle_reference": st.settle_reference,
               "created_at": _iso(st.created_at)}
        if not agency_view:
            out.update({"issue_request": {"id": st.issue_mc_request_id, "status": mc_status(db, st.issue_mc_request_id)} if st.issue_mc_request_id else None,
                        "settle_request": {"id": st.settle_mc_request_id, "status": mc_status(db, st.settle_mc_request_id)} if st.settle_mc_request_id else None})
        if detail:
            ds = disputes_of(db, st)
            by_line = {d.line_id: d for d in ds if d.status in ("open", "adjustment_pending")}
            lines_all = lines_of(db, st)
            refs = {r.id: r.booking_reference for r in db.scalars(select(m.Reservation).where(m.Reservation.tenant_id == st.tenant_id, m.Reservation.id.in_(
                {x.reservation_id for x in lines_all if x.reservation_id})))} if lines_all else {}
            rows: dict[str, dict] = {}
            for x in lines_all:
                if x.line_type not in ("SALE", "REFUND", "COMMISSION", "VAT", "COMMISSION_REVERSAL", "VAT_REVERSAL") or not x.reservation_id:
                    continue
                key = f"{x.reservation_id}:{'R' if x.line_type in ('REFUND', 'COMMISSION_REVERSAL', 'VAT_REVERSAL') else 'S'}:{x.ledger_entry_id}"
                r = rows.setdefault(key, {"key": key, "reservation_id": x.reservation_id, "booking_reference": refs.get(x.reservation_id), "kind": "sale",
                                          "date": _iso(x.occurred_at), "sale_irr": 0, "refund_irr": 0, "commission_irr": 0, "vat_irr": 0, "net_irr": 0, "line_id": None,
                                          "open_dispute_id": None})
                if x.line_type == "SALE":
                    r["sale_irr"], r["line_id"] = x.amount_irr, x.id
                elif x.line_type == "REFUND":
                    r["refund_irr"], r["line_id"], r["kind"] = x.amount_irr, x.id, "refund"
                elif x.line_type in ("COMMISSION", "COMMISSION_REVERSAL"):
                    r["commission_irr"] += x.amount_irr
                else:
                    r["vat_irr"] += x.amount_irr
                r["net_irr"] += x.amount_irr
            for r in rows.values():
                r["open_dispute_id"] = by_line[r["line_id"]].id if r["line_id"] in by_line else None
                r["disputable"] = st.status in ("issued", "disputed") and r["line_id"] is not None and r["open_dispute_id"] is None
            out["booking_rows"] = sorted(rows.values(), key=lambda r: r["date"] or "")
            out["lines"] = [{"id": x.id, "line_no": x.line_no, "line_type": x.line_type, "type_label": LINE_FA.get(x.line_type, x.line_type), "amount_irr": x.amount_irr,
                             "description": x.description, "reservation_id": x.reservation_id, "vat_rate_id": x.vat_rate_id, "vat_rate_bps": x.vat_rate_bps,
                             "occurred_at": _iso(x.occurred_at), "dispute_id": x.dispute_id, "open_dispute_id": by_line[x.id].id if x.id in by_line else None,
                             "disputable": st.status in ("issued", "disputed") and x.id not in by_line and x.line_type != "OPENING"} for x in lines_of(db, st)]
            nm = names(db, [d.opened_by_user_id for d in ds] + [d.resolved_by_user_id for d in ds])
            out["disputes"] = [dispute_out(db, d, nm) for d in ds]
            evs = db.scalars(select(AgencySettlementEvent).where(AgencySettlementEvent.tenant_id == st.tenant_id, AgencySettlementEvent.settlement_id == st.id)
                             .order_by(AgencySettlementEvent.created_at, AgencySettlementEvent.id)).all()
            en = names(db, [e.actor_id for e in evs])
            out["timeline"] = [{"type": e.event_type, "actor_kind": e.actor_kind, "actor": (en.get(e.actor_id) if not agency_view or e.actor_kind == "agency" else None)
                                or {"agency": "آژانس", "finance": "کارشناس مالی", "system": "سامانه"}.get(e.actor_kind), "note": e.note, "dispute_id": e.dispute_id,
                                "at": _iso(e.created_at)} for e in evs]
        return out

    def dispute_out(db: Session, d: AgencySettlementDispute, nm: dict) -> dict:
        line = db.get(AgencySettlementLine, d.line_id)
        return {"id": d.id, "settlement_id": d.settlement_id, "line_id": d.line_id, "line_no": line.line_no if line else None,
                "line_type": line.line_type if line else None, "line_amount_irr": line.amount_irr if line else None, "line_description": line.description if line else None,
                "reason": d.reason, "claimed_amount_irr": d.claimed_amount_irr, "status": d.status, "status_label": DISPUTE_FA.get(d.status, d.status),
                "adjustment_amount_irr": d.adjustment_amount_irr, "resolution_note": d.resolution_note, "mc_request_id": d.mc_request_id,
                "opened_by": nm.get(d.opened_by_user_id), "resolved_by": nm.get(d.resolved_by_user_id), "created_at": _iso(d.created_at), "resolved_at": _iso(d.resolved_at)}

    def settler(user=Depends(current_user)):
        if not role_has_permission(user.role, "settlement:manage"):
            raise HTTPException(status_code=403, detail="مجوز تسویهٔ مالی لازم است")
        return user

    def fin_reader(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("settlement:manage", "ledger:read", "refund:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مالی لازم است")
        return user

    def owner_of(db: Session, agency_id: str, user, write: bool = False):
        agency, role = agency_membership(db, agency_id, user, role_has_permission, owner=write)
        if role == "agent":
            raise HTTPException(status_code=403, detail="صورت تسویه فقط برای مدیر آژانس است")
        return agency, role

    def mc(db, user, kind, payload, key, summary, amount, agency_id):
        try:
            return approvals.create_request(db, user=user, kind=kind, payload=payload, idempotency_key=key, summary=summary, amount=amount,
                                            target_ref=f"agency:{agency_id}", audit=audit)
        except approvals.MakerCheckerError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    # ---- maker-checker executors ----------------------------------------------------------------------------------
    def _exec_issue(db: Session, request, payload: dict, checker) -> dict:
        st = db.scalar(select(AgencySettlement).where(AgencySettlement.id == payload["settlement_id"], AgencySettlement.tenant_id == request.tenant_id).with_for_update())
        if st is None or st.status != "draft":
            raise ValueError("فقط پیش‌نویس قابل صدور است")
        if st.net_irr != payload["net_irr"]:
            raise ValueError("مبلغ صورت پس از درخواست تغییر کرده است؛ درخواست تازه ثبت کنید")
        st.status, st.issued_at = "issued", utcnow()
        event(db, st, "issued", "finance", checker.id, payload={"mc_request_id": request.id, "maker_user_id": request.maker_user_id}, key=f"ase-issued:{st.id}")
        notify_agency(db, st.tenant_id, st.agency_id, title=f"صورت تسویهٔ {st.statement_no} صادر شد",
                      message="صورت تسویهٔ دوره صادر شد. لطفاً ردیف‌ها را بررسی و تأیید کنید یا روی ردیف اعتراض ثبت کنید.", link=f"/agency/settlements/{st.id}",
                      event_type="agency_settlement.issued", aggregate_type="agency_settlement", aggregate_id=st.id, key=f"ase-issued:{st.id}", payload={"net_irr": st.net_irr})
        return {"settlement_id": st.id, "status": st.status}

    def _exec_settle(db: Session, request, payload: dict, checker) -> dict:
        st = db.scalar(select(AgencySettlement).where(AgencySettlement.id == payload["settlement_id"], AgencySettlement.tenant_id == request.tenant_id).with_for_update())
        if st is None or st.status != "accepted":
            raise ValueError("فقط صورت پذیرفته‌شده توسط آژانس قابل تسویه است")
        if st.net_irr != payload["net_irr"]:
            raise ValueError("مبلغ صورت پس از درخواست تغییر کرده است؛ درخواست تازه ثبت کنید")
        t = totals_of(lines_of(db, st))
        acc = account_for(db, st.tenant_id, st.agency_id, create=True)
        base = f"mc:{request.id}"
        posted = []
        commission_due = -t["commission_irr"] - t["vat_irr"]  # what the platform owes for commission incl. VAT, net of reversals
        if commission_due:
            e = post_entry(db, acc, "COMMISSION" if commission_due > 0 else "COMM_REVERSAL", abs(commission_due), key=f"{base}:commission", user_id=checker.id,
                           mc_request_id=request.id, reference=st.statement_no, note=f"کمیسیون و ارزش افزودهٔ صورت {st.statement_no}")
            posted.append(e.id)
        if t["adjustments_irr"]:
            e = post_entry(db, acc, "ADJ_DEBIT" if t["adjustments_irr"] > 0 else "ADJ_CREDIT", abs(t["adjustments_irr"]), key=f"{base}:adjust", user_id=checker.id,
                           mc_request_id=request.id, reference=st.statement_no, note=f"اصلاحیه‌های صورت {st.statement_no}")
            posted.append(e.id)
        if st.net_irr > 0:
            e = post_entry(db, acc, "SETTLE_IN", st.net_irr, key=f"{base}:payment", user_id=checker.id, mc_request_id=request.id,
                           reference=payload.get("bank_reference"), note=f"پرداخت تسویهٔ صورت {st.statement_no}")
            posted.append(e.id)
        st.status, st.settled_at, st.settle_reference = "settled", utcnow(), payload.get("bank_reference")
        event(db, st, "settled", "finance", checker.id, note=payload.get("note"), payload={"mc_request_id": request.id, "ledger_entries": posted,
                                                                                         "bank_reference": payload.get("bank_reference")}, key=f"ase-settled:{st.id}")
        notify_agency(db, st.tenant_id, st.agency_id, title=f"صورت تسویهٔ {st.statement_no} تسویه شد", message="تسویهٔ دوره در حساب آژانس ثبت شد.",
                      link=f"/agency/settlements/{st.id}", event_type="agency_settlement.settled", aggregate_type="agency_settlement", aggregate_id=st.id,
                      key=f"ase-settled:{st.id}", payload={"net_irr": st.net_irr})
        return {"settlement_id": st.id, "status": st.status, "ledger_entries": posted}

    def _exec_adjust(db: Session, request, payload: dict, checker) -> dict:
        st = db.scalar(select(AgencySettlement).where(AgencySettlement.id == payload["settlement_id"], AgencySettlement.tenant_id == request.tenant_id).with_for_update())
        if st is None or st.status not in ("issued", "accepted", "disputed"):
            raise ValueError("اصلاحیه فقط روی صورت صادرشده و تسویه‌نشده ثبت می‌شود")
        d = None
        if payload.get("dispute_id"):
            d = db.scalar(select(AgencySettlementDispute).where(AgencySettlementDispute.id == payload["dispute_id"], AgencySettlementDispute.tenant_id == st.tenant_id).with_for_update())
            if d is None or d.status != "adjustment_pending":
                raise ValueError("اعتراض در انتظار اصلاحیه نیست")
        no = (db.scalar(select(func.max(AgencySettlementLine.line_no)).where(AgencySettlementLine.tenant_id == st.tenant_id, AgencySettlementLine.settlement_id == st.id)) or 0) + 1
        line = AgencySettlementLine(tenant_id=st.tenant_id, settlement_id=st.id, line_no=no, line_type="ADJUSTMENT", amount_irr=int(payload["amount_irr"]),
                                    description=f"{LINE_FA['ADJUSTMENT']}: {payload['reason']}"[:300], dispute_id=d.id if d else None, mc_request_id=request.id,
                                    occurred_at=utcnow(), created_by_user_id=checker.id)
        db.add(line)
        db.flush()
        recompute(db, st)
        if d is not None:
            d.status, d.resolved_by_user_id, d.resolved_at = "accepted", checker.id, utcnow()
            event(db, st, "dispute_accepted", "finance", checker.id, note=d.resolution_note, dispute_id=d.id, payload={"adjustment_line_id": line.id,
                                                                                                                         "amount_irr": line.amount_irr}, key=f"ase-dacc:{d.id}")
        else:
            event(db, st, "adjustment_added", "finance", checker.id, note=payload["reason"], payload={"line_id": line.id, "amount_irr": line.amount_irr}, key=f"ase-adj:{request.id}")
        after_dispute_change(db, st, checker.id)
        if st.status == "accepted":  # a later correction needs the agency's acceptance again
            st.status, st.accepted_at = "issued", None
        notify_agency(db, st.tenant_id, st.agency_id, title=f"اصلاحیه روی صورت {st.statement_no}", message="یک ردیف اصلاحیه به صورت تسویه اضافه شد.",
                      link=f"/agency/settlements/{st.id}", event_type="agency_settlement.adjusted", aggregate_type="agency_settlement", aggregate_id=st.id,
                      key=f"ase-adj:{request.id}", payload={"amount_irr": line.amount_irr})
        return {"settlement_id": st.id, "line_id": line.id, "net_irr": st.net_irr}

    def after_dispute_change(db: Session, st: AgencySettlement, actor_id: Optional[int]) -> None:
        if st.status == "disputed" and not any(d.status in ("open", "adjustment_pending") for d in disputes_of(db, st)):
            st.status = "issued"
            event(db, st, "disputes_closed", "system", actor_id, note="همهٔ اعتراض‌ها بسته شد؛ صورت دوباره منتظر تأیید آژانس است.")

    # ---- finance --------------------------------------------------------------------------------------------------
    @api.get("/finance/agency-settlements")
    def fin_list(status: Optional[str] = Query(default=None, pattern="^(draft|issued|accepted|disputed|settled|superseded|open)$"), agency_id: Optional[str] = None,
                 user=Depends(fin_reader), db: Session = Depends(get_db)) -> dict:
        q = select(AgencySettlement).where(AgencySettlement.tenant_id == user.tenant_id)
        if status == "open":
            q = q.where(AgencySettlement.status.in_(OPEN_STATUSES))
        elif status:
            q = q.where(AgencySettlement.status == status)
        if agency_id:
            q = q.where(AgencySettlement.agency_id == agency_id)
        rows = db.scalars(q.order_by(AgencySettlement.created_at.desc()).limit(300)).all()
        items = [st_out(db, x) for x in rows]
        counts = dict(db.execute(select(AgencySettlement.status, func.count()).where(AgencySettlement.tenant_id == user.tenant_id).group_by(AgencySettlement.status)).all())
        open_disputes = db.scalar(select(func.count()).select_from(AgencySettlementDispute).where(AgencySettlementDispute.tenant_id == user.tenant_id,
                                                                                                  AgencySettlementDispute.status.in_(("open", "adjustment_pending")))) or 0
        agencies = db.scalars(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id).order_by(m.Agency.display_name)).all()
        db.commit()
        return {"items": items, "counts": counts, "open_disputes": open_disputes, "can_manage": role_has_permission(user.role, "settlement:manage"), "me": user.id,
                "agencies": [{"id": a.id, "name": a.display_name} for a in agencies]}

    @api.post("/finance/agency-settlements", status_code=201)
    def fin_draft(data: DraftIn, user=Depends(settler), db: Session = Depends(get_db)) -> dict:
        agency = db.scalar(select(m.Agency).where(m.Agency.id == data.agency_id, m.Agency.tenant_id == user.tenant_id).with_for_update())
        if agency is None:
            raise HTTPException(status_code=404, detail="آژانس یافت نشد")
        today = utcnow().astimezone(TEHRAN).date()
        if data.period_end < data.period_start or data.period_end > today:
            raise HTTPException(status_code=422, detail="بازهٔ دوره نامعتبر است (پایان دوره نمی‌تواند بعد از امروز باشد)")
        rows = db.scalars(select(AgencySettlement).where(AgencySettlement.tenant_id == user.tenant_id, AgencySettlement.agency_id == agency.id,
                                                         AgencySettlement.status != "superseded").order_by(AgencySettlement.cutoff_at)).all()
        if any(r.status in ("issued", "accepted", "disputed") for r in rows):
            raise HTTPException(status_code=409, detail={"code": "PREVIOUS_STATEMENT_OPEN", "message": "صورت قبلی این آژانس هنوز تسویه نشده است"})
        settled = [r for r in rows if r.status == "settled"]
        prev = settled[-1] if settled else None
        if prev is not None and data.period_start < prev.period_end:
            raise HTTPException(status_code=422, detail="شروع دوره پیش از پایان صورت قبلی است")
        from_at = prev.cutoff_at if prev else None
        _, end = tehran_bounds(data.period_end)
        cutoff = min(end - timedelta(microseconds=1), utcnow())
        try:
            lines, opening, closing = build_lines(db, user.tenant_id, agency.id, from_at, cutoff)
        except LookupError as exc:
            raise HTTPException(status_code=422, detail={"code": "VAT_RATE_MISSING", "message": f"نرخ ارزش افزوده برای تاریخ فروش ثبت نشده است: {exc}"}) from exc
        for r in rows:
            if r.status == "draft":
                r.status = "superseded"
                event(db, r, "superseded", "finance", user.id, note="پیش‌نویس تازه جایگزین شد")
        n = db.scalar(select(func.count()).select_from(AgencySettlement).where(AgencySettlement.tenant_id == user.tenant_id, AgencySettlement.agency_id == agency.id)) or 0
        st = AgencySettlement(tenant_id=user.tenant_id, agency_id=agency.id, statement_no=f"ST-{agency.id[:6].upper()}-{data.period_end:%Y%m%d}-{n + 1}",
                              period_start=data.period_start, period_end=data.period_end, from_at=from_at, cutoff_at=cutoff, status="draft",
                              opening_balance_irr=opening, closing_balance_irr=closing, created_by_user_id=user.id)
        db.add(st)
        db.flush()
        for i, ln in enumerate(lines, start=1):
            db.add(AgencySettlementLine(tenant_id=user.tenant_id, settlement_id=st.id, line_no=i, line_type=ln["line_type"], amount_irr=ln["amount_irr"],
                                        description=ln["description"][:300], booking_line_id=ln.get("booking_line_id"), ledger_entry_id=ln.get("ledger_entry_id"),
                                        reservation_id=ln.get("reservation_id"), vat_rate_id=ln.get("vat_rate_id"), vat_rate_bps=ln.get("vat_rate_bps"),
                                        occurred_at=ln.get("occurred_at"), created_by_user_id=user.id))
        db.flush()
        recompute(db, st)
        event(db, st, "drafted", "finance", user.id, payload={"lines": len(lines), "net_irr": st.net_irr})
        audit(db, user, "agency.settlement.drafted", "agency_settlement", {"settlement_id": st.id, "agency_id": agency.id, "net_irr": st.net_irr})
        db.commit()
        return st_out(db, st, detail=True)

    @api.get("/finance/agency-settlements/{sid}")
    def fin_detail(sid: str, user=Depends(fin_reader), db: Session = Depends(get_db)) -> dict:
        st = statement(db, user.tenant_id, sid)
        out = st_out(db, st, detail=True)
        out["can_manage"] = role_has_permission(user.role, "settlement:manage")
        db.commit()
        return out

    @api.post("/finance/agency-settlements/{sid}/issue-request", status_code=202)
    def fin_issue(sid: str, data: NoteIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                  user=Depends(settler), db: Session = Depends(get_db)) -> dict:
        st = statement(db, user.tenant_id, sid, lock=True)
        if st.status != "draft":
            raise HTTPException(status_code=409, detail="فقط پیش‌نویس قابل صدور است")
        if st.issue_mc_request_id and mc_status(db, st.issue_mc_request_id) == "pending":
            prior = db.get(approvals.MakerCheckerRequest, st.issue_mc_request_id)
            if prior.idempotency_key == idempotency_key and prior.maker_user_id == user.id:
                return {"request_id": prior.id, "status": prior.status, "message": "درخواست صدور قبلاً ثبت شده است."}
            raise HTTPException(status_code=409, detail="درخواست صدور این صورت در انتظار تأیید است")
        r = mc(db, user, "agency.settlement_issue", {"settlement_id": st.id, "net_irr": st.net_irr, "note": data.note}, idempotency_key,
               f"صدور صورت تسویهٔ {st.statement_no}", st.net_irr, st.agency_id)
        st.issue_mc_request_id = r.id
        event(db, st, "issue_requested", "finance", user.id, note=data.note, payload={"mc_request_id": r.id})
        db.commit()
        return {"request_id": r.id, "status": r.status, "message": "درخواست صدور ثبت شد و پس از تأیید کارشناس مالی دوم اعمال می‌شود."}

    @api.post("/finance/agency-settlements/{sid}/settle-request", status_code=202)
    def fin_settle(sid: str, data: SettleIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                   user=Depends(settler), db: Session = Depends(get_db)) -> dict:
        st = statement(db, user.tenant_id, sid, lock=True)
        if st.status != "accepted":
            raise HTTPException(status_code=409, detail="فقط صورت پذیرفته‌شده توسط آژانس قابل تسویه است")
        if st.net_irr > 0 and not data.bank_reference:
            raise HTTPException(status_code=422, detail="برای دریافت مبلغ از آژانس، شمارهٔ پیگیری واریز بانکی لازم است")
        if st.settle_mc_request_id and mc_status(db, st.settle_mc_request_id) == "pending":
            prior = db.get(approvals.MakerCheckerRequest, st.settle_mc_request_id)
            if prior.idempotency_key == idempotency_key and prior.maker_user_id == user.id:
                return {"request_id": prior.id, "status": prior.status, "message": "درخواست تسویه قبلاً ثبت شده است."}
            raise HTTPException(status_code=409, detail="درخواست تسویهٔ این صورت در انتظار تأیید است")
        r = mc(db, user, "agency.settlement_settle", {"settlement_id": st.id, "net_irr": st.net_irr, "bank_reference": data.bank_reference,
                                                      "paid_on": _iso(data.paid_on), "note": data.note}, idempotency_key, f"تسویهٔ صورت {st.statement_no}", st.net_irr, st.agency_id)
        st.settle_mc_request_id = r.id
        event(db, st, "settle_requested", "finance", user.id, note=data.note, payload={"mc_request_id": r.id, "bank_reference": data.bank_reference})
        db.commit()
        return {"request_id": r.id, "status": r.status, "message": "درخواست تسویه ثبت شد و پس از تأیید کارشناس مالی دوم اعمال می‌شود."}

    @api.post("/finance/agency-settlements/{sid}/adjustments", status_code=202)
    def fin_adjust(sid: str, data: AdjustmentIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                   user=Depends(settler), db: Session = Depends(get_db)) -> dict:
        st = statement(db, user.tenant_id, sid, lock=True)
        if st.status not in ("issued", "accepted", "disputed"):
            raise HTTPException(status_code=409, detail="اصلاحیه فقط روی صورت صادرشده و تسویه‌نشده ثبت می‌شود")
        if data.amount_irr == 0:
            raise HTTPException(status_code=422, detail="مبلغ اصلاحیه صفر است")
        r = mc(db, user, "agency.settlement_adjustment", {"settlement_id": st.id, "amount_irr": data.amount_irr, "reason": data.reason, "dispute_id": None},
               idempotency_key, f"اصلاحیهٔ صورت {st.statement_no}", data.amount_irr, st.agency_id)
        event(db, st, "adjustment_requested", "finance", user.id, note=data.reason, payload={"mc_request_id": r.id, "amount_irr": data.amount_irr})
        db.commit()
        return {"request_id": r.id, "status": r.status, "message": "اصلاحیه پس از تأیید کارشناس مالی دوم به صورت اضافه می‌شود."}

    @api.get("/finance/agency-settlement-disputes")
    def fin_disputes(status: Optional[str] = Query(default="open", pattern="^(open|closed|all)$"), user=Depends(fin_reader), db: Session = Depends(get_db)) -> dict:
        q = select(AgencySettlementDispute).where(AgencySettlementDispute.tenant_id == user.tenant_id)
        if status == "open":
            q = q.where(AgencySettlementDispute.status.in_(("open", "adjustment_pending")))
        elif status == "closed":
            q = q.where(AgencySettlementDispute.status.in_(("accepted", "rejected")))
        rows = db.scalars(q.order_by(AgencySettlementDispute.created_at).limit(300)).all()
        nm = names(db, [d.opened_by_user_id for d in rows] + [d.resolved_by_user_id for d in rows])
        sts = {s.id: s for s in db.scalars(select(AgencySettlement).where(AgencySettlement.tenant_id == user.tenant_id, AgencySettlement.id.in_({d.settlement_id for d in rows})))} if rows else {}
        ags = {a.id: a.display_name for a in db.scalars(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id, m.Agency.id.in_({d.agency_id for d in rows})))} if rows else {}
        items = []
        for d in rows:
            if d.status == "adjustment_pending" and mc_status(db, d.mc_request_id) in ("rejected", "expired"):
                d.status = "open"
            o = dispute_out(db, d, nm)
            o.update({"statement_no": sts[d.settlement_id].statement_no if d.settlement_id in sts else None, "agency_name": ags.get(d.agency_id),
                      "age_hours": int((utcnow() - _aw(d.created_at)).total_seconds() // 3600)})
            items.append(o)
        db.commit()
        return {"items": items, "can_manage": role_has_permission(user.role, "settlement:manage")}

    @api.post("/finance/agency-settlement-disputes/{did}/resolve")
    def fin_resolve(did: str, data: ResolveIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                    user=Depends(settler), db: Session = Depends(get_db)) -> dict:
        d = db.scalar(select(AgencySettlementDispute).where(AgencySettlementDispute.id == did, AgencySettlementDispute.tenant_id == user.tenant_id).with_for_update())
        if d is None:
            raise HTTPException(status_code=404, detail="اعتراض یافت نشد")
        st = statement(db, user.tenant_id, d.settlement_id, lock=True)
        if d.status == "adjustment_pending" and mc_status(db, d.mc_request_id) in ("rejected", "expired"):
            d.status = "open"
        if d.status != "open":
            raise HTTPException(status_code=409, detail="این اعتراض باز نیست")
        if data.decision == "reject":
            d.status, d.resolution_note, d.resolved_by_user_id, d.resolved_at = "rejected", data.reason, user.id, utcnow()
            event(db, st, "dispute_rejected", "finance", user.id, note=data.reason, dispute_id=d.id)
            after_dispute_change(db, st, user.id)
            msg = "اعتراض رد شد"
        else:
            amount = d.claimed_amount_irr if data.adjustment_amount_irr is None else data.adjustment_amount_irr
            d.resolution_note, d.adjustment_amount_irr = data.reason, amount
            if amount > 0:
                r = mc(db, user, "agency.settlement_adjustment", {"settlement_id": st.id, "amount_irr": -amount, "reason": f"اعتراض پذیرفته‌شده: {data.reason}"[:300],
                                                                  "dispute_id": d.id}, idempotency_key, f"اصلاحیهٔ اعتراض صورت {st.statement_no}", -amount, st.agency_id)
                d.status, d.mc_request_id = "adjustment_pending", r.id
                event(db, st, "dispute_adjustment_requested", "finance", user.id, note=data.reason, dispute_id=d.id, payload={"mc_request_id": r.id, "amount_irr": -amount})
                msg = "پذیرش با اصلاحیه ثبت شد؛ اصلاحیه پس از تأیید کارشناس مالی دوم اعمال می‌شود."
            else:
                d.status, d.resolved_by_user_id, d.resolved_at = "accepted", user.id, utcnow()
                event(db, st, "dispute_accepted", "finance", user.id, note=data.reason, dispute_id=d.id, payload={"amount_irr": 0})
                after_dispute_change(db, st, user.id)
                msg = "اعتراض بدون اصلاحیه پذیرفته شد"
        notify_agency(db, st.tenant_id, st.agency_id, title=f"نتیجهٔ اعتراض صورت {st.statement_no}", message=msg, link=f"/agency/settlements/{st.id}",
                      event_type=f"agency_settlement.dispute_{d.status}", aggregate_type="agency_settlement_dispute", aggregate_id=d.id, key=f"asd:{d.id}:{d.status}")
        audit(db, user, f"agency.settlement.dispute_{data.decision}", "agency_settlement", {"settlement_id": st.id, "dispute_id": d.id, "status": d.status})
        db.commit()
        return {"dispute": dispute_out(db, d, names(db, [d.opened_by_user_id, d.resolved_by_user_id])), "statement_status": st.status, "message": msg}

    @api.get("/finance/agency-credit-refunds")
    def fin_credit_refunds(status: Optional[str] = Query(default=None, pattern="^(pending_approval|executed|rejected|expired)$"), user=Depends(fin_reader),
                           db: Session = Depends(get_db)) -> dict:
        rows = db.scalars(select(AgencyCreditRefund).where(AgencyCreditRefund.tenant_id == user.tenant_id).order_by(AgencyCreditRefund.created_at.desc()).limit(300)).all()
        items = [refund_out(db, r) for r in rows]
        if status:
            items = [i for i in items if i["status"] == status]
        ags = {a.id: a.display_name for a in db.scalars(select(m.Agency).where(m.Agency.tenant_id == user.tenant_id))}
        for i in items:
            i["agency_name"] = ags.get(i["agency_id"])
        db.commit()
        return {"items": items}

    @api.get("/finance/agency-credit-refunds/{rid}")
    def fin_credit_refund(rid: str, user=Depends(fin_reader), db: Session = Depends(get_db)) -> dict:
        """FIN-02c: what goes back to the agency credit, the agency's free credit before/after, and the effect on the period settlement
        (commission and its VAT reversed for the refunded part only). The approval itself is the maker-checker request."""
        from .agency_b2b import balances
        row = db.scalar(select(AgencyCreditRefund).where(AgencyCreditRefund.id == rid, AgencyCreditRefund.tenant_id == user.tenant_id))
        if row is None:
            raise HTTPException(status_code=404, detail="بازگشت به اعتبار یافت نشد")
        out = refund_out(db, row)
        line = db.get(AgencyBookingLine, row.booking_line_id)
        agency = db.get(m.Agency, row.agency_id)
        acc = balances(account_for(db, user.tenant_id, row.agency_id))
        rate = vat_rate_on(tehran_day(line.created_at), db, user.tenant_id)
        rev = half_up(line.commission_irr * row.amount_irr, line.net_irr) if line.net_irr else 0
        mc = db.get(approvals.MakerCheckerRequest, row.mc_request_id) if row.mc_request_id else None
        nm = names(db, [row.created_by_user_id, mc.checker_user_id if mc else None])
        free_before = acc["available_irr"] if row.status != "executed" else acc["available_irr"] - row.amount_irr
        out.update({"agency_name": agency.display_name if agency else None, "title": line.title, "units": line.units, "paid_from_credit_irr": line.net_irr,
                    "refundable_irr": row.amount_irr, "method": "agency_credit", "ledger_type": "REFUND",
                    "free_credit_before_irr": free_before, "free_credit_after_irr": free_before + row.amount_irr,
                    "settlement_effect": {"commission_bps": line.commission_bps, "commission_reversal_irr": rev, "vat_rate_bps": rate.rate_bps, "vat_rate_id": rate.id,
                                          "vat_reversal_irr": bps_of(rev, rate.rate_bps), "commission_kept_irr": line.commission_irr - rev,
                                          "vat_kept_irr": bps_of(line.commission_irr - rev, rate.rate_bps)},
                    "maker": nm.get(row.created_by_user_id), "maker_user_id": row.created_by_user_id, "checker": nm.get(mc.checker_user_id) if mc else None,
                    "mc_status": mc.status if mc else None, "note": row.note,
                    "can_approve": bool(mc and mc.status == "pending" and mc.maker_user_id != user.id and role_has_permission(user.role, "refund:manage")),
                    "destinations": [{"key": "agency_credit", "label": "بازگشت به اعتبار آژانس", "available": True, "detail": "آژانس با مسافر خودش تسویه می‌کند."},
                                     {"key": "agency_iban", "label": "واریز به شبای آژانس", "available": False, "detail": "هنوز پیاده نشده است؛ نیازمند تصمیم مالک (با دلیل و تأیید نفر دوم)."},
                                     {"key": "customer", "label": "کیف پول یا کارت مسافر", "available": False, "detail": "برای رزرو آژانسی مجاز نیست؛ مسافر مشتری آژانس است."}]})
        db.commit()
        return out

    @api.post("/finance/agency-credit-refunds/{rid}/requeue", status_code=202)
    def fin_requeue(rid: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        if not any(role_has_permission(user.role, p) for p in ("refund:manage", "service_request:decide", "inventory:publish")):
            raise HTTPException(status_code=403, detail="مجوز لازم وجود ندارد")
        row = db.scalar(select(AgencyCreditRefund).where(AgencyCreditRefund.id == rid, AgencyCreditRefund.tenant_id == user.tenant_id).with_for_update())
        if row is None:
            raise HTTPException(status_code=404, detail="بازگشت به اعتبار یافت نشد")
        if sync_refund_status(db, row).status not in ("rejected", "expired"):
            raise HTTPException(status_code=409, detail="فقط درخواست ردشده یا منقضی دوباره ارسال می‌شود")
        line = db.get(AgencyBookingLine, row.booking_line_id)
        if row.amount_irr > credit_remaining(db, line):
            raise HTTPException(status_code=409, detail="مبلغ از باقی‌ماندهٔ قابل برگشت بیشتر است")
        try:
            _request_credit_refund(db, row, user, audit)
        except approvals.MakerCheckerError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        db.commit()
        return refund_out(db, row)

    # ---- agency ---------------------------------------------------------------------------------------------------
    @api.get("/agency/{agency_id}/settlement-statements")
    def ag_list(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = owner_of(db, agency_id, user)
        rows = db.scalars(select(AgencySettlement).where(AgencySettlement.tenant_id == user.tenant_id, AgencySettlement.agency_id == agency.id,
                                                         AgencySettlement.status.notin_(("draft", "superseded"))).order_by(AgencySettlement.cutoff_at.desc())).all()
        refunds = db.scalars(select(AgencyCreditRefund).where(AgencyCreditRefund.tenant_id == user.tenant_id, AgencyCreditRefund.agency_id == agency.id)
                             .order_by(AgencyCreditRefund.created_at.desc()).limit(50)).all()
        out = {"member_role": role, "items": [st_out(db, x, agency_view=True) for x in rows], "credit_refunds": [refund_out(db, r) for r in refunds],
               "awaiting_action": sum(1 for x in rows if x.status == "issued")}
        db.commit()
        return out

    @api.get("/agency/{agency_id}/settlement-statements/{sid}")
    def ag_detail(agency_id: str, sid: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = owner_of(db, agency_id, user)
        st = statement(db, user.tenant_id, sid, agency_id=agency.id)
        if st.status == "superseded":
            raise HTTPException(status_code=404, detail="صورت تسویه یافت نشد")
        out = {**st_out(db, st, detail=True, agency_view=True), "member_role": role, "can_act": role == "owner" and st.status in ("issued", "disputed")}
        db.commit()
        return out

    @api.post("/agency/{agency_id}/settlement-statements/{sid}/accept")
    def ag_accept(agency_id: str, sid: str, data: NoteIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = owner_of(db, agency_id, user, write=True)
        st = statement(db, user.tenant_id, sid, agency_id=agency.id, lock=True)
        if st.status == "accepted":
            return st_out(db, st, agency_view=True)
        if st.status != "issued":
            raise HTTPException(status_code=409, detail="فقط صورت صادرشده و بدون اعتراض باز قابل تأیید است")
        st.status, st.accepted_at, st.accepted_by_user_id = "accepted", utcnow(), user.id
        event(db, st, "accepted", "agency", user.id, note=data.note)
        db.add(m.OutboxEvent(tenant_id=st.tenant_id, aggregate_type="agency_settlement", aggregate_id=st.id, event_type="agency_settlement.accepted",
                             payload_json=json.dumps({"agency_id": st.agency_id}), correlation_id=str(uuid.uuid4()), idempotency_key=f"ase-acc:{st.id}:{uuid.uuid4().hex[:8]}"))
        audit(db, user, "agency.settlement.accepted", "agency_settlement", {"settlement_id": st.id, "agency_id": agency.id})
        db.commit()
        return st_out(db, st, agency_view=True)

    @api.post("/agency/{agency_id}/settlement-statements/{sid}/disputes", status_code=201)
    def ag_dispute(agency_id: str, sid: str, data: DisputeIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = owner_of(db, agency_id, user, write=True)
        st = statement(db, user.tenant_id, sid, agency_id=agency.id, lock=True)
        if st.status not in ("issued", "disputed"):
            raise HTTPException(status_code=409, detail="اعتراض فقط روی صورت صادرشده و پذیرفته‌نشده ثبت می‌شود")
        line = db.scalar(select(AgencySettlementLine).where(AgencySettlementLine.id == data.line_id, AgencySettlementLine.tenant_id == user.tenant_id,
                                                            AgencySettlementLine.settlement_id == st.id))
        if line is None or line.line_type == "OPENING":
            raise HTTPException(status_code=404, detail="ردیف یافت نشد")
        if any(d.line_id == line.id and d.status in ("open", "adjustment_pending") for d in disputes_of(db, st)):
            raise HTTPException(status_code=409, detail="روی این ردیف اعتراض باز وجود دارد")
        d = AgencySettlementDispute(tenant_id=user.tenant_id, settlement_id=st.id, line_id=line.id, agency_id=agency.id, reason=data.reason.strip(),
                                    claimed_amount_irr=data.claimed_amount_irr, status="open", opened_by_user_id=user.id)
        db.add(d)
        db.flush()
        st.status = "disputed"
        event(db, st, "dispute_opened", "agency", user.id, note=data.reason.strip(), dispute_id=d.id, payload={"line_id": line.id, "claimed_amount_irr": data.claimed_amount_irr})
        db.add(m.OutboxEvent(tenant_id=st.tenant_id, aggregate_type="agency_settlement_dispute", aggregate_id=d.id, event_type="agency_settlement.dispute_opened",
                             payload_json=json.dumps({"settlement_id": st.id, "agency_id": agency.id, "claimed_amount_irr": data.claimed_amount_irr}),
                             correlation_id=str(uuid.uuid4()), idempotency_key=f"asd-open:{d.id}"))
        audit(db, user, "agency.settlement.dispute_opened", "agency_settlement", {"settlement_id": st.id, "dispute_id": d.id, "line_id": line.id})
        db.commit()
        return dispute_out(db, d, names(db, [user.id]))

    return api


__all__ = ["AgencySettlement", "AgencySettlementLine", "AgencySettlementDispute", "AgencySettlementEvent", "AgencyCreditRefund", "TABLES", "APPEND_ONLY",
           "agency_settlement_router", "queue_credit_refund", "credit_line_for_reservation", "credit_remaining", "post_entry", "notify_agency", "build_lines",
           "totals_of", "LEDGER_SIGN"]
