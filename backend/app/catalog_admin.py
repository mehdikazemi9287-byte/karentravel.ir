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

from .catalog import (AMENITIES, BED_TYPES, HOTEL_STATUS, HOTEL_TYPES, POLICY_FIELDS, POLICY_VALUES, ROOM_VIEWS, STARS_STATUS, CatalogHotel, CatalogHotelImage, CatalogHotelMatch,
                      CatalogHotelProviderMapping, CatalogHotelRatePlanMapping, CatalogHotelRoomMapping, CatalogHotelRoomType, CatalogPlace, CatalogTour, CatalogTourDeparture, CatalogTourHotel, CatalogTourItineraryDay, TOUR_BOARD, TOUR_TRANSPORT, _hotel, _places_for, content_is_complete, hotel_image, normalize_text, room_type)

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
    mark_verified: bool = False  # reviewer states the content was checked against its source now

    @field_validator("amenities")
    @classmethod
    def known_amenities(cls, v: list[str]) -> list[str]:
        return _known_amenities(v)


class StatusIn(Strict):
    status: Literal[tuple(HOTEL_STATUS)]  # type: ignore[valid-type]


class MatchDecisionIn(Strict):
    decision: Literal["confirm", "reject"]
    merge_fields: bool = False  # on confirm: copy the duplicate's values into the canonical record's EMPTY fields only


class RoomMappingIn(Strict):
    room_type_id: int
    provider_room_id: str = Field(min_length=1, max_length=120)


class RatePlanMappingIn(Strict):
    provider_rate_plan_id: str = Field(min_length=1, max_length=120)
    board: Optional[Literal[tuple(TOUR_BOARD)]] = None  # type: ignore[valid-type]
    refundable: Optional[bool] = None


class ItineraryDayIn(Strict):
    day_no: int = Field(ge=1, le=60)
    title: str = Field(min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=3000)
    place_id: Optional[str] = Field(default=None, max_length=80)


class TourHotelIn(Strict):
    hotel_id: str = Field(max_length=40)
    nights: Optional[int] = Field(default=None, ge=1, le=60)


class TourIn(Strict):
    title_fa: str = Field(min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=6000)
    origin_place_id: Optional[str] = Field(default=None, max_length=80)
    destination_place_id: Optional[str] = Field(default=None, max_length=80)
    duration_nights: Optional[int] = Field(default=None, ge=0, le=60)
    duration_days: Optional[int] = Field(default=None, ge=1, le=61)
    transport_mode: Optional[Literal[tuple(TOUR_TRANSPORT)]] = None  # type: ignore[valid-type]
    board: Optional[Literal[tuple(TOUR_BOARD)]] = None  # type: ignore[valid-type]
    guide_included: Optional[bool] = None
    transfer_included: Optional[bool] = None
    documents_required: Optional[str] = Field(default=None, max_length=3000)
    cancellation_policy_text: Optional[str] = Field(default=None, max_length=4000)
    status: Literal["draft", "published", "hidden"] = "draft"
    itinerary: list[ItineraryDayIn] = Field(default_factory=list, max_length=60)
    hotels: list[TourHotelIn] = Field(default_factory=list, max_length=30)


class ProviderMappingIn(Strict):
    provider: str = Field(pattern=r"^[a-z0-9_-]{2,40}$")
    provider_hotel_id: str = Field(min_length=1, max_length=120)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:150] or "hotel"


def catalog_admin_router(get_db, guard: Callable, audit: Callable, history: Callable) -> APIRouter:
    router = APIRouter(prefix="/admin/catalog", tags=["catalog-admin"])

    def full(db: Session, row: CatalogHotel) -> dict:
        data = _hotel(row, _places_for(db, {row.city_id, row.region_id, row.country_code.lower()}), full=True)
        matches = db.scalars(select(CatalogHotelMatch).where(or_(CatalogHotelMatch.hotel_id == row.id, CatalogHotelMatch.candidate_id == row.id)).order_by(CatalogHotelMatch.id)).all()
        others = {h.id: h for h in db.scalars(select(CatalogHotel).where(CatalogHotel.id.in_({m.hotel_id for m in matches} | {m.candidate_id for m in matches} | {row.duplicate_of or ""})))}

        def brief(hid):
            h = others.get(hid)
            return None if h is None else {"id": h.id, "name": h.name_fa or h.name_en or h.name_local, "name_en": h.name_en, "source": h.source, "status": h.status, "address": h.address}
        data.update({"duplicate_of": brief(row.duplicate_of) if row.duplicate_of else None, "match_basis": row.match_basis,
                     "matches": [{"id": m.id, "basis": m.basis, "status": m.status, "rule_based": m.decided_by is None and m.status != "proposed", "duplicate": brief(m.hotel_id), "canonical": brief(m.candidate_id)} for m in matches],
                     "provider_mappings": [{"id": pm.id, "provider": pm.provider, "provider_hotel_id": pm.provider_hotel_id, "status": pm.status, "verified_at": pm.verified_at.isoformat() if pm.verified_at else None,
                                            "rooms": [{"id": r.id, "room_type_id": r.room_type_id, "provider_room_id": r.provider_room_id} for r in db.scalars(select(CatalogHotelRoomMapping).where(CatalogHotelRoomMapping.mapping_id == pm.id))],
                                            "rate_plans": [{"id": r.id, "provider_rate_plan_id": r.provider_rate_plan_id, "board": r.board, "refundable": r.refundable} for r in db.scalars(select(CatalogHotelRatePlanMapping).where(CatalogHotelRatePlanMapping.mapping_id == pm.id))]}
                                           for pm in db.scalars(select(CatalogHotelProviderMapping).where(CatalogHotelProviderMapping.hotel_id == row.id).order_by(CatalogHotelProviderMapping.id))]})
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
    def list_hotels(q: str = "", status: Optional[str] = None, review: Optional[str] = None, source: Optional[str] = None, country: Optional[str] = None, offset: int = Query(default=0, ge=0),
                    limit: int = Query(default=30, ge=1, le=100), user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        stmt = select(CatalogHotel)
        if status: stmt = stmt.where(CatalogHotel.status == status)
        if review == "duplicates": stmt = stmt.where(or_(CatalogHotel.duplicate_of.is_not(None), CatalogHotel.id.in_(select(CatalogHotelMatch.hotel_id).where(CatalogHotelMatch.status == "proposed"))))
        elif review == "no_city": stmt = stmt.where(CatalogHotel.city_id.is_(None))
        elif review == "complete": stmt = stmt.where(CatalogHotel.content_complete.is_(True))
        elif review == "incomplete": stmt = stmt.where(CatalogHotel.content_complete.is_(False))
        if source: stmt = stmt.where(CatalogHotel.source == source)
        if country: stmt = stmt.where(CatalogHotel.country_code == country.upper())
        for token in normalize_text(q).split()[:4]: stmt = stmt.where(or_(CatalogHotel.search_text.like(f"%{token}%"), CatalogHotel.id == q.strip()))
        total = db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = db.scalars(stmt.order_by(CatalogHotel.updated_at.desc().nulls_last(), CatalogHotel.quality.desc(), CatalogHotel.id).offset(offset).limit(limit)).all()
        places = _places_for(db, {r.city_id for r in rows})
        return {"total": total, "items": [{"id": r.id, "slug": r.slug, "name": r.name_fa or r.name_en or r.name_local, "name_en": r.name_en, "country_code": r.country_code,
                                           "city": (places[r.city_id].name_fa or places[r.city_id].name_en) if r.city_id in places else None, "stars": r.stars, "status": r.status,
                                           "source": r.source, "admin_owned": r.updated_by is not None, "content_complete": bool(r.content_complete), "duplicate_of": r.duplicate_of} for r in rows]}

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
        if data.status == "published" and row.duplicate_of: raise HTTPException(status_code=422, detail="این رکورد تکراری یک هتل دیگر است و منتشر نمی‌شود")
        for key, value in data.model_dump(exclude={"images", "room_types", "amenities", "mark_verified"}).items(): setattr(row, key, value)
        if data.mark_verified: row.last_verified_at = datetime.now(timezone.utc)
        row.region_id = city.parent_id if city and city.parent_id and city.parent_id != data.country_code.lower() else None
        row.amenities_json = json.dumps(data.amenities)
        row.content_complete = content_is_complete(row, len(data.images), len(data.room_types))
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
        changed = sorted(k for k, v in data.model_dump(exclude={"mark_verified"}).items() if before.get(k if k != "amenities" else "amenity_keys") != v) + (["verified"] if data.mark_verified else [])
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

    @router.post("/hotels/{hotel_id}/status")
    def set_status(hotel_id: str, data: StatusIn, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        row = db.scalar(select(CatalogHotel).where(CatalogHotel.id == hotel_id).with_for_update())
        if row is None: raise HTTPException(status_code=404, detail="هتل پیدا نشد")
        if data.status == "published":
            if row.duplicate_of: raise HTTPException(status_code=422, detail="این رکورد تکراری یک هتل دیگر است و منتشر نمی‌شود")
            if not row.city_id: raise HTTPException(status_code=422, detail="برای انتشار، شهر الزامی است")
            if row.stars is not None and row.stars_status is None: raise HTTPException(status_code=422, detail="وضعیت تأیید درجهٔ ستاره را مشخص کنید")
        previous, row.status = row.status, data.status
        row.updated_at, row.updated_by = datetime.now(timezone.utc), user.id
        audit(db, user, "catalog_hotel.status_changed", {"hotel_id": row.id, "from": previous, "to": data.status})
        db.commit()
        return full(db, row)

    @router.get("/hotels/{hotel_id}/history")
    def hotel_history(hotel_id: str, user=Depends(guard), db: Session = Depends(get_db)) -> list[dict]:
        if db.get(CatalogHotel, hotel_id) is None: raise HTTPException(status_code=404, detail="هتل پیدا نشد")
        return history(db, hotel_id)

    @router.post("/matches/{match_id}")
    def decide_match(match_id: int, data: MatchDecisionIn, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        match = db.scalar(select(CatalogHotelMatch).where(CatalogHotelMatch.id == match_id).with_for_update())
        if match is None: raise HTTPException(status_code=404, detail="مورد تطبیق پیدا نشد")
        dup, canonical = db.get(CatalogHotel, match.hotel_id), db.get(CatalogHotel, match.candidate_id)
        now, filled = datetime.now(timezone.utc), []
        if data.decision == "reject":
            match.status = "rejected"
            if dup.duplicate_of == canonical.id: dup.duplicate_of, dup.match_basis = None, None
        else:
            if canonical.duplicate_of: raise HTTPException(status_code=409, detail="رکورد اصلی خودش تکراری رکورد دیگری است")
            if dup.status == "published": raise HTTPException(status_code=409, detail="ابتدا رکورد تکراری را از انتشار خارج کنید")
            match.status, dup.duplicate_of, dup.match_basis = "confirmed", canonical.id, f"{match.basis}+reviewed"
            if data.merge_fields:
                for key in ("name_fa", "name_en", "address", "checkin_time", "checkout_time"):
                    if getattr(canonical, key) in (None, "") and getattr(dup, key):
                        setattr(canonical, key, getattr(dup, key)); filled.append(key)
                if canonical.stars is None and dup.stars is not None:
                    canonical.stars, canonical.stars_status = dup.stars, dup.stars_status; filled.append("stars")
                if filled:
                    canonical.search_text = normalize_text(" ".join(filter(None, [canonical.search_text, dup.name_fa, dup.name_en])))
                    canonical.updated_at, canonical.updated_by = now, user.id
        match.decided_by, match.decided_at = user.id, now
        dup.updated_at, dup.updated_by = now, user.id
        audit(db, user, f"catalog_hotel.match_{match.status}", {"hotel_id": dup.id, "canonical_id": canonical.id, "basis": match.basis, "filled": filled})
        if filled: audit(db, user, "catalog_hotel.merged_fields", {"hotel_id": canonical.id, "from": dup.id, "filled": filled})
        db.commit()
        return full(db, dup)

    @router.post("/hotels/{hotel_id}/provider-mappings", status_code=201)
    def add_mapping(hotel_id: str, data: ProviderMappingIn, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        row = db.get(CatalogHotel, hotel_id)
        if row is None: raise HTTPException(status_code=404, detail="هتل پیدا نشد")
        if db.scalar(select(CatalogHotelProviderMapping.id).where(CatalogHotelProviderMapping.provider == data.provider, CatalogHotelProviderMapping.provider_hotel_id == data.provider_hotel_id)):
            raise HTTPException(status_code=409, detail="این شناسهٔ تأمین‌کننده قبلاً به هتل دیگری یا همین هتل نگاشت شده است")
        db.add(CatalogHotelProviderMapping(hotel_id=row.id, provider=data.provider, provider_hotel_id=data.provider_hotel_id, status="unverified"))
        audit(db, user, "catalog_hotel.provider_mapping_added", {"hotel_id": row.id, "provider": data.provider, "provider_hotel_id": data.provider_hotel_id})
        db.commit()
        return full(db, row)

    @router.post("/provider-mappings/{mapping_id}/verify")
    def verify_mapping(mapping_id: int, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        """States that this supplier hotel id was checked against the supplier's own record. Still no rate until a rate source is registered."""
        mapping = db.scalar(select(CatalogHotelProviderMapping).where(CatalogHotelProviderMapping.id == mapping_id).with_for_update())
        if mapping is None: raise HTTPException(status_code=404, detail="نگاشت پیدا نشد")
        mapping.status, mapping.verified_at, mapping.verified_by = "verified", datetime.now(timezone.utc), user.id
        audit(db, user, "catalog_hotel.provider_mapping_verified", {"hotel_id": mapping.hotel_id, "provider": mapping.provider, "provider_hotel_id": mapping.provider_hotel_id})
        db.commit()
        return full(db, db.get(CatalogHotel, mapping.hotel_id))

    def tour(row: CatalogTour, departures: list[CatalogTourDeparture]) -> dict:
        return {"description": row.description, "origin_place_id": row.origin_place_id, "destination_place_id": row.destination_place_id, "duration_nights": row.duration_nights, "duration_days": row.duration_days,
                "transport_mode": row.transport_mode, "board": row.board, "guide_included": row.guide_included, "transfer_included": row.transfer_included, "documents_required": row.documents_required,
                "cancellation_policy_text": row.cancellation_policy_text, "capacity": None, "supplier": None, "details": __import__("app.catalog", fromlist=["source_details"]).source_details(row),
                "id": row.id, "title": row.title_fa, "status": row.status, "source": row.source, "source_ref": row.source_ref, "source_disabled": row.source_disabled, "source_soldout": row.source_soldout,
                "sellable": False, "price": None, "departures_recorded": len(departures), "latest_departure": max((d.starts_on.isoformat() for d in departures if d.starts_on), default=None),
                "departures": [{"starts_jalali": d.starts_jalali, "ends_jalali": d.ends_jalali, "starts_on": d.starts_on.isoformat() if d.starts_on else None, "ends_on": d.ends_on.isoformat() if d.ends_on else None} for d in departures]}

    @router.get("/tours")
    def list_tours(q: str = "", offset: int = Query(default=0, ge=0), limit: int = Query(default=30, ge=1, le=100), user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        stmt = select(CatalogTour)
        for token in normalize_text(q).split()[:4]: stmt = stmt.where(CatalogTour.search_text.like(f"%{token}%"))
        total = db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = db.scalars(stmt.order_by(CatalogTour.id).offset(offset).limit(limit)).all()
        by_tour: dict[str, list] = {}
        for d in db.scalars(select(CatalogTourDeparture).where(CatalogTourDeparture.tour_id.in_({r.id for r in rows})).order_by(CatalogTourDeparture.source_row)): by_tour.setdefault(d.tour_id, []).append(d)
        return {"total": total, "items": [{k: v for k, v in tour(r, by_tour.get(r.id, [])).items() if k != "departures"} for r in rows]}

    @router.get("/tours/{tour_id}")
    def get_tour(tour_id: str, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        row = db.get(CatalogTour, tour_id)
        if row is None: raise HTTPException(status_code=404, detail="تور پیدا نشد")
        return tour_full(db, row)

    def tour_full(db: Session, row: CatalogTour) -> dict:
        data = tour(row, db.scalars(select(CatalogTourDeparture).where(CatalogTourDeparture.tour_id == row.id).order_by(CatalogTourDeparture.source_row)).all())
        data["itinerary"] = [{"day_no": d.day_no, "title": d.title, "description": d.description, "place_id": d.place_id} for d in db.scalars(select(CatalogTourItineraryDay).where(CatalogTourItineraryDay.tour_id == row.id).order_by(CatalogTourItineraryDay.day_no))]
        data["hotels"] = [{"hotel_id": h.hotel_id, "nights": h.nights} for h in db.scalars(select(CatalogTourHotel).where(CatalogTourHotel.tour_id == row.id).order_by(CatalogTourHotel.id))]
        data["options"] = {"transport": TOUR_TRANSPORT, "board": TOUR_BOARD}
        return data

    @router.put("/tours/{tour_id}")
    def save_tour(tour_id: str, data: TourIn, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        """Edits reference content only. There is no field here for price, capacity, supplier or a future departure."""
        row = db.scalar(select(CatalogTour).where(CatalogTour.id == tour_id).with_for_update())
        if row is None: raise HTTPException(status_code=404, detail="تور پیدا نشد")
        for key in ("origin_place_id", "destination_place_id"):
            if getattr(data, key) and db.get(CatalogPlace, getattr(data, key)) is None: raise HTTPException(status_code=422, detail="مبدأ یا مقصد در فهرست مرجع نیست")
        if any(d.place_id and db.get(CatalogPlace, d.place_id) is None for d in data.itinerary): raise HTTPException(status_code=422, detail="مکان برنامهٔ سفر در فهرست مرجع نیست")
        if len({d.day_no for d in data.itinerary}) != len(data.itinerary) or len({h.hotel_id for h in data.hotels}) != len(data.hotels): raise HTTPException(status_code=422, detail="روز یا هتل تکراری در تور")
        if any(db.get(CatalogHotel, h.hotel_id) is None for h in data.hotels): raise HTTPException(status_code=422, detail="هتل در فهرست مرجع نیست")
        if data.duration_nights is not None and data.duration_days is not None and not 0 <= data.duration_days - data.duration_nights <= 1: raise HTTPException(status_code=422, detail="تعداد شب و روز هم‌خوان نیست")
        if data.status == "published" and not (data.destination_place_id and data.itinerary): raise HTTPException(status_code=422, detail="برای انتشار، مقصد و برنامهٔ سفر لازم است")
        for key, value in data.model_dump(exclude={"itinerary", "hotels"}).items(): setattr(row, key, value)
        row.search_text, row.updated_at, row.updated_by = normalize_text(data.title_fa), datetime.now(timezone.utc), user.id
        db.execute(delete(CatalogTourItineraryDay).where(CatalogTourItineraryDay.tour_id == row.id)); db.execute(delete(CatalogTourHotel).where(CatalogTourHotel.tour_id == row.id))
        db.add_all([CatalogTourItineraryDay(tour_id=row.id, **d.model_dump()) for d in data.itinerary]); db.add_all([CatalogTourHotel(tour_id=row.id, **h.model_dump()) for h in data.hotels])
        audit(db, user, "catalog_tour.updated", {"tour_id": row.id, "status": data.status})
        db.commit()
        return tour_full(db, row)

    @router.post("/provider-mappings/{mapping_id}/rooms", status_code=201)
    def map_room(mapping_id: int, data: RoomMappingIn, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        mapping = db.get(CatalogHotelProviderMapping, mapping_id)
        room = db.get(CatalogHotelRoomType, data.room_type_id)
        if mapping is None: raise HTTPException(status_code=404, detail="نگاشت پیدا نشد")
        if room is None or room.hotel_id != mapping.hotel_id: raise HTTPException(status_code=422, detail="این نوع اتاق متعلق به همین هتل نیست")
        if db.scalar(select(CatalogHotelRoomMapping.id).where(CatalogHotelRoomMapping.mapping_id == mapping.id, CatalogHotelRoomMapping.provider_room_id == data.provider_room_id)): raise HTTPException(status_code=409, detail="این شناسهٔ اتاق قبلاً نگاشت شده است")
        row = CatalogHotelRoomMapping(mapping_id=mapping.id, room_type_id=room.id, provider_room_id=data.provider_room_id); db.add(row)
        audit(db, user, "catalog_hotel.room_mapping_added", {"hotel_id": mapping.hotel_id, "provider": mapping.provider, "provider_room_id": data.provider_room_id}); db.commit()
        return {"id": row.id, "mapping_id": mapping.id, "room_type_id": room.id, "provider_room_id": row.provider_room_id}

    @router.post("/provider-mappings/{mapping_id}/rate-plans", status_code=201)
    def map_rate_plan(mapping_id: int, data: RatePlanMappingIn, user=Depends(guard), db: Session = Depends(get_db)) -> dict:
        mapping = db.get(CatalogHotelProviderMapping, mapping_id)
        if mapping is None: raise HTTPException(status_code=404, detail="نگاشت پیدا نشد")
        if db.scalar(select(CatalogHotelRatePlanMapping.id).where(CatalogHotelRatePlanMapping.mapping_id == mapping.id, CatalogHotelRatePlanMapping.provider_rate_plan_id == data.provider_rate_plan_id)): raise HTTPException(status_code=409, detail="این طرح نرخ قبلاً نگاشت شده است")
        row = CatalogHotelRatePlanMapping(mapping_id=mapping.id, **data.model_dump()); db.add(row)
        audit(db, user, "catalog_hotel.rate_plan_mapping_added", {"hotel_id": mapping.hotel_id, "provider": mapping.provider, "provider_rate_plan_id": data.provider_rate_plan_id}); db.commit()
        return {"id": row.id, "mapping_id": mapping.id, "provider_rate_plan_id": row.provider_rate_plan_id, "board": row.board, "refundable": row.refundable, "amount": None}

    return router
