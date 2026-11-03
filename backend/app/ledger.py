"""General ledger (دفتر کل): balanced vouchers, trial balance, period closing, Faranegar export from vouchers.

* Chart of accounts per tenant (`gl_accounts`) — codes are the tenant's own (as in Faranegar), never invented.
* Every voucher is balanced (sum debit == sum credit, at least two lines, each line one side only) and immutable;
  a correction is a reversing voucher.
* Treasury → ledger: each single-sided treasury entry becomes a two-line voucher. The entry's own side uses the
  existing account-code map (counterparty type × account type); the other side comes from a posting rule
  (operation × account type → counter account). Entries without both codes are reported, never guessed.
* Periods are Jalali months ("1405-08"). A closed period rejects new vouchers and reversals dated inside it.
  Closing requires every treasury entry of the month to be posted. Re-opening needs the tenant admin and a reason.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .operations import OperationalMixin

KINDS = ("asset", "liability", "equity", "revenue", "expense")
KIND_FA = {"asset": "دارایی", "liability": "بدهی", "equity": "سرمایه", "revenue": "درآمد", "expense": "هزینه"}
OPERATIONS = ("deposit", "withdrawal", "purchase", "refund", "settlement", "adjustment", "fee", "revenue")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ Jalali calendar
def g2j(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return jy, 1 + days // 31, 1 + days % 31
    return jy, 7 + (days - 186) // 30, 1 + (days - 186) % 30


def j2g(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd + ((jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186)
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    months = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 12 and gd > months[gm]:
        gd -= months[gm]
        gm += 1
    return gy, gm + 1, gd


def period_of(iso_day: str) -> str:
    d = date.fromisoformat(iso_day)
    jy, jm, _ = g2j(d.year, d.month, d.day)
    return f"{jy}-{jm:02d}"


def period_bounds(period: str) -> tuple[str, str]:
    """Inclusive Gregorian first and last day of a Jalali month."""
    if not re.fullmatch(r"1[34]\d\d-(0[1-9]|1[0-2])", period):
        raise ValueError("period")
    jy, jm = int(period[:4]), int(period[5:])
    first = date(*j2g(jy, jm, 1))
    ny, nm = (jy + 1, 1) if jm == 12 else (jy, jm + 1)
    nxt = date(*j2g(ny, nm, 1))
    return first.isoformat(), date.fromordinal(nxt.toordinal() - 1).isoformat()


# ------------------------------------------------------------------ models
class GlAccount(OperationalMixin, Base):
    __tablename__ = "gl_accounts"
    code: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(12))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_gl_account_code"),)


class GlPostingRule(OperationalMixin, Base):
    __tablename__ = "gl_posting_rules"
    operation: Mapped[str] = mapped_column(String(24))
    account_type: Mapped[str] = mapped_column(String(24))
    counter_code: Mapped[str] = mapped_column(String(20))
    __table_args__ = (UniqueConstraint("tenant_id", "operation", "account_type", name="uq_gl_posting_rule"),)


class GlVoucher(OperationalMixin, Base):
    __tablename__ = "gl_vouchers"
    number: Mapped[int] = mapped_column(Integer)
    voucher_date: Mapped[str] = mapped_column(String(10), index=True)
    period: Mapped[str] = mapped_column(String(7), index=True)
    description: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(16), default="manual")    # manual | treasury | reversal
    source_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="posted")    # posted | reversed
    reversal_of_id: Mapped[Optional[str]] = mapped_column(ForeignKey("gl_vouchers.id"), nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "number", name="uq_gl_voucher_number"),
                      UniqueConstraint("tenant_id", "source", "source_ref", name="uq_gl_voucher_source"))


class GlVoucherLine(OperationalMixin, Base):
    __tablename__ = "gl_voucher_lines"
    voucher_id: Mapped[str] = mapped_column(ForeignKey("gl_vouchers.id"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    account_code: Mapped[str] = mapped_column(String(20), index=True)
    debit: Mapped[int] = mapped_column(Integer, default=0)
    credit: Mapped[int] = mapped_column(Integer, default=0)
    counterparty: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)


class GlPeriod(OperationalMixin, Base):
    __tablename__ = "gl_periods"
    period: Mapped[str] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(String(8), default="closed")     # closed | open (re-opened)
    closed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reopen_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    __table_args__ = (UniqueConstraint("tenant_id", "period", name="uq_gl_period"),)


def check_balanced(lines: list[dict]) -> Optional[str]:
    if len(lines) < 2:
        return "سند حداقل دو ردیف لازم دارد"
    for i, ln in enumerate(lines, start=1):
        d, c = int(ln.get("debit") or 0), int(ln.get("credit") or 0)
        if d < 0 or c < 0 or (d > 0) == (c > 0):
            return f"ردیف {i}: هر ردیف یا بدهکار است یا بستانکار، با مبلغ مثبت"
    td, tc = sum(int(ln.get("debit") or 0) for ln in lines), sum(int(ln.get("credit") or 0) for ln in lines)
    if td != tc:
        return f"سند تراز نیست: بدهکار {td} و بستانکار {tc}"
    return None


# ------------------------------------------------------------------ schemas
class AccountIn(BaseModel):
    code: str = Field(pattern=r"^[0-9A-Za-z.\-]{1,20}$")
    title: str = Field(min_length=2, max_length=160)
    kind: str = Field(pattern="^(" + "|".join(KINDS) + ")$")
    active: bool = True


class AccountsIn(BaseModel):
    items: list[AccountIn] = Field(max_length=2000)


class RuleIn(BaseModel):
    operation: str = Field(pattern="^(" + "|".join(OPERATIONS) + ")$")
    account_type: str = Field(pattern=r"^[a-z_]{2,24}$")
    counter_code: str = Field(pattern=r"^[0-9A-Za-z.\-]{1,20}$")


class RulesIn(BaseModel):
    items: list[RuleIn] = Field(max_length=200)


class LineIn(BaseModel):
    account_code: str = Field(pattern=r"^[0-9A-Za-z.\-]{1,20}$")
    debit: int = Field(default=0, ge=0)
    credit: int = Field(default=0, ge=0)
    counterparty: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=300)


class VoucherIn(BaseModel):
    voucher_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field(min_length=3, max_length=500)
    lines: list[LineIn] = Field(min_length=2, max_length=200)


class ReverseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    voucher_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class PostTreasuryIn(BaseModel):
    period: str = Field(pattern=r"^1[34]\d\d-(0[1-9]|1[0-2])$")
    confirm: bool = False


class ReopenIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


def ledger_router(get_db, current_user, role_has_permission, User, audit=None):
    from .commerce import TreasuryEntry
    from .data_exchange import JOURNAL_HEADER, AccountingCode
    from .tabular import write_csv, write_xlsx

    api = APIRouter(tags=["ledger"])

    def _has(user, *p):
        return any(role_has_permission(user.role, x) for x in p)

    def reader(user=Depends(current_user)):
        if not _has(user, "ledger:read", "tenant:manage"):
            raise HTTPException(status_code=403, detail="دسترسی مالی لازم است")
        return user

    def writer(user=Depends(current_user)):
        if not _has(user, "settlement:manage", "tenant:manage"):
            raise HTTPException(status_code=403, detail="دسترسی ثبت سند مالی لازم است")
        return user

    def _a(db, user, action, detail):
        if audit:
            audit(db, user, action, "gl", detail)

    def _closed(db: Session, tenant_id: int, period: str) -> bool:
        return db.scalar(select(GlPeriod.id).where(GlPeriod.tenant_id == tenant_id, GlPeriod.period == period, GlPeriod.status == "closed")) is not None

    def _accounts(db: Session, tenant_id: int) -> dict[str, GlAccount]:
        return {a.code: a for a in db.scalars(select(GlAccount).where(GlAccount.tenant_id == tenant_id)).all()}

    def _next_number(db: Session, tenant_id: int) -> int:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": 7_310_000 + int(tenant_id)})
        return int(db.scalar(select(func.coalesce(func.max(GlVoucher.number), 0)).where(GlVoucher.tenant_id == tenant_id)) or 0) + 1

    def _create(db: Session, user, voucher_date: str, description: str, lines: list[dict], source: str = "manual",
                source_ref: Optional[str] = None, reversal_of: Optional[str] = None) -> GlVoucher:
        err = check_balanced(lines)
        if err:
            raise HTTPException(status_code=422, detail=err)
        try:
            period = period_of(voucher_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="تاریخ سند نامعتبر است")
        if _closed(db, user.tenant_id, period):
            raise HTTPException(status_code=409, detail=f"دوره‌ی {period} بسته است؛ سند در دوره‌ی بسته ثبت نمی‌شود")
        accounts = _accounts(db, user.tenant_id)
        for ln in lines:
            acc = accounts.get(ln["account_code"])
            if acc is None or not acc.active:
                raise HTTPException(status_code=422, detail=f"حساب {ln['account_code']} در سرفصل‌ها نیست یا غیرفعال است")
        v = GlVoucher(tenant_id=user.tenant_id, number=_next_number(db, user.tenant_id), voucher_date=voucher_date, period=period, description=description,
                      source=source, source_ref=source_ref, reversal_of_id=reversal_of, total=sum(int(ln.get("debit") or 0) for ln in lines), created_by=user.id)
        db.add(v)
        db.flush()
        for i, ln in enumerate(lines, start=1):
            db.add(GlVoucherLine(tenant_id=user.tenant_id, voucher_id=v.id, line_no=i, account_code=ln["account_code"], debit=int(ln.get("debit") or 0),
                                 credit=int(ln.get("credit") or 0), counterparty=ln.get("counterparty"), description=ln.get("description")))
        return v

    def _vout(db: Session, v: GlVoucher, with_lines: bool = True) -> dict:
        out = {"id": v.id, "number": v.number, "voucher_date": v.voucher_date, "period": v.period, "description": v.description, "source": v.source,
               "source_ref": v.source_ref, "status": v.status, "reversal_of_id": v.reversal_of_id, "total": v.total}
        if with_lines:
            accounts = _accounts(db, v.tenant_id)
            out["lines"] = [{"line_no": ln.line_no, "account_code": ln.account_code, "account_title": accounts[ln.account_code].title if ln.account_code in accounts else None,
                             "debit": ln.debit, "credit": ln.credit, "counterparty": ln.counterparty, "description": ln.description}
                            for ln in db.scalars(select(GlVoucherLine).where(GlVoucherLine.voucher_id == v.id).order_by(GlVoucherLine.line_no)).all()]
        return out

    # ---------------------------------------------------------- chart & rules
    @api.get("/ledger/accounts")
    def accounts(user=Depends(reader), db: Session = Depends(get_db)):
        rows = db.scalars(select(GlAccount).where(GlAccount.tenant_id == user.tenant_id).order_by(GlAccount.code)).all()
        return {"items": [{"code": a.code, "title": a.title, "kind": a.kind, "kind_fa": KIND_FA[a.kind], "active": a.active} for a in rows], "kinds": KIND_FA}

    @api.put("/ledger/accounts")
    def put_accounts(data: AccountsIn, user=Depends(writer), db: Session = Depends(get_db)):
        codes = [a.code for a in data.items]
        if len(codes) != len(set(codes)):
            raise HTTPException(status_code=422, detail="کد حساب تکراری است")
        existing = _accounts(db, user.tenant_id)
        used = set(db.scalars(select(GlVoucherLine.account_code).where(GlVoucherLine.tenant_id == user.tenant_id).distinct()).all())
        missing_used = sorted(c for c in existing if c not in codes and c in used)
        if missing_used:
            raise HTTPException(status_code=409, detail="حساب‌های دارای سند حذف نمی‌شوند؛ غیرفعالشان کنید: " + "، ".join(missing_used))
        for code, acc in existing.items():
            if code not in codes:
                db.delete(acc)
        for a in data.items:
            row = existing.get(a.code)
            if row is None:
                db.add(GlAccount(tenant_id=user.tenant_id, code=a.code, title=a.title, kind=a.kind, active=a.active))
            else:
                row.title, row.kind, row.active = a.title, a.kind, a.active
        _a(db, user, "gl.accounts.saved", {"count": len(codes)})
        db.commit()
        return accounts(user, db)

    @api.get("/ledger/posting-rules")
    def rules(user=Depends(reader), db: Session = Depends(get_db)):
        rows = db.scalars(select(GlPostingRule).where(GlPostingRule.tenant_id == user.tenant_id).order_by(GlPostingRule.operation, GlPostingRule.account_type)).all()
        return {"items": [{"operation": r.operation, "account_type": r.account_type, "counter_code": r.counter_code} for r in rows], "operations": list(OPERATIONS)}

    @api.put("/ledger/posting-rules")
    def put_rules(data: RulesIn, user=Depends(writer), db: Session = Depends(get_db)):
        accounts_map = _accounts(db, user.tenant_id)
        for r in data.items:
            if r.counter_code not in accounts_map:
                raise HTTPException(status_code=422, detail=f"حساب {r.counter_code} در سرفصل‌ها نیست")
        for old in db.scalars(select(GlPostingRule).where(GlPostingRule.tenant_id == user.tenant_id)).all():
            db.delete(old)
        db.flush()
        for r in {(r.operation, r.account_type): r for r in data.items}.values():
            db.add(GlPostingRule(tenant_id=user.tenant_id, operation=r.operation, account_type=r.account_type, counter_code=r.counter_code))
        _a(db, user, "gl.rules.saved", {"count": len(data.items)})
        db.commit()
        return rules(user, db)

    # ---------------------------------------------------------- vouchers
    @api.get("/ledger/vouchers")
    def vouchers(period: Optional[str] = Query(default=None, pattern=r"^1[34]\d\d-(0[1-9]|1[0-2])$"), user=Depends(reader), db: Session = Depends(get_db)):
        s = select(GlVoucher).where(GlVoucher.tenant_id == user.tenant_id)
        if period:
            s = s.where(GlVoucher.period == period)
        rows = db.scalars(s.order_by(GlVoucher.number.desc()).limit(500)).all()
        return {"items": [_vout(db, v, with_lines=False) for v in rows]}

    @api.get("/ledger/vouchers/{voucher_id}")
    def voucher(voucher_id: str, user=Depends(reader), db: Session = Depends(get_db)):
        v = db.scalar(select(GlVoucher).where(GlVoucher.id == voucher_id, GlVoucher.tenant_id == user.tenant_id))
        if v is None:
            raise HTTPException(status_code=404, detail="سند یافت نشد")
        return _vout(db, v)

    @api.post("/ledger/vouchers", status_code=201)
    def create_voucher(data: VoucherIn, user=Depends(writer), db: Session = Depends(get_db)):
        v = _create(db, user, data.voucher_date, data.description, [ln.model_dump() for ln in data.lines])
        _a(db, user, "gl.voucher.created", {"number": v.number, "total": v.total})
        db.commit()
        return _vout(db, v)

    @api.post("/ledger/vouchers/{voucher_id}/reverse", status_code=201)
    def reverse(voucher_id: str, data: ReverseIn, user=Depends(writer), db: Session = Depends(get_db)):
        v = db.scalar(select(GlVoucher).where(GlVoucher.id == voucher_id, GlVoucher.tenant_id == user.tenant_id).with_for_update())
        if v is None:
            raise HTTPException(status_code=404, detail="سند یافت نشد")
        if v.status == "reversed" or v.source == "reversal":
            raise HTTPException(status_code=409, detail="این سند قبلاً برگشت خورده یا خودش سند برگشتی است")
        lines = [{"account_code": ln.account_code, "debit": ln.credit, "credit": ln.debit, "counterparty": ln.counterparty, "description": ln.description}
                 for ln in db.scalars(select(GlVoucherLine).where(GlVoucherLine.voucher_id == v.id).order_by(GlVoucherLine.line_no)).all()]
        r = _create(db, user, data.voucher_date or date.today().isoformat(), f"برگشت سند {v.number}: {data.reason}", lines, source="reversal", source_ref=v.id, reversal_of=v.id)
        v.status = "reversed"
        _a(db, user, "gl.voucher.reversed", {"number": v.number, "reversal": r.number, "reason": data.reason})
        db.commit()
        return _vout(db, r)

    # ---------------------------------------------------------- treasury -> ledger
    def _treasury_plan(db: Session, tenant_id: int, period: str):
        first, last = period_bounds(period)
        posted = set(db.scalars(select(GlVoucher.source_ref).where(GlVoucher.tenant_id == tenant_id, GlVoucher.source == "treasury")).all())
        cmap = {(c.counterparty_type, c.account_type): c.code for c in db.scalars(select(AccountingCode).where(AccountingCode.tenant_id == tenant_id)).all()}
        rmap = {(r.operation, r.account_type): r.counter_code for r in db.scalars(select(GlPostingRule).where(GlPostingRule.tenant_id == tenant_id)).all()}
        chart = _accounts(db, tenant_id)
        ready, missing = [], {}
        entries = db.scalars(select(TreasuryEntry).where(TreasuryEntry.tenant_id == tenant_id, TreasuryEntry.operation_date >= first,
                                                         TreasuryEntry.operation_date <= last).order_by(TreasuryEntry.operation_date, TreasuryEntry.created_at)).all()
        for e in entries:
            if e.id in posted:
                continue
            amount = int(e.debit or 0) or int(e.credit or 0)
            if amount <= 0 or (e.debit and e.credit):
                missing["مبلغ دوطرفه یا صفر"] = missing.get("مبلغ دوطرفه یا صفر", 0) + 1
                continue
            own = cmap.get((e.counterparty_type, e.account_type))
            counter = rmap.get((e.operation, e.account_type))
            if not own or own not in chart:
                k = f"کد حساب {e.counterparty_type}/{e.account_type}"
                missing[k] = missing.get(k, 0) + 1
                continue
            if not counter:
                k = f"قانون طرف مقابل {e.operation}/{e.account_type}"
                missing[k] = missing.get(k, 0) + 1
                continue
            who = e.counterparty_name or e.counterparty_ref
            desc = (e.description or e.operation)[:300]
            own_line = {"account_code": own, "debit": int(e.debit or 0), "credit": int(e.credit or 0), "counterparty": who, "description": desc}
            other = {"account_code": counter, "debit": int(e.credit or 0), "credit": int(e.debit or 0), "counterparty": who, "description": desc}
            ready.append((e, [own_line, other]))
        return ready, missing, len(entries)

    @api.post("/ledger/post-treasury")
    def post_treasury(data: PostTreasuryIn, user=Depends(writer), db: Session = Depends(get_db)):
        if _closed(db, user.tenant_id, data.period):
            raise HTTPException(status_code=409, detail=f"دوره‌ی {data.period} بسته است")
        ready, missing, total = _treasury_plan(db, user.tenant_id, data.period)
        out = {"period": data.period, "entries": total, "ready": len(ready), "amount": sum(ln[0]["debit"] + ln[0]["credit"] for _, ln in ready),
               "missing": [{"reason": k, "count": v} for k, v in sorted(missing.items())], "created": 0}
        if data.confirm and ready:
            for e, lines in ready:
                _create(db, user, e.operation_date, f"صندوق: {(e.description or e.operation)[:200]}", lines, source="treasury", source_ref=e.id)
            out["created"] = len(ready)
            _a(db, user, "gl.treasury.posted", {"period": data.period, "vouchers": len(ready)})
            db.commit()
        return out

    # ---------------------------------------------------------- trial balance
    def _balances(db: Session, tenant_id: int, first: str, last: str) -> list[dict]:
        chart = _accounts(db, tenant_id)
        rows = {}
        q = select(GlVoucherLine.account_code, GlVoucher.voucher_date < first, func.sum(GlVoucherLine.debit), func.sum(GlVoucherLine.credit)) \
            .join(GlVoucher, GlVoucher.id == GlVoucherLine.voucher_id).where(GlVoucher.tenant_id == tenant_id, GlVoucher.voucher_date <= last) \
            .group_by(GlVoucherLine.account_code, GlVoucher.voucher_date < first)
        for code, before, d, c in db.execute(q).all():
            r = rows.setdefault(code, {"code": code, "title": chart[code].title if code in chart else None, "kind": chart[code].kind if code in chart else None,
                                       "opening": 0, "debit": 0, "credit": 0})
            if before:
                r["opening"] += int(d or 0) - int(c or 0)
            else:
                r["debit"] += int(d or 0)
                r["credit"] += int(c or 0)
        out = sorted(rows.values(), key=lambda r: r["code"])
        for r in out:
            r["closing"] = r["opening"] + r["debit"] - r["credit"]
        return out

    @api.get("/ledger/trial-balance")
    def trial_balance(period: str = Query(pattern=r"^1[34]\d\d-(0[1-9]|1[0-2])$"), user=Depends(reader), db: Session = Depends(get_db)):
        first, last = period_bounds(period)
        rows = _balances(db, user.tenant_id, first, last)
        totals = {k: sum(r[k] for r in rows) for k in ("opening", "debit", "credit", "closing")}
        return {"period": period, "from": first, "to": last, "items": rows, "totals": totals, "balanced": totals["debit"] == totals["credit"] and totals["closing"] == 0,
                "closed": _closed(db, user.tenant_id, period)}

    # ---------------------------------------------------------- periods
    @api.get("/ledger/periods")
    def periods(user=Depends(reader), db: Session = Depends(get_db)):
        found = {p: n for p, n in db.execute(select(GlVoucher.period, func.count(GlVoucher.id)).where(GlVoucher.tenant_id == user.tenant_id).group_by(GlVoucher.period)).all()}
        for d in db.scalars(select(TreasuryEntry.operation_date).where(TreasuryEntry.tenant_id == user.tenant_id).distinct()).all():
            try:
                found.setdefault(period_of(d), 0)
            except ValueError:
                pass
        found.setdefault(period_of(date.today().isoformat()), 0)
        state = {p.period: p for p in db.scalars(select(GlPeriod).where(GlPeriod.tenant_id == user.tenant_id)).all()}
        items = []
        for p in sorted(found, reverse=True)[:36]:
            ready, missing, total = _treasury_plan(db, user.tenant_id, p)
            st = state.get(p)
            items.append({"period": p, "vouchers": found[p], "treasury_entries": total, "unposted": len(ready) + sum(missing.values()),
                          "status": st.status if st else "open", "closed_at": st.closed_at.isoformat() if st and st.closed_at else None,
                          "reopen_reason": st.reopen_reason if st else None})
        return {"items": items}

    @api.post("/ledger/periods/{period}/close")
    def close(period: str, user=Depends(writer), db: Session = Depends(get_db)):
        try:
            first, last = period_bounds(period)
        except ValueError:
            raise HTTPException(status_code=422, detail="دوره نامعتبر است")
        if last >= date.today().isoformat():
            raise HTTPException(status_code=409, detail="ماه جاری یا آینده را نمی‌توان بست")
        if _closed(db, user.tenant_id, period):
            raise HTTPException(status_code=409, detail="این دوره قبلاً بسته شده است")
        ready, missing, _ = _treasury_plan(db, user.tenant_id, period)
        pending = len(ready) + sum(missing.values())
        if pending:
            raise HTTPException(status_code=409, detail=f"{pending} ردیف صندوق این ماه هنوز به سند تبدیل نشده است")
        rows = _balances(db, user.tenant_id, first, last)
        td, tc = sum(r["debit"] for r in rows), sum(r["credit"] for r in rows)
        if td != tc:
            raise HTTPException(status_code=409, detail="تراز آزمایشی این دوره برابر نیست")
        st = db.scalar(select(GlPeriod).where(GlPeriod.tenant_id == user.tenant_id, GlPeriod.period == period))
        if st is None:
            st = GlPeriod(tenant_id=user.tenant_id, period=period)
            db.add(st)
        st.status, st.closed_by, st.closed_at = "closed", user.id, utcnow()
        st.snapshot_json = json.dumps({"debit": td, "credit": tc, "accounts": len(rows)})
        _a(db, user, "gl.period.closed", {"period": period, "debit": td})
        db.commit()
        return {"period": period, "status": "closed", "debit": td, "credit": tc}

    @api.post("/ledger/periods/{period}/reopen")
    def reopen(period: str, data: ReopenIn, user=Depends(current_user), db: Session = Depends(get_db)):
        if not _has(user, "tenant:manage"):
            raise HTTPException(status_code=403, detail="فقط مدیر مجموعه می‌تواند دوره‌ی بسته را باز کند")
        st = db.scalar(select(GlPeriod).where(GlPeriod.tenant_id == user.tenant_id, GlPeriod.period == period, GlPeriod.status == "closed"))
        if st is None:
            raise HTTPException(status_code=404, detail="دوره‌ی بسته‌ای با این نام نیست")
        st.status, st.reopen_reason = "open", data.reason
        _a(db, user, "gl.period.reopened", {"period": period, "reason": data.reason})
        db.commit()
        return {"period": period, "status": "open"}

    # ---------------------------------------------------------- export
    @api.get("/ledger/export")
    def export(period: str = Query(pattern=r"^1[34]\d\d-(0[1-9]|1[0-2])$"), fmt: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
               user=Depends(reader), db: Session = Depends(get_db)):
        chart = _accounts(db, user.tenant_id)
        rows = []
        for v in db.scalars(select(GlVoucher).where(GlVoucher.tenant_id == user.tenant_id, GlVoucher.period == period).order_by(GlVoucher.number)).all():
            for ln in db.scalars(select(GlVoucherLine).where(GlVoucherLine.voucher_id == v.id).order_by(GlVoucherLine.line_no)).all():
                rows.append([v.voucher_date, v.number, ln.line_no, ln.account_code, chart[ln.account_code].title if ln.account_code in chart else "",
                             ln.counterparty or "", (ln.description or v.description)[:250], ln.debit, ln.credit, "IRR", "", v.source_ref or ""])
        data = write_xlsx(JOURNAL_HEADER, rows, "سند") if fmt == "xlsx" else write_csv(JOURNAL_HEADER, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "text/csv; charset=utf-8"
        _a(db, user, "gl.export", {"period": period, "rows": len(rows)})
        db.commit()
        return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="karenseir-vouchers-{period}.{fmt}"'})

    return api
