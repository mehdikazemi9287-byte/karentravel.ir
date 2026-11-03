"""Site content management (مدیریت محتوای سایت).

Editable slots of the public homepage and footer, with a draft → publish flow, a revision history and a media
library. Every slot has a fixed schema (text, internal link, image) so an editor cannot put prices, ratings or
availability into marketing content; those still come only from real offers. Nothing here is shown publicly until
it is published, and the public site falls back to its built-in content for any slot never published.

Images are stored in the tenant's media library (JPEG/PNG/WebP, magic bytes checked, SVG refused) and served by an
immutable id. An image that is used by a draft or published slot cannot be deleted.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .operations import OperationalMixin

MAX_IMAGE_BYTES = 3 * 1024 * 1024
_HREF = r"^(/[^\s]*|https://[^\s]+)$"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SiteContentBlock(OperationalMixin, Base):
    __tablename__ = "site_content_blocks"
    key: Mapped[str] = mapped_column(String(40))
    draft_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    draft_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_site_content_block_key"),)


class SiteContentRevision(OperationalMixin, Base):
    __tablename__ = "site_content_revisions"
    key: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[int] = mapped_column(Integer)
    data_json: Mapped[str] = mapped_column(Text)
    published_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class SiteMediaAsset(OperationalMixin, Base):
    __tablename__ = "site_media_assets"
    filename: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    alt: Mapped[str] = mapped_column(String(200), default="")
    data: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


# ---- slot schemas -------------------------------------------------------------------------------------------
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


Image = Field(min_length=1, max_length=200, pattern=r"^(/images/[A-Za-z0-9_./-]+|media:[0-9a-f-]{36})$")


class Card(Strict):
    title: str = Field(min_length=1, max_length=60)
    title2: str = Field(default="", max_length=60)
    meta: str = Field(default="", max_length=60)
    href: str = Field(pattern=_HREF, max_length=300)
    image: str = Image


class Hero(Strict):
    title: str = Field(min_length=1, max_length=40)
    title2: str = Field(default="", max_length=40)
    subtitle: str = Field(default="", max_length=120)
    subtitle2: str = Field(default="", max_length=120)
    image: str = Image
    image_alt: str = Field(default="", max_length=160)
    minis: list[Card] = Field(default_factory=list, max_length=2)


class Bento(Strict):
    title: str = Field(min_length=1, max_length=40)
    title2: str = Field(default="", max_length=40)
    tiles: list[Card] = Field(min_length=4, max_length=4)


class Trips(Strict):
    title: str = Field(min_length=1, max_length=80)
    items: list[Card] = Field(min_length=1, max_length=6)


class Assistant(Strict):
    title: str = Field(min_length=1, max_length=80)
    prompts: list[str] = Field(min_length=1, max_length=6)

    @field_validator("prompts")
    @classmethod
    def _short(cls, v: list[str]) -> list[str]:
        v = [p.strip() for p in v if p.strip()]
        if not v or any(len(p) > 60 for p in v):
            raise ValueError("هر پیشنهاد گفتگو حداکثر ۶۰ حرف است")
        return v


class Compare(Strict):
    title: str = Field(min_length=1, max_length=80)
    items: list[Card] = Field(min_length=2, max_length=2)


class Organization(Strict):
    title: str = Field(min_length=1, max_length=80)
    items: list[str] = Field(min_length=1, max_length=4)


class Footer(Strict):
    tagline: str = Field(min_length=1, max_length=160)
    copyright: str = Field(min_length=1, max_length=120)


class Announcement(Strict):
    active: bool = False
    text: str = Field(default="", max_length=160)
    href: str = Field(default="", pattern=r"^$|" + _HREF, max_length=300)


SLOTS: dict[str, tuple[type[Strict], str]] = {
    "announcement": (Announcement, "نوار اطلاع‌رسانی بالای صفحه"),
    "hero": (Hero, "بخش اصلی بالای صفحه"),
    "bento": (Bento, "کجای ایران صدایت می‌زند"),
    "trips": (Trips, "سفرهای انتخاب‌شده"),
    "assistant": (Assistant, "همراه هوشمند"),
    "compare": (Compare, "مقایسه‌ی دو انتخاب"),
    "organization": (Organization, "سفر سازمانی"),
    "footer": (Footer, "پانویس سایت"),
}
PRICE_WORDS = ("تومان", "ریال", "تخفیف", "%", "٪")


def _media_refs(data: dict) -> set[str]:
    out: set[str] = set()

    def walk(v):
        if isinstance(v, str) and v.startswith("media:"):
            out.add(v[6:])
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(data)
    return out


def validate_slot(key: str, data: dict) -> dict:
    if key not in SLOTS:
        raise HTTPException(status_code=404, detail="این بخش در سایت وجود ندارد")
    try:
        clean = SLOTS[key][0].model_validate(data).model_dump()
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise HTTPException(status_code=422, detail=f"مقدار نامعتبر در «{where}»: {first['msg']}")
    text = json.dumps(clean, ensure_ascii=False)
    if any(ch.isdigit() for ch in text) and any(w in text for w in PRICE_WORDS):
        raise HTTPException(status_code=422, detail="قیمت و درصد تخفیف در محتوای سایت ثبت نمی‌شود؛ قیمت فقط از نتیجه‌ی استعلام نمایش داده می‌شود")
    return clean


def sniff_image(data: bytes) -> Optional[str]:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class AltIn(Strict):
    alt: str = Field(default="", max_length=200)


def site_cms_router(get_db, current_user, role_has_permission, public_tenant: Callable, audit: Optional[Callable] = None) -> APIRouter:
    api = APIRouter(tags=["site-cms"])

    def editor(user=Depends(current_user)):
        if user.role not in ("platform_admin", "tenant_admin", "backoffice_expert") and not role_has_permission(user.role, "tenant:manage"):
            raise HTTPException(status_code=403, detail="ویرایش محتوای سایت فقط برای مدیران مجموعه است")
        return user

    def _block(db: Session, tenant_id: int, key: str, lock: bool = False) -> Optional[SiteContentBlock]:
        s = select(SiteContentBlock).where(SiteContentBlock.tenant_id == tenant_id, SiteContentBlock.key == key)
        return db.scalar(s.with_for_update() if lock else s)

    def _check_media(db: Session, tenant_id: int, data: dict) -> None:
        refs = _media_refs(data)
        if refs:
            found = set(db.scalars(select(SiteMediaAsset.id).where(SiteMediaAsset.tenant_id == tenant_id, SiteMediaAsset.id.in_(refs))).all())
            if refs - found:
                raise HTTPException(status_code=422, detail="تصویر انتخاب‌شده در کتابخانه‌ی رسانه پیدا نشد")

    def _view(key: str, b: Optional[SiteContentBlock]) -> dict:
        return {"key": key, "label": SLOTS[key][1], "draft": json.loads(b.draft_json) if b and b.draft_json else None,
                "published": json.loads(b.published_json) if b and b.published_json else None, "version": b.version if b else 0,
                "has_unpublished_changes": bool(b and b.draft_json and b.draft_json != b.published_json),
                "published_at": b.published_at.isoformat() if b and b.published_at else None}

    @api.get("/cms/blocks")
    def list_blocks(user=Depends(editor), db: Session = Depends(get_db)):
        rows = {b.key: b for b in db.scalars(select(SiteContentBlock).where(SiteContentBlock.tenant_id == user.tenant_id)).all()}
        return {"items": [_view(k, rows.get(k)) for k in SLOTS]}

    @api.put("/cms/blocks/{key}")
    def save_draft(key: str, data: dict, user=Depends(editor), db: Session = Depends(get_db)):
        clean = validate_slot(key, data)
        _check_media(db, user.tenant_id, clean)
        b = _block(db, user.tenant_id, key, lock=True)
        if b is None:
            b = SiteContentBlock(tenant_id=user.tenant_id, key=key, version=0)
            db.add(b)
        b.draft_json, b.draft_by = json.dumps(clean, ensure_ascii=False, sort_keys=True), user.id
        if audit:
            audit(db, user, "cms.draft.saved", "site_content_block", {"key": key})
        db.commit()
        return _view(key, b)

    @api.post("/cms/blocks/{key}/publish")
    def publish(key: str, user=Depends(editor), db: Session = Depends(get_db)):
        if key not in SLOTS:
            raise HTTPException(status_code=404, detail="این بخش در سایت وجود ندارد")
        b = _block(db, user.tenant_id, key, lock=True)
        if b is None or not b.draft_json:
            raise HTTPException(status_code=409, detail="پیش‌نویسی برای انتشار وجود ندارد")
        clean = validate_slot(key, json.loads(b.draft_json))
        _check_media(db, user.tenant_id, clean)
        b.version += 1
        b.published_json, b.published_at, b.published_by = b.draft_json, utcnow(), user.id
        db.add(SiteContentRevision(tenant_id=user.tenant_id, key=key, version=b.version, data_json=b.draft_json, published_by=user.id))
        if audit:
            audit(db, user, "cms.published", "site_content_block", {"key": key, "version": b.version})
        db.commit()
        return _view(key, b)

    @api.post("/cms/blocks/{key}/unpublish")
    def unpublish(key: str, user=Depends(editor), db: Session = Depends(get_db)):
        b = _block(db, user.tenant_id, key, lock=True)
        if b is None or not b.published_json:
            raise HTTPException(status_code=409, detail="این بخش منتشر نشده است")
        b.published_json, b.published_at = None, None
        if audit:
            audit(db, user, "cms.unpublished", "site_content_block", {"key": key})
        db.commit()
        return _view(key, b)

    @api.get("/cms/blocks/{key}/revisions")
    def revisions(key: str, user=Depends(editor), db: Session = Depends(get_db)):
        rows = db.scalars(select(SiteContentRevision).where(SiteContentRevision.tenant_id == user.tenant_id, SiteContentRevision.key == key)
                          .order_by(SiteContentRevision.version.desc()).limit(30)).all()
        return {"items": [{"id": r.id, "version": r.version, "created_at": r.created_at.isoformat(), "data": json.loads(r.data_json)} for r in rows]}

    @api.post("/cms/blocks/{key}/revisions/{revision_id}/restore")
    def restore(key: str, revision_id: str, user=Depends(editor), db: Session = Depends(get_db)):
        r = db.scalar(select(SiteContentRevision).where(SiteContentRevision.id == revision_id, SiteContentRevision.tenant_id == user.tenant_id, SiteContentRevision.key == key))
        if r is None:
            raise HTTPException(status_code=404, detail="نسخه یافت نشد")
        return save_draft(key, json.loads(r.data_json), user, db)

    # ---- media library ----
    def _media_view(m: SiteMediaAsset, used: set[str]) -> dict:
        return {"id": m.id, "ref": f"media:{m.id}", "filename": m.filename, "content_type": m.content_type, "size_bytes": m.size_bytes,
                "alt": m.alt, "created_at": m.created_at.isoformat(), "in_use": m.id in used}

    def _used(db: Session, tenant_id: int) -> set[str]:
        used: set[str] = set()
        for d, p in db.execute(select(SiteContentBlock.draft_json, SiteContentBlock.published_json).where(SiteContentBlock.tenant_id == tenant_id)).all():
            for raw in (d, p):
                if raw:
                    used |= _media_refs(json.loads(raw))
        return used

    @api.get("/cms/media")
    def list_media(user=Depends(editor), db: Session = Depends(get_db)):
        used = _used(db, user.tenant_id)
        rows = db.scalars(select(SiteMediaAsset).where(SiteMediaAsset.tenant_id == user.tenant_id).order_by(SiteMediaAsset.created_at.desc()).limit(500)).all()
        return {"items": [_media_view(m, used) for m in rows], "max_bytes": MAX_IMAGE_BYTES}

    @api.post("/cms/media", status_code=201)
    async def upload(file: UploadFile = File(...), alt: str = Form(default=""), user=Depends(editor), db: Session = Depends(get_db)):
        data = await file.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="حجم تصویر بیشتر از ۳ مگابایت است")
        kind = sniff_image(data)
        if kind is None:
            raise HTTPException(status_code=415, detail="فقط تصویر JPG، PNG یا WebP پذیرفته می‌شود")
        digest = hashlib.sha256(data).hexdigest()
        same = db.scalar(select(SiteMediaAsset).where(SiteMediaAsset.tenant_id == user.tenant_id, SiteMediaAsset.sha256 == digest))
        if same is not None:
            return _media_view(same, set()) | {"duplicate": True}
        name = (file.filename or "image").replace("\\", "/").rsplit("/", 1)[-1][:160] or "image"
        m = SiteMediaAsset(tenant_id=user.tenant_id, filename=name, content_type=kind, size_bytes=len(data), sha256=digest, alt=alt.strip()[:200], data=data, uploaded_by=user.id)
        db.add(m)
        if audit:
            audit(db, user, "cms.media.uploaded", "site_media_asset", {"filename": name, "size": len(data)})
        db.commit()
        return _media_view(m, set())

    @api.put("/cms/media/{media_id}")
    def set_alt(media_id: str, data: AltIn, user=Depends(editor), db: Session = Depends(get_db)):
        m = db.scalar(select(SiteMediaAsset).where(SiteMediaAsset.id == media_id, SiteMediaAsset.tenant_id == user.tenant_id))
        if m is None:
            raise HTTPException(status_code=404, detail="تصویر یافت نشد")
        m.alt = data.alt
        db.commit()
        return _media_view(m, _used(db, user.tenant_id))

    @api.delete("/cms/media/{media_id}")
    def delete_media(media_id: str, user=Depends(editor), db: Session = Depends(get_db)):
        m = db.scalar(select(SiteMediaAsset).where(SiteMediaAsset.id == media_id, SiteMediaAsset.tenant_id == user.tenant_id))
        if m is None:
            raise HTTPException(status_code=404, detail="تصویر یافت نشد")
        if media_id in _used(db, user.tenant_id):
            raise HTTPException(status_code=409, detail="این تصویر در محتوای سایت استفاده شده است؛ اول آن را از بخش مربوط بردارید")
        db.delete(m)
        if audit:
            audit(db, user, "cms.media.deleted", "site_media_asset", {"filename": m.filename})
        db.commit()
        return {"deleted": True}

    # ---- public ----
    @api.get("/public/tenants/{tenant_slug}/site-content")
    def public_content(tenant_slug: str, response: Response, db: Session = Depends(get_db)):
        tenant = public_tenant(db, tenant_slug)
        rows = db.execute(select(SiteContentBlock.key, SiteContentBlock.published_json).where(SiteContentBlock.tenant_id == tenant.id, SiteContentBlock.published_json.is_not(None))).all()
        response.headers["Cache-Control"] = "public, max-age=60"
        return {k: json.loads(v) for k, v in rows if k in SLOTS}

    @api.get("/public/tenants/{tenant_slug}/media/{media_id}")
    def public_media(tenant_slug: str, media_id: str, db: Session = Depends(get_db)):
        tenant = public_tenant(db, tenant_slug)
        m = db.scalar(select(SiteMediaAsset).where(SiteMediaAsset.id == media_id, SiteMediaAsset.tenant_id == tenant.id))
        if m is None:
            raise HTTPException(status_code=404, detail="تصویر یافت نشد")
        return Response(content=m.data, media_type=m.content_type, headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"})

    return api


__all__ = ["site_cms_router", "SLOTS", "validate_slot", "sniff_image", "SiteContentBlock", "SiteContentRevision", "SiteMediaAsset"]
