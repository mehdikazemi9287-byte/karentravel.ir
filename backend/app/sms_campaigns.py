"""SMS campaigns (کمپین پیامکی) for the sales desk and the loyalty circle.

Audience is built only from the tenant's own data:
- sales-desk customers, filtered by stage and/or channel (their mobile on the case)
- loyalty members of a level (users with a mobile on file)
Opted-out numbers are always removed; the message carries the opt-out line ("لغو۱۱").

Sending goes through the platform SMS adapter (ADAPTERS["sms"]). While no SMS provider is connected the adapter
answers `external_provider_not_configured`; recipients are then marked `blocked_external` and the campaign
`waiting_for_provider` — nothing is reported as delivered that was not.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .operations import OperationalMixin
from .sales_desk import CHANNELS, STAGES, SalesCase, normalize_mobile

OPT_OUT_LINE = "لغو۱۱"
MAX_LEN = 335  # 5 Persian SMS parts (67 chars each)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SmsCampaign(OperationalMixin, Base):
    __tablename__ = "sms_campaigns"
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    audience_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)  # draft | sending | sent | failed | waiting_for_provider | cancelled
    recipients: Mapped[int] = mapped_column(Integer, default=0)
    delivered: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class SmsCampaignRecipient(OperationalMixin, Base):
    __tablename__ = "sms_campaign_recipients"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("sms_campaigns.id"), index=True)
    mobile: Mapped[str] = mapped_column(String(16))
    name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")  # queued | delivered | blocked_external | failed
    error: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "campaign_id", "mobile", name="uq_sms_campaign_mobile"),)


class SmsOptOut(OperationalMixin, Base):
    __tablename__ = "sms_opt_outs"
    mobile: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(24), default="manual")
    __table_args__ = (UniqueConstraint("tenant_id", "mobile", name="uq_sms_opt_out_mobile"),)


class AudienceIn(BaseModel):
    source: str = Field(pattern="^(sales_desk|loyalty)$")
    stages: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    level_key: Optional[str] = Field(default=None, max_length=24)

    @field_validator("stages")
    @classmethod
    def _st(cls, v: list[str]) -> list[str]:
        if set(v) - set(STAGES):
            raise ValueError("مرحله نامعتبر است")
        return v

    @field_validator("channels")
    @classmethod
    def _ch(cls, v: list[str]) -> list[str]:
        if set(v) - set(CHANNELS):
            raise ValueError("کانال نامعتبر است")
        return v


class CampaignIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    body: str = Field(min_length=5, max_length=MAX_LEN - len(OPT_OUT_LINE) - 1)
    audience: AudienceIn


class OptOutIn(BaseModel):
    mobile: str

    @field_validator("mobile")
    @classmethod
    def _m(cls, v: str) -> str:
        return normalize_mobile(v)


def full_text(body: str) -> str:
    return f"{body.strip()}\n{OPT_OUT_LINE}"


def sms_parts(text: str) -> int:
    return max(1, -(-len(text) // 67))


def sms_campaigns_router(get_db, current_user, role_has_permission, User, audit=None, sms_adapter=None, provider_context=None):
    api = APIRouter(tags=["sms-campaigns"])

    def manager(user=Depends(current_user)):
        if not (role_has_permission(user.role, "tenant:manage") or role_has_permission(user.role, "platform:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مدیریت لازم است")
        return user

    def _audience(db: Session, tenant_id: int, a: AudienceIn) -> list[tuple[str, Optional[str]]]:
        out: dict[str, Optional[str]] = {}
        if a.source == "sales_desk":
            s = select(SalesCase.mobile, SalesCase.customer_name).where(SalesCase.tenant_id == tenant_id)
            if a.stages:
                s = s.where(SalesCase.stage.in_(a.stages))
            if a.channels:
                s = s.where(SalesCase.channel.in_(a.channels))
            for mobile, name in db.execute(s.order_by(SalesCase.created_at.desc())).all():
                out.setdefault(mobile, name)
        else:
            from .loyalty import LoyaltyAccount, _settings, level_for, levels_of
            levels = levels_of(_settings(db, tenant_id, create=False))
            rows = db.execute(select(LoyaltyAccount.points_earned, User.mobile_e164, User.name).join(User, User.id == LoyaltyAccount.user_id)
                              .where(LoyaltyAccount.tenant_id == tenant_id, User.mobile_e164.is_not(None))).all()
            for earned, e164, name in rows:
                if a.level_key and level_for(levels, earned)[0]["key"] != a.level_key:
                    continue
                try:
                    out.setdefault(normalize_mobile(e164), name)
                except ValueError:
                    continue
        blocked = set(db.scalars(select(SmsOptOut.mobile).where(SmsOptOut.tenant_id == tenant_id)).all())
        return [(m, n) for m, n in out.items() if m not in blocked]

    def _out(c: SmsCampaign) -> dict:
        text = full_text(c.body)
        return {"id": c.id, "title": c.title, "body": c.body, "text": text, "parts": sms_parts(text), "audience": json.loads(c.audience_json or "{}"),
                "status": c.status, "recipients": c.recipients, "delivered": c.delivered, "blocked": c.blocked,
                "created_at": c.created_at.isoformat() if c.created_at else None}

    def _get(db, tenant_id, cid) -> SmsCampaign:
        c = db.scalar(select(SmsCampaign).where(SmsCampaign.id == cid, SmsCampaign.tenant_id == tenant_id))
        if c is None:
            raise HTTPException(status_code=404, detail="کمپین یافت نشد")
        return c

    def _health() -> tuple[str, Optional[str]]:
        if sms_adapter is None:
            return "not_connected", "SMS adapter is not wired"
        try:
            h = sms_adapter.health()
            return getattr(h, "status", "not_connected"), getattr(h, "detail", None)
        except Exception as exc:
            return "unavailable", type(exc).__name__

    def _connected() -> bool:
        return _health()[0] in ("available", "healthy", "ok", "connected")

    @api.get("/sms-campaigns/provider")
    def provider(user=Depends(manager)):
        status, detail = _health()
        return {"connected": status in ("available", "healthy", "ok", "connected"), "status": status, "detail": detail}

    @api.post("/sms-campaigns/preview")
    def preview(data: AudienceIn, user=Depends(manager), db: Session = Depends(get_db)):
        people = _audience(db, user.tenant_id, data)
        return {"count": len(people), "sample": [{"mobile": m[:4] + "***" + m[-4:], "name": n} for m, n in people[:5]]}

    @api.get("/sms-campaigns")
    def list_campaigns(user=Depends(manager), db: Session = Depends(get_db)):
        rows = db.scalars(select(SmsCampaign).where(SmsCampaign.tenant_id == user.tenant_id).order_by(SmsCampaign.created_at.desc()).limit(100)).all()
        return {"items": [_out(c) for c in rows]}

    @api.post("/sms-campaigns", status_code=201)
    def create(data: CampaignIn, user=Depends(manager), db: Session = Depends(get_db)):
        c = SmsCampaign(tenant_id=user.tenant_id, title=data.title.strip(), body=data.body.strip(), audience_json=data.audience.model_dump_json(), status="draft", created_by=user.id)
        db.add(c)
        db.commit()
        return _out(c)

    @api.post("/sms-campaigns/{cid}/send")
    def send(cid: str, user=Depends(manager), db: Session = Depends(get_db)):
        c = _get(db, user.tenant_id, cid)
        if c.status not in ("draft", "waiting_for_provider", "failed"):
            raise HTTPException(status_code=409, detail="این کمپین قبلاً ارسال شده است")
        if c.status == "draft":
            people = _audience(db, user.tenant_id, AudienceIn.model_validate_json(c.audience_json))
            if not people:
                raise HTTPException(status_code=409, detail="مخاطبی برای این کمپین نیست")
            for mobile, name in people:
                db.add(SmsCampaignRecipient(tenant_id=user.tenant_id, campaign_id=c.id, mobile=mobile, name=name, status="queued"))
            c.recipients = len(people)
            db.flush()
        c.status = "sending"
        text = full_text(c.body)
        pending = db.scalars(select(SmsCampaignRecipient).where(SmsCampaignRecipient.tenant_id == user.tenant_id, SmsCampaignRecipient.campaign_id == c.id,
                                                                SmsCampaignRecipient.status.in_(("queued", "blocked_external", "failed")))).all()
        connected = _connected()
        for r in pending:
            result = {"ok": False, "reason": "external_provider_not_configured"}
            if connected and provider_context is not None:
                try:
                    result = sms_adapter.execute("send_campaign_sms", {"to": r.mobile, "text": text, "campaign_id": c.id},
                                                 provider_context(user.tenant_id, f"sms-campaign:{c.id}:{r.mobile}"))
                except Exception as exc:  # adapter misconfiguration counts as not sent
                    result = {"ok": False, "reason": type(exc).__name__}
            if result.get("ok"):
                r.status, r.error = "delivered", None
            elif result.get("reason") == "external_provider_not_configured":
                r.status, r.error = "blocked_external", "external_provider_not_configured"
            else:
                r.status, r.error = "failed", str(result.get("reason") or "failed")[:120]
        counts = dict(db.execute(select(SmsCampaignRecipient.status, func.count()).where(SmsCampaignRecipient.tenant_id == user.tenant_id, SmsCampaignRecipient.campaign_id == c.id)
                                 .group_by(SmsCampaignRecipient.status)).all())
        c.delivered, c.blocked = counts.get("delivered", 0), counts.get("blocked_external", 0)
        failed = counts.get("failed", 0)
        c.status = "waiting_for_provider" if c.blocked else ("failed" if failed and not c.delivered else "sent")
        if audit:
            audit(db, user, "sms_campaign.send", "sms_campaign", {"campaign_id": c.id, "recipients": c.recipients, "delivered": c.delivered, "blocked": c.blocked})
        db.commit()
        return {**_out(c), "failed": counts.get("failed", 0)}

    @api.post("/sms-campaigns/{cid}/cancel")
    def cancel(cid: str, user=Depends(manager), db: Session = Depends(get_db)):
        c = _get(db, user.tenant_id, cid)
        if c.status == "sent":
            raise HTTPException(status_code=409, detail="کمپین ارسال‌شده لغو نمی‌شود")
        c.status = "cancelled"
        db.commit()
        return _out(c)

    @api.get("/sms-campaigns/opt-outs")
    def opt_outs(limit: int = Query(default=200, ge=1, le=2000), user=Depends(manager), db: Session = Depends(get_db)):
        return {"items": [{"mobile": o.mobile, "source": o.source} for o in db.scalars(select(SmsOptOut).where(SmsOptOut.tenant_id == user.tenant_id).limit(limit)).all()]}

    @api.post("/sms-campaigns/opt-outs", status_code=201)
    def add_opt_out(data: OptOutIn, user=Depends(manager), db: Session = Depends(get_db)):
        if not db.scalar(select(SmsOptOut.id).where(SmsOptOut.tenant_id == user.tenant_id, SmsOptOut.mobile == data.mobile)):
            db.add(SmsOptOut(tenant_id=user.tenant_id, mobile=data.mobile, source="manual"))
            db.commit()
        return {"mobile": data.mobile, "opted_out": True}

    return api
