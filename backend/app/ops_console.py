"""Ops console: unified operations dashboard (پیشخوان عملیات) and the contract file (پرونده‌ی قرارداد).

Everything here is read from rows that already exist (reservations, payments, invoices, treasury, sales desk,
own flight inventory, support). Nothing is estimated: a figure that cannot be computed from data is omitted.

Moadian (سامانه‌ی مؤدیان): the contract file checks whether an issued invoice is ready to be sent and builds the
invoice payload from real rows. Sending needs the company's signing key/certificate and a provider adapter; until
one is configured a prepared invoice stays `waiting_for_provider` — it is never shown as sent or accepted.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

TEHRAN = timezone(timedelta(hours=3, minutes=30))  # Iran has no DST since 2022
OPEN_RES = ("confirmed", "issued", "completed", "changed")
CHANGE_RES = ("cancel_requested", "change_requested", "refund_requested")
STATUS_FA = {"draft": "پیش‌نویس", "booking_pending": "در انتظار میزبان", "pending": "در انتظار تأیید", "reserved": "رزرو شد",
             "awaiting_payment": "در انتظار پرداخت", "confirmed": "تأیید شد", "issued": "صادر شد", "completed": "تکمیل شد",
             "cancel_requested": "درخواست کنسلی", "change_requested": "درخواست تغییر", "refund_requested": "درخواست استرداد",
             "cancelled": "کنسل شد", "changed": "تغییر کرد", "refunded": "مسترد شد", "failed": "ناموفق", "expired": "منقضی"}
MOADIAN_FA = {"not_ready": "آماده‌ی ارسال نیست", "ready": "آماده‌ی ارسال", "waiting_for_provider": "در انتظار اتصال به سامانه",
              "sent": "ارسال شد", "accepted": "پذیرفته شد", "rejected": "رد شد"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aw(dt: Optional[datetime]) -> Optional[datetime]:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def _iso(dt: Optional[datetime]) -> Optional[str]:
    dt = _aw(dt)
    return dt.isoformat() if dt else None


def tehran_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=TEHRAN)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def tehran_today(now: Optional[datetime] = None) -> date:
    return (now or utcnow()).astimezone(TEHRAN).date()


def _snap(raw: Optional[str]) -> dict:
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def snapshot_total(raw: Optional[str]) -> Optional[int]:
    s = _snap(raw)
    for k in ("total_amount", "amount"):
        if isinstance(s.get(k), (int, float)):
            return int(s[k])
    return None


def mask_ref(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value if len(value) <= 4 else "•" * (len(value) - 4) + value[-4:]


class MoadianSettings(OperationalMixin, Base):
    __tablename__ = "ops_moadian_settings"
    economic_code: Mapped[Optional[str]] = mapped_column(String(14), nullable=True)   # شناسه‌ی ملی/کد اقتصادی فروشنده
    memory_id: Mapped[Optional[str]] = mapped_column(String(6), nullable=True)        # شناسه‌ی یکتای حافظه‌ی مالیاتی
    service_codes_json: Mapped[str] = mapped_column(Text, default="{}")               # service_type -> 13-digit شناسه‌ی خدمت
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_moadian_settings_tenant"),)


class MoadianRecord(OperationalMixin, Base):
    __tablename__ = "ops_moadian_records"
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    provider_reference: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)   # taxid / reference from the system
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    prepared_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_id", name="uq_moadian_invoice"),)


def moadian_checks(reservation, invoice, settings: Optional[MoadianSettings]) -> list[dict]:
    codes = _snap(settings.service_codes_json) if settings else {}
    econ = settings.economic_code if settings else None
    mem = settings.memory_id if settings else None
    return [
        {"key": "invoice", "label": "فاکتور رسمی صادر شده باشد", "ok": invoice is not None},
        {"key": "status", "label": "قرارداد قطعی باشد (تأییدشده، صادرشده یا تکمیل‌شده)", "ok": reservation.status in OPEN_RES},
        {"key": "amounts", "label": "جمع مبلغ و مالیات فاکتور با مبلغ کل برابر باشد",
         "ok": invoice is not None and invoice.subtotal_amount + invoice.tax_amount == invoice.total_amount},
        {"key": "economic_code", "label": "شناسه‌ی ملی / کد اقتصادی فروشنده ثبت شده باشد", "ok": bool(econ and re.fullmatch(r"\d{10,14}", econ))},
        {"key": "memory_id", "label": "شناسه‌ی یکتای حافظه‌ی مالیاتی ثبت شده باشد", "ok": bool(mem and re.fullmatch(r"[A-Za-z0-9]{6}", mem))},
        {"key": "service_code", "label": f"شناسه‌ی خدمت برای «{reservation.service_type}» ثبت شده باشد",
         "ok": bool(re.fullmatch(r"\d{13}", str(codes.get(reservation.service_type, ""))))},
    ]


def moadian_payload(reservation, invoice, settings: MoadianSettings) -> dict:
    """Invoice payload in the field names of the Moadian standard (header + one service line). No taxid is
    invented: the unique tax id is produced by the signing adapter when sending."""
    codes = _snap(settings.service_codes_json)
    issued = _aw(invoice.issued_at) or utcnow()
    return {
        "header": {"inno": invoice.invoice_number, "indatim": int(issued.timestamp() * 1000), "inty": 2, "inp": 1, "ins": 1,
                   "tins": settings.economic_code, "tprdis": invoice.subtotal_amount, "tdis": 0, "tadis": invoice.subtotal_amount,
                   "tvam": invoice.tax_amount, "todam": 0, "tbill": invoice.total_amount, "setm": 1},
        "body": [{"sstid": codes.get(reservation.service_type), "sstt": f"{reservation.service_type} {reservation.booking_reference or ''}".strip(),
                  "am": 1, "fee": invoice.subtotal_amount, "prdis": invoice.subtotal_amount, "dis": 0, "adis": invoice.subtotal_amount,
                  "vra": round(invoice.tax_amount * 100 / invoice.subtotal_amount, 2) if invoice.subtotal_amount else 0,
                  "vam": invoice.tax_amount, "tsstam": invoice.total_amount}],
        "memory_id": settings.memory_id, "currency": invoice.currency,
    }


class MoadianSettingsIn(BaseModel):
    economic_code: Optional[str] = Field(default=None, pattern=r"^\d{10,14}$")
    memory_id: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9]{6}$")
    service_codes: dict[str, str] = Field(default_factory=dict)


def ops_console_router(get_db, current_user, role_has_permission, User, audit=None):
    from .charter_quotas import held_seats
    from .commerce import TreasuryEntry, TreasuryRequest
    from .inventory import FlightInstance, FlightRoute, FlightSeries
    from .markup_revenue import AppliedMarkup
    from .sales_desk import OPEN_STAGES, SalesCase, SalesCaseActivity, SalesDeskAgent

    api = APIRouter(tags=["ops-console"])

    def _has(user, *perms):
        return any(role_has_permission(user.role, p) for p in perms)

    def staff(user=Depends(current_user)):
        if user.role in ("employee", "customer") or not _has(user, "backoffice:read", "ledger:read", "tenant:manage"):
            raise HTTPException(status_code=403, detail="دسترسی کارکنان عملیات لازم است")
        return user

    def _settings(db: Session, tenant_id: int) -> Optional[MoadianSettings]:
        return db.scalar(select(MoadianSettings).where(MoadianSettings.tenant_id == tenant_id))

    # ---------------------------------------------------------------- dashboard
    @api.get("/ops/dashboard")
    def dashboard(user=Depends(staff), db: Session = Depends(get_db)):
        t = user.tenant_id
        now = utcnow()
        today = tehran_today(now)
        d0, d1 = tehran_day_bounds(today)
        R = m.Reservation

        def count(q):
            return int(db.scalar(q) or 0)

        new_today = count(select(func.count(R.id)).where(R.tenant_id == t, R.created_at >= d0, R.created_at < d1, R.status != "draft"))
        confirmed_rows = db.execute(select(R.price_snapshot_json).where(R.tenant_id == t, R.confirmed_at >= d0, R.confirmed_at < d1)).scalars().all()
        confirmed_value = sum(v for v in (snapshot_total(s) for s in confirmed_rows) if v)
        captured = db.scalars(select(m.PaymentIntent).where(m.PaymentIntent.tenant_id == t, m.PaymentIntent.captured_amount > 0,
                                                             m.PaymentIntent.updated_at >= d0, m.PaymentIntent.updated_at < d1)).all()
        markup_today = int(db.scalar(select(func.coalesce(func.sum(AppliedMarkup.markup_total), 0)).where(
            AppliedMarkup.tenant_id == t, AppliedMarkup.created_at >= d0, AppliedMarkup.created_at < d1, AppliedMarkup.reversed_entry_id.is_(None))) or 0)
        cases_today = count(select(func.count(SalesCase.id)).where(SalesCase.tenant_id == t, SalesCase.created_at >= d0, SalesCase.created_at < d1))
        open_cases = count(select(func.count(SalesCase.id)).where(SalesCase.tenant_id == t, SalesCase.stage.in_(OPEN_STAGES)))

        kpis = [
            {"key": "new_reservations", "label": "رزرو جدید امروز", "value": new_today, "unit": "count"},
            {"key": "confirmed", "label": "قرارداد تأییدشده امروز", "value": len(confirmed_rows), "unit": "count"},
            {"key": "confirmed_value", "label": "ارزش قراردادهای امروز", "value": confirmed_value, "unit": "IRR"},
            {"key": "captured", "label": "دریافتی درگاه امروز", "value": sum(p.captured_amount for p in captured), "unit": "IRR"},
            {"key": "markup", "label": "سود فروش امروز", "value": markup_today, "unit": "IRR"},
            {"key": "sales_cases", "label": "درخواست فروش امروز", "value": cases_today, "unit": "count", "hint": f"{open_cases} پرونده‌ی باز"},
        ]

        overdue_cases = count(select(func.count(SalesCase.id)).where(SalesCase.tenant_id == t, SalesCase.stage.in_(OPEN_STAGES),
                                                                     SalesCase.next_follow_up_at.is_not(None), SalesCase.next_follow_up_at < now))
        tasks = [
            {"key": "treasury_requests", "label": "واریز/برداشت در انتظار تأیید صندوق", "count": count(select(func.count(TreasuryRequest.id)).where(
                TreasuryRequest.tenant_id == t, TreasuryRequest.status == "submitted")), "href": "/finance/treasury"},
            {"key": "change_requests", "label": "درخواست کنسلی، تغییر یا استرداد", "count": count(select(func.count(R.id)).where(
                R.tenant_id == t, R.status.in_(CHANGE_RES))), "href": "/backoffice/booking-requests"},
            {"key": "awaiting_payment", "label": "رزرو در انتظار پرداخت", "count": count(select(func.count(R.id)).where(
                R.tenant_id == t, R.status == "awaiting_payment")), "href": "/admin/contracts"},
            {"key": "sales_overdue", "label": "پیگیری فروش عقب‌افتاده", "count": overdue_cases, "href": "/admin/sales-desk"},
            {"key": "support_open", "label": "تیکت پشتیبانی باز", "count": count(select(func.count(m.SupportCase.id)).where(
                m.SupportCase.tenant_id == t, func.lower(m.SupportCase.status).notin_(("resolved", "closed", "cancelled")))), "href": "/backoffice/support"},
        ]

        # 30-day series (Tehran days): confirmed contracts and their value
        start_day = today - timedelta(days=29)
        s0, _ = tehran_day_bounds(start_day)
        series = {start_day + timedelta(days=i): {"count": 0, "value": 0} for i in range(30)}
        for confirmed_at, snap in db.execute(select(R.confirmed_at, R.price_snapshot_json).where(R.tenant_id == t, R.confirmed_at >= s0, R.confirmed_at < d1)).all():
            day = _aw(confirmed_at).astimezone(TEHRAN).date()
            if day in series:
                series[day]["count"] += 1
                series[day]["value"] += snapshot_total(snap) or 0
        chart = [{"day": d.isoformat(), **v} for d, v in sorted(series.items())]

        users = {}
        latest = []
        for r in db.scalars(select(R).where(R.tenant_id == t, R.status != "draft").order_by(R.created_at.desc()).limit(10)).all():
            if r.user_id not in users:
                users[r.user_id] = db.scalar(select(User.name).where(User.id == r.user_id))
            latest.append({"id": r.id, "booking_reference": r.booking_reference, "service_type": r.service_type, "status": r.status,
                           "status_fa": STATUS_FA.get(r.status, r.status), "customer": users[r.user_id], "amount": snapshot_total(r.price_snapshot_json),
                           "currency": _snap(r.price_snapshot_json).get("currency") or "IRR", "created_at": _iso(r.created_at)})

        flights = []
        for inst, s, rt in db.execute(select(FlightInstance, FlightSeries, FlightRoute).join(FlightSeries, FlightSeries.id == FlightInstance.series_id)
                                      .join(FlightRoute, FlightRoute.id == FlightSeries.route_id)
                                      .where(FlightInstance.tenant_id == t, FlightInstance.departure_at >= d0, FlightInstance.departure_at < d1)
                                      .order_by(FlightInstance.departure_at)).all():
            held = held_seats(db, t, inst.id)
            offer = db.get(m.Offer, inst.offer_id) if inst.offer_id else None
            available = offer.available_units if offer else None
            flights.append({"id": inst.id, "flight": f"{s.airline_code}{s.flight_number}", "route": f"{rt.origin}-{rt.destination}",
                            "departure_at": _iso(inst.departure_at), "status": inst.status, "capacity": inst.capacity, "held": held,
                            "available": available, "sold": None if available is None else max(0, inst.capacity - available - held),
                            "list_sent": inst.list_sent_at is not None})

        agents = []
        for a in db.scalars(select(SalesDeskAgent).where(SalesDeskAgent.tenant_id == t)).all():
            agents.append({"user_id": a.user_id, "name": db.scalar(select(User.name).where(User.id == a.user_id)), "present": a.present,
                           "open_cases": count(select(func.count(SalesCase.id)).where(SalesCase.tenant_id == t, SalesCase.agent_user_id == a.user_id,
                                                                                      SalesCase.stage.in_(OPEN_STAGES)))})
        channels = [{"channel": c, "count": int(n)} for c, n in db.execute(select(SalesCase.channel, func.count(SalesCase.id)).where(
            SalesCase.tenant_id == t, SalesCase.created_at >= s0).group_by(SalesCase.channel).order_by(func.count(SalesCase.id).desc())).all()]

        # data alerts: inconsistencies visible in the tenant's own rows
        no_invoice = count(select(func.count(R.id)).where(R.tenant_id == t, R.status.in_(OPEN_RES),
                                                         ~select(m.Invoice.id).where(m.Invoice.reservation_id == R.id).exists()))
        paid_unconfirmed = count(select(func.count(func.distinct(m.PaymentIntent.reservation_id))).select_from(m.PaymentIntent).join(R, R.id == m.PaymentIntent.reservation_id).where(
            m.PaymentIntent.tenant_id == t, m.PaymentIntent.captured_amount > m.PaymentIntent.refunded_amount, R.status.in_(("reserved", "awaiting_payment", "pending"))))
        unmatched = count(select(func.count(m.ReconciliationRecord.id)).where(m.ReconciliationRecord.tenant_id == t, m.ReconciliationRecord.status == "UNMATCHED"))
        invoices_total = count(select(func.count(m.Invoice.id)).where(m.Invoice.tenant_id == t, m.Invoice.status == "issued"))
        moadian_done = count(select(func.count(MoadianRecord.id)).where(MoadianRecord.tenant_id == t, MoadianRecord.status.in_(("sent", "accepted"))))
        moadian_rejected = count(select(func.count(MoadianRecord.id)).where(MoadianRecord.tenant_id == t, MoadianRecord.status == "rejected"))
        alerts = [a for a in [
            {"key": "no_invoice", "level": "warn", "count": no_invoice, "label": "قرارداد قطعی بدون فاکتور"},
            {"key": "paid_unconfirmed", "level": "bad", "count": paid_unconfirmed, "label": "پرداخت موفق اما رزرو هنوز تأیید نشده"},
            {"key": "unmatched", "level": "warn", "count": unmatched, "label": "تراکنش تطبیق‌نشده با بانک/درگاه"},
            {"key": "moadian_pending", "level": "warn", "count": max(0, invoices_total - moadian_done), "label": "فاکتور ارسال‌نشده به سامانه‌ی مؤدیان"},
            {"key": "moadian_rejected", "level": "bad", "count": moadian_rejected, "label": "فاکتور ردشده در سامانه‌ی مؤدیان"},
        ] if a["count"]]

        return {"today": today.isoformat(), "generated_at": now.isoformat(), "kpis": kpis, "tasks": tasks, "chart": chart, "latest": latest,
                "flights": flights, "team": {"agents": agents, "channels": channels}, "alerts": alerts}

    # ------------------------------------------------------------ contract file
    @api.get("/ops/contracts")
    def search_contracts(q: Optional[str] = Query(default=None, max_length=80), status: Optional[str] = Query(default=None, max_length=32),
                         user=Depends(staff), db: Session = Depends(get_db)):
        R = m.Reservation
        s = select(R, User.name, User.mobile_e164).join(User, User.id == R.user_id).where(R.tenant_id == user.tenant_id, R.status != "draft")
        if status:
            s = s.where(R.status == status)
        if q:
            like = f"%{q.strip()}%"
            s = s.where(or_(R.booking_reference.ilike(like), User.name.ilike(like), User.mobile_e164.ilike(like), R.id == q.strip()))
        rows = db.execute(s.order_by(R.created_at.desc()).limit(50)).all()
        return {"items": [{"id": r.id, "booking_reference": r.booking_reference, "service_type": r.service_type, "status": r.status,
                           "status_fa": STATUS_FA.get(r.status, r.status), "customer": name, "mobile": mask_ref(mobile),
                           "amount": snapshot_total(r.price_snapshot_json), "created_at": _iso(r.created_at)} for r, name, mobile in rows]}

    def _reservation(db: Session, user, rid: str):
        r = db.scalar(select(m.Reservation).where(m.Reservation.id == rid, m.Reservation.tenant_id == user.tenant_id))
        if r is None:
            raise HTTPException(status_code=404, detail="قرارداد یافت نشد")
        return r

    @api.get("/ops/contracts/{reservation_id}")
    def contract_file(reservation_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        t = user.tenant_id
        r = _reservation(db, user, reservation_id)
        snap = _snap(r.price_snapshot_json)
        customer = db.execute(select(User.name, User.email, User.mobile_e164).where(User.id == r.user_id)).first()
        names: dict[int, str] = {}

        def name_of(uid):
            if uid is None:
                return None
            if uid not in names:
                names[uid] = db.scalar(select(User.name).where(User.id == uid))
            return names[uid]

        # case path: sales-desk case (if any) + booking status history
        case = db.scalar(select(SalesCase).where(SalesCase.tenant_id == t, SalesCase.reservation_id == r.id))
        path = []
        if case:
            path.append({"at": _iso(case.created_at), "kind": "sales_case", "title": f"درخواست فروش {case.code} از کانال {case.channel}", "actor": name_of(case.agent_user_id)})
            for a in db.scalars(select(SalesCaseActivity).where(SalesCaseActivity.case_id == case.id).order_by(SalesCaseActivity.created_at)).all():
                path.append({"at": _iso(a.created_at), "kind": f"sales_{a.kind}", "title": (a.body or a.kind)[:200], "actor": name_of(a.actor_user_id)})
        for h in db.scalars(select(m.BookingStatusHistory).where(m.BookingStatusHistory.tenant_id == t, m.BookingStatusHistory.reservation_id == r.id)
                            .order_by(m.BookingStatusHistory.created_at)).all():
            path.append({"at": _iso(h.created_at), "kind": "status", "title": f"{STATUS_FA.get(h.from_status or '', h.from_status or 'شروع')} ← {STATUS_FA.get(h.to_status, h.to_status)}",
                         "actor": name_of(h.actor_id), "reason": h.reason})
        path.sort(key=lambda x: x["at"] or "")

        # services: booking items + applied markup (net / markup / sell)
        markup = db.scalar(select(AppliedMarkup).where(AppliedMarkup.tenant_id == t, AppliedMarkup.reservation_id == r.id))
        items = []
        for it in db.scalars(select(m.BookingItem).where(m.BookingItem.tenant_id == t, m.BookingItem.reservation_id == r.id)).all():
            s = _snap(it.snapshot_json)
            items.append({"id": it.id, "item_type": it.item_type, "title": s.get("title") or s.get("name") or it.item_type,
                          "units": s.get("units"), "amount": s.get("total_amount") or s.get("amount")})
        invoice = db.scalar(select(m.Invoice).where(m.Invoice.tenant_id == t, m.Invoice.reservation_id == r.id))
        services = {"items": items, "net": markup.net_total if markup else None, "markup": markup.markup_total if markup else None,
                    "sell": markup.sell_total if markup else snapshot_total(r.price_snapshot_json),
                    "markup_reversed": bool(markup and markup.reversed_entry_id), "rule": markup.rule_title if markup else None,
                    "tax": invoice.tax_amount if invoice else None, "currency": snap.get("currency") or "IRR"}

        # payments and finance
        intents = db.scalars(select(m.PaymentIntent).where(m.PaymentIntent.tenant_id == t, m.PaymentIntent.reservation_id == r.id).order_by(m.PaymentIntent.created_at)).all()
        payments = [{"id": p.id, "kind": "gateway", "amount": p.amount, "captured": p.captured_amount, "refunded": p.refunded_amount, "status": p.status,
                     "reference": mask_ref(p.provider_capture_reference or p.provider_reference), "at": _iso(p.created_at)} for p in intents]
        treasury = db.scalars(select(TreasuryEntry).where(TreasuryEntry.tenant_id == t, TreasuryEntry.contract_ref == r.booking_reference)
                              .order_by(TreasuryEntry.created_at)).all() if r.booking_reference else []
        for e in treasury:
            payments.append({"id": e.id, "kind": "treasury", "account_type": e.account_type, "operation": e.operation, "debit": e.debit, "credit": e.credit,
                             "reference": mask_ref(e.tracking_no), "at": _iso(e.created_at)})
        total = services["sell"]
        paid = sum(p.captured_amount - p.refunded_amount for p in intents)
        finance = {"total": total, "paid_gateway": paid, "balance": None if total is None else total - paid, "currency": services["currency"],
                   "invoice": None if invoice is None else {"id": invoice.id, "number": invoice.invoice_number, "subtotal": invoice.subtotal_amount,
                                                            "tax": invoice.tax_amount, "total": invoice.total_amount, "status": invoice.status,
                                                            "issued_at": _iso(invoice.issued_at)}}

        travellers = [{"id": tr.id, "full_name": tr.full_name, "document": mask_ref(tr.profile_reference)} for tr in db.scalars(
            select(m.Traveller).join(m.ReservationTraveller, m.ReservationTraveller.traveller_id == m.Traveller.id)
            .where(m.ReservationTraveller.reservation_id == r.id, m.Traveller.tenant_id == t)).all()]
        if not travellers and snap.get("travellers") is not None:
            travellers_note = f"{snap.get('travellers')} مسافر در قیمت ثبت شده، ولی مشخصات مسافران هنوز وارد نشده است"
        else:
            travellers_note = None

        requests = [{"id": q.id, "type": q.request_type, "case_type": q.case_type, "status": q.status, "reason": q.reason, "at": _iso(q.created_at)}
                    for q in db.scalars(select(m.BookingServiceRequest).where(m.BookingServiceRequest.tenant_id == t, m.BookingServiceRequest.reservation_id == r.id)
                                        .order_by(m.BookingServiceRequest.created_at)).all()]
        support = [{"id": c.id, "subject": c.subject, "status": c.status, "at": _iso(c.created_at)} for c in db.scalars(
            select(m.SupportCase).where(m.SupportCase.tenant_id == t, m.SupportCase.reservation_id == r.id)).all()]

        settings = _settings(db, t)
        rec = db.scalar(select(MoadianRecord).where(MoadianRecord.tenant_id == t, MoadianRecord.reservation_id == r.id).order_by(MoadianRecord.created_at.desc()))
        checks = moadian_checks(r, invoice, settings)
        if rec:
            mstatus = rec.status
        else:
            mstatus = "ready" if all(c["ok"] for c in checks) else "not_ready"
        moadian = {"status": mstatus, "status_fa": MOADIAN_FA[mstatus], "checks": checks, "record_id": rec.id if rec else None,
                   "provider_reference": rec.provider_reference if rec else None, "error": rec.error if rec else None,
                   "prepared_at": _iso(rec.created_at) if rec else None}

        return {"id": r.id, "booking_reference": r.booking_reference, "service_type": r.service_type, "status": r.status,
                "status_fa": STATUS_FA.get(r.status, r.status), "created_at": _iso(r.created_at), "confirmed_at": _iso(r.confirmed_at),
                "customer": None if customer is None else {"name": customer[0], "email": customer[1], "mobile": customer[2]},
                "sales_case": None if case is None else {"id": case.id, "code": case.code, "channel": case.channel, "agent": name_of(case.agent_user_id)},
                "path": path, "services": services, "finance": finance, "payments": payments, "travellers": travellers, "travellers_note": travellers_note,
                "cancellation": {"policy_at_booking": _snap(r.policy_at_booking_json), "requests": requests}, "support": support, "moadian": moadian}

    # ------------------------------------------------------------------ moadian
    @api.get("/ops/moadian/settings")
    def get_moadian_settings(user=Depends(staff), db: Session = Depends(get_db)):
        s = _settings(db, user.tenant_id)
        return {"economic_code": s.economic_code if s else None, "memory_id": s.memory_id if s else None,
                "service_codes": _snap(s.service_codes_json) if s else {}, "provider_connected": False,
                "provider_note": "ارسال واقعی به سامانه‌ی مؤدیان به کلید خصوصی و گواهی امضای شرکت و اتصال رسمی نیاز دارد و هنوز تنظیم نشده است."}

    @api.put("/ops/moadian/settings")
    def put_moadian_settings(data: MoadianSettingsIn, user=Depends(current_user), db: Session = Depends(get_db)):
        if not _has(user, "tenant:manage"):
            raise HTTPException(status_code=403, detail="فقط مدیر مجموعه می‌تواند تنظیمات مؤدیان را تغییر دهد")
        for k, v in data.service_codes.items():
            if not re.fullmatch(r"[a-z_]{2,48}", k) or not re.fullmatch(r"\d{13}", v):
                raise HTTPException(status_code=422, detail=f"شناسه‌ی خدمت «{k}» باید ۱۳ رقم باشد")
        s = _settings(db, user.tenant_id)
        if s is None:
            s = MoadianSettings(tenant_id=user.tenant_id)
            db.add(s)
        s.economic_code, s.memory_id = data.economic_code, data.memory_id
        s.service_codes_json = json.dumps(data.service_codes, sort_keys=True)
        s.updated_by = user.id
        if audit:
            audit(db, user, "moadian.settings.updated", "ops_moadian_settings", {"economic_code": mask_ref(data.economic_code), "services": sorted(data.service_codes)})
        db.commit()
        return get_moadian_settings(user, db)

    @api.post("/ops/contracts/{reservation_id}/moadian", status_code=201)
    def prepare_moadian(reservation_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
        if user.role in ("employee", "customer") or not _has(user, "invoice:manage", "tenant:manage"):
            raise HTTPException(status_code=403, detail="دسترسی صدور فاکتور لازم است")
        r = _reservation(db, user, reservation_id)
        invoice = db.scalar(select(m.Invoice).where(m.Invoice.tenant_id == user.tenant_id, m.Invoice.reservation_id == r.id))
        settings = _settings(db, user.tenant_id)
        failed = [c["label"] for c in moadian_checks(r, invoice, settings) if not c["ok"]]
        if failed:
            raise HTTPException(status_code=409, detail="آماده‌ی ارسال نیست: " + "؛ ".join(failed))
        rec = db.scalar(select(MoadianRecord).where(MoadianRecord.tenant_id == user.tenant_id, MoadianRecord.invoice_id == invoice.id))
        if rec and rec.status in ("sent", "accepted"):
            raise HTTPException(status_code=409, detail="این فاکتور قبلاً به سامانه ارسال شده است")
        if rec is None:
            rec = MoadianRecord(tenant_id=user.tenant_id, reservation_id=r.id, invoice_id=invoice.id)
            db.add(rec)
        rec.payload_json = json.dumps(moadian_payload(r, invoice, settings), ensure_ascii=False, sort_keys=True)
        rec.attempts = (rec.attempts or 0) + 1
        rec.prepared_by = user.id
        # No signing adapter is configured: keep it queued honestly instead of pretending it was sent.
        rec.status, rec.error = "waiting_for_provider", None
        db.flush()
        if audit:
            audit(db, user, "moadian.invoice.prepared", "ops_moadian_record", {"record_id": rec.id, "invoice": invoice.invoice_number, "reservation_id": r.id})
        db.commit()
        return {"id": rec.id, "status": rec.status, "status_fa": MOADIAN_FA[rec.status], "payload": json.loads(rec.payload_json)}

    return api
