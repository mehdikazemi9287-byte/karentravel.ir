"""Applied markup / commission per booking, posted as revenue.

CheckLine's weak point was a commission field that stayed zero: the sale was
recorded but what the agency actually earned on it was not. Here, when a booking
is created with a commerce markup rule applied, the exact adjustment is stored
per reservation and service (net unit, sell unit, units, rule) and a revenue line
is posted to the treasury sub-ledger under the tenant itself:

- markup  -> credit  "revenue" (income)
- discount-> debit   "revenue" (discount given away)

Postings are idempotent (command_id markup:<reservation>) and run in a savepoint
so they can never break a booking. Amounts are integer IRR (or offer currency).
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .operations import OperationalMixin


class AppliedMarkup(OperationalMixin, Base):
    __tablename__ = "commerce_applied_markups"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    booking_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    service_type: Mapped[str] = mapped_column(String(48), index=True)
    rule_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    rule_title: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    effect: Mapped[str] = mapped_column(String(16))  # markup | discount
    units: Mapped[int] = mapped_column(Integer, default=1)
    net_unit: Mapped[int] = mapped_column(Integer)
    sell_unit: Mapped[int] = mapped_column(Integer)
    net_total: Mapped[int] = mapped_column(Integer)
    sell_total: Mapped[int] = mapped_column(Integer)
    markup_total: Mapped[int] = mapped_column(Integer)  # signed: negative for a discount
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    supplier_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    supplier_cost: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    treasury_entry_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reversed_entry_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reversed_reason: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "reservation_id", name="uq_applied_markup_reservation"),)


def markup_from_snapshot(commercial: Optional[dict], units: int) -> Optional[dict]:
    """commercial = snapshot["commercial_rule"] = {rule_id, net_unit, adjustment}; returns totals or None."""
    if not commercial:
        return None
    try:
        net_unit = int(commercial["net_unit"])
        adjustment = int(commercial["adjustment"])
    except (KeyError, TypeError, ValueError):
        return None
    units = max(1, int(units or 1))
    return {"rule_id": commercial.get("rule_id"), "net_unit": net_unit, "sell_unit": net_unit + adjustment, "units": units,
            "net_total": net_unit * units, "sell_total": (net_unit + adjustment) * units, "markup_total": adjustment * units,
            "effect": "discount" if adjustment < 0 else "markup"}


def record_markup(db: Session, *, tenant_id: int, reservation, commercial: Optional[dict], units: int, currency: str,
                  supplier_id: Optional[str] = None, supplier_cost: Optional[int] = None) -> Optional[AppliedMarkup]:
    """Store the applied markup of one booking and post it as revenue. Never raises."""
    calc = markup_from_snapshot(commercial, units)
    if calc is None:
        return None
    try:
        with db.begin_nested():
            existing = db.scalar(select(AppliedMarkup).where(AppliedMarkup.tenant_id == tenant_id, AppliedMarkup.reservation_id == reservation.id))
            if existing:
                return existing
            from .commerce import MarkupRule, post_treasury
            rule = db.scalar(select(MarkupRule).where(MarkupRule.id == calc["rule_id"], MarkupRule.tenant_id == tenant_id)) if calc["rule_id"] else None
            row = AppliedMarkup(tenant_id=tenant_id, reservation_id=reservation.id, booking_reference=reservation.booking_reference,
                                service_type=reservation.service_type, rule_id=calc["rule_id"], rule_title=rule.title if rule else None,
                                effect=calc["effect"], units=calc["units"], net_unit=calc["net_unit"], sell_unit=calc["sell_unit"],
                                net_total=calc["net_total"], sell_total=calc["sell_total"], markup_total=calc["markup_total"],
                                currency=currency, supplier_id=supplier_id, supplier_cost=supplier_cost)
            db.add(row)
            db.flush()
            amount = calc["markup_total"]
            if amount != 0:
                ref = reservation.booking_reference or reservation.id
                title = f" — {rule.title}" if rule else ""
                entry = post_treasury(db, tenant_id=tenant_id, command_id=f"markup:{reservation.id}", counterparty_type="company",
                                      counterparty_ref=f"tenant:{tenant_id}", counterparty_name="درآمد فروش",
                                      account_type="revenue", operation="markup" if amount > 0 else "discount",
                                      credit=amount if amount > 0 else 0, debit=-amount if amount < 0 else 0, currency=currency,
                                      contract_ref=ref, purchase_ref=reservation.id,
                                      description=("سود فروش" if amount > 0 else "تخفیف فروش") + f" {reservation.service_type} — رزرو {ref}{title}")
                row.treasury_entry_id = entry.id
            return row
    except Exception:  # pragma: no cover - a posting must never break a booking
        return None


REVERSING_STATUSES = frozenset({"cancelled", "failed", "expired", "refunded"})


def reverse_markup(db: Session, reservation, reason: str) -> Optional[AppliedMarkup]:
    """A booking that ends cancelled/failed/expired/refunded earned no markup: post the mirror entry. Idempotent, never raises.

    Uses the same command id as a manual reversal from the treasury book (reverse:<entry>), so a booking can never be reversed twice.
    """
    try:
        with db.begin_nested():
            row = db.scalar(select(AppliedMarkup).where(AppliedMarkup.tenant_id == reservation.tenant_id, AppliedMarkup.reservation_id == reservation.id))
            if row is None or row.reversed_entry_id:
                return row
            if row.treasury_entry_id:
                from .commerce import TreasuryEntry, post_treasury
                e = db.scalar(select(TreasuryEntry).where(TreasuryEntry.tenant_id == reservation.tenant_id, TreasuryEntry.id == row.treasury_entry_id))
                if e is not None:
                    rev = post_treasury(db, tenant_id=e.tenant_id, command_id=f"reverse:{e.id}", counterparty_type=e.counterparty_type, counterparty_ref=e.counterparty_ref,
                                        counterparty_name=e.counterparty_name, account_type=e.account_type, operation=e.operation, debit=e.credit, credit=e.debit,
                                        currency=e.currency, reversal_of_id=e.id, contract_ref=e.contract_ref, purchase_ref=e.purchase_ref,
                                        description=f"برگشت سود/تخفیف — رزرو {e.contract_ref or reservation.id} ({reason})")
                    row.reversed_entry_id = rev.id
            row.reversed_reason = reason
            return row
    except Exception:  # pragma: no cover - a posting must never block a status change
        return None


def _bounds(date_from: Optional[date], date_to: Optional[date]):
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else None
    end = datetime.combine(date_to, time.max, tzinfo=timezone.utc) if date_to else None
    return start, end


def markup_revenue_router(get_db, current_user, role_has_permission):
    api = APIRouter(tags=["commerce"])

    def finance_read(user=Depends(current_user)):
        if not (role_has_permission(user.role, "ledger:read") or role_has_permission(user.role, "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مالی لازم است")
        return user

    @api.get("/commerce/markup-revenue")
    def report(date_from: Optional[date] = None, date_to: Optional[date] = None, service_type: Optional[str] = Query(default=None, max_length=48),
               limit: int = Query(default=100, ge=1, le=500), user=Depends(finance_read), db: Session = Depends(get_db)):
        if date_from and date_to and date_from > date_to:
            raise HTTPException(status_code=422, detail="بازه‌ی تاریخ نامعتبر است")
        start, end = _bounds(date_from, date_to)
        s = select(AppliedMarkup).where(AppliedMarkup.tenant_id == user.tenant_id)
        if start: s = s.where(AppliedMarkup.created_at >= start)
        if end: s = s.where(AppliedMarkup.created_at <= end)
        if service_type: s = s.where(AppliedMarkup.service_type == service_type)
        rows = db.scalars(s.order_by(AppliedMarkup.created_at.desc())).all()
        by: dict[tuple[str, str], dict] = {}
        for r in rows:
            g = by.setdefault((r.service_type, r.currency), {"service_type": r.service_type, "currency": r.currency, "bookings": 0, "net_total": 0,
                                                            "sell_total": 0, "markup": 0, "discount": 0, "revenue": 0, "reversed": 0, "reversed_amount": 0})
            if r.reversed_reason:
                g["reversed"] += 1
                g["reversed_amount"] += r.markup_total
                continue
            g["bookings"] += 1
            g["net_total"] += r.net_total
            g["sell_total"] += r.sell_total
            if r.markup_total >= 0: g["markup"] += r.markup_total
            else: g["discount"] += -r.markup_total
            g["revenue"] += r.markup_total
        items = [{"id": r.id, "reservation_id": r.reservation_id, "booking_reference": r.booking_reference, "service_type": r.service_type,
                  "rule_id": r.rule_id, "rule_title": r.rule_title, "effect": r.effect, "units": r.units, "net_unit": r.net_unit, "sell_unit": r.sell_unit,
                  "markup_total": r.markup_total, "currency": r.currency, "posted": r.treasury_entry_id is not None,
                  "reversed": r.reversed_reason, "reversed_entry_id": r.reversed_entry_id,
                  "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows[:limit]]
        return {"by_service": sorted(by.values(), key=lambda g: -g["revenue"]), "items": items, "total": len(rows)}

    return api
