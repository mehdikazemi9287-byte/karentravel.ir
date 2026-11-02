"""Excel in, accounting out.

1. Sales-desk lead import (ورود اکسل): upload .xlsx/.csv -> per-row errors and warnings -> confirm -> result.
   Rows with errors are never written; rows whose mobile already has an open case are skipped with a warning.
2. Accounting export for Faranegar (خروجی فرانگر): the treasury book as journal lines with the tenant's own
   account codes per (counterparty type, account type). The column layout is a generic journal sheet; it must
   be matched once to the tenant's Faranegar import template (not published by the vendor), so unmapped lines
   are reported instead of guessed.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .commerce import TreasuryEntry
from .database import Base
from .operations import OperationalMixin
from .sales_desk import CHANNELS, OPEN_STAGES, SalesCase, _log, _new_code, _next_agent, _settings, normalize_mobile
from .tabular import TableError, read_table, write_csv, write_xlsx

LEAD_COLUMNS = {
    "customer_name": ("نام", "نام مشتری", "name", "customer"),
    "mobile": ("موبایل", "شماره موبایل", "تلفن همراه", "mobile", "phone"),
    "trip": ("سفر", "سفر درخواستی", "مقصد", "trip", "destination"),
    "travel_date": ("تاریخ", "تاریخ سفر", "travel_date", "date"),
    "travellers": ("تعداد", "تعداد مسافر", "travellers", "pax"),
    "channel": ("کانال", "channel", "source"),
    "description": ("توضیحات", "description", "notes"),
}
TEMPLATE_HEADER = ["نام", "موبایل", "سفر", "تاریخ سفر", "تعداد مسافر", "کانال", "توضیحات"]
ACCOUNT_TYPES = ("wallet", "credit", "receivable", "payable", "bank", "cash", "gateway", "revenue")
COUNTERPARTY_TYPES = ("user", "organization", "agency", "supplier", "company")
JOURNAL_HEADER = ["تاریخ", "شماره سند", "ردیف", "کد حساب", "عنوان حساب", "طرف حساب", "شرح", "بدهکار", "بستانکار", "ارز", "شماره پیگیری", "مرجع"]


class AccountingCode(OperationalMixin, Base):
    __tablename__ = "accounting_code_map"
    counterparty_type: Mapped[str] = mapped_column(String(24))
    account_type: Mapped[str] = mapped_column(String(24))
    code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("tenant_id", "counterparty_type", "account_type", name="uq_accounting_code_pair"),)


class CodeIn(BaseModel):
    counterparty_type: str = Field(pattern="^(" + "|".join(COUNTERPARTY_TYPES) + ")$")
    account_type: str = Field(pattern="^(" + "|".join(ACCOUNT_TYPES) + ")$")
    code: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z\-./]+$")
    title: str = Field(min_length=1, max_length=120)


class CodesIn(BaseModel):
    items: list[CodeIn] = Field(max_length=80)


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").replace("‌", " ").strip().lower())


def map_columns(header: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    norm = [_norm_header(h) for h in header]
    for key, names in LEAD_COLUMNS.items():
        for i, h in enumerate(norm):
            if h in {_norm_header(n) for n in names}:
                found[key] = i
                break
    return found


def validate_leads(db: Session, tenant_id: int, rows: list[list[str]]) -> dict:
    if not rows:
        raise TableError("فایل خالی است")
    cols = map_columns(rows[0])
    missing = [k for k in ("customer_name", "mobile", "trip") if k not in cols]
    if missing:
        raise TableError("ستون‌های لازم پیدا نشد: " + "، ".join({"customer_name": "نام", "mobile": "موبایل", "trip": "سفر"}[k] for k in missing))
    open_mobiles = set(db.scalars(select(SalesCase.mobile).where(SalesCase.tenant_id == tenant_id, SalesCase.stage.in_(OPEN_STAGES))).all())
    seen: set[str] = set()
    out = []
    for n, raw in enumerate(rows[1:], start=2):
        get = lambda k: (raw[cols[k]] if k in cols and cols[k] < len(raw) else "").strip()  # noqa: E731
        errors, warnings, rec = [], [], {"customer_name": get("customer_name"), "trip": get("trip")}
        if not rec["customer_name"]:
            errors.append("نام خالی است")
        if not rec["trip"]:
            errors.append("سفر خالی است")
        try:
            rec["mobile"] = normalize_mobile(get("mobile"))
        except ValueError:
            rec["mobile"] = get("mobile")
            errors.append("موبایل نامعتبر است")
        date = get("travel_date")
        if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            warnings.append("تاریخ با قالب ۱۴۰۵-۰۹-۱۵ نیست و ثبت نمی‌شود")
            date = ""
        rec["travel_date"] = date or None
        trav = get("travellers") or "1"
        rec["travellers"] = int(trav) if trav.isdigit() and 1 <= int(trav) <= 500 else None
        if rec["travellers"] is None:
            errors.append("تعداد مسافر نامعتبر است")
        ch = get("channel") or "manual"
        rec["channel"] = ch if ch in CHANNELS else "manual"
        if ch not in CHANNELS:
            warnings.append(f"کانال «{ch}» شناخته نشد؛ «ثبت دستی» در نظر گرفته شد")
        rec["description"] = get("description")[:4000] or None
        skip = False
        if not errors and rec["mobile"] in open_mobiles:
            warnings.append("این موبایل پرونده‌ی باز دارد؛ ثبت نمی‌شود")
            skip = True
        if not errors and rec["mobile"] in seen:
            warnings.append("موبایل تکراری در همین فایل؛ فقط ردیف اول ثبت می‌شود")
            skip = True
        if not errors:
            seen.add(rec["mobile"])
        out.append({"row": n, "data": rec, "errors": errors, "warnings": warnings, "will_import": not errors and not skip})
    return {"rows": out, "total": len(out), "importable": sum(r["will_import"] for r in out),
            "errors": sum(bool(r["errors"]) for r in out), "warnings": sum(bool(r["warnings"]) for r in out)}


def data_exchange_router(get_db, current_user, role_has_permission, User, audit=None):
    api = APIRouter(tags=["data-exchange"])

    def agent(user=Depends(current_user)):
        if user.role in ("employee", "customer") or not any(role_has_permission(user.role, p) for p in ("support:manage", "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی میز فروش لازم است")
        return user

    def finance_read(user=Depends(current_user)):
        if not (role_has_permission(user.role, "ledger:read") or role_has_permission(user.role, "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مالی لازم است")
        return user

    def finance_admin(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("tenant:manage", "reconciliation:manage", "platform:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مدیر مالی لازم است")
        return user

    # ---- lead import
    @api.get("/sales-desk/import/template")
    def template(fmt: str = Query(default="xlsx", pattern="^(xlsx|csv)$"), user=Depends(agent)):
        sample = [["نمونه — این ردیف را پاک کنید", "09120000000", "مشهد ۳ شب", "1405-09-15", 2, "phone", ""]]
        data = write_xlsx(TEMPLATE_HEADER, sample, "مشتریان") if fmt == "xlsx" else write_csv(TEMPLATE_HEADER, sample)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "text/csv; charset=utf-8"
        return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="sales-desk-import.{fmt}"'})

    @api.post("/sales-desk/import")
    async def import_leads(file: UploadFile = File(...), confirm: bool = Form(default=False), user=Depends(agent), db: Session = Depends(get_db)):
        data = await file.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="حجم فایل بیش از ۵ مگابایت است")
        try:
            report = validate_leads(db, user.tenant_id, read_table(file.filename or "", data))
        except (TableError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc) if isinstance(exc, TableError) else "فایل CSV باید UTF-8 باشد")
        if not confirm:
            return {"stage": "review", **report}
        settings = _settings(db, user.tenant_id)
        now = datetime.now(timezone.utc)
        created = []
        for r in report["rows"]:
            if not r["will_import"]:
                continue
            d = r["data"]
            case = SalesCase(tenant_id=user.tenant_id, code=_new_code(db, user.tenant_id), customer_name=d["customer_name"][:160], mobile=d["mobile"], channel=d["channel"],
                             trip=d["trip"][:240], travel_date=d["travel_date"], travellers=d["travellers"], stage="new", is_complaint=False,
                             description=d["description"], created_by_user_id=user.id, sla_due_at=now + timedelta(minutes=settings.sla_alert_minutes))
            if settings.auto_assign:
                nxt = _next_agent(db, user.tenant_id)
                if nxt:
                    case.agent_user_id, nxt.last_assigned_at = nxt.user_id, now
            db.add(case)
            db.flush()
            _log(db, case, user.id, "created", None, {"channel": case.channel, "import_row": r["row"], "file": (file.filename or "")[:80]})
            created.append(case.code)
        if audit:
            audit(db, user, "sales_desk.import", "sales_desk_case", {"file": (file.filename or "")[:80], "created": len(created), "rows": report["total"]})
        db.commit()
        return {"stage": "done", "created": len(created), "codes": created[:50], **{k: report[k] for k in ("total", "errors", "warnings")}, "rows": report["rows"]}

    # ---- accounting codes + Faranegar export
    @api.get("/commerce/accounting-codes")
    def codes(user=Depends(finance_read), db: Session = Depends(get_db)):
        rows = db.scalars(select(AccountingCode).where(AccountingCode.tenant_id == user.tenant_id)).all()
        return {"items": [{"counterparty_type": r.counterparty_type, "account_type": r.account_type, "code": r.code, "title": r.title} for r in rows],
                "counterparty_types": list(COUNTERPARTY_TYPES), "account_types": list(ACCOUNT_TYPES)}

    @api.put("/commerce/accounting-codes")
    def put_codes(data: CodesIn, user=Depends(finance_admin), db: Session = Depends(get_db)):
        pairs = {(c.counterparty_type, c.account_type) for c in data.items}
        if len(pairs) != len(data.items):
            raise HTTPException(status_code=422, detail="هر جفت «طرف حساب / نوع حساب» فقط یک کد دارد")
        existing = {(r.counterparty_type, r.account_type): r for r in db.scalars(select(AccountingCode).where(AccountingCode.tenant_id == user.tenant_id)).all()}
        for key, row in existing.items():
            if key not in pairs:
                db.delete(row)
        for c in data.items:
            row = existing.get((c.counterparty_type, c.account_type))
            if row is None:
                db.add(AccountingCode(tenant_id=user.tenant_id, counterparty_type=c.counterparty_type, account_type=c.account_type, code=c.code, title=c.title))
            else:
                row.code, row.title = c.code, c.title
        if audit:
            audit(db, user, "accounting.codes.saved", "accounting_code_map", {"count": len(data.items)})
        db.commit()
        return codes(user, db)

    def _journal(db: Session, tenant_id: int, date_from: Optional[str], date_to: Optional[str]):
        s = select(TreasuryEntry).where(TreasuryEntry.tenant_id == tenant_id)
        if date_from:
            s = s.where(TreasuryEntry.operation_date >= date_from)
        if date_to:
            s = s.where(TreasuryEntry.operation_date <= date_to)
        entries = db.scalars(s.order_by(TreasuryEntry.operation_date, TreasuryEntry.created_at)).all()
        cmap = {(r.counterparty_type, r.account_type): r for r in db.scalars(select(AccountingCode).where(AccountingCode.tenant_id == tenant_id)).all()}
        rows, unmapped = [], {}
        for i, e in enumerate(entries, start=1):
            code = cmap.get((e.counterparty_type, e.account_type))
            if code is None:
                key = f"{e.counterparty_type}/{e.account_type}"
                unmapped[key] = unmapped.get(key, 0) + 1
            rows.append([e.operation_date, e.id[:8].upper(), i, code.code if code else "", code.title if code else "", e.counterparty_name or e.counterparty_ref,
                         (e.description or e.operation or "")[:250], int(e.debit or 0), int(e.credit or 0), e.currency, e.tracking_no or "", e.contract_ref or ""])
        return rows, unmapped

    def _check_dates(date_from, date_to):
        for d in (date_from, date_to):
            if d and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                raise HTTPException(status_code=422, detail="تاریخ با قالب YYYY-MM-DD لازم است")
        if date_from and date_to and date_from > date_to:
            raise HTTPException(status_code=422, detail="بازه‌ی تاریخ نامعتبر است")

    @api.get("/commerce/treasury/export/check")
    def export_check(date_from: Optional[str] = None, date_to: Optional[str] = None, user=Depends(finance_read), db: Session = Depends(get_db)):
        _check_dates(date_from, date_to)
        rows, unmapped = _journal(db, user.tenant_id, date_from, date_to)
        return {"rows": len(rows), "debit": sum(r[7] for r in rows), "credit": sum(r[8] for r in rows),
                "unmapped": [{"pair": k, "count": v} for k, v in sorted(unmapped.items())]}

    @api.get("/commerce/treasury/export")
    def export(date_from: Optional[str] = None, date_to: Optional[str] = None, fmt: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
               user=Depends(finance_read), db: Session = Depends(get_db)):
        _check_dates(date_from, date_to)
        rows, _ = _journal(db, user.tenant_id, date_from, date_to)
        data = write_xlsx(JOURNAL_HEADER, rows, "سند") if fmt == "xlsx" else write_csv(JOURNAL_HEADER, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "text/csv; charset=utf-8"
        name = f"karenseir-journal-{date_from or 'all'}-{date_to or 'all'}.{fmt}"
        if audit:
            audit(db, user, "accounting.export", "treasury", {"rows": len(rows), "from": date_from, "to": date_to, "fmt": fmt})
            db.commit()
        return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})

    return api
