"""Live Niira / Mahan flights in the customer flight search, as request-only offers (owner decision 1405-09-08,
docs/product/approvals.md): the customer sees the indicative SELL price and sends a «درخواست رزرو»; staff call back and issue.

Flow: karenseir-search (provider `flight_suppliers_live`) → POST /internal/search/flight-suppliers (main.py) → `search_rows()`.
* Only `NIRA_MODE=live` / `MAHAN_MODE=live` inventory. Sandbox / QAA test inventory never reaches this path.
* DB reads (airports) are copied to plain values and rolled back BEFORE any supplier call; pricing reads come after.
* All supplier calls run in parallel under one short deadline; a failing or slow supplier is left out, never fails the search.
* Raw supplier answers are cached in-process for a short time (PUBLIC_FLIGHT_CACHE_SECONDS, default 180) per route/day/party;
  prices are computed per request, so one price group's figure is never served to another. Error outcomes are not cached.
* Price = indicative adult sell (`flight_pricing.IndicativePricer`, tenant + price group); above the CAO cap → not listed.
  The net price is never put in a row. Attributes are built from an allow-list.
* Each row carries `request_token`: an HMAC-signed flight spec + the sell price shown, so the sales-desk request records
  server-authoritative details (sales_desk.py verifies it). It is evidence of what was shown, not a hold or a quote.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .flight_port import FareOffer, FlightSearchQuery, validate_fares, validate_search

BOOKING_MODE = "request"
REQUEST_TOKEN_TTL = timedelta(hours=48)       # evidence of the shown offer; the desk re-prices before issuing anyway
ROW_TTL_SECONDS = 600                          # > cache (180 s) + search-service cache (45 s)
MAX_PAIRS = 4                                  # airport pairs per search (multi-airport cities)
SUPPLIER_NAME_FA = "کارن تراول"


def _deadline() -> float:
    try:
        return max(2.0, min(20.0, float(os.getenv("PUBLIC_FLIGHT_SUPPLIER_DEADLINE") or 8)))
    except ValueError:
        return 8.0


def _cache_seconds() -> int:
    try:
        return max(0, min(600, int(os.getenv("PUBLIC_FLIGHT_CACHE_SECONDS") or 180)))
    except ValueError:
        return 180


# ------------------------------------------------------------------------------------------------ request token
class RequestTokenError(ValueError):
    pass


def _key(secret: str) -> bytes:
    return hmac.new(secret.encode(), b"karenseir-flight-request-v1", hashlib.sha256).digest()


def sign_request(secret: str, spec: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
    mac = base64.urlsafe_b64encode(hmac.new(_key(secret), raw.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{raw}.{mac}"


def verify_request(secret: str, token: str, now: Optional[datetime] = None) -> dict:
    try:
        raw, mac = token.split(".")
    except (ValueError, AttributeError):
        raise RequestTokenError("format")
    good = base64.urlsafe_b64encode(hmac.new(_key(secret), raw.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    if not hmac.compare_digest(good, mac):
        raise RequestTokenError("signature")
    try:
        spec = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except (ValueError, TypeError):
        raise RequestTokenError("body")
    if not isinstance(spec, dict) or int(spec.get("exp", 0)) < int((now or datetime.now(timezone.utc)).timestamp()):
        raise RequestTokenError("expired")
    return spec


def describe(spec: dict) -> tuple[str, str]:
    """(short trip line ≤ 240, full description) for the sales-desk case, from a verified spec only."""
    dep = str(spec.get("dep", ""))
    arr = str(spec.get("arr", ""))
    price = spec.get("price")
    price_fa = f"{int(price):,} ریال".replace(",", "٬") if isinstance(price, int) else "نامشخص"
    trip = (f"درخواست رزرو پرواز {spec.get('airline_fa', '')} {spec.get('fn', '')} "
            f"{spec.get('o_fa', '')} ({spec.get('o', '')}) به {spec.get('d_fa', '')} ({spec.get('d', '')}) {dep[:10]} {dep[11:16]}")[:240]
    lines = [
        "درخواست رزرو از نتایج جست‌وجوی سایت (پرداخت و صدور انجام نشده است).",
        f"ایرلاین: {spec.get('airline_fa', '')} ({spec.get('air', '')}) — شماره پرواز: {spec.get('fn', '')}",
        f"مسیر: {spec.get('o_fa', '')} ({spec.get('o', '')}) ← {spec.get('d_fa', '')} ({spec.get('d', '')})",
        f"حرکت: {dep} — ورود: {arr}",
        f"کلاس نرخ: {spec.get('rbd', '')}",
        f"قیمت فروش نمایش‌داده‌شده (تقریبی، هر بزرگسال): {price_fa}",
        f"مسافران جست‌وجو: {spec.get('adt', 0)} بزرگسال، {spec.get('chd', 0)} کودک، {spec.get('inf', 0)} نوزاد",
        f"تأمین‌کننده: {spec.get('p', '')}",
    ]
    if spec.get("ret"):
        lines.append(f"تاریخ برگشت درخواستی: {spec['ret']} (قیمت برگشت را کارشناس اعلام می‌کند)")
    return trip, "\n".join(lines)


# ------------------------------------------------------------------------------------------------ places
def _norm(value: Optional[str]) -> str:
    from .catalog import normalize_text
    return normalize_text(value or "")


def resolve_airports(db: Session, text: Optional[str]) -> list[str]:
    """IATA codes for what the search form sends: a 3-letter code, an airport name, or a city name. Exact (normalized) matches
    only; nothing is guessed. Iranian airports first."""
    from .catalog import CatalogAirport, CatalogPlace
    raw = (text or "").strip()
    if not raw:
        return []
    if len(raw) == 3 and raw.isascii() and raw.isalpha():
        return [raw.upper()] if db.get(CatalogAirport, raw.upper()) is not None else []
    n = _norm(raw)
    if not n:
        return []
    found: list[str] = []
    rows = db.scalars(select(CatalogAirport).where(or_(CatalogAirport.search_text.like(f"%{n}%"), CatalogAirport.city_name == raw,
                                                       CatalogAirport.name_fa == raw)).limit(40)).all()
    for a in rows:
        if n in (_norm(a.name_fa), _norm(a.name_en)):
            found.append(a.id)
    if found:
        return found[:MAX_PAIRS]
    cities = [p.id for p in db.scalars(select(CatalogPlace).where(CatalogPlace.kind == "city", or_(CatalogPlace.name_fa == raw, CatalogPlace.name_en == raw))).all()]
    by_city = db.scalars(select(CatalogAirport).where(CatalogAirport.city_id.in_(cities))).all() if cities else []
    by_name = [a for a in rows if _norm(a.city_name) == n]
    ordered = sorted({a.id: a for a in [*by_city, *by_name] if a.scheduled_service is not False}.values(),
                     key=lambda a: (a.country_code != "IR", a.airport_type or "", a.id))
    return [a.id for a in ordered][:MAX_PAIRS]


# ------------------------------------------------------------------------------------------------ suppliers
_CACHE: dict[tuple, tuple[float, list[FareOffer]]] = {}
_CACHE_LOCK = threading.Lock()


def _cache_get(key: tuple) -> Optional[list[FareOffer]]:
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        _CACHE.pop(key, None)
    return None


def _cache_put(key: tuple, offers: list[FareOffer]) -> None:
    ttl = _cache_seconds()
    if ttl <= 0:
        return
    with _CACHE_LOCK:
        if len(_CACHE) > 500:
            now = time.monotonic()
            for k in [k for k, v in _CACHE.items() if v[0] <= now]:
                _CACHE.pop(k, None)
        _CACHE[key] = (time.monotonic() + ttl, offers)


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _suppliers(secret: str, deadline: float) -> list[tuple[str, str, Any, Callable[[str], bool]]]:
    """(provider, mode, adapter, airline_exists) for every supplier that is LIVE and usable. No network call here."""
    out = []
    from . import nira_flight
    from .nira_nrs import nira_mode
    mode, reason = nira_mode()
    if reason is None and mode == "live":
        clients, st = nira_flight.build_clients()
        if clients and st["mode"] == "live":
            # one adapter per task (its last_airlines is per search); the clients are shared
            make = lambda c=clients: nira_flight.NiraFlightAdapter("live", c, nira_flight.OfferSigner(secret), deadline=max(1.0, deadline - 0.5))  # noqa: E731
            out.append(("nira", "live", make, lambda code, c=clients: code in c))
    from . import mahan_flight
    mmode, mreason = mahan_flight.mahan_mode()
    if mreason is None and mmode == "live":
        madapter, mst = mahan_flight.build_adapter(secret)
        if madapter is not None and mst["mode"] == "live":
            out.append(("mahan", "live", lambda a=madapter: a, lambda code: code == mahan_flight.AIRLINE))
    return out


class SupplierDown(RuntimeError):
    """Every airline of a supplier failed: reported, never cached as an empty answer."""


def _eligible(provider: str, adapter: Any, o: str, d: str) -> bool:
    return bool(adapter._eligible(o, d)) if provider == "nira" else True


def provider_of(adapter: Any) -> str:
    return str(getattr(adapter, "key", "supplier"))


def fetch_offers(secret: str, pairs: list[tuple[str, str]], day: date, pax: dict, tz: dict) -> tuple[list[tuple[str, FareOffer]], list[dict]]:
    """Validated one-way FareOffers per (provider) over the airport pairs, under one deadline. Never raises."""
    deadline = _deadline()
    started = time.monotonic()
    results: list[tuple[str, FareOffer]] = []
    status: list[dict] = []
    tasks = []
    for provider, mode, make, airline_exists in _suppliers(secret, deadline):
        for o, d in pairs:
            if o not in tz or d not in tz or not _eligible(provider, make(), o, d):
                continue
            key = (provider, mode, o, d, day.isoformat(), pax.get("ADT", 1), pax.get("CHD", 0), pax.get("INF", 0))
            cached = _cache_get(key)
            if cached is not None:
                results.extend((provider, x) for x in cached)
                status.append({"provider": provider, "route": f"{o}-{d}", "status": "cached", "offers": len(cached)})
                continue
            tasks.append((provider, make, airline_exists, o, d, key))
    if not tasks:
        return results, status

    def run(make: Callable[[], Any], airline_exists: Callable[[str], bool], o: str, d: str) -> list[FareOffer]:
        adapter = make()
        q = FlightSearchQuery(o, d, datetime(day.year, day.month, day.day, 12, tzinfo=ZoneInfo(tz[o])), dict(pax))
        validate_search(q, lambda code: code in tz)
        offers = adapter.search(q, tz)
        outcome = getattr(adapter, "last_airlines", None)
        if not offers and outcome and all(a.get("status") == "error" for a in outcome):
            raise SupplierDown(provider_of(adapter))
        return validate_fares(q, offers, airline_exists, lambda code: code in tz)   # drop, never repair

    pool = ThreadPoolExecutor(max_workers=min(6, len(tasks)))
    futures = {pool.submit(run, a, ex, o, d): (p, o, d, key) for p, a, ex, o, d, key in tasks}
    done, pending = wait(futures, timeout=max(0.1, deadline - (time.monotonic() - started)))
    for f in done:
        p, o, d, key = futures[f]
        try:
            offers = f.result()
        except Exception as exc:                                          # one supplier's failure never fails the others
            status.append({"provider": p, "route": f"{o}-{d}", "status": "error", "error": type(exc).__name__})
            continue
        _cache_put(key, offers)
        results.extend((p, x) for x in offers)
        status.append({"provider": p, "route": f"{o}-{d}", "status": "ok", "offers": len(offers)})
    for f in pending:
        p, o, d, _ = futures[f]
        status.append({"provider": p, "route": f"{o}-{d}", "status": "timeout"})
    pool.shutdown(wait=False, cancel_futures=True)
    return results, status


# ------------------------------------------------------------------------------------------------ rows for karenseir-search
def _airline_fa(code: str) -> str:
    from .nira_nrs import NAMES_FA
    return NAMES_FA.get(code.upper(), code.upper())


def _party(filters: dict, travellers: int) -> Optional[dict]:
    def n(key: str, default: int) -> int:
        try:
            return int(filters.get(key, default))
        except (TypeError, ValueError):
            return default
    adt, chd, inf = n("adults", max(1, travellers)), n("children", 0), n("infants", 0)
    if adt < 1 or chd < 0 or inf < 0 or inf > adt or adt + chd + inf > 9:
        return None
    return {"ADT": adt, "CHD": chd, "INF": inf}


def search_rows(db: Session, *, secret: str, tenant_id: int, group_id: Optional[str], origin: Optional[str], destination: Optional[str],
                filters: dict, travellers: int, now: Optional[datetime] = None) -> dict:
    from .catalog import CatalogAirport
    from .flight_pricing import IndicativePricer
    now = now or datetime.now(timezone.utc)
    try:
        day = date.fromisoformat(str((filters or {}).get("depart") or ""))
    except ValueError:
        return {"offers": [], "suppliers": [], "reason": "no_date"}
    pax = _party(filters or {}, travellers)
    if pax is None:
        return {"offers": [], "suppliers": [], "reason": "party"}
    o_codes, d_codes = resolve_airports(db, origin), resolve_airports(db, destination)
    pairs = [(o, d) for o in o_codes for d in d_codes if o != d][:MAX_PAIRS]
    if not pairs:
        db.rollback()
        return {"offers": [], "suppliers": [], "reason": "route_unresolved"}
    codes = {c for pair in pairs for c in pair}
    names = {a.id: (a.city_name, a.timezone) for a in db.scalars(select(CatalogAirport).where(CatalogAirport.id.in_(codes)))}
    tz = {k: v[1] for k, v in names.items() if v[1]}
    db.rollback()                                                         # no transaction is open while suppliers are called
    found, suppliers = fetch_offers(secret, pairs, day, pax, tz)
    if not found:
        return {"offers": [], "suppliers": suppliers}
    pricers: dict[str, IndicativePricer] = {}
    ret = str((filters or {}).get("return") or "")[:10] if (filters or {}).get("trip_type") == "round_trip" else ""
    rows = []
    for provider, x in found:
        s = x.segments[0]
        pricer = pricers.setdefault(provider, IndicativePricer(db, tenant_id, None, provider, group_id=group_id))
        sell = pricer.adult_sell(s.carrier, [s.origin, s.destination], x.total_amount)
        if pricer.cap([(s.origin, s.destination, s.departs_at.date())], sell)["cap_state"] == "exceeded":
            continue                                                      # owner decision (PR #119): above the CAO cap is never listed
        flight_key = hashlib.sha256(f"{provider}|{s.carrier}|{s.flight_number}|{s.departs_at.isoformat()}".encode()).hexdigest()[:24]
        offer_id = "supplier-flight:" + hashlib.sha256(f"{flight_key}|{x.fare_basis}".encode()).hexdigest()[:24]
        spec = {"v": 1, "p": provider, "air": s.carrier, "airline_fa": _airline_fa(s.carrier), "fn": s.flight_number, "o": s.origin, "d": s.destination,
                "o_fa": origin or s.origin, "d_fa": destination or s.destination, "dep": s.departs_at.isoformat(), "arr": s.arrives_at.isoformat(),
                "rbd": x.fare_basis, "price": int(sell), "cur": x.currency, "adt": pax["ADT"], "chd": pax["CHD"], "inf": pax["INF"],
                "ret": ret or None, "exp": int((now + REQUEST_TOKEN_TTL).timestamp())}
        attrs = {
            "booking_mode": BOOKING_MODE, "entity_id": "supplier-flight:" + flight_key,
            "airline": _airline_fa(s.carrier), "airline_code": s.carrier, "flight_number": s.flight_number,
            "origin": origin or s.origin, "destination": destination or s.destination, "origin_code": s.origin, "destination_code": s.destination,
            "departure_time": s.departs_at.isoformat(), "arrival_time": s.arrives_at.isoformat(), "fare_class": x.fare_basis,
            "supplier_name": SUPPLIER_NAME_FA, "instant_booking": False, "price_state": "INDICATIVE",
            "request_price": int(sell), "request_currency": x.currency, "request_token": sign_request(secret, spec),
            "observed_at": now.isoformat(), "freshness_ttl_seconds": ROW_TTL_SECONDS,
        }
        if ret:
            attrs["return_date"] = ret
        rows.append({"id": offer_id, "service_type": "flight", "title": f"پرواز {attrs['origin']} به {attrs['destination']}",
                     "amount": int(sell), "currency": x.currency, "available_units": None, "provider_key": provider, "fulfillment_mode": BOOKING_MODE,
                     "attributes": attrs, "policy": {}, "valid_until": (now + timedelta(seconds=ROW_TTL_SECONDS)).isoformat(),
                     "updated_at": now.isoformat()})
    db.rollback()
    return {"offers": rows, "suppliers": suppliers}
