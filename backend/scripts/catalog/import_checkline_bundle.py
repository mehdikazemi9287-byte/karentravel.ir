"""Import the full CheckLine bundle content into the master catalog (additive, idempotent, provenance kept).

  DATABASE_URL=... python scripts/catalog/import_checkline_bundle.py <extracted_bundle_dir> [--dry-run]

Reads evidence-round3/deep-data-audit-round3.json (catalog items with public body) and
evidence-round3/catalog-controls-round3.json (full meta, taxonomy), round3-technical/media-workbench.json
(attachment id -> file) and ecosystem-technical/country-city-mismatches.json.

What is written: places (countries, provinces, cities), hotels with description, address, stars (source-reported),
clock times, rules, phone, room types, images, facts; reference tours with description, destination, duration,
transport, inclusions, hotels; attractions; visa articles; the old site's page/menu map.
What is never written: price, discount, capacity, availability, coordinates that the source does not carry,
facility lists whose labels are not in the bundle. Admin-edited rows keep their values (only empty fields are filled).
Rows of other sources are never changed. Nothing is deleted except replace-on-import children of CheckLine-owned rows.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import delete, func, select  # noqa: E402

from app.catalog import (AMENITIES, CatalogContent, CatalogHotel, CatalogHotelImage, CatalogHotelRoomType, CatalogLegacyRoute, CatalogPlace, CatalogTour, CatalogTourHotel, CatalogVenue,  # noqa: E402
                         content_is_complete, normalize_text)
from app.database import SessionLocal  # noqa: E402
from scripts.catalog.import_checkline import ISO, LICENSE, RETRIEVED, SOURCE, _match, clock, squash  # noqa: E402

MEDIA_BASE = "https://checkline.travel/wp-content/uploads/"
IMAGE_LICENSE = "CheckLine media library; rights unverified"
ROOM_AMENITY = {"wifi": "wifi", "elevator": "elevator", "reception_24": "reception_24h", "air_conditioning": "air_conditioning", "safe_box": "safe", "full_fridge": "minibar", "satellite": "tv", "tv": "tv", "room_service": "room_service",
                "breakfast": "breakfast", "kitchen": "kitchen", "parking": "parking", "laundry": "laundry", "toothbrush_toothpaste_soap": "toiletries", "towel_slippers": "towels", "closet_with_hangers": "wardrobe", "hairdryer": "hairdryer",
                "fire_sensor": "smoke_detector", "alarm": "wake_up", "terrace": "terrace", "airport_transportation": "airport_shuttle", "exchange": "currency_exchange", "buffet_breakfast": "breakfast", "restaurant": "restaurant",
                "room_service_24": "room_service", "luggage": "luggage_storage", "atm": "atm", "breakfast_in_room": "breakfast", "emergency_power": "emergency_power", "translator": "translator", "lobby": "lobby", "car_rental": "car_rental_desk",
                "shop_in_hotel": "shop", "outdoor_swimming_pool": "pool", "indoor_swimming_pool": "pool", "jacuzzi": "jacuzzi", "conference_room": "meeting_room", "prayer_room": "prayer_room", "gym": "fitness", "sauna": "spa", "massage": "spa"}
# facilities a room list states about the whole property (the source ticks them per room)
PROPERTY_WIDE = {"elevator", "reception_24", "parking", "restaurant", "laundry", "exchange", "airport_transportation", "room_service_24", "buffet_breakfast", "luggage", "atm", "emergency_power", "translator", "lobby", "car_rental", "shop_in_hotel",
                 "outdoor_swimming_pool", "indoor_swimming_pool", "jacuzzi", "conference_room", "prayer_room", "gym", "sauna", "massage"}
BOARD_FA = {"RO": "بدون وعده", "BB": "صبحانه", "HB": "نیم‌پانسیون", "FB": "تمام‌پانسیون", "ALL": "همه‌چیز رایگان", "UALL": "اولترا آل‌اینکلوسیو"}
TOUR_INCLUSION = {"ticket-go": "بلیت رفت", "ticket-back": "بلیت برگشت", "transfer-to-airport": "ترانسفر فرودگاهی", "transfer-to-hotel": "ترانسفر هتل", "simcart": "سیم‌کارت", "persian-tour-leader": "راهنمای فارسی‌زبان", "hotel-eghamat": "اقامت در هتل",
                  "food": "وعدهٔ غذایی", "travel-insurance": "بیمهٔ مسافرتی", "visa": "ویزا", "city-tour": "گشت شهری", "local-leader": "راهنمای محلی"}
TRANSPORT = {"هوایی": "flight", "زمینی": "bus", "ریلی": "train", "دریایی": "cruise"}
EMPTY = (None, "", [], {}, [""], [[]], [None], "null", ["null"])


def first(value):
    if isinstance(value, list):
        for item in value:
            if item not in EMPTY: return item
        return None
    return None if value in EMPTY else value


def ids_of(value) -> list[str]:
    """Attachment ids of a gallery field: [[ids]] in the full meta export, [ids] in the reduced one."""
    if isinstance(value, list) and value and isinstance(value[0], list): value = value[0]
    return [str(v) for v in value if v not in EMPTY and str(v).isdigit()] if isinstance(value, list) else []


def map_link(embed) -> str | None:
    """The source stores a Google Maps embed with a text query, not coordinates: keep it as a link, never as a position."""
    m = re.search(r"maps\?q=([^&\"']+)", embed or "") if isinstance(embed, str) else None
    return f"https://www.google.com/maps/search/?api=1&query={m[1]}" if m else None


def text_of(markup) -> str | None:
    if not markup or not isinstance(markup, str): return None
    t = re.sub(r"(?is)<(script|style|iframe)[^>]*>.*?</\1>", " ", markup)
    t = re.sub(r"(?i)<\s*(br|/p|/div|/h[1-6]|/li|/tr)\s*/?>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    lines = [re.sub(r"[ \t  ]+", " ", ln).strip() for ln in t.splitlines()]
    out = "\n".join(ln for ln in lines if ln)
    return out or None


def rows_of(meta: dict, prefix: str, fields: tuple[str, ...]) -> list[dict]:
    out = []
    for i in range(60):
        row = {f: first(meta.get(f"{prefix}_{i}_{f}")) for f in fields}
        if all(v is None for v in row.values()):
            if i > 0 and f"{prefix}_{i}_{fields[0]}" not in meta: break
            continue
        out.append(row)
    return out


def main(bundle_dir: str, dry_run: bool, publish: bool = True) -> dict:
    """publish=False (CLI default): content is written, but no hotel or tour becomes public or stops being public by this run."""
    root = Path(bundle_dir)
    deep = json.loads((root / "evidence-round3/deep-data-audit-round3.json").read_text(encoding="utf-8"))
    controls = json.loads((root / "evidence-round3/catalog-controls-round3.json").read_text(encoding="utf-8"))
    media = {str(x["id"]): x for x in json.loads((root / "round3-technical/media-workbench.json").read_text(encoding="utf-8")) if x.get("image") and x.get("exists") and x.get("relative_file")}
    conflicts = {str(c["hotel_id"]) for c in json.loads((root / "ecosystem-technical/country-city-mismatches.json").read_text(encoding="utf-8"))}
    full_meta = {str(x["id"]): (x["meta"] if isinstance(x["meta"], dict) else {}) for x in controls["catalog_meta"]}
    term_names = {x["term_taxonomy_id"]: (x["taxonomy"], x["name"]) for x in deep["taxonomy"]}
    categories: dict[str, list[str]] = {}
    for x in controls["catalog_taxonomy"]:
        tax, name = term_names.get(x["term_taxonomy_id"], (None, None))
        if tax in ("location-category", "tour-category", "city-category", "country-category", "region", "visa-category", "attraction-category") and name:
            categories.setdefault(str(x["post_id"]), []).append(name)
    items: dict[str, list[dict]] = {}
    for x in sorted(deep["catalog"], key=lambda x: int(x["id"])): items.setdefault(x["type"], []).append(x)
    by_id = {str(x["id"]): x for x in deep["catalog"]}
    meta_of = lambda x: {**(x["meta"] if isinstance(x["meta"], dict) else {}), **full_meta.get(str(x["id"]), {})}  # noqa: E731
    image_url = lambda att: MEDIA_BASE + quote(media[str(att)]["relative_file"]) if att is not None and str(att) in media else None  # noqa: E731

    def gallery_urls(ids, limit=12) -> list[str]:
        """Existing image files only, one per distinct file content (the library holds 858 byte-identical copies)."""
        seen, out = set(), []
        for g in ids:
            rec = media.get(str(g))
            if rec is None or (rec.get("sha256") or rec["relative_file"]) in seen: continue
            seen.add(rec.get("sha256") or rec["relative_file"]); out.append(MEDIA_BASE + quote(rec["relative_file"]))
        return out[:limit]
    report = {"places": {"countries_added": 0, "regions_added": 0, "cities_added": 0, "enriched": 0}, "hotels": {"input": 0, "inserted": 0, "updated": 0, "unchanged": 0, "admin_filled": 0, "published": 0, "kept_draft": 0, "quarantined": {}, "city_unresolved": 0,
                                                                                                                 "with_description": 0, "room_types": 0, "images": 0, "bad_image_refs": 0},
              "tours": {"input": 0, "inserted": 0, "updated": 0, "admin_skipped": 0, "hotel_links": 0, "published": 0}, "attractions": 0, "content": 0, "legacy_routes": 0, "skipped_commercial_fields": ["discount-amount", "start-price", "hotels-list prices", "holding-dates capacity", "price-percent"]}
    now = datetime.now(timezone.utc)
    publish_flag = publish
    with SessionLocal() as db:
        places = {p.id: p for p in db.scalars(select(CatalogPlace))}
        countries = {p.country_code: p for p in places.values() if p.kind == "country"}
        city_index: dict[tuple[str, str], list[CatalogPlace]] = {}; region_index: dict[tuple[str, str], CatalogPlace] = {}
        for p in sorted(places.values(), key=lambda p: p.id):
            for name in {squash(p.name_fa), squash(p.name_en)} - {""}:
                if p.kind == "city": city_index.setdefault((p.country_code, name), []).append(p)
                if p.kind == "region": region_index.setdefault((p.country_code, name.replace(squash("استان"), "", 1) if name.startswith(squash("استان")) else name), p)
        geo_place: dict[str, CatalogPlace] = {}
        enriched_ids: set[str] = set()  # the source has duplicate country/city posts: the lowest id speaks for the place

        def enrich(place: CatalogPlace, x: dict, meta: dict, extra: dict) -> None:
            """Fill only what is empty on records of other sources; CheckLine-owned records follow the bundle."""
            if place.id in enriched_ids: return
            enriched_ids.add(place.id)
            own = place.source == SOURCE or place.source == "iso3166-1"
            body, mp = text_of(x.get("public_body")), first(meta.get("map"))
            before = (place.description, place.latitude, place.name_en, place.details_json, place.image_url)
            if body and (own or not place.description): place.description = body
            if isinstance(mp, dict) and place.latitude is None:
                try:
                    lat, lng = float(mp.get("lat")), float(mp.get("lng"))
                    if -90 <= lat <= 90 and -180 <= lng <= 180 and (lat, lng) != (0.0, 0.0): place.latitude, place.longitude = lat, lng
                except (TypeError, ValueError): pass
            english = first(meta.get("title-en"))
            if english and not place.name_en: place.name_en = str(english).strip()[:160]
            img = image_url(first(meta.get("top-image"))) or next((image_url(g) for g in ids_of(meta.get("gallery")) if image_url(g)), None)
            if img and not place.image_url: place.image_url, place.image_credit = img, IMAGE_LICENSE
            details = json.loads(place.details_json or "{}")
            details["checkline"] = {k: v for k, v in {"legacy_id": x["id"], "legacy_slug": unquote(x.get("slug") or ""), "source_status": x["status"], "categories": categories.get(str(x["id"])),
                                                      "images": gallery_urls(ids_of(meta.get("gallery")), 8), "map_link": map_link(first(meta.get("map-embed"))), "flag_url": image_url(first(meta.get("flag"))), **extra}.items() if v not in EMPTY}
            place.details_json = json.dumps(details, ensure_ascii=False, sort_keys=True)
            if own:
                missing = [n for n in (normalize_text(place.name_fa), normalize_text(place.name_en)) if n and n not in (place.search_text or "")]
                if missing: place.search_text = " ".join([place.search_text or "", *missing]).strip()[:2000]
            if before != (place.description, place.latitude, place.name_en, place.details_json, place.image_url): report["places"]["enriched"] += 1

        def new_place(pid: str, kind: str, parent, code: str, x: dict, meta: dict, source=SOURCE, ref=None) -> CatalogPlace:
            english = first(meta.get("title-en"))
            p = CatalogPlace(id=pid, kind=kind, parent_id=parent, country_code=code, name_fa=(x.get("title") or "").strip()[:160] or None, name_en=str(english).strip()[:160] if english else None, hotel_count=0,
                             search_text=normalize_text(f"{x.get('title') or ''} {english or ''}"), source=source, source_ref=ref or f"geography/{x['id']}", source_license=LICENSE, retrieved_on=RETRIEVED)
            places[pid] = p
            if not dry_run: db.add(p)
            return p

        # ---- countries
        for x in items.get("country", []):
            meta = meta_of(x); iso = ISO.get(str(first(meta.get("title-en")) or "").strip().lower())
            if iso is None or x["status"] != "publish": continue
            code = iso[0]; place = countries.get(code)
            if place is None:
                place = new_place(code.lower(), "country", None, code, x, {**meta, "title-en": [iso[1]]}, source="iso3166-1", ref=code); countries[code] = place; report["places"]["countries_added"] += 1
            geo_place.setdefault(str(x["id"]), place)
            enrich(place, x, meta, {"capital": first(meta.get("capital")), "currency": first(meta.get("currency")), "official_language": first(meta.get("official_language")), "population_text": first(meta.get("population")),
                                    "voltage": first(meta.get("voltage")), "visa_note": text_of(first(meta.get("visa"))), "major_cities": text_of(first(meta.get("major_cities")))})
        # ---- provinces (the source only has Iranian ones)
        for x in items.get("state", []):
            meta = meta_of(x); country = geo_place.get(str(first(meta.get("country")) or ""))
            if country is None or x["status"] != "publish": continue
            place = region_index.get((country.country_code, squash(x["title"])))
            if place is None:
                place = new_place(f"cl-state-{x['id']}", "region", country.id, country.country_code, x, meta); region_index[(country.country_code, squash(x["title"]))] = place; report["places"]["regions_added"] += 1
            geo_place[str(x["id"])] = place
            enrich(place, x, meta, {"population_text": first(meta.get("population")), "time_zone": first(meta.get("time_zone")), "guide": text_of(first(meta.get("guide")))})
        # ---- cities
        for x in items.get("city", []):
            meta = meta_of(x); country = geo_place.get(str(first(meta.get("country")) or ""))
            if country is None or x["status"] != "publish" or not (x.get("title") or "").strip(): continue
            found = {p.id: p for name in (x["title"], first(meta.get("title-en"))) for p in city_index.get((country.country_code, squash(name)), [])}
            if len(found) > 1: continue  # ambiguous: left alone
            place = next(iter(found.values())) if found else None
            if place is None:
                place = new_place(f"cl-city-{x['id']}", "city", country.id, country.country_code, x, meta)
                for name in {squash(place.name_fa), squash(place.name_en)} - {""}: city_index.setdefault((country.country_code, name), []).append(place)
                report["places"]["cities_added"] += 1
            geo_place[str(x["id"])] = place
            state = geo_place.get(str(first(meta.get("state")) or ""))
            if state is not None and place.source == SOURCE and place.parent_id == country.id and state.kind == "region": place.parent_id = state.id
            enrich(place, x, meta, {"population_text": first(meta.get("population")), "time_zone": first(meta.get("time_zone")), "guide": text_of(first(meta.get("guide")))})
        if not dry_run: db.flush()

        # ---- hotels
        touched: list[str] = []
        wanted: dict[str, bool] = {}
        for x in items.get("location", []):
            report["hotels"]["input"] += 1
            legacy, meta, title = str(x["id"]), meta_of(x), (x.get("title") or "").strip()
            q = lambda reason: report["hotels"]["quarantined"].__setitem__(reason, report["hotels"]["quarantined"].get(reason, 0) + 1)  # noqa: E731
            if not title: q("no_title"); continue
            if legacy in conflicts: q("country_city_conflict"); continue
            country = geo_place.get(str(first(meta.get("country")) or ""))
            if country is None or country.kind != "country": q("country_unresolved"); continue
            city = geo_place.get(str(first(meta.get("city")) or ""))
            if city is not None and (city.kind != "city" or city.country_code != country.country_code): city = None
            if city is None: report["hotels"]["city_unresolved"] += 1
            english = re.search(r"\(([A-Za-z0-9][^()]*)\)\s*$", title); latin = not re.search(r"[؀-ۿ]", title)
            name_fa = None if latin else re.sub(r"\s*\([A-Za-z0-9][^()]*\)\s*$", "", title).strip()[:200]
            name_en = (title if latin else english[1].strip() if english else None)
            rating = str(first(meta.get("rating")) or "").strip(); stars = int(rating) if rating in {"1", "2", "3", "4", "5"} else None
            description = text_of(x.get("public_body")); rules = "\n".join(filter(None, [text_of(first(meta.get("rules-title"))), text_of(first(meta.get("rules-text")))])) or None
            boards = [b for b in (first(meta.get("services")) or []) if b in BOARD_FA] if isinstance(first(meta.get("services")), list) else []
            restaurants = rows_of(meta, "cafe-restaurant", ("cafe-name", "cafe-capacity", "cafe-hours"))
            rooms = [r for r in rows_of(meta, "rooms-info", ("room-title", "hidden", "room-desc", "room-facilities", "room-photo")) if r["room-title"] and str(r["hidden"] or "0") != "1"]
            amenity_keys = list(dict.fromkeys([*("breakfast" for b in boards if b != "RO"), *(["restaurant"] if restaurants else []), *(["parking"] if first(meta.get("parking-capacity")) else []),
                                               *(ROOM_AMENITY[c] for r in rooms for c in (r["room-facilities"] or []) if c in PROPERTY_WIDE and c in ROOM_AMENITY)]))
            amenity_keys = [a for a in amenity_keys if a in AMENITIES]
            phone, site = first(meta.get("tel")), first(meta.get("url"))
            details = {k: v for k, v in {"legacy_id": x["id"], "legacy_slug": unquote(x.get("slug") or ""), "source_status": x["status"], "categories": categories.get(legacy), "district": first(meta.get("district")),
                                         "room_count": first(meta.get("room-count")), "bed_count": first(meta.get("bed-count")), "built_year_jalali": first(meta.get("built-year")), "floors": first(meta.get("step-count")),
                                         "hotel_view": (first(meta.get("hotel-view")) or "").strip() or None, "board_plans": [BOARD_FA[b] for b in boards], "review": text_of(first(meta.get("review"))),
                                         "map_link": map_link(first(meta.get("map-embed"))), "traffic": text_of(first(meta.get("traffic-situation"))),
                                         "nearby": [{"place": r["hdtbp-place"], "distance": r["hdtbp-distance"], "unit": r["hdtbp-unit"]} for r in rows_of(meta, "hotel-distance-to-bold-points", ("hdtbp-place", "hdtbp-distance", "hdtbp-unit")) if r["hdtbp-place"]],
                                         "restaurants": [{"name": r["cafe-name"], "capacity": r["cafe-capacity"], "hours": r["cafe-hours"]} for r in restaurants if r["cafe-name"]]}.items() if v not in EMPTY}
            values = {"slug": f"checkline-{legacy}", "country_code": country.country_code, "region_id": city.parent_id if city and city.parent_id != country.id else None, "city_id": city.id if city else None, "name_fa": name_fa,
                      "name_en": name_en[:200] if name_en else None, "hotel_type": "guest_house" if first(meta.get("stay-type")) == "ecotourism" else "hotel", "stars": stars, "stars_status": "source_reported" if stars else None,
                      "address": (first(meta.get("address")) or "").strip()[:400] or None, "checkin_time": clock(first(meta.get("check-in-time"))), "checkout_time": clock(first(meta.get("check-out-time"))), "description": description,
                      "rules_text": rules, "phone": str(phone).strip()[:80] if phone else None, "website": str(site).strip()[:300] if site and str(site).startswith("https://") else None, "amenities_json": json.dumps(amenity_keys),
                      "details_json": json.dumps({"checkline": details}, ensure_ascii=False, sort_keys=True),
                      "search_text": normalize_text(" ".join(filter(None, [name_fa, name_en, city.search_text if city else None, country.name_fa, first(meta.get("address")), first(meta.get("district"))])))[:2000],
                      "source": SOURCE, "source_ref": f"hotel/{legacy}", "source_license": LICENSE, "retrieved_on": RETRIEVED}
            image_ids = list(dict.fromkeys(ids_of(meta.get("gallery"))))
            images = gallery_urls(image_ids)
            report["hotels"]["bad_image_refs"] += sum(1 for g in image_ids if not image_url(g))
            if description: report["hotels"]["with_description"] += 1
            row = db.get(CatalogHotel, f"cl-{legacy}")
            if row is not None and row.source != SOURCE: q("id_owned_by_other_source"); continue
            if row is not None and row.updated_by is not None:  # reviewer-edited: only fill what is still empty
                filled = [k for k in ("description", "address", "rules_text", "phone", "checkin_time", "checkout_time") if getattr(row, k) in (None, "") and values[k]]
                for k in filled: setattr(row, k, values[k])
                if not dry_run and not row.details_json: row.details_json = values["details_json"]
                report["hotels"]["admin_filled"] += 1 if filled else 0; touched.append(row.id); continue
            if row is None:
                report["hotels"]["inserted"] += 1
                row = CatalogHotel(id=f"cl-{legacy}", status="draft", quality=0, content_complete=False, **values)
                if not dry_run: db.add(row)
            elif any(getattr(row, k) != v for k, v in values.items()):
                report["hotels"]["updated"] += 1
                for k, v in values.items(): setattr(row, k, v)
            else:
                report["hotels"]["unchanged"] += 1
            touched.append(row.id)
            report["hotels"]["room_types"] += len(rooms); report["hotels"]["images"] += len(images)
            row.image_url, row.image_credit = (images[0], IMAGE_LICENSE) if images else (None, None)
            row.quality = sum(bool(v) for v in (name_fa, values["address"], description, images, rooms, amenity_keys, values["checkin_time"], stars))
            row.content_complete = content_is_complete(row, len(images), len(rooms))
            wanted[row.id] = x["status"] == "publish"  # decided after duplicate matching
            if not dry_run:
                db.flush()
                db.execute(delete(CatalogHotelImage).where(CatalogHotelImage.hotel_id == row.id)); db.execute(delete(CatalogHotelRoomType).where(CatalogHotelRoomType.hotel_id == row.id))
                db.add_all([CatalogHotelImage(hotel_id=row.id, url=u, license=IMAGE_LICENSE, source_url=u, sort_order=i) for i, u in enumerate(images)])
                db.add_all([CatalogHotelRoomType(hotel_id=row.id, name_fa=str(r["room-title"]).strip()[:160], description=text_of(r["room-desc"]), sort_order=i, image_url=image_url(r["room-photo"]),
                                                 amenities_json=json.dumps(list(dict.fromkeys(ROOM_AMENITY[c] for c in (r["room-facilities"] or []) if c in ROOM_AMENITY and ROOM_AMENITY[c] in AMENITIES)))) for i, r in enumerate(rooms)])
        if not dry_run:
            db.flush()
            match_report = {"matches": {"auto_linked": 0, "proposed": 0, "kept_decisions": 0}}
            _match(db, [t for t in touched if t.startswith("cl-") and t[3:].isdigit()], match_report); report["hotels"]["matches"] = match_report["matches"]
            from app.catalog import CatalogHotelMatch
            proposed = set(db.scalars(select(CatalogHotelMatch.hotel_id).where(CatalogHotelMatch.status == "proposed"))) | set(db.scalars(select(CatalogHotelMatch.candidate_id).where(CatalogHotelMatch.status == "proposed")))
            for hid in touched:
                row = db.get(CatalogHotel, hid)
                if row is None or row.updated_by is not None: continue
                publish_allowed = publish_flag
                publish = wanted.get(hid, False) and row.city_id is not None and row.duplicate_of is None and row.id not in proposed and bool(row.description or row.address)
                if publish_allowed: row.status = "published" if publish else "draft"
                elif row.status == "published" and (row.duplicate_of is not None or row.id in proposed): row.status = "draft"  # a duplicate is never public
                report["hotels"]["published" if row.status == "published" else "kept_draft"] += 1
            counts = dict(db.execute(select(CatalogHotel.city_id, func.count()).where(CatalogHotel.status == "published", CatalogHotel.duplicate_of.is_(None), CatalogHotel.city_id.is_not(None)).group_by(CatalogHotel.city_id)).all())
            for p in places.values():
                if p.kind == "city" and (p.source == SOURCE or p.id in counts) and p.hotel_count != counts.get(p.id, 0) and (p.source == SOURCE or counts.get(p.id, 0) > p.hotel_count): p.hotel_count = counts.get(p.id, p.hotel_count)

        # ---- reference tours
        used_slugs: set[str] = set()
        for x in items.get("tour", []):
            if x["status"] == "trash" or not (x.get("title") or "").strip(): continue
            report["tours"]["input"] += 1
            meta, tid = meta_of(x), f"cl-tour-{x['id']}"
            cities, countries_ref = first(meta.get("cities")) or [], first(meta.get("countries")) or []
            dest = next((geo_place[str(c)] for c in (cities if isinstance(cities, list) else [cities]) if str(c) in geo_place), None) or next((geo_place[str(c)] for c in (countries_ref if isinstance(countries_ref, list) else [countries_ref]) if str(c) in geo_place), None)
            duration = str(first(meta.get("travel-duration")) or x["title"]).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
            nights, days = re.search(r"(\d{1,2})\s*شب", duration), re.search(r"(\d{1,2})\s*روز", duration)
            nights, days = (int(nights[1]) if nights else None, int(days[1]) if days else None)
            if nights is not None and days is not None and not 0 <= days - nights <= 1: nights = days = None
            legs = [l for l in rows_of(meta, "transport-list-column-titles", ("direction_title", "origin_title", "destination_title", "movement_time_title", "arriving_time_title", "company_name_title", "vehicle_title", "number_title")) if l["origin_title"] or l["destination_title"]]
            codes = first(meta.get("facilities")) if isinstance(first(meta.get("facilities")), list) else []
            hotel_ids = list(dict.fromkeys(str(first(meta.get(f"hotels-list_{i}_hl-hotel-items_{j}_hl-hotel-select"))) for i in range(40) for j in range(6) if first(meta.get(f"hotels-list_{i}_hl-hotel-items_{j}_hl-hotel-select"))))
            details = {k: v for k, v in {"legacy_id": x["id"], "legacy_slug": unquote(x.get("slug") or ""), "source_status": x["status"], "long_title": first(meta.get("long_title")), "categories": categories.get(str(x["id"])),
                                         "services_text": text_of(first(meta.get("services"))), "inclusions": [TOUR_INCLUSION.get(c, c) for c in codes], "leave_duration": first(meta.get("leave-duration")), "difficulty": first(meta.get("difficulty")),
                                         "age_range": first(meta.get("age_range")), "moving_point": first(meta.get("moving-point")), "roadmap": text_of(first(meta.get("roadmap"))), "notice": text_of(first(meta.get("notice-text"))),
                                         "transport_legs": [{"mode": l["direction_title"], "origin": l["origin_title"], "destination": l["destination_title"], "departs": l["movement_time_title"], "arrives": l["arriving_time_title"], "carrier": l["company_name_title"]} for l in legs],
                                         "images": gallery_urls([*ids_of(meta.get("gallery")), *ids_of(meta.get("places-gallery"))], 10), "carriers": [c for c in (first(meta.get(f"carrier_{i}_name")) for i in range(6)) if c],
                                         "ribbon": first(meta.get("ribbon_title")), "booking_note": text_of(first(meta.get("packages-details"))), "title_en": first(meta.get("title-en")),
                                         "hotel_notes": [n for n in (text_of(first(meta.get(f"hotels-list_{i}_hl-description"))) for i in range(40)) if n][:10],
                                         "image_url": image_url(first(meta.get("top-image"))), "image_credit": IMAGE_LICENSE if image_url(first(meta.get("top-image"))) else None}.items() if v not in EMPTY}
            slug = re.sub(r"[^\w\u0600-\u06FF-]+", "-", unquote(x.get("slug") or "")).strip("-")[:180] or tid
            if slug in used_slugs: slug = f"{slug}-{x['id']}"
            used_slugs.add(slug)
            values = {"slug": slug, "title_fa": x["title"].strip()[:200], "search_text": normalize_text(" ".join(filter(None, [x["title"], first(meta.get("long_title")), dest.name_fa if dest else None, *(categories.get(str(x["id"])) or [])]))), "description": text_of(x.get("public_body")),
                      "destination_place_id": dest.id if dest else None, "duration_nights": nights, "duration_days": days, "transport_mode": next((TRANSPORT[l["direction_title"]] for l in legs if l["direction_title"] in TRANSPORT), None),
                      "guide_included": True if "persian-tour-leader" in codes else None, "transfer_included": True if any(c.startswith("transfer-") for c in codes) else None,
                      "cancellation_policy_text": "\n".join(filter(None, [text_of(first(meta.get("title_table_jarime"))), text_of(first(meta.get("txt_table_jarime"))), text_of(first(meta.get("tour-rules")))])) or None,
                      "details_json": json.dumps({"checkline": details}, ensure_ascii=False, sort_keys=True), "source_disabled": str(first(meta.get("disabled")) or "0") == "1", "source_soldout": str(first(meta.get("static-soldout")) or "0") == "1",
                      "source": SOURCE, "source_ref": f"tour/{x['id']}", "source_license": LICENSE, "retrieved_on": RETRIEVED, "status": "published" if x["status"] == "publish" else "draft"}
            row = db.get(CatalogTour, tid)
            if not publish_flag: values["status"] = row.status if row is not None else "draft"
            if row is not None and row.updated_by is not None: report["tours"]["admin_skipped"] += 1; continue
            if row is None:
                report["tours"]["inserted"] += 1; row = CatalogTour(id=tid, **values)
                if not dry_run: db.add(row)
            elif any(getattr(row, k) != v for k, v in values.items()):
                report["tours"]["updated"] += 1
                for k, v in values.items(): setattr(row, k, v)
            report["tours"]["published"] += 1 if values["status"] == "published" else 0
            if not dry_run:
                db.flush(); db.execute(delete(CatalogTourHotel).where(CatalogTourHotel.tour_id == tid))
                linked = [h for h in hotel_ids if db.get(CatalogHotel, f"cl-{h}") is not None]
                db.add_all([CatalogTourHotel(tour_id=tid, hotel_id=f"cl-{h}") for h in linked]); report["tours"]["hotel_links"] += len(linked)

        # ---- attractions (the source gives name, city and coordinates)
        for aid, meta in full_meta.items():
            src = next((c for c in controls["catalog_meta"] if str(c["id"]) == aid and c["type"] == "attraction"), None)
            mp = first(meta.get("map")) if src else None
            if src is None or not isinstance(mp, dict): continue
            try: lat, lng = float(mp["lat"]), float(mp["lng"])
            except (KeyError, TypeError, ValueError): continue
            city = geo_place.get(str(first(meta.get("city")) or ""))
            vid = f"cl-attr-{aid}"
            if db.get(CatalogVenue, vid) is None and not dry_run:
                db.add(CatalogVenue(id=vid, kind="attraction", name_fa=src["title"].strip()[:200], name_en=first(meta.get("title-en")), city_id=city.id if city and city.kind == "city" else None, region_id=city.parent_id if city and city.kind == "city" and places.get(city.parent_id or "") and places[city.parent_id].kind == "region" else None,
                                    latitude=lat, longitude=lng, address=str(mp.get("address") or "")[:400] or None, image_url=next((image_url(g) for g in ids_of(meta.get("gallery")) if image_url(g)), None),
                                    quality=1, search_text=normalize_text(src["title"]), source=SOURCE, source_ref=f"attraction/{aid}", source_license=LICENSE, retrieved_on=RETRIEVED))
            report["attractions"] += 1

        # ---- visa articles and the old site's structure
        for x in items.get("visa", []):
            body = text_of(x.get("public_body"))
            if not body or x["status"] != "publish": continue
            cid = f"cl-visa-{x['id']}"; row = db.get(CatalogContent, cid)
            vals = {"kind": "visa", "title": x["title"].strip()[:200], "slug": unquote(x.get("slug") or "")[:200], "body": body, "status": "published", "source": SOURCE, "source_ref": f"visa/{x['id']}", "source_license": LICENSE, "retrieved_on": RETRIEVED}
            if row is None and not dry_run: db.add(CatalogContent(id=cid, **vals))
            elif row is not None:
                for k, v in vals.items(): setattr(row, k, v)
            report["content"] += 1
        for code, place in countries.items():
            note = json.loads(place.details_json or "{}").get("checkline", {}).get("visa_note")
            cid = f"cl-visa-country-{code.lower()}"; row = db.get(CatalogContent, cid)
            if not note: continue
            vals = {"kind": "visa_country", "title": f"ویزای {place.name_fa}", "slug": code.lower(), "body": note, "status": "published", "source": SOURCE, "source_ref": f"country/{code}", "source_license": LICENSE, "retrieved_on": RETRIEVED}
            if row is None and not dry_run: db.add(CatalogContent(id=cid, **vals))
            elif row is not None:
                for k2, v2 in vals.items(): setattr(row, k2, v2)
            report["content"] += 1
        STATIC = {"ثبت شکایت": "/support", "مشاوره گردشگری آنلاین": "/support", "چرا ما را انتخاب می کنید؟": "/about", "جاذبه های گردشگری": "/attractions", "صنایع دستی": "/handicrafts", "رزرو هتل خارجی": "/hotels",
                  "راهنمای خرید هتل": "/hotels", "کشور": "/destinations", "تفریحات کیش": "/attractions", "تورهای ویژه BSI": "/tours/search", "bsi tour": "/tours/search", "بلاگ": "/travel-guides"}
        menu_targets = {str(mi.get("_menu_item_object_id")) for mi in deep["menu_items"] if mi.get("_menu_item_object") == "page"}
        for page in deep["pages"]:
            if page["post_status"] != "publish": continue
            title, slug = (page["post_title"] or "").strip(), unquote(page.get("post_name") or "")
            norm = squash(title)
            target = "/" if slug in ("صفحه-اصلی",) or "صفحه اصلی" in title else "/contact" if slug == "contact" else "/terms" if slug == "site-rules" else "/travel-guides" if slug in ("blog",) or "مجله" in title else "/about" if slug in ("about", "abouttazhban") else None
            if target is None and norm.startswith(squash("هتل های")):
                key = norm[len(squash("هتل های")):]
                c = next((p for p in places.values() if p.kind == "city" and squash(p.name_fa) == key), None) or next((p for p in places.values() if p.kind == "country" and squash(p.name_fa) == key), None)
                target = (f"/hotels?country={c.country_code}&city={c.id}" if c.kind == "city" else f"/hotels?country={c.country_code}") if c else "/hotels"
            if target is None and norm.startswith(squash("تور")):
                key = norm[len(squash("تور")):]
                c = next((p for p in places.values() if p.kind in ("country", "city") and squash(p.name_fa) == key), None)
                target = f"/tours/search?destination={c.id}" if c else "/tours/search"
            if target is None: target = {"flight": "/flights", "hotel": "/hotels", "tour": "/tours/search", "visa": "/visa"}.get(slug) or STATIC.get(title.replace("\u2028", "").strip())
            rid = f"cl-page-{page['ID']}"; row = db.get(CatalogLegacyRoute, rid)
            vals = {"legacy_path": "/" + slug + "/", "title": title[:200], "target_path": target, "in_menu": page["ID"] in menu_targets, "body_chars": int(page.get("body_chars") or 0), "source": SOURCE, "source_ref": f"page/{page['ID']}", "source_license": LICENSE, "retrieved_on": RETRIEVED}
            if row is None and not dry_run: db.add(CatalogLegacyRoute(id=rid, **vals))
            elif row is not None:
                for k, v in vals.items(): setattr(row, k, v)
            report["legacy_routes"] += 1
        if not dry_run: db.commit()
    print(json.dumps({"dry_run": dry_run, **report}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], "--dry-run" in sys.argv, publish="--publish" in sys.argv)
