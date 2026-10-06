"""Import staged CheckLine hotels into the master catalog as editable drafts (additive, idempotent).

  DATABASE_URL=... python scripts/catalog/import_checkline.py <staged_dir> [--dry-run] [--only=<legacy_id>,...]

Identity: id is cl-<legacy id>, so a re-run never duplicates. Rows land as status=draft and are published only
from the admin panel. Admin-owned rows (updated_by set) are never touched; nothing is ever deleted.
Unknown stays NULL: no price, availability, coordinates, amenities, rooms, images or description are derived.
The CheckLine rating is kept as a source-reported, unverified star value.

Reference data (additive, with provenance): a country missing from catalog_places is added only when its
CheckLine English title is an exact ISO 3166-1 short name in ISO below; a city is added only from a CheckLine
geography row of type city whose own country resolves to the same ISO code. Neither gets coordinates.

Duplicates: pairs are found by an exact normalised name within the same city. Name alone only records a
*proposed* pair for a reviewer. A pair is linked automatically (duplicate_of, never deleted, never merged)
only when the two addresses also share a number and a distinctive word. Reviewer decisions are never changed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select  # noqa: E402

from app.catalog import CatalogHotel, CatalogHotelMatch, CatalogPlace, normalize_text  # noqa: E402
from app.database import SessionLocal  # noqa: E402

SOURCE, LICENSE, RETRIEVED = "checkline", "CheckLine content; rights unverified", "2026-10-06"
FIELDS = ("slug", "country_code", "region_id", "city_id", "name_fa", "name_en", "hotel_type", "stars", "stars_status", "address", "checkin_time", "checkout_time",
          "search_text", "source", "source_ref", "source_license", "retrieved_on")
ISO = {"thailand": ("TH", "Thailand"), "türkiye": ("TR", "Türkiye"), "turkey": ("TR", "Türkiye"), "france": ("FR", "France"), "morocco": ("MA", "Morocco"), "georgia": ("GE", "Georgia"),
       "armenia": ("AM", "Armenia"), "greece": ("GR", "Greece"), "india": ("IN", "India"), "iran": ("IR", "Iran"), "iraq": ("IQ", "Iraq"), "djibouti": ("DJ", "Djibouti"), "japan": ("JP", "Japan"),
       "jordan": ("JO", "Jordan"), "kazakhstan": ("KZ", "Kazakhstan"), "north korea": ("KP", "North Korea"), "south korea": ("KR", "South Korea"), "kuwait": ("KW", "Kuwait"),
       "kyrgyzstan": ("KG", "Kyrgyzstan"), "lebanon": ("LB", "Lebanon"), "maldives": ("MV", "Maldives"), "mongolia": ("MN", "Mongolia"), "nepal": ("NP", "Nepal"), "oman": ("OM", "Oman"),
       "pakistan": ("PK", "Pakistan"), "philippines": ("PH", "Philippines"), "qatar": ("QA", "Qatar"), "saudi arabia": ("SA", "Saudi Arabia"), "singapore": ("SG", "Singapore"),
       "sri lanka": ("LK", "Sri Lanka"), "syria": ("SY", "Syria"), "taiwan": ("TW", "Taiwan"), "tajikistan": ("TJ", "Tajikistan"), "turkmenistan": ("TM", "Turkmenistan"), "vietnam": ("VN", "Vietnam"),
       "united arab emirates": ("AE", "United Arab Emirates"), "uzbekistan": ("UZ", "Uzbekistan"), "yemen": ("YE", "Yemen"), "spain": ("ES", "Spain"), "russia": ("RU", "Russia"),
       "brazil": ("BR", "Brazil"), "canada": ("CA", "Canada"), "malaysia": ("MY", "Malaysia"), "netherlands": ("NL", "Netherlands"), "belgium": ("BE", "Belgium"), "china": ("CN", "China"),
       "italy": ("IT", "Italy"), "bahrain": ("BH", "Bahrain"), "cyprus": ("CY", "Cyprus"), "indonesia": ("ID", "Indonesia"), "afghanistan": ("AF", "Afghanistan")}
GENERIC = {"hotel", "هتل", "street", "avenue", "road", "str", "city", "floor", "near", "square", "district", "building"}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def clock(value) -> str | None:
    """Only an unambiguous 24h clock value is kept; ranges and am/pm prose stay in the staged raw record."""
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})(?::00)?", (value or "").translate(_DIGITS).strip())
    return f"{int(m[1]):02d}:{m[2]}" if m and int(m[1]) < 24 and int(m[2]) < 60 else None


def squash(value) -> str:
    return normalize_text(value).replace(" ", "")


def name_keys(*names) -> set[str]:
    keys = {" ".join(w for w in normalize_text(n).split() if w not in GENERIC) for n in names if n}
    return {k for k in keys if len(k) >= 4}


def address_evidence(a, b, ignore: set[str]) -> bool:
    def parts(text):
        text = normalize_text((text or "").translate(_DIGITS))
        return set(re.findall(r"\d+", text)), {w for w in re.findall(r"[^\W\d_]{4,}", text) if w not in GENERIC and w not in ignore}
    (na, wa), (nb, wb) = parts(a), parts(b)
    return bool(na & nb) and bool(wa & wb)


def main(staged_dir: str, dry_run: bool, only: set[str] | None = None) -> dict:
    staged = Path(staged_dir)
    hotels = [json.loads(line)["raw"] for line in (staged / "hotels.jsonl").open(encoding="utf-8")]
    geo = {str(g["id"]): g for g in (json.loads(line)["raw"] for line in (staged / "geography.jsonl").open(encoding="utf-8"))}
    conflict_file = staged / "country-city-mismatches.json"
    conflicts = {str(c["hotel_id"]) for c in json.loads(conflict_file.read_text(encoding="utf-8"))} if conflict_file.exists() else set()
    report = {"input": len(hotels), "inserted": 0, "updated": 0, "unchanged": 0, "admin_owned_skipped": 0, "quarantined": {}, "city_unresolved": 0,
              "countries_added": [], "cities_added": 0, "matches": {"auto_linked": 0, "proposed": 0, "kept_decisions": 0}}
    with SessionLocal() as db:
        countries = {p.country_code: p for p in db.scalars(select(CatalogPlace).where(CatalogPlace.kind == "country"))}
        cities: dict[tuple[str, str], list[CatalogPlace]] = {}
        for p in db.scalars(select(CatalogPlace).where(CatalogPlace.kind == "city").order_by(CatalogPlace.id)):
            for name in {squash(p.name_fa), squash(p.name_en)} - {""}:
                cities.setdefault((p.country_code, name), []).append(p)

        def quarantine(reason: str) -> None:
            report["quarantined"][reason] = report["quarantined"].get(reason, 0) + 1

        def iso_of(g: dict) -> tuple[str, str] | None:
            return ISO.get((g.get("english_title") or "").strip().lower()) if g.get("type") == "country" else None

        def country_for(raw: dict) -> CatalogPlace | None:
            g = geo.get(str(raw.get("country_id") or ""), {})
            iso = iso_of(g)
            if iso is None:
                return None
            code, english = iso
            if code not in countries:
                place = CatalogPlace(id=code.lower(), kind="country", country_code=code, name_fa=(g.get("title") or "").strip() or None, name_en=english, hotel_count=0,
                                     search_text=normalize_text(f"{g.get('title') or ''} {english}"), source="iso3166-1", source_ref=code,
                                     source_license="ISO 3166-1 code; Persian name as recorded by CheckLine", retrieved_on=RETRIEVED)
                countries[code] = place
                report["countries_added"].append(code)
                if not dry_run:
                    db.add(place); db.flush()
            return countries[code]

        def city_for(raw: dict, country: CatalogPlace) -> CatalogPlace | None:
            g = geo.get(str(raw.get("city_id") or ""), {})
            found = {p.id: p for name in (raw.get("city"), g.get("title"), g.get("english_title")) for p in cities.get((country.country_code, squash(name)), [])}
            if len(found) == 1:
                return next(iter(found.values()))
            if found or g.get("type") != "city" or not (g.get("title") or "").strip():
                return None  # ambiguous, or the source row is not a city: unresolved, never guessed
            if (iso_of(geo.get(str(g.get("country_id") or ""), {})) or ("",))[0] != country.country_code:
                return None  # the city's own country disagrees with the hotel's
            english = (g.get("english_title") or "").strip().strip("َُ") or None
            place = CatalogPlace(id=f"cl-city-{g['id']}", kind="city", parent_id=country.id, country_code=country.country_code, name_fa=g["title"].strip(), name_en=english.title() if english and english.islower() else english,
                                 hotel_count=0, search_text=normalize_text(f"{g['title']} {english or ''} {country.name_fa or ''} {country.name_en or ''}"), source=SOURCE, source_ref=f"geography/{g['id']}",
                                 source_license=LICENSE, retrieved_on=RETRIEVED)
            for name in {squash(place.name_fa), squash(place.name_en)} - {""}:
                cities.setdefault((country.country_code, name), []).append(place)
            report["cities_added"] += 1
            if not dry_run:
                db.add(place); db.flush()
            return place

        touched: list[str] = []
        for raw in hotels:
            legacy = str(raw["hotel_id"])
            if only and legacy not in only:
                continue
            title = (raw.get("title") or "").strip()
            if not title:
                quarantine("no_title"); continue
            if legacy in conflicts:
                quarantine("country_city_conflict"); continue
            country = country_for(raw)
            if country is None:
                quarantine("country_unresolved"); continue
            city = city_for(raw, country)
            if city is None:
                report["city_unresolved"] += 1
            english = re.search(r"\(([A-Za-z0-9][^()]*)\)\s*$", title)
            latin = not re.search(r"[؀-ۿ]", title)
            name_fa = None if latin else re.sub(r"\s*\([A-Za-z0-9][^()]*\)\s*$", "", title).strip()[:200]
            name_en = (title if latin else english[1].strip() if english else None)
            rating = str(raw.get("rating_current_unverified") or "").strip()
            stars = int(rating) if rating in {"1", "2", "3", "4", "5"} else None
            address = (raw.get("address_current") or "").strip()[:400] or None
            values = {"slug": f"checkline-{legacy}", "country_code": country.country_code, "region_id": city.parent_id if city and city.parent_id != country.id else None,
                      "city_id": city.id if city else None, "name_fa": name_fa, "name_en": name_en[:200] if name_en else None, "hotel_type": "hotel", "stars": stars,
                      "stars_status": "source_reported" if stars else None, "address": address, "checkin_time": clock(raw.get("check_in_current")),
                      "checkout_time": clock(raw.get("check_out_current")),
                      "search_text": normalize_text(" ".join(filter(None, [name_fa, name_en, city.search_text if city else raw.get("city"), country.name_fa, address]))),
                      "source": SOURCE, "source_ref": f"hotel/{legacy}", "source_license": LICENSE, "retrieved_on": RETRIEVED}
            row = db.get(CatalogHotel, f"cl-{legacy}")
            if row is None:
                report["inserted"] += 1
                if not dry_run:
                    db.add(CatalogHotel(id=f"cl-{legacy}", status="draft", amenities_json="[]", quality=0, content_complete=False, **values))
            elif row.source != SOURCE:
                quarantine("id_owned_by_other_source"); continue
            elif row.updated_by is not None:
                report["admin_owned_skipped"] += 1
            elif any(getattr(row, k) != values[k] for k in FIELDS):
                report["updated"] += 1
                if not dry_run:
                    for k in FIELDS: setattr(row, k, values[k])
            else:
                report["unchanged"] += 1
            touched.append(f"cl-{legacy}")
        if not dry_run:
            db.flush()
            _match(db, touched, report)
            db.commit()
    print(json.dumps({"dry_run": dry_run, **report}, ensure_ascii=False))
    return report


def _match(db, ids: list[str], report: dict) -> None:
    legacy = lambda h: int(h.id[3:]) if h.id.startswith("cl-") and h.id[3:].isdigit() else -1  # noqa: E731
    place_words = {w for p in db.scalars(select(CatalogPlace).where(CatalogPlace.kind.in_(("country", "city")))) for n in (p.name_fa, p.name_en) for w in normalize_text(n).split()}
    index: dict[tuple[str, str], list[CatalogHotel]] = {}
    for h in db.scalars(select(CatalogHotel).where(CatalogHotel.city_id.is_not(None)).order_by(CatalogHotel.id)):
        for key in name_keys(h.name_fa, h.name_en, h.name_local):
            index.setdefault((h.city_id, key), []).append(h)
    existing = {(m.hotel_id, m.candidate_id): m for m in db.scalars(select(CatalogHotelMatch))}
    for hid in sorted(ids, key=lambda i: int(i[3:])):
        row = db.get(CatalogHotel, hid)
        if row is None or row.city_id is None:
            continue
        candidates = {c.id: c for key in name_keys(row.name_fa, row.name_en) for c in index.get((row.city_id, key), [])
                      if c.id != row.id and (c.source != SOURCE or legacy(c) < legacy(row))}
        seen: set[str] = set()
        for cand in sorted(candidates.values(), key=lambda c: (c.source == SOURCE, legacy(c), c.id)):  # a non-CheckLine record is the preferred canonical
            canonical = cand
            while canonical.duplicate_of and canonical.duplicate_of != row.id:
                canonical = db.get(CatalogHotel, canonical.duplicate_of)
            if canonical.id == row.id or canonical.id in seen:
                continue
            seen.add(canonical.id)
            strong = address_evidence(row.address, cand.address, place_words)
            match = existing.get((row.id, canonical.id))
            if match is not None and match.decided_by is not None:
                report["matches"]["kept_decisions"] += 1
                continue
            basis, status = ("name+city+address", "confirmed") if strong else ("name+city", "proposed")
            if match is None:
                match = CatalogHotelMatch(hotel_id=row.id, candidate_id=canonical.id, basis=basis, status=status)
                db.add(match); existing[(row.id, canonical.id)] = match
            else:
                match.basis, match.status = basis, status
            if strong and row.updated_by is None and row.duplicate_of is None:
                row.duplicate_of, row.match_basis = canonical.id, basis
            report["matches"]["auto_linked" if strong else "proposed"] += 1
        db.flush()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = next((set(a.split("=", 1)[1].split(",")) for a in sys.argv[1:] if a.startswith("--only=")), None)
    main(args[0], "--dry-run" in sys.argv, only)
