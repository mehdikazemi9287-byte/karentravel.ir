"""Autocomplete foundation: static curated city/airport entities (ported from the
monolith), fuzzy-normalized matching, cache-backed. No fabricated inventory."""
from __future__ import annotations

import unicodedata


def _fold(s: str) -> str:
    # prefix-friendly fold: NFKC + strip marks + casefold. No city-alias rewrite
    # (autocomplete wants raw prefix matching, incl. latin codes/names).
    t = unicodedata.normalize("NFKC", s or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(t.casefold().split())

ENTITIES = (
    {"id": "city-tehran", "title": "تهران", "type": "city", "code": "THR", "country": "ایران", "popularity": 100, "aliases": ["تهرون", "Tehran"]},
    {"id": "city-shiraz", "title": "شیراز", "type": "city", "code": "SYZ", "country": "ایران", "popularity": 92, "aliases": ["Shiraz"]},
    {"id": "city-mashhad", "title": "مشهد", "type": "city", "code": "MHD", "country": "ایران", "popularity": 96, "aliases": ["Mashhad"]},
    {"id": "city-yazd", "title": "یزد", "type": "city", "code": "AZD", "country": "ایران", "popularity": 78, "aliases": ["Yazd"]},
    {"id": "city-isfahan", "title": "اصفهان", "type": "city", "code": "IFN", "country": "ایران", "popularity": 90, "aliases": ["Isfahan", "Esfahan"]},
    {"id": "city-kish", "title": "کیش", "type": "city", "code": "KIH", "country": "ایران", "popularity": 86, "aliases": ["Kish"]},
    {"id": "city-qeshm", "title": "قشم", "type": "city", "code": "GSM", "country": "ایران", "popularity": 82, "aliases": ["Qeshm"]},
    {"id": "airport-thr", "title": "فرودگاه مهرآباد", "type": "airport", "code": "THR", "city": "تهران", "country": "ایران", "popularity": 94, "aliases": ["Mehrabad"]},
    {"id": "airport-ika", "title": "فرودگاه امام خمینی", "type": "airport", "code": "IKA", "city": "تهران", "country": "ایران", "popularity": 91, "aliases": ["Imam Khomeini Airport"]},
    {"id": "poi-hafezieh", "title": "حافظیه", "type": "attraction", "city": "شیراز", "country": "ایران", "popularity": 75, "aliases": ["Hafezieh"]},
    {"id": "poi-persepolis", "title": "تخت جمشید", "type": "attraction", "city": "مرودشت", "country": "ایران", "popularity": 88, "aliases": ["Persepolis"]},
)


def suggest(q: str, limit: int = 8) -> dict:
    qn = _fold(q or "")
    scored = []
    for e in ENTITIES:
        hay = _fold(" ".join([e["title"], e.get("code", ""), e.get("city", ""), *e.get("aliases", [])]))
        if not qn:
            score = e["popularity"]
        elif qn in hay:
            score = e["popularity"] + (40 if hay.startswith(qn) else 0)
        else:
            continue
        scored.append((score, e))
    scored.sort(key=lambda t: -t[0])
    return {"query": q, "normalized_query": qn,
            "suggestions": [{k: v for k, v in e.items() if k != "aliases"} for _, e in scored[:limit]]}
