"""Traveller documents (مدارک مسافر): customer upload, staff review queue with masked preview, automatic deletion.

* Customers upload passport / national card / visa / photo files for their own travellers or reservations.
* Staff see a queue without the file; the default preview is a blurred, low-resolution rendering (images only).
  Opening the original requires a reason and is written to the audit log.
* Retention: every document gets `delete_after` (tenant setting, default 90 days after upload). A document linked to a
  reservation that is still active is kept until that reservation ends. The sweep removes the file from storage and
  keeps only the metadata row (type, masked number, status, dates) as evidence.
"""
from __future__ import annotations

import io
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin
from .storage import StorageError, sha256_hex, storage_root, validate_upload

DOC_TYPES = {"passport": "گذرنامه", "national_id": "کارت ملی", "visa": "ویزا", "photo": "عکس پرسنلی", "birth_certificate": "شناسنامه", "other": "سایر"}
ACTIVE_RES = ("draft", "booking_pending", "pending", "reserved", "awaiting_payment", "confirmed", "issued", "change_requested", "cancel_requested", "refund_requested", "changed")
DEFAULT_RETENTION_DAYS = 90
_KEY_RE = re.compile(r"^tenant/[1-9][0-9]{0,17}/traveller-docs/[0-9a-f]{32}\.[a-z0-9]{2,5}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aw(dt: Optional[datetime]) -> Optional[datetime]:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def _iso(dt: Optional[datetime]) -> Optional[str]:
    dt = _aw(dt)
    return dt.isoformat() if dt else None


def mask_number(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = re.sub(r"\s", "", value)
    return "•" * max(0, len(v) - 3) + v[-3:]


def _path(key: str) -> Path:
    if not _KEY_RE.match(key or ""):
        raise StorageError("کلید ذخیره‌سازی نامعتبر است")
    root = storage_root()
    p = (root / key).resolve()
    if root not in p.parents:
        raise StorageError("مسیر ذخیره‌سازی خارج از محدوده مجاز است")
    return p


def blurred_preview(data: bytes) -> bytes:
    """Low-resolution, heavily blurred JPEG: enough to see that the right kind of document was sent, not to read it."""
    from PIL import Image, ImageFilter

    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((360, 360))
        w, h = im.size
        im = im.resize((max(1, w // 12), max(1, h // 12))).resize((w, h), Image.NEAREST)
        im = im.filter(ImageFilter.GaussianBlur(6))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=60)
        return out.getvalue()


class TravellerDocument(OperationalMixin, Base):
    __tablename__ = "traveller_documents"
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    traveller_id: Mapped[Optional[str]] = mapped_column(ForeignKey("travellers.id"), nullable=True, index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reservations.id"), nullable=True, index=True)
    doc_type: Mapped[str] = mapped_column(String(24), index=True)
    holder_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    number_masked: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    expires_on: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="submitted", index=True)  # submitted | approved | rejected | deleted
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delete_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_reason: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)  # retention | owner | staff


class DocumentSettings(OperationalMixin, Base):
    __tablename__ = "traveller_document_settings"
    retention_days: Mapped[int] = mapped_column(Integer, default=DEFAULT_RETENTION_DAYS)
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_traveller_doc_settings_tenant"),)


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: Optional[str] = Field(default=None, max_length=500)


class RevealIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class SettingsIn(BaseModel):
    retention_days: int = Field(ge=7, le=730)


def traveller_documents_router(get_db, current_user, role_has_permission, User, audit=None):
    api = APIRouter(tags=["traveller-documents"])

    def staff(user=Depends(current_user)):
        if user.role in ("employee", "customer") or not any(role_has_permission(user.role, p) for p in ("backoffice:read", "support:manage", "tenant:manage")):
            raise HTTPException(status_code=403, detail="دسترسی کارشناس عملیات لازم است")
        return user

    def _retention(db: Session, tenant_id: int) -> int:
        s = db.scalar(select(DocumentSettings).where(DocumentSettings.tenant_id == tenant_id))
        return s.retention_days if s else DEFAULT_RETENTION_DAYS

    def _remove_file(d: TravellerDocument, reason: str):
        if d.storage_key:
            try:
                _path(d.storage_key).unlink()
            except (FileNotFoundError, StorageError):
                pass
        d.storage_key, d.status, d.deleted_at, d.deleted_reason = None, "deleted", utcnow(), reason

    def sweep(db: Session, tenant_id: int) -> int:
        """Delete files past retention, unless the linked reservation is still active."""
        n = 0
        for d in db.scalars(select(TravellerDocument).where(TravellerDocument.tenant_id == tenant_id, TravellerDocument.status != "deleted",
                                                            TravellerDocument.delete_after <= utcnow())).all():
            if d.reservation_id:
                st = db.scalar(select(m.Reservation.status).where(m.Reservation.id == d.reservation_id))
                if st in ACTIVE_RES:
                    continue
            _remove_file(d, "retention")
            n += 1
        return n

    def _out(d: TravellerDocument, owner: Optional[str] = None, booking: Optional[str] = None) -> dict:
        return {"id": d.id, "doc_type": d.doc_type, "doc_type_fa": DOC_TYPES.get(d.doc_type, d.doc_type), "holder_name": d.holder_name,
                "number": d.number_masked, "expires_on": d.expires_on, "status": d.status, "review_note": d.review_note,
                "reservation_id": d.reservation_id, "booking_reference": booking, "traveller_id": d.traveller_id, "owner": owner,
                "content_type": d.content_type, "byte_size": d.byte_size, "has_file": bool(d.storage_key),
                "uploaded_at": _iso(d.created_at), "reviewed_at": _iso(d.reviewed_at), "delete_after": _iso(d.delete_after),
                "deleted_at": _iso(d.deleted_at), "deleted_reason": d.deleted_reason}

    # ------------------------------------------------------------ customer
    @api.post("/me/documents", status_code=201)
    async def upload(doc_type: str = Form(...), file: UploadFile = File(...), holder_name: Optional[str] = Form(default=None),
                     number: Optional[str] = Form(default=None), expires_on: Optional[str] = Form(default=None),
                     reservation_id: Optional[str] = Form(default=None), traveller_id: Optional[str] = Form(default=None),
                     user=Depends(current_user), db: Session = Depends(get_db)):
        if doc_type not in DOC_TYPES:
            raise HTTPException(status_code=422, detail="نوع مدرک نامعتبر است")
        if number and not re.fullmatch(r"[A-Za-z0-9\s-]{4,30}", number):
            raise HTTPException(status_code=422, detail="شماره‌ی مدرک نامعتبر است")
        if expires_on:
            try:
                date.fromisoformat(expires_on)
            except ValueError:
                raise HTTPException(status_code=422, detail="تاریخ انقضا نامعتبر است")
        if reservation_id and db.scalar(select(m.Reservation.id).where(m.Reservation.id == reservation_id, m.Reservation.tenant_id == user.tenant_id,
                                                                       m.Reservation.user_id == user.id)) is None:
            raise HTTPException(status_code=404, detail="رزرو یافت نشد")
        if traveller_id and db.scalar(select(m.Traveller.id).where(m.Traveller.id == traveller_id, m.Traveller.tenant_id == user.tenant_id,
                                                                    m.Traveller.user_id == user.id)) is None:
            raise HTTPException(status_code=404, detail="مسافر یافت نشد")
        data = await file.read(15 * 1024 * 1024 + 1)
        try:
            ext, ctype = validate_upload(kind="document", filename=file.filename or "", content_type=file.content_type or "", data=data)
        except StorageError as e:
            raise HTTPException(status_code=422, detail=str(e))
        key = f"tenant/{int(user.tenant_id)}/traveller-docs/{uuid.uuid4().hex}.{ext}"
        p = _path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        d = TravellerDocument(tenant_id=user.tenant_id, owner_user_id=user.id, traveller_id=traveller_id, reservation_id=reservation_id, doc_type=doc_type,
                              holder_name=(holder_name or "").strip()[:160] or None, number_masked=mask_number(number), expires_on=expires_on,
                              storage_key=key, content_type=ctype, byte_size=len(data), sha256=sha256_hex(data), status="submitted",
                              delete_after=utcnow() + timedelta(days=_retention(db, user.tenant_id)))
        db.add(d)
        db.commit()
        return _out(d)

    @api.get("/me/documents")
    def mine(user=Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(TravellerDocument).where(TravellerDocument.tenant_id == user.tenant_id, TravellerDocument.owner_user_id == user.id)
                          .order_by(TravellerDocument.created_at.desc()).limit(200)).all()
        return {"items": [_out(d) for d in rows], "retention_days": _retention(db, user.tenant_id)}

    @api.delete("/me/documents/{doc_id}")
    def delete_mine(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
        d = db.scalar(select(TravellerDocument).where(TravellerDocument.id == doc_id, TravellerDocument.tenant_id == user.tenant_id,
                                                      TravellerDocument.owner_user_id == user.id))
        if d is None:
            raise HTTPException(status_code=404, detail="مدرک یافت نشد")
        if d.status != "deleted":
            _remove_file(d, "owner")
        db.commit()
        return _out(d)

    # ------------------------------------------------------------ staff queue
    @api.get("/ops/documents")
    def queue(status: str = Query(default="submitted", pattern="^(submitted|approved|rejected|deleted|all)$"), user=Depends(staff), db: Session = Depends(get_db)):
        purged = sweep(db, user.tenant_id)
        if purged:
            db.commit()
        s = select(TravellerDocument, User.name, m.Reservation.booking_reference).join(User, User.id == TravellerDocument.owner_user_id) \
            .outerjoin(m.Reservation, m.Reservation.id == TravellerDocument.reservation_id).where(TravellerDocument.tenant_id == user.tenant_id)
        if status != "all":
            s = s.where(TravellerDocument.status == status)
        rows = db.execute(s.order_by(TravellerDocument.created_at).limit(300)).all()
        counts = {k: 0 for k in ("submitted", "approved", "rejected", "deleted")}
        for st in db.scalars(select(TravellerDocument.status).where(TravellerDocument.tenant_id == user.tenant_id)).all():
            counts[st] = counts.get(st, 0) + 1
        return {"items": [_out(d, owner, ref) for d, owner, ref in rows], "counts": counts, "purged_now": purged, "retention_days": _retention(db, user.tenant_id)}

    def _doc(db: Session, user, doc_id: str, lock: bool = False) -> TravellerDocument:
        q = select(TravellerDocument).where(TravellerDocument.id == doc_id, TravellerDocument.tenant_id == user.tenant_id)
        d = db.scalar(q.with_for_update() if lock else q)
        if d is None:
            raise HTTPException(status_code=404, detail="مدرک یافت نشد")
        return d

    @api.get("/ops/documents/{doc_id}/preview")
    def preview(doc_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        d = _doc(db, user, doc_id)
        if not d.storage_key:
            raise HTTPException(status_code=410, detail="فایل این مدرک حذف شده است")
        if not (d.content_type or "").startswith("image/"):
            raise HTTPException(status_code=415, detail="برای PDF پیش‌نمایش پوشانده وجود ندارد؛ نمایش اصل با ثبت دلیل")
        try:
            return Response(content=blurred_preview(_path(d.storage_key).read_bytes()), media_type="image/jpeg", headers={"Cache-Control": "no-store"})
        except (FileNotFoundError, StorageError):
            raise HTTPException(status_code=410, detail="فایل این مدرک در دسترس نیست")

    @api.post("/ops/documents/{doc_id}/reveal")
    def reveal(doc_id: str, data: RevealIn, user=Depends(staff), db: Session = Depends(get_db)):
        d = _doc(db, user, doc_id)
        if not d.storage_key:
            raise HTTPException(status_code=410, detail="فایل این مدرک حذف شده است")
        try:
            blob = _path(d.storage_key).read_bytes()
        except (FileNotFoundError, StorageError):
            raise HTTPException(status_code=410, detail="فایل این مدرک در دسترس نیست")
        if audit:
            audit(db, user, "traveller_document.revealed", "traveller_document", {"document_id": d.id, "reason": data.reason})
        db.commit()
        return Response(content=blob, media_type=d.content_type or "application/octet-stream",
                        headers={"Cache-Control": "no-store", "Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})

    @api.post("/ops/documents/{doc_id}/review")
    def review(doc_id: str, data: ReviewIn, user=Depends(staff), db: Session = Depends(get_db)):
        d = _doc(db, user, doc_id, lock=True)
        if d.status == "deleted":
            raise HTTPException(status_code=409, detail="این مدرک حذف شده است")
        if data.decision == "reject" and not (data.note or "").strip():
            raise HTTPException(status_code=422, detail="برای رد مدرک، دلیل را بنویسید تا مشتری بداند چه کند")
        d.status = "approved" if data.decision == "approve" else "rejected"
        d.review_note, d.reviewed_by, d.reviewed_at = (data.note or "").strip() or None, user.id, utcnow()
        if audit:
            audit(db, user, f"traveller_document.{d.status}", "traveller_document", {"document_id": d.id})
        db.commit()
        return _out(d)

    @api.put("/ops/documents/settings")
    def put_settings(data: SettingsIn, user=Depends(current_user), db: Session = Depends(get_db)):
        if not role_has_permission(user.role, "tenant:manage"):
            raise HTTPException(status_code=403, detail="فقط مدیر مجموعه می‌تواند مدت نگهداری را تغییر دهد")
        s = db.scalar(select(DocumentSettings).where(DocumentSettings.tenant_id == user.tenant_id))
        if s is None:
            s = DocumentSettings(tenant_id=user.tenant_id)
            db.add(s)
        s.retention_days = data.retention_days
        if audit:
            audit(db, user, "traveller_document.retention_set", "traveller_document_settings", {"days": data.retention_days})
        db.commit()
        return {"retention_days": s.retention_days, "applies_to": "مدارکی که از این به بعد بارگذاری می‌شوند"}

    @api.post("/ops/documents/purge")
    def purge(user=Depends(staff), db: Session = Depends(get_db)):
        n = sweep(db, user.tenant_id)
        db.commit()
        return {"purged": n}

    return api
