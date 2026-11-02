"""Sales desk ("میز گفتگو و فروش") — KarenSeir's own design.

One sales case per customer request, from the first contact to the trip and the
survey. Replaces the split CheckLine flow (WordPress sales cases + Citynet
contracts glued together by a manual sync).

- 13 intake channels, 8 stages with explicit transitions (any stage -> lost,
  lost -> new to reopen)
- presence of agents and round-robin auto-assignment among present agents
- first-response SLA: alert and automatic reassignment sweep
- quote (amount + validity) with a message rendered from the tenant templates
- link to a real reservation of the same tenant
- complaint owner, monthly targets, team table and today's KPIs

All amounts are integer IRR. Nothing here touches payments or the ledger: a case
only *points* to a reservation; money stays in the commerce/treasury modules.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

STAGES = ("new", "contacted", "quoted", "awaiting_payment", "paid", "issued", "travelled", "lost")
STAGE_FA = {"new": "جدید", "contacted": "تماس گرفته شد", "quoted": "پیش‌فاکتور ارسال شد", "awaiting_payment": "منتظر پرداخت",
            "paid": "پرداخت شد", "issued": "صادر شد", "travelled": "سفر انجام شد", "lost": "لغو / منصرف"}
OPEN_STAGES = ("new", "contacted", "quoted", "awaiting_payment")
WON_STAGES = ("paid", "issued", "travelled")
CHANNELS = ("web_form", "whatsapp", "bale", "phone", "manual", "rebook", "referral", "abandoned", "trip_request",
            "campaign", "complaint", "instagram", "walk_in")
ACTIVITY_KINDS = ("note", "call", "message")
DEFAULT_TEMPLATES = {
    "welcome": "سلام {name} عزیز، درخواست شما برای {trip} رسید؛ من {agent} کارشناس شما هستم و به‌زودی بهترین گزینه‌ها را می‌فرستم.",
    "quote": "سلام {name} عزیز، پیش‌فاکتور {trip} به مبلغ {amount} آماده است و تا {expires} معتبر است. {agent}",
    "pay_remind": "سلام {name} عزیز، پیش‌فاکتور {trip} هنوز پرداخت نشده و ظرفیت تا {expires} نگه داشته شده است.",
    "confirm": "سلام {name} عزیز، رزرو {trip} قطعی شد. سفر خوبی داشته باشید.",
    "pre_trip": "سلام {name} عزیز، سفر {trip} نزدیک است؛ مدارک شناسایی را همراه داشته باشید. {agent}",
    "survey": "سلام {name} عزیز، امیدواریم سفر {trip} خوش گذشته باشد؛ لطفاً نظرتان را بگویید.",
}
PLACEHOLDERS = ("name", "trip", "agent", "amount", "expires")

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def normalize_mobile(raw: str) -> str:
    """Return an Iranian mobile as 09XXXXXXXXX; raise ValueError otherwise."""
    digits = re.sub(r"\D", "", (raw or "").translate(_PERSIAN_DIGITS))
    if digits.startswith("0098"):
        digits = "0" + digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    if not re.fullmatch(r"09\d{9}", digits):
        raise ValueError("شماره‌ی موبایل معتبر نیست")
    return digits


def can_move(current: str, target: str) -> bool:
    if current == target:
        return False
    if target == "lost":
        return current != "lost"
    if current == "lost":
        return target == "new"
    return STAGES.index(target) > STAGES.index(current)


def render_template(text: str, values: dict[str, Any]) -> str:
    out = text
    for key in PLACEHOLDERS:
        out = out.replace("{" + key + "}", str(values.get(key) or ""))
    return out


# ---------------------------------------------------------------- models
class SalesCase(OperationalMixin, Base):
    __tablename__ = "sales_desk_cases"
    code: Mapped[str] = mapped_column(String(24))
    customer_name: Mapped[str] = mapped_column(String(160))
    mobile: Mapped[str] = mapped_column(String(16), index=True)
    customer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    organization_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    channel: Mapped[str] = mapped_column(String(24), index=True)
    trip: Mapped[str] = mapped_column(String(240))
    travel_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    travellers: Mapped[int] = mapped_column(Integer, default=1)
    stage: Mapped[str] = mapped_column(String(24), default="new", index=True)
    agent_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    is_complaint: Mapped[bool] = mapped_column(Boolean, default=False)
    next_follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quote_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quote_currency: Mapped[str] = mapped_column(String(3), default="IRR")
    quote_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quote_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    won_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_sales_desk_case_code"),)


class SalesCaseActivity(OperationalMixin, Base):
    __tablename__ = "sales_desk_activities"
    case_id: Mapped[str] = mapped_column(ForeignKey("sales_desk_cases.id"), index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(24))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")


class SalesDeskAgent(OperationalMixin, Base):
    __tablename__ = "sales_desk_agents"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    present: Mapped[bool] = mapped_column(Boolean, default=False)
    last_assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    monthly_target: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_sales_desk_agent_user"),)


class SalesDeskSettings(OperationalMixin, Base):
    __tablename__ = "sales_desk_settings"
    auto_assign: Mapped[bool] = mapped_column(Boolean, default=True)
    sla_alert_minutes: Mapped[int] = mapped_column(Integer, default=10)
    sla_reassign_minutes: Mapped[int] = mapped_column(Integer, default=30)
    complaint_owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    templates_json: Mapped[str] = mapped_column(Text, default="{}")
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_sales_desk_settings_tenant"),)


# ---------------------------------------------------------------- schemas
class CaseIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=160)
    mobile: str
    channel: str = "manual"
    trip: str = Field(min_length=1, max_length=240)
    travel_date: Optional[str] = Field(default=None, max_length=10)
    travellers: int = Field(default=1, ge=1, le=500)
    organization_name: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=4000)
    is_complaint: bool = False
    agent_user_id: Optional[int] = None

    @field_validator("mobile")
    @classmethod
    def _mobile(cls, v: str) -> str:
        return normalize_mobile(v)

    @field_validator("channel")
    @classmethod
    def _channel(cls, v: str) -> str:
        if v not in CHANNELS:
            raise ValueError("کانال نامعتبر است")
        return v


class PublicCaseIn(BaseModel):
    """Public 'request a trip' form. Only what a visitor can type; channel, stage and agent are decided server side."""
    customer_name: str = Field(min_length=2, max_length=160)
    mobile: str
    trip: str = Field(min_length=2, max_length=240)
    travel_date: Optional[str] = Field(default=None, max_length=10)
    travellers: int = Field(default=1, ge=1, le=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    consent: bool
    website: Optional[str] = Field(default=None, max_length=200)  # honeypot: humans never fill it

    @field_validator("mobile")
    @classmethod
    def _mobile(cls, v: str) -> str:
        return normalize_mobile(v)

    @field_validator("travel_date")
    @classmethod
    def _date(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("تاریخ سفر نامعتبر است")
        return v or None


PUBLIC_DAILY_CAP = 3  # new web-form cases per mobile per 24h; later ones are added to the open case


class StageIn(BaseModel):
    stage: str
    reason: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("stage")
    @classmethod
    def _stage(cls, v: str) -> str:
        if v not in STAGES:
            raise ValueError("مرحله نامعتبر است")
        return v


class AssignIn(BaseModel):
    agent_user_id: int


class ActivityIn(BaseModel):
    kind: str = "note"
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in ACTIVITY_KINDS:
            raise ValueError("نوع فعالیت نامعتبر است")
        return v


class FollowUpIn(BaseModel):
    at: datetime


class QuoteIn(BaseModel):
    amount: int = Field(gt=0)
    currency: str = Field(default="IRR", min_length=3, max_length=3)
    valid_hours: int = Field(default=24, ge=1, le=24 * 30)
    note: Optional[str] = Field(default=None, max_length=2000)


class LinkReservationIn(BaseModel):
    reservation_id: str = Field(min_length=1, max_length=36)


class PresenceIn(BaseModel):
    present: bool


class TargetIn(BaseModel):
    user_id: int
    monthly_target: int = Field(ge=0)


class SettingsIn(BaseModel):
    auto_assign: bool = True
    sla_alert_minutes: int = Field(default=10, ge=1, le=24 * 60)
    sla_reassign_minutes: int = Field(default=30, ge=1, le=7 * 24 * 60)
    complaint_owner_user_id: Optional[int] = None
    templates: dict[str, str] = Field(default_factory=dict)

    @field_validator("templates")
    @classmethod
    def _templates(cls, v: dict[str, str]) -> dict[str, str]:
        unknown = set(v) - set(DEFAULT_TEMPLATES)
        if unknown:
            raise ValueError("قالب ناشناخته: " + "، ".join(sorted(unknown)))
        if any(len(t) > 1000 for t in v.values()):
            raise ValueError("متن قالب بیش از حد طولانی است")
        return v

    @field_validator("sla_reassign_minutes")
    @classmethod
    def _order(cls, v: int, info) -> int:
        alert = info.data.get("sla_alert_minutes")
        if alert is not None and v < alert:
            raise ValueError("زمان انتقال باید بعد از زمان هشدار باشد")
        return v


class RenderIn(BaseModel):
    template: str

    @field_validator("template")
    @classmethod
    def _t(cls, v: str) -> str:
        if v not in DEFAULT_TEMPLATES:
            raise ValueError("قالب ناشناخته است")
        return v


# ---------------------------------------------------------------- helpers
def _settings(db: Session, tenant_id: int) -> SalesDeskSettings:
    row = db.scalar(select(SalesDeskSettings).where(SalesDeskSettings.tenant_id == tenant_id))
    if row is None:
        row = SalesDeskSettings(tenant_id=tenant_id, templates_json="{}")
        db.add(row)
        db.flush()
    return row


def _templates(row: SalesDeskSettings) -> dict[str, str]:
    try:
        stored = json.loads(row.templates_json or "{}")
    except ValueError:
        stored = {}
    return {**DEFAULT_TEMPLATES, **{k: v for k, v in stored.items() if k in DEFAULT_TEMPLATES and v}}


def _agent_row(db: Session, tenant_id: int, user_id: int) -> SalesDeskAgent:
    row = db.scalar(select(SalesDeskAgent).where(SalesDeskAgent.tenant_id == tenant_id, SalesDeskAgent.user_id == user_id))
    if row is None:
        row = SalesDeskAgent(tenant_id=tenant_id, user_id=user_id, present=False)
        db.add(row)
        db.flush()
    return row


def _next_agent(db: Session, tenant_id: int, exclude: Optional[int] = None) -> Optional[SalesDeskAgent]:
    rows = db.scalars(select(SalesDeskAgent).where(SalesDeskAgent.tenant_id == tenant_id, SalesDeskAgent.present.is_(True))).all()
    rows = [r for r in rows if r.user_id != exclude]
    if not rows:
        return None
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    rows.sort(key=lambda r: (_aware(r.last_assigned_at) or epoch, r.user_id))
    return rows[0]


def _log(db: Session, case: SalesCase, actor_id: Optional[int], kind: str, body: Optional[str] = None, detail: Optional[dict] = None) -> None:
    db.add(SalesCaseActivity(tenant_id=case.tenant_id, case_id=case.id, actor_user_id=actor_id, kind=kind, body=body,
                             detail_json=json.dumps(detail or {}, ensure_ascii=False, sort_keys=True)))


def _new_code(db: Session, tenant_id: int) -> str:
    for _ in range(5):
        code = "DSK-" + uuid.uuid4().hex[:8].upper()
        if not db.scalar(select(SalesCase.id).where(SalesCase.tenant_id == tenant_id, SalesCase.code == code)):
            return code
    raise HTTPException(status_code=500, detail="ساخت کد پرونده ممکن نشد")


def _iso(value: Optional[datetime]) -> Optional[str]:
    value = _aware(value)
    return value.isoformat() if value else None


def _case_out(case: SalesCase, names: dict[int, str], now: datetime) -> dict:
    sla_due = _aware(case.sla_due_at)
    follow = _aware(case.next_follow_up_at)
    return {
        "id": case.id, "code": case.code, "customer_name": case.customer_name, "mobile": case.mobile,
        "organization_name": case.organization_name, "channel": case.channel, "trip": case.trip,
        "travel_date": case.travel_date, "travellers": case.travellers, "stage": case.stage, "stage_fa": STAGE_FA[case.stage],
        "agent_user_id": case.agent_user_id, "agent_name": names.get(case.agent_user_id) if case.agent_user_id else None,
        "is_complaint": case.is_complaint, "next_follow_up_at": _iso(follow), "follow_up_overdue": bool(follow and follow < now and case.stage in OPEN_STAGES),
        "sla_due_at": _iso(sla_due), "first_response_at": _iso(case.first_response_at),
        "sla_breached": bool(sla_due and case.first_response_at is None and sla_due < now and case.stage == "new"),
        "quote_amount": case.quote_amount, "quote_currency": case.quote_currency, "quote_expires_at": _iso(case.quote_expires_at),
        "quote_note": case.quote_note, "reservation_id": case.reservation_id, "lost_reason": case.lost_reason,
        "description": case.description, "created_at": _iso(case.created_at), "updated_at": _iso(case.updated_at),
    }


def _day_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _month_start(now: datetime) -> datetime:
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------- router
def sales_desk_router(get_db, current_user, role_has_permission, User, audit=None, public_tenant=None):
    """public_tenant(db) -> tenant id that receives the public web form (sets the RLS context); None or raising 503 = intake closed."""
    api = APIRouter(tags=["sales-desk"])

    def agent(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("support:manage", "reservation:manage", "tenant:manage")) or user.role in ("employee", "customer"):
            raise HTTPException(status_code=403, detail="دسترسی میز فروش لازم است")
        return user

    def manager(user=Depends(current_user)):
        if not (role_has_permission(user.role, "tenant:manage") or role_has_permission(user.role, "platform:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مدیریت لازم است")
        return user

    def _audit(db, user, action, ref, detail=None):
        if audit:
            try:
                audit(db, user, action, "sales_desk_case", {"ref": ref, **(detail or {})})
            except Exception:
                pass

    def _names(db, tenant_id: int, ids) -> dict[int, str]:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        return dict(db.execute(select(User.id, User.name).where(User.tenant_id == tenant_id, User.id.in_(ids))).all())

    def _tenant_user(db, tenant_id: int, user_id: int):
        u = db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
        if u is None:
            raise HTTPException(status_code=422, detail="کاربر در این مستأجر وجود ندارد")
        return u

    def _get_case(db, tenant_id: int, case_id: str) -> SalesCase:
        row = db.scalar(select(SalesCase).where(SalesCase.id == case_id, SalesCase.tenant_id == tenant_id))
        if row is None:
            raise HTTPException(status_code=404, detail="پرونده یافت نشد")
        return row

    def _out(db, case: SalesCase) -> dict:
        return _case_out(case, _names(db, case.tenant_id, [case.agent_user_id]), utcnow())

    # ---- cases
    @api.post("/sales-desk/cases", status_code=201)
    def create_case(data: CaseIn, user=Depends(agent), db: Session = Depends(get_db)):
        settings = _settings(db, user.tenant_id)
        now = utcnow()
        case = SalesCase(tenant_id=user.tenant_id, code=_new_code(db, user.tenant_id), customer_name=data.customer_name.strip(), mobile=data.mobile,
                         organization_name=(data.organization_name or None), channel=data.channel, trip=data.trip.strip(), travel_date=data.travel_date,
                         travellers=data.travellers, stage="new", is_complaint=data.is_complaint or data.channel == "complaint",
                         description=data.description, created_by_user_id=user.id, sla_due_at=now + timedelta(minutes=settings.sla_alert_minutes))
        customer = db.scalar(select(User.id).where(User.tenant_id == user.tenant_id, User.mobile_e164 == "+98" + data.mobile[1:])) if hasattr(User, "mobile_e164") else None
        case.customer_user_id = customer
        assigned_by = "manual"
        if data.agent_user_id:
            _tenant_user(db, user.tenant_id, data.agent_user_id)
            case.agent_user_id = data.agent_user_id
        elif case.is_complaint and settings.complaint_owner_user_id:
            case.agent_user_id = settings.complaint_owner_user_id
            assigned_by = "complaint_owner"
        elif settings.auto_assign:
            nxt = _next_agent(db, user.tenant_id)
            if nxt:
                case.agent_user_id = nxt.user_id
                nxt.last_assigned_at = now
                assigned_by = "round_robin"
        if case.agent_user_id is None and data.channel in ("phone", "walk_in", "manual"):
            case.agent_user_id = user.id
            assigned_by = "creator"
        db.add(case)
        db.flush()
        _log(db, case, user.id, "created", None, {"channel": case.channel, "assigned_by": assigned_by, "agent_user_id": case.agent_user_id})
        _audit(db, user, "sales_desk.case.created", case.id)
        db.commit()
        db.refresh(case)
        return _out(db, case)

    @api.get("/sales-desk/cases")
    def list_cases(stage: Optional[str] = None, mine: bool = False, overdue: bool = False, complaint: Optional[bool] = None,
                   q: Optional[str] = Query(default=None, max_length=80), limit: int = Query(default=100, ge=1, le=500),
                   user=Depends(agent), db: Session = Depends(get_db)):
        stmt = select(SalesCase).where(SalesCase.tenant_id == user.tenant_id)
        if stage:
            if stage == "open":
                stmt = stmt.where(SalesCase.stage.in_(OPEN_STAGES))
            elif stage in STAGES:
                stmt = stmt.where(SalesCase.stage == stage)
            else:
                raise HTTPException(status_code=422, detail="مرحله نامعتبر است")
        if mine:
            stmt = stmt.where(SalesCase.agent_user_id == user.id)
        if complaint is not None:
            stmt = stmt.where(SalesCase.is_complaint.is_(complaint))
        if q:
            like = f"%{q.strip()}%"
            digits = q.translate(_PERSIAN_DIGITS)
            stmt = stmt.where((SalesCase.customer_name.ilike(like)) | (SalesCase.trip.ilike(like)) | (SalesCase.code.ilike(like)) | (SalesCase.mobile.like(f"%{re.sub(r'[^0-9]', '', digits) or '#'}%")))
        rows = db.scalars(stmt.order_by(SalesCase.created_at.desc()).limit(limit)).all()
        now = utcnow()
        names = _names(db, user.tenant_id, [r.agent_user_id for r in rows])
        items = [_case_out(r, names, now) for r in rows]
        if overdue:
            items = [i for i in items if i["follow_up_overdue"] or i["sla_breached"]]
        return {"items": items}

    @api.get("/sales-desk/cases/{case_id}")
    def get_case(case_id: str, user=Depends(agent), db: Session = Depends(get_db)):
        case = _get_case(db, user.tenant_id, case_id)
        acts = db.scalars(select(SalesCaseActivity).where(SalesCaseActivity.tenant_id == user.tenant_id, SalesCaseActivity.case_id == case.id)
                          .order_by(SalesCaseActivity.created_at.desc())).all()
        names = _names(db, user.tenant_id, [case.agent_user_id, *[a.actor_user_id for a in acts]])
        out = _case_out(case, names, utcnow())
        out["activities"] = [{"id": a.id, "kind": a.kind, "body": a.body, "actor_name": names.get(a.actor_user_id), "at": _iso(a.created_at),
                              "detail": json.loads(a.detail_json or "{}")} for a in acts]
        return out

    def _first_response(case: SalesCase, actor_id: int, now: datetime) -> None:
        if case.first_response_at is None and (case.agent_user_id in (None, actor_id)):
            case.first_response_at = now

    @api.post("/sales-desk/cases/{case_id}/stage")
    def move_stage(case_id: str, data: StageIn, user=Depends(agent), db: Session = Depends(get_db)):
        case = _get_case(db, user.tenant_id, case_id)
        if not can_move(case.stage, data.stage):
            raise HTTPException(status_code=409, detail=f"انتقال از «{STAGE_FA[case.stage]}» به «{STAGE_FA[data.stage]}» مجاز نیست")
        if data.stage == "lost" and not (data.reason and data.reason.strip()):
            raise HTTPException(status_code=422, detail="دلیل لغو یا انصراف لازم است")
        if data.stage in ("awaiting_payment",) and not case.quote_amount and not case.reservation_id:
            raise HTTPException(status_code=409, detail="برای انتظار پرداخت، پیش‌فاکتور یا رزرو لازم است")
        if data.stage in WON_STAGES and not case.reservation_id:
            raise HTTPException(status_code=409, detail="برای این مرحله باید پرونده به یک رزرو وصل شود")
        now = utcnow()
        before = case.stage
        case.stage = data.stage
        if data.stage == "lost":
            case.lost_reason = data.reason.strip()
        if data.stage == "new":
            case.lost_reason = None
        if data.stage in WON_STAGES and case.won_at is None:
            case.won_at = now
        _first_response(case, user.id, now)
        _log(db, case, user.id, "stage", data.reason, {"from": before, "to": data.stage})
        _audit(db, user, "sales_desk.case.stage", case.id, {"from": before, "to": data.stage})
        db.commit()
        db.refresh(case)
        return _out(db, case)

    @api.post("/sales-desk/cases/{case_id}/assign")
    def assign(case_id: str, data: AssignIn, user=Depends(agent), db: Session = Depends(get_db)):
        case = _get_case(db, user.tenant_id, case_id)
        target = _tenant_user(db, user.tenant_id, data.agent_user_id)
        is_manager = role_has_permission(user.role, "tenant:manage")
        if not is_manager and case.agent_user_id not in (None, user.id):
            raise HTTPException(status_code=403, detail="فقط مسئول پرونده یا مدیر می‌تواند آن را منتقل کند")
        before = case.agent_user_id
        case.agent_user_id = target.id
        _log(db, case, user.id, "assign", None, {"from": before, "to": target.id})
        db.commit()
        db.refresh(case)
        return _out(db, case)

    @api.post("/sales-desk/cases/{case_id}/activities", status_code=201)
    def add_activity(case_id: str, data: ActivityIn, user=Depends(agent), db: Session = Depends(get_db)):
        case = _get_case(db, user.tenant_id, case_id)
        now = utcnow()
        if data.kind in ("call", "message"):
            _first_response(case, user.id, now)
            if case.stage == "new":
                case.stage = "contacted"
                _log(db, case, user.id, "stage", None, {"from": "new", "to": "contacted", "auto": True})
        _log(db, case, user.id, data.kind, data.body.strip())
        case.updated_at = now
        db.commit()
        return get_case(case_id, user, db)

    @api.post("/sales-desk/cases/{case_id}/follow-up")
    def follow_up(case_id: str, data: FollowUpIn, user=Depends(agent), db: Session = Depends(get_db)):
        case = _get_case(db, user.tenant_id, case_id)
        at = _aware(data.at)
        if at < utcnow() - timedelta(minutes=1):
            raise HTTPException(status_code=422, detail="زمان پیگیری نمی‌تواند در گذشته باشد")
        case.next_follow_up_at = at
        _log(db, case, user.id, "follow_up", None, {"at": at.isoformat()})
        db.commit()
        db.refresh(case)
        return _out(db, case)

    @api.post("/sales-desk/cases/{case_id}/quote")
    def quote(case_id: str, data: QuoteIn, user=Depends(agent), db: Session = Depends(get_db)):
        case = _get_case(db, user.tenant_id, case_id)
        if case.stage not in ("new", "contacted", "quoted", "awaiting_payment"):
            raise HTTPException(status_code=409, detail="برای این مرحله نمی‌توان پیش‌فاکتور صادر کرد")
        now = utcnow()
        case.quote_amount = data.amount
        case.quote_currency = data.currency.upper()
        case.quote_expires_at = now + timedelta(hours=data.valid_hours)
        case.quote_note = data.note
        before = case.stage
        if STAGES.index(case.stage) < STAGES.index("quoted"):
            case.stage = "quoted"
        _first_response(case, user.id, now)
        templates = _templates(_settings(db, user.tenant_id))
        message = render_template(templates["quote"], {"name": case.customer_name, "trip": case.trip, "agent": user.name,
                                                       "amount": f"{data.amount:,} {'ریال' if case.quote_currency == 'IRR' else case.quote_currency}",
                                                       "expires": case.quote_expires_at.strftime("%Y-%m-%d %H:%M UTC")})
        _log(db, case, user.id, "quote", message, {"amount": data.amount, "currency": case.quote_currency, "valid_hours": data.valid_hours, "from": before, "to": case.stage})
        _audit(db, user, "sales_desk.case.quote", case.id, {"amount": data.amount})
        db.commit()
        db.refresh(case)
        return {**_out(db, case), "message": message}

    @api.post("/sales-desk/cases/{case_id}/reservation")
    def link_reservation(case_id: str, data: LinkReservationIn, user=Depends(agent), db: Session = Depends(get_db)):
        case = _get_case(db, user.tenant_id, case_id)
        res = db.scalar(select(m.Reservation).where(m.Reservation.id == data.reservation_id, m.Reservation.tenant_id == user.tenant_id))
        if res is None:
            raise HTTPException(status_code=404, detail="رزرو در این مستأجر یافت نشد")
        other = db.scalar(select(SalesCase.code).where(SalesCase.tenant_id == user.tenant_id, SalesCase.reservation_id == res.id, SalesCase.id != case.id))
        if other:
            raise HTTPException(status_code=409, detail=f"این رزرو قبلاً به پرونده‌ی {other} وصل شده است")
        case.reservation_id = res.id
        if case.stage in ("new", "contacted", "quoted"):
            _log(db, case, user.id, "stage", None, {"from": case.stage, "to": "awaiting_payment", "auto": True})
            case.stage = "awaiting_payment"
        _log(db, case, user.id, "reservation", res.booking_reference, {"reservation_id": res.id, "status": res.status})
        db.commit()
        db.refresh(case)
        return {**_out(db, case), "reservation": {"id": res.id, "booking_reference": res.booking_reference, "status": res.status, "service_type": res.service_type}}

    @api.post("/sales-desk/cases/{case_id}/render")
    def render(case_id: str, data: RenderIn, user=Depends(agent), db: Session = Depends(get_db)):
        case = _get_case(db, user.tenant_id, case_id)
        names = _names(db, user.tenant_id, [case.agent_user_id])
        templates = _templates(_settings(db, user.tenant_id))
        expires = _aware(case.quote_expires_at)
        amount = f"{case.quote_amount:,} {'ریال' if case.quote_currency == 'IRR' else case.quote_currency}" if case.quote_amount else ""
        text = render_template(templates[data.template], {"name": case.customer_name, "trip": case.trip, "agent": names.get(case.agent_user_id) or user.name,
                                                          "amount": amount, "expires": expires.strftime("%Y-%m-%d %H:%M UTC") if expires else ""})
        return {"template": data.template, "text": text, "mobile": case.mobile}

    # ---- messenger / PBX intake (webhooks). Each channel is closed until its own secret is configured.
    def _inbound(db: Session, tenant_id: int, channel: str, mobile: str, name: Optional[str], text: str, ext_id: str, kind: str = "message") -> str:
        """Append to the open case of this mobile, or open a new case. Idempotent on the provider's message/call id."""
        marker = f'"ext_id": {json.dumps(ext_id)}'
        if db.scalar(select(SalesCaseActivity.id).where(SalesCaseActivity.tenant_id == tenant_id, SalesCaseActivity.detail_json.contains(marker))):
            return "duplicate"
        now = utcnow()
        case = db.scalar(select(SalesCase).where(SalesCase.tenant_id == tenant_id, SalesCase.mobile == mobile, SalesCase.stage.in_(OPEN_STAGES),
                                                 SalesCase.created_at >= now - timedelta(days=14)).order_by(SalesCase.created_at.desc()))
        detail = {"channel": channel, "ext_id": ext_id, "inbound": True}
        if case is not None:
            _log(db, case, None, kind, text[:4000] or None, detail)
            case.updated_at = now
            db.commit()
            return "appended"
        settings = _settings(db, tenant_id)
        label = {"whatsapp": "واتس‌اپ", "bale": "بله", "phone": "تماس تلفنی"}[channel]
        case = SalesCase(tenant_id=tenant_id, code=_new_code(db, tenant_id), customer_name=(name or "").strip()[:160] or f"مشتری {label}", mobile=mobile, channel=channel,
                         trip=(text.strip()[:240] or f"درخواست از {label}"), travellers=1, stage="new", is_complaint=False,
                         sla_due_at=now + timedelta(minutes=settings.sla_alert_minutes))
        if hasattr(User, "mobile_e164"):
            case.customer_user_id = db.scalar(select(User.id).where(User.tenant_id == tenant_id, User.mobile_e164 == "+98" + mobile[1:]))
        if settings.auto_assign:
            nxt = _next_agent(db, tenant_id)
            if nxt:
                case.agent_user_id, nxt.last_assigned_at = nxt.user_id, now
        db.add(case)
        db.flush()
        _log(db, case, None, "created", None, {**detail, "agent_user_id": case.agent_user_id})
        if text.strip():
            _log(db, case, None, kind, text[:4000], {**detail, "ext_id": ext_id + "#body"})
        db.commit()
        return "created"

    def _tenant_or_503(db: Session) -> int:
        if public_tenant is None:
            raise HTTPException(status_code=503, detail="ورودی پیام‌رسان فعال نیست")
        return public_tenant(db)

    def _secret(name: str) -> str:
        value = (os.getenv(name) or "").strip()
        if not value:
            raise HTTPException(status_code=503, detail="این کانال هنوز پیکربندی نشده است")
        return value

    def _mobile_or_none(raw: Any) -> Optional[str]:
        try:
            return normalize_mobile(str(raw or ""))
        except ValueError:
            return None

    @api.get("/public/sales-desk/inbound/whatsapp")
    def whatsapp_verify(request: Request):
        """WhatsApp Cloud API webhook verification handshake."""
        q = request.query_params
        token = _secret("SALES_DESK_WHATSAPP_VERIFY_TOKEN")
        if q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", ""), token):
            return PlainTextResponse(q.get("hub.challenge", ""))
        raise HTTPException(status_code=403, detail="forbidden")

    @api.post("/public/sales-desk/inbound/whatsapp")
    async def whatsapp_inbound(request: Request, db: Session = Depends(get_db)):
        secret = _secret("SALES_DESK_WHATSAPP_APP_SECRET")
        body = await request.body()
        sent = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sent, expected):
            raise HTTPException(status_code=401, detail="invalid signature")
        tenant_id = _tenant_or_503(db)
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid json")
        results = []
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value") or {}
                names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", []) or []}
                for msg in value.get("messages", []) or []:
                    mobile = _mobile_or_none(msg.get("from"))
                    if not mobile or not msg.get("id"):
                        results.append("skipped")
                        continue
                    text = (msg.get("text") or {}).get("body") or f"[{msg.get('type', 'message')}]"
                    results.append(_inbound(db, tenant_id, "whatsapp", mobile, names.get(msg.get("from")), text, "wa:" + str(msg["id"])))
        return {"received": len(results), "results": results}

    @api.post("/public/sales-desk/inbound/bale/{token}")
    async def bale_inbound(token: str, request: Request, db: Session = Depends(get_db)):
        """Bale bot webhook (the secret is the path token). A case needs a phone number, so only messages
        where the customer shared their contact open or update a case; others are acknowledged and skipped."""
        if not hmac.compare_digest(token, _secret("SALES_DESK_BALE_WEBHOOK_TOKEN")):
            raise HTTPException(status_code=403, detail="forbidden")
        tenant_id = _tenant_or_503(db)
        try:
            update = json.loads(await request.body() or b"{}")
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid json")
        msg = update.get("message") or {}
        contact = msg.get("contact") or {}
        mobile = _mobile_or_none(contact.get("phone_number"))
        if not mobile or update.get("update_id") is None:
            return {"result": "skipped", "reason": "no shared phone number"}
        sender = msg.get("from") or {}
        name = " ".join(x for x in (contact.get("first_name") or sender.get("first_name"), contact.get("last_name") or sender.get("last_name")) if x)
        return {"result": _inbound(db, tenant_id, "bale", mobile, name, msg.get("text") or msg.get("caption") or "", f"bale:{update['update_id']}")}

    @api.post("/public/sales-desk/inbound/pbx")
    async def pbx_inbound(request: Request, db: Session = Depends(get_db)):
        """Generic PBX (سانترال) call event, HMAC-SHA256 signed: {"call_id","caller","event": incoming|missed|answered, "extension"}."""
        secret = _secret("SALES_DESK_PBX_SECRET")
        body = await request.body()
        sent = request.headers.get("x-karenseir-signature", "")
        if not hmac.compare_digest(sent, hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()):
            raise HTTPException(status_code=401, detail="invalid signature")
        tenant_id = _tenant_or_503(db)
        try:
            ev = json.loads(body or b"{}")
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid json")
        mobile = _mobile_or_none(ev.get("caller"))
        if not mobile or not ev.get("call_id") or ev.get("event") not in ("incoming", "missed", "answered"):
            return {"result": "skipped"}
        text = {"incoming": "تماس ورودی", "missed": "تماس بی‌پاسخ — نیاز به تماس دوباره", "answered": "تماس پاسخ داده شد"}[ev["event"]]
        if ev.get("extension"):
            text += f" (داخلی {str(ev['extension'])[:12]})"
        return {"result": _inbound(db, tenant_id, "phone", mobile, None, text, f"pbx:{ev['call_id']}:{ev['event']}", kind="call")}

    # ---- public intake (website form)
    @api.post("/public/sales-desk/requests", status_code=202)
    def public_request(data: PublicCaseIn, db: Session = Depends(get_db)):
        if data.website:  # bot: answer like a success, store nothing
            return {"received": True}
        if not data.consent:
            raise HTTPException(status_code=422, detail="برای تماس کارشناس، رضایت لازم است")
        if public_tenant is None:
            raise HTTPException(status_code=503, detail="ثبت درخواست آنلاین هنوز فعال نشده است")
        tenant_id = public_tenant(db)
        now = utcnow()
        recent = db.scalars(select(SalesCase).where(SalesCase.tenant_id == tenant_id, SalesCase.mobile == data.mobile, SalesCase.channel == "web_form",
                                                    SalesCase.created_at >= now - timedelta(hours=24)).order_by(SalesCase.created_at.desc())).all()
        open_case = next((c for c in recent if c.stage in OPEN_STAGES), None)
        if open_case is not None and (len(recent) >= PUBLIC_DAILY_CAP or open_case.trip.strip() == data.trip.strip()):
            _log(db, open_case, None, "message", f"درخواست دوباره از سایت: {data.trip}" + (f" — {data.description}" if data.description else ""),
                 {"channel": "web_form", "travel_date": data.travel_date, "travellers": data.travellers})
            open_case.updated_at = now
            db.commit()
            return {"received": True}
        if len(recent) >= PUBLIC_DAILY_CAP:
            return {"received": True}
        settings = _settings(db, tenant_id)
        case = SalesCase(tenant_id=tenant_id, code=_new_code(db, tenant_id), customer_name=data.customer_name.strip(), mobile=data.mobile, channel="web_form",
                         trip=data.trip.strip(), travel_date=data.travel_date, travellers=data.travellers, stage="new", is_complaint=False,
                         description=data.description, sla_due_at=now + timedelta(minutes=settings.sla_alert_minutes))
        case.customer_user_id = db.scalar(select(User.id).where(User.tenant_id == tenant_id, User.mobile_e164 == "+98" + data.mobile[1:])) if hasattr(User, "mobile_e164") else None
        assigned_by = None
        if settings.auto_assign:
            nxt = _next_agent(db, tenant_id)
            if nxt:
                case.agent_user_id, nxt.last_assigned_at, assigned_by = nxt.user_id, now, "round_robin"
        db.add(case)
        db.flush()
        _log(db, case, None, "created", None, {"channel": "web_form", "assigned_by": assigned_by, "agent_user_id": case.agent_user_id, "consent": True})
        db.commit()
        # The visitor gets no case code or agent name: nothing about the desk is disclosed to an anonymous caller.
        return {"received": True}

    # ---- presence, team and KPIs
    @api.get("/sales-desk/presence")
    def my_presence(user=Depends(agent), db: Session = Depends(get_db)):
        row = _agent_row(db, user.tenant_id, user.id)
        db.commit()
        return {"user_id": user.id, "present": row.present}

    @api.put("/sales-desk/presence")
    def set_presence(data: PresenceIn, user=Depends(agent), db: Session = Depends(get_db)):
        row = _agent_row(db, user.tenant_id, user.id)
        row.present = data.present
        db.commit()
        return {"user_id": user.id, "present": row.present}

    @api.get("/sales-desk/summary")
    def summary(user=Depends(agent), db: Session = Depends(get_db)):
        now = utcnow()
        start, end = _day_bounds(now)
        base = select(func.count()).select_from(SalesCase).where(SalesCase.tenant_id == user.tenant_id)
        today = db.scalar(base.where(SalesCase.created_at >= start, SalesCase.created_at < end)) or 0
        unanswered = db.scalar(base.where(SalesCase.stage == "new", SalesCase.first_response_at.is_(None))) or 0
        breached = db.scalar(base.where(SalesCase.stage == "new", SalesCase.first_response_at.is_(None), SalesCase.sla_due_at < now)) or 0
        open_quotes = db.scalar(base.where(SalesCase.stage.in_(("quoted", "awaiting_payment")))) or 0
        overdue = db.scalar(base.where(SalesCase.stage.in_(OPEN_STAGES), SalesCase.next_follow_up_at.is_not(None), SalesCase.next_follow_up_at < now)) or 0
        won_today = db.execute(select(func.count(), func.coalesce(func.sum(SalesCase.quote_amount), 0)).where(
            SalesCase.tenant_id == user.tenant_id, SalesCase.won_at >= start, SalesCase.won_at < end)).one()
        present = db.scalar(select(func.count()).select_from(SalesDeskAgent).where(SalesDeskAgent.tenant_id == user.tenant_id, SalesDeskAgent.present.is_(True))) or 0
        settings = _settings(db, user.tenant_id)
        db.commit()
        return {"requests_today": today, "unanswered": unanswered, "sla_breached": breached, "open_quotes": open_quotes,
                "overdue_follow_ups": overdue, "won_today": won_today[0], "won_amount_today": int(won_today[1] or 0),
                "present_agents": present, "auto_assign": settings.auto_assign and present > 0}

    @api.get("/sales-desk/team")
    def team(user=Depends(agent), db: Session = Depends(get_db)):
        now = utcnow()
        start, end = _day_bounds(now)
        month = _month_start(now)
        agents = db.scalars(select(SalesDeskAgent).where(SalesDeskAgent.tenant_id == user.tenant_id)).all()
        ids = {a.user_id for a in agents} | set(db.scalars(select(SalesCase.agent_user_id).where(SalesCase.tenant_id == user.tenant_id, SalesCase.agent_user_id.is_not(None)).distinct()).all())
        names = _names(db, user.tenant_id, ids)
        by_id = {a.user_id: a for a in agents}
        rows = []
        for uid in sorted(ids):
            cases = db.scalars(select(SalesCase).where(SalesCase.tenant_id == user.tenant_id, SalesCase.agent_user_id == uid)).all()
            today = [c for c in cases if start <= _aware(c.created_at) < end]
            responses = sorted((_aware(c.first_response_at) - _aware(c.created_at)).total_seconds() / 60 for c in today if c.first_response_at)
            median = responses[len(responses) // 2] if responses else None
            won_month = [c for c in cases if c.won_at and _aware(c.won_at) >= month]
            a = by_id.get(uid)
            rows.append({"user_id": uid, "name": names.get(uid), "present": bool(a and a.present), "requests_today": len(today),
                         "median_first_response_minutes": round(median, 1) if median is not None else None,
                         "open_cases": sum(1 for c in cases if c.stage in OPEN_STAGES), "won_month": len(won_month),
                         "sales_month": sum(c.quote_amount or 0 for c in won_month), "monthly_target": a.monthly_target if a else 0})
        return {"items": rows}

    @api.put("/sales-desk/targets")
    def set_target(data: TargetIn, user=Depends(manager), db: Session = Depends(get_db)):
        _tenant_user(db, user.tenant_id, data.user_id)
        row = _agent_row(db, user.tenant_id, data.user_id)
        row.monthly_target = data.monthly_target
        db.commit()
        return {"user_id": data.user_id, "monthly_target": row.monthly_target}

    # ---- settings and SLA sweep
    @api.get("/sales-desk/settings")
    def get_settings(user=Depends(agent), db: Session = Depends(get_db)):
        row = _settings(db, user.tenant_id)
        db.commit()
        return {"auto_assign": row.auto_assign, "sla_alert_minutes": row.sla_alert_minutes, "sla_reassign_minutes": row.sla_reassign_minutes,
                "complaint_owner_user_id": row.complaint_owner_user_id, "templates": _templates(row), "placeholders": list(PLACEHOLDERS),
                "channels": list(CHANNELS), "stages": [{"key": s, "label": STAGE_FA[s]} for s in STAGES]}

    @api.put("/sales-desk/settings")
    def put_settings(data: SettingsIn, user=Depends(manager), db: Session = Depends(get_db)):
        if data.complaint_owner_user_id:
            _tenant_user(db, user.tenant_id, data.complaint_owner_user_id)
        row = _settings(db, user.tenant_id)
        row.auto_assign = data.auto_assign
        row.sla_alert_minutes = data.sla_alert_minutes
        row.sla_reassign_minutes = data.sla_reassign_minutes
        row.complaint_owner_user_id = data.complaint_owner_user_id
        row.templates_json = json.dumps({k: v for k, v in data.templates.items() if v and v != DEFAULT_TEMPLATES[k]}, ensure_ascii=False, sort_keys=True)
        _audit(db, user, "sales_desk.settings.saved", row.id)
        db.commit()
        return get_settings(user, db)

    @api.post("/sales-desk/sla/sweep")
    def sla_sweep(user=Depends(manager), db: Session = Depends(get_db)):
        """Reassign unanswered new cases older than the reassign window to the next present agent."""
        settings = _settings(db, user.tenant_id)
        now = utcnow()
        limit = now - timedelta(minutes=settings.sla_reassign_minutes)
        stale = db.scalars(select(SalesCase).where(SalesCase.tenant_id == user.tenant_id, SalesCase.stage == "new",
                                                   SalesCase.first_response_at.is_(None), SalesCase.created_at < limit)).all()
        moved = 0
        for case in stale:
            nxt = _next_agent(db, user.tenant_id, exclude=case.agent_user_id)
            if nxt is None:
                continue
            before = case.agent_user_id
            case.agent_user_id = nxt.user_id
            case.sla_due_at = now + timedelta(minutes=settings.sla_alert_minutes)
            nxt.last_assigned_at = now
            _log(db, case, user.id, "assign", "انتقال خودکار پس از گذشت مهلت پاسخ", {"from": before, "to": nxt.user_id, "auto": True})
            moved += 1
        db.commit()
        return {"checked": len(stale), "reassigned": moved}

    return api
