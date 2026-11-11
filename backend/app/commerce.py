"""Commercial rules and treasury (KarenSeir's own design).

- customer groups (price levels) and membership
- markup / discount rules per service, group, supplier, route, airline, hotel city/stars, pax type
- cancellation penalty rules (time tiers before service start, per pax type)
- baggage allowance rules
- currency rates
- treasury journal (append-only debit/credit book) with reversal, per-counterparty
  debtor/creditor report, customer deposit requests and admin wallet/credit adjustments
- customer payout bank account (card / Sheba) with checksum validation

Amounts are integer IRR. Percent values are basis points (100 bps = 1%).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import approvals
from . import operations as m
from .database import Base
from .operations import OperationalMixin

SERVICES = ("flight", "hotel", "tour", "train", "bus", "insurance", "visa", "package", "cip", "transfer", "any")
PAX = ("adult", "child", "infant")


# ---------------------------------------------------------------- models
class CustomerGroup(OperationalMixin, Base):
    __tablename__ = "commerce_customer_groups"
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_commerce_group_code"),)


class CustomerGroupMember(OperationalMixin, Base):
    __tablename__ = "commerce_group_members"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("commerce_customer_groups.id"), index=True)
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_commerce_member_user"),)


class MarkupRule(OperationalMixin, Base):
    __tablename__ = "commerce_markup_rules"
    title: Mapped[str] = mapped_column(String(160))
    service_type: Mapped[str] = mapped_column(String(24), index=True)
    group_id: Mapped[Optional[str]] = mapped_column(ForeignKey("commerce_customer_groups.id"), nullable=True)
    supplier_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    scope: Mapped[str] = mapped_column(String(16), default="any")            # any | domestic | international
    flight_type: Mapped[str] = mapped_column(String(16), default="any")      # any | charter | system
    airline_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    origin: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    destination: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    city_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    min_stars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    effect: Mapped[str] = mapped_column(String(16), default="markup")        # markup | discount
    calc: Mapped[str] = mapped_column(String(16), default="percent")         # percent | fixed
    basis: Mapped[str] = mapped_column(String(16), default="total")          # base | total
    adult: Mapped[int] = mapped_column(Integer, default=0)
    child: Mapped[int] = mapped_column(Integer, default=0)
    infant: Mapped[int] = mapped_column(Integer, default=0)
    round_to: Mapped[int] = mapped_column(Integer, default=0)
    cap_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    valid_from: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    valid_to: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PenaltyRule(OperationalMixin, Base):
    __tablename__ = "commerce_penalty_rules"
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    service_type: Mapped[str] = mapped_column(String(24), index=True)
    airline_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    flight_type: Mapped[str] = mapped_column(String(16), default="any")
    supplier_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tiers_json: Mapped[str] = mapped_column(Text, default="[]")
    text_rules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_commerce_penalty_code"),)


class BaggageRule(OperationalMixin, Base):
    __tablename__ = "commerce_baggage_rules"
    airline_code: Mapped[str] = mapped_column(String(8), index=True)
    cabin: Mapped[str] = mapped_column(String(16), default="economy")
    fare_class: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    scope: Mapped[str] = mapped_column(String(16), default="any")
    adult_kg: Mapped[int] = mapped_column(Integer, default=20)
    child_kg: Mapped[int] = mapped_column(Integer, default=20)
    infant_kg: Mapped[int] = mapped_column(Integer, default=10)
    pieces: Mapped[int] = mapped_column(Integer, default=1)
    hand_kg: Mapped[int] = mapped_column(Integer, default=5)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


class CurrencyRate(OperationalMixin, Base):
    __tablename__ = "commerce_currency_rates"
    from_currency: Mapped[str] = mapped_column(String(3), index=True)
    to_currency: Mapped[str] = mapped_column(String(3), default="IRR")
    rate: Mapped[str] = mapped_column(String(32))          # decimal string, IRR per one unit
    display_on_sale: Mapped[bool] = mapped_column(Boolean, default=True)
    set_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class TreasuryEntry(OperationalMixin, Base):
    """Append-only book. A correction is a new entry with reversal_of_id."""
    __tablename__ = "commerce_treasury_entries"
    counterparty_type: Mapped[str] = mapped_column(String(24), index=True)   # user | organization | agency | supplier | company
    counterparty_ref: Mapped[str] = mapped_column(String(64), index=True)
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    account_type: Mapped[str] = mapped_column(String(24), index=True)        # wallet | credit | receivable | payable | bank | cash | gateway
    operation: Mapped[str] = mapped_column(String(24), index=True)           # deposit | withdrawal | purchase | refund | settlement | adjustment | fee
    debit: Mapped[int] = mapped_column(Integer, default=0)
    credit: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    fx_rate: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    tracking_no: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    contract_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    purchase_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operation_date: Mapped[str] = mapped_column(String(10))
    registered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reversal_of_id: Mapped[Optional[str]] = mapped_column(ForeignKey("commerce_treasury_entries.id"), nullable=True)
    command_id: Mapped[str] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("tenant_id", "command_id", name="uq_commerce_treasury_command"),)


class TreasuryRequest(OperationalMixin, Base):
    __tablename__ = "commerce_treasury_requests"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(16), default="deposit")   # deposit | withdrawal
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    bank_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    tracking_no: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    paid_on: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="submitted", index=True)
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treasury_entry_id: Mapped[Optional[str]] = mapped_column(ForeignKey("commerce_treasury_entries.id"), nullable=True)


class UserBankAccount(OperationalMixin, Base):
    __tablename__ = "commerce_user_bank_accounts"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    holder_name: Mapped[str] = mapped_column(String(160))
    card_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    card_bank: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    sheba: Mapped[Optional[str]] = mapped_column(String(26), nullable=True)
    sheba_bank: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="unverified")
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_commerce_bank_user"),)


class SupplierAccount(OperationalMixin, Base):
    __tablename__ = "commerce_supplier_accounts"
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    credit_limit: Mapped[int] = mapped_column(Integer, default=0)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=7)
    settlement_cycle: Mapped[str] = mapped_column(String(16), default="weekly")
    account_holder: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    sheba: Mapped[Optional[str]] = mapped_column(String(26), nullable=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    booking_only: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    __table_args__ = (UniqueConstraint("tenant_id", "supplier_id", name="uq_commerce_supplier_account"),)


TABLES = ("commerce_customer_groups", "commerce_group_members", "commerce_markup_rules", "commerce_penalty_rules",
          "commerce_baggage_rules", "commerce_currency_rates", "commerce_treasury_entries", "commerce_treasury_requests",
          "commerce_user_bank_accounts", "commerce_supplier_accounts")
APPEND_ONLY = ("commerce_treasury_entries",)


# ---------------------------------------------------------------- Iranian bank identifiers
CARD_BANKS = {"603799": "ملی", "589210": "سپه", "627648": "توسعه صادرات", "627961": "صنعت و معدن", "603770": "کشاورزی",
              "628023": "مسکن", "627760": "پست بانک", "502908": "توسعه تعاون", "627412": "اقتصاد نوین", "622106": "پارسیان",
              "502229": "پاسارگاد", "627488": "کارآفرین", "621986": "سامان", "639346": "سینا", "639607": "سرمایه",
              "636214": "آینده", "502806": "شهر", "502938": "دی", "603769": "صادرات", "610433": "ملت", "627353": "تجارت",
              "585983": "تجارت", "589463": "رفاه", "627381": "انصار", "639370": "مهر اقتصاد", "639599": "قوامین",
              "504172": "رسالت", "606373": "مهر ایران", "505785": "ایران زمین", "505801": "کوثر", "636949": "حکمت ایرانیان",
              "507677": "نور", "585947": "خاورمیانه", "991975": "ملت"}
SHEBA_BANKS = {"010": "مرکزی", "011": "صنعت و معدن", "012": "ملت", "013": "رفاه", "014": "مسکن", "015": "سپه", "016": "کشاورزی",
               "017": "ملی", "018": "تجارت", "019": "صادرات", "020": "توسعه صادرات", "021": "پست بانک", "022": "توسعه تعاون",
               "051": "موسسه توسعه", "053": "کارآفرین", "054": "پارسیان", "055": "اقتصاد نوین", "056": "سامان", "057": "پاسارگاد",
               "058": "سرمایه", "059": "سینا", "060": "مهر ایران", "061": "شهر", "062": "آینده", "063": "انصار", "064": "گردشگری",
               "065": "حکمت ایرانیان", "066": "دی", "069": "ایران زمین", "070": "رسالت", "073": "کوثر", "075": "ملل", "078": "خاورمیانه",
               "080": "نور", "090": "مهر اقتصاد"}

_FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def digits(value: str) -> str:
    return re.sub(r"[\s\-]", "", (value or "").translate(_FA))


def valid_card(card: str) -> bool:
    card = digits(card)
    if not re.fullmatch(r"\d{16}", card):
        return False
    total = 0
    for i, ch in enumerate(card):
        d = int(ch) * (2 if i % 2 == 0 else 1)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


def normalize_sheba(sheba: str) -> str:
    s = digits(sheba).upper()
    return s if s.startswith("IR") else "IR" + s


def valid_sheba(sheba: str) -> bool:
    s = normalize_sheba(sheba)
    if not re.fullmatch(r"IR\d{24}", s):
        return False
    rearranged = s[4:] + "1827" + s[2:4]   # I=18, R=27
    return int(rearranged) % 97 == 1


# ---------------------------------------------------------------- pricing engine
def _today() -> str:
    return date.today().isoformat()


def user_group_id(db: Session, tenant_id: int, user_id: Optional[int]) -> Optional[str]:
    if user_id is not None:
        gid = db.scalar(select(CustomerGroupMember.group_id).where(CustomerGroupMember.tenant_id == tenant_id, CustomerGroupMember.user_id == user_id))
        if gid:
            return gid
    return db.scalar(select(CustomerGroup.id).where(CustomerGroup.tenant_id == tenant_id, CustomerGroup.is_default.is_(True), CustomerGroup.status == "active"))


def _matches(rule: MarkupRule, ctx: dict, group_id: Optional[str], on: str) -> Optional[int]:
    """Return specificity score when the rule applies, else None. A null rule field is a wildcard."""
    if rule.service_type not in (ctx["service_type"], "any"):
        return None
    if rule.valid_from and on < rule.valid_from or rule.valid_to and on > rule.valid_to:
        return None
    score = 0 if rule.service_type == "any" else 1
    checks = (("group_id", group_id), ("supplier_id", ctx.get("supplier_id")), ("airline_code", (ctx.get("airline_code") or "").upper() or None),
              ("origin", (ctx.get("origin") or "").upper() or None), ("destination", (ctx.get("destination") or "").upper() or None),
              ("city_id", ctx.get("city_id")))
    for field, value in checks:
        want = getattr(rule, field)
        if want is None:
            continue
        if (want.upper() if isinstance(want, str) and field in ("airline_code", "origin", "destination") else want) != value:
            return None
        score += 2
    for field in ("scope", "flight_type"):
        want = getattr(rule, field)
        if want and want != "any":
            if want != ctx.get(field):
                return None
            score += 1
    if rule.min_stars is not None:
        if (ctx.get("stars") or 0) < rule.min_stars:
            return None
        score += 1
    return score


def _round_up(amount: int, step: int) -> int:
    if step <= 1:
        return amount
    return -((-amount) // step) * step


def choose_rule(db: Session, tenant_id: int, ctx: dict, *, user_id: Optional[int] = None) -> Optional[MarkupRule]:
    group_id = user_group_id(db, tenant_id, user_id)
    on = ctx.get("on_date") or _today()
    rules = db.scalars(select(MarkupRule).where(MarkupRule.tenant_id == tenant_id, MarkupRule.status == "active",
                                                MarkupRule.service_type.in_((ctx["service_type"], "any")))).all()
    best, best_key = None, None
    for rule in rules:
        score = _matches(rule, ctx, group_id, on)
        if score is None:
            continue
        key = (-score, rule.priority, rule.created_at or datetime.min.replace(tzinfo=timezone.utc))
        if best_key is None or key < best_key:
            best, best_key = rule, key
    return best


def apply_rule(rule: Optional[MarkupRule], fares: dict) -> dict:
    """fares: {adult: {"count": n, "base": irr, "total": irr}, child: ..., infant: ...} (per passenger amounts)."""
    lines, net_total, sell_total = [], 0, 0
    for pax in PAX:
        f = fares.get(pax) or {}
        count = int(f.get("count") or 0)
        if count <= 0:
            continue
        total = int(f.get("total") or f.get("base") or 0)
        base = int(f.get("base") or total)
        adj = 0
        if rule is not None:
            value = getattr(rule, pax)
            adj = (base if rule.basis == "base" else total) * value // 10000 if rule.calc == "percent" else value
            if rule.cap_amount is not None:
                adj = min(adj, rule.cap_amount)
            if rule.effect == "discount":
                adj = -min(adj, total)
        sell = _round_up(total + adj, rule.round_to if rule else 0)
        lines.append({"pax": pax, "count": count, "net": total, "adjustment": sell - total, "sell": sell, "line_total": sell * count})
        net_total += total * count
        sell_total += sell * count
    return {"rule": None if rule is None else {"id": rule.id, "title": rule.title, "effect": rule.effect, "calc": rule.calc},
            "lines": lines, "net_total": net_total, "sell_total": sell_total, "margin": sell_total - net_total}


def quote(db: Session, tenant_id: int, ctx: dict, fares: dict, *, user_id: Optional[int] = None) -> dict:
    return apply_rule(choose_rule(db, tenant_id, ctx, user_id=user_id), fares)


def penalty_for(rule: PenaltyRule, minutes_before: int, fares: dict) -> dict:
    """tiers: [{"until_minutes": 4320, "type": "percent", "adult": 3000, "child": 3000, "infant": 1000}, ...]
    A tier applies while minutes_before >= until_minutes; tiers are checked from the largest window down.
    The last tier (until_minutes 0) covers the final window; no-show uses a negative minutes_before."""
    tiers = sorted(json.loads(rule.tiers_json or "[]"), key=lambda t: -int(t.get("until_minutes", 0)))
    tier = next((t for t in tiers if minutes_before >= int(t.get("until_minutes", 0))), tiers[-1] if tiers else None)
    lines, total = [], 0
    for pax in PAX:
        f = fares.get(pax) or {}
        count = int(f.get("count") or 0)
        if not count or tier is None:
            continue
        amount = int(f.get("total") or 0)
        v = int(tier.get(pax, 0))
        fee = min(amount, amount * v // 10000 if tier.get("type", "percent") == "percent" else v)
        lines.append({"pax": pax, "count": count, "fee": fee, "refund": amount - fee})
        total += fee * count
    return {"tier": tier, "lines": lines, "penalty_total": total}


# ---------------------------------------------------------------- treasury helpers
def post_treasury(db: Session, *, tenant_id: int, command_id: str, counterparty_type: str, counterparty_ref: str, account_type: str,
                  operation: str, debit: int = 0, credit: int = 0, registered_by: Optional[int] = None, **extra: Any) -> TreasuryEntry:
    existing = db.scalar(select(TreasuryEntry).where(TreasuryEntry.tenant_id == tenant_id, TreasuryEntry.command_id == command_id))
    if existing:
        return existing
    if debit < 0 or credit < 0 or (debit == 0) == (credit == 0):
        raise ValueError("exactly one of debit/credit must be positive")
    row = TreasuryEntry(tenant_id=tenant_id, command_id=command_id, counterparty_type=counterparty_type, counterparty_ref=str(counterparty_ref),
                        account_type=account_type, operation=operation, debit=debit, credit=credit, registered_by=registered_by,
                        operation_date=extra.pop("operation_date", None) or _today(), **extra)
    db.add(row)
    db.flush()
    return row


def _entry_dict(e: TreasuryEntry, balance: Optional[int] = None) -> dict:
    d = {k: getattr(e, k) for k in ("id", "counterparty_type", "counterparty_ref", "counterparty_name", "account_type", "operation", "debit", "credit",
                                     "currency", "fx_rate", "bank_name", "tracking_no", "contract_ref", "purchase_ref", "description", "operation_date",
                                     "registered_by", "reversal_of_id")}
    d["created_at"] = e.created_at.isoformat() if e.created_at else None
    if balance is not None:
        d["balance"] = balance
    return d


def _user_wallet(db: Session, tenant_id: int, user_id: int, currency: str = "IRR") -> m.Wallet:
    w = db.scalar(select(m.Wallet).where(m.Wallet.tenant_id == tenant_id, m.Wallet.owner_type == "user", m.Wallet.owner_reference == str(user_id), m.Wallet.currency == currency))
    if w is None:
        w = m.Wallet(tenant_id=tenant_id, owner_type="user", owner_reference=str(user_id), currency=currency)
        db.add(w)
        db.flush()
    return w


def _user_credit(db: Session, tenant_id: int, user_id: int, currency: str = "IRR") -> m.CreditAccount:
    c = db.scalar(select(m.CreditAccount).where(m.CreditAccount.tenant_id == tenant_id, m.CreditAccount.user_id == user_id, m.CreditAccount.currency == currency))
    if c is None:
        c = m.CreditAccount(tenant_id=tenant_id, user_id=user_id, currency=currency, limit_amount=0)
        db.add(c)
        db.flush()
    return c


# ---------------------------------------------------------------- schemas
class GroupIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_default: bool = False
    status: str = Field(default="active", pattern="^(active|disabled)$")


class MembersIn(BaseModel):
    user_ids: list[int] = Field(max_length=500)


class MarkupIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    service_type: str
    group_id: Optional[str] = None
    supplier_id: Optional[str] = Field(default=None, max_length=64)
    scope: str = Field(default="any", pattern="^(any|domestic|international)$")
    flight_type: str = Field(default="any", pattern="^(any|charter|system)$")
    airline_code: Optional[str] = Field(default=None, max_length=8)
    origin: Optional[str] = Field(default=None, max_length=8)
    destination: Optional[str] = Field(default=None, max_length=8)
    city_id: Optional[str] = Field(default=None, max_length=64)
    min_stars: Optional[int] = Field(default=None, ge=1, le=7)
    effect: str = Field(default="markup", pattern="^(markup|discount)$")
    calc: str = Field(default="percent", pattern="^(percent|fixed)$")
    basis: str = Field(default="total", pattern="^(base|total)$")
    adult: int = Field(default=0, ge=0, le=10_000_000_000)
    child: int = Field(default=0, ge=0, le=10_000_000_000)
    infant: int = Field(default=0, ge=0, le=10_000_000_000)
    round_to: int = Field(default=0, ge=0, le=10_000_000)
    cap_amount: Optional[int] = Field(default=None, ge=0)
    priority: int = Field(default=100, ge=0, le=10000)
    valid_from: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    valid_to: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: str = Field(default="active", pattern="^(active|disabled)$")
    note: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("service_type")
    @classmethod
    def _svc(cls, v: str) -> str:
        if v not in SERVICES:
            raise ValueError("نوع خدمت معتبر نیست")
        return v

    @field_validator("airline_code", "origin", "destination", "supplier_id", "city_id", "group_id")
    @classmethod
    def _blank(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip()
        return v or None


class QuoteIn(BaseModel):
    service_type: str
    user_id: Optional[int] = None
    scope: Optional[str] = None
    flight_type: Optional[str] = None
    airline_code: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    supplier_id: Optional[str] = None
    city_id: Optional[str] = None
    stars: Optional[int] = None
    on_date: Optional[str] = None
    fares: dict[str, dict[str, int]]


class TierIn(BaseModel):
    until_minutes: int = Field(ge=-100000, le=10_000_000)
    type: str = Field(default="percent", pattern="^(percent|fixed)$")
    adult: int = Field(default=0, ge=0)
    child: int = Field(default=0, ge=0)
    infant: int = Field(default=0, ge=0)


class PenaltyIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=2, max_length=160)
    service_type: str
    airline_code: Optional[str] = Field(default=None, max_length=8)
    flight_type: str = Field(default="any", pattern="^(any|charter|system)$")
    supplier_id: Optional[str] = Field(default=None, max_length=64)
    tiers: list[TierIn] = Field(min_length=1, max_length=20)
    text_rules: Optional[str] = Field(default=None, max_length=8000)
    status: str = Field(default="active", pattern="^(active|disabled)$")


class PenaltyCalcIn(BaseModel):
    minutes_before: int
    fares: dict[str, dict[str, int]]


class BaggageIn(BaseModel):
    airline_code: str = Field(min_length=2, max_length=8)
    cabin: str = Field(default="economy", pattern="^(economy|premium|business|first)$")
    fare_class: Optional[str] = Field(default=None, max_length=8)
    scope: str = Field(default="any", pattern="^(any|domestic|international)$")
    adult_kg: int = Field(default=20, ge=0, le=200)
    child_kg: int = Field(default=20, ge=0, le=200)
    infant_kg: int = Field(default=10, ge=0, le=200)
    pieces: int = Field(default=1, ge=0, le=10)
    hand_kg: int = Field(default=5, ge=0, le=50)
    note: Optional[str] = Field(default=None, max_length=2000)
    status: str = Field(default="active", pattern="^(active|disabled)$")


class RateIn(BaseModel):
    from_currency: str = Field(pattern="^[A-Z]{3}$")
    to_currency: str = Field(default="IRR", pattern="^[A-Z]{3}$")
    rate: str = Field(pattern=r"^\d{1,14}(\.\d{1,6})?$")
    display_on_sale: bool = True


class TreasuryIn(BaseModel):
    counterparty_type: str = Field(pattern="^(user|organization|agency|supplier|company)$")
    counterparty_ref: str = Field(min_length=1, max_length=64)
    counterparty_name: Optional[str] = Field(default=None, max_length=200)
    account_type: str = Field(pattern="^(wallet|credit|receivable|payable|bank|cash|gateway)$")
    operation: str = Field(pattern="^(deposit|withdrawal|purchase|refund|settlement|adjustment|fee)$")
    debit: int = Field(default=0, ge=0)
    credit: int = Field(default=0, ge=0)
    currency: str = Field(default="IRR", pattern="^[A-Z]{3}$")
    fx_rate: Optional[str] = Field(default=None, max_length=32)
    bank_name: Optional[str] = Field(default=None, max_length=80)
    tracking_no: Optional[str] = Field(default=None, max_length=80)
    contract_ref: Optional[str] = Field(default=None, max_length=64)
    purchase_ref: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=2000)
    operation_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class AdjustIn(BaseModel):
    target: str = Field(pattern="^(wallet|credit)$")
    direction: str = Field(pattern="^(increase|decrease)$")
    amount: int = Field(gt=0, le=100_000_000_000)
    description: str = Field(min_length=3, max_length=2000)
    tracking_no: Optional[str] = Field(default=None, max_length=80)
    bank_name: Optional[str] = Field(default=None, max_length=80)
    # Idempotency for the maker-checker request (wallet increase / any credit change).
    command_id: Optional[str] = Field(default=None, min_length=8, max_length=120)


class TreasuryRequestIn(BaseModel):
    request_type: str = Field(default="deposit", pattern="^(deposit|withdrawal)$")
    amount: int = Field(gt=0, le=100_000_000_000)
    bank_name: Optional[str] = Field(default=None, max_length=80)
    tracking_no: Optional[str] = Field(default=None, max_length=80)
    paid_on: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    note: Optional[str] = Field(default=None, max_length=1000)


class DecisionIn(BaseModel):
    approve: bool
    note: Optional[str] = Field(default=None, max_length=1000)


class BankAccountIn(BaseModel):
    holder_name: str = Field(min_length=3, max_length=160)
    card_number: Optional[str] = Field(default=None, max_length=24)
    sheba: Optional[str] = Field(default=None, max_length=32)


class SupplierAccountIn(BaseModel):
    credit_limit: int = Field(default=0, ge=0)
    payment_terms_days: int = Field(default=7, ge=0, le=180)
    settlement_cycle: str = Field(default="weekly", pattern="^(per_booking|weekly|biweekly|monthly)$")
    account_holder: Optional[str] = Field(default=None, max_length=160)
    sheba: Optional[str] = Field(default=None, max_length=32)
    contact_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=160)
    booking_only: bool = False
    notes: Optional[str] = Field(default=None, max_length=4000)
    status: str = Field(default="active", pattern="^(active|suspended)$")


class SettleIn(BaseModel):
    amount: int = Field(gt=0)
    bank_name: Optional[str] = Field(default=None, max_length=80)
    tracking_no: str = Field(min_length=3, max_length=80)
    description: Optional[str] = Field(default=None, max_length=2000)
    operation_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- router
def _plain(row, fields) -> dict:
    d = {f: getattr(row, f) for f in fields}
    d["id"] = row.id
    return d


MARKUP_FIELDS = tuple(MarkupIn.model_fields)
GROUP_FIELDS = tuple(GroupIn.model_fields)
BAGGAGE_FIELDS = tuple(BaggageIn.model_fields)


def commerce_router(get_db, current_user, role_has_permission, User, audit=None):
    api = APIRouter(tags=["commerce"])

    def admin(user=Depends(current_user)):
        if not (role_has_permission(user.role, "platform:manage") or role_has_permission(user.role, "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مدیریت لازم است")
        return user

    def finance_read(user=Depends(current_user)):
        if not (role_has_permission(user.role, "ledger:read") or role_has_permission(user.role, "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مالی لازم است")
        return user

    def finance_write(user=Depends(current_user)):
        if not (role_has_permission(user.role, "reconciliation:manage") or role_has_permission(user.role, "platform:manage")):
            raise HTTPException(status_code=403, detail="مجوز ثبت مالی لازم است")
        return user

    def _audit(db, user, action, ref, detail=None):
        if audit:
            try:
                audit(db, user, action, ref, detail or {})
            except Exception:
                pass

    def _get(db, model, tenant_id, row_id):
        row = db.scalar(select(model).where(model.id == row_id, model.tenant_id == tenant_id))
        if row is None:
            raise HTTPException(status_code=404, detail="یافت نشد")
        return row

    # ---- customer groups
    @api.get("/commerce/groups")
    def list_groups(user=Depends(admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(CustomerGroup).where(CustomerGroup.tenant_id == user.tenant_id).order_by(CustomerGroup.code)).all()
        counts = dict(db.execute(select(CustomerGroupMember.group_id, func.count()).where(CustomerGroupMember.tenant_id == user.tenant_id).group_by(CustomerGroupMember.group_id)).all())
        return {"items": [{**_plain(r, GROUP_FIELDS), "members": counts.get(r.id, 0)} for r in rows]}

    def _save_group(db, user, row, data):
        if data.is_default:
            for other in db.scalars(select(CustomerGroup).where(CustomerGroup.tenant_id == user.tenant_id, CustomerGroup.is_default.is_(True))):
                other.is_default = False
        for f in GROUP_FIELDS:
            setattr(row, f, getattr(data, f))
        db.flush()
        _audit(db, user, "commerce.group.saved", row.id)
        db.commit()
        return _plain(row, GROUP_FIELDS)

    @api.post("/commerce/groups", status_code=201)
    def create_group(data: GroupIn, user=Depends(admin), db: Session = Depends(get_db)):
        if db.scalar(select(CustomerGroup.id).where(CustomerGroup.tenant_id == user.tenant_id, CustomerGroup.code == data.code)):
            raise HTTPException(status_code=409, detail="این کد گروه قبلاً ثبت شده است")
        row = CustomerGroup(tenant_id=user.tenant_id)
        db.add(row)
        return _save_group(db, user, row, data)

    @api.put("/commerce/groups/{group_id}")
    def update_group(group_id: str, data: GroupIn, user=Depends(admin), db: Session = Depends(get_db)):
        return _save_group(db, user, _get(db, CustomerGroup, user.tenant_id, group_id), data)

    @api.get("/commerce/groups/{group_id}/members")
    def group_members(group_id: str, user=Depends(admin), db: Session = Depends(get_db)):
        _get(db, CustomerGroup, user.tenant_id, group_id)
        rows = db.execute(select(User.id, User.name, User.email).join(CustomerGroupMember, CustomerGroupMember.user_id == User.id)
                          .where(CustomerGroupMember.tenant_id == user.tenant_id, CustomerGroupMember.group_id == group_id).order_by(User.id)).all()
        return {"items": [{"user_id": r.id, "name": r.name, "email": r.email} for r in rows]}

    @api.put("/commerce/groups/{group_id}/members")
    def set_members(group_id: str, data: MembersIn, user=Depends(admin), db: Session = Depends(get_db)):
        _get(db, CustomerGroup, user.tenant_id, group_id)
        valid = set(db.scalars(select(User.id).where(User.tenant_id == user.tenant_id, User.id.in_(data.user_ids))))
        if valid != set(data.user_ids):
            raise HTTPException(status_code=422, detail="برخی کاربران در این مجموعه نیستند")
        for uid in valid:
            row = db.scalar(select(CustomerGroupMember).where(CustomerGroupMember.tenant_id == user.tenant_id, CustomerGroupMember.user_id == uid))
            if row is None:
                db.add(CustomerGroupMember(tenant_id=user.tenant_id, user_id=uid, group_id=group_id))
            else:
                row.group_id = group_id
        _audit(db, user, "commerce.group.members", group_id, {"count": len(valid)})
        db.commit()
        return {"group_id": group_id, "assigned": len(valid)}

    # ---- markup rules
    @api.get("/commerce/markup-rules")
    def list_markups(service_type: Optional[str] = None, user=Depends(admin), db: Session = Depends(get_db)):
        q = select(MarkupRule).where(MarkupRule.tenant_id == user.tenant_id)
        if service_type:
            q = q.where(MarkupRule.service_type == service_type)
        rows = db.scalars(q.order_by(MarkupRule.service_type, MarkupRule.priority)).all()
        return {"items": [_plain(r, MARKUP_FIELDS) for r in rows]}

    def _save_markup(db, user, row, data):
        if data.group_id:
            _get(db, CustomerGroup, user.tenant_id, data.group_id)
        if data.valid_from and data.valid_to and data.valid_to < data.valid_from:
            raise HTTPException(status_code=422, detail="تاریخ پایان قبل از تاریخ شروع است")
        if data.calc == "percent" and max(data.adult, data.child, data.infant) > 100000:
            raise HTTPException(status_code=422, detail="درصد بیش از حد مجاز است")
        for f in MARKUP_FIELDS:
            v = getattr(data, f)
            setattr(row, f, v.upper() if f in ("airline_code", "origin", "destination") and v else v)
        db.flush()
        _audit(db, user, "commerce.markup.saved", row.id)
        db.commit()
        return _plain(row, MARKUP_FIELDS)

    @api.post("/commerce/markup-rules", status_code=201)
    def create_markup(data: MarkupIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = MarkupRule(tenant_id=user.tenant_id)
        db.add(row)
        return _save_markup(db, user, row, data)

    @api.put("/commerce/markup-rules/{rule_id}")
    def update_markup(rule_id: str, data: MarkupIn, user=Depends(admin), db: Session = Depends(get_db)):
        return _save_markup(db, user, _get(db, MarkupRule, user.tenant_id, rule_id), data)

    @api.post("/commerce/markup-rules/preview")
    def preview(data: QuoteIn, user=Depends(admin), db: Session = Depends(get_db)):
        ctx = data.model_dump(exclude={"fares", "user_id"})
        return quote(db, user.tenant_id, ctx, data.fares, user_id=data.user_id)

    # ---- penalty rules
    def _penalty_dict(r):
        d = _plain(r, ("code", "title", "service_type", "airline_code", "flight_type", "supplier_id", "text_rules", "status"))
        d["tiers"] = json.loads(r.tiers_json or "[]")
        return d

    @api.get("/commerce/penalty-rules")
    def list_penalties(user=Depends(admin), db: Session = Depends(get_db)):
        return {"items": [_penalty_dict(r) for r in db.scalars(select(PenaltyRule).where(PenaltyRule.tenant_id == user.tenant_id).order_by(PenaltyRule.code))]}

    def _save_penalty(db, user, row, data):
        dup = db.scalar(select(PenaltyRule.id).where(PenaltyRule.tenant_id == user.tenant_id, PenaltyRule.code == data.code, PenaltyRule.id != (row.id or "")))
        if dup:
            raise HTTPException(status_code=409, detail="این کد جریمه قبلاً ثبت شده است")
        for f in ("code", "title", "service_type", "flight_type", "supplier_id", "text_rules", "status"):
            setattr(row, f, getattr(data, f))
        row.airline_code = (data.airline_code or "").upper() or None
        row.tiers_json = json.dumps([t.model_dump() for t in sorted(data.tiers, key=lambda t: -t.until_minutes)])
        db.flush()
        _audit(db, user, "commerce.penalty.saved", row.id)
        db.commit()
        return _penalty_dict(row)

    @api.post("/commerce/penalty-rules", status_code=201)
    def create_penalty(data: PenaltyIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = PenaltyRule(tenant_id=user.tenant_id)
        db.add(row)
        return _save_penalty(db, user, row, data)

    @api.put("/commerce/penalty-rules/{rule_id}")
    def update_penalty(rule_id: str, data: PenaltyIn, user=Depends(admin), db: Session = Depends(get_db)):
        return _save_penalty(db, user, _get(db, PenaltyRule, user.tenant_id, rule_id), data)

    @api.post("/commerce/penalty-rules/{rule_id}/calculate")
    def calc_penalty(rule_id: str, data: PenaltyCalcIn, user=Depends(admin), db: Session = Depends(get_db)):
        return penalty_for(_get(db, PenaltyRule, user.tenant_id, rule_id), data.minutes_before, data.fares)

    # ---- baggage
    @api.get("/commerce/baggage-rules")
    def list_baggage(user=Depends(admin), db: Session = Depends(get_db)):
        return {"items": [_plain(r, BAGGAGE_FIELDS) for r in db.scalars(select(BaggageRule).where(BaggageRule.tenant_id == user.tenant_id).order_by(BaggageRule.airline_code, BaggageRule.cabin))]}

    def _save_baggage(db, user, row, data):
        for f in BAGGAGE_FIELDS:
            setattr(row, f, getattr(data, f))
        row.airline_code = data.airline_code.upper()
        db.flush()
        db.commit()
        return _plain(row, BAGGAGE_FIELDS)

    @api.post("/commerce/baggage-rules", status_code=201)
    def create_baggage(data: BaggageIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = BaggageRule(tenant_id=user.tenant_id)
        db.add(row)
        return _save_baggage(db, user, row, data)

    @api.put("/commerce/baggage-rules/{rule_id}")
    def update_baggage(rule_id: str, data: BaggageIn, user=Depends(admin), db: Session = Depends(get_db)):
        return _save_baggage(db, user, _get(db, BaggageRule, user.tenant_id, rule_id), data)

    # ---- currency rates (history kept; latest per pair is current)
    @api.get("/commerce/currency-rates")
    def list_rates(user=Depends(admin), db: Session = Depends(get_db)):
        rows = db.scalars(select(CurrencyRate).where(CurrencyRate.tenant_id == user.tenant_id).order_by(CurrencyRate.created_at.desc())).all()
        current, history = {}, []
        for r in rows:
            d = {"id": r.id, "from_currency": r.from_currency, "to_currency": r.to_currency, "rate": r.rate, "display_on_sale": r.display_on_sale,
                 "created_at": r.created_at.isoformat() if r.created_at else None}
            current.setdefault((r.from_currency, r.to_currency), d)
            history.append(d)
        return {"current": list(current.values()), "history": history[:200]}

    @api.post("/commerce/currency-rates", status_code=201)
    def set_rate(data: RateIn, user=Depends(admin), db: Session = Depends(get_db)):
        if data.from_currency == data.to_currency:
            raise HTTPException(status_code=422, detail="دو ارز باید متفاوت باشند")
        row = CurrencyRate(tenant_id=user.tenant_id, set_by=user.id, **data.model_dump())
        db.add(row)
        db.flush()
        _audit(db, user, "commerce.rate.set", row.id, {"pair": f"{data.from_currency}/{data.to_currency}", "rate": data.rate})
        db.commit()
        return {"id": row.id, **data.model_dump()}

    # ---- treasury book
    @api.get("/commerce/treasury")
    def treasury(date_from: Optional[str] = None, date_to: Optional[str] = None, counterparty_type: Optional[str] = None,
                 counterparty_ref: Optional[str] = None, account_type: Optional[str] = None, operation: Optional[str] = None,
                 q: Optional[str] = Query(default=None, max_length=80), limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
                 user=Depends(finance_read), db: Session = Depends(get_db)):
        s = select(TreasuryEntry).where(TreasuryEntry.tenant_id == user.tenant_id)
        if date_from: s = s.where(TreasuryEntry.operation_date >= date_from)
        if date_to: s = s.where(TreasuryEntry.operation_date <= date_to)
        if counterparty_type: s = s.where(TreasuryEntry.counterparty_type == counterparty_type)
        if counterparty_ref: s = s.where(TreasuryEntry.counterparty_ref == counterparty_ref)
        if account_type: s = s.where(TreasuryEntry.account_type == account_type)
        if operation: s = s.where(TreasuryEntry.operation == operation)
        if q:
            like = f"%{q}%"
            s = s.where(TreasuryEntry.tracking_no.ilike(like) | TreasuryEntry.description.ilike(like) | TreasuryEntry.contract_ref.ilike(like)
                        | TreasuryEntry.purchase_ref.ilike(like) | TreasuryEntry.counterparty_name.ilike(like))
        rows = db.scalars(s.order_by(TreasuryEntry.operation_date, TreasuryEntry.created_at)).all()
        balance, out, td, tc = 0, [], 0, 0
        for r in rows:
            balance += r.credit - r.debit
            td += r.debit
            tc += r.credit
            out.append(_entry_dict(r, balance))
        out.reverse()
        return {"items": out[offset:offset + limit], "total": len(out), "totals": {"debit": td, "credit": tc, "balance": tc - td}}

    @api.post("/commerce/treasury", status_code=201)
    def add_entry(data: TreasuryIn, user=Depends(finance_write), db: Session = Depends(get_db)):
        try:
            row = post_treasury(db, tenant_id=user.tenant_id, command_id=f"manual:{uuid.uuid4()}", registered_by=user.id, **data.model_dump())
        except ValueError:
            raise HTTPException(status_code=422, detail="فقط یکی از بدهکار یا بستانکار باید مقدار داشته باشد")
        _audit(db, user, "commerce.treasury.posted", row.id)
        db.commit()
        return _entry_dict(row)

    @api.post("/commerce/treasury/{entry_id}/reverse", status_code=201)
    def reverse_entry(entry_id: str, data: DecisionIn, user=Depends(finance_write), db: Session = Depends(get_db)):
        e = _get(db, TreasuryEntry, user.tenant_id, entry_id)
        if e.reversal_of_id or db.scalar(select(TreasuryEntry.id).where(TreasuryEntry.tenant_id == user.tenant_id, TreasuryEntry.reversal_of_id == e.id)):
            raise HTTPException(status_code=409, detail="این سند قبلاً برگشت خورده یا خودش سند برگشتی است")
        row = post_treasury(db, tenant_id=user.tenant_id, command_id=f"reverse:{e.id}", counterparty_type=e.counterparty_type, counterparty_ref=e.counterparty_ref,
                            counterparty_name=e.counterparty_name, account_type=e.account_type, operation=e.operation, debit=e.credit, credit=e.debit,
                            currency=e.currency, registered_by=user.id, reversal_of_id=e.id, contract_ref=e.contract_ref, purchase_ref=e.purchase_ref,
                            description=f"برگشت سند: {data.note or ''}".strip())
        _audit(db, user, "commerce.treasury.reversed", e.id)
        db.commit()
        return _entry_dict(row)

    @api.get("/commerce/subsidiary")
    def subsidiary(counterparty_type: Optional[str] = None, user=Depends(finance_read), db: Session = Depends(get_db)):
        s = select(TreasuryEntry.counterparty_type, TreasuryEntry.counterparty_ref, func.max(TreasuryEntry.counterparty_name),
                   func.sum(TreasuryEntry.debit), func.sum(TreasuryEntry.credit)).where(TreasuryEntry.tenant_id == user.tenant_id)
        if counterparty_type:
            s = s.where(TreasuryEntry.counterparty_type == counterparty_type)
        rows = db.execute(s.group_by(TreasuryEntry.counterparty_type, TreasuryEntry.counterparty_ref)).all()
        items = [{"counterparty_type": t, "counterparty_ref": r, "name": n, "debtor": int(d or 0), "creditor": int(c or 0), "remaining": int((c or 0) - (d or 0))}
                 for t, r, n, d, c in rows]
        items.sort(key=lambda x: x["remaining"])
        return {"items": items, "totals": {"debtor": sum(i["debtor"] for i in items), "creditor": sum(i["creditor"] for i in items)}}

    # ---- user wallet / credit administration
    def _target_user(db, tenant_id, user_id):
        u = db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
        if u is None:
            raise HTTPException(status_code=404, detail="کاربر یافت نشد")
        return u

    def _balances(db, tenant_id, uid):
        w = _user_wallet(db, tenant_id, uid)
        c = _user_credit(db, tenant_id, uid)
        return {"wallet": m.wallet_balances(db, tenant_id=tenant_id, wallet_id=w.id), "credit": m.credit_balances(db, tenant_id=tenant_id, credit_account_id=c.id)}

    @api.get("/commerce/users/{user_id}/account")
    def user_account(user_id: int, user=Depends(finance_read), db: Session = Depends(get_db)):
        u = _target_user(db, user.tenant_id, user_id)
        bal = _balances(db, user.tenant_id, u.id)
        db.commit()
        rows = db.scalars(select(TreasuryEntry).where(TreasuryEntry.tenant_id == user.tenant_id, TreasuryEntry.counterparty_type == "user",
                                                      TreasuryEntry.counterparty_ref == str(u.id)).order_by(TreasuryEntry.operation_date, TreasuryEntry.created_at)).all()
        running, out = 0, []
        for r in rows:
            running += r.credit - r.debit
            out.append(_entry_dict(r, running))
        out.reverse()
        gid = user_group_id(db, user.tenant_id, u.id)
        group = db.get(CustomerGroup, gid) if gid else None
        bank = db.scalar(select(UserBankAccount).where(UserBankAccount.tenant_id == user.tenant_id, UserBankAccount.user_id == u.id))
        return {"user": {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "mobile": getattr(u, "mobile_e164", None)},
                "group": {"id": group.id, "name": group.name} if group else None, **bal, "statement": out[:300],
                "bank_account": _bank_dict(bank)}

    def _can_adjust(actor, target: str) -> bool:
        if not (role_has_permission(actor.role, "reconciliation:manage") or role_has_permission(actor.role, "platform:manage")):
            return False
        return target != "credit" or role_has_permission(actor.role, "credit:manage") or role_has_permission(actor.role, "platform:manage")

    def _apply_adjust(db, user, u, data: AdjustIn, cmd: str, maker_id: Optional[int] = None):
        if data.target == "wallet":
            w = _user_wallet(db, user.tenant_id, u.id)
            try:
                if data.direction == "increase":
                    m.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=w.id, command_id=cmd, entry_type="allocate", amount=data.amount)
                else:
                    m.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=w.id, command_id=cmd + ":r", entry_type="reserve", amount=data.amount)
                    m.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=w.id, command_id=cmd + ":c", entry_type="capture", amount=data.amount)
            except ValueError:
                raise HTTPException(status_code=409, detail="موجودی کیف پول کافی نیست")
        else:
            c = _user_credit(db, user.tenant_id, u.id)
            available = m.credit_balances(db, tenant_id=user.tenant_id, credit_account_id=c.id)["available"]
            if data.direction == "decrease" and available < data.amount:
                raise HTTPException(status_code=409, detail="اعتبار آزاد کافی برای کاهش نیست")
            c.limit_amount += data.amount if data.direction == "increase" else -data.amount
        inc = data.direction == "increase"
        post_treasury(db, tenant_id=user.tenant_id, command_id=cmd, counterparty_type="user", counterparty_ref=str(u.id), counterparty_name=u.name,
                      account_type=data.target, operation="deposit" if inc and data.target == "wallet" else "adjustment",
                      credit=data.amount if inc else 0, debit=0 if inc else data.amount, registered_by=maker_id or user.id,
                      description=data.description, tracking_no=data.tracking_no, bank_name=data.bank_name)
        _audit(db, user, f"commerce.{data.target}.{data.direction}", str(u.id), {"amount": data.amount, "maker_user_id": maker_id or user.id, "checker_user_id": user.id if maker_id else None})

    def _execute_adjust(db, request, payload, checker):
        """Maker-checker executor (H-1): runs only after a second finance user approves."""
        data = AdjustIn(**payload["adjust"])
        u = _target_user(db, checker.tenant_id, int(payload["user_id"]))
        if u.id == checker.id:
            raise approvals.MakerCheckerError(403, "تأیید تغییر حساب خودتان مجاز نیست")
        try:
            _apply_adjust(db, checker, u, data, f"mc:{request.id}", maker_id=request.maker_user_id)
            db.flush()
        except HTTPException as exc:
            raise approvals.MakerCheckerError(exc.status_code, str(exc.detail)) from exc
        return _balances(db, checker.tenant_id, u.id)

    approvals.register("commerce.adjust", can_check=lambda actor, payload: _can_adjust(actor, payload["adjust"]["target"]),
                       execute=_execute_adjust, label="تغییر کیف پول / سقف اعتبار کاربر")

    @api.post("/commerce/users/{user_id}/adjust", status_code=201)
    def adjust(user_id: int, data: AdjustIn, response: Response, user=Depends(finance_write), db: Session = Depends(get_db)):
        u = _target_user(db, user.tenant_id, user_id)
        if data.target == "credit" and not (role_has_permission(user.role, "credit:manage") or role_has_permission(user.role, "platform:manage")):
            raise HTTPException(status_code=403, detail="تغییر سقف اعتبار فقط با مجوز مدیریت اعتبار ممکن است")
        if u.id == user.id:
            raise HTTPException(status_code=403, detail="تغییر حساب خودتان مجاز نیست")
        if data.target == "wallet" and data.direction == "decrease":
            # Early answer for an impossible decrease; the approval re-checks the balance at execution time.
            available = m.wallet_balances(db, tenant_id=user.tenant_id, wallet_id=_user_wallet(db, user.tenant_id, u.id).id)["available"]
            if available < data.amount:
                raise HTTPException(status_code=409, detail="موجودی کیف پول کافی نیست")
        # Every manual wallet/credit change (increase, DECREASE, limit) is maker-checker: nothing moves until a
        # second finance user approves (security follow-up: a single user could otherwise drain a wallet).
        try:
            row = approvals.create_request(db, user=user, kind="commerce.adjust", payload={"user_id": u.id, "adjust": data.model_dump(exclude={"command_id"})},
                                           idempotency_key=data.command_id or f"adjust:{uuid.uuid4()}", amount=data.amount, target_ref=f"user:{u.id}",
                                           summary=f"{'سقف اعتبار' if data.target == 'credit' else 'کیف پول'} {'افزایش' if data.direction == 'increase' else 'کاهش'} — {u.name}",
                                           audit=lambda d, a, action, entity, detail: _audit(d, a, action, entity, detail))
        except approvals.MakerCheckerError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        db.commit()
        response.status_code = 202
        return {"status": "pending_approval", "approval_request": approvals.output(row), **_balances(db, user.tenant_id, u.id)}

    # ---- treasury requests (customer side + review)
    def _req_dict(r):
        d = _plain(r, ("user_id", "request_type", "amount", "currency", "bank_name", "tracking_no", "paid_on", "note", "status", "decision_note", "treasury_entry_id"))
        d["created_at"] = r.created_at.isoformat() if r.created_at else None
        return d

    @api.get("/me/treasury-requests")
    def my_requests(user=Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(TreasuryRequest).where(TreasuryRequest.tenant_id == user.tenant_id, TreasuryRequest.user_id == user.id).order_by(TreasuryRequest.created_at.desc()).limit(100))
        return {"items": [_req_dict(r) for r in rows]}

    @api.post("/me/treasury-requests", status_code=201)
    def submit_request(data: TreasuryRequestIn, user=Depends(current_user), db: Session = Depends(get_db)):
        open_count = db.scalar(select(func.count()).select_from(TreasuryRequest).where(TreasuryRequest.tenant_id == user.tenant_id, TreasuryRequest.user_id == user.id, TreasuryRequest.status == "submitted")) or 0
        if open_count >= 5:
            raise HTTPException(status_code=429, detail="درخواست‌های بررسی‌نشده‌ی شما زیاد است؛ لطفاً منتظر بررسی بمانید")
        if data.request_type == "deposit" and not data.tracking_no:
            raise HTTPException(status_code=422, detail="برای واریز، شماره پیگیری لازم است")
        if data.request_type == "withdrawal":
            bank = db.scalar(select(UserBankAccount).where(UserBankAccount.tenant_id == user.tenant_id, UserBankAccount.user_id == user.id))
            if bank is None or not bank.sheba:
                raise HTTPException(status_code=422, detail="برای برداشت ابتدا شماره شبا را در پروفایل ثبت کنید")
            available = m.wallet_balances(db, tenant_id=user.tenant_id, wallet_id=_user_wallet(db, user.tenant_id, user.id).id)["available"]
            if available < data.amount:
                raise HTTPException(status_code=409, detail="موجودی کیف پول کافی نیست")
        row = TreasuryRequest(tenant_id=user.tenant_id, user_id=user.id, **data.model_dump())
        db.add(row)
        db.commit()
        return _req_dict(row)

    @api.get("/commerce/treasury-requests")
    def review_list(status: Optional[str] = "submitted", user=Depends(finance_read), db: Session = Depends(get_db)):
        s = select(TreasuryRequest, User.name).join(User, User.id == TreasuryRequest.user_id).where(TreasuryRequest.tenant_id == user.tenant_id)
        if status:
            s = s.where(TreasuryRequest.status == status)
        return {"items": [{**_req_dict(r), "user_name": n} for r, n in db.execute(s.order_by(TreasuryRequest.created_at.desc()).limit(300))]}

    @api.post("/commerce/treasury-requests/{request_id}/decide")
    def decide(request_id: str, data: DecisionIn, user=Depends(finance_write), db: Session = Depends(get_db)):
        r = db.scalar(select(TreasuryRequest).where(TreasuryRequest.id == request_id, TreasuryRequest.tenant_id == user.tenant_id).with_for_update())
        if r is None:
            raise HTTPException(status_code=404, detail="یافت نشد")
        if r.status != "submitted":
            raise HTTPException(status_code=409, detail="این درخواست قبلاً بررسی شده است")
        if r.user_id == user.id:
            raise HTTPException(status_code=403, detail="درخواست خودتان را نمی‌توانید تأیید کنید")
        r.decided_by, r.decision_note = user.id, data.note
        if not data.approve:
            r.status = "rejected"
            db.commit()
            return _req_dict(r)
        target = db.get(User, r.user_id)
        w = _user_wallet(db, user.tenant_id, r.user_id)
        try:
            if r.request_type == "deposit":
                m.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=w.id, command_id=f"treq:{r.id}", entry_type="allocate", amount=r.amount)
            else:
                m.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=w.id, command_id=f"treq:{r.id}:r", entry_type="reserve", amount=r.amount)
                m.apply_credit_command(db, tenant_id=user.tenant_id, wallet_id=w.id, command_id=f"treq:{r.id}:c", entry_type="capture", amount=r.amount)
        except ValueError:
            raise HTTPException(status_code=409, detail="موجودی کیف پول کاربر کافی نیست")
        e = post_treasury(db, tenant_id=user.tenant_id, command_id=f"treq:{r.id}", counterparty_type="user", counterparty_ref=str(r.user_id),
                          counterparty_name=target.name if target else None, account_type="wallet",
                          operation="deposit" if r.request_type == "deposit" else "withdrawal",
                          credit=r.amount if r.request_type == "deposit" else 0, debit=r.amount if r.request_type == "withdrawal" else 0,
                          registered_by=user.id, bank_name=r.bank_name, tracking_no=r.tracking_no, operation_date=r.paid_on,
                          description=f"درخواست صندوق — {data.note or ''}".strip(" —"))
        r.status, r.treasury_entry_id = "approved", e.id
        _audit(db, user, "commerce.treasury_request.approved", r.id, {"amount": r.amount})
        db.commit()
        return _req_dict(r)

    # ---- payout bank account
    def _bank_dict(b):
        if b is None:
            return None
        return {"holder_name": b.holder_name, "card_last4": b.card_last4, "card_bank": b.card_bank,
                "sheba": b.sheba, "sheba_bank": b.sheba_bank, "status": b.status}

    @api.get("/me/bank-account")
    def my_bank(user=Depends(current_user), db: Session = Depends(get_db)):
        return {"bank_account": _bank_dict(db.scalar(select(UserBankAccount).where(UserBankAccount.tenant_id == user.tenant_id, UserBankAccount.user_id == user.id)))}

    @api.put("/me/bank-account")
    def save_bank(data: BankAccountIn, user=Depends(current_user), db: Session = Depends(get_db)):
        if not data.card_number and not data.sheba:
            raise HTTPException(status_code=422, detail="شماره کارت یا شماره شبا را وارد کنید")
        card_last4 = card_bank = sheba = sheba_bank = None
        if data.card_number:
            if not valid_card(data.card_number):
                raise HTTPException(status_code=422, detail="شماره کارت معتبر نیست")
            c = digits(data.card_number)
            card_last4, card_bank = c[-4:], CARD_BANKS.get(c[:6])
        if data.sheba:
            if not valid_sheba(data.sheba):
                raise HTTPException(status_code=422, detail="شماره شبا معتبر نیست")
            sheba = normalize_sheba(data.sheba)
            sheba_bank = SHEBA_BANKS.get(sheba[4:7])
        b = db.scalar(select(UserBankAccount).where(UserBankAccount.tenant_id == user.tenant_id, UserBankAccount.user_id == user.id))
        if b is None:
            b = UserBankAccount(tenant_id=user.tenant_id, user_id=user.id, holder_name=data.holder_name)
            db.add(b)
        b.holder_name = data.holder_name.strip()
        if data.card_number:
            b.card_last4, b.card_bank = card_last4, card_bank
        if data.sheba:
            b.sheba, b.sheba_bank = sheba, sheba_bank
        b.status = "unverified"
        db.commit()
        return {"bank_account": _bank_dict(b)}

    @api.get("/commerce/users")
    def find_users(q: str = Query(min_length=1, max_length=80), user=Depends(finance_read), db: Session = Depends(get_db)):
        like = f"%{q}%"
        cond = User.name.ilike(like) | User.email.ilike(like)
        if hasattr(User, "mobile_e164"):
            cond = cond | User.mobile_e164.ilike(like)
        if q.isdigit():
            cond = cond | (User.id == int(q))
        rows = db.scalars(select(User).where(User.tenant_id == user.tenant_id, cond).order_by(User.id).limit(20)).all()
        return {"items": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role} for u in rows]}

    # ---- supplier accounts
    def _payable(db, tenant_id, supplier_id):
        d, c, oldest = db.execute(select(func.sum(TreasuryEntry.debit), func.sum(TreasuryEntry.credit), func.min(TreasuryEntry.operation_date))
                                  .where(TreasuryEntry.tenant_id == tenant_id, TreasuryEntry.counterparty_type == "supplier", TreasuryEntry.counterparty_ref == supplier_id)).one()
        return int(c or 0) - int(d or 0), oldest

    def _sacc(a):
        if a is None:
            return None
        return {k: getattr(a, k) for k in ("credit_limit", "payment_terms_days", "settlement_cycle", "account_holder", "sheba", "contact_name", "phone", "email", "booking_only", "notes", "status")}

    @api.get("/commerce/suppliers")
    def supplier_accounts(user=Depends(finance_read), db: Session = Depends(get_db)):
        out = []
        for sup in db.scalars(select(m.Supplier).where(m.Supplier.tenant_id == user.tenant_id).order_by(m.Supplier.display_name)):
            acc = db.scalar(select(SupplierAccount).where(SupplierAccount.tenant_id == user.tenant_id, SupplierAccount.supplier_id == sup.id))
            payable, oldest = _payable(db, user.tenant_id, sup.id)
            limit = acc.credit_limit if acc else 0
            out.append({"id": sup.id, "name": sup.display_name, "type": sup.supplier_type, "status": sup.status, "account": _sacc(acc), "payable": payable,
                        "credit_used_pct": round(100 * payable / limit) if limit else None, "over_limit": bool(limit and payable > limit), "oldest_entry": oldest})
        return {"items": out, "total_payable": sum(max(0, i["payable"]) for i in out)}

    @api.put("/commerce/suppliers/{supplier_id}/account")
    def save_supplier_account(supplier_id: str, data: SupplierAccountIn, user=Depends(finance_write), db: Session = Depends(get_db)):
        sup = db.scalar(select(m.Supplier).where(m.Supplier.id == supplier_id, m.Supplier.tenant_id == user.tenant_id))
        if sup is None:
            raise HTTPException(status_code=404, detail="تأمین‌کننده یافت نشد")
        if data.sheba and not valid_sheba(data.sheba):
            raise HTTPException(status_code=422, detail="شماره شبا معتبر نیست")
        acc = db.scalar(select(SupplierAccount).where(SupplierAccount.tenant_id == user.tenant_id, SupplierAccount.supplier_id == supplier_id))
        if acc is None:
            acc = SupplierAccount(tenant_id=user.tenant_id, supplier_id=supplier_id)
            db.add(acc)
        for k, v in data.model_dump().items():
            setattr(acc, k, v)
        acc.sheba = normalize_sheba(data.sheba) if data.sheba else None
        _audit(db, user, "commerce.supplier_account.saved", supplier_id)
        db.commit()
        return _sacc(acc)

    @api.get("/commerce/suppliers/{supplier_id}/statement")
    def supplier_statement(supplier_id: str, user=Depends(finance_read), db: Session = Depends(get_db)):
        rows = db.scalars(select(TreasuryEntry).where(TreasuryEntry.tenant_id == user.tenant_id, TreasuryEntry.counterparty_type == "supplier",
                                                      TreasuryEntry.counterparty_ref == supplier_id).order_by(TreasuryEntry.operation_date, TreasuryEntry.created_at)).all()
        running, out = 0, []
        for r in rows:
            running += r.credit - r.debit
            out.append(_entry_dict(r, running))
        out.reverse()
        return {"items": out[:500], "payable": running}

    @api.post("/commerce/suppliers/{supplier_id}/settle", status_code=201)
    def settle_supplier(supplier_id: str, data: SettleIn, user=Depends(finance_write), db: Session = Depends(get_db)):
        sup = db.scalar(select(m.Supplier).where(m.Supplier.id == supplier_id, m.Supplier.tenant_id == user.tenant_id))
        if sup is None:
            raise HTTPException(status_code=404, detail="تأمین‌کننده یافت نشد")
        payable, _ = _payable(db, user.tenant_id, supplier_id)
        if data.amount > payable:
            raise HTTPException(status_code=409, detail="مبلغ پرداخت از بدهی به تأمین‌کننده بیشتر است")
        e = post_treasury(db, tenant_id=user.tenant_id, command_id=f"settle:{uuid.uuid4()}", counterparty_type="supplier", counterparty_ref=supplier_id, counterparty_name=sup.display_name,
                          account_type="payable", operation="settlement", debit=data.amount, registered_by=user.id, bank_name=data.bank_name, tracking_no=data.tracking_no,
                          description=data.description or "تسویه با تأمین‌کننده", operation_date=data.operation_date)
        _audit(db, user, "commerce.supplier.settled", supplier_id, {"amount": data.amount})
        db.commit()
        return _entry_dict(e)

    # ---- bank gateway report
    @api.get("/commerce/reports/gateway")
    def gateway_report(date_from: Optional[str] = None, date_to: Optional[str] = None, status: Optional[str] = None, limit: int = Query(default=300, ge=1, le=2000),
                       user=Depends(finance_read), db: Session = Depends(get_db)):
        q = select(m.PaymentIntent, User.name).join(User, User.id == m.PaymentIntent.user_id).where(m.PaymentIntent.tenant_id == user.tenant_id)
        if date_from: q = q.where(m.PaymentIntent.created_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
        if date_to: q = q.where(m.PaymentIntent.created_at < datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1))
        if status: q = q.where(m.PaymentIntent.status == status)
        rows = db.execute(q.order_by(m.PaymentIntent.created_at.desc()).limit(limit)).all()
        items, totals = [], {}
        for p, name in rows:
            items.append({"id": p.id, "reservation_id": p.reservation_id, "user": name, "amount": p.amount, "captured_amount": p.captured_amount, "refunded_amount": p.refunded_amount,
                          "currency": p.currency, "status": p.status, "provider": p.provider_key, "authority": p.provider_authority, "ref_id": p.provider_capture_reference,
                          "created_at": p.created_at.isoformat() if p.created_at else None})
            t = totals.setdefault(p.status, {"count": 0, "amount": 0})
            t["count"] += 1
            t["amount"] += p.captured_amount if p.status == "captured" else p.amount
        return {"items": items, "by_status": totals}

    return api


# ---------------------------------------------------------------- automatic postings (sub-ledger)
def _safe_post(db: Session, **kw) -> None:
    """Posting must never break a booking or a payment: it runs in a savepoint and is skipped on error."""
    try:
        with db.begin_nested():
            post_treasury(db, **kw)
    except Exception:  # pragma: no cover - logged by caller's observability
        pass


def record_sale(db: Session, *, tenant_id: int, reservation, buyer_id: int, buyer_name: Optional[str], amount: int, currency: str,
                supplier_id: Optional[str], supplier_name: Optional[str], supplier_cost: Optional[int]) -> None:
    ref = reservation.booking_reference or reservation.id
    if amount > 0:
        _safe_post(db, tenant_id=tenant_id, command_id=f"sale:{reservation.id}", counterparty_type="user", counterparty_ref=str(buyer_id), counterparty_name=buyer_name,
                   account_type="receivable", operation="purchase", debit=amount, currency=currency, contract_ref=ref, purchase_ref=reservation.id,
                   description=f"خرید {reservation.service_type} — رزرو {ref}")
    if supplier_id and supplier_cost and supplier_cost > 0:
        _safe_post(db, tenant_id=tenant_id, command_id=f"cost:{reservation.id}", counterparty_type="supplier", counterparty_ref=supplier_id, counterparty_name=supplier_name,
                   account_type="payable", operation="purchase", credit=supplier_cost, currency=currency, contract_ref=ref, purchase_ref=reservation.id,
                   description=f"بهای تمام‌شده رزرو {ref}")


def record_payment(db: Session, *, tenant_id: int, intent, buyer_name: Optional[str], booking_reference: Optional[str]) -> None:
    _safe_post(db, tenant_id=tenant_id, command_id=f"pay:{intent.id}", counterparty_type="user", counterparty_ref=str(intent.user_id), counterparty_name=buyer_name,
               account_type="gateway", operation="deposit", credit=intent.captured_amount or intent.amount, currency=intent.currency, bank_name=intent.provider_key,
               tracking_no=intent.provider_capture_reference, contract_ref=booking_reference, purchase_ref=intent.reservation_id,
               description=f"پرداخت آنلاین رزرو {booking_reference or ''}".strip())
