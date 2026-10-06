"""Normalize, validate, deduplicate and enrich raw source data into catalog files.

Input: raw cache written by fetch_osm.py / fetch_reference.py.
Output: backend/catalog_data/*.json.gz + MANIFEST.json (provenance and counts).
Only facts published by the sources are kept; nothing commercial (price, availability,
rooms, ratings, reviews) is produced. Usage: python build_catalog.py <raw_dir> <out_dir>
"""
from __future__ import annotations

import gzip
import json
import math
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.catalog import normalize_text  # noqa: E402

UA = "KarenSeirCatalog/1.0 (catalog import; mehdikazemi.9287@gmail.com)"
TODAY = date.today().isoformat()
OSM = {"source": "openstreetmap", "source_license": "ODbL 1.0 © OpenStreetMap contributors", "retrieved_on": TODAY}
COUNTRIES = {"IR": ("ایران", "Iran", 32.0, 53.0, "Asia/Tehran"), "TR": ("ترکیه", "Turkey", 39.0, 35.0, "Europe/Istanbul"), "AE": ("امارات متحده عربی", "United Arab Emirates", 24.0, 54.0, "Asia/Dubai"),
             "AM": ("ارمنستان", "Armenia", 40.2, 44.9, "Asia/Yerevan"), "GE": ("گرجستان", "Georgia", 42.0, 43.5, "Asia/Tbilisi"), "IQ": ("عراق", "Iraq", 33.0, 44.0, "Asia/Baghdad")}
QID_COUNTRY = {"Q794": "IR", "Q43": "TR", "Q878": "AE", "Q399": "AM", "Q230": "GE", "Q796": "IQ", "Q846": "QA", "Q842": "OM", "Q817": "KW", "Q227": "AZ"}
GENERIC = {normalize_text(x) for x in ("هتل", "hotel", "otel", "مهمانپذیر", "مهمانسرا", "مسافرخانه", "guest house", "guesthouse", "hostel", "motel", "apartment", "apartments", "pansiyon",
                                       "سوئیت", "ویلا", "villa", "resort", "رستوران", "restaurant", "cafe", "کافه", "کافی شاپ", "coffee shop", "استخر", "pool", "موزه", "museum", "فندق", "مطعم")}
FA_RE = re.compile(r"[؀-ۿ]")
FA_DISPLAY = str.maketrans({"\u064a": "\u06cc", "\u0649": "\u06cc", "\u0643": "\u06a9"})  # Persian display forms of Arabic-keyboard letters
STAY_TYPES = {"hotel", "motel", "guest_house", "hostel", "apartment", "chalet"}
VENUE_RULES = [("amenity", {"restaurant": "restaurant", "cafe": "cafe", "events_venue": "event_venue", "conference_centre": "event_venue", "car_rental": "car_rental",
                            "bus_station": "transport_terminal", "ferry_terminal": "transport_terminal"}),
               ("tourism", {"museum": "museum", "attraction": "attraction", "theme_park": "attraction", "zoo": "attraction", "gallery": "attraction", "information": "tourist_info"}),
               ("leisure", {"swimming_pool": "pool_sport", "sports_centre": "pool_sport", "water_park": "pool_sport"}),
               ("shop", {"craft": "handicraft", "carpet": "handicraft", "pottery": "handicraft", "art": "handicraft", "travel_agency": "travel_agency"}),
               ("office", {"travel_agent": "travel_agency"}), ("historic", None)]
RAIL_OPERATORS = [  # official sites checked reachable on the retrieval date; only names shown on the operator's own site
    {"id": "rai", "name_fa": "راه‌آهن جمهوری اسلامی ایران", "name_en": "Islamic Republic of Iran Railways", "operator_kind": "national_infrastructure", "website": "https://www.rai.ir", "source": "wikidata", "source_ref": "Q748603", "source_license": "CC0"},
    {"id": "raja", "name_fa": "شرکت حمل‌ونقل ریلی رجا", "name_en": "Raja Rail Transportation", "operator_kind": "passenger_operator", "website": "https://www.raja.ir", "source": "official_website", "source_ref": "https://www.raja.ir"},
    {"id": "joopar", "name_fa": "جوپار", "name_en": "Joopar", "operator_kind": "passenger_operator", "website": "https://www.joopar.com", "source": "official_website", "source_ref": "https://www.joopar.com"},
]


def http_json(url: str, params: dict) -> dict:
    for attempt in range(5):
        try:
            req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        except Exception:
            time.sleep(5 + attempt * 10)
    return {}


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70]


def km(a_lat, a_lon, b_lat, b_lon) -> float:
    p = math.pi / 180
    h = 0.5 - math.cos((b_lat - a_lat) * p) / 2 + math.cos(a_lat * p) * math.cos(b_lat * p) * (1 - math.cos((b_lon - a_lon) * p)) / 2
    return 12742 * math.asin(math.sqrt(h))


def coords(el: dict):
    c = el.get("center") or el
    return c.get("lat"), c.get("lon")


def names(tags: dict, country: str):
    name = (tags.get("name") or "").strip()
    fa = (tags.get("name:fa") or "").strip() or None
    if fa: fa = fa.translate(FA_DISPLAY)
    en = (tags.get("name:en") or tags.get("int_name") or "").strip() or None
    local = None
    if FA_RE.search(name):
        if country == "IR" and not fa: fa = name.translate(FA_DISPLAY)
        elif country != "IR": local = name
    elif not en and name.isascii(): en = name
    else: local = local or (name if name not in (fa, en) else None)
    return fa, en, local


def address(tags: dict):
    if tags.get("addr:full"): return tags["addr:full"][:400]
    parts = [tags.get("addr:city"), tags.get("addr:suburb"), tags.get("addr:street"), tags.get("addr:housenumber")]
    text = "، ".join(p for p in parts if p)
    return text[:400] or None


def clean_url(value):
    if not value: return None
    value = value.strip().split(";")[0]
    if not re.match(r"^https?://", value): value = "https://" + value
    return value[:300] if re.match(r"^https?://[^\s/]+\.[^\s]+$", value) else None


def amenities(tags: dict) -> list[str]:
    yes = lambda k: tags.get(k) in ("yes", "wlan", "free", "customers", "designated", "limited")  # noqa: E731
    found = []
    if tags.get("internet_access") in ("wlan", "yes", "wifi") or yes("wifi"): found.append("wifi")
    if yes("parking") or tags.get("parking"): found.append("parking")
    if yes("swimming_pool") or yes("pool"): found.append("pool")
    if yes("restaurant"): found.append("restaurant")
    if yes("bar") or yes("cafe"): found.append("bar")
    if yes("air_conditioning"): found.append("air_conditioning")
    if tags.get("wheelchair") in ("yes", "designated"): found.append("accessible")
    if yes("breakfast"): found.append("breakfast")
    if yes("spa") or yes("sauna"): found.append("spa")
    if yes("fitness_centre") or yes("gym"): found.append("fitness")
    if tags.get("pets") == "yes" or tags.get("dog") == "yes": found.append("pets")
    return found


def commons_file(tags: dict):
    value = tags.get("wikimedia_commons") or ""
    if value.startswith("File:"): return value[5:]
    image = tags.get("image") or ""
    match = re.search(r"commons\.wikimedia\.org/wiki/File:([^?#]+)", image) or re.search(r"upload\.wikimedia\.org/wikipedia/commons/(?:thumb/)?\w/\w\w/([^/?#]+)", image)
    return urllib.parse.unquote(match.group(1)) if match else None


def dedupe(records: list[dict], radius_km: float, key=lambda r: "") -> tuple[list[dict], int]:
    """Merge records that share a normalized name (any language) and lie within radius_km."""
    grid: dict = defaultdict(list)
    kept: list[dict] = []
    removed = 0
    records.sort(key=lambda r: -r["_score"])
    for rec in records:
        cell = (round(rec["latitude"] / 0.02), round(rec["longitude"] / 0.02))
        rec_names = {n for n in (normalize_text(rec.get("name_fa")), normalize_text(rec.get("name_en")), normalize_text(rec.get("name_local"))) if n}
        duplicate = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in grid[(cell[0] + dx, cell[1] + dy)]:
                    if key(other) != key(rec): continue
                    same_wd = rec.get("wikidata_id") and rec.get("wikidata_id") == other.get("wikidata_id")
                    if (same_wd or rec_names & other["_names"]) and km(rec["latitude"], rec["longitude"], other["latitude"], other["longitude"]) <= radius_km:
                        duplicate = other; break
                if duplicate: break
            if duplicate: break
        if duplicate:
            removed += 1
            for field, value in rec.items():  # keep the richer record, fill its gaps from the duplicate
                if not field.startswith("_") and value and not duplicate.get(field): duplicate[field] = value
            duplicate["_names"] |= rec_names
            continue
        rec["_names"] = rec_names
        grid[cell].append(rec); kept.append(rec)
    return kept, removed


def wikidata_entities(qids: list[str]) -> dict:
    out = {}
    for i in range(0, len(qids), 50):
        data = http_json("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "labels|claims|descriptions", "languages": "fa|en", "format": "json"})
        for qid, ent in data.get("entities", {}).items():
            claims = ent.get("claims", {})
            def first(prop):
                try: return claims[prop][0]["mainsnak"]["datavalue"]["value"]
                except (KeyError, IndexError): return None
            pop = first("P1082")
            out[qid] = {"fa": ent.get("labels", {}).get("fa", {}).get("value"), "en": ent.get("labels", {}).get("en", {}).get("value"),
                        "desc_fa": ent.get("descriptions", {}).get("fa", {}).get("value"), "image": first("P18"),
                        "population": int(float(pop["amount"])) if isinstance(pop, dict) and pop.get("amount") else None}
        time.sleep(0.5)
    return out


def commons_licenses(files: list[str]) -> dict:
    out = {}
    for i in range(0, len(files), 40):
        data = http_json("https://commons.wikimedia.org/w/api.php", {"action": "query", "titles": "|".join("File:" + f for f in files[i:i + 40]), "prop": "imageinfo",
                                                                    "iiprop": "extmetadata|mime", "iiextmetadatafilter": "LicenseShortName|Artist", "format": "json"})
        normalized = {n["to"]: n["from"] for n in data.get("query", {}).get("normalized", [])}
        for page in data.get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = meta.get("LicenseShortName", {}).get("value", "")
            if not info or not re.match(r"^(CC|Public domain|PD|No restrictions|FAL|GFDL)", lic, re.I) or info.get("mime") not in ("image/jpeg", "image/png", "image/webp", "image/svg+xml"): continue
            artist = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", ""))).strip()[:80] or "ناشناس"
            title = normalized.get(page["title"], page["title"])[5:].replace("_", " ")
            out[title] = (lic, artist)
        time.sleep(0.5)
    return out


def image_fields(file_name, licenses, width=960):
    key = (file_name or "").replace("_", " ")
    if key not in licenses: return None, None
    lic, artist = licenses[key]
    return ("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(key.replace(" ", "_")) + f"?width={width}", f"{artist} · {lic} · Wikimedia Commons")


def main(raw_dir: str, out_dir: str) -> None:
    raw, out = Path(raw_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    regions = json.loads((raw / "_regions.json").read_text())
    stats: Counter = Counter()
    places: dict[str, dict] = {}
    for cc, (fa, en, lat, lon, _tz) in COUNTRIES.items():
        places[cc.lower()] = {"id": cc.lower(), "kind": "country", "parent_id": None, "country_code": cc, "name_fa": fa, "name_en": en, "latitude": lat, "longitude": lon, "source": "iso-3166", "source_ref": cc}
    cities, stays, venues, stations, missing = [], [], [], [], []
    for region in regions:
        rid, cc = region["code"].lower(), region["country"]
        places[rid] = {"id": rid, "kind": "region", "parent_id": cc.lower(), "country_code": cc, "name_fa": region.get("name_fa") or (region["name"] if cc == "IR" else None), "name_en": region.get("name_en"),
                       "name_local": region.get("name"), "latitude": region.get("lat"), "longitude": region.get("lon"), "wikidata_id": region.get("wikidata"), **OSM, "source_ref": "ISO3166-2:" + region["code"]}
        path = raw / f"{region['code']}.json"
        if not path.exists():
            missing.append(region["code"]); continue
        for el in json.loads(path.read_text()):
            tags = el.get("tags", {})
            lat, lon = coords(el)
            if lat is None or not tags.get("name"): continue
            fa, en, local = names(tags, cc)
            base = {"name_fa": fa, "name_en": en, "name_local": local, "country_code": cc, "region_id": rid, "latitude": round(lat, 6), "longitude": round(lon, 6),
                    "wikidata_id": tags.get("wikidata"), "source_ref": f"{el['type']}/{el['id']}", "_tags": tags, "_osm": f"{el['type'][0]}{el['id']}"}
            if tags.get("place") in ("city", "town"):
                pop = re.sub(r"\D", "", tags.get("population", ""))
                cities.append({**base, "_place": tags["place"], "population": int(pop) if pop else None, "_score": (2 if tags["place"] == "city" else 0) + (1 if tags.get("wikidata") else 0) + (int(pop) / 1e7 if pop else 0)}); continue
            stay_type = tags.get("tourism") if tags.get("tourism") in STAY_TYPES else "resort" if tags.get("leisure") == "resort" else None
            if stay_type:
                if any(normalize_text(n) in GENERIC or len(normalize_text(n)) < 3 for n in (fa, en, local) if n) and len({fa, en, local} - {None}) == 1:
                    stats["hotels_dropped_generic_name"] += 1; continue
                stars = re.match(r"^([1-5])", tags.get("stars", ""))
                rec = {**base, "hotel_type": stay_type, "stars": int(stars.group(1)) if stars else None, "address": address(tags), "amenities": amenities(tags),
                       "description": (tags.get("description:fa") or tags.get("description") or None), "checkin_time": tags.get("check_in") or tags.get("checkin"), "checkout_time": tags.get("check_out") or tags.get("checkout"),
                       "phone": (tags.get("phone") or tags.get("contact:phone") or "")[:80] or None, "website": clean_url(tags.get("website") or tags.get("contact:website")), "email": (tags.get("email") or tags.get("contact:email") or "")[:160] or None,
                       "_commons": commons_file(tags)}
                rec["_score"] = sum([3 if rec["stars"] else 0, 2 if stay_type == "hotel" else 0, bool(rec["website"]), bool(rec["phone"]), bool(rec["address"]), bool(fa and en), bool(rec["amenities"]), 2 if rec["wikidata_id"] or rec["_commons"] else 0])
                stays.append(rec); continue
            if cc != "IR": continue
            if tags.get("railway") == "station":
                stations.append({**base, "_score": bool(fa) + bool(en) + bool(tags.get("wikidata"))}); continue
            kind = None
            for tag_key, mapping in VENUE_RULES:
                if tag_key in tags:
                    kind = "historic" if mapping is None else mapping.get(tags[tag_key])
                    if kind: break
            if not kind or (kind == "tourist_info" and tags.get("information") != "office"): continue
            if all(normalize_text(n) in GENERIC or len(normalize_text(n)) < 3 for n in (fa, en, local) if n): stats["venues_dropped_generic_name"] += 1; continue
            rec = {**base, "kind": kind, "address": address(tags), "phone": (tags.get("phone") or tags.get("contact:phone") or "")[:80] or None, "website": clean_url(tags.get("website") or tags.get("contact:website")),
                   "opening_hours": (tags.get("opening_hours") or "")[:200] or None, "detail": (tags.get("cuisine") or tags.get("sport") or tags.get("historic") or tags.get("craft") or "")[:200] or None,
                   "description": tags.get("description:fa") or tags.get("description") or None, "_commons": commons_file(tags)}
            rec["_score"] = sum([bool(rec["website"]), bool(rec["phone"]), bool(rec["address"]), bool(fa and en), bool(rec["opening_hours"]), 3 if rec["wikidata_id"] or rec["_commons"] else 0])
            venues.append(rec)
    stats["raw_hotels"], stats["raw_cities"], stats["raw_venues"], stats["raw_stations"] = len(stays), len(cities), len(venues), len(stations)

    cities, removed = dedupe(cities, 15, key=lambda r: r["country_code"]); stats["dup_cities"] = removed
    stays, removed = dedupe(stays, 0.4, key=lambda r: r["country_code"]); stats["dup_hotels"] = removed
    venues, removed = dedupe(venues, 0.15, key=lambda r: r["kind"]); stats["dup_venues"] = removed
    stations, removed = dedupe(stations, 1.0); stats["dup_stations"] = removed

    qids = sorted({r["wikidata_id"] for r in cities + stays + venues + stations if r.get("wikidata_id")} | {p["wikidata_id"] for p in places.values() if p.get("wikidata_id")})
    wd = wikidata_entities([q for q in qids if re.match(r"^Q\d+$", q)])
    for p in places.values():
        info = wd.get(p.get("wikidata_id") or "", {})
        p["name_fa"] = p.get("name_fa") or info.get("fa"); p["name_en"] = p.get("name_en") or info.get("en"); p["_image"] = info.get("image")
    used_ids: set = set(places)
    for c in cities:
        info = wd.get(c.get("wikidata_id") or "", {})
        c["name_fa"] = c["name_fa"] or info.get("fa"); c["name_en"] = c["name_en"] or info.get("en"); c["population"] = c.get("population") or info.get("population")
        if c["population"] and not 0 < c["population"] < 40_000_000: c["population"] = None  # reject source typos
        if not (c["name_fa"] or c["name_en"]): c["name_en"] = None
        cid = f"{c['country_code'].lower()}-{slugify(c['name_en'] or '') or c['_osm']}"
        if cid in used_ids: cid = f"{cid}-{c['_osm']}"
        used_ids.add(cid); c["id"] = cid
        places[cid] = {"id": cid, "kind": "city", "parent_id": c["region_id"], "country_code": c["country_code"], "name_fa": c["name_fa"], "name_en": c["name_en"], "name_local": c.get("name_local"), "latitude": c["latitude"],
                       "longitude": c["longitude"], "population": c.get("population"), "description": info.get("desc_fa"), "wikidata_id": c.get("wikidata_id"), "_image": info.get("image"), **OSM, "source_ref": c["source_ref"]}
    by_country = defaultdict(list)
    for c in cities: by_country[c["country_code"]].append(c)

    def nearest_city(rec, limit_km):
        """Main city within 20 km wins over its own districts/satellite towns; otherwise the nearest town."""
        best, best_d, city, city_d = None, limit_km, None, 20.0
        for c in by_country[rec["country_code"]]:
            if abs(c["latitude"] - rec["latitude"]) > 0.6: continue
            d = km(rec["latitude"], rec["longitude"], c["latitude"], c["longitude"])
            if d < best_d: best, best_d = c, d
            if c["_place"] == "city" and d < city_d: city, city_d = c, d
        chosen = city or best
        return chosen["id"] if chosen else None

    files = set()
    for rec in stays + venues:
        info = wd.get(rec.get("wikidata_id") or "", {})
        rec["name_fa"] = rec["name_fa"] or info.get("fa"); rec["name_en"] = rec["name_en"] or info.get("en")
        rec["_commons"] = rec.get("_commons") or info.get("image")
        if rec["_commons"]: files.add(rec["_commons"].replace("_", " "))
    files |= {p["_image"].replace("_", " ") for p in places.values() if p.get("_image")}
    licenses = commons_licenses(sorted(files))
    usage = Counter(rec["_commons"].replace("_", " ") for rec in stays + venues if rec.get("_commons"))

    def place_names(pid):
        p = places.get(pid or "")
        return [p.get("name_fa"), p.get("name_en"), p.get("name_local")] if p else []

    def finish(rec, extra_search=()):
        rec["city_id"] = nearest_city(rec, 40)
        file_name = rec.pop("_commons", None)
        # An image is attached only when the source ties it to this exact record; shared files are dropped.
        rec["image_url"], rec["image_credit"] = image_fields(file_name, licenses) if file_name and usage[file_name.replace("_", " ")] == 1 else (None, None)
        rec["search_text"] = normalize_text(" ".join(filter(None, [rec.get("name_fa"), rec.get("name_en"), rec.get("name_local"), *place_names(rec["city_id"]), *place_names(rec["region_id"]), *place_names(rec["country_code"].lower()), *extra_search])))
        rec.update(OSM)

    hotels_out, venue_out, station_out = [], [], []
    for rec in stays:
        finish(rec)
        rec["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "karenseir:hotel:osm:" + rec["source_ref"]))
        rec["slug"] = f"{slugify(rec['name_en'] or '') or 'hotel'}-{rec['_osm']}"
        rec["amenities_json"] = json.dumps(rec.pop("amenities"))
        rec["quality"] = rec["_score"] + (4 if rec["image_url"] else 0) + (1 if rec["city_id"] else 0)
        hotels_out.append({k: v for k, v in rec.items() if not k.startswith("_")})
    for rec in venues:
        finish(rec, extra_search=[rec.get("detail")])
        rec["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "karenseir:venue:osm:" + rec["source_ref"]))
        rec["quality"] = rec["_score"] + (4 if rec["image_url"] else 0)
        venue_out.append({k: v for k, v in rec.items() if not k.startswith("_")})
    for rec in stations:
        rec["city_id"] = nearest_city(rec, 30)
        rec["search_text"] = normalize_text(" ".join(filter(None, [rec.get("name_fa"), rec.get("name_en"), *place_names(rec["city_id"])])))
        rec["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "karenseir:station:osm:" + rec["source_ref"])); rec.update(OSM)
        station_out.append({k: v for k, v in rec.items() if not k.startswith("_") and k not in ("name_local", "wikidata_id")})

    hotel_counts = Counter()
    for h in hotels_out:
        for pid in (h["city_id"], h["region_id"], h["country_code"].lower()):
            if pid: hotel_counts[pid] += 1
    places_out = []
    for p in places.values():
        p["image_url"], p["image_credit"] = image_fields(p.pop("_image", None), licenses, 1200)
        p["hotel_count"] = hotel_counts[p["id"]]
        parent = places.get(p.get("parent_id") or "", {})
        p["search_text"] = normalize_text(" ".join(filter(None, [p.get("name_fa"), p.get("name_en"), p.get("name_local"), parent.get("name_fa") if p["kind"] == "city" else None])))
        if p["kind"] == "city" and not (p.get("name_fa") or p.get("name_en") or p.get("name_local")): continue
        places_out.append(p)

    labels = {}
    for row in json.loads((raw / "_airport_labels.json").read_text()):
        if row.get("fa"): labels[row["iata"]] = (row["fa"], row["item"].rsplit("/", 1)[-1])
    airports_out, seen_iata = [], set()
    for a in json.loads((raw / "_airports.json").read_text()):
        if a["iata_code"] in seen_iata: stats["dup_airports"] += 1; continue
        seen_iata.add(a["iata_code"])
        rec = {"country_code": a["iso_country"], "latitude": float(a["latitude_deg"]), "longitude": float(a["longitude_deg"])}
        fa = labels.get(a["iata_code"], (None, None))[0]
        if fa: fa = fa.translate(FA_DISPLAY).replace("بینالمللی", "بین\u200cالمللی")
        city_id = nearest_city(rec, 70)
        airports_out.append({"id": a["iata_code"], "icao_code": (a.get("icao_code") or a.get("gps_code") or "")[:4] or None, "name_fa": fa, "name_en": a["name"], "city_id": city_id, "city_name": (places.get(city_id or "", {}).get("name_fa") or a.get("municipality") or None), **rec,
                             "timezone": COUNTRIES[a["iso_country"]][4], "scope": "international" if "international" in a["name"].lower() else None, "airport_type": a["type"], "scheduled_service": a["scheduled_service"] == "yes",
                             "search_text": normalize_text(" ".join(filter(None, [fa, a["name"], a["iata_code"], a.get("municipality"), *place_names(city_id)]))),
                             "source": "ourairports", "source_ref": a["ident"], "source_license": "Public domain (OurAirports); Persian name: Wikidata CC0", "retrieved_on": TODAY})

    airline_rows = defaultdict(list)
    for row in json.loads((raw / "_airlines.json").read_text()): airline_rows[row["item"].rsplit("/", 1)[-1]].append(row)
    type_labels = {"Q46970": "airline", "Q1057026": "low_cost", "Q1757562": "flag_carrier", "Q1362225": "charter", "Q1349587": "cargo", "Q9385390": "regional"}
    airlines, logo_files = [], set()
    for qid, rows in airline_rows.items():
        first = rows[0]
        if any(r.get("end") for r in rows): stats["airlines_dropped_dissolved"] += 1; continue
        if not (first.get("fa") or first.get("en")): continue
        types = {r.get("type", "").rsplit("/", 1)[-1] for r in rows}
        logo = urllib.parse.unquote(first["logo"].rsplit("/", 1)[-1]).replace("_", " ") if first.get("logo") else None
        if logo: logo_files.add(logo)
        airlines.append({"id": qid, "iata_code": first["iata"][:3], "icao_code": (first.get("icao") or "")[:4] or None, "name_fa": first.get("fa"), "name_en": first.get("en"), "country_code": QID_COUNTRY[first["c"].rsplit("/", 1)[-1]],
                         "airline_type": next((type_labels[t] for t in ("Q1757562", "Q1057026", "Q1362225", "Q1349587", "Q9385390") if t in types), "airline"), "website": clean_url(first.get("web")), "_logo": logo,
                         "search_text": normalize_text(" ".join(filter(None, [first.get("fa"), first.get("en"), first["iata"], first.get("icao")]))), "source": "wikidata", "source_ref": qid, "source_license": "CC0 (logo: see logo_credit)", "retrieved_on": TODAY})
    logo_lic = commons_licenses(sorted(logo_files))
    by_key = {}
    for a in sorted(airlines, key=lambda r: -(bool(r["name_fa"]) + bool(r["icao_code"]) + bool(r["website"]) + bool(r["_logo"]))):
        key = (a["iata_code"], normalize_text(a["name_en"] or a["name_fa"]))
        if key in by_key: stats["dup_airlines"] += 1; continue
        a["logo_url"], a["logo_credit"] = image_fields(a.pop("_logo"), logo_lic, 240)
        by_key[key] = a
    airlines_out = list(by_key.values())
    rail_ops = [{**op, "brands_json": "[]", "country_code": "IR", "retrieved_on": TODAY} for op in RAIL_OPERATORS]

    datasets = {"places": places_out, "hotels": hotels_out, "airlines": airlines_out, "airports": airports_out, "rail_operators": rail_ops, "rail_stations": station_out, "venues": venue_out}
    for name, rows in datasets.items():
        with gzip.open(out / f"{name}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))
    manifest = {"generated_on": TODAY, "counts": {k: len(v) for k, v in datasets.items()}, "hotels_by_country": dict(Counter(h["country_code"] for h in hotels_out)),
                "venues_by_kind": dict(Counter(v["kind"] for v in venue_out)), "hotels_with_image": sum(1 for h in hotels_out if h["image_url"]), "places_with_image": sum(1 for p in places_out if p["image_url"]),
                "venues_with_image": sum(1 for v in venue_out if v["image_url"]), "airlines_with_logo": sum(1 for a in airlines_out if a["logo_url"]), "cities_with_hotels": sum(1 for p in places_out if p["kind"] == "city" and p["hotel_count"]),
                "stats": dict(stats), "regions_missing_raw": missing, "commercial_records": 0,
                "sources": {"openstreetmap": "Hotels, places, venues, rail stations — © OpenStreetMap contributors, ODbL 1.0 (overpass-api.de)", "wikidata": "Airlines, Persian labels, populations — CC0",
                            "ourairports": "Airports — public domain (ourairports.com)", "wikimedia_commons": "Images/logos — per-file licence and author stored in image_credit/logo_credit",
                            "official_website": "Rail operators — operator's own website"}}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False)[:1800])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
