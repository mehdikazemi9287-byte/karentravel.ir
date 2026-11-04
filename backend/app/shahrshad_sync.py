"""ShahrShad (شهرشاد) partner places — restaurants, cafés, pools, sports, events, museums and attractions.

ShahrShad is a sister business of the group with a public read API (`GET {base}/v1/venues`, active venues only). We
copy its venue list into one reference table and show it on the restaurant / attraction / pool / events pages with a
link to the venue on shahrshad.ir, where the session is chosen and paid. Prices are shown only when ShahrShad marks
them published and not stale, as a "from" price with the date it was checked; nothing is invented here.

Sync: `POST /admin/shahrshad/sync` (platform admin / tenant admin) or `python -m app.shahrshad_sync`.
Base URL: `SHAHRSHAD_API_URL` (default https://shahrshad.ir).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base

SECTIONS = {
    "restaurants": ("restaurant",),
    "attractions": ("attraction", "amusement", "museum", "nature", "bowling"),
    "pools-sports": ("pool", "sport", "wellness"),
    "events-venues": ("event", "venue"),
}
CATEGORY_FA = {"restaurant": "رستوران و کافه", "attraction": "جاذبه", "amusement": "شهربازی و سرگرمی", "museum": "موزه", "nature": "طبیعت",
               "bowling": "بولینگ", "pool": "استخر و پارک آبی", "sport": "ورزش", "wellness": "سلامت و آرامش", "event": "رویداد", "venue": "تالار و فضای مراسم"}
FACILITY_FA = {"cafe": "کافه", "food": "غذا", "indoor": "سرپوشیده", "outdoor": "روباز", "jacuzzi": "جکوزی", "kids_area": "بخش کودک", "lazy_river": "رودخانه‌ی آرام",
               "locker_room": "رختکن", "massage": "ماساژ", "slides": "سرسره", "spa": "اسپا", "wave_pool": "استخر موج", "parking": "پارکینگ", "sauna": "سونا",
               "wifi": "اینترنت", "delivery": "ارسال غذا", "family": "خانوادگی", "wheelchair": "دسترسی ویلچر"}
ADMISSION_FA = {"men": "آقایان", "women": "بانوان", "family": "خانوادگی", "mixed": "عمومی"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PartnerVenue(Base):
    """Global reference copy of ShahrShad venues (no tenant: public places, same for every tenant)."""
    __tablename__ = "partner_venues"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="shahrshad", index=True)
    slug: Mapped[str] = mapped_column(String(240))
    name: Mapped[str] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(24), index=True)
    kind: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cuisine: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    admission_json: Mapped[str] = mapped_column(Text, default="[]")
    facilities_json: Mapped[str] = mapped_column(Text, default="[]")
    price_from_irr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_published: Mapped[bool] = mapped_column(Boolean, default=False)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    operating_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    facts_checked_on: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_alt: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def base_url() -> str:
    return (os.environ.get("SHAHRSHAD_API_URL") or "https://shahrshad.ir").rstrip("/")


def _str(v, n: int) -> Optional[str]:
    return v.strip()[:n] if isinstance(v, str) and v.strip() else None


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def fetch_all(get: Optional[Callable[[str], dict]] = None, page: int = 100, cap: int = 10000) -> list[dict]:
    """All active venues from ShahrShad's public API, page by page."""
    if get is None:
        client = httpx.Client(timeout=20, headers={"User-Agent": "KarenSeir-partner-sync/1.0"})
        get = lambda url: client.get(url).raise_for_status().json()  # noqa: E731
    out: list[dict] = []
    offset = 0
    while offset < cap:
        data = get(f"{base_url()}/v1/venues?limit={page}&offset={offset}")
        items = data.get("items") or []
        out.extend(i for i in items if isinstance(i, dict))
        if len(items) < page:
            break
        offset += page
    return out


def apply(db: Session, items: list[dict]) -> dict:
    """Upsert the fetched list; venues missing from it are marked inactive (never deleted)."""
    now = utcnow()
    seen: set[str] = set()
    created = updated = 0
    for it in items:
        vid, slug, name, cat = _str(it.get("id"), 40), _str(it.get("slug"), 240), _str(it.get("name"), 240), _str(it.get("category"), 24)
        if not (vid and slug and name and cat):
            continue
        seen.add(vid)
        row = db.get(PartnerVenue, vid)
        if row is None:
            row = PartnerVenue(id=vid, source="shahrshad")
            db.add(row)
            created += 1
        else:
            updated += 1
        price = it.get("price_from_irr")
        row.slug, row.name, row.category, row.kind = slug, name, cat, _str(it.get("kind"), 40)
        row.description, row.city, row.district, row.province = _str(it.get("description"), 2000), _str(it.get("city"), 80), _str(it.get("district"), 80), _str(it.get("province"), 80)
        row.latitude, row.longitude, row.cuisine = _num(it.get("latitude")), _num(it.get("longitude")), _str(it.get("cuisine"), 80)
        row.admission_json = json.dumps([a for a in (it.get("admission") or []) if isinstance(a, str)][:8])
        row.facilities_json = json.dumps([f for f in (it.get("facilities") or []) if isinstance(f, str)][:20])
        row.price_from_irr = int(price) if isinstance(price, int) and not isinstance(price, bool) and price > 0 else None
        row.price_published = it.get("price_state") == "published"
        row.stale = bool(it.get("stale"))
        row.operating_status, row.facts_checked_on = _str(it.get("operating_status"), 40), _str(it.get("facts_checked_on"), 10)
        img = _str(it.get("image_url"), 500)
        row.image_url = img if img and img.startswith("https://") else None
        row.image_alt = _str(it.get("image_alt"), 240)
        row.active, row.synced_at = True, now
    deactivated = 0
    if items:
        for row in db.scalars(select(PartnerVenue).where(PartnerVenue.source == "shahrshad", PartnerVenue.active.is_(True))).all():
            if row.id not in seen:
                row.active = False
                deactivated += 1
    db.commit()
    return {"fetched": len(items), "created": created, "updated": updated, "deactivated": deactivated, "synced_at": now.isoformat()}


def venue_out(v: PartnerVenue) -> dict:
    show_price = v.price_published and not v.stale and v.price_from_irr
    return {"id": v.id, "name": v.name, "category": v.category, "category_fa": CATEGORY_FA.get(v.category, v.category), "description": v.description,
            "city": v.city, "district": v.district, "cuisine": v.cuisine,
            "admission": [ADMISSION_FA.get(a, a) for a in json.loads(v.admission_json or "[]")],
            "facilities": [FACILITY_FA[f] for f in json.loads(v.facilities_json or "[]") if f in FACILITY_FA][:5],
            "price_from_irr": v.price_from_irr if show_price else None, "facts_checked_on": v.facts_checked_on if show_price else None,
            "image_url": v.image_url, "image_alt": v.image_alt or v.name,
            "map_url": f"https://www.openstreetmap.org/?mlat={v.latitude}&mlon={v.longitude}#map=16/{v.latitude}/{v.longitude}" if v.latitude and v.longitude else None,
            "book_url": f"{base_url()}/venues/{quote(v.slug)}", "source": "شهرشاد"}


def shahrshad_router(get_db, require_admin) -> APIRouter:
    api = APIRouter(tags=["partner-venues"])

    @api.get("/public/partner-venues")
    def list_public(section: str = Query(pattern="^(" + "|".join(SECTIONS) + ")$"), city: Optional[str] = Query(default=None, max_length=80),
                    category: Optional[str] = Query(default=None, max_length=24), q: Optional[str] = Query(default=None, max_length=80),
                    limit: int = Query(default=24, ge=1, le=60), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
        cats = SECTIONS[section]
        if category and category not in cats:
            raise HTTPException(status_code=422, detail="دسته‌ی نامعتبر")
        s = select(PartnerVenue).where(PartnerVenue.active.is_(True), PartnerVenue.category.in_((category,) if category else cats))
        if city:
            s = s.where(PartnerVenue.city == city)
        if q:
            like = f"%{q.strip()}%"
            s = s.where(or_(PartnerVenue.name.ilike(like), PartnerVenue.description.ilike(like), PartnerVenue.cuisine.ilike(like)))
        total = db.scalar(select(func.count()).select_from(s.subquery())) or 0
        rows = db.scalars(s.order_by(PartnerVenue.price_published.desc(), PartnerVenue.image_url.is_(None), PartnerVenue.name).limit(limit).offset(offset)).all()
        city_rows = db.execute(select(PartnerVenue.city, func.count()).where(PartnerVenue.active.is_(True), PartnerVenue.category.in_(cats), PartnerVenue.city.is_not(None))
                               .group_by(PartnerVenue.city).order_by(func.count().desc()).limit(30)).all()
        cat_rows = db.execute(select(PartnerVenue.category, func.count()).where(PartnerVenue.active.is_(True), PartnerVenue.category.in_(cats)).group_by(PartnerVenue.category)).all()
        return {"items": [venue_out(v) for v in rows], "total": int(total), "limit": limit, "offset": offset,
                "cities": [{"name": c, "count": int(n)} for c, n in city_rows],
                "categories": [{"key": c, "label": CATEGORY_FA.get(c, c), "count": int(n)} for c, n in cat_rows]}

    @api.post("/admin/shahrshad/sync")
    def sync_now(user=Depends(require_admin), db: Session = Depends(get_db)):
        try:
            items = fetch_all()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"ارتباط با شهرشاد برقرار نشد: {type(exc).__name__}")
        return apply(db, items)

    @api.get("/admin/shahrshad/status")
    def status(user=Depends(require_admin), db: Session = Depends(get_db)):
        last = db.scalar(select(func.max(PartnerVenue.synced_at)))
        active = db.scalar(select(func.count(PartnerVenue.id)).where(PartnerVenue.active.is_(True))) or 0
        return {"active": int(active), "last_synced_at": last.isoformat() if last else None, "source": base_url()}

    return api


if __name__ == "__main__":  # python -m app.shahrshad_sync
    from .database import SessionLocal
    with SessionLocal() as session:
        print(json.dumps(apply(session, fetch_all()), ensure_ascii=False))
