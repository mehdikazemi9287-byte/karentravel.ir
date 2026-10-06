"""Admin editing of global hotel master content (ADR-028 addendum).

Only platform_admin / backoffice_expert (guard injected by main). Every save is one transaction with
an audit event; saving marks the row admin-owned (updated_by) so bulk importers never overwrite it.
Prices, rates and availability are not part of this contract and are rejected by the schema.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Callable, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from .catalog import (AMENITIES, BED_TYPES, HOTEL_STATUS, HOTEL_TYPES, POLICY_FIELDS, POLICY_VALUES, ROOM_VIEWS, STARS_STATUS, CatalogHotel, CatalogHotelImage,
                      CatalogHotelRoomType, CatalogPlace, _hotel, _places_for, hotel_image, normalize_text, room_type)

Policy = Optional[Literal["allowed", "not_allowed", "on_request"]]
_URL = r"^https://[^\s]+$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown keys (e.g. price) are a 422, never silently stored


def _known_amenities(v: list[str]) -> list[str]:
    bad = [a for a in v if a not in AMENITIES]
    if bad: raise ValueError(f"امکانات ناشناخته: {', '.join(bad)}")
    return list(dict.fromkeys(v))


class ImageIn(Strict):
    url: str = Field(pattern=_URL, max_length=500)
    caption: Optional[str] = Field(default=None, max_length=200)
    author: Optional[str] = Field(default=None, max_length=200)
    license: str = Field(min_length=2, max_length=80)
    license_url: Optional[str] = Field(default=None, pattern=_URL, max_length=300)
    source_url: str = Field(pattern=_URL, max_length=500)


class RoomTypeIn(Strict):
    name_fa: str = Field(min_length=2, max_length=160)
    name_en: Optional[str] = Field(default=None, max_length=160)
    bed_type: Optional[Literal[tuple(BED_TYPES)]] = None  # type: ignore[valid-type]
    max_adults: Optional[int] = Field(default=None, ge=1, le=12)
    max_children: Optional[int] = Field(default=None, ge=0, le=8)
    size_m2: Optional[int] = Field(default=None, ge=5, le=1000)
    view: Optional[Literal[tuple(ROOM_VIEWS)]] = None  # type: ignore[valid-type]
    amenities: list[str] = Field(default_factory=list, max_length=30)
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("amenities")
    @classmethod
    def known(cls, v: list[str]) -> list[str]:
        return _known_amenities(v)


class HotelIn(Strict):
    name_fa: Optional[str] = Field(default=None, max_length=200)
    name_en: Optional[str] = Field(default=None, max_length=200)
    name_local: Optional[str] = Field(default=None, max_length=200)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    city_id: Optional[str] = Field(default=None, max_length=80)
    hotel_type: Literal[tuple(HOTEL_TYPES)] = "hotel"  # type: ignore[valid-type]
    stars: Optional[int] = Field(default=None, ge=1, le=5)
    stars_status: Optional[Literal[tuple(STARS_STATUS)]] = None  # type: ignore[valid-type]
    address: Optional[str] = Field(default=None, max_length=400)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    amenities: list[str] = Field(default_factory=list, max_length=40)
    description: Optional[str] = Field(default=None, max_length=6000)
    rules_text: Optional[str] = Field(default=None, max_length=4000)
    checkin_time: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    checkout_time: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    children_policy: Policy = None
    pets_policy: Policy = None
    smoking_policy: Policy = None
    phone: Optional[str] = Field(default=None, max_length=80)
    website: Optional[str] = Field(default=None, pattern=_URL, max_length=300)
    email: Optional[str] = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=160)
    status: Literal[tuple(HOTEL_STATUS)] = "draft"  # type: ignore[valid-type]
    source_ref: Optional[str] = Field(default=None, max_length=200)
    retrieved_on: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    images: list[ImageIn] = Field(default_factory=list, max_length=40)
    room_types: list[RoomTypeIn] = Field(default_factory=list, max_length=40)

    @field_validator("amenities")
    @classmethod
    def known_amenities(cls, v: list[str]) -> list[str]:
        return _known_amenities(v)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:150] or "hotel"


def catalog_admin_router(get_db, guard: Callable, audit: Callable) -> APIRouter:
    router = APIRouter(prefix="/admin/catalog", tags=["catalog-admin"])

    def full(db: Session, row: CatalogHotel) -> dict:
        data = _hotel(row, _places_for(db, {row.city_id, row.region_id, row.country_code.lower()}), full=True)
        data.update({"status": row.status, "children_policy": row.children_policy, "pets_policy": row.pets_policy, "smoking_policy": row.smoking_policy,
                     "amenity_keys": json.loads(row.amenities_json or "[]"), "updated_at": row.updated_at.isoformat() if row.updated_at else None, "admin_owned": row.updated_by is not None,
                     "images": [hotel_image(i) for i in db.scalars(select(CatalogHotelImage).where(CatalogHotelImage.hotel_id == row.id).order_by(CatalogHotelImage.sort_order))],
                     "room_types": [room_type(r) for r in db.scalars(select(CatalogHotelRoomType).where(CatalogHotelRoomType.hotel_id == row.id).order_by(CatalogHotelRoomType.sort_order))]})
        return data

    @router.get("/options")
    def options(user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        countries = db.scalars(select(CatalogPlace).where(CatalogPlace.kind == "country").order_by(CatalogPlace.name_fa)).all()
        return {"hotel_types": HOTEL_TYPES, "amenities": AMENITIES, "policy_fields": POLICY_FIELDS, "policy_values": POLICY_VALUES, "bed_types": BED_TYPES, "views": ROOM_VIEWS,
                "stars_status": STARS_STATUS, "status": HOTEL_STATUS, "countries": [{"code": c.country_code, "name": c.name_fa or c.name_en} for c in countries]}

    @router.get("/cities")
    def cities(country: str = Query(pattern=r"^[A-Z]{2}$"), q: str = "", user=Depends(guard), db: Session = Depends(get_db)) -> list[dict]:
        stmt = select(CatalogPlace).where(CatalogPlace.kind == "city", CatalogPlace.country_code == country)
        if normalize_text(q): stmt = stmt.where(CatalogPlace.search_text.like(f"%{normalize_text(q)}%"))
        return [{"id": c.id, "name": c.name_fa or c.name_en, "name_en": c.name_en} for c in db.scalars(stmt.order_by(CatalogPlace.hotel_count.desc(), CatalogPlace.population.desc().nulls_last()).limit(50))]

    @router.get("/hotels")
    def list_hotels(q: str = "", status: Optional[str] = None, source: Optional[str] = None, country: Optional[str] = None, offset: int = Query(default=0, ge=0),
                    limit: int = Query(default=30, ge=1, le=100), user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        stmt = select(CatalogHotel)
        if status: stmt = stmt.where(CatalogHotel.status == status)
        if source: stmt = stmt.where(CatalogHotel.source == source)
        if country: stmt = stmt.where(CatalogHotel.country_code == country.upper())
        for token in normalize_text(q).split()[:4]: stmt = stmt.where(or_(CatalogHotel.search_text.like(f"%{token}%"), CatalogHotel.id == q.strip()))
        total = db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = db.scalars(stmt.order_by(CatalogHotel.updated_at.desc().nulls_last(), CatalogHotel.quality.desc(), CatalogHotel.id).offset(offset).limit(limit)).all()
        places = _places_for(db, {r.city_id for r in rows})
        return {"total": total, "items": [{"id": r.id, "slug": r.slug, "name": r.name_fa or r.name_en or r.name_local, "name_en": r.name_en, "country_code": r.country_code,
                                           "city": (places[r.city_id].name_fa or places[r.city_id].name_en) if r.city_id in places else None, "stars": r.stars, "status": r.status,
                                           "source": r.source, "admin_owned": r.updated_by is not None} for r in rows]}

    @router.get("/hotels/{hotel_id}")
    def get_hotel(hotel_id: str, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        row = db.get(CatalogHotel, hotel_id)
        if row is None: raise HTTPException(status_code=404, detail="هتل پیدا نشد")
        return full(db, row)

    def apply(db: Session, row: CatalogHotel, data: HotelIn, user) -> None:
        if not (data.name_fa or data.name_en or data.name_local): raise HTTPException(status_code=422, detail="دست‌کم یک نام لازم است")
        if (data.latitude is None) != (data.longitude is None): raise HTTPException(status_code=422, detail="عرض و طول جغرافیایی باید با هم ثبت شوند")
        if data.stars is not None and data.stars_status is None: raise HTTPException(status_code=422, detail="وضعیت تأیید درجهٔ ستاره را مشخص کنید")
        city = db.get(CatalogPlace, data.city_id) if data.city_id else None
        if data.city_id and (city is None or city.kind != "city" or city.country_code != data.country_code): raise HTTPException(status_code=422, detail="شهر با کشور انتخاب‌شده هم‌خوان نیست")
        if data.status == "published" and city is None: raise HTTPException(status_code=422, detail="برای انتشار، شهر الزامی است")
        for key, value in data.model_dump(exclude={"images", "room_types", "amenities"}).items(): setattr(row, key, value)
        row.region_id = city.parent_id if city and city.parent_id and city.parent_id != data.country_code.lower() else None
        row.amenities_json = json.dumps(data.amenities)
        row.image_url = data.images[0].url if data.images else None
        row.image_credit = f"{data.images[0].author or ''} · {data.images[0].license}".strip(" ·") if data.images else None
        names = " ".join(filter(None, [data.name_fa, data.name_en, data.name_local, city.search_text if city else "", data.address]))
        row.search_text = normalize_text(names)
        row.quality = sum(bool(x) for x in (data.name_fa, data.address, data.description, data.images, data.room_types, data.amenities, data.checkin_time, data.stars))
        row.updated_at, row.updated_by = datetime.now(timezone.utc), user.id
        db.flush()
        db.execute(delete(CatalogHotelImage).where(CatalogHotelImage.hotel_id == row.id))
        db.execute(delete(CatalogHotelRoomType).where(CatalogHotelRoomType.hotel_id == row.id))
        db.add_all([CatalogHotelImage(hotel_id=row.id, sort_order=i, **img.model_dump()) for i, img in enumerate(data.images)])
        db.add_all([CatalogHotelRoomType(hotel_id=row.id, sort_order=i, amenities_json=json.dumps(rt.amenities), **rt.model_dump(exclude={"amenities"})) for i, rt in enumerate(data.room_types)])

    @router.put("/hotels/{hotel_id}")
    def save_hotel(hotel_id: str, data: HotelIn, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        row = db.scalar(select(CatalogHotel).where(CatalogHotel.id == hotel_id).with_for_update())
        if row is None: raise HTTPException(status_code=404, detail="هتل پیدا نشد")
        before = full(db, row)
        apply(db, row, data, user)
        changed = sorted(k for k, v in data.model_dump().items() if before.get(k if k != "amenities" else "amenity_keys") != v)
        audit(db, user, "catalog_hotel.updated", {"hotel_id": row.id, "changed": changed})
        db.commit()
        return full(db, row)

    @router.post("/hotels", status_code=201)
    def create_hotel(data: HotelIn, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        base = _slugify(data.name_en or data.name_local or "") if (data.name_en or data.name_local) else "hotel"
        hotel_id = f"ks-{db.scalar(select(func.count()).select_from(CatalogHotel).where(CatalogHotel.source == 'karenseir')) + 1:06d}"
        while db.get(CatalogHotel, hotel_id): hotel_id = f"{hotel_id}x"
        row = CatalogHotel(id=hotel_id, slug=f"{base}-{hotel_id}", country_code=data.country_code, hotel_type=data.hotel_type, source="karenseir", source_license="KarenSeir editorial")
        db.add(row)
        apply(db, row, data, user)
        audit(db, user, "catalog_hotel.created", {"hotel_id": row.id})
        db.commit()
        return full(db, row)

    return router
