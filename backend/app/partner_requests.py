"""Requests to the group's partner sites, sent from KarenSeir on the customer's behalf.

* Padvira (padviradonia.com): its public request API — `POST /api/requests` (Idempotency-Key; fullName, contact,
  message, category family|org) and `POST /api/requests/track` (id + contact → status and public note).
* Gift Asan (giftasan.com, WooCommerce): a souvenir request becomes an `on-hold` WooCommerce order with no line items
  and the request in the customer note, through the WooCommerce REST API (`GIFTASAN_WC_KEY` / `GIFTASAN_WC_SECRET`,
  read/write key made in WooCommerce › Settings › Advanced › REST API). Without a key the endpoint answers 503 and the
  site keeps the WhatsApp link Gift Asan itself publishes.

Each request is kept in `partner_requests` so the customer sees it under حساب من. Prices are never sent or invented
here; the partner answers with price and time after review.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .operations import OperationalMixin

PADVIRA_STATUS_FA = {"new": "ثبت شد", "review": "در حال بررسی", "done": "رسیدگی شد", "rejected": "رد شد"}
GIFTASAN_STATUS_FA = {"on-hold": "در انتظار بررسی", "pending": "در انتظار پرداخت", "processing": "در حال آماده‌سازی", "completed": "ارسال شد", "cancelled": "لغو شد"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PartnerRequest(OperationalMixin, Base):
    __tablename__ = "partner_requests"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    partner: Mapped[str] = mapped_column(String(16), index=True)          # padvira | giftasan
    service: Mapped[str] = mapped_column(String(160))
    reference: Mapped[str] = mapped_column(String(100))                   # partner's id
    contact: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="new")
    public_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


def padvira_base() -> str:
    return (os.environ.get("PADVIRA_API_URL") or "https://padviradonia.com").rstrip("/")


def giftasan_base() -> str:
    return (os.environ.get("GIFTASAN_URL") or "https://giftasan.com").rstrip("/")


def giftasan_auth() -> Optional[tuple[str, str]]:
    k, s = os.environ.get("GIFTASAN_WC_KEY"), os.environ.get("GIFTASAN_WC_SECRET")
    return (k, s) if k and s else None


def _client() -> httpx.Client:
    return httpx.Client(timeout=20, headers={"User-Agent": "KarenSeir-partner/1.0", "Accept": "application/json"})


class Contact(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    contact: str = Field(min_length=7, max_length=200)

    @field_validator("contact")
    @classmethod
    def _digits(cls, v: str) -> str:
        return v.strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


class PadviraIn(Contact):
    service: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=5, max_length=3000)
    category: str = Field(default="family", pattern="^(family|org)$")


class SouvenirIn(Contact):
    city: str = Field(min_length=2, max_length=60)
    items: str = Field(min_length=2, max_length=500)
    deliver_to: str = Field(min_length=2, max_length=200)
    note: Optional[str] = Field(default=None, max_length=500)


def padvira_create(data: PadviraIn, key: str, post=None) -> str:
    body = {"fullName": data.full_name, "contact": data.contact, "category": data.category,
            "message": f"[از کارن‌سیر] {data.service}\n{data.message}"}
    if post is None:
        with _client() as c:
            r = c.post(f"{padvira_base()}/api/requests", json=body, headers={"Idempotency-Key": key})
            status, payload = r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})
    else:
        status, payload = post(body, key)
    if status in (200, 201) and isinstance(payload.get("id"), str):
        return payload["id"]
    if status == 422:
        errs = payload.get("fieldErrors") or {}
        raise HTTPException(status_code=422, detail="پادویرا درخواست را نپذیرفت: " + "، ".join(str(v) for v in errs.values()) if errs else "اطلاعات درخواست معتبر نیست")
    if status == 429:
        raise HTTPException(status_code=429, detail="پادویرا الان درخواست زیادی دارد؛ چند دقیقه‌ی دیگر دوباره بفرستید")
    raise HTTPException(status_code=502, detail="ارتباط با پادویرا برقرار نشد؛ دوباره تلاش کنید")


def padvira_track(ref: str, contact: str, post=None) -> Optional[dict]:
    try:
        if post is None:
            with _client() as c:
                r = c.post(f"{padvira_base()}/api/requests/track", json={"id": ref, "contact": contact})
                return r.json() if r.status_code == 200 else None
        return post(ref, contact)
    except (httpx.HTTPError, ValueError):
        return None


def giftasan_create(data: SouvenirIn, ref: str, post=None) -> str:
    auth = giftasan_auth()
    if auth is None and post is None:
        raise HTTPException(status_code=503, detail="ثبت مستقیم در گیفت آسان هنوز فعال نشده است؛ از واتساپ گیفت آسان درخواست بدهید")
    note = f"درخواست گیفت سوغات از کارن‌سیر\nسوغات {data.city}: {data.items}\nارسال به: {data.deliver_to}" + (f"\nتوضیح: {data.note}" if data.note else "")
    first, _, last = data.full_name.partition(" ")
    body = {"status": "on-hold", "set_paid": False, "customer_note": note, "created_via": "karenseir",
            "billing": {"first_name": first, "last_name": last, "phone": data.contact if "@" not in data.contact else "", "email": data.contact if "@" in data.contact else "", "city": data.deliver_to[:100]},
            "meta_data": [{"key": "_karenseir_ref", "value": ref}, {"key": "_souvenir_city", "value": data.city}]}
    if post is None:
        with _client() as c:
            r = c.post(f"{giftasan_base()}/wp-json/wc/v3/orders", json=body, auth=auth)
            status, payload = r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})
    else:
        status, payload = post(body)
    if status == 201 and payload.get("id"):
        return str(payload["id"])
    if status in (401, 403):
        raise HTTPException(status_code=503, detail="کلید اتصال گیفت آسان معتبر نیست یا دسترسی نوشتن ندارد")
    raise HTTPException(status_code=502, detail="ارتباط با گیفت آسان برقرار نشد؛ دوباره تلاش کنید")


def giftasan_status(ref: str, get=None) -> Optional[dict]:
    auth = giftasan_auth()
    try:
        if get is not None:
            return get(ref)
        if auth is None:
            return None
        with _client() as c:
            r = c.get(f"{giftasan_base()}/wp-json/wc/v3/orders/{ref}", auth=auth)
            return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def partner_requests_router(get_db, current_user, audit=None) -> APIRouter:
    api = APIRouter(tags=["partner-requests"])

    def _out(r: PartnerRequest) -> dict:
        fa = (PADVIRA_STATUS_FA if r.partner == "padvira" else GIFTASAN_STATUS_FA).get(r.status, r.status)
        return {"id": r.id, "partner": r.partner, "partner_fa": "پادویرا" if r.partner == "padvira" else "گیفت آسان", "service": r.service, "reference": r.reference,
                "summary": r.summary, "status": r.status, "status_fa": fa, "public_note": r.public_note, "created_at": r.created_at.isoformat(),
                "track_url": f"{padvira_base()}/request" if r.partner == "padvira" else f"{giftasan_base()}/my-account/"}

    @api.get("/partners/status")
    def status(user=Depends(current_user)):
        return {"padvira": True, "giftasan": giftasan_auth() is not None}

    @api.post("/partners/padvira/requests", status_code=201)
    def padvira(data: PadviraIn, user=Depends(current_user), db: Session = Depends(get_db)):
        key = str(uuid.uuid4())
        ref = padvira_create(data, key)
        r = PartnerRequest(tenant_id=user.tenant_id, user_id=user.id, partner="padvira", service=data.service[:160], reference=ref, contact=data.contact,
                           summary=data.message[:1000], status="new", checked_at=utcnow())
        db.add(r)
        if audit:
            audit(db, user, "partner.padvira.request", "partner_request", {"service": data.service, "ref": ref})
        db.commit()
        return _out(r)

    @api.post("/partners/giftasan/souvenir-requests", status_code=201)
    def giftasan(data: SouvenirIn, user=Depends(current_user), db: Session = Depends(get_db)):
        own = str(uuid.uuid4())
        ref = giftasan_create(data, own)
        r = PartnerRequest(id=own, tenant_id=user.tenant_id, user_id=user.id, partner="giftasan", service=f"سوغات {data.city}"[:160], reference=ref, contact=data.contact,
                           summary=f"{data.items} — ارسال به {data.deliver_to}"[:1000], status="on-hold", checked_at=utcnow())
        db.add(r)
        if audit:
            audit(db, user, "partner.giftasan.souvenir", "partner_request", {"city": data.city, "order": ref})
        db.commit()
        return _out(r)

    @api.get("/me/partner-requests")
    def mine(user=Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(PartnerRequest).where(PartnerRequest.tenant_id == user.tenant_id, PartnerRequest.user_id == user.id).order_by(PartnerRequest.created_at.desc()).limit(50)).all()
        now = utcnow()
        changed = False
        for r in rows[:10]:   # refresh recent ones, at most every 10 minutes
            last = r.checked_at if r.checked_at is None or r.checked_at.tzinfo else r.checked_at.replace(tzinfo=timezone.utc)
            if r.status in ("done", "rejected", "completed", "cancelled") or (last and now - last < timedelta(minutes=10)):
                continue
            info = padvira_track(r.reference, r.contact) if r.partner == "padvira" else giftasan_status(r.reference)
            r.checked_at = now
            changed = True
            if info and isinstance(info.get("status"), str):
                r.status = info["status"][:24]
                note = info.get("publicNote")
                if isinstance(note, str) and note.strip():
                    r.public_note = note.strip()[:2000]
        if changed:
            db.commit()
        return {"items": [_out(r) for r in rows]}

    return api


__all__ = ["partner_requests_router", "PartnerRequest", "padvira_create", "giftasan_create", "padvira_track", "giftasan_status"]
