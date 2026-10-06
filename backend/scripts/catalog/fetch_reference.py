"""Fetch airport and airline reference data.

Sources: OurAirports (public domain) for airports; Wikidata (CC0) for airlines and Persian labels.
Usage: python fetch_reference.py <raw_dir>
"""
from __future__ import annotations

import csv
import io
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = "KarenSeirCatalog/1.0 (catalog import; mehdikazemi.9287@gmail.com)"
MARKET = {"IR": "Q794", "TR": "Q43", "AE": "Q878", "AM": "Q399", "GE": "Q230", "IQ": "Q796"}
AIRLINE_COUNTRIES = {**MARKET, "QA": "Q846", "OM": "Q842", "KW": "Q817", "AZ": "Q227"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"}), timeout=180) as resp:
        return resp.read()


def sparql(query: str) -> list[dict]:
    data = json.loads(get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(query)))
    return [{k: v["value"] for k, v in row.items()} for row in data["results"]["bindings"]]


def main(raw_dir: str) -> None:
    out = Path(raw_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(io.StringIO(get("https://davidmegginson.github.io/ourairports-data/airports.csv").decode("utf-8"))))
    airports = [r for r in rows if r["iso_country"] in MARKET and r["iata_code"] and r["type"] in ("large_airport", "medium_airport", "small_airport")]
    (out / "_airports.json").write_text(json.dumps(airports, ensure_ascii=False))
    values = " ".join(f"wd:{q}" for q in MARKET.values())
    labels = sparql(f'SELECT ?iata ?fa ?item WHERE {{ VALUES ?c {{ {values} }} ?item wdt:P238 ?iata; wdt:P17 ?c. OPTIONAL {{ ?item rdfs:label ?fa FILTER(lang(?fa)="fa") }} }}')
    (out / "_airport_labels.json").write_text(json.dumps(labels, ensure_ascii=False))
    values = " ".join(f"wd:{q}" for q in AIRLINE_COUNTRIES.values())
    airlines = sparql(
        "SELECT ?item ?iata ?icao ?en ?fa ?c ?web ?logo ?end ?type WHERE { VALUES ?c { " + values + " } "
        "?item wdt:P31/wdt:P279* wd:Q46970; wdt:P229 ?iata; wdt:P17 ?c. "
        "OPTIONAL { ?item wdt:P230 ?icao } OPTIONAL { ?item wdt:P856 ?web } OPTIONAL { ?item wdt:P154 ?logo } "
        "OPTIONAL { ?item wdt:P576 ?end } OPTIONAL { ?item wdt:P31 ?type } "
        'OPTIONAL { ?item rdfs:label ?en FILTER(lang(?en)="en") } OPTIONAL { ?item rdfs:label ?fa FILTER(lang(?fa)="fa") } }')
    (out / "_airlines.json").write_text(json.dumps(airlines, ensure_ascii=False))
    print("airports", len(airports), "labels", len(labels), "airline rows", len(airlines))


if __name__ == "__main__":
    main(sys.argv[1])
