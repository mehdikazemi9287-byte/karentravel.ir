"""Safarsaz (سفرساز) — the tour builder of the operations panel.

A tour is prepared as a draft (sales data: source, hotels, room prices per room and
passenger type, deposit, cancellation, documents, day-by-day plan, departures with
capacity), checked against a publish checklist, and then published into the
existing bookable catalogue (tour_products / tour_departures). Booking, payment and
public listing keep using the existing, tested tour endpoints.

Sources are restricted to the allowed ones: manual entry, a supplier contract, a
charter block, the platform reference catalogue, or a copy of an earlier tour.
A published tour whose departures have all passed returns to draft
(`/safarsaz/expire`) so it is never sold or shown stale.

All prices are integer IRR. Room types the booking engine can charge are double
(base), single, triple and extra_bed; child/infant prices are kept with the
departure and charged by the tour quote/booking endpoints (children=, infants=).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .database import Base
from .operations import OperationalMixin

SOURCES = ("manual", "supplier_contract", "charter_block", "catalog", "copy")
SOURCE_FA = {"manual": "ورود دستی", "supplier_contract": "قرارداد تأمین‌کننده", "charter_block": "بلوک چارتر", "catalog": "تور مرجع", "copy": "کپی تور قبلی"}
ROOMS = ("double", "single", "triple", "extra_bed")
ROOM_FA = {"double": "دوتخته", "single": "یک‌تخته", "triple": "سه‌تخته", "extra_bed": "تخت اضافه"}
BOARDS = ("RO", "BB", "HB", "FB", "AI")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(v: Optional[datetime]) -> Optional[datetime]:
    if v is None:
        return None
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- models
class SafarsazTour(OperationalMixin, Base):
    __tablename__ = "safarsaz_tours"
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(180))
    origin: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(120), index=True)
    tour_type: Mapped[str] = mapped_column(String(48), default="leisure")
    supplier_id: Mapped[Optional[str]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(24), default="manual")
    source_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    content_json: Mapped[str] = mapped_column(Text, default="{}")  # description, itinerary, hotels, services, documents, cancellation, deposit
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)  # draft | pending_review (sent by a contracted agency) | published | archived
    published_tour_id: Mapped[Optional[str]] = mapped_column(ForeignKey("tour_products.id"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_safarsaz_tour_slug"),)


class SafarsazDeparture(OperationalMixin, Base):
    __tablename__ = "safarsaz_departures"
    tour_id: Mapped[str] = mapped_column(ForeignKey("safarsaz_tours.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booking_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    prices_json: Mapped[str] = mapped_column(Text, default="[]")  # [{room, adult, child, infant}]
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    published_departure_id: Mapped[Optional[str]] = mapped_column(ForeignKey("tour_departures.id"), nullable=True)


# ---------------------------------------------------------------- schemas
class DayIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=2000)


class HotelIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=120)
    nights: int = Field(ge=1, le=60)
    board: str = "BB"
    stars: Optional[int] = Field(default=None, ge=1, le=7)

    @field_validator("board")
    @classmethod
    def _b(cls, v: str) -> str:
        v = v.upper()
        if v not in BOARDS:
            raise ValueError("نوع سرویس هتل نامعتبر است")
        return v


class CancelTierIn(BaseModel):
    days_before: int = Field(ge=0, le=365)
    penalty_bps: int = Field(ge=0, le=10000)


class TourIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=180)
    origin: str = Field(min_length=2, max_length=120)
    destination: str = Field(min_length=2, max_length=120)
    tour_type: str = Field(default="leisure", min_length=2, max_length=48)
    supplier_id: Optional[str] = Field(default=None, max_length=36)
    source: str = "manual"
    source_ref: Optional[str] = Field(default=None, max_length=120)
    description: str = Field(default="", max_length=8000)
    itinerary: list[DayIn] = Field(default_factory=list, max_length=60)
    hotels: list[HotelIn] = Field(default_factory=list, max_length=20)
    inclusions: list[str] = Field(default_factory=list, max_length=40)
    exclusions: list[str] = Field(default_factory=list, max_length=40)
    documents: list[str] = Field(default_factory=list, max_length=20)
    cancellation: list[CancelTierIn] = Field(default_factory=list, max_length=10)
    deposit_bps: int = Field(default=0, ge=0, le=10000)
    visa_status: str = Field(default="VISA_NOT_REQUIRED", pattern="^(VISA_NOT_REQUIRED|VISA_REQUIRED|VISA_ON_ARRIVAL|VISA_STATUS_UNKNOWN)$")

    @field_validator("source")
    @classmethod
    def _s(cls, v: str) -> str:
        if v not in SOURCES:
            raise ValueError("منبع تور مجاز نیست")
        return v

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.fullmatch(r"[a-z0-9-]{3,180}", v):
            raise ValueError("نامک فقط حروف کوچک لاتین، عدد و خط تیره")
        return v or None

    @model_validator(mode="after")
    def _ref(self):
        if self.source in ("supplier_contract", "charter_block", "catalog") and not (self.source_ref and self.source_ref.strip()):
            raise ValueError("برای این منبع، شناسه‌ی قرارداد/بلوک/تور مرجع لازم است")
        return self


class PriceIn(BaseModel):
    room: str
    adult: int = Field(gt=0)
    child: Optional[int] = Field(default=None, ge=0)
    infant: Optional[int] = Field(default=None, ge=0)

    @field_validator("room")
    @classmethod
    def _r(cls, v: str) -> str:
        if v not in ROOMS:
            raise ValueError("نوع اتاق نامعتبر است")
        return v


class DepartureIn(BaseModel):
    starts_at: datetime
    ends_at: datetime
    booking_deadline: datetime
    capacity: int = Field(ge=1, le=10000)
    prices: list[PriceIn] = Field(min_length=1, max_length=len(ROOMS))

    @model_validator(mode="after")
    def _check(self):
        s, e, d = _aware(self.starts_at), _aware(self.ends_at), _aware(self.booking_deadline)
        if e <= s:
            raise ValueError("تاریخ برگشت باید بعد از رفت باشد")
        if d > s:
            raise ValueError("مهلت رزرو باید پیش از حرکت باشد")
        rooms = [p.room for p in self.prices]
        if len(set(rooms)) != len(rooms):
            raise ValueError("هر نوع اتاق فقط یک بار")
        if "double" not in rooms:
            raise ValueError("نرخ اتاق دوتخته (پایه) لازم است")
        return self


# ---------------------------------------------------------------- helpers
def _slugify(title: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return (s[:160].strip("-") if len(s) >= 3 else "tour") + "-" + fallback[:6]


def pricing_for_engine(prices: list[dict]) -> tuple[int, dict]:
    """Map the room/passenger matrix to the booking engine: double = base, others = surcharge per traveller."""
    by = {p["room"]: p for p in prices}
    base = int(by["double"]["adult"])
    pricing = {f"{room}_surcharge": int(by[room]["adult"]) - base for room in ROOMS if room != "double" and room in by}
    pricing["matrix"] = [{k: p.get(k) for k in ("room", "adult", "child", "infant")} for p in prices]
    return base, pricing


def checklist(tour: SafarsazTour, departures: list[SafarsazDeparture], supplier_ok: bool, now: datetime) -> list[dict]:
    c = json.loads(tour.content_json or "{}")
    future = [d for d in departures if _aware(d.booking_deadline) > now]
    items = [
        ("basics", "عنوان، مبدأ و مقصد", bool(tour.title and tour.origin and tour.destination)),
        ("supplier", "برگزارکننده‌ی فعال", supplier_ok),
        ("source", "منبع مجاز ثبت شده", tour.source in SOURCES),
        ("description", "معرفی تور (حداقل ۴۰ نویسه)", len((c.get("description") or "").strip()) >= 40),
        ("itinerary", "برنامه‌ی روزانه", len(c.get("itinerary") or []) >= 1),
        ("hotels", "هتل و نوع سرویس", len(c.get("hotels") or []) >= 1),
        ("cancellation", "قوانین کنسلی", len(c.get("cancellation") or []) >= 1),
        ("documents", "مدارک لازم مسافر", len(c.get("documents") or []) >= 1),
        ("departure", "حداقل یک حرکت با مهلت رزرو باز و نرخ", len(future) >= 1),
    ]
    return [{"key": k, "label": label, "ok": ok} for k, label, ok in items]


def _content(data: TourIn) -> str:
    return json.dumps({"description": data.description, "itinerary": [d.model_dump() for d in data.itinerary], "hotels": [h.model_dump() for h in data.hotels],
                       "inclusions": data.inclusions, "exclusions": data.exclusions, "documents": data.documents,
                       "cancellation": [t.model_dump() for t in sorted(data.cancellation, key=lambda t: -t.days_before)],
                       "deposit_bps": data.deposit_bps, "visa_status": data.visa_status}, ensure_ascii=False, sort_keys=True)


def _dep_out(d: SafarsazDeparture, now: datetime) -> dict:
    return {"id": d.id, "starts_at": _aware(d.starts_at).isoformat(), "ends_at": _aware(d.ends_at).isoformat(), "booking_deadline": _aware(d.booking_deadline).isoformat(),
            "capacity": d.capacity, "currency": d.currency, "prices": json.loads(d.prices_json or "[]"), "published": d.published_departure_id is not None,
            "published_departure_id": d.published_departure_id, "open": _aware(d.booking_deadline) > now}


# ---------------------------------------------------------------- router
def safarsaz_router(get_db, current_user, role_has_permission, User, audit=None):
    api = APIRouter(tags=["safarsaz"])

    PARTNER_ROLES = ("supplier", "agency_partner")

    def _is_staff(user) -> bool:
        return user.role not in ("employee", "customer", *PARTNER_ROLES) and any(role_has_permission(user.role, p) for p in ("reservation:manage", "tenant:manage"))

    def _scope(db, user) -> Optional[set[str]]:
        """None = staff (whole tenant); otherwise the organiser (supplier) ids this partner works for:
        its supplier memberships, plus, for an agency user, the tour organiser linked to each agency it is a member of."""
        if _is_staff(user):
            return None
        ids = set(db.scalars(select(m.SupplierMembership.supplier_id).where(m.SupplierMembership.tenant_id == user.tenant_id, m.SupplierMembership.user_id == user.id)).all())
        if user.role == "agency_partner":
            mine = select(m.AgencyMembership.agency_id).where(m.AgencyMembership.tenant_id == user.tenant_id, m.AgencyMembership.user_id == user.id)
            ids |= {sid for sid in db.scalars(select(m.Agency.supplier_id).where(m.Agency.tenant_id == user.tenant_id, m.Agency.id.in_(mine), m.Agency.supplier_id.is_not(None))).all() if sid}
        return ids

    def staff(user=Depends(current_user), db: Session = Depends(get_db)):
        """Tenant staff, or a contracted agency (supplier member) working only on its own tours."""
        if not _is_staff(user) and (user.role not in PARTNER_ROLES or not _scope(db, user)):
            raise HTTPException(status_code=403, detail="دسترسی سفرساز لازم است")
        return user

    def tenant_staff(user=Depends(current_user)):
        if not _is_staff(user):
            raise HTTPException(status_code=403, detail="این کار با کارشناسان مجموعه است")
        return user

    def publisher(user=Depends(current_user)):
        if user.role in ("supplier", "agency_partner") or not (role_has_permission(user.role, "tenant:manage") or role_has_permission(user.role, "platform:manage")):
            raise HTTPException(status_code=403, detail="انتشار تور با مدیر است")
        return user

    def _a(db, user, action, ref, detail=None):
        if audit:
            audit(db, user, action, "safarsaz_tour", {"ref": ref, **(detail or {})})

    def _tour(db, tenant_id, tour_id) -> SafarsazTour:
        t = db.scalar(select(SafarsazTour).where(SafarsazTour.id == tour_id, SafarsazTour.tenant_id == tenant_id))
        if t is None:
            raise HTTPException(status_code=404, detail="تور یافت نشد")
        return t

    def _own(db, user, tour_id) -> SafarsazTour:
        t = _tour(db, user.tenant_id, tour_id)
        scope = _scope(db, user)
        if scope is not None and t.supplier_id not in scope:
            raise HTTPException(status_code=404, detail="تور یافت نشد")
        return t

    def _deps(db, t: SafarsazTour) -> list[SafarsazDeparture]:
        return list(db.scalars(select(SafarsazDeparture).where(SafarsazDeparture.tenant_id == t.tenant_id, SafarsazDeparture.tour_id == t.id).order_by(SafarsazDeparture.starts_at)).all())

    def _supplier_ok(db, t: SafarsazTour) -> bool:
        if not t.supplier_id:
            return False
        return db.scalar(select(m.Supplier.id).where(m.Supplier.id == t.supplier_id, m.Supplier.tenant_id == t.tenant_id, m.Supplier.status == "active")) is not None

    def _out(db, t: SafarsazTour) -> dict:
        now = utcnow()
        deps = _deps(db, t)
        checks = checklist(t, deps, _supplier_ok(db, t), now)
        return {"id": t.id, "title": t.title, "slug": t.slug, "origin": t.origin, "destination": t.destination, "tour_type": t.tour_type,
                "supplier_id": t.supplier_id, "source": t.source, "source_fa": SOURCE_FA.get(t.source, t.source), "source_ref": t.source_ref,
                "status": t.status, "published_tour_id": t.published_tour_id, "published_at": _aware(t.published_at).isoformat() if t.published_at else None,
                **json.loads(t.content_json or "{}"), "departures": [_dep_out(d, now) for d in deps], "checklist": checks,
                "ready": all(c["ok"] for c in checks), "updated_at": _aware(t.updated_at).isoformat() if t.updated_at else None}

    def _validate_refs(db, user, data: TourIn):
        scope = _scope(db, user)
        if scope is not None:
            if data.supplier_id not in scope:
                raise HTTPException(status_code=422, detail="تور را فقط برای آژانس خودتان می‌توانید ثبت کنید")
            if data.source not in ("manual", "copy"):
                raise HTTPException(status_code=422, detail="آژانس همکار تور را با ورود دستی یا کپی ثبت می‌کند")
        if data.supplier_id and db.scalar(select(m.Supplier.id).where(m.Supplier.id == data.supplier_id, m.Supplier.tenant_id == user.tenant_id)) is None:
            raise HTTPException(status_code=422, detail="تأمین‌کننده در این مستأجر نیست")
        if data.source == "copy":
            if not data.source_ref or db.scalar(select(SafarsazTour.id).where(SafarsazTour.id == data.source_ref, SafarsazTour.tenant_id == user.tenant_id)) is None:
                raise HTTPException(status_code=422, detail="تور مبدأ برای کپی یافت نشد")

    def _unique_slug(db, tenant_id, slug, own_id: str = "", own_product: Optional[str] = None):
        if db.scalar(select(SafarsazTour.id).where(SafarsazTour.tenant_id == tenant_id, SafarsazTour.slug == slug, SafarsazTour.id != own_id)) or \
                db.scalar(select(m.TourProduct.id).where(m.TourProduct.tenant_id == tenant_id, m.TourProduct.slug == slug, m.TourProduct.id != (own_product or ""))):
            raise HTTPException(status_code=409, detail="این نامک قبلاً استفاده شده است")

    @api.get("/safarsaz/meta")
    def meta(user=Depends(staff)):
        return {"sources": [{"key": k, "label": SOURCE_FA[k]} for k in SOURCES], "rooms": [{"key": k, "label": ROOM_FA[k]} for k in ROOMS], "boards": list(BOARDS),
                "bookable_online": {"rooms": list(ROOMS), "child_infant_prices": True}}

    @api.get("/safarsaz/suppliers")
    def suppliers(user=Depends(staff), db: Session = Depends(get_db)):
        """Organisers this user may pick: every active supplier for staff, only its own agency for a partner."""
        q = select(m.Supplier.id, m.Supplier.display_name).where(m.Supplier.tenant_id == user.tenant_id, m.Supplier.status == "active")
        scope = _scope(db, user)
        if scope is not None:
            q = q.where(m.Supplier.id.in_(scope or {""}))
        return {"items": [{"id": i, "name": n} for i, n in db.execute(q.order_by(m.Supplier.display_name)).all()], "partner": scope is not None}

    @api.get("/safarsaz/tours")
    def list_tours(status: Optional[str] = None, user=Depends(staff), db: Session = Depends(get_db)):
        s = select(SafarsazTour).where(SafarsazTour.tenant_id == user.tenant_id)
        scope = _scope(db, user)
        if scope is not None:
            s = s.where(SafarsazTour.supplier_id.in_(scope or {""}))
        if status:
            s = s.where(SafarsazTour.status == status)
        rows = db.scalars(s.order_by(SafarsazTour.updated_at.desc())).all()
        now = utcnow()
        out = []
        for t in rows:
            deps = _deps(db, t)
            nxt = next((d for d in deps if _aware(d.starts_at) > now), None)
            checks = checklist(t, deps, _supplier_ok(db, t), now)
            out.append({"id": t.id, "title": t.title, "destination": t.destination, "status": t.status, "source": t.source, "source_fa": SOURCE_FA.get(t.source),
                        "departures": len(deps), "next_departure": _aware(nxt.starts_at).isoformat() if nxt else None,
                        "capacity": sum(d.capacity for d in deps if _aware(d.starts_at) > now), "checklist_done": sum(c["ok"] for c in checks), "checklist_total": len(checks)})
        return {"items": out}

    @api.post("/safarsaz/tours", status_code=201)
    def create(data: TourIn, user=Depends(staff), db: Session = Depends(get_db)):
        _validate_refs(db, user, data)
        new_id = str(uuid.uuid4())
        slug = data.slug or _slugify(data.title, new_id.replace("-", ""))
        _unique_slug(db, user.tenant_id, slug)
        t = SafarsazTour(id=new_id, tenant_id=user.tenant_id, title=data.title.strip(), origin=data.origin.strip(), destination=data.destination.strip(), tour_type=data.tour_type,
                         supplier_id=data.supplier_id, source=data.source, source_ref=data.source_ref, content_json=_content(data), status="draft", created_by=user.id, slug=slug)
        db.add(t)
        _a(db, user, "safarsaz.tour.created", t.id, {"source": t.source})
        db.commit()
        return _out(db, t)

    @api.get("/safarsaz/tours/{tour_id}")
    def get_tour(tour_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        return _out(db, _own(db, user, tour_id))

    @api.put("/safarsaz/tours/{tour_id}")
    def update(tour_id: str, data: TourIn, user=Depends(staff), db: Session = Depends(get_db)):
        t = _own(db, user, tour_id)
        if t.status == "archived":
            raise HTTPException(status_code=409, detail="تور بایگانی‌شده قابل ویرایش نیست")
        _validate_refs(db, user, data)
        if data.slug and data.slug != t.slug:
            if t.published_tour_id:
                raise HTTPException(status_code=409, detail="نامک تور منتشرشده تغییر نمی‌کند")
            _unique_slug(db, user.tenant_id, data.slug, t.id)
            t.slug = data.slug
        t.title, t.origin, t.destination, t.tour_type = data.title.strip(), data.origin.strip(), data.destination.strip(), data.tour_type
        t.supplier_id, t.source, t.source_ref, t.content_json = data.supplier_id, data.source, data.source_ref, _content(data)
        t.updated_at = utcnow()
        _a(db, user, "safarsaz.tour.updated", t.id)
        db.commit()
        return _out(db, t)

    @api.get("/safarsaz/tours/{tour_id}/bookings")
    def tour_bookings(tour_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        """Bookings received on this tour's published departures, per departure. Only the organiser's own tour (404 otherwise).
        Counts and amounts are the stored reservation rows; no customer identity is returned to the partner."""
        t = _own(db, user, tour_id)
        out = []
        for d in _deps(db, t):
            pub = db.scalar(select(m.TourDeparture).where(m.TourDeparture.id == d.published_departure_id, m.TourDeparture.tenant_id == t.tenant_id)) if d.published_departure_id else None
            rows = db.execute(select(m.TourReservation, m.Reservation).join(m.Reservation, m.Reservation.id == m.TourReservation.reservation_id)
                              .where(m.TourReservation.tenant_id == t.tenant_id, m.Reservation.tenant_id == t.tenant_id, m.TourReservation.departure_id == pub.id)
                              .order_by(m.TourReservation.created_at.desc())).all() if pub else []
            items = [{"id": tr.id, "booking_reference": r.booking_reference, "status": r.status, "hold_status": tr.status, "travellers": tr.travellers, "room_type": tr.room_type,
                      "room_fa": ROOM_FA.get(tr.room_type, tr.room_type), "total_amount": tr.total_amount, "currency": pub.currency, "created_at": _aware(tr.created_at).isoformat()} for tr, r in rows]
            active = [i for i in items if i["status"] not in ("cancelled", "canceled", "expired", "refunded")]
            out.append({"departure_id": d.id, "published_departure_id": d.published_departure_id, "starts_at": _aware(d.starts_at).isoformat(), "ends_at": _aware(d.ends_at).isoformat(),
                        "published": pub is not None, "capacity": pub.capacity if pub else d.capacity, "remaining": pub.remaining if pub else None,
                        "booked_travellers": sum(i["travellers"] for i in active), "bookings": items})
        return {"tour_id": t.id, "title": t.title, "departures": out}

    @api.post("/safarsaz/tours/{tour_id}/copy", status_code=201)
    def copy(tour_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        src = _own(db, user, tour_id)
        new_id = str(uuid.uuid4())
        t = SafarsazTour(id=new_id, tenant_id=user.tenant_id, title=src.title + " (کپی)", origin=src.origin, destination=src.destination, tour_type=src.tour_type,
                         supplier_id=src.supplier_id, source="copy", source_ref=src.id, content_json=src.content_json, status="draft", created_by=user.id,
                         slug=_slugify(src.slug, new_id.replace("-", "")))
        db.add(t)
        _a(db, user, "safarsaz.tour.copied", t.id, {"from": src.id})
        db.commit()
        return _out(db, t)

    @api.post("/safarsaz/tours/{tour_id}/departures", status_code=201)
    def add_departure(tour_id: str, data: DepartureIn, user=Depends(staff), db: Session = Depends(get_db)):
        t = _own(db, user, tour_id)
        if t.status == "archived":
            raise HTTPException(status_code=409, detail="تور بایگانی‌شده است")
        if _aware(data.booking_deadline) <= utcnow():
            raise HTTPException(status_code=422, detail="مهلت رزرو گذشته است")
        d = SafarsazDeparture(tenant_id=user.tenant_id, tour_id=t.id, starts_at=data.starts_at, ends_at=data.ends_at, booking_deadline=data.booking_deadline,
                              capacity=data.capacity, prices_json=json.dumps([p.model_dump() for p in data.prices], sort_keys=True))
        db.add(d)
        t.updated_at = utcnow()
        db.commit()
        return _out(db, t)

    @api.delete("/safarsaz/tours/{tour_id}/departures/{dep_id}")
    def remove_departure(tour_id: str, dep_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        t = _own(db, user, tour_id)
        d = db.scalar(select(SafarsazDeparture).where(SafarsazDeparture.id == dep_id, SafarsazDeparture.tour_id == t.id, SafarsazDeparture.tenant_id == user.tenant_id))
        if d is None:
            raise HTTPException(status_code=404, detail="حرکت یافت نشد")
        if d.published_departure_id:
            raise HTTPException(status_code=409, detail="حرکت منتشرشده حذف نمی‌شود؛ آن را در پنل تور متوقف کنید")
        db.delete(d)
        db.commit()
        return _out(db, t)

    @api.post("/safarsaz/tours/{tour_id}/publish")
    def publish(tour_id: str, user=Depends(publisher), db: Session = Depends(get_db)):
        t = _own(db, user, tour_id)
        if t.status == "archived":
            raise HTTPException(status_code=409, detail="تور بایگانی‌شده است")
        now = utcnow()
        deps = _deps(db, t)
        checks = checklist(t, deps, _supplier_ok(db, t), now)
        missing = [c["label"] for c in checks if not c["ok"]]
        if missing:
            raise HTTPException(status_code=409, detail={"code": "CHECKLIST_INCOMPLETE", "message": "چک‌لیست انتشار کامل نیست", "missing": missing})
        c = json.loads(t.content_json)
        details = {"description": c["description"], "itinerary": [{"title": d["title"], "body": d.get("body", "")} for d in c["itinerary"]],
                   "inclusions": c.get("inclusions", []), "exclusions": c.get("exclusions", []), "requirements": c.get("documents", []),
                   "hotels": c.get("hotels", []), "deposit_bps": c.get("deposit_bps", 0), "visa_status": c.get("visa_status", "VISA_STATUS_UNKNOWN"),
                   "cancellation_policy": {"refundable": True, "tiers": c.get("cancellation", [])}, "safarsaz_id": t.id, "source": t.source}
        product = db.get(m.TourProduct, t.published_tour_id) if t.published_tour_id else None
        if product is None:
            product = m.TourProduct(tenant_id=t.tenant_id, supplier_id=t.supplier_id, title=t.title, slug=t.slug, origin=t.origin, destination=t.destination,
                                    tour_type=t.tour_type, status="published", details_json="{}")
            db.add(product)
            db.flush()
        product.title, product.origin, product.destination, product.tour_type, product.supplier_id = t.title, t.origin, t.destination, t.tour_type, t.supplier_id
        product.details_json = json.dumps(details, ensure_ascii=False, sort_keys=True)
        product.status = "published"
        created = 0
        for d in deps:
            if d.published_departure_id or _aware(d.booking_deadline) <= now:
                continue
            base, pricing = pricing_for_engine(json.loads(d.prices_json))
            row = m.TourDeparture(tenant_id=t.tenant_id, tour_id=product.id, starts_at=d.starts_at, ends_at=d.ends_at, booking_deadline=d.booking_deadline,
                                  capacity=d.capacity, remaining=d.capacity, base_price=base, currency=d.currency, status="active", pricing_json=json.dumps(pricing, sort_keys=True))
            db.add(row)
            db.flush()
            d.published_departure_id = row.id
            created += 1
        t.status, t.published_tour_id, t.published_at, t.updated_at = "published", product.id, now, now
        _a(db, user, "safarsaz.tour.published", t.id, {"tour_product_id": product.id, "departures": created})
        db.commit()
        return {**_out(db, t), "new_departures": created}

    @api.post("/safarsaz/tours/{tour_id}/unpublish")
    def unpublish(tour_id: str, user=Depends(publisher), db: Session = Depends(get_db)):
        t = _own(db, user, tour_id)
        if t.published_tour_id:
            product = db.get(m.TourProduct, t.published_tour_id)
            if product is not None and product.tenant_id == t.tenant_id:
                product.status = "draft"
        t.status, t.updated_at = "draft", utcnow()
        _a(db, user, "safarsaz.tour.unpublished", t.id)
        db.commit()
        return _out(db, t)

    @api.post("/safarsaz/tours/{tour_id}/submit")
    def submit(tour_id: str, user=Depends(staff), db: Session = Depends(get_db)):
        """A contracted agency sends a ready draft for review; staff then publish it from the same panel."""
        t = _own(db, user, tour_id)
        if t.status not in ("draft", "pending_review"):
            raise HTTPException(status_code=409, detail="فقط پیش‌نویس برای بررسی فرستاده می‌شود")
        checks = checklist(t, _deps(db, t), _supplier_ok(db, t), utcnow())
        missing = [c["label"] for c in checks if not c["ok"]]
        if missing:
            raise HTTPException(status_code=422, detail="پیش از ارسال کامل کنید: " + "، ".join(missing))
        t.status, t.updated_at = "pending_review", utcnow()
        _a(db, user, "safarsaz.tour.submitted", t.id)
        db.commit()
        return _out(db, t)

    @api.post("/safarsaz/tours/{tour_id}/reject")
    def reject(tour_id: str, user=Depends(tenant_staff), db: Session = Depends(get_db)):
        t = _own(db, user, tour_id)
        if t.status != "pending_review":
            raise HTTPException(status_code=409, detail="این تور در انتظار بررسی نیست")
        t.status, t.updated_at = "draft", utcnow()
        _a(db, user, "safarsaz.tour.returned", t.id)
        db.commit()
        return _out(db, t)

    @api.post("/safarsaz/expire")
    def expire(user=Depends(tenant_staff), db: Session = Depends(get_db)):
        """Published tours with no departure still open for booking go back to draft (site and catalogue stop showing them)."""
        now = utcnow()
        moved = []
        for t in db.scalars(select(SafarsazTour).where(SafarsazTour.tenant_id == user.tenant_id, SafarsazTour.status == "published")).all():
            if any(_aware(d.booking_deadline) > now for d in _deps(db, t)):
                continue
            t.status, t.updated_at = "draft", now
            if t.published_tour_id:
                product = db.get(m.TourProduct, t.published_tour_id)
                if product is not None and product.tenant_id == t.tenant_id:
                    product.status = "draft"
            moved.append(t.id)
        if moved:
            _a(db, user, "safarsaz.tour.expired", ",".join(moved)[:200], {"count": len(moved)})
        db.commit()
        return {"returned_to_draft": len(moved), "ids": moved}

    return api
