"""Markup-rule import from Excel/CSV (PR-7): template → upload → per-row errors (review) → confirm.

Same mechanics as the sales-desk lead import (data_exchange.py, tabular.py). Every row is validated through the same
MarkupIn model and checks as the markup form, so an import cannot create a rule the form could not. Confirm re-reads and
re-validates the file and is all-or-nothing: one bad row and nothing is written. Nothing is pre-loaded.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import operations as m
from .tabular import TableError

# key -> accepted header names (first is the template header)
COLUMNS = {
    "title": ("عنوان",),
    "service_type": ("نوع خدمت",),
    "group": ("گروه", "گروه قیمتی", "گروه مشتری"),
    "supplier": ("تأمین‌کننده", "تامین کننده", "تأمین کننده"),
    "scope": ("داخلی/خارجی", "داخلی یا خارجی", "محدوده"),
    "flight_type": ("سیستمی/چارتری", "سیستمی یا چارتری", "نوع پرواز"),
    "airline_code": ("ایرلاین", "کد ایرلاین", "شرکت هواپیمایی"),
    "origin": ("مبدأ", "مبدا"),
    "destination": ("مقصد",),
    "pct_adult": ("درصد بزرگسال",),
    "pct_child": ("درصد کودک",),
    "pct_infant": ("درصد نوزاد",),
    "fix_adult": ("مبلغ ثابت بزرگسال",),
    "fix_child": ("مبلغ ثابت کودک",),
    "fix_infant": ("مبلغ ثابت نوزاد",),
    "active": ("فعال",),
}
TEMPLATE_HEADER = [names[0] for names in COLUMNS.values()]
TEMPLATE_SAMPLE = [["نمونه — این ردیف را پاک کنید", "پرواز", "", "نیرا", "داخلی", "سیستمی", "VR", "THR", "MHD", "5", "5", "0", "", "", "", "بله"]]

SERVICE_FA = {"پرواز": "flight", "هتل": "hotel", "تور": "tour", "قطار": "train", "اتوبوس": "bus", "بیمه": "insurance", "ویزا": "visa",
              "بسته": "package", "پکیج": "package", "سی‌آی‌پی": "cip", "ترانسفر": "transfer", "همه": "any"}
SCOPE_FA = {"": "any", "همه": "any", "داخلی": "domestic", "خارجی": "international", "any": "any", "domestic": "domestic", "international": "international"}
FLIGHT_TYPE_FA = {"": "any", "همه": "any", "سیستمی": "system", "چارتری": "charter", "any": "any", "system": "system", "charter": "charter"}
YES = {"", "بله", "آری", "فعال", "1", "true", "yes", "y"}
NO = {"خیر", "نه", "غیرفعال", "0", "false", "no", "n"}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def latin_digits(value: str) -> str:
    return (value or "").translate(_DIGITS)


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").replace("‌", " ").replace("ي", "ی").replace("ك", "ک").replace("أ", "ا").strip())


def _norm_text(v: str) -> str:
    return _norm_header(v).lower()


def map_columns(header: list[str]) -> dict[str, int]:
    norm = [_norm_header(h) for h in header]
    found: dict[str, int] = {}
    for key, names in COLUMNS.items():
        wanted = {_norm_header(n) for n in names}
        for i, h in enumerate(norm):
            if h in wanted:
                found[key] = i
                break
    return found


def parse_percent(raw: str) -> Optional[int]:
    """'۱۲٫۵٪' → 1250 basis points. Empty → None. Raises ValueError for anything else (max two decimals)."""
    text = latin_digits(raw).replace("٪", "").replace("%", "").replace("٫", ".").replace("/", ".").strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError("درصد عدد نیست")
    if not value.is_finite():                                   # NaN / Infinity: a row error, never a 500
        raise ValueError("درصد عدد نیست")
    bps = value * 100
    if value < 0 or bps != bps.to_integral_value():
        raise ValueError("درصد باید مثبت و حداکثر با دو رقم اعشار باشد")
    return int(bps)


def excel_percent_fraction(raw: str) -> bool:
    """True for a bare fraction 0 < v < 1 with no % sign (e.g. 0.05): what an Excel cell with the «Percent» format
    stores for 5%. Read as-is it would be a 0.05% rule, so the row is rejected with a clear message instead."""
    text = latin_digits(raw).replace("٫", ".").replace("/", ".").strip()
    if not text or "%" in text or "٪" in text:
        return False
    try:
        value = Decimal(text)
    except InvalidOperation:
        return False
    return value.is_finite() and 0 < value < 1


def parse_amount(raw: str) -> Optional[int]:
    """'۱٬۵۰۰٬۰۰۰' → 1500000 rial. Empty → None."""
    text = re.sub(r"[\s,،٬]", "", latin_digits(raw))
    if not text:
        return None
    if not text.isdigit():
        raise ValueError("مبلغ ثابت باید عدد صحیح ریالی باشد")
    return int(text)


AMBIGUOUS = "\x00ambiguous"


def _put(index: dict, key: str, value: str) -> None:
    """Two different targets under one name → the name is ambiguous (row error), never a silent first-wins."""
    if key in index and index[key] != value:
        index[key] = AMBIGUOUS
    else:
        index[key] = value


def _supplier_index(db: Session, tenant_id: int) -> dict[str, str]:
    """name / provider_key / id → the value a markup rule stores (provider_key for web services, else the supplier id)."""
    index = {"mahan": "mahan", "ماهان": "mahan", "nira": "nira", "نیرا": "nira"}
    for s in db.scalars(select(m.Supplier).where(m.Supplier.tenant_id == tenant_id)):
        value = s.provider_key or s.id
        _put(index, _norm_text(s.display_name), value)
        index[s.id.lower()] = value
        if s.provider_key:
            index[s.provider_key] = value
    return index


def validate_rules(db: Session, tenant_id: int, rows: list[list[str]]) -> dict:
    from .commerce import CustomerGroup, MarkupIn
    if not rows:
        raise TableError("فایل خالی است")
    cols = map_columns(rows[0])
    if not any(k in cols for k in ("pct_adult", "fix_adult")):
        raise TableError("ستون «درصد بزرگسال» یا «مبلغ ثابت بزرگسال» پیدا نشد؛ از فایل نمونه استفاده کنید")
    groups = {}
    for g in db.scalars(select(CustomerGroup).where(CustomerGroup.tenant_id == tenant_id, CustomerGroup.status == "active")):
        _put(groups, _norm_text(g.name), g.id)
        _put(groups, _norm_text(g.code), g.id)
    suppliers = _supplier_index(db, tenant_id)
    from .commerce import MarkupRule
    existing = {tuple(getattr(r, k) for k in ("service_type", "group_id", "supplier_id", "scope", "flight_type", "airline_code", "origin", "destination"))
                for r in db.scalars(select(MarkupRule).where(MarkupRule.tenant_id == tenant_id, MarkupRule.status == "active"))}
    seen: dict[tuple, int] = {}
    out = []
    for n, raw in enumerate(rows[1:], start=2):
        get = lambda k: (str(raw[cols[k]]) if k in cols and cols[k] < len(raw) else "").strip()  # noqa: E731
        if not any(str(c).strip() for c in raw):
            continue
        errors: list[str] = []
        warnings: list[str] = []
        rec: dict = {}
        svc_raw = _norm_text(get("service_type"))
        rec["service_type"] = SERVICE_FA.get(svc_raw, svc_raw) if svc_raw else "flight"
        group = _norm_text(get("group"))
        rec["group_id"] = None
        if group and group != "همه":
            rec["group_id"] = groups.get(group)
            if rec["group_id"] == AMBIGUOUS:
                errors.append(f"چند گروه با نام «{get('group')}» هست؛ کد گروه را بنویسید")
            elif rec["group_id"] is None:
                errors.append(f"گروه «{get('group')}» در این مجموعه نیست (گروه‌ها خودکار ساخته نمی‌شوند)")
        supplier = _norm_text(get("supplier"))
        rec["supplier_id"] = None
        if supplier and supplier != "همه":
            rec["supplier_id"] = suppliers.get(supplier)
            if rec["supplier_id"] == AMBIGUOUS:
                errors.append(f"چند تأمین‌کننده با نام «{get('supplier')}» هست؛ شناسهٔ تأمین‌کننده را بنویسید")
            elif rec["supplier_id"] is None:
                errors.append(f"تأمین‌کننده «{get('supplier')}» پیدا نشد")
        for key, table, label in (("scope", SCOPE_FA, "داخلی/خارجی"), ("flight_type", FLIGHT_TYPE_FA, "سیستمی/چارتری")):
            value = _norm_text(get(key))
            rec[key] = table.get(value)
            if rec[key] is None:
                errors.append(f"مقدار «{get(key)}» برای {label} معتبر نیست")
                rec[key] = value
        for key in ("airline_code", "origin", "destination"):
            value = latin_digits(get(key)).strip().upper()
            rec[key] = None if value in ("", "همه") else value
            if rec[key] and not re.fullmatch(r"[A-Z0-9]{2,8}", rec[key]):
                errors.append(f"کد «{get(key)}» باید لاتین باشد (مثل THR یا W5)")
        pct, fix = {}, {}
        for pax in ("adult", "child", "infant"):
            if excel_percent_fraction(get("pct_" + pax)):
                errors.append(f"{COLUMNS['pct_' + pax][0]}: مقدار «{get('pct_' + pax)}» کسری است و احتمالاً سلول اکسل قالب «درصد» دارد "
                              f"(مثلاً 0.05 یعنی ۵٪)؛ قالب سلول را «عدد» کنید و درصد را به صورت عدد کامل بنویسید (مثلاً 5)، "
                              f"یا اگر واقعاً کمتر از ۱٪ است علامت ٪ را هم بنویسید (مثلاً 0.5٪)")
                pct[pax] = None
                continue
            try:
                pct[pax] = parse_percent(get("pct_" + pax))
            except ValueError as exc:
                errors.append(f"{COLUMNS['pct_' + pax][0]}: {exc}")
            try:
                fix[pax] = parse_amount(get("fix_" + pax))
            except ValueError as exc:
                errors.append(f"{COLUMNS['fix_' + pax][0]}: {exc}")
        has_pct = any(v is not None for v in pct.values())
        has_fix = any(v is not None for v in fix.values())
        if has_pct and has_fix:
            errors.append("در یک ردیف یا درصد بنویسید یا مبلغ ثابت، نه هر دو")
        elif not has_pct and not has_fix:
            errors.append("درصد یا مبلغ ثابت بزرگسال خالی است")
        rec["calc"] = "fixed" if has_fix and not has_pct else "percent"
        source = fix if rec["calc"] == "fixed" else pct
        for pax in ("adult", "child", "infant"):
            rec[pax] = source.get(pax) or 0
        if rec["calc"] == "percent" and 0 < rec["adult"] < 100:
            warnings.append("درصد بزرگسال کمتر از ۱٪ است؛ اگر سلول در اکسل قالب «درصد» دارد، عدد را بدون قالب (مثلاً 5) بنویسید")
        if rec["calc"] == "percent" and max(rec["adult"], rec["child"], rec["infant"]) > 100000:
            errors.append("درصد بیش از حد مجاز است")
        active = _norm_text(get("active"))
        rec["status"] = "active" if active in YES else "disabled" if active in NO else None
        if rec["status"] is None:
            errors.append(f"ستون فعال باید «بله» یا «خیر» باشد، نه «{get('active')}»")
            rec["status"] = active
        title = get("title")
        if not title or title.startswith("نمونه"):
            if title.startswith("نمونه"):
                errors.append("ردیف نمونه را پاک کنید")
            parts = [get("supplier") or "همه", get("scope") or "", get("flight_type") or "", rec.get("airline_code") or "", "-".join(x for x in (rec.get("origin"), rec.get("destination")) if x)]
            title = "ورود اکسل: " + " ".join(p for p in parts if p)
        rec["title"] = title[:160]
        if not errors:
            try:
                rec = MarkupIn(**rec).model_dump()
            except ValidationError as exc:
                errors.extend(str(e.get("msg", "")).replace("Value error, ", "") for e in exc.errors())
        if not errors:
            key = tuple(rec.get(k) for k in ("service_type", "group_id", "supplier_id", "scope", "flight_type", "airline_code", "origin", "destination"))
            if key in existing:
                warnings.append("قاعدهٔ فعالی با همین شرط‌ها از قبل هست؛ با ثبت این ردیف دو قاعده خواهید داشت")
            if key in seen:
                warnings.append(f"همان شرط‌های ردیف {seen[key]}؛ هر دو ثبت می‌شوند و قاعدهٔ اول (اولویت یکسان) برنده است")
            else:
                seen[key] = n
        out.append({"row": n, "data": rec, "errors": errors, "warnings": warnings})
    return {"rows": out, "total": len(out), "valid": sum(not r["errors"] for r in out), "errors": sum(bool(r["errors"]) for r in out),
            "warnings": sum(bool(r["warnings"]) for r in out)}
