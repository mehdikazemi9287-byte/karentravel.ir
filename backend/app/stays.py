"""Own hotel contracts (KarenSeir design): contract -> rooms -> nightly rate & allotment calendar.

Availability for concrete dates is computed from the calendar (allotment, stop-sell, closed-to-arrival,
min/max stay, release days). A chosen room is materialised as a fixed-stay hotel Offer so the
normal price-check / checkout path (and commerce markup rules) apply. Rooms sold = units consumed on
those offers, counted per night, so a night never sells beyond its allotment at materialisation time.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import operations as m
from .catalog import CatalogHotel
from .database import Base
from .operations import OperationalMixin

TEHRAN = ZoneInfo("Asia/Tehran")
BOARDS = {"RO": "بدون صبحانه", "BB": "با صبحانه", "HB": "نیم‌پانسیون", "FB": "تمام‌پانسیون", "AI": "همه‌چیز رایگان"}


class HotelContract(OperationalMixin, Base):
    __tablename__ = "stay_contracts"
    hotel_id: Mapped[str] = mapped_column(ForeignKey("catalog_hotels.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    valid_from: Mapped[str] = mapped_column(String(10))
    valid_to: Mapped[str] = mapped_column(String(10))
    release_days: Mapped[int] = mapped_column(Integer, default=0)
    min_stay: Mapped[int] = mapped_column(Integer, default=1)
    max_stay: Mapped[int] = mapped_column(Integer, default=30)
    refundable: Mapped[bool] = mapped_column(Boolean, default=True)
    penalty_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    child_free_age: Mapped[int] = mapped_column(Integer, default=2)
    child_max_age: Mapped[int] = mapped_column(Integer, default=12)
    terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


class ContractRoom(OperationalMixin, Base):
    __tablename__ = "stay_contract_rooms"
    contract_id: Mapped[str] = mapped_column(ForeignKey("stay_contracts.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    board: Mapped[str] = mapped_column(String(4), default="BB")
    max_adults: Mapped[int] = mapped_column(Integer, default=2)
    max_children: Mapped[int] = mapped_column(Integer, default=1)
    extra_beds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")


class RoomNight(OperationalMixin, Base):
    __tablename__ = "stay_room_nights"
    room_id: Mapped[str] = mapped_column(ForeignKey("stay_contract_rooms.id"), index=True)
    night: Mapped[str] = mapped_column(String(10), index=True)
    allotment: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[int] = mapped_column(Integer, default=0)            # per room per night, for base occupancy (max_adults)
    single_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)   # one adult
    extra_bed_price: Mapped[int] = mapped_column(Integer, default=0)
    child_price: Mapped[int] = mapped_column(Integer, default=0)
    stop_sell: Mapped[bool] = mapped_column(Boolean, default=False)
    closed_to_arrival: Mapped[bool] = mapped_column(Boolean, default=False)
    min_stay: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "room_id", "night", name="uq_stay_room_night"),)


TABLES = ("stay_contracts", "stay_contract_rooms", "stay_room_nights")


# ---------------------------------------------------------------- schemas
class ContractIn(BaseModel):
    hotel_id: str = Field(min_length=1, max_length=64)
    supplier_id: str
    title: str = Field(min_length=2, max_length=160)
    currency: str = Field(default="IRR", pattern="^[A-Z]{3}$")
    valid_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    valid_to: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    release_days: int = Field(default=0, ge=0, le=60)
    min_stay: int = Field(default=1, ge=1, le=30)
    max_stay: int = Field(default=30, ge=1, le=60)
    refundable: bool = True
    penalty_code: Optional[str] = Field(default=None, max_length=40)
    child_free_age: int = Field(default=2, ge=0, le=17)
    child_max_age: int = Field(default=12, ge=0, le=17)
    terms: Optional[str] = Field(default=None, max_length=8000)
    status: str = Field(default="active", pattern="^(active|disabled)$")


class RoomIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    board: str = Field(default="BB")
    max_adults: int = Field(default=2, ge=1, le=8)
    max_children: int = Field(default=1, ge=0, le=6)
    extra_beds: int = Field(default=0, ge=0, le=3)
    status: str = Field(default="active", pattern="^(active|disabled)$")

    @field_validator("board")
    @classmethod
    def _b(cls, v):
        if v not in BOARDS:
            raise ValueError("نوع وعده معتبر نیست")
        return v


class CalendarIn(BaseModel):
    date_from: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)))   # python weekday(): 0=Monday
    allotment: Optional[int] = Field(default=None, ge=0, le=500)
    price: Optional[int] = Field(default=None, ge=0)
    single_price: Optional[int] = Field(default=None, ge=0)
    extra_bed_price: Optional[int] = Field(default=None, ge=0)
    child_price: Optional[int] = Field(default=None, ge=0)
    stop_sell: Optional[bool] = None
    closed_to_arrival: Optional[bool] = None
    min_stay: Optional[int] = Field(default=None, ge=1, le=30)


class BookIn(BaseModel):
    room_id: str
    checkin: date
    checkout: date
    adults: int = Field(ge=1, le=8)
    children_ages: list[int] = Field(default_factory=list, max_length=6)
    rooms: int = Field(default=1, ge=1, le=10)


# ---------------------------------------------------------------- availability engine
def _nights(checkin: date, checkout: date) -> list[str]:
    return [(checkin + timedelta(days=i)).isoformat() for i in range((checkout - checkin).days)]


def _sold_by_night(db: Session, tenant_id: int, room_id: str, nights: list[str]) -> dict[str, int]:
    """Rooms consumed on materialised offers of this room, per night (initial units - remaining units)."""
    sold = {n: 0 for n in nights}
    offers = db.scalars(select(m.Offer).where(m.Offer.tenant_id == tenant_id, m.Offer.service_type == "hotel", m.Offer.provider_key == "karenseir_contract",
                                              m.Offer.attributes_json.like(f'%"stay_room_id": "{room_id}"%'))).all()
    for o in offers:
        a = json.loads(o.attributes_json or "{}")
        used = int(a.get("stay_units_initial", 0)) - int(o.available_units or 0)
        if used <= 0:
            continue
        for n in a.get("stay_nights", []):
            if n in sold:
                sold[n] += used
    return sold


def _price_room(room: ContractRoom, contract: HotelContract, night_rows: list[RoomNight], adults: int, children_ages: list[int]) -> Optional[int]:
    paying_children = [a for a in children_ages if contract.child_free_age <= a <= contract.child_max_age]
    adult_like = [a for a in children_ages if a > contract.child_max_age]
    adults_total = adults + len(adult_like)
    if adults_total > room.max_adults + room.extra_beds or len(children_ages) - len(adult_like) > room.max_children + max(0, room.max_adults + room.extra_beds - adults_total):
        return None
    total = 0
    for r in night_rows:
        base = r.single_price if adults_total == 1 and r.single_price else r.price
        extra = max(0, adults_total - room.max_adults) * r.extra_bed_price
        total += base + extra + len(paying_children) * r.child_price
    return total


def availability(db: Session, tenant_id: int, hotel_id: str, checkin: date, checkout: date, adults: int, children_ages: list[int], rooms: int = 1,
                 today: Optional[date] = None) -> list[dict]:
    today = today or datetime.now(TEHRAN).date()
    nights = _nights(checkin, checkout)
    if not nights or checkin < today:
        return []
    out = []
    contracts = db.scalars(select(HotelContract).where(HotelContract.tenant_id == tenant_id, HotelContract.hotel_id == hotel_id, HotelContract.status == "active",
                                                       HotelContract.valid_from <= nights[0], HotelContract.valid_to >= nights[-1])).all()
    for c in contracts:
        if len(nights) < c.min_stay or len(nights) > c.max_stay or (checkin - today).days < c.release_days:
            continue
        for room in db.scalars(select(ContractRoom).where(ContractRoom.tenant_id == tenant_id, ContractRoom.contract_id == c.id, ContractRoom.status == "active")):
            rows = {r.night: r for r in db.scalars(select(RoomNight).where(RoomNight.tenant_id == tenant_id, RoomNight.room_id == room.id, RoomNight.night.in_(nights)))}
            if len(rows) != len(nights):
                continue
            first = rows[nights[0]]
            if first.closed_to_arrival or (first.min_stay and len(nights) < first.min_stay):
                continue
            if any(r.stop_sell or r.price <= 0 for r in rows.values()):
                continue
            sold = _sold_by_night(db, tenant_id, room.id, nights)
            free = min(rows[n].allotment - sold[n] for n in nights)
            if free < rooms:
                continue
            price = _price_room(room, c, [rows[n] for n in nights], adults, children_ages)
            if price is None:
                continue
            out.append({"room_id": room.id, "contract_id": c.id, "room_name": room.name, "board": room.board, "board_fa": BOARDS[room.board], "nights": len(nights),
                        "rooms_left": free, "net_total_per_room": price, "currency": c.currency, "refundable": c.refundable, "penalty_code": c.penalty_code,
                        "terms": c.terms, "supplier_id": c.supplier_id})
    return sorted(out, key=lambda x: x["net_total_per_room"])


def has_contract(db: Session, tenant_id: int, hotel_ids: set[str]) -> set[str]:
    if not hotel_ids:
        return set()
    today = datetime.now(TEHRAN).date().isoformat()
    return set(db.scalars(select(HotelContract.hotel_id).where(HotelContract.tenant_id == tenant_id, HotelContract.hotel_id.in_(hotel_ids),
                                                               HotelContract.status == "active", HotelContract.valid_to >= today)))


# ---------------------------------------------------------------- router
def stays_router(get_db, current_user, role_has_permission, User, audit=None, optional_user=None):
    api = APIRouter(tags=["stays"])

    def admin(user=Depends(current_user)):
        if not any(role_has_permission(user.role, p) for p in ("platform:manage", "tenant:manage", "inventory:manage")):
            raise HTTPException(status_code=403, detail="دسترسی مدیریت موجودی لازم است")
        return user

    def _a(db, user, action, ref, detail=None):
        if audit:
            try:
                audit(db, user, action, ref, detail or {})
            except Exception:
                pass

    def _get(db, model, tenant_id, row_id):
        row = db.scalar(select(model).where(model.id == row_id, model.tenant_id == tenant_id))
        if row is None:
            raise HTTPException(status_code=404, detail="یافت نشد")
        return row

    def _cdict(c, hotel_name=None):
        d = {k: getattr(c, k) for k in ("id", "hotel_id", "supplier_id", "title", "currency", "valid_from", "valid_to", "release_days", "min_stay", "max_stay",
                                         "refundable", "penalty_code", "child_free_age", "child_max_age", "terms", "status")}
        d["hotel_name"] = hotel_name
        return d

    @api.get("/stays/hotels/search")
    def hotel_lookup(q: str = Query(min_length=2, max_length=80), user=Depends(admin), db: Session = Depends(get_db)):
        like = f"%{q}%"
        rows = db.scalars(select(CatalogHotel).where(or_(CatalogHotel.name_fa.ilike(like), CatalogHotel.name_en.ilike(like), CatalogHotel.slug.ilike(like))).limit(15)).all()
        return {"items": [{"id": h.id, "name": h.name_fa or h.name_en, "slug": h.slug, "city_id": h.city_id, "stars": h.stars} for h in rows]}

    @api.get("/stays/contracts")
    def contracts(user=Depends(admin), db: Session = Depends(get_db)):
        rows = db.execute(select(HotelContract, CatalogHotel.name_fa).join(CatalogHotel, CatalogHotel.id == HotelContract.hotel_id)
                          .where(HotelContract.tenant_id == user.tenant_id).order_by(HotelContract.valid_from.desc())).all()
        return {"items": [_cdict(c, n) for c, n in rows]}

    def _save_contract(db, user, row, data):
        if db.get(CatalogHotel, data.hotel_id) is None:
            raise HTTPException(status_code=422, detail="هتل در فهرست هتل‌ها پیدا نشد")
        if db.scalar(select(m.Supplier.id).where(m.Supplier.id == data.supplier_id, m.Supplier.tenant_id == user.tenant_id)) is None:
            raise HTTPException(status_code=422, detail="تأمین‌کننده معتبر نیست")
        if data.valid_to < data.valid_from or data.max_stay < data.min_stay or data.child_max_age < data.child_free_age:
            raise HTTPException(status_code=422, detail="بازه‌ی تاریخ، مدت اقامت یا سن کودک نامعتبر است")
        for k, v in data.model_dump().items():
            setattr(row, k, v)
        db.flush()
        _a(db, user, "stays.contract.saved", row.id)
        db.commit()
        return _cdict(row)

    @api.post("/stays/contracts", status_code=201)
    def create_contract(data: ContractIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = HotelContract(tenant_id=user.tenant_id)
        db.add(row)
        return _save_contract(db, user, row, data)

    @api.put("/stays/contracts/{contract_id}")
    def update_contract(contract_id: str, data: ContractIn, user=Depends(admin), db: Session = Depends(get_db)):
        return _save_contract(db, user, _get(db, HotelContract, user.tenant_id, contract_id), data)

    def _rdict(r):
        return {k: getattr(r, k) for k in ("id", "contract_id", "name", "board", "max_adults", "max_children", "extra_beds", "status")}

    @api.get("/stays/contracts/{contract_id}/rooms")
    def rooms(contract_id: str, user=Depends(admin), db: Session = Depends(get_db)):
        _get(db, HotelContract, user.tenant_id, contract_id)
        return {"items": [_rdict(r) for r in db.scalars(select(ContractRoom).where(ContractRoom.tenant_id == user.tenant_id, ContractRoom.contract_id == contract_id).order_by(ContractRoom.name))]}

    @api.post("/stays/contracts/{contract_id}/rooms", status_code=201)
    def add_room(contract_id: str, data: RoomIn, user=Depends(admin), db: Session = Depends(get_db)):
        _get(db, HotelContract, user.tenant_id, contract_id)
        row = ContractRoom(tenant_id=user.tenant_id, contract_id=contract_id, **data.model_dump())
        db.add(row)
        db.commit()
        return _rdict(row)

    @api.put("/stays/contracts/{contract_id}/rooms/{room_id}")
    def update_room(contract_id: str, room_id: str, data: RoomIn, user=Depends(admin), db: Session = Depends(get_db)):
        row = _get(db, ContractRoom, user.tenant_id, room_id)
        if row.contract_id != contract_id:
            raise HTTPException(status_code=404, detail="یافت نشد")
        for k, v in data.model_dump().items():
            setattr(row, k, v)
        db.commit()
        return _rdict(row)

    @api.get("/stays/rooms/{room_id}/calendar")
    def calendar(room_id: str, date_from: str, date_to: str, user=Depends(admin), db: Session = Depends(get_db)):
        room = _get(db, ContractRoom, user.tenant_id, room_id)
        rows = {r.night: r for r in db.scalars(select(RoomNight).where(RoomNight.tenant_id == user.tenant_id, RoomNight.room_id == room.id,
                                                                       RoomNight.night >= date_from, RoomNight.night <= date_to))}
        d0, d1 = date.fromisoformat(date_from), date.fromisoformat(date_to)
        if (d1 - d0).days > 120:
            raise HTTPException(status_code=422, detail="حداکثر ۱۲۰ روز")
        nights = [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
        sold = _sold_by_night(db, user.tenant_id, room.id, nights)
        out = []
        for n in nights:
            r = rows.get(n)
            out.append({"night": n, "weekday": date.fromisoformat(n).weekday(), "allotment": r.allotment if r else 0, "sold": sold[n],
                        "free": (r.allotment if r else 0) - sold[n], "price": r.price if r else None, "single_price": r.single_price if r else None,
                        "extra_bed_price": r.extra_bed_price if r else None, "child_price": r.child_price if r else None,
                        "stop_sell": bool(r and r.stop_sell), "closed_to_arrival": bool(r and r.closed_to_arrival), "min_stay": r.min_stay if r else None})
        return {"room": _rdict(room), "nights": out}

    @api.put("/stays/rooms/{room_id}/calendar")
    def set_calendar(room_id: str, data: CalendarIn, user=Depends(admin), db: Session = Depends(get_db)):
        room = _get(db, ContractRoom, user.tenant_id, room_id)
        d0, d1 = date.fromisoformat(data.date_from), date.fromisoformat(data.date_to)
        if d1 < d0 or (d1 - d0).days > 400:
            raise HTTPException(status_code=422, detail="بازه‌ی تاریخ نامعتبر است (حداکثر ۴۰۰ روز)")
        nights = [(d0 + timedelta(days=i)) for i in range((d1 - d0).days + 1)]
        nights = [n for n in nights if n.weekday() in set(data.weekdays)]
        sold = _sold_by_night(db, user.tenant_id, room.id, [n.isoformat() for n in nights])
        changed = 0
        for n in nights:
            key = n.isoformat()
            r = db.scalar(select(RoomNight).where(RoomNight.tenant_id == user.tenant_id, RoomNight.room_id == room.id, RoomNight.night == key))
            if r is None:
                r = RoomNight(tenant_id=user.tenant_id, room_id=room.id, night=key, allotment=0, price=0, extra_bed_price=0, child_price=0)
                db.add(r)
            if data.allotment is not None:
                if data.allotment < sold[key]:
                    raise HTTPException(status_code=409, detail=f"ظرفیت شب {key} نمی‌تواند کمتر از {sold[key]} اتاق فروخته‌شده باشد")
                r.allotment = data.allotment
            for f in ("price", "single_price", "extra_bed_price", "child_price", "stop_sell", "closed_to_arrival", "min_stay"):
                v = getattr(data, f)
                if v is not None:
                    setattr(r, f, v)
            changed += 1
        _a(db, user, "stays.calendar.set", room.id, {"nights": changed})
        db.commit()
        return {"nights_updated": changed}

    # ---- public availability + booking handoff
    def _quote_rows(db, tenant_id, hotel, user_id, checkin, checkout, adults, ages, rooms):
        from .commerce import quote as commerce_quote
        rows = availability(db, tenant_id, hotel.id, checkin, checkout, adults, ages, rooms)
        for r in rows:
            ctx = {"service_type": "hotel", "supplier_id": r["supplier_id"], "city_id": hotel.city_id, "stars": hotel.stars,
                   "scope": "domestic" if (hotel.country_code or "").upper() == "IR" else "international"}
            q = commerce_quote(db, tenant_id, ctx, {"adult": {"count": 1, "total": r["net_total_per_room"]}}, user_id=user_id)
            r["total_per_room"] = q["lines"][0]["sell"] if q["lines"] else r["net_total_per_room"]
            r["total"] = r["total_per_room"] * rooms
            r.pop("supplier_id", None)
            r.pop("net_total_per_room", None)
        return rows

    def _hotel(db, slug):
        h = db.scalar(select(CatalogHotel).where(or_(CatalogHotel.slug == slug, CatalogHotel.id == slug), CatalogHotel.status == "published"))
        if h is None:
            raise HTTPException(status_code=404, detail="هتل پیدا نشد")
        return h

    def _ages(children_ages: Optional[str]) -> list[int]:
        try:
            ages = [int(x) for x in (children_ages or "").split(",") if x.strip() != ""]
        except ValueError:
            raise HTTPException(status_code=422, detail="سن کودکان نامعتبر است")
        if any(a < 0 or a > 17 for a in ages) or len(ages) > 6:
            raise HTTPException(status_code=422, detail="سن کودکان نامعتبر است")
        return ages

    @api.get("/stays/hotels/{slug}/contracted")
    def contracted(slug: str, user=Depends(current_user), db: Session = Depends(get_db)):
        hotel = _hotel(db, slug)
        return {"hotel_id": hotel.id, "contracted": hotel.id in has_contract(db, user.tenant_id, {hotel.id})}

    @api.get("/stays/hotels/{slug}/availability")
    def public_availability(slug: str, checkin: date, checkout: date, adults: int = Query(default=2, ge=1, le=8), children_ages: Optional[str] = None,
                            rooms: int = Query(default=1, ge=1, le=10), user=Depends(current_user), db: Session = Depends(get_db)):
        if checkout <= checkin or (checkout - checkin).days > 30:
            raise HTTPException(status_code=422, detail="بازه‌ی اقامت نامعتبر است")
        hotel = _hotel(db, slug)
        return {"hotel_id": hotel.id, "checkin": checkin.isoformat(), "checkout": checkout.isoformat(),
                "offers": _quote_rows(db, user.tenant_id, hotel, user.id, checkin, checkout, adults, _ages(children_ages), rooms)}

    @api.post("/stays/hotels/{slug}/book", status_code=201)
    def book(slug: str, data: BookIn, user=Depends(current_user), db: Session = Depends(get_db)):
        """Materialise the chosen room as a fixed-stay Offer; the client continues with /offers/{id} (price-check, checkout)."""
        hotel = _hotel(db, slug)
        ages = sorted(data.children_ages)
        if data.checkout <= data.checkin or any(a < 0 or a > 17 for a in ages):
            raise HTTPException(status_code=422, detail="اطلاعات اقامت نامعتبر است")
        room = _get(db, ContractRoom, user.tenant_id, data.room_id)
        contract = _get(db, HotelContract, user.tenant_id, room.contract_id)
        if contract.hotel_id != hotel.id:
            raise HTTPException(status_code=404, detail="اتاق در این هتل نیست")
        # lock the room's nights for the duration of the check
        nights = _nights(data.checkin, data.checkout)
        db.execute(select(RoomNight).where(RoomNight.tenant_id == user.tenant_id, RoomNight.room_id == room.id, RoomNight.night.in_(nights)).with_for_update()).all()
        rows = [r for r in availability(db, user.tenant_id, hotel.id, data.checkin, data.checkout, data.adults, ages, data.rooms) if r["room_id"] == room.id]
        if not rows:
            raise HTTPException(status_code=409, detail="این اتاق برای تاریخ و ترکیب مسافران انتخاب‌شده موجود نیست")
        r = rows[0]
        expires = min(datetime.now(timezone.utc) + timedelta(minutes=30), datetime.combine(data.checkin, time(12, 0), tzinfo=TEHRAN).astimezone(timezone.utc))
        occupancy = {"adults": data.adults, "children_ages": ages}
        attrs = {"hotel_rate": {"check_in": data.checkin.isoformat(), "check_out": data.checkout.isoformat(), "room_type": room.name, "rate_plan": BOARDS[room.board],
                                "price_basis": "room_stay", "occupancy": occupancy},
                 "city": hotel.city_id, "city_id": hotel.city_id, "stars": hotel.stars, "catalog_hotel_id": hotel.id, "hotel_slug": hotel.slug,
                 "board": room.board, "stay_room_id": room.id, "stay_contract_id": contract.id, "stay_nights": nights, "stay_units_initial": data.rooms,
                 "supplier_net_rate": r["net_total_per_room"], "supplier_currency": contract.currency, "price_source": "CTR",
                 "authoritative_inventory": True, "instant_booking": True, "observed_at": datetime.now(timezone.utc).isoformat(), "penalty_code": contract.penalty_code}
        policy = {"verified": True, "cancellation": {"refundable": bool(contract.refundable), "penalty_code": contract.penalty_code}, "terms": contract.terms}
        offer = m.Offer(tenant_id=user.tenant_id, supplier_id=contract.supplier_id, service_type="hotel", title=f"{hotel.name_fa or hotel.name_en} · {room.name} · {BOARDS[room.board]}",
                        amount=r["net_total_per_room"], currency=contract.currency, available_units=data.rooms, status="active", provider_key="karenseir_contract",
                        fulfillment_mode="manual_supplier", attributes_json=json.dumps(attrs, ensure_ascii=False, sort_keys=True),
                        policy_json=json.dumps(policy, ensure_ascii=False, sort_keys=True), valid_until=expires)
        db.add(offer)
        db.flush()
        db.commit()
        return {"offer_id": offer.id, "hotel_stay": {"check_in": data.checkin.isoformat(), "check_out": data.checkout.isoformat(), "rooms": [occupancy] * data.rooms},
                "expires_at": expires.isoformat()}

    return api
