"""Add airports of the countries already in the catalogue from the OurAirports table (public domain). Additive only.

Usage: python scripts/catalog/import_airports_reference.py <airports.csv> [--dry-run]
Only airports with an IATA code and scheduled service, of type large_airport or medium_airport, in a country that has a
country record. An airport that already exists is never touched (whatever its source, and whether or not a reviewer edited it).
The city is linked only when exactly one city of that country carries the municipality name; the Persian name is left empty.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select  # noqa: E402

from app.catalog import CatalogAirport, CatalogPlace, normalize_text  # noqa: E402
from app.database import SessionLocal  # noqa: E402

LICENSE, RETRIEVED = "Public domain (OurAirports)", "2026-10-07"


def main(csv_path: str, dry_run: bool) -> dict:
    report = {"input": 0, "eligible": 0, "inserted": 0, "existing": 0, "city_linked": 0, "countries": 0}
    with SessionLocal() as db, open(csv_path, encoding="utf-8", newline="") as fh:
        countries = set(db.scalars(select(CatalogPlace.country_code).where(CatalogPlace.kind == "country")))
        cities: dict[tuple[str, str], list[str]] = {}
        for pid, code, name in db.execute(select(CatalogPlace.id, CatalogPlace.country_code, CatalogPlace.name_en).where(CatalogPlace.kind == "city", CatalogPlace.name_en.is_not(None))):
            cities.setdefault((code, name.strip().lower()), []).append(pid)
        have = set(db.scalars(select(CatalogAirport.id))); added_countries = set()
        for r in csv.DictReader(fh):
            report["input"] += 1
            iata, code = (r["iata_code"] or "").strip().upper(), (r["iso_country"] or "").strip().upper()
            if len(iata) != 3 or not iata.isalpha() or code not in countries or r["type"] not in ("large_airport", "medium_airport") or r["scheduled_service"] != "yes" or not r["name"].strip(): continue
            try: lat, lng = float(r["latitude_deg"]), float(r["longitude_deg"])
            except ValueError: continue
            report["eligible"] += 1
            if iata in have: report["existing"] += 1; continue
            have.add(iata); town = (r["municipality"] or "").strip() or None
            match = cities.get((code, town.lower()), []) if town else []
            city_id = match[0] if len(match) == 1 else None
            report["inserted"] += 1; report["city_linked"] += 1 if city_id else 0; added_countries.add(code)
            if not dry_run:
                db.add(CatalogAirport(id=iata, icao_code=(r["icao_code"] or r["gps_code"] or "").strip()[:4] or None, name_en=r["name"].strip()[:200], city_id=city_id, city_name=town[:160] if town else None, country_code=code, latitude=lat, longitude=lng,
                                      airport_type=r["type"], scheduled_service=True, search_text=normalize_text(" ".join(filter(None, [r["name"], iata, town])))[:2000], source="ourairports", source_ref=r["ident"], source_license=LICENSE, retrieved_on=RETRIEVED))
        report["countries"] = len(added_countries)
        if not dry_run: db.commit()
    print(json.dumps({"dry_run": dry_run, **report}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("--")][0], "--dry-run" in sys.argv)
