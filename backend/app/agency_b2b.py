"""Panels Phase 2 — B2B agency core (AG-02 profile & licences, AG-07 pricing, AG-15 wallet/credit, AG-20 users,
OPS-09 onboarding/verification, FIN credit operations).

Money rules (spec §3, 03-tax-b2b-research, 05-owner-legal-answers):
* Every amount is an integer rial; rates are basis points; rounding is half-up on integers (no float).
* The agency buys at its **net** price = the platform's server-side checked price (`PriceCheck.amount`).
* Commission = net × `Agency.commission_bps` (set by the platform, read-only for the agency; Figma AG-07 "از نرخ پایه").
* **VAT is charged on the commission only, never on the ticket fare** (AGENT model; the agency invoices its commission and
  the VAT on it). The rate comes from the dated schedule `VAT_RATE_SCHEDULE` below, not from a constant in the formula.
* The agency's own markup (its rules, AG-07) is added on top of net; the agency's customer price = net + markup. The
  platform never shows an agency the customer price set by *another* seller (owner default 1, OQ-O7).
* For flights, the customer price per passenger may not exceed the CAO price cap when one is configured for the route and
  date (owner L5: «سقف ما = سقف سازمان»); see `charter_blocks.PriceCap`. No cap configured = not checked, and said so.

Wallet / credit (AG-15): one `AgencyAccount` per agency: `balance` (prepaid money; may go negative down to the credit
limit), `credit_limit`, `held`. available = balance + credit_limit − held. Holds are taken with ONE conditional UPDATE
(`... WHERE balance + credit_limit − held >= amount`), so two concurrent bookings can never both spend the last credit.
Top-up, decrease and credit-limit changes only happen through maker-checker (`approvals.py`): the agency owner or a
finance user asks, a different finance user (`credit:fund`) approves; nothing moves before that.

Licence verification (owner L7): a licence is verified by staff (`license:verify`) against every registry its type needs —
national licence portal for all; CAO for flight (بند الف) and CAO online-sales; Cultural Heritage ministry for tours (بند ب),
MCTH online-sales and the Heritage licence. There is no registry API yet: staff look the licence up themselves and record
the result, method and inquiry reference. Nothing here calls an external registry or fabricates a result.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import approvals
from . import operations as m
from .database import Base
from .operations import OperationalMixin

# ------------------------------------------------------------------------------------------------ configuration
# VAT rate schedule (effective-dated; FIN-11 will move this into an admin-managed table). Source for every row:
# docs/product/panels/03-tax-b2b-research-1405-08-17.md §الف-۱ «نرخ»: 9% from 1400-10-13 (VAT law 1400); 10% in
# 1403 and 1404 (annual budget laws); 10% in 1405 — the 12% figure was only in the 1405 budget *bill* (secondary source
# zharfban.com, reviewed 1405-05-19); the final budget-law text still has to be confirmed by the accountant.
# Gregorian dates: 1400-10-13 = 2022-01-03, 1403-01-01 = 2024-03-20.
VAT_RATE_SCHEDULE: tuple[tuple[str, date, Optional[date], int, str], ...] = (
    ("IR-VAT-1400", date(2022, 1, 3), date(2024, 3, 19), 900, "قانون مالیات بر ارزش افزوده ۱۴۰۰ (۹٪)"),
    ("IR-VAT-1403", date(2024, 3, 20), None, 1000, "قوانین بودجهٔ ۱۴۰۳، ۱۴۰۴ و ۱۴۰۵ (۱۰٪؛ متن نهایی بودجهٔ ۱۴۰۵ نیازمند تأیید حسابدار)"),
)

LICENCE_TYPES: dict[str, str] = {"BAND_ALEF": "بند الف (بلیت هواپیما)", "BAND_BE": "بند ب (تور)", "ONLINE_SALES": "مجوز فروش آنلاین", "MIRAS": "مجوز وزارت میراث فرهنگی"}
REGISTRIES: dict[str, str] = {"national_portal": "درگاه ملی مجوزها", "cao": "سازمان هواپیمایی کشوری", "mcth": "وزارت میراث فرهنگی، گردشگری و صنایع‌دستی"}
AUTHORITIES = ("cao", "mcth")
CHECK_RESULTS = {"confirmed": "منطبق", "mismatch": "نامنطبق", "not_found": "یافت نشد"}
KYC_STATUSES = ("draft", "submitted", "active", "rejected", "suspended")
MEMBER_ROLES = {"owner": "مدیر آژانس", "agent": "کارشناس فروش آژانس"}
LEDGER_TYPES = ("TOPUP", "DECREASE", "HOLD", "CAPTURE", "RELEASE", "REFUND", "COMMISSION", "LIMIT_CHANGE")
SERVICE_SCOPES = ("any", "flight", "flight_charter", "hotel", "tour")


def required_registries(licence_type: str, authority: Optional[str]) -> tuple[str, ...]:
    """Owner L7 (05-owner-legal-answers): every licence on the national portal, plus its own issuer."""
    if licence_type == "BAND_ALEF":
        return ("national_portal", "cao")
    if licence_type in ("BAND_BE", "MIRAS"):
        return ("national_portal", "mcth")
    if licence_type == "ONLINE_SALES":
        return ("national_portal", authority if authority in AUTHORITIES else "cao")
    return ("national_portal",)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def half_up(numerator: int, denominator: int) -> int:
    """round(numerator / denominator) half away from zero, on integers only."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    return sign * ((abs(numerator) * 2 + denominator) // (2 * denominator))


def bps_of(amount: int, bps: int) -> int:
    return half_up(amount * bps, 10_000)


@dataclass(frozen=True)
class VatRate:
    id: str
    rate_bps: int
    legal_reference: str


def vat_rate_on(day: date) -> VatRate:
    for rid, start, end, bps, ref in VAT_RATE_SCHEDULE:
        if start <= day and (end is None or day <= end):
            return VatRate(rid, bps, ref)
    raise LookupError(f"no VAT rate configured for {day.isoformat()}")


_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def latin_digits(value: Optional[str]) -> Optional[str]:
    """Persian/Arabic digits become Latin before validation (lesson: never strip them as non-digits)."""
    return value.translate(_FA_DIGITS).strip() if isinstance(value, str) else value


# ------------------------------------------------------------------------------------------------ models
class AgencyProfile(OperationalMixin, Base):
    __tablename__ = "agency_profiles"
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    brand_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    national_id: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    economic_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    ceo_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    technical_manager: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    iban: Mapped[Optional[str]] = mapped_column(String(26), nullable=True)
    kyc_status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    kyc_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "agency_id", name="uq_agency_profile"),)


class AgencyLicence(OperationalMixin, Base):
    __tablename__ = "agency_licences"
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    licence_type: Mapped[str] = mapped_column(String(16), index=True)
    authority: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # ONLINE_SALES issuer: cao | mcth
    number: Mapped[str] = mapped_column(String(40))
    issued_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | verified | rejected (expired is derived)
    document_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    submitted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("tenant_id", "agency_id", "licence_type", "number", name="uq_agency_licence_number"),)


class AgencyLicenceCheck(OperationalMixin, Base):
    """Append-only: one row per manual registry check by staff."""
    __tablename__ = "agency_licence_checks"
    licence_id: Mapped[str] = mapped_column(ForeignKey("agency_licences.id"), index=True)
    registry: Mapped[str] = mapped_column(String(24))
    result: Mapped[str] = mapped_column(String(16))
    method: Mapped[str] = mapped_column(String(24), default="registry_lookup")  # registry_lookup | document_review
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    checked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class AgencyAccount(OperationalMixin, Base):
    __tablename__ = "agency_accounts"
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    balance_irr: Mapped[int] = mapped_column(Integer, default=0)
    credit_limit_irr: Mapped[int] = mapped_column(Integer, default=0)
    held_irr: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("tenant_id", "agency_id", name="uq_agency_account"),)


class AgencyLedgerEntry(OperationalMixin, Base):
    """Append-only movements of an agency account. Corrections are new entries."""
    __tablename__ = "agency_ledger_entries"
    account_id: Mapped[str] = mapped_column(ForeignKey("agency_accounts.id"), index=True)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    entry_type: Mapped[str] = mapped_column(String(16), index=True)
    amount_irr: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    held_after: Mapped[int] = mapped_column(Integer)
    limit_after: Mapped[int] = mapped_column(Integer)
    reservation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    booking_line_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    mc_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_agency_ledger_idempotency"),)


class AgencyMarkupRule(OperationalMixin, Base):
    __tablename__ = "agency_markup_rules"
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    service_scope: Mapped[str] = mapped_column(String(16), default="any")
    route: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)  # "IKA-IST"
    kind: Mapped[str] = mapped_column(String(8))  # pct | fixed
    value_bps: Mapped[int] = mapped_column(Integer, default=0)
    fixed_irr: Mapped[int] = mapped_column(Integer, default=0)  # per passenger/unit
    min_irr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # per unit
    max_irr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # per unit
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="active")


class AgencyBookingLine(OperationalMixin, Base):
    """Order-line financial snapshot of one booking an agency paid from its account (spec §3.1, channel fields)."""
    __tablename__ = "agency_booking_lines"
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    command_id: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str] = mapped_column(String(64))
    price_check_id: Mapped[str] = mapped_column(String(36))
    offer_id: Mapped[str] = mapped_column(String(36), index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    service_type: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(200), default="")
    units: Mapped[int] = mapped_column(Integer, default=1)
    net_irr: Mapped[int] = mapped_column(Integer)
    commission_bps: Mapped[int] = mapped_column(Integer)
    commission_irr: Mapped[int] = mapped_column(Integer)
    vat_rate_id: Mapped[str] = mapped_column(String(24))
    vat_rate_bps: Mapped[int] = mapped_column(Integer)
    vat_irr: Mapped[int] = mapped_column(Integer)
    markup_irr: Mapped[int] = mapped_column(Integer)
    markup_rule_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    customer_price_irr: Mapped[int] = mapped_column(Integer)
    price_cap_unit_irr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_cap_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    charter_quota_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="holding", index=True)  # holding | captured | released
    failure_reason: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    booked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("tenant_id", "agency_id", "command_id", name="uq_agency_booking_command"),)


TABLES = ("agency_profiles", "agency_licences", "agency_licence_checks", "agency_accounts", "agency_ledger_entries",
          "agency_markup_rules", "agency_booking_lines")
APPEND_ONLY = ("agency_licence_checks", "agency_ledger_entries")


# ------------------------------------------------------------------------------------------------ pure money math
def markup_for(rule: Optional[AgencyMarkupRule], unit_net: int, units: int) -> int:
    if rule is None:
        return 0
    unit = bps_of(unit_net, rule.value_bps) if rule.kind == "pct" else rule.fixed_irr
    if rule.min_irr is not None:
        unit = max(unit, rule.min_irr)
    if rule.max_irr is not None:
        unit = min(unit, rule.max_irr)
    return max(0, unit) * units


def compute_line(*, net_irr: int, units: int, commission_bps: int, vat: VatRate, markup_irr: int, cap_unit_irr: Optional[int]) -> dict:
    """The agency_buyer breakdown. Raises ValueError('PRICE_CAP_EXCEEDED') when the customer price per unit is above the cap."""
    if net_irr <= 0 or units <= 0 or markup_irr < 0 or not 0 <= commission_bps <= 10_000:
        raise ValueError("invalid amounts")
    commission = bps_of(net_irr, commission_bps)
    vat_on_commission = bps_of(commission, vat.rate_bps)  # VAT on the commission, never on the fare
    customer = net_irr + markup_irr
    out = {"net_irr": net_irr, "units": units, "commission_bps": commission_bps, "commission_irr": commission,
           "vat_rate_id": vat.id, "vat_rate_bps": vat.rate_bps, "vat_legal_reference": vat.legal_reference, "vat_irr": vat_on_commission,
           "commission_with_vat_irr": commission + vat_on_commission, "markup_irr": markup_irr, "customer_price_irr": customer,
           "agency_pays_irr": net_irr, "agency_income_irr": markup_irr + commission,
           "price_cap_unit_irr": cap_unit_irr, "price_cap_total_irr": cap_unit_irr * units if cap_unit_irr is not None else None,
           "price_cap_status": "not_configured" if cap_unit_irr is None else "within"}
    if cap_unit_irr is not None:
        out["max_markup_irr"] = max(0, cap_unit_irr * units - net_irr)
        if customer > cap_unit_irr * units:
            out["price_cap_status"] = "exceeded"
    return out


def request_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def safe_cell(value) -> object:
    """CSV formula-injection guard for text cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


# ------------------------------------------------------------------------------------------------ account primitives
class CreditError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def account_for(db: Session, tenant_id: int, agency_id: str, create: bool = False) -> Optional[AgencyAccount]:
    row = db.scalar(select(AgencyAccount).where(AgencyAccount.tenant_id == tenant_id, AgencyAccount.agency_id == agency_id))
    if row is None and create:
        row = AgencyAccount(tenant_id=tenant_id, agency_id=agency_id, currency="IRR", balance_irr=0, credit_limit_irr=0, held_irr=0, version=0)
        db.add(row)
        db.flush()
    return row


def balances(acc: Optional[AgencyAccount]) -> dict:
    if acc is None:
        return {"exists": False, "balance_irr": 0, "credit_limit_irr": 0, "held_irr": 0, "available_irr": 0, "used_irr": 0, "usage_bps": 0}
    used = max(0, -acc.balance_irr) + acc.held_irr
    return {"exists": True, "balance_irr": acc.balance_irr, "credit_limit_irr": acc.credit_limit_irr, "held_irr": acc.held_irr,
            "available_irr": acc.balance_irr + acc.credit_limit_irr - acc.held_irr, "used_irr": used,
            "usage_bps": half_up(used * 10_000, acc.credit_limit_irr) if acc.credit_limit_irr > 0 else 0}


def _entry(db: Session, acc: AgencyAccount, entry_type: str, amount: int, key: str, user_id: Optional[int], **extra) -> AgencyLedgerEntry:
    db.refresh(acc)
    e = AgencyLedgerEntry(tenant_id=acc.tenant_id, account_id=acc.id, agency_id=acc.agency_id, entry_type=entry_type, amount_irr=amount,
                          balance_after=acc.balance_irr, held_after=acc.held_irr, limit_after=acc.credit_limit_irr,
                          idempotency_key=key[:160], created_by_user_id=user_id, **extra)
    db.add(e)
    db.flush()
    return e


def _prior(db: Session, tenant_id: int, key: str) -> Optional[AgencyLedgerEntry]:
    return db.scalar(select(AgencyLedgerEntry).where(AgencyLedgerEntry.tenant_id == tenant_id, AgencyLedgerEntry.idempotency_key == key[:160]))


def hold(db: Session, acc: AgencyAccount, amount: int, *, key: str, user_id: Optional[int], **extra) -> AgencyLedgerEntry:
    """Atomic: one conditional UPDATE; a concurrent hold that would overdraw the credit updates 0 rows and is refused."""
    prior = _prior(db, acc.tenant_id, key)
    if prior is not None:
        return prior
    if amount <= 0:
        raise CreditError(422, "INVALID_AMOUNT", "مبلغ نامعتبر است")
    res = db.execute(update(AgencyAccount).where(AgencyAccount.id == acc.id, AgencyAccount.tenant_id == acc.tenant_id,
                                                 AgencyAccount.balance_irr + AgencyAccount.credit_limit_irr - AgencyAccount.held_irr >= amount)
                     .values(held_irr=AgencyAccount.held_irr + amount, version=AgencyAccount.version + 1).execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise CreditError(409, "INSUFFICIENT_CREDIT", "اعتبار قابل استفادهٔ آژانس برای این خرید کافی نیست")
    return _entry(db, acc, "HOLD", amount, key, user_id, **extra)


def release(db: Session, acc: AgencyAccount, amount: int, *, key: str, user_id: Optional[int], **extra) -> AgencyLedgerEntry:
    prior = _prior(db, acc.tenant_id, key)
    if prior is not None:
        return prior
    res = db.execute(update(AgencyAccount).where(AgencyAccount.id == acc.id, AgencyAccount.held_irr >= amount)
                     .values(held_irr=AgencyAccount.held_irr - amount, version=AgencyAccount.version + 1).execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise CreditError(409, "HOLD_MISMATCH", "مبلغ آزادسازی با مسدودی هم‌خوان نیست")
    return _entry(db, acc, "RELEASE", amount, key, user_id, **extra)


def capture(db: Session, acc: AgencyAccount, amount: int, *, key: str, user_id: Optional[int], **extra) -> AgencyLedgerEntry:
    prior = _prior(db, acc.tenant_id, key)
    if prior is not None:
        return prior
    res = db.execute(update(AgencyAccount).where(AgencyAccount.id == acc.id, AgencyAccount.held_irr >= amount)
                     .values(held_irr=AgencyAccount.held_irr - amount, balance_irr=AgencyAccount.balance_irr - amount, version=AgencyAccount.version + 1)
                     .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise CreditError(409, "HOLD_MISMATCH", "مبلغ کسر با مسدودی هم‌خوان نیست")
    return _entry(db, acc, "CAPTURE", amount, key, user_id, **extra)


def adjust(db: Session, acc: AgencyAccount, direction: str, amount: int, *, key: str, user_id: Optional[int], **extra) -> AgencyLedgerEntry:
    prior = _prior(db, acc.tenant_id, key)
    if prior is not None:
        return prior
    if amount <= 0:
        raise ValueError("مبلغ نامعتبر است")
    if direction == "topup":
        db.execute(update(AgencyAccount).where(AgencyAccount.id == acc.id).values(balance_irr=AgencyAccount.balance_irr + amount, version=AgencyAccount.version + 1)
                   .execution_options(synchronize_session=False))
        return _entry(db, acc, "TOPUP", amount, key, user_id, **extra)
    res = db.execute(update(AgencyAccount).where(AgencyAccount.id == acc.id, AgencyAccount.balance_irr + AgencyAccount.credit_limit_irr - AgencyAccount.held_irr >= amount)
                     .values(balance_irr=AgencyAccount.balance_irr - amount, version=AgencyAccount.version + 1).execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise ValueError("کاهش از ماندهٔ قابل استفادهٔ آژانس بیشتر است")
    return _entry(db, acc, "DECREASE", amount, key, user_id, **extra)


def set_limit(db: Session, acc: AgencyAccount, new_limit: int, *, key: str, user_id: Optional[int], **extra) -> AgencyLedgerEntry:
    prior = _prior(db, acc.tenant_id, key)
    if prior is not None:
        return prior
    if new_limit < 0:
        raise ValueError("سقف اعتبار نامعتبر است")
    res = db.execute(update(AgencyAccount).where(AgencyAccount.id == acc.id, AgencyAccount.balance_irr + new_limit - AgencyAccount.held_irr >= 0)
                     .values(credit_limit_irr=new_limit, version=AgencyAccount.version + 1).execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise ValueError("سقف تازه از اعتبار مصرف‌شده و مسدودشدهٔ آژانس کمتر است")
    return _entry(db, acc, "LIMIT_CHANGE", new_limit, key, user_id, **extra)


# ------------------------------------------------------------------------------------------------ maker-checker kinds
def _can_fund(role_has_permission):
    return lambda actor, payload: role_has_permission(actor.role, "credit:fund")


def _execute_adjust(db: Session, request, payload: dict, checker) -> dict:
    acc = account_for(db, request.tenant_id, payload["agency_id"], create=True)
    e = adjust(db, acc, payload["direction"], int(payload["amount_irr"]), key=f"mc:{request.id}", user_id=checker.id, mc_request_id=request.id,
               reference=payload.get("bank_reference"), note=(payload.get("reason") or "")[:300])
    return {"entry_id": e.id, "balance_after": e.balance_after}


def _execute_limit(db: Session, request, payload: dict, checker) -> dict:
    acc = account_for(db, request.tenant_id, payload["agency_id"], create=True)
    e = set_limit(db, acc, int(payload["new_limit_irr"]), key=f"mc:{request.id}", user_id=checker.id, mc_request_id=request.id, note=(payload.get("reason") or "")[:300])
    return {"entry_id": e.id, "limit_after": e.limit_after}


# ------------------------------------------------------------------------------------------------ schemas
class Strict(BaseModel):
    model_config = {"extra": "forbid"}


class ProfileIn(Strict):
    legal_name: Optional[str] = Field(default=None, max_length=200)
    brand_name: Optional[str] = Field(default=None, max_length=160)
    national_id: Optional[str] = Field(default=None, max_length=20)
    economic_code: Optional[str] = Field(default=None, max_length=20)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    ceo_name: Optional[str] = Field(default=None, max_length=120)
    technical_manager: Optional[str] = Field(default=None, max_length=120)
    iban: Optional[str] = Field(default=None, max_length=40)

    @field_validator("national_id", "economic_code", "postal_code", "iban", mode="before")
    @classmethod
    def _digits(cls, v):
        v = latin_digits(v)
        return v.replace(" ", "").replace("-", "").upper() if isinstance(v, str) else v

    @field_validator("national_id")
    @classmethod
    def _nid(cls, v):
        if v and not re.fullmatch(r"\d{11}", v):
            raise ValueError("شناسهٔ ملی شخص حقوقی ۱۱ رقم است")
        return v or None

    @field_validator("economic_code")
    @classmethod
    def _eco(cls, v):
        if v and not re.fullmatch(r"\d{11,14}", v):
            raise ValueError("شمارهٔ اقتصادی باید ۱۱ تا ۱۴ رقم باشد")
        return v or None

    @field_validator("postal_code")
    @classmethod
    def _postal(cls, v):
        if v and not re.fullmatch(r"\d{10}", v):
            raise ValueError("کد پستی ۱۰ رقم است")
        return v or None

    @field_validator("iban")
    @classmethod
    def _iban(cls, v):
        if v and not re.fullmatch(r"IR\d{24}", v):
            raise ValueError("شبا باید با IR و ۲۴ رقم باشد")
        return v or None


class LicenceIn(Strict):
    licence_type: str = Field(pattern="^(BAND_ALEF|BAND_BE|ONLINE_SALES|MIRAS)$")
    authority: Optional[str] = Field(default=None, pattern="^(cao|mcth)$")
    number: str = Field(min_length=2, max_length=40)
    issued_on: Optional[date] = None
    expires_on: date
    document_reference: Optional[str] = Field(default=None, max_length=200)
    attest: bool

    @field_validator("number", mode="before")
    @classmethod
    def _n(cls, v):
        return latin_digits(v)


class LicenceCheckIn(Strict):
    registry: str = Field(pattern="^(national_portal|cao|mcth)$")
    result: str = Field(pattern="^(confirmed|mismatch|not_found)$")
    method: str = Field(default="registry_lookup", pattern="^(registry_lookup|document_review)$")
    reference: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = Field(default=None, max_length=500)


class KycDecisionIn(Strict):
    decision: str = Field(pattern="^(approve|reject|suspend|reinstate)$")
    reason: Optional[str] = Field(default=None, max_length=500)


class MemberRoleIn(Strict):
    role: str = Field(pattern="^(owner|agent)$")


class StaffMemberIn(Strict):
    user_id: int = Field(gt=0)
    role: str = Field(default="agent", pattern="^(owner|agent)$")


class TopupRequestIn(Strict):
    amount_irr: int = Field(gt=0, le=10**12)
    bank_reference: str = Field(min_length=4, max_length=60)
    paid_on: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=300)


class AdjustIn(Strict):
    direction: str = Field(pattern="^(topup|decrease)$")
    amount_irr: int = Field(gt=0, le=10**12)
    reason: str = Field(min_length=3, max_length=300)
    bank_reference: Optional[str] = Field(default=None, max_length=60)


class LimitIn(Strict):
    new_limit_irr: int = Field(ge=0, le=10**13)
    reason: str = Field(min_length=3, max_length=300)


class MarkupRuleIn(Strict):
    priority: int = Field(default=100, ge=1, le=1000)
    service_scope: str = Field(default="any", pattern="^(any|flight|flight_charter|hotel|tour)$")
    route: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}-[A-Z]{3}$")
    kind: str = Field(pattern="^(pct|fixed)$")
    value_bps: int = Field(default=0, ge=0, le=5000)
    fixed_irr: int = Field(default=0, ge=0, le=10**10)
    min_irr: Optional[int] = Field(default=None, ge=0, le=10**10)
    max_irr: Optional[int] = Field(default=None, ge=0, le=10**10)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    status: str = Field(default="active", pattern="^(active|disabled)$")


class CreditBookingIn(Strict):
    price_check_id: str = Field(min_length=36, max_length=36)
    markup_irr: Optional[int] = Field(default=None, ge=0, le=10**11)
    command_id: str = Field(min_length=8, max_length=100)


class PreviewIn(Strict):
    price_check_id: str = Field(min_length=36, max_length=36)
    markup_irr: Optional[int] = Field(default=None, ge=0, le=10**11)


# ------------------------------------------------------------------------------------------------ outputs
def _iso(v) -> Optional[str]:
    return v.isoformat() if v is not None else None


def licence_out(lic: AgencyLicence, checks: list[AgencyLicenceCheck], today: Optional[date] = None) -> dict:
    today = today or utcnow().date()
    req = required_registries(lic.licence_type, lic.authority)
    latest: dict[str, AgencyLicenceCheck] = {}
    for c in sorted(checks, key=lambda c: (c.created_at or utcnow())):
        latest[c.registry] = c
    status = lic.status
    if lic.expires_on < today:
        status = "expired"
    days_left = (lic.expires_on - today).days
    return {"id": lic.id, "licence_type": lic.licence_type, "type_label": LICENCE_TYPES.get(lic.licence_type, lic.licence_type), "authority": lic.authority,
            "number": lic.number, "issued_on": _iso(lic.issued_on), "expires_on": _iso(lic.expires_on), "days_left": days_left, "status": status,
            "expiring_soon": status == "verified" and 0 <= days_left <= 30, "document_reference": lic.document_reference,
            "registries": [{"registry": r, "label": REGISTRIES[r], "result": latest[r].result if r in latest else None,
                            "result_label": CHECK_RESULTS.get(latest[r].result) if r in latest else "در انتظار بررسی",
                            "method": latest[r].method if r in latest else None, "reference": latest[r].reference if r in latest else None,
                            "checked_at": _iso(latest[r].created_at) if r in latest else None} for r in req],
            "submitted_at": _iso(lic.created_at)}


def derive_licence_status(lic: AgencyLicence, checks: list[AgencyLicenceCheck]) -> str:
    latest: dict[str, str] = {}
    for c in sorted(checks, key=lambda c: (c.created_at or utcnow())):
        latest[c.registry] = c.result
    req = required_registries(lic.licence_type, lic.authority)
    if any(latest.get(r) in ("mismatch", "not_found") for r in req):
        return "rejected"
    if all(latest.get(r) == "confirmed" for r in req):
        return "verified"
    return "pending"


def valid_licence_types(db: Session, tenant_id: int, agency_id: str, today: Optional[date] = None) -> set[str]:
    today = today or utcnow().date()
    rows = db.scalars(select(AgencyLicence).where(AgencyLicence.tenant_id == tenant_id, AgencyLicence.agency_id == agency_id, AgencyLicence.status == "verified",
                                                  AgencyLicence.expires_on >= today)).all()
    return {r.licence_type for r in rows}


def entry_out(e: AgencyLedgerEntry) -> dict:
    sign = {"TOPUP": 1, "DECREASE": -1, "CAPTURE": -1, "REFUND": 1, "COMMISSION": 1}.get(e.entry_type, 0)
    return {"id": e.id, "entry_type": e.entry_type, "amount_irr": e.amount_irr, "signed_amount_irr": sign * e.amount_irr if sign else None,
            "balance_after": e.balance_after, "held_after": e.held_after, "limit_after": e.limit_after, "reservation_id": e.reservation_id,
            "reference": e.reference, "note": e.note, "created_at": _iso(e.created_at)}


def line_out(line: AgencyBookingLine, booking_reference: Optional[str] = None, reservation_status: Optional[str] = None) -> dict:
    """agency_buyer view: net, commission, VAT on commission, own markup, own customer price. Never platform markup or supplier cost."""
    return {"id": line.id, "reservation_id": line.reservation_id, "booking_reference": booking_reference, "reservation_status": reservation_status,
            "service_type": line.service_type, "title": line.title, "units": line.units, "status": line.status,
            "breakdown": {"view": "agency_buyer", "net_irr": line.net_irr, "commission_bps": line.commission_bps, "commission_irr": line.commission_irr,
                          "vat_rate_id": line.vat_rate_id, "vat_rate_bps": line.vat_rate_bps, "vat_irr": line.vat_irr, "markup_irr": line.markup_irr,
                          "customer_price_irr": line.customer_price_irr, "agency_pays_irr": line.net_irr,
                          "price_cap_unit_irr": line.price_cap_unit_irr, "price_cap_reference": line.price_cap_reference},
            "failure_reason": line.failure_reason, "created_at": _iso(line.created_at)}


def agency_membership(db: Session, agency_id: str, user, role_has_permission, *, owner: bool = False) -> tuple[m.Agency, str]:
    """(agency, member role). Only members reach an agency (tenant admins read it as "staff"); everyone else gets 404."""
    agency = db.scalar(select(m.Agency).where(m.Agency.id == agency_id, m.Agency.tenant_id == user.tenant_id))
    if agency is None:
        raise HTTPException(status_code=404, detail="آژانس در دسترس این حساب نیست")
    if role_has_permission(user.role, "agency:manage") and not role_has_permission(user.role, "platform:manage"):
        mem = db.scalar(select(m.AgencyMembership).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.agency_id == agency.id,
                                                         m.AgencyMembership.user_id == user.id))
        if mem is None:
            raise HTTPException(status_code=404, detail="آژانس در دسترس این حساب نیست")
        role = mem.agency_role or "owner"
        if owner and role != "owner":
            raise HTTPException(status_code=403, detail="این اقدام فقط برای مدیر آژانس مجاز است")
        return agency, role
    if role_has_permission(user.role, "tenant:manage") and not owner:
        return agency, "staff"
    raise HTTPException(status_code=404, detail="آژانس در دسترس این حساب نیست")


# ------------------------------------------------------------------------------------------------ router
def agency_b2b_router(get_db, current_user, role_has_permission, User, audit: Callable, *, book: Callable, booking_input, transition: Callable) -> APIRouter:
    api = APIRouter(tags=["agency-b2b"])

    approvals.register("agency.wallet_adjust", can_check=_can_fund(role_has_permission), execute=_execute_adjust, label="شارژ یا کاهش حساب آژانس")
    approvals.register("agency.credit_limit", can_check=_can_fund(role_has_permission), execute=_execute_limit, label="تغییر سقف اعتبار آژانس")

    def is_tenant_admin(user) -> bool:
        return role_has_permission(user.role, "tenant:manage")

    def a(db, user, action: str, detail: dict) -> None:
        audit(db, user, action, "agency_b2b", detail)

    # ---- access ---------------------------------------------------------------------------------------------------
    def membership(db: Session, agency_id: str, user, *, owner: bool = False) -> tuple[m.Agency, str]:
        return agency_membership(db, agency_id, user, role_has_permission, owner=owner)

    def staff_reader(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("license:verify", "tenant:manage", "ledger:read", "backoffice:read")):
            raise HTTPException(status_code=403, detail="دسترسی کارکنان لازم است")
        return user

    def verifier(user=Depends(current_user)):
        if not role_has_permission(user.role, "license:verify"):
            raise HTTPException(status_code=403, detail="مجوز احراز مجوز آژانس لازم است")
        return user

    def funder(user=Depends(current_user)):
        if not role_has_permission(user.role, "credit:fund"):
            raise HTTPException(status_code=403, detail="مجوز عملیات اعتبار لازم است")
        return user

    def profile_for(db: Session, user_tenant: int, agency_id: str, create: bool = False) -> Optional[AgencyProfile]:
        row = db.scalar(select(AgencyProfile).where(AgencyProfile.tenant_id == user_tenant, AgencyProfile.agency_id == agency_id))
        if row is None and create:
            row = AgencyProfile(tenant_id=user_tenant, agency_id=agency_id, kyc_status="draft")
            db.add(row)
            db.flush()
        return row

    def licences_for(db: Session, tenant_id: int, agency_id: str) -> list[dict]:
        lics = db.scalars(select(AgencyLicence).where(AgencyLicence.tenant_id == tenant_id, AgencyLicence.agency_id == agency_id).order_by(AgencyLicence.created_at)).all()
        checks: dict[str, list] = {}
        if lics:
            for c in db.scalars(select(AgencyLicenceCheck).where(AgencyLicenceCheck.tenant_id == tenant_id, AgencyLicenceCheck.licence_id.in_([x.id for x in lics]))):
                checks.setdefault(c.licence_id, []).append(c)
        return [licence_out(x, checks.get(x.id, [])) for x in lics]

    def profile_out(p: Optional[AgencyProfile], masked: bool = False) -> dict:
        if p is None:
            return {"kyc_status": "draft", "complete": False}
        iban = p.iban
        if masked and iban:
            iban = iban[:4] + "…" + iban[-4:]
        fields = {k: getattr(p, k) for k in ("legal_name", "brand_name", "national_id", "economic_code", "postal_code", "ceo_name", "technical_manager")}
        complete = all(fields[k] for k in ("legal_name", "national_id", "economic_code", "postal_code", "ceo_name")) and bool(p.iban)
        return {**fields, "iban": iban, "kyc_status": p.kyc_status, "kyc_note": p.kyc_note, "submitted_at": _iso(p.submitted_at), "decided_at": _iso(p.decided_at), "complete": complete}

    def is_active(db: Session, tenant_id: int, agency_id: str) -> bool:
        p = profile_for(db, tenant_id, agency_id)
        return p is not None and p.kyc_status == "active"

    # ---- agency: identity -----------------------------------------------------------------------------------------
    @api.get("/agency/{agency_id}/b2b")
    def b2b_context(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = membership(db, agency_id, user)
        p = profile_for(db, user.tenant_id, agency.id)
        lic_types = sorted(valid_licence_types(db, user.tenant_id, agency.id))
        acc = account_for(db, user.tenant_id, agency.id)
        return {"agency": {"id": agency.id, "name": agency.display_name, "status": agency.status, "commission_bps": agency.commission_bps},
                "member_role": role, "member_role_label": MEMBER_ROLES.get(role, "کارکنان مجموعه"), "kyc_status": p.kyc_status if p else "draft",
                "valid_licence_types": lic_types, "can_book": bool(p and p.kyc_status == "active" and acc is not None),
                "can_charter": bool(p and p.kyc_status == "active" and "BAND_ALEF" in lic_types), "account": balances(acc),
                "vat": {"id": vat_rate_on(utcnow().date()).id, "rate_bps": vat_rate_on(utcnow().date()).rate_bps, "legal_reference": vat_rate_on(utcnow().date()).legal_reference}}

    @api.get("/agency/{agency_id}/profile")
    def get_profile(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = membership(db, agency_id, user)
        return {"agency_id": agency.id, "name": agency.display_name, "member_role": role, "profile": profile_out(profile_for(db, user.tenant_id, agency.id), masked=role == "agent"),
                "licences": licences_for(db, user.tenant_id, agency.id), "licence_types": LICENCE_TYPES, "registries": REGISTRIES,
                "publishing_rules": [{"what": "پرواز و چارتر", "needs": "BAND_ALEF"}, {"what": "تور", "needs": "BAND_BE"}]}

    @api.put("/agency/{agency_id}/profile")
    def put_profile(agency_id: str, data: ProfileIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user, owner=True)
        p = profile_for(db, user.tenant_id, agency.id, create=True)
        if p.kyc_status in ("submitted", "active", "suspended"):
            raise HTTPException(status_code=409, detail="پس از ارسال برای احراز، فیلدهای حقوقی فقط با درخواست تغییر و تأیید عملیات قابل ویرایش‌اند")
        before = profile_out(p)
        for k, v in data.model_dump().items():
            setattr(p, k, (v.strip() if isinstance(v, str) else v) or None)
        a(db, user, "agency.profile.updated", {"agency_id": agency.id, "changed": sorted(k for k, v in profile_out(p).items() if before.get(k) != v and k != "iban") + (["iban"] if before.get("iban") != p.iban else [])})
        db.commit()
        return profile_out(p)

    @api.post("/agency/{agency_id}/profile/submit")
    def submit_profile(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user, owner=True)
        p = profile_for(db, user.tenant_id, agency.id, create=True)
        if p.kyc_status not in ("draft", "rejected"):
            raise HTTPException(status_code=409, detail="پروفایل در وضعیت قابل ارسال نیست")
        if not profile_out(p)["complete"]:
            raise HTTPException(status_code=422, detail="نام حقوقی، شناسهٔ ملی، شمارهٔ اقتصادی، کد پستی، مدیرعامل و شبا لازم است")
        if not db.scalar(select(AgencyLicence.id).where(AgencyLicence.tenant_id == user.tenant_id, AgencyLicence.agency_id == agency.id).limit(1)):
            raise HTTPException(status_code=422, detail="دست‌کم یک مجوز ثبت کنید")
        p.kyc_status, p.submitted_at, p.kyc_note = "submitted", utcnow(), None
        a(db, user, "agency.kyc.submitted", {"agency_id": agency.id})
        db.commit()
        return profile_out(p)

    @api.post("/agency/{agency_id}/licences", status_code=201)
    def add_licence(agency_id: str, data: LicenceIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user, owner=True)
        if not data.attest:
            raise HTTPException(status_code=422, detail="تأیید مطابقت اطلاعات با مدرک لازم است")
        if data.expires_on <= utcnow().date():
            raise HTTPException(status_code=422, detail="تاریخ انقضای مجوز گذشته است")
        if data.issued_on and data.issued_on >= data.expires_on:
            raise HTTPException(status_code=422, detail="تاریخ صدور باید پیش از انقضا باشد")
        if data.licence_type == "ONLINE_SALES" and not data.authority:
            raise HTTPException(status_code=422, detail="مرجع صدور مجوز فروش آنلاین را انتخاب کنید")
        if db.scalar(select(AgencyLicence.id).where(AgencyLicence.tenant_id == user.tenant_id, AgencyLicence.agency_id == agency.id, AgencyLicence.licence_type == data.licence_type, AgencyLicence.number == data.number)):
            raise HTTPException(status_code=409, detail="این مجوز قبلاً ثبت شده است")
        lic = AgencyLicence(tenant_id=user.tenant_id, agency_id=agency.id, licence_type=data.licence_type, authority=data.authority if data.licence_type == "ONLINE_SALES" else None,
                            number=data.number.strip(), issued_on=data.issued_on, expires_on=data.expires_on, status="pending", document_reference=data.document_reference, submitted_by_user_id=user.id)
        db.add(lic)
        db.flush()
        a(db, user, "agency.licence.submitted", {"agency_id": agency.id, "licence_id": lic.id, "licence_type": lic.licence_type})
        db.commit()
        return licence_out(lic, [])

    # ---- agency: users --------------------------------------------------------------------------------------------
    @api.get("/agency/{agency_id}/members")
    def members(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = membership(db, agency_id, user)
        rows = db.scalars(select(m.AgencyMembership).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.agency_id == agency.id)).all()
        names = {u.id: u.name for u in db.scalars(select(User).where(User.tenant_id == user.tenant_id, User.id.in_([r.user_id for r in rows])))} if rows else {}
        return {"member_role": role, "roles": MEMBER_ROLES, "items": [{"user_id": r.user_id, "name": names.get(r.user_id), "role": (r.agency_role or "owner"),
                                                                       "role_label": MEMBER_ROLES.get((r.agency_role or "owner")), "is_me": r.user_id == user.id} for r in rows]}

    @api.put("/agency/{agency_id}/members/{member_user_id}/role")
    def set_member_role(agency_id: str, member_user_id: int, data: MemberRoleIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user, owner=True)
        row = db.scalar(select(m.AgencyMembership).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.agency_id == agency.id, m.AgencyMembership.user_id == member_user_id).with_for_update())
        if row is None:
            raise HTTPException(status_code=404, detail="کاربر عضو این آژانس نیست")
        if member_user_id == user.id and data.role != "owner":
            raise HTTPException(status_code=409, detail="مدیر آژانس نمی‌تواند نقش خودش را کاهش دهد")
        previous = row.agency_role
        row.agency_role = data.role
        a(db, user, "agency.member.role_changed", {"agency_id": agency.id, "user_id": member_user_id, "from": previous, "to": data.role})
        db.commit()
        return {"user_id": member_user_id, "role": data.role}

    # ---- agency: wallet / credit ----------------------------------------------------------------------------------
    def pending_requests(db: Session, tenant_id: int, agency_id: str) -> list[dict]:
        rows = db.scalars(select(approvals.MakerCheckerRequest).where(approvals.MakerCheckerRequest.tenant_id == tenant_id,
                                                                      approvals.MakerCheckerRequest.kind.in_(("agency.wallet_adjust", "agency.credit_limit")),
                                                                      approvals.MakerCheckerRequest.target_ref == f"agency:{agency_id}")
                          .order_by(approvals.MakerCheckerRequest.created_at.desc()).limit(20)).all()
        return [{"id": r.id, "kind": r.kind, "status": r.status, "summary": r.summary, "amount_irr": r.amount, "created_at": _iso(r.created_at), "decided_at": _iso(r.decided_at)} for r in rows]

    @api.get("/agency/{agency_id}/wallet")
    def wallet(agency_id: str, entry_type: Optional[str] = Query(default=None, pattern="^(TOPUP|DECREASE|HOLD|CAPTURE|RELEASE|REFUND|COMMISSION|LIMIT_CHANGE)$"),
               limit: int = Query(default=100, ge=1, le=500), user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = membership(db, agency_id, user)
        acc = account_for(db, user.tenant_id, agency.id)
        entries = []
        if acc is not None and role != "agent":
            q = select(AgencyLedgerEntry).where(AgencyLedgerEntry.tenant_id == user.tenant_id, AgencyLedgerEntry.account_id == acc.id)
            if entry_type:
                q = q.where(AgencyLedgerEntry.entry_type == entry_type)
            entries = [entry_out(e) for e in db.scalars(q.order_by(AgencyLedgerEntry.created_at.desc(), AgencyLedgerEntry.id.desc()).limit(limit))]
        return {"agency_id": agency.id, "member_role": role, "currency": "IRR", "balances": balances(acc), "entries": entries,
                "entries_visible": role != "agent", "requests": pending_requests(db, user.tenant_id, agency.id) if role != "agent" else []}

    @api.get("/agency/{agency_id}/wallet/statement.csv")
    def statement_csv(agency_id: str, date_from: Optional[date] = Query(default=None, alias="from"), date_to: Optional[date] = Query(default=None, alias="to"),
                      user=Depends(current_user), db: Session = Depends(get_db)) -> Response:
        agency, _ = membership(db, agency_id, user, owner=True)
        acc = account_for(db, user.tenant_id, agency.id)
        rows = []
        if acc is not None:
            q = select(AgencyLedgerEntry).where(AgencyLedgerEntry.tenant_id == user.tenant_id, AgencyLedgerEntry.account_id == acc.id)
            if date_from:
                q = q.where(AgencyLedgerEntry.created_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
            if date_to:
                q = q.where(AgencyLedgerEntry.created_at < datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc))
            rows = db.scalars(q.order_by(AgencyLedgerEntry.created_at, AgencyLedgerEntry.id).limit(10_000)).all()
        refs = {r.id: r.booking_reference for r in db.scalars(select(m.Reservation).where(m.Reservation.tenant_id == user.tenant_id, m.Reservation.id.in_({e.reservation_id for e in rows if e.reservation_id})))} if rows else {}
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["created_at_utc", "entry_type", "amount_irr", "signed_amount_irr", "balance_after_irr", "held_after_irr", "credit_limit_after_irr", "booking_reference", "reference", "note"])
        for e in rows:
            d = entry_out(e)
            w.writerow([d["created_at"], e.entry_type, e.amount_irr, d["signed_amount_irr"] if d["signed_amount_irr"] is not None else "", e.balance_after, e.held_after, e.limit_after,
                        safe_cell(refs.get(e.reservation_id) or ""), safe_cell(e.reference or ""), safe_cell(e.note or "")])
        a(db, user, "agency.statement.exported", {"agency_id": agency.id, "rows": len(rows)})
        db.commit()
        return Response(content=("﻿" + out.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="agency-statement-{agency.id[:8]}.csv"'})

    def _mc(db, user, kind, payload, key, summary, amount, agency_id):
        try:
            row = approvals.create_request(db, user=user, kind=kind, payload=payload, idempotency_key=key, summary=summary, amount=amount,
                                           target_ref=f"agency:{agency_id}", audit=audit)
        except approvals.MakerCheckerError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        db.commit()
        return {"request_id": row.id, "status": row.status, "kind": row.kind, "summary": row.summary, "amount_irr": row.amount,
                "message": "درخواست ثبت شد و پس از تأیید کارشناس مالی دوم اعمال می‌شود."}

    @api.post("/agency/{agency_id}/topup-requests", status_code=202)
    def topup_request(agency_id: str, data: TopupRequestIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                      user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user, owner=True)
        if not is_active(db, user.tenant_id, agency.id):
            raise HTTPException(status_code=409, detail="شارژ حساب پس از احراز و فعال شدن آژانس ممکن است")
        payload = {"agency_id": agency.id, "direction": "topup", "amount_irr": data.amount_irr, "bank_reference": data.bank_reference, "paid_on": _iso(data.paid_on),
                   "reason": (data.note or "واریز بانکی آژانس")[:300], "source": "agency_request"}
        return _mc(db, user, "agency.wallet_adjust", payload, idempotency_key, f"شارژ حساب {agency.display_name} با واریز بانکی", data.amount_irr, agency.id)

    @api.post("/agency/{agency_id}/credit-limit-requests", status_code=202)
    def limit_request(agency_id: str, data: LimitIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                      user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user, owner=True)
        if not is_active(db, user.tenant_id, agency.id):
            raise HTTPException(status_code=409, detail="درخواست سقف اعتبار پس از احراز و فعال شدن آژانس ممکن است")
        payload = {"agency_id": agency.id, "new_limit_irr": data.new_limit_irr, "reason": data.reason, "source": "agency_request"}
        return _mc(db, user, "agency.credit_limit", payload, idempotency_key, f"تغییر سقف اعتبار {agency.display_name}", data.new_limit_irr, agency.id)

    # ---- agency: pricing ------------------------------------------------------------------------------------------
    def rule_out(r: AgencyMarkupRule) -> dict:
        return {k: (_iso(getattr(r, k)) if k in ("valid_from", "valid_to") else getattr(r, k)) for k in
                ("id", "priority", "service_scope", "route", "kind", "value_bps", "fixed_irr", "min_irr", "max_irr", "valid_from", "valid_to", "status")}

    @api.get("/agency/{agency_id}/markup-rules")
    def list_rules(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = membership(db, agency_id, user)
        rows = db.scalars(select(AgencyMarkupRule).where(AgencyMarkupRule.tenant_id == user.tenant_id, AgencyMarkupRule.agency_id == agency.id).order_by(AgencyMarkupRule.priority, AgencyMarkupRule.created_at)).all()
        v = vat_rate_on(utcnow().date())
        return {"member_role": role, "contract": {"commission_bps": agency.commission_bps, "platform_markup_bps": agency.markup_bps, "vat_rate_bps": v.rate_bps, "vat_rate_id": v.id,
                                                   "vat_legal_reference": v.legal_reference, "read_only": True},
                "items": [rule_out(r) for r in rows]}

    def _validate_rule(data: MarkupRuleIn) -> None:
        if data.kind == "pct" and data.value_bps <= 0:
            raise HTTPException(status_code=422, detail="درصد markup باید بیشتر از صفر باشد")
        if data.kind == "fixed" and data.fixed_irr <= 0:
            raise HTTPException(status_code=422, detail="مبلغ ثابت markup باید بیشتر از صفر باشد")
        if data.min_irr is not None and data.max_irr is not None and data.min_irr > data.max_irr:
            raise HTTPException(status_code=422, detail="حداقل از حداکثر بیشتر است")
        if data.valid_from and data.valid_to and data.valid_from > data.valid_to:
            raise HTTPException(status_code=422, detail="بازهٔ تاریخ نامعتبر است")

    @api.post("/agency/{agency_id}/markup-rules", status_code=201)
    def create_rule(agency_id: str, data: MarkupRuleIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user, owner=True)
        _validate_rule(data)
        r = AgencyMarkupRule(tenant_id=user.tenant_id, agency_id=agency.id, **data.model_dump())
        db.add(r)
        db.flush()
        a(db, user, "agency.markup_rule.created", {"agency_id": agency.id, "rule": rule_out(r)})
        db.commit()
        return rule_out(r)

    @api.put("/agency/{agency_id}/markup-rules/{rule_id}")
    def update_rule(agency_id: str, rule_id: str, data: MarkupRuleIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user, owner=True)
        _validate_rule(data)
        r = db.scalar(select(AgencyMarkupRule).where(AgencyMarkupRule.id == rule_id, AgencyMarkupRule.tenant_id == user.tenant_id, AgencyMarkupRule.agency_id == agency.id))
        if r is None:
            raise HTTPException(status_code=404, detail="قاعده یافت نشد")
        before = rule_out(r)
        for k, v in data.model_dump().items():
            setattr(r, k, v)
        a(db, user, "agency.markup_rule.updated", {"agency_id": agency.id, "before": before, "after": rule_out(r)})
        db.commit()
        return rule_out(r)

    # ---- agency: booking on credit ----------------------------------------------------------------------------------
    def _scope_of(offer: m.Offer, attrs: dict) -> str:
        if offer.service_type == "flight":
            return "flight_charter" if str(attrs.get("flight_type") or attrs.get("fare_type")) == "charter" else "flight"
        return offer.service_type

    def pick_rule(db: Session, agency_id: str, tenant_id: int, offer: m.Offer, attrs: dict, day: date) -> Optional[AgencyMarkupRule]:
        scope = _scope_of(offer, attrs)
        route = f"{attrs.get('origin_code') or attrs.get('origin') or ''}-{attrs.get('destination_code') or attrs.get('destination') or ''}".upper()
        for r in db.scalars(select(AgencyMarkupRule).where(AgencyMarkupRule.tenant_id == tenant_id, AgencyMarkupRule.agency_id == agency_id, AgencyMarkupRule.status == "active")
                            .order_by(AgencyMarkupRule.priority, AgencyMarkupRule.created_at)):
            if r.service_scope not in ("any", scope) and not (r.service_scope == "flight" and scope == "flight_charter"):
                continue
            if r.route and r.route != route:
                continue
            if (r.valid_from and day < r.valid_from) or (r.valid_to and day > r.valid_to):
                continue
            return r
        return None

    def _check_context(db: Session, user, price_check_id: str):
        check = db.scalar(select(m.PriceCheck).where(m.PriceCheck.id == price_check_id, m.PriceCheck.tenant_id == user.tenant_id, m.PriceCheck.user_id == user.id))
        if check is None:
            raise HTTPException(status_code=404, detail="استعلام قیمت یافت نشد")
        expires = check.expires_at if check.expires_at.tzinfo else check.expires_at.replace(tzinfo=timezone.utc)
        if check.consumed_at is not None or expires <= utcnow():
            raise HTTPException(status_code=409, detail="استعلام قیمت منقضی یا مصرف شده است؛ دوباره استعلام کنید")
        if check.currency != "IRR":
            raise HTTPException(status_code=422, detail="خرید از حساب آژانس فقط برای قیمت ریالی ممکن است")
        offer = db.scalar(select(m.Offer).where(m.Offer.id == check.offer_id, m.Offer.tenant_id == user.tenant_id))
        if offer is None:
            raise HTTPException(status_code=404, detail="عرضه یافت نشد")
        return check, offer, json.loads(offer.attributes_json or "{}")

    def breakdown_for(db: Session, user, agency: m.Agency, check, offer, attrs, markup_override: Optional[int]) -> tuple[dict, Optional[AgencyMarkupRule], Optional[str]]:
        from .charter_blocks import applicable_cap  # lazy: charter_blocks imports this module
        today = utcnow().date()
        rule = pick_rule(db, agency.id, user.tenant_id, offer, attrs, today)
        unit_net = check.amount // max(1, check.units)
        if markup_override is not None:
            if rule is not None:
                lo = (rule.min_irr or 0) * check.units
                hi = rule.max_irr * check.units if rule.max_irr is not None else None
                if markup_override < lo or (hi is not None and markup_override > hi):
                    raise HTTPException(status_code=422, detail={"code": "MARKUP_OUT_OF_RULE", "message": "markup این سفارش خارج از حداقل و حداکثر قاعدهٔ شماست", "min_irr": lo, "max_irr": hi})
            markup = markup_override
        else:
            markup = markup_for(rule, unit_net, check.units)
        cap, cap_ref = (applicable_cap(db, user.tenant_id, attrs) if offer.service_type == "flight" else (None, None))
        out = compute_line(net_irr=check.amount, units=check.units, commission_bps=agency.commission_bps, vat=vat_rate_on(today), markup_irr=markup, cap_unit_irr=cap)
        out["price_cap_reference"] = cap_ref
        out["markup_rule_id"] = rule.id if rule else None
        out["markup_source"] = "override" if markup_override is not None else ("rule" if rule else "none")
        return out, rule, cap_ref

    @api.post("/agency/{agency_id}/credit-bookings/preview")
    def preview(agency_id: str, data: PreviewIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user)
        check, offer, attrs = _check_context(db, user, data.price_check_id)
        out, _, _ = breakdown_for(db, user, agency, check, offer, attrs, data.markup_irr)
        acc = account_for(db, user.tenant_id, agency.id)
        return {"view": "agency_buyer", "title": offer.title, "service_type": offer.service_type, "breakdown": out, "account": balances(acc),
                "sufficient_credit": bool(acc is not None and balances(acc)["available_irr"] >= out["net_irr"])}

    @api.post("/agency/{agency_id}/credit-bookings", status_code=201)
    def credit_booking(agency_id: str, data: CreditBookingIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, role = membership(db, agency_id, user)
        if role == "staff":
            raise HTTPException(status_code=403, detail="خرید به نام آژانس فقط برای اعضای آژانس است")
        h = request_hash({"price_check_id": data.price_check_id, "markup_irr": data.markup_irr})
        prior = db.scalar(select(AgencyBookingLine).where(AgencyBookingLine.tenant_id == user.tenant_id, AgencyBookingLine.agency_id == agency.id, AgencyBookingLine.command_id == data.command_id))
        if prior is not None:
            if prior.request_hash != h:
                raise HTTPException(status_code=409, detail="این شناسهٔ درخواست قبلاً با محتوای دیگری استفاده شده است")
            res = db.get(m.Reservation, prior.reservation_id) if prior.reservation_id else None
            return line_out(prior, res.booking_reference if res else None, res.status if res else None)
        if not is_active(db, user.tenant_id, agency.id):
            raise HTTPException(status_code=409, detail={"code": "AGENCY_NOT_ACTIVE", "message": "آژانس هنوز احراز و فعال نشده است"})
        acc = account_for(db, user.tenant_id, agency.id)
        if acc is None:
            raise HTTPException(status_code=409, detail={"code": "NO_ACCOUNT", "message": "برای این آژانس حساب اعتبار تعریف نشده است"})
        check, offer, attrs = _check_context(db, user, data.price_check_id)
        out, rule, cap_ref = breakdown_for(db, user, agency, check, offer, attrs, data.markup_irr)
        if out["price_cap_status"] == "exceeded":
            raise HTTPException(status_code=422, detail={"code": "PRICE_CAP_EXCEEDED", "message": "قیمت به مشتری از سقف سازمان هواپیمایی بیشتر می‌شود",
                                                         "price_cap_total_irr": out["price_cap_total_irr"], "max_markup_irr": out.get("max_markup_irr")})
        line = AgencyBookingLine(tenant_id=user.tenant_id, agency_id=agency.id, command_id=data.command_id, request_hash=h, price_check_id=check.id, offer_id=offer.id,
                                 service_type=offer.service_type, title=offer.title[:200], units=check.units, net_irr=out["net_irr"], commission_bps=out["commission_bps"],
                                 commission_irr=out["commission_irr"], vat_rate_id=out["vat_rate_id"], vat_rate_bps=out["vat_rate_bps"], vat_irr=out["vat_irr"],
                                 markup_irr=out["markup_irr"], markup_rule_id=out["markup_rule_id"], customer_price_irr=out["customer_price_irr"],
                                 price_cap_unit_irr=out["price_cap_unit_irr"], price_cap_reference=cap_ref, status="holding", booked_by_user_id=user.id)
        db.add(line)
        db.flush()
        try:
            hold(db, acc, line.net_irr, key=f"agb-hold:{line.id}", user_id=user.id, booking_line_id=line.id, note=offer.title[:300])
        except CreditError as exc:
            db.rollback()
            raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message}) from exc
        # Seats this agency holds on the flight (charter allocation / quota) go to its own booking first.
        from .charter_blocks import take_agency_quota
        line.charter_quota_id = take_agency_quota(db, user.tenant_id, agency.id, attrs, check.units)
        a(db, user, "agency.credit_booking.held", {"agency_id": agency.id, "line_id": line.id, "net_irr": line.net_irr})
        db.commit()
        line_id = line.id
        try:
            booked = book(booking_input(price_check_id=check.id, command_id=f"agb:{line_id}"), user, db)
        except Exception as exc:
            db.rollback()
            line = db.get(AgencyBookingLine, line_id)
            acc = account_for(db, user.tenant_id, agency.id)
            release(db, acc, line.net_irr, key=f"agb-release:{line.id}", user_id=user.id, booking_line_id=line.id, note="رزرو ثبت نشد")
            line.status, line.failure_reason = "released", str(getattr(exc, "detail", "") or type(exc).__name__)[:300]
            a(db, user, "agency.credit_booking.released", {"agency_id": agency.id, "line_id": line.id, "reason": line.failure_reason})
            db.commit()
            raise
        line = db.get(AgencyBookingLine, line_id)
        acc = account_for(db, user.tenant_id, agency.id)
        reservation = db.scalar(select(m.Reservation).where(m.Reservation.id == booked["id"], m.Reservation.tenant_id == user.tenant_id))
        capture(db, acc, line.net_irr, key=f"agb-capture:{line.id}", user_id=user.id, booking_line_id=line.id, reservation_id=reservation.id, reference=reservation.booking_reference)
        line.reservation_id, line.status = reservation.id, "captured"
        transition(db, reservation, "confirmed", user.id, f"agency-credit:{line.id}")
        a(db, user, "agency.credit_booking.captured", {"agency_id": agency.id, "line_id": line.id, "reservation_id": reservation.id, "net_irr": line.net_irr,
                                                       "commission_irr": line.commission_irr, "vat_irr": line.vat_irr, "markup_irr": line.markup_irr})
        db.commit()
        return line_out(line, reservation.booking_reference, reservation.status)

    @api.get("/agency/{agency_id}/credit-bookings")
    def credit_bookings(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        agency, _ = membership(db, agency_id, user)
        rows = db.scalars(select(AgencyBookingLine).where(AgencyBookingLine.tenant_id == user.tenant_id, AgencyBookingLine.agency_id == agency.id)
                          .order_by(AgencyBookingLine.created_at.desc()).limit(300)).all()
        res = {r.id: r for r in db.scalars(select(m.Reservation).where(m.Reservation.tenant_id == user.tenant_id, m.Reservation.id.in_({x.reservation_id for x in rows if x.reservation_id})))} if rows else {}
        return {"items": [line_out(x, res[x.reservation_id].booking_reference if x.reservation_id in res else None, res[x.reservation_id].status if x.reservation_id in res else None) for x in rows]}

    @api.get("/agency/{agency_id}/invoices")
    def invoices(agency_id: str, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        """Commission invoice lines (agency → platform, B2B type 1): commission + VAT on it. Drafts until finance settles them;
        nothing is sent to the Moadian system from here (phase 5)."""
        agency, role = membership(db, agency_id, user)
        if role == "agent":
            raise HTTPException(status_code=403, detail="صورتحساب‌ها فقط برای مدیر آژانس است")
        rows = db.scalars(select(AgencyBookingLine).where(AgencyBookingLine.tenant_id == user.tenant_id, AgencyBookingLine.agency_id == agency.id, AgencyBookingLine.status == "captured")
                          .order_by(AgencyBookingLine.created_at.desc()).limit(500)).all()
        refs = {r.id: r.booking_reference for r in db.scalars(select(m.Reservation).where(m.Reservation.tenant_id == user.tenant_id, m.Reservation.id.in_({x.reservation_id for x in rows})))} if rows else {}
        items = [{"line_id": x.id, "booking_reference": refs.get(x.reservation_id), "title": x.title, "date": _iso(x.created_at), "commission_irr": x.commission_irr,
                  "vat_rate_bps": x.vat_rate_bps, "vat_rate_id": x.vat_rate_id, "vat_irr": x.vat_irr, "total_irr": x.commission_irr + x.vat_irr, "status": "draft",
                  "status_label": "پیش‌نویس، در انتظار تسویه"} for x in rows]
        return {"pattern": "B2B نوع اول — کمیسیون آژانس", "moadian": "not_sent", "items": items,
                "totals": {"commission_irr": sum(i["commission_irr"] for i in items), "vat_irr": sum(i["vat_irr"] for i in items), "total_irr": sum(i["total_irr"] for i in items)}}

    # ---- staff: onboarding & verification (OPS-09) ---------------------------------------------------------------
    @api.get("/staff/agencies")
    def staff_agencies(user=Depends(staff_reader), db: Session = Depends(get_db)) -> dict:
        t = user.tenant_id
        agencies = db.scalars(select(m.Agency).where(m.Agency.tenant_id == t).order_by(m.Agency.created_at.desc())).all()
        profiles = {p.agency_id: p for p in db.scalars(select(AgencyProfile).where(AgencyProfile.tenant_id == t))}
        accounts = {x.agency_id: x for x in db.scalars(select(AgencyAccount).where(AgencyAccount.tenant_id == t))}
        items = []
        for ag in agencies:
            lics = licences_for(db, t, ag.id)
            p = profiles.get(ag.id)
            items.append({"id": ag.id, "name": ag.display_name, "status": ag.status, "commission_bps": ag.commission_bps, "profile": profile_out(p, masked=True),
                          "licences": lics, "pending_checks": sum(1 for x in lics for r in x["registries"] if r["result"] is None),
                          "account": balances(accounts.get(ag.id))})
        queue = [x for x in items if x["profile"]["kyc_status"] == "submitted" or x["pending_checks"]]
        return {"items": items, "summary": {"in_queue": len(queue), "expiring_30d": sum(1 for x in items for l in x["licences"] if l["expiring_soon"]),
                                            "suspended": sum(1 for x in items if x["profile"]["kyc_status"] == "suspended")},
                "registries": REGISTRIES, "can_verify": role_has_permission(user.role, "license:verify"), "registry_api": "not_connected"}

    @api.get("/staff/agencies/{agency_id}")
    def staff_agency(agency_id: str, user=Depends(staff_reader), db: Session = Depends(get_db)) -> dict:
        ag = db.scalar(select(m.Agency).where(m.Agency.id == agency_id, m.Agency.tenant_id == user.tenant_id))
        if ag is None:
            raise HTTPException(status_code=404, detail="آژانس یافت نشد")
        events = db.execute(select(_audit_model()).where(_audit_model().tenant_id == user.tenant_id, _audit_model().entity == "agency_b2b",
                                                         _audit_model().detail.contains(agency_id)).order_by(_audit_model().created_at.desc()).limit(50)).scalars().all()
        return {"id": ag.id, "name": ag.display_name, "profile": profile_out(profile_for(db, user.tenant_id, ag.id)), "licences": licences_for(db, user.tenant_id, ag.id),
                "account": balances(account_for(db, user.tenant_id, ag.id)),
                "audit": [{"action": e.action, "actor_id": e.actor_id, "at": _iso(e.created_at)} for e in events]}

    @api.post("/staff/agencies/{agency_id}/licences/{licence_id}/checks", status_code=201)
    def record_check(agency_id: str, licence_id: str, data: LicenceCheckIn, user=Depends(verifier), db: Session = Depends(get_db)) -> dict:
        lic = db.scalar(select(AgencyLicence).where(AgencyLicence.id == licence_id, AgencyLicence.agency_id == agency_id, AgencyLicence.tenant_id == user.tenant_id).with_for_update())
        if lic is None:
            raise HTTPException(status_code=404, detail="مجوز یافت نشد")
        if data.registry not in required_registries(lic.licence_type, lic.authority):
            raise HTTPException(status_code=422, detail="این مرجع برای این نوع مجوز لازم نیست")
        if data.method == "registry_lookup" and not (data.reference or "").strip():
            raise HTTPException(status_code=422, detail="شمارهٔ پیگیری استعلام از مرجع را وارد کنید")
        db.add(AgencyLicenceCheck(tenant_id=user.tenant_id, licence_id=lic.id, registry=data.registry, result=data.result, method=data.method,
                                  reference=(data.reference or "").strip() or None, note=data.note, checked_by_user_id=user.id))
        db.flush()
        checks = db.scalars(select(AgencyLicenceCheck).where(AgencyLicenceCheck.tenant_id == user.tenant_id, AgencyLicenceCheck.licence_id == lic.id)).all()
        before, lic.status = lic.status, derive_licence_status(lic, checks)
        a(db, user, "agency.licence.checked", {"agency_id": agency_id, "licence_id": lic.id, "registry": data.registry, "result": data.result, "method": data.method,
                                               "status_before": before, "status_after": lic.status})
        db.commit()
        return licence_out(lic, checks)

    @api.post("/staff/agencies/{agency_id}/kyc")
    def kyc_decision(agency_id: str, data: KycDecisionIn, user=Depends(verifier), db: Session = Depends(get_db)) -> dict:
        ag = db.scalar(select(m.Agency).where(m.Agency.id == agency_id, m.Agency.tenant_id == user.tenant_id))
        if ag is None:
            raise HTTPException(status_code=404, detail="آژانس یافت نشد")
        p = profile_for(db, user.tenant_id, ag.id, create=True)
        allowed = {"approve": ("submitted",), "reject": ("submitted",), "suspend": ("active",), "reinstate": ("suspended",)}[data.decision]
        if p.kyc_status not in allowed:
            raise HTTPException(status_code=409, detail="این تصمیم در وضعیت فعلی پروفایل ممکن نیست")
        if data.decision in ("reject", "suspend") and not (data.reason or "").strip():
            raise HTTPException(status_code=422, detail="دلیل لازم است")
        if data.decision in ("approve", "reinstate"):
            if not profile_out(p)["complete"]:
                raise HTTPException(status_code=422, detail="پروفایل حقوقی کامل نیست")
            if not valid_licence_types(db, user.tenant_id, ag.id):
                raise HTTPException(status_code=422, detail="دست‌کم یک مجوز معتبر و احرازشده در همهٔ مراجع لازم است")
        before = p.kyc_status
        p.kyc_status = {"approve": "active", "reject": "rejected", "suspend": "suspended", "reinstate": "active"}[data.decision]
        p.kyc_note, p.decided_by_user_id, p.decided_at = (data.reason or None), user.id, utcnow()
        if p.kyc_status == "active":
            account_for(db, user.tenant_id, ag.id, create=True)
        a(db, user, f"agency.kyc.{data.decision}", {"agency_id": ag.id, "from": before, "to": p.kyc_status, "reason": data.reason})
        db.commit()
        return profile_out(p)

    @api.put("/staff/agencies/{agency_id}/members")
    def staff_member(agency_id: str, data: StaffMemberIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        if not is_tenant_admin(user):
            raise HTTPException(status_code=403, detail="مدیریت مجموعه لازم است")
        ag = db.scalar(select(m.Agency).where(m.Agency.id == agency_id, m.Agency.tenant_id == user.tenant_id))
        target = db.scalar(select(User).where(User.id == data.user_id, User.tenant_id == user.tenant_id))
        if ag is None or target is None or not role_has_permission(target.role, "agency:manage") or role_has_permission(target.role, "platform:manage"):
            raise HTTPException(status_code=422, detail="آژانس یا کاربر آژانسی در این مجموعه یافت نشد")
        row = db.scalar(select(m.AgencyMembership).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.agency_id == ag.id, m.AgencyMembership.user_id == target.id))
        if row is None:
            row = m.AgencyMembership(tenant_id=user.tenant_id, agency_id=ag.id, user_id=target.id, agency_role=data.role)
            db.add(row)
        else:
            row.agency_role = data.role
        a(db, user, "agency.member.set", {"agency_id": ag.id, "user_id": target.id, "role": data.role})
        db.commit()
        return {"agency_id": ag.id, "user_id": target.id, "role": data.role}

    # ---- finance: credit operations (always maker-checker) --------------------------------------------------------
    @api.get("/finance/agency-accounts")
    def finance_accounts(user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        if not any(role_has_permission(user.role, p) for p in ("credit:fund", "ledger:read")):
            raise HTTPException(status_code=403, detail="دسترسی مالی لازم است")
        t = user.tenant_id
        agencies = db.scalars(select(m.Agency).where(m.Agency.tenant_id == t).order_by(m.Agency.display_name)).all()
        accounts = {x.agency_id: x for x in db.scalars(select(AgencyAccount).where(AgencyAccount.tenant_id == t))}
        profiles = {p.agency_id: p.kyc_status for p in db.scalars(select(AgencyProfile).where(AgencyProfile.tenant_id == t))}
        reqs = approvals.list_requests(db, user=user, status=None, audit=audit)
        reqs = [r for r in reqs if r["kind"] in ("agency.wallet_adjust", "agency.credit_limit")]
        db.commit()
        return {"items": [{"agency_id": ag.id, "name": ag.display_name, "kyc_status": profiles.get(ag.id, "draft"), **balances(accounts.get(ag.id))} for ag in agencies],
                "requests": reqs, "can_request": role_has_permission(user.role, "credit:fund")}

    def _finance_agency(db, user, agency_id) -> m.Agency:
        ag = db.scalar(select(m.Agency).where(m.Agency.id == agency_id, m.Agency.tenant_id == user.tenant_id))
        if ag is None:
            raise HTTPException(status_code=404, detail="آژانس یافت نشد")
        if not is_active(db, user.tenant_id, ag.id):
            raise HTTPException(status_code=409, detail="حساب فقط برای آژانس احرازشده و فعال قابل تغییر است")
        return ag

    @api.post("/finance/agency-accounts/{agency_id}/adjustments", status_code=202)
    def finance_adjust(agency_id: str, data: AdjustIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                       user=Depends(funder), db: Session = Depends(get_db)) -> dict:
        ag = _finance_agency(db, user, agency_id)
        payload = {"agency_id": ag.id, "direction": data.direction, "amount_irr": data.amount_irr, "reason": data.reason, "bank_reference": data.bank_reference, "source": "finance"}
        label = "شارژ" if data.direction == "topup" else "کاهش"
        return _mc(db, user, "agency.wallet_adjust", payload, idempotency_key, f"{label} حساب {ag.display_name}", data.amount_irr, ag.id)

    @api.post("/finance/agency-accounts/{agency_id}/credit-limit", status_code=202)
    def finance_limit(agency_id: str, data: LimitIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120),
                      user=Depends(funder), db: Session = Depends(get_db)) -> dict:
        ag = _finance_agency(db, user, agency_id)
        payload = {"agency_id": ag.id, "new_limit_irr": data.new_limit_irr, "reason": data.reason, "source": "finance"}
        return _mc(db, user, "agency.credit_limit", payload, idempotency_key, f"تغییر سقف اعتبار {ag.display_name}", data.new_limit_irr, ag.id)

    return api


def _audit_model():
    from .main import AuditEvent  # lazy: main imports this module
    return AuditEvent
