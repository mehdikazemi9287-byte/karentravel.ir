"""Import staged CheckLine hotels into the master catalog as editable drafts (additive, idempotent).

  DATABASE_URL=... python scripts/catalog/import_checkline.py <staged_dir> [--dry-run] [--only=<legacy_id>,...]

Rules: id is cl-<legacy id> (stable, so a re-run never duplicates); rows land as status=draft and are
published only from the admin panel after review; admin-owned rows (updated_by set) are never
touched; nothing is ever deleted; rows of other sources are never matched or merged (possible
duplicates are only reported). Unknown stays NULL: no price, availability, coordinates, amenities,
rooms or images are derived -- the bundle carries none of them. The CheckLine rating is stored as a
source-reported, unverified star value. Hotels whose country or city has no exact, unique match in
catalog_places are reported, not guessed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select  # noqa: E402

from app.catalog import CatalogHotel, CatalogPlace, normalize_text  # noqa: E402
from app.database import SessionLocal  # noqa: E402

SOURCE, LICENSE, RETRIEVED = "checkline", "CheckLine content; rights unverified", "2026-10-06"
FIELDS = ("slug", "country_code", "region_id", "city_id", "name_fa", "name_en", "hotel_type", "stars", "stars_status", "address", "checkin_time", "checkout_time",
          "search_text", "source", "source_ref", "source_license", "retrieved_on")
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def clock(value) -> str | None:
    """Only an unambiguous 24h clock value is kept; ranges and am/pm prose stay in the staged raw record."""
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})(?::00)?", (value or "").translate(_DIGITS).strip())
    return f"{int(m[1]):02d}:{m[2]}" if m and int(m[1]) < 24 and int(m[2]) < 60 else None


def main(staged_dir: str, dry_run: bool, only: set[str] | None = None) -> dict:
    staged = Path(staged_dir)
    hotels = [json.loads(line)["raw"] for line in (staged / "hotels.jsonl").open(encoding="utf-8")]
    geo = {str(g["id"]): g for g in (json.loads(line)["raw"] for line in (staged / "geography.jsonl").open(encoding="utf-8"))}
    conflict_file = staged / "country-city-mismatches.json"
    conflicts = {str(c["hotel_id"]) for c in json.loads(conflict_file.read_text(encoding="utf-8"))} if conflict_file.exists() else set()
    report = {"input": len(hotels), "inserted": 0, "updated": 0, "unchanged": 0, "admin_owned_skipped": 0, "quarantined": {}, "city_unmatched": 0, "possible_duplicates": []}
    with SessionLocal() as db:
        countries, cities = {}, {}
        for p in db.scalars(select(CatalogPlace).where(CatalogPlace.kind.in_(("country", "city")))):
            target = countries if p.kind == "country" else cities
            for name in {normalize_text(p.name_fa), normalize_text(p.name_en)} - {""}:
                target.setdefault(name if p.kind == "country" else (p.country_code, name), []).append(p)
        other = {}
        for h in db.scalars(select(CatalogHotel).where(CatalogHotel.source != SOURCE)):
            for name in {normalize_text(h.name_fa), normalize_text(h.name_en)} - {""}:
                other.setdefault((h.city_id, name), h.id)

        def quarantine(reason: str) -> None:
            report["quarantined"][reason] = report["quarantined"].get(reason, 0) + 1

        for raw in hotels:
            legacy = str(raw["hotel_id"])
            if only and legacy not in only:
                continue
            title = (raw.get("title") or "").strip()
            g_country = geo.get(str(raw.get("country_id") or ""), {})
            matches = {p.id: p for name in (raw.get("country"), g_country.get("title"), g_country.get("english_title")) for p in countries.get(normalize_text(name), [])}
            if not title:
                quarantine("no_title"); continue
            if len(matches) != 1:
                quarantine("country_not_in_master_catalog"); continue
            country = next(iter(matches.values()))
            g_city = geo.get(str(raw.get("city_id") or ""), {})
            if legacy in conflicts:
                quarantine("country_city_conflict"); continue
            city_matches = {p.id: p for name in (raw.get("city"), g_city.get("title"), g_city.get("english_title")) for p in cities.get((country.country_code, normalize_text(name)), [])}
            city = next(iter(city_matches.values())) if len(city_matches) == 1 else None
            if city is None:
                report["city_unmatched"] += 1
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
            for name in {normalize_text(name_fa), normalize_text(name_en)} - {""}:
                if city and (city.id, name) in other:
                    report["possible_duplicates"].append({"checkline": f"cl-{legacy}", "existing": other[(city.id, name)]}); break
            row = db.get(CatalogHotel, f"cl-{legacy}")
            if row is None:
                report["inserted"] += 1
                if not dry_run:
                    db.add(CatalogHotel(id=f"cl-{legacy}", status="draft", amenities_json="[]", quality=0, **values))
            elif row.source != SOURCE:
                quarantine("id_owned_by_other_source")
            elif row.updated_by is not None:
                report["admin_owned_skipped"] += 1
            elif any(getattr(row, k) != values[k] for k in FIELDS):
                report["updated"] += 1
                if not dry_run:
                    for k in FIELDS: setattr(row, k, values[k])
            else:
                report["unchanged"] += 1
        if not dry_run:
            db.commit()
    report["possible_duplicates_count"] = len(report["possible_duplicates"])
    report["possible_duplicates"] = report["possible_duplicates"][:20]
    print(json.dumps({"dry_run": dry_run, **report}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = next((set(a.split("=", 1)[1].split(",")) for a in sys.argv[1:] if a.startswith("--only=")), None)
    main(args[0], "--dry-run" in sys.argv, only)
