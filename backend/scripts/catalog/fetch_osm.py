"""Fetch raw catalog source data from OpenStreetMap (Overpass API), one file per region.

Source licence: OpenStreetMap contributors, ODbL 1.0. Raw output is a cache, not committed.
Usage: python fetch_osm.py <raw_dir> [IR|OTHER]  (two workers may run in parallel; finished regions are skipped)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINTS = ["https://lz4.overpass-api.de/api/interpreter", "https://overpass-api.de/api/interpreter"]
UA = "KarenSeirCatalog/1.0 (catalog import; mehdikazemi.9287@gmail.com)"
STAY = 'nwr[tourism~"^(hotel|motel|guest_house|hostel|apartment|chalet)$"][name](area.a);nwr[leisure=resort][name](area.a);'
PLACES = 'node[place~"^(city|town)$"][name](area.a);'
IRAN_EXTRA = (
    'nwr[railway=station][name][station!=subway][station!=light_rail](area.a);'
    'nwr[tourism~"^(attraction|museum|theme_park|zoo|gallery)$"][name](area.a);'
    'nwr[historic~"^(castle|fort|monument|archaeological_site|ruins|city_gate|palace|caravanserai|tomb|bridge)$"][name](area.a);'
    'nwr[amenity~"^(restaurant|cafe)$"][name](area.a);'
    'nwr[leisure~"^(swimming_pool|sports_centre|water_park)$"][name](area.a);'
    'nwr[amenity~"^(events_venue|conference_centre)$"][name](area.a);'
    'nwr[amenity=car_rental][name](area.a);'
    'nwr[shop~"^(craft|carpet|pottery|art)$"][name](area.a);'
    'nwr[shop=travel_agency][name](area.a);nwr[office=travel_agent][name](area.a);'
    'nwr[tourism=information][information=office][name](area.a);'
    'nwr[amenity~"^(bus_station|ferry_terminal)$"][name](area.a);'
)
# Whole-country coverage except Turkey, where the tourism provinces relevant to the Iranian market are used.
TURKEY = ["TR-34", "TR-07", "TR-65", "TR-06", "TR-35", "TR-09", "TR-48", "TR-61", "TR-50", "TR-16", "TR-25", "TR-42", "TR-53"]
COUNTRIES = ["IR", "AE", "AM", "GE", "IQ"]


def overpass(query: str) -> dict:
    last = None
    for attempt in range(40):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=200) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # rate limit / gateway timeout: back off and retry
            last = exc
            time.sleep(min(8 + attempt * 4, 45))
    raise RuntimeError(f"overpass failed: {last}")


def main(raw_dir: str, only: str = "") -> None:
    out = Path(raw_dir)
    out.mkdir(parents=True, exist_ok=True)
    regions_file = out / "_regions.json"
    if regions_file.exists():
        regions = json.loads(regions_file.read_text())
    else:
        regions = []
        for cc in COUNTRIES + ["TR"]:
            data = overpass(f'[out:json][timeout:120];rel["ISO3166-2"~"^{cc}-"][boundary=administrative];out tags center;')
            for el in data["elements"]:
                tags = el["tags"]
                code = tags["ISO3166-2"]
                if cc == "TR" and code not in TURKEY:
                    continue
                regions.append({"code": code, "country": cc, "name": tags.get("name"), "name_fa": tags.get("name:fa"), "name_en": tags.get("name:en"),
                                "wikidata": tags.get("wikidata"), "lat": el.get("center", {}).get("lat"), "lon": el.get("center", {}).get("lon")})
            time.sleep(5)
        regions = list({r["code"]: r for r in regions}.values())
        regions_file.write_text(json.dumps(regions, ensure_ascii=False))
    print("regions", len(regions), flush=True)
    for region in regions:
        if only and (region["country"] == "IR") != (only == "IR"):
            continue
        target = out / f"{region['code']}.json"
        if target.exists():
            continue
        # Dense regions time out as one query, so each tag group is fetched separately and merged.
        parts = [STAY + PLACES] + ([clause + ";" for clause in IRAN_EXTRA.split(";") if clause] if region["country"] == "IR" else [])
        elements = {}
        for part in parts:
            data = overpass(f'[out:json][timeout:180];area["ISO3166-2"="{region["code"]}"]->.a;({part});out center tags;')
            for el in data["elements"]:
                elements[(el["type"], el["id"])] = el
            time.sleep(1)
        target.write_text(json.dumps(list(elements.values()), ensure_ascii=False))
        print(region["code"], len(elements), flush=True)
        time.sleep(2)
    print("DONE", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
