"""Add airlines of the countries already in the catalogue from Wikidata (CC0). Additive only.

Usage: python scripts/catalog/import_airlines_reference.py --fetch <out.json>      (network; run once)
       python scripts/catalog/import_airlines_reference.py <fetched.json> [--dry-run]
Only airlines that carry an IATA and an ICAO code, a country and no dissolution date. An airline already in the catalogue
(same Wikidata item, or same IATA code in the same country) is never touched. Where several items share one IATA code in a
country (a carrier and its cargo arm, for instance) the one with the most Wikipedia articles is taken. No logo is taken: its licence differs per file.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

LICENSE, RETRIEVED = "Wikidata CC0", "2026-10-07"
QUERY = ('SELECT ?item ?iata ?icao ?iso ?web ?en ?fa ?links WHERE { ?item wdt:P31/wdt:P279* wd:Q46970; wdt:P229 ?iata; wdt:P230 ?icao; wdt:P17 ?c; wikibase:sitelinks ?links. ?c wdt:P297 ?iso. '
         'FILTER NOT EXISTS { ?item wdt:P576 ?end } OPTIONAL { ?item wdt:P856 ?web } OPTIONAL { ?item rdfs:label ?en FILTER(lang(?en)="en") } OPTIONAL { ?item rdfs:label ?fa FILTER(lang(?fa)="fa") } }')


def fetch(out: str) -> None:
    req = urllib.request.Request("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(QUERY), headers={"User-Agent": "KarenSeirCatalog/1.0 (reference data)", "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=180) as resp: rows = json.loads(resp.read())["results"]["bindings"]
    Path(out).write_text(json.dumps([{k: v["value"] for k, v in r.items()} for r in rows], ensure_ascii=False), encoding="utf-8"); print("rows", len(rows))


def main(path: str, dry_run: bool) -> dict:
    from sqlalchemy import select

    from app.catalog import CatalogAirline, CatalogPlace, normalize_text
    from app.database import SessionLocal
    report = {"input": 0, "inserted": 0, "existing": 0, "outside_catalogue_countries": 0, "countries": 0}
    by_item: dict[str, dict] = {}
    for r in json.loads(Path(path).read_text(encoding="utf-8")):
        qid = r["item"].rsplit("/", 1)[-1]; cur = by_item.setdefault(qid, {"countries": set(), **r}); cur["countries"].add(r["iso"].upper())
        for k in ("web", "en", "fa"): cur.setdefault(k, r.get(k))
    with SessionLocal() as db:
        countries = set(db.scalars(select(CatalogPlace.country_code).where(CatalogPlace.kind == "country")))
        have_ids = set(db.scalars(select(CatalogAirline.id))); have_codes = {(a, b) for a, b in db.execute(select(CatalogAirline.iata_code, CatalogAirline.country_code))}; added = set()
        for qid, r in sorted(by_item.items(), key=lambda kv: (-int(kv[1].get("links") or 0), kv[0])):
            report["input"] += 1
            iata, icao, name = r["iata"].strip().upper(), r["icao"].strip().upper(), (r.get("en") or "").strip()
            if len(r["countries"]) != 1 or len(iata) != 2 or len(icao) != 3 or not name: continue  # one country, well-formed codes, a name
            code = next(iter(r["countries"]))
            if code not in countries: report["outside_catalogue_countries"] += 1; continue
            if qid in have_ids or (iata, code) in have_codes: report["existing"] += 1; continue
            have_ids.add(qid); have_codes.add((iata, code)); added.add(code); report["inserted"] += 1
            web = r.get("web") if (r.get("web") or "").startswith("https://") and len(r["web"]) <= 300 else None
            if not dry_run:
                db.add(CatalogAirline(id=qid, iata_code=iata, icao_code=icao, name_fa=(r.get("fa") or "").strip()[:160] or None, name_en=name[:160], country_code=code, airline_type="airline", website=web,
                                      search_text=normalize_text(" ".join(filter(None, [r.get("fa"), name, iata, icao])))[:2000], source="wikidata", source_ref=qid, source_license=LICENSE, retrieved_on=RETRIEVED))
        report["countries"] = len(added)
        if not dry_run: db.commit()
    print(json.dumps({"dry_run": dry_run, **report}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fetch(args[0]) if "--fetch" in sys.argv else main(args[0], "--dry-run" in sys.argv)
