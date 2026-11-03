"""Supplier performance and purchase reconciliation (تأمین‌کنندگان: نرخ کنسلی و تطبیق خرید).

* Cancellation rate per supplier over a window: reservations whose price snapshot names the supplier, or that carry a
  supplier cost entry in the treasury book. Rate = cancelled-or-failed / all non-draft. No supplier link -> not counted.
* Purchase reconciliation: the supplier's own statement (xlsx/csv with reference, date, amount) is compared with our
  supplier purchase entries (treasury `purchase` credits to that supplier). Matching is by reference against our
  booking reference, reservation id or tracking number. Result: matched, amount differs, only in their statement,
  only in our book. A confirmed run is stored as evidence; nothing is posted automatically.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

CANCELLED = ("cancelled", "failed", "refunded", "expired")
REF_COLS = ("شماره", "مرجع", "شماره رزرو", "کد رزرو", "شماره سند", "ref", "reference", "booking", "pnr", "voucher")
DATE_COLS = ("تاریخ", "date")
AMOUNT_COLS = ("مبلغ", "مبلغ ریال", "بدهکار", "بستانکار", "amount", "total")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _norm(h: str) -> str:
    return re.sub(r"[\s‌_]+", " ", (h or "").strip().lower())


def _amount(v: str) -> Optional[int]:
    v = (v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).replace(",", "").replace("٬", "").strip()
    if not re.fullmatch(r"-?\d+(\.0+)?", v):
        return None
    return int(float(v))


def parse_statement(rows: list[list[str]]) -> tuple[list[dict], list[str]]:
    if not rows:
        return [], ["فایل خالی است"]
    header = [_norm(h) for h in rows[0]]

    def col(names):
        for n in names:
            if _norm(n) in header:
                return header.index(_norm(n))
        return None

    ri, di, ai = col(REF_COLS), col(DATE_COLS), col(AMOUNT_COLS)
    if ri is None or ai is None:
        return [], ["ستون «شماره/مرجع» و «مبلغ» در سطر اول لازم است"]
    items, errors = [], []
    for n, r in enumerate(rows[1:], start=2):
        if not any((c or "").strip() for c in r):
            continue
        ref = (r[ri] if ri < len(r) else "").strip()
        amt = _amount(r[ai] if ai < len(r) else "")
        if not ref or amt is None:
            errors.append(f"سطر {n}: شماره یا مبلغ نامعتبر")
            continue
        items.append({"ref": ref, "date": (r[di] if di is not None and di < len(r) else "").strip() or None, "amount": abs(amt), "row": n})
    return items, errors


def reconcile(theirs: list[dict], ours: list[dict]) -> dict:
    """ours: {id, refs:[...], amount, date, booking}. Each of ours matches at most one of theirs."""
    index: dict[str, dict] = {}
    for o in ours:
        for r in o["refs"]:
            if r:
                index.setdefault(r.strip().upper(), o)
    used, matched, differs, only_theirs = set(), [], [], []
    for t in theirs:
        o = index.get(t["ref"].upper())
        if o is None or o["id"] in used:
            only_theirs.append(t)
            continue
        used.add(o["id"])
        row = {"ref": t["ref"], "their_amount": t["amount"], "our_amount": o["amount"], "date": t["date"] or o["date"], "booking": o["booking"]}
        (matched if t["amount"] == o["amount"] else differs).append({**row, "difference": t["amount"] - o["amount"]})
    only_ours = [{"ref": o["booking"] or o["refs"][0], "our_amount": o["amount"], "date": o["date"]} for o in ours if o["id"] not in used]
    return {"matched": matched, "amount_differs": differs, "only_theirs": only_theirs, "only_ours": only_ours,
            "totals": {"theirs": sum(t["amount"] for t in theirs), "ours": sum(o["amount"] for o in ours),
                       "difference": sum(t["amount"] for t in theirs) - sum(o["amount"] for o in ours)}}


class SupplierReconRun(OperationalMixin, Base):
    __tablename__ = "supplier_recon_runs"
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    date_from: Mapped[str] = mapped_column(String(10))
    date_to: Mapped[str] = mapped_column(String(10))
    filename: Mapped[str] = mapped_column(String(200))
    matched: Mapped[int] = mapped_column(Integer, default=0)
    differs: Mapped[int] = mapped_column(Integer, default=0)
    only_theirs: Mapped[int] = mapped_column(Integer, default=0)
    only_ours: Mapped[int] = mapped_column(Integer, default=0)
    difference: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


def supplier_insights_router(get_db, current_user, role_has_permission, User, audit=None):
    from .commerce import TreasuryEntry
    from .tabular import TableError, read_table

    api = APIRouter(tags=["supplier-insights"])

    def finance(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("ledger:read", "reconciliation:manage", "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مالی لازم است")
        return user

    @api.get("/commerce/suppliers/insights")
    def insights(days: int = Query(default=90, ge=7, le=730), user=Depends(finance), db: Session = Depends(get_db)):
        since = utcnow() - timedelta(days=days)
        t = user.tenant_id
        link: dict[str, str] = {}
        for rid, snap in db.execute(select(m.Reservation.id, m.Reservation.price_snapshot_json).where(m.Reservation.tenant_id == t, m.Reservation.created_at >= since)).all():
            try:
                sid = (json.loads(snap or "{}") or {}).get("supplier_id")
            except ValueError:
                sid = None
            if sid:
                link[rid] = str(sid)
        for ref, sid in db.execute(select(TreasuryEntry.purchase_ref, TreasuryEntry.counterparty_ref).where(
                TreasuryEntry.tenant_id == t, TreasuryEntry.counterparty_type == "supplier", TreasuryEntry.operation == "purchase", TreasuryEntry.purchase_ref.is_not(None))).all():
            link.setdefault(ref, sid)
        stats: dict[str, dict] = {}
        if link:
            for rid, st, created in db.execute(select(m.Reservation.id, m.Reservation.status, m.Reservation.created_at).where(
                    m.Reservation.tenant_id == t, m.Reservation.id.in_(list(link)), m.Reservation.created_at >= since, m.Reservation.status != "draft")).all():
                s = stats.setdefault(link[rid], {"reservations": 0, "cancelled": 0})
                s["reservations"] += 1
                if st in CANCELLED:
                    s["cancelled"] += 1
        purchase_totals: dict[str, int] = {}
        for sid, v in db.execute(select(TreasuryEntry.counterparty_ref, TreasuryEntry.credit).where(
                TreasuryEntry.tenant_id == t, TreasuryEntry.counterparty_type == "supplier", TreasuryEntry.operation == "purchase", TreasuryEntry.created_at >= since)).all():
            purchase_totals[sid] = purchase_totals.get(sid, 0) + int(v or 0)
        last_runs = {}
        for r in db.scalars(select(SupplierReconRun).where(SupplierReconRun.tenant_id == t).order_by(SupplierReconRun.created_at)).all():
            last_runs[r.supplier_id] = r
        items = []
        for sup in db.scalars(select(m.Supplier).where(m.Supplier.tenant_id == t).order_by(m.Supplier.display_name)).all():
            s = stats.get(sup.id, {"reservations": 0, "cancelled": 0})
            run = last_runs.get(sup.id)
            items.append({"id": sup.id, "name": sup.display_name, "type": sup.supplier_type, "status": sup.status, **s,
                          "cancellation_rate": round(100 * s["cancelled"] / s["reservations"], 1) if s["reservations"] else None,
                          "purchases": purchase_totals.get(sup.id, 0),
                          "last_recon": None if run is None else {"at": run.created_at.isoformat(), "matched": run.matched, "differs": run.differs,
                                                                   "only_theirs": run.only_theirs, "only_ours": run.only_ours, "difference": run.difference}})
        return {"days": days, "items": items}

    @api.post("/commerce/suppliers/{supplier_id}/reconcile")
    async def reconcile_statement(supplier_id: str, file: UploadFile = File(...), date_from: str = Form(...), date_to: str = Form(...),
                                  confirm: bool = Form(default=False), user=Depends(finance), db: Session = Depends(get_db)):
        for d in (date_from, date_to):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                raise HTTPException(status_code=422, detail="تاریخ با قالب YYYY-MM-DD لازم است")
        if date_from > date_to:
            raise HTTPException(status_code=422, detail="بازه‌ی تاریخ نامعتبر است")
        sup = db.scalar(select(m.Supplier).where(m.Supplier.id == supplier_id, m.Supplier.tenant_id == user.tenant_id))
        if sup is None:
            raise HTTPException(status_code=404, detail="تأمین‌کننده یافت نشد")
        data = await file.read(5 * 1024 * 1024 + 1)
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=422, detail="حجم فایل بیش از ۵ مگابایت است")
        try:
            rows = read_table(file.filename or "", data)
        except TableError as e:
            raise HTTPException(status_code=422, detail=str(e))
        theirs, errors = parse_statement(rows)
        if not theirs and errors:
            raise HTTPException(status_code=422, detail=errors[0])
        entries = db.scalars(select(TreasuryEntry).where(TreasuryEntry.tenant_id == user.tenant_id, TreasuryEntry.counterparty_type == "supplier",
                                                         TreasuryEntry.counterparty_ref == supplier_id, TreasuryEntry.operation == "purchase",
                                                         TreasuryEntry.operation_date >= date_from, TreasuryEntry.operation_date <= date_to)).all()
        reversed_ids = {e.reversal_of_id for e in entries if e.reversal_of_id}
        ours = [{"id": e.id, "refs": [e.contract_ref, e.purchase_ref, e.tracking_no], "amount": int(e.credit or 0), "date": e.operation_date, "booking": e.contract_ref}
                for e in entries if e.credit and e.id not in reversed_ids and not e.reversal_of_id]
        result = reconcile(theirs, ours)
        result["errors"] = errors
        if confirm:
            run = SupplierReconRun(tenant_id=user.tenant_id, supplier_id=supplier_id, date_from=date_from, date_to=date_to, filename=(file.filename or "")[:200],
                                   matched=len(result["matched"]), differs=len(result["amount_differs"]), only_theirs=len(result["only_theirs"]),
                                   only_ours=len(result["only_ours"]), difference=result["totals"]["difference"],
                                   result_json=json.dumps(result, ensure_ascii=False), created_by=user.id)
            db.add(run)
            db.flush()
            if audit:
                audit(db, user, "supplier.reconciliation.saved", "supplier_recon_run", {"run_id": run.id, "supplier_id": supplier_id})
            db.commit()
            result["run_id"] = run.id
        return result

    @api.get("/commerce/suppliers/{supplier_id}/reconciliations")
    def runs(supplier_id: str, user=Depends(finance), db: Session = Depends(get_db)):
        rows = db.scalars(select(SupplierReconRun).where(SupplierReconRun.tenant_id == user.tenant_id, SupplierReconRun.supplier_id == supplier_id)
                          .order_by(SupplierReconRun.created_at.desc()).limit(50)).all()
        return {"items": [{"id": r.id, "at": r.created_at.isoformat(), "from": r.date_from, "to": r.date_to, "file": r.filename, "matched": r.matched,
                           "differs": r.differs, "only_theirs": r.only_theirs, "only_ours": r.only_ours, "difference": r.difference} for r in rows]}

    return api
