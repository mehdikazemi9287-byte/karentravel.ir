"""Master/catalog data: real, relatively static reference records shared by all tenants.

Strictly separated from commercial data: nothing here carries a price, offer, availability,
inventory, seat or review. Supplier offers attach later by catalog id.
Hotel content (room *types*, policies, licensed images) is descriptive only: it never implies a
rate or free room. Tables are global (no tenant_id); the API role may edit hotel content only
through the audited admin endpoints in catalog_admin.py (ADR-028 addendum).
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base

PRICE_NOTE_FA = "قیمت پس از انتخاب تاریخ و استعلام"
VENUE_PRICE_NOTE_FA = "قیمت پس از استعلام"
HOTEL_TYPES = {"hotel": "هتل", "motel": "متل", "guest_house": "مهمان‌پذیر و اقامتگاه", "hostel": "هاستل", "apartment": "هتل‌آپارتمان و سوئیت", "chalet": "ویلا و کلبه", "resort": "ریزورت"}
AMENITIES = {"wifi": "اینترنت", "parking": "پارکینگ", "pool": "استخر", "restaurant": "رستوران", "bar": "کافه/بار", "air_conditioning": "تهویه مطبوع", "accessible": "دسترسی ویلچر", "breakfast": "صبحانه", "spa": "اسپا", "fitness": "سالن ورزش", "pets": "پذیرش حیوان خانگی",
             "elevator": "آسانسور", "reception_24h": "پذیرش ۲۴ ساعته", "room_service": "سرویس اتاق", "laundry": "خشک‌شویی", "airport_shuttle": "ترانسفر فرودگاهی",
             "family_rooms": "اتاق خانوادگی", "non_smoking_rooms": "اتاق‌های غیرسیگاری", "safe": "گاوصندوق", "minibar": "یخچال/مینی‌بار", "tv": "تلویزیون",
             "kitchen": "آشپزخانه", "meeting_room": "سالن جلسات", "prayer_room": "نمازخانه", "currency_exchange": "صرافی", "tour_desk": "میز تور"}
POLICY_VALUES = {"allowed": "مجاز", "not_allowed": "غیرمجاز", "on_request": "با هماهنگی"}
POLICY_FIELDS = {"children_policy": "پذیرش کودک", "pets_policy": "حیوان خانگی", "smoking_policy": "استعمال دخانیات"}
BED_TYPES = {"single": "یک‌تخته", "double": "دوتخته دبل", "twin": "دوتخته توئین", "triple": "سه‌تخته", "quad": "چهارتخته", "family": "خانوادگی", "suite": "سوئیت", "apartment": "آپارتمان"}
ROOM_VIEWS = {"city": "شهر", "sea": "دریا", "garden": "باغ", "mountain": "کوه", "courtyard": "حیاط", "none": "بدون منظره"}
STARS_STATUS = {"source_reported": "اعلام‌شده توسط منبع", "verified": "تأییدشده با منبع رسمی"}
HOTEL_STATUS = {"draft": "پیش‌نویس", "published": "منتشرشده", "hidden": "پنهان"}
VENUE_KINDS = {"restaurant": "رستوران", "cafe": "کافه", "attraction": "جاذبه گردشگری", "museum": "موزه", "historic": "بنای تاریخی", "pool_sport": "استخر و ورزش", "event_venue": "تالار و رویداد", "car_rental": "اجاره خودرو", "handicraft": "صنایع‌دستی", "travel_agency": "آژانس و تور", "tourist_info": "راهنمای گردشگری", "transport_terminal": "پایانه حمل‌ونقل"}
_ARABIC_MAP = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا", "آ": "ا", "ؤ": "و", "‌": " ", "‏": "", "ـ": ""})


def normalize_text(value: Optional[str]) -> str:
    """Fold Persian/Arabic variants, diacritics, case and punctuation for matching."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value).translate(_ARABIC_MAP)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


class SourceMixin:
    source: Mapped[str] = mapped_column(String(40), default="")
    source_ref: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source_license: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    retrieved_on: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)


class CatalogPlace(SourceMixin, Base):
    __tablename__ = "catalog_places"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # country | region | city
    parent_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_places.id"), nullable=True, index=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    name_fa: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    name_local: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    population: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_credit: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    wikidata_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    hotel_count: Mapped[int] = mapped_column(Integer, default=0)
    search_text: Mapped[str] = mapped_column(Text, default="")


class CatalogHotel(SourceMixin, Base):
    __tablename__ = "catalog_hotels"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    region_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_places.id"), nullable=True, index=True)
    city_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_places.id"), nullable=True, index=True)
    name_fa: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    name_local: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hotel_type: Mapped[str] = mapped_column(String(24), index=True)
    stars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    address: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # unknown stays null; never a city centroid
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    amenities_json: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checkin_time: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    checkout_time: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_credit: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    wikidata_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    quality: Mapped[int] = mapped_column(Integer, default=0, index=True)  # completeness score, used only for ordering
    search_text: Mapped[str] = mapped_column(Text, default="")
    rules_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    children_policy: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    pets_policy: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    smoking_policy: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    stars_status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="published", server_default="published", index=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # set => admin-owned; bulk importers never overwrite
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # only an explicit reviewer action sets this
    content_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    duplicate_of: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_hotels.id"), nullable=True, index=True)  # set => never public; canonical record wins
    match_basis: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    __table_args__ = (Index("ix_catalog_hotels_country_city", "country_code", "city_id"),)


class CatalogHotelImage(Base):
    __tablename__ = "catalog_hotel_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[str] = mapped_column(ForeignKey("catalog_hotels.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    caption: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    license: Mapped[str] = mapped_column(String(80))  # required: no licence, no image
    license_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    source_url: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CatalogHotelRoomType(Base):
    """Descriptive room type (bedding, occupancy, view). Never a rate, allotment or free room."""
    __tablename__ = "catalog_hotel_room_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[str] = mapped_column(ForeignKey("catalog_hotels.id", ondelete="CASCADE"), index=True)
    name_fa: Mapped[str] = mapped_column(String(160))
    name_en: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    bed_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    max_adults: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_children: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    size_m2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    view: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    amenities_json: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CatalogAirline(SourceMixin, Base):
    __tablename__ = "catalog_airlines"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    iata_code: Mapped[str] = mapped_column(String(3), index=True)
    icao_code: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    name_fa: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    airline_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    logo_credit: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    search_text: Mapped[str] = mapped_column(Text, default="")


class CatalogAirport(SourceMixin, Base):
    __tablename__ = "catalog_airports"
    id: Mapped[str] = mapped_column(String(3), primary_key=True)  # IATA code
    icao_code: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    name_fa: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    name_en: Mapped[str] = mapped_column(String(200))
    city_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_places.id"), nullable=True, index=True)
    city_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # international | None when not established
    airport_type: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    scheduled_service: Mapped[Optional[bool]] = mapped_column(nullable=True)
    search_text: Mapped[str] = mapped_column(Text, default="")


class CatalogRailOperator(SourceMixin, Base):
    __tablename__ = "catalog_rail_operators"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name_fa: Mapped[str] = mapped_column(String(160))
    name_en: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    operator_kind: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    brands_json: Mapped[str] = mapped_column(Text, default="[]")
    website: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IR")


class CatalogRailStation(SourceMixin, Base):
    __tablename__ = "catalog_rail_stations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name_fa: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    region_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_places.id"), nullable=True, index=True)
    city_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_places.id"), nullable=True, index=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IR")
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    search_text: Mapped[str] = mapped_column(Text, default="")


class CatalogVenue(SourceMixin, Base):
    __tablename__ = "catalog_venues"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    name_fa: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IR")
    region_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_places.id"), nullable=True, index=True)
    city_id: Mapped[Optional[str]] = mapped_column(ForeignKey("catalog_places.id"), nullable=True, index=True)
    address: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    phone: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    opening_hours: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # cuisine, sport, craft… as published by the source
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_credit: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    wikidata_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    quality: Mapped[int] = mapped_column(Integer, default=0)
    search_text: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (Index("ix_catalog_venues_kind_city", "kind", "city_id"),)


class CatalogHotelMatch(Base):
    """A possible duplicate pair. Name similarity alone only ever yields status=proposed (human decision)."""
    __tablename__ = "catalog_hotel_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[str] = mapped_column(ForeignKey("catalog_hotels.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("catalog_hotels.id", ondelete="CASCADE"), index=True)
    basis: Mapped[str] = mapped_column(String(40))  # name+city | name+city+address
    status: Mapped[str] = mapped_column(String(16), default="proposed", index=True)  # proposed | confirmed | rejected
    decided_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # null => rule-based decision
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ux_catalog_hotel_matches_pair", "hotel_id", "candidate_id", unique=True),)


class CatalogHotelProviderMapping(Base):
    """Links a catalog hotel to a supplier's own hotel id. Only a verified mapping may ever feed rates; none is guessed."""
    __tablename__ = "catalog_hotel_provider_mappings"
    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[str] = mapped_column(ForeignKey("catalog_hotels.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    provider_hotel_id: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="unverified")  # unverified | verified
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    __table_args__ = (Index("ux_catalog_hotel_provider_mappings", "provider", "provider_hotel_id", unique=True),)


class CatalogTour(SourceMixin, Base):
    """Reference description of a tour that was offered. Not a product: no price, capacity, supplier or tenant."""
    __tablename__ = "catalog_tours"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title_fa: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)  # draft | published | hidden
    source_disabled: Mapped[bool] = mapped_column(Boolean, default=False)  # flags exactly as the source had them
    source_soldout: Mapped[bool] = mapped_column(Boolean, default=False)
    search_text: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class CatalogTourDeparture(Base):
    """A date the source recorded for a tour. History/reference only; a sellable departure lives in tour_departures."""
    __tablename__ = "catalog_tour_departures"
    id: Mapped[int] = mapped_column(primary_key=True)
    tour_id: Mapped[str] = mapped_column(ForeignKey("catalog_tours.id", ondelete="CASCADE"), index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    starts_jalali: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # verbatim source text
    ends_jalali: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    starts_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)  # only when the text is a valid calendar date
    ends_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    __table_args__ = (Index("ux_catalog_tour_departures_row", "tour_id", "source_row", unique=True),)


CATALOG_TABLES = tuple(m.__table__ for m in (CatalogPlace, CatalogHotel, CatalogAirline, CatalogAirport, CatalogRailOperator, CatalogRailStation, CatalogVenue))
HOTEL_CONTENT_TABLES = (CatalogHotelImage.__table__, CatalogHotelRoomType.__table__)
HOTEL_LINK_TABLES = (CatalogHotelMatch.__table__, CatalogHotelProviderMapping.__table__)
TOUR_TABLES = (CatalogTour.__table__, CatalogTourDeparture.__table__)
CATALOG_MODELS = {"places": CatalogPlace, "hotels": CatalogHotel, "airlines": CatalogAirline, "airports": CatalogAirport, "rail_operators": CatalogRailOperator, "rail_stations": CatalogRailStation, "venues": CatalogVenue}


def _place(row: Optional[CatalogPlace]) -> Optional[dict]:
    if row is None:
        return None
    return {"id": row.id, "kind": row.kind, "parent_id": row.parent_id, "country_code": row.country_code, "name_fa": row.name_fa, "name_en": row.name_en,
            "name": row.name_fa or row.name_en or row.name_local, "latitude": row.latitude, "longitude": row.longitude, "population": row.population,
            "description": row.description, "image_url": row.image_url, "image_credit": row.image_credit, "hotel_count": row.hotel_count}


BOOKING_FROM_CATALOG_ENABLED = False  # flips only with an approved booking flow for supplier-quoted catalog hotels


def hotel_state(row: CatalogHotel, rateable: bool = False) -> dict:
    """Explicit lifecycle flags. rate_available means a live rate can be requested (verified provider mapping to a
    registered rate source, see hotel_rates.py); it is never assumed. bookable additionally needs the booking flow."""
    published = row.status == "published" and row.duplicate_of is None
    return {"catalogued": True, "content_complete": bool(row.content_complete), "rate_available": bool(rateable and published), "bookable": bool(rateable and published and BOOKING_FROM_CATALOG_ENABLED), "published": published,
            "source": row.source, "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None}


def content_is_complete(row: CatalogHotel, images: int, room_types: int) -> bool:
    return bool((row.name_fa or row.name_en) and row.city_id and row.address and row.description and row.checkin_time and row.checkout_time and images and room_types
                and json.loads(row.amenities_json or "[]"))


def _provenance(row) -> dict:
    return {"source": row.source, "source_ref": row.source_ref, "license": row.source_license, "retrieved_on": row.retrieved_on}


def _hotel(row: CatalogHotel, places: dict[str, CatalogPlace], full: bool = False, rateable: bool = False) -> dict:
    city, region = places.get(row.city_id or ""), places.get(row.region_id or "")
    data = {"id": row.id, "slug": row.slug, "name": row.name_fa or row.name_en or row.name_local, "name_fa": row.name_fa, "name_en": row.name_en, "name_local": row.name_local,
            "hotel_type": row.hotel_type, "hotel_type_fa": HOTEL_TYPES.get(row.hotel_type, row.hotel_type), "stars": row.stars, "country_code": row.country_code,
            "city": _brief(city), "region": _brief(region), "address": row.address, "latitude": row.latitude, "longitude": row.longitude,
            "amenities": [{"key": a, "label": AMENITIES.get(a, a)} for a in json.loads(row.amenities_json or "[]")],
            "image_url": row.image_url, "image_credit": row.image_credit,
            # Commercial data is deliberately absent until a real supplier offer is mapped to this record.
            "price": None, "price_status": "inquiry", "price_note": PRICE_NOTE_FA, "state": hotel_state(row, rateable)}
    if full:
        data.update({"description": row.description, "checkin_time": row.checkin_time, "checkout_time": row.checkout_time, "phone": row.phone, "website": row.website,
                     "email": row.email, "provenance": _provenance(row), "rules_text": row.rules_text, "stars_status": row.stars_status,
                     "stars_status_fa": STARS_STATUS.get(row.stars_status or ""),
                     "policies": [{"key": k, "label": label, "value": getattr(row, k), "value_fa": POLICY_VALUES[getattr(row, k)]} for k, label in POLICY_FIELDS.items() if getattr(row, k) in POLICY_VALUES]})
    return data


def hotel_image(i: CatalogHotelImage) -> dict:
    return {"id": i.id, "url": i.url, "caption": i.caption, "author": i.author, "license": i.license, "license_url": i.license_url, "source_url": i.source_url, "sort_order": i.sort_order}


def room_type(r: CatalogHotelRoomType) -> dict:
    return {"id": r.id, "name_fa": r.name_fa, "name_en": r.name_en, "bed_type": r.bed_type, "bed_type_fa": BED_TYPES.get(r.bed_type or ""), "max_adults": r.max_adults,
            "max_children": r.max_children, "size_m2": r.size_m2, "view": r.view, "view_fa": ROOM_VIEWS.get(r.view or ""), "description": r.description, "sort_order": r.sort_order,
            "amenities": [{"key": a, "label": AMENITIES.get(a, a)} for a in json.loads(r.amenities_json or "[]")]}


def _brief(place: Optional[CatalogPlace]) -> Optional[dict]:
    return None if place is None else {"id": place.id, "name": place.name_fa or place.name_en or place.name_local, "name_en": place.name_en}


def _places_for(db: Session, ids: set) -> dict[str, CatalogPlace]:
    ids = {i for i in ids if i}
    return {p.id: p for p in db.scalars(select(CatalogPlace).where(CatalogPlace.id.in_(ids)))} if ids else {}


def _venue(row: CatalogVenue, places: dict[str, CatalogPlace]) -> dict:
    return {"id": row.id, "kind": row.kind, "kind_fa": VENUE_KINDS.get(row.kind, row.kind), "name": row.name_fa or row.name_en, "name_fa": row.name_fa, "name_en": row.name_en,
            "city": _brief(places.get(row.city_id or "")), "region": _brief(places.get(row.region_id or "")), "address": row.address, "latitude": row.latitude,
            "longitude": row.longitude, "phone": row.phone, "website": row.website, "opening_hours": row.opening_hours, "detail": row.detail, "description": row.description,
            "image_url": row.image_url, "image_credit": row.image_credit, "price": None, "price_status": "inquiry", "price_note": VENUE_PRICE_NOTE_FA, "provenance": _provenance(row)}


def _like(column, q: str):
    return column.like(f"%{normalize_text(q)}%")


def catalog_router(get_db) -> APIRouter:
    router = APIRouter(prefix="/catalog", tags=["catalog"])

    def cached(response: Response) -> None:
        response.headers["Cache-Control"] = "public, max-age=300"

    @router.get("/summary")
    def summary(response: Response, db: Session = Depends(get_db)) -> dict:
        cached(response)
        counts = {name: db.scalar(select(func.count()).select_from(model)) for name, model in CATALOG_MODELS.items()}
        by_country = dict(db.execute(select(CatalogHotel.country_code, func.count()).group_by(CatalogHotel.country_code)).all())
        by_kind = dict(db.execute(select(CatalogVenue.kind, func.count()).group_by(CatalogVenue.kind)).all())
        return {"counts": counts, "hotels_by_country": by_country, "venues_by_kind": by_kind, "commercial_data": False}

    @router.get("/places")
    def places(response: Response, kind: Optional[str] = None, country: Optional[str] = None, parent: Optional[str] = None, q: Optional[str] = None,
               with_hotels: bool = False, with_image: bool = False, limit: int = Query(default=60, ge=1, le=500), db: Session = Depends(get_db)) -> dict:
        cached(response)
        stmt = select(CatalogPlace)
        if kind: stmt = stmt.where(CatalogPlace.kind == kind)
        if country: stmt = stmt.where(CatalogPlace.country_code == country.upper())
        if parent: stmt = stmt.where(CatalogPlace.parent_id == parent)
        if with_hotels: stmt = stmt.where(CatalogPlace.hotel_count > 0)
        if with_image: stmt = stmt.where(CatalogPlace.image_url.is_not(None))
        if q and normalize_text(q): stmt = stmt.where(_like(CatalogPlace.search_text, q))
        rows = db.scalars(stmt.order_by(CatalogPlace.hotel_count.desc(), CatalogPlace.population.desc().nulls_last(), CatalogPlace.id).limit(limit)).all()
        return {"items": [_place(r) for r in rows]}

    @router.get("/places/{place_id}")
    def place_detail(place_id: str, response: Response, db: Session = Depends(get_db)) -> dict:
        cached(response)
        row = db.get(CatalogPlace, place_id)
        if row is None:
            raise HTTPException(status_code=404, detail="مقصد پیدا نشد")
        scope = CatalogHotel.city_id if row.kind == "city" else CatalogHotel.region_id if row.kind == "region" else None
        airport_filter = CatalogAirport.city_id == row.id if row.kind == "city" else CatalogAirport.country_code == row.country_code
        airports = db.scalars(select(CatalogAirport).where(airport_filter).order_by(CatalogAirport.airport_type, CatalogAirport.id).limit(12)).all() if row.kind != "region" else []
        stations = db.scalars(select(CatalogRailStation).where((CatalogRailStation.city_id if row.kind == "city" else CatalogRailStation.region_id) == row.id).limit(12)).all() if row.kind != "country" else []
        venue_scope = CatalogVenue.city_id if row.kind == "city" else CatalogVenue.region_id
        venue_counts = dict(db.execute(select(CatalogVenue.kind, func.count()).where(venue_scope == row.id).group_by(CatalogVenue.kind)).all()) if row.kind != "country" else {}
        children = db.scalars(select(CatalogPlace).where(CatalogPlace.parent_id == row.id).order_by(CatalogPlace.hotel_count.desc(), CatalogPlace.population.desc().nulls_last()).limit(40)).all()
        return {**_place(row), "parent": _place(db.get(CatalogPlace, row.parent_id)) if row.parent_id else None, "children": [_place(c) for c in children],
                "hotels": row.hotel_count if scope is not None else db.scalar(select(func.count()).select_from(CatalogHotel).where(CatalogHotel.country_code == row.country_code)),
                "airports": [_airport(a) for a in airports], "rail_stations": [_station(s) for s in stations], "venue_counts": venue_counts, "provenance": _provenance(row)}

    def hotel_filters(stmt, country, region, city, stars, hotel_type, amenity, q, has_image, policy=None):
        stmt = stmt.where(CatalogHotel.status == "published", CatalogHotel.duplicate_of.is_(None))
        for item in (policy or "").split(","):  # e.g. pets_policy:allowed
            key, _, value = item.partition(":")
            if key in POLICY_FIELDS and value in POLICY_VALUES: stmt = stmt.where(getattr(CatalogHotel, key) == value)
        if country: stmt = stmt.where(CatalogHotel.country_code == country.upper())
        if region: stmt = stmt.where(CatalogHotel.region_id == region)
        if city: stmt = stmt.where(CatalogHotel.city_id == city)
        if stars: stmt = stmt.where(CatalogHotel.stars == stars)
        if hotel_type: stmt = stmt.where(CatalogHotel.hotel_type.in_(hotel_type.split(",")))
        if amenity:
            for key in amenity.split(","):
                if key in AMENITIES: stmt = stmt.where(CatalogHotel.amenities_json.like(f'%"{key}"%'))
        if has_image: stmt = stmt.where(CatalogHotel.image_url.is_not(None))
        if q and normalize_text(q):
            for token in normalize_text(q).split()[:4]:
                if token not in ("هتل", "hotel"): stmt = stmt.where(CatalogHotel.search_text.like(f"%{token}%"))
        return stmt

    @router.get("/hotels")
    def hotels(response: Response, country: Optional[str] = None, region: Optional[str] = None, city: Optional[str] = None, stars: Optional[int] = Query(default=None, ge=1, le=5),
               hotel_type: Optional[str] = None, amenity: Optional[str] = None, q: Optional[str] = None, has_image: bool = False, policy: Optional[str] = None,
               offset: int = Query(default=0, ge=0), limit: int = Query(default=24, ge=1, le=60), db: Session = Depends(get_db)) -> dict:
        cached(response)
        base = hotel_filters(select(CatalogHotel), country, region, city, stars, hotel_type, amenity, q, has_image, policy)
        total = db.scalar(select(func.count()).select_from(base.subquery()))
        rows = db.scalars(base.order_by(CatalogHotel.quality.desc(), CatalogHotel.id).offset(offset).limit(limit)).all()
        places_map = _places_for(db, {r.city_id for r in rows} | {r.region_id for r in rows})
        from .hotel_rates import rateable_hotel_ids
        rateable = rateable_hotel_ids(db, {r.id for r in rows})
        return {"total": total, "offset": offset, "limit": limit, "items": [_hotel(r, places_map, rateable=r.id in rateable) for r in rows], "price_status": "inquiry", "price_note": PRICE_NOTE_FA}

    @router.get("/hotels/facets")
    def hotel_facets(response: Response, country: Optional[str] = None, city: Optional[str] = None, db: Session = Depends(get_db)) -> dict:
        cached(response)
        countries = db.execute(select(CatalogHotel.country_code, func.count()).where(CatalogHotel.status == "published", CatalogHotel.duplicate_of.is_(None)).group_by(CatalogHotel.country_code).order_by(func.count().desc())).all()
        country_places = _places_for(db, {c.lower() for c, _ in countries})
        scoped = hotel_filters(select(CatalogHotel), country, None, city, None, None, None, None, False).subquery()
        city_rows = db.execute(select(scoped.c.city_id, func.count()).where(scoped.c.city_id.is_not(None)).group_by(scoped.c.city_id).order_by(func.count().desc()).limit(80)).all() if not city else []
        city_places = _places_for(db, {c for c, _ in city_rows})
        stars = db.execute(select(scoped.c.stars, func.count()).where(scoped.c.stars.is_not(None)).group_by(scoped.c.stars).order_by(scoped.c.stars.desc())).all()
        types = db.execute(select(scoped.c.hotel_type, func.count()).group_by(scoped.c.hotel_type).order_by(func.count().desc())).all()
        amenities = [{"key": key, "label": label, "count": db.scalar(select(func.count()).select_from(scoped).where(scoped.c.amenities_json.like(f'%"{key}"%')))} for key, label in AMENITIES.items()]
        return {"countries": [{"code": c, "name": (country_places.get(c.lower()).name_fa if country_places.get(c.lower()) else c), "count": n} for c, n in countries],
                "cities": [{"id": c, "name": city_places[c].name_fa or city_places[c].name_en, "count": n} for c, n in city_rows if c in city_places],
                "stars": [{"value": s, "count": n} for s, n in stars], "types": [{"key": t, "label": HOTEL_TYPES.get(t, t), "count": n} for t, n in types],
                "amenities": [a for a in amenities if a["count"]],
                "policies": [{"key": f"{k}:{v}", "label": f"{label}: {vfa}", "count": n} for k, label in POLICY_FIELDS.items() for v, vfa in POLICY_VALUES.items()
                             for n in [db.scalar(select(func.count()).select_from(scoped).where(getattr(scoped.c, k) == v))] if n]}

    @router.get("/hotels/{slug}")
    def hotel_detail(slug: str, response: Response, db: Session = Depends(get_db)) -> dict:
        cached(response)
        row = db.scalar(select(CatalogHotel).where(or_(CatalogHotel.slug == slug, CatalogHotel.id == slug), CatalogHotel.status == "published", CatalogHotel.duplicate_of.is_(None)))
        if row is None:
            raise HTTPException(status_code=404, detail="هتل پیدا نشد")
        places_map = _places_for(db, {row.city_id, row.region_id, row.country_code.lower()})
        from .hotel_rates import rateable_hotel_ids
        data = _hotel(row, places_map, full=True, rateable=bool(rateable_hotel_ids(db, {row.id})))
        data["country"] = _brief(places_map.get(row.country_code.lower()))
        data["images"] = [hotel_image(i) for i in db.scalars(select(CatalogHotelImage).where(CatalogHotelImage.hotel_id == row.id).order_by(CatalogHotelImage.sort_order, CatalogHotelImage.id))]
        data["room_types"] = [room_type(r) for r in db.scalars(select(CatalogHotelRoomType).where(CatalogHotelRoomType.hotel_id == row.id).order_by(CatalogHotelRoomType.sort_order, CatalogHotelRoomType.id))]
        if row.city_id:
            data["nearby_airports"] = [_airport(a) for a in db.scalars(select(CatalogAirport).where(CatalogAirport.city_id == row.city_id).limit(4))]
            data["nearby_rail_stations"] = [_station(s) for s in db.scalars(select(CatalogRailStation).where(CatalogRailStation.city_id == row.city_id).limit(4))]
        return data

    @router.get("/hotels/{slug}/rates")
    def hotel_rates(slug: str, checkin: date, checkout: date, adults: int = Query(default=2, ge=1, le=12), children: int = Query(default=0, ge=0, le=8), db: Session = Depends(get_db)) -> dict:
        """Live supplier quote for concrete dates. Never cached, never defaulted: without a rate source the answer says so."""
        row = db.scalar(select(CatalogHotel).where(or_(CatalogHotel.slug == slug, CatalogHotel.id == slug), CatalogHotel.status == "published", CatalogHotel.duplicate_of.is_(None)))
        if row is None:
            raise HTTPException(status_code=404, detail="هتل پیدا نشد")
        if checkout <= checkin or (checkout - checkin).days > 30:
            raise HTTPException(status_code=422, detail="بازهٔ اقامت نامعتبر است")
        from .hotel_rates import quote_hotel
        return {"hotel_id": row.id, "checkin": checkin.isoformat(), "checkout": checkout.isoformat(), **quote_hotel(db, row, checkin, checkout, adults, children)}

    def _airport(a: CatalogAirport) -> dict:
        return {"iata": a.id, "icao": a.icao_code, "name": a.name_fa or a.name_en, "name_fa": a.name_fa, "name_en": a.name_en, "city_id": a.city_id, "city_name": a.city_name,
                "country_code": a.country_code, "latitude": a.latitude, "longitude": a.longitude, "timezone": a.timezone, "scope": a.scope, "airport_type": a.airport_type,
                "scheduled_service": a.scheduled_service, "provenance": _provenance(a)}

    def _station(s: CatalogRailStation) -> dict:
        return {"id": s.id, "name": s.name_fa or s.name_en, "name_fa": s.name_fa, "name_en": s.name_en, "city_id": s.city_id, "region_id": s.region_id,
                "latitude": s.latitude, "longitude": s.longitude, "provenance": _provenance(s)}

    @router.get("/airlines")
    def airlines(response: Response, country: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db)) -> dict:
        cached(response)
        stmt = select(CatalogAirline)
        if country: stmt = stmt.where(CatalogAirline.country_code == country.upper())
        if q and normalize_text(q): stmt = stmt.where(_like(CatalogAirline.search_text, q))
        rows = db.scalars(stmt.order_by(CatalogAirline.country_code != "IR", CatalogAirline.name_en)).all()
        return {"items": [{"id": r.id, "iata": r.iata_code, "icao": r.icao_code, "name": r.name_fa or r.name_en, "name_fa": r.name_fa, "name_en": r.name_en, "country_code": r.country_code,
                           "airline_type": r.airline_type, "website": r.website, "logo_url": r.logo_url, "logo_credit": r.logo_credit, "provenance": _provenance(r)} for r in rows]}

    @router.get("/airports")
    def airports(response: Response, country: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db)) -> dict:
        cached(response)
        stmt = select(CatalogAirport)
        if country: stmt = stmt.where(CatalogAirport.country_code == country.upper())
        if q and normalize_text(q): stmt = stmt.where(_like(CatalogAirport.search_text, q))
        return {"items": [_airport(a) for a in db.scalars(stmt.order_by(CatalogAirport.country_code != "IR", CatalogAirport.airport_type, CatalogAirport.id))]}

    @router.get("/rail/operators")
    def rail_operators(response: Response, db: Session = Depends(get_db)) -> dict:
        cached(response)
        return {"items": [{"id": r.id, "name_fa": r.name_fa, "name_en": r.name_en, "operator_kind": r.operator_kind, "brands": json.loads(r.brands_json or "[]"), "website": r.website,
                           "provenance": _provenance(r)} for r in db.scalars(select(CatalogRailOperator).order_by(CatalogRailOperator.name_fa))]}

    @router.get("/rail/stations")
    def rail_stations(response: Response, region: Optional[str] = None, q: Optional[str] = None, limit: int = Query(default=500, ge=1, le=1000), db: Session = Depends(get_db)) -> dict:
        cached(response)
        stmt = select(CatalogRailStation)
        if region: stmt = stmt.where(CatalogRailStation.region_id == region)
        if q and normalize_text(q): stmt = stmt.where(_like(CatalogRailStation.search_text, q))
        return {"items": [_station(s) for s in db.scalars(stmt.order_by(CatalogRailStation.name_fa).limit(limit))]}

    def venue_filters(stmt, kind, region, city, q):
        if kind: stmt = stmt.where(CatalogVenue.kind.in_(kind.split(",")))
        if region: stmt = stmt.where(CatalogVenue.region_id == region)
        if city: stmt = stmt.where(CatalogVenue.city_id == city)
        if q and normalize_text(q): stmt = stmt.where(_like(CatalogVenue.search_text, q))
        return stmt

    @router.get("/venues")
    def venues(response: Response, kind: Optional[str] = None, region: Optional[str] = None, city: Optional[str] = None, q: Optional[str] = None,
               offset: int = Query(default=0, ge=0), limit: int = Query(default=24, ge=1, le=60), db: Session = Depends(get_db)) -> dict:
        cached(response)
        base = venue_filters(select(CatalogVenue), kind, region, city, q)
        total = db.scalar(select(func.count()).select_from(base.subquery()))
        rows = db.scalars(base.order_by(CatalogVenue.quality.desc(), CatalogVenue.id).offset(offset).limit(limit)).all()
        places_map = _places_for(db, {r.city_id for r in rows} | {r.region_id for r in rows})
        return {"total": total, "offset": offset, "limit": limit, "items": [_venue(r, places_map) for r in rows], "price_status": "inquiry", "price_note": VENUE_PRICE_NOTE_FA}

    @router.get("/venues/facets")
    def venue_facets(response: Response, kind: Optional[str] = None, db: Session = Depends(get_db)) -> dict:
        cached(response)
        scoped = venue_filters(select(CatalogVenue), kind, None, None, None).subquery()
        rows = db.execute(select(scoped.c.city_id, func.count()).where(scoped.c.city_id.is_not(None)).group_by(scoped.c.city_id).order_by(func.count().desc()).limit(60)).all()
        places_map = _places_for(db, {c for c, _ in rows})
        return {"cities": [{"id": c, "name": places_map[c].name_fa or places_map[c].name_en, "count": n} for c, n in rows if c in places_map]}

    @router.get("/venues/{venue_id}")
    def venue_detail(venue_id: str, response: Response, db: Session = Depends(get_db)) -> dict:
        cached(response)
        row = db.get(CatalogVenue, venue_id)
        if row is None:
            raise HTTPException(status_code=404, detail="مورد پیدا نشد")
        return _venue(row, _places_for(db, {row.city_id, row.region_id}))

    @router.get("/suggest")
    def suggest(q: str, response: Response, db: Session = Depends(get_db)) -> dict:
        """Destination, airport and hotel suggestions from master data only (no tenant or commercial data)."""
        cached(response)
        norm = normalize_text(q)
        tokens = [t for t in norm.split() if t not in ("هتل", "hotel")] or norm.split()
        if len(norm) < 2:
            raise HTTPException(status_code=422, detail="حداقل دو نویسه برای پیشنهاد لازم است")
        term = " ".join(tokens)
        candidates = db.scalars(select(CatalogPlace).where(CatalogPlace.search_text.like(f"%{term}%")).order_by(CatalogPlace.hotel_count.desc(), CatalogPlace.population.desc().nulls_last()).limit(60)).all()

        def rank(p: CatalogPlace) -> int:  # exact name, then prefix, then whole word, then substring («وان» must not rank «ایروان» first)
            names_norm = [normalize_text(n) for n in (p.name_fa, p.name_en, p.name_local) if n]
            if term in names_norm: return 0
            if any(n.startswith(term) for n in names_norm): return 1
            return 2 if term in p.search_text.split() or f" {term} " in f" {p.search_text} " else 3
        place_rows = sorted(candidates, key=rank)[:6]
        airport_rows = db.scalars(select(CatalogAirport).where(or_(CatalogAirport.search_text.like(f"%{term}%"), CatalogAirport.id == term.upper())).limit(4)).all()
        hotel_stmt = select(CatalogHotel).where(CatalogHotel.status == "published", CatalogHotel.duplicate_of.is_(None))
        for token in tokens[:4]:
            hotel_stmt = hotel_stmt.where(CatalogHotel.search_text.like(f"%{token}%"))
        hotel_rows = db.scalars(hotel_stmt.order_by(CatalogHotel.quality.desc()).limit(6)).all()
        places_map = _places_for(db, {h.city_id for h in hotel_rows} | {p.parent_id for p in place_rows})
        country_names = {p.id: p.name_fa for p in db.scalars(select(CatalogPlace).where(CatalogPlace.kind == "country"))}
        items = [{"type": p.kind, "id": p.id, "title": p.name_fa or p.name_en, "subtitle": " · ".join(filter(None, [(places_map.get(p.parent_id).name_fa if places_map.get(p.parent_id) and p.kind == "city" else None), country_names.get(p.country_code.lower()) if p.kind != "country" else None])),
                  "name_en": p.name_en, "country_code": p.country_code, "hotel_count": p.hotel_count, "href": f"/hotels?{'city' if p.kind == 'city' else 'region' if p.kind == 'region' else 'country'}={p.id if p.kind != 'country' else p.country_code}"} for p in place_rows]
        items += [{"type": "airport", "id": a.id, "title": a.name_fa or a.name_en, "subtitle": f"{a.id} · {a.city_name or ''}".strip(" ·"), "name_en": a.name_en, "country_code": a.country_code, "city_id": a.city_id} for a in airport_rows]
        items += [{"type": "hotel", "id": h.id, "title": h.name_fa or h.name_en or h.name_local, "subtitle": (places_map[h.city_id].name_fa or places_map[h.city_id].name_en) if h.city_id in places_map else "", "name_en": h.name_en,
                   "country_code": h.country_code, "href": f"/hotels/{h.slug}"} for h in hotel_rows]
        return {"query": q, "items": items, "commercial_data": False}

    return router
