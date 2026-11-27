"""Niira NRS airlines as one flight supplier behind `flight_port` — same shape as the Mahan supplier (mahan_flight.py).

Switch: NIRA_MODE = off (default) | sandbox | live, airlines in NIRA_AIRLINES, per-airline NIRA_<CODE>_* (see nira_nrs.py).
* off / invalid / no usable airline → search answers `unavailable` with a reason and NO offers; no network call is made.
* sandbox → Niira's test airline A1 only, and only for staff (`backoffice:read`); customers get `sandbox_test_only`.
* live    → every enabled airline that has credentials (and, if NIRA_<CODE>_ROUTES is set, flies that route).

Exposed now: status, search (indicative prices from AvailabilityFare) and the staff test console (one airline, one call).
Reservation, ticket issue, cancel and refund are implemented in `NiraClient` and unit-tested, but NOT exposed over HTTP:
like Mahan, issuing is financial and stays a guarded, disabled path until the owner approves it and payment capture,
idempotency records and reconciliation are wired.

No network call happens while a DB transaction is open (airport reads are rolled back first). One failing airline is
left out with its reason; it never fails the others and never produces an invented result.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .flight_port import FareOffer, FlightContractViolation, FlightSearchQuery, FlightSegment, Pnr, ScheduleChange
from .nira_nrs import (NAMES_FA, SANDBOX_AIRLINE, Availability, NiraClient, NiraError, airline_config, canonical, nira_mode, redact,
                       requested_airlines)

PROVIDER_KEY = "nira"
OFFER_TTL = timedelta(minutes=20)
MAX_OFFERS = 80
MAX_PARALLEL = 6
SEARCH_DEADLINE = 25.0            # seconds for all airlines together; late airlines are reported as timeout
STAFF_PERMISSION = "backoffice:read"

REASONS_FA = {
    "off": "پرواز نیرا در این سایت هنوز فعال نشده است.",
    "invalid_mode": "تنظیم اتصال نیرا نامعتبر است؛ اتصال بسته است.",
    "no_airline": "هیچ ایرلاینی برای اتصال نیرا پیکربندی نشده است.",
    "sandbox_test_only": "اتصال نیرا فعلاً فقط آزمایشی است و برای مشتری فعال نیست.",
    "provider_error": "پاسخ ایرلاین‌ها دریافت نشد؛ کمی بعد دوباره تلاش کنید.",
    "no_airline_for_route": "ایرلاین فعالی برای این مسیر پیکربندی نشده است.",
}
AIRLINE_REASONS_FA = {
    "ok": "فعال", "sandbox_only_a1": "در حالت آزمایشی فقط ایرلاین تست A1 مجاز است.", "test_airline_in_live": "ایرلاین تست A1 در حالت عملیاتی مجاز نیست.",
    "unknown_airline": "این کد در جدول ایرلاین‌های نیرا نیست.", "missing_credentials": "نام کاربری یا رمز وب‌سرویس تنظیم نشده است.",
    "invalid_host": "آدرس تنظیم‌شده نامعتبر است.", "host_not_allowed": "این آدرس برای حالت فعلی مجاز نیست.", "invalid_cgi": "نام فایل cgi نامعتبر است.",
}


# ------------------------------------------------------------------------------------------------ configuration
def provider_status() -> dict:
    """Names and reasons only — never a user name, password or full URL."""
    mode, reason = nira_mode()
    airlines = []
    if reason is None:
        for code in requested_airlines():
            cfg, why, missing = airline_config(code, mode)
            airlines.append({"code": code, "name_fa": NAMES_FA.get(code, code), "enabled": cfg is not None, "reason": why,
                             "missing_settings": missing, "host": cfg.host if cfg else None, "route_table": sorted(cfg.routes) if cfg and cfg.routes else None})
        if not any(a["enabled"] for a in airlines):
            reason = "no_airline"
    return {"provider": PROVIDER_KEY, "mode": mode, "enabled": reason is None, "reason": reason or "ok", "airlines": airlines,
            "test_inventory": mode == "sandbox", "ticket_issuance": "disabled_pending_owner_approval"}


def _http() -> Any:
    """httpx.Client for NiraClient; None = a fresh real client per call. Tests replace this with a MockTransport client."""
    return None


def build_clients() -> tuple[dict[str, NiraClient], dict]:
    st = provider_status()
    if not st["enabled"]:
        return {}, st
    clients = {}
    for a in st["airlines"]:
        if a["enabled"]:
            cfg, _, _ = airline_config(a["code"], st["mode"])
            if cfg is not None:
                clients[a["code"]] = NiraClient(st["mode"], cfg, http=_http(), sleep=time.sleep)
    return clients, st


# ------------------------------------------------------------------------------------------------ signed offer reference
class OfferRefError(ValueError):
    pass


class OfferSigner:
    """Selection (airline, flight, class, date/time, party, expiry) — never a price — HMAC-signed so it cannot be altered."""

    def __init__(self, secret: str):
        self.key = hmac.new(secret.encode(), b"karenseir-nira-offer-v1", hashlib.sha256).digest()

    def _mac(self, raw: str) -> str:
        return base64.urlsafe_b64encode(hmac.new(self.key, raw.encode(), hashlib.sha256).digest()[:24]).decode().rstrip("=")

    def sign(self, body: dict) -> str:
        raw = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
        return f"{raw}.{self._mac(raw)}"

    def verify(self, ref: str, now: datetime) -> dict:
        try:
            raw, sig = ref.split(".", 1)
            if not hmac.compare_digest(sig, self._mac(raw)):
                raise OfferRefError("signature")
            body = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        except OfferRefError:
            raise
        except Exception as exc:
            raise OfferRefError("malformed") from exc
        if body.get("p") != PROVIDER_KEY or int(body.get("exp", 0)) < int(now.timestamp()):
            raise OfferRefError("expired")
        return body


# ------------------------------------------------------------------------------------------------ adapter (no DB)
def _zoned(dt: Optional[datetime], tz: Optional[str]) -> Optional[datetime]:
    if dt is None or not tz:
        return None
    try:
        return dt.replace(tzinfo=ZoneInfo(tz))
    except ZoneInfoNotFoundError:
        return None


class NiraFlightAdapter:
    """FlightSupplierPort over several NRS airlines. Never registered in FLIGHT_SOURCES; built per request when configured."""
    key = PROVIDER_KEY

    def __init__(self, mode: str, clients: dict[str, NiraClient], signer: OfferSigner, *, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 deadline: float = SEARCH_DEADLINE):
        self.mode, self.clients, self.signer, self._now, self.deadline = mode, clients, signer, now, deadline
        self.last_airlines: list[dict] = []       # per-airline outcome of the last search (staff view)

    def _eligible(self, origin: str, destination: str) -> list[str]:
        return [c for c, cl in self.clients.items() if cl.cfg.flies(origin, destination)]

    def _fan_out(self, codes: list[str], origin: str, destination: str, day: date, pax: dict) -> dict[str, Any]:
        """One AvailabilityFare per eligible airline, in parallel, under one overall deadline."""
        out: dict[str, Any] = {}
        if not codes:
            return out
        pool = ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(codes)))
        futures = {pool.submit(self.clients[c].availability_fare, origin, destination, day, pax.get("ADT", 1), pax.get("CHD", 0), pax.get("INF", 0)): c for c in codes}
        done, pending = wait(futures, timeout=self.deadline)
        for f in done:
            c = futures[f]
            try:
                out[c] = f.result()
            except NiraError as exc:
                out[c] = exc
            except Exception:  # an unexpected bug in one airline's parsing must not fail the others
                out[c] = NiraError("BAD_RESPONSE", airline=c)
        for f in pending:
            out[futures[f]] = NiraError("TIMEOUT", airline=futures[f], ambiguous=True)
        pool.shutdown(wait=False, cancel_futures=True)
        return out

    def _legs(self, origin: str, destination: str, day: date, pax: dict, tz: dict, outcome: dict) -> list[dict]:
        seated = pax.get("ADT", 0) + pax.get("CHD", 0)
        legs: list[dict] = []
        for code, res in self._fan_out(self._eligible(origin, destination), origin, destination, day, pax).items():
            if isinstance(res, NiraError):
                outcome.setdefault(code, {"code": code, "status": "error", "error_code": res.code, "flights": 0, "rejected": 0})
                continue
            assert isinstance(res, Availability)
            row = outcome.setdefault(code, {"code": code, "status": "ok", "error_code": None, "flights": 0, "rejected": 0})
            row["flights"] += len(res.flights)
            row["rejected"] += len(res.rejected)
            for f in res.flights:
                dep, arr = _zoned(f.departure, tz.get(origin)), _zoned(f.arrival, tz.get(destination))
                if dep is None or arr is None:
                    row["rejected"] += 1
                    continue                                              # no fabricated times
                for c in f.classes:
                    if not c.bookable_for(seated) or c.price is None or c.price <= 0 or (c.currency or "IRR").upper() != "IRR":
                        continue
                    legs.append({"seg": FlightSegment(code, f.flight_no, origin, destination, dep, arr), "rbd": c.rbd, "indicative": c.price, "air": code})
        return legs

    def search(self, query: FlightSearchQuery, tz: Optional[dict] = None) -> list[FareOffer]:
        """Indicative per-adult price from AvailabilityFare (sum over legs). Round trips pair two one-way searches of the same
        airline (NRS round-trip support differs per airline)."""
        tz = tz or {}
        outcome: dict[str, dict] = {}
        out_legs = self._legs(query.origin, query.destination, query.depart_on.date(), query.passengers, tz, outcome)
        combos = [[o] for o in out_legs]
        if query.return_on is not None and out_legs:
            back = self._legs(query.destination, query.origin, query.return_on.date(), query.passengers, tz, outcome)
            combos = [[o, b] for o in out_legs for b in back if b["air"] == o["air"] and b["seg"].departs_at > o["seg"].arrives_at]
        self.last_airlines = list(outcome.values())
        combos.sort(key=lambda c: sum(x["indicative"] for x in c))
        exp = self._now() + OFFER_TTL
        pax = [query.passengers.get("ADT", 0), query.passengers.get("CHD", 0), query.passengers.get("INF", 0)]
        offers = []
        for c in combos[:MAX_OFFERS]:
            ref = self.signer.sign({"p": PROVIDER_KEY, "env": self.mode, "pax": pax, "exp": int(exp.timestamp()),
                                    "segs": [{"a": x["air"], "o": x["seg"].origin, "d": x["seg"].destination, "fn": x["seg"].flight_number, "rbd": x["rbd"],
                                              "dep": x["seg"].departs_at.isoformat(), "arr": x["seg"].arrives_at.isoformat()} for x in c]})
            offers.append(FareOffer(provider_offer_ref=ref, segments=tuple(x["seg"] for x in c), total_amount=sum(x["indicative"] for x in c), currency="IRR",
                                    fare_basis="/".join(x["rbd"] for x in c), refundable=None, expires_at=exp))
        return offers

    def selection(self, offer_ref: str) -> dict:
        body = self.signer.verify(offer_ref, self._now())
        if body.get("env") != self.mode:
            raise OfferRefError("environment")                            # a sandbox offer never books on live, nor the reverse
        return body

    # -- FlightSupplierPort surface: writes stay guarded until the owner approves them
    def fare_rules(self, offer: FareOffer) -> dict:
        return {}

    def revalidate(self, offer: FareOffer) -> Optional[FareOffer]:
        return None                                                       # FareJS-based price check is not exposed yet

    def create_pnr(self, offer: FareOffer, passengers: list[dict], idempotency_key: str) -> Pnr:
        raise FlightContractViolation("Niira reservation is not exposed yet (needs idempotency record + owner approval)")

    def issue(self, record_locator: str, idempotency_key: str) -> Pnr:
        raise FlightContractViolation("Niira ticket issuance is disabled pending owner approval")

    def void(self, record_locator: str, idempotency_key: str) -> Pnr:
        raise FlightContractViolation("Niira void is not enabled")

    def refund(self, record_locator: str, idempotency_key: str) -> tuple[Pnr, int]:
        raise FlightContractViolation("Niira refund is not enabled")

    def schedule_changes(self, since: datetime) -> list[ScheduleChange]:
        return []


# ------------------------------------------------------------------------------------------------ API
class SearchIn(BaseModel):
    origin: str = Field(pattern=r"^[A-Za-z]{3}$")
    destination: str = Field(pattern=r"^[A-Za-z]{3}$")
    depart_on: date
    return_on: Optional[date] = None
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    infants: int = Field(default=0, ge=0, le=9)


class ConsoleIn(BaseModel):
    airline: str = Field(pattern=r"^[A-Za-z0-9]{2,3}$")
    origin: str = Field(pattern=r"^[A-Za-z]{3}$")
    destination: str = Field(pattern=r"^[A-Za-z]{3}$")
    depart_on: date
    adults: int = Field(default=1, ge=1, le=9)


def _unavailable(reason: str) -> dict:
    return {"provider": PROVIDER_KEY, "status": "unavailable", "reason": reason, "message": REASONS_FA.get(reason, REASONS_FA["off"]), "offers": []}


def _sanitize(value: Any, secrets: tuple[str, ...]) -> Any:
    """Raw NRS answer for the staff console with any credential-looking key or known secret value removed."""
    if isinstance(value, dict):
        return {k: ("***" if any(s in str(k).lower() for s in ("pass", "user", "office")) else _sanitize(v, secrets)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v, secrets) for v in value[:200]]
    if isinstance(value, str):
        return redact(value, *secrets)
    return value


def nira_flight_router(get_db, current_user, role_has_permission, signing_secret: str) -> APIRouter:
    api = APIRouter(tags=["flight-supplier-nira"])

    def _is_staff(user) -> bool:
        return role_has_permission(user.role, STAFF_PERMISSION)

    @api.get("/flights/suppliers/nira/status")
    def status(user=Depends(current_user)) -> dict:
        if not _is_staff(user):
            raise HTTPException(403, "دسترسی ندارید")
        return provider_status()

    def _airports(db: Session, codes: set[str]) -> dict:
        from .catalog import CatalogAirport
        rows = {a.id: a for a in db.scalars(select(CatalogAirport).where(CatalogAirport.id.in_(codes)))}
        db.rollback()                                                     # no transaction is open while airlines are called
        return rows

    @api.post("/flights/suppliers/nira/search")
    def search(data: SearchIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        from .flight_port import validate_fares, validate_search
        mode, reason = nira_mode()
        if reason is not None:
            return _unavailable(reason)
        if mode == "sandbox" and not _is_staff(user):
            return _unavailable("sandbox_test_only")                     # checked before any client is built or called
        clients, st = build_clients()
        if not clients:
            return _unavailable(st["reason"] if st["reason"] != "ok" else "no_airline")
        o, d = data.origin.upper(), data.destination.upper()
        airports = _airports(db, {o, d})
        tz = {k: a.timezone for k, a in airports.items() if a.timezone}
        midday = lambda day: datetime(day.year, day.month, day.day, 12, tzinfo=ZoneInfo(tz.get(o) or "Asia/Tehran"))  # noqa: E731
        q = FlightSearchQuery(o, d, midday(data.depart_on), {"ADT": data.adults, "CHD": data.children, "INF": data.infants},
                              midday(data.return_on) if data.return_on else None)
        try:
            validate_search(q, airports.__contains__)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if o not in tz or d not in tz:
            return {**_unavailable("provider_error"), "reason": "airport_timezone_missing"}
        adapter = NiraFlightAdapter(st["mode"], clients, OfferSigner(signing_secret))
        if not adapter._eligible(o, d):
            return _unavailable("no_airline_for_route")
        offers = adapter.search(q, tz)
        offers = validate_fares(q, offers, lambda code: code in clients, airports.__contains__)   # drop, never repair
        if not offers and adapter.last_airlines and all(a["status"] == "error" for a in adapter.last_airlines):
            out = _unavailable("provider_error")
            out["retryable"] = True
        else:
            out = {"provider": PROVIDER_KEY, "status": "ok", "test_inventory": st["mode"] == "sandbox", "price_state": "INDICATIVE",
                   "price_note": "قیمت تقریبی از جدول پرواز ایرلاین (هر بزرگسال)؛ قیمت قطعی پس از استعلام نهایی نمایش داده می‌شود.",
                   "offers": [{"offer_ref": x.provider_offer_ref, "indicative_adult_fare": x.total_amount, "currency": x.currency, "booking_class": x.fare_basis,
                               "expires_at": x.expires_at.isoformat(), "refundable": x.refundable,
                               "segments": [{"carrier": s.carrier, "flight_number": s.flight_number, "origin": s.origin, "destination": s.destination,
                                             "departs_at": s.departs_at.isoformat(), "arrives_at": s.arrives_at.isoformat()} for s in x.segments]} for x in offers]}
        if _is_staff(user):
            out["airlines"] = adapter.last_airlines                       # per-airline outcome: codes and counts only
        return out

    @api.post("/flights/suppliers/nira/console/availability")
    def console(data: ConsoleIn, user=Depends(current_user)) -> dict:
        """Staff test console: ONE AvailabilityFare call to ONE configured airline. The host always comes from configuration,
        never from the request. Shows the parsed result, the raw answer with credentials removed, and any NRS error."""
        if not _is_staff(user):
            raise HTTPException(403, "دسترسی ندارید")
        mode, reason = nira_mode()
        if reason is not None:
            raise HTTPException(503, {"code": f"NIRA_{reason.upper()}", "message": REASONS_FA.get(reason, REASONS_FA["off"])})
        code = canonical(data.airline)
        if code not in [canonical(c) for c in requested_airlines()]:
            raise HTTPException(404, {"code": "NIRA_AIRLINE_NOT_ENABLED", "message": "این ایرلاین در NIRA_AIRLINES فعال نیست."})
        cfg, why, missing = airline_config(code, mode)
        if cfg is None:
            raise HTTPException(503, {"code": f"NIRA_{why.upper()}", "message": AIRLINE_REASONS_FA.get(why, why), "missing_settings": missing})
        client = NiraClient(mode, cfg, http=_http(), sleep=time.sleep)
        raw: dict[str, Any] = {}
        secrets = (cfg.user, cfg.password)
        original_send = client._send

        def capture(op: str, url: str, params: dict) -> Any:
            answer = original_send(op, url, params)
            raw["answer"] = _sanitize(answer, secrets)
            return answer
        client._send = capture                                            # type: ignore[method-assign]
        client._read = lambda op, url, params: capture(op, url, params)   # type: ignore[method-assign]  # console: one call, no retry
        started = time.monotonic()
        base = {"airline": code, "name_fa": NAMES_FA.get(code, code), "mode": mode, "host": cfg.host, "test_inventory": code == SANDBOX_AIRLINE}
        try:
            res = client.availability_fare(data.origin, data.destination, data.depart_on, data.adults)
        except NiraError as exc:
            return {**base, "status": "error", "ms": int((time.monotonic() - started) * 1000),
                    "error": {"code": exc.code, "category": exc.category, "message": exc.message_fa, "nrs_text": redact(exc.nrs_text, *secrets)},
                    "raw": raw.get("answer")}
        return {**base, "status": "ok", "ms": int((time.monotonic() - started) * 1000), "rejected": list(res.rejected), "raw": raw.get("answer"),
                "flights": [{"flight_no": f.flight_no, "origin": f.origin, "destination": f.destination, "departure": f.departure.isoformat(),
                             "arrival": f.arrival.isoformat() if f.arrival else None, "aircraft": f.aircraft,
                             "classes": [{"rbd": c.rbd, "state": c.state, "seats": c.seats, "more_than_nine": c.more_than_nine, "price": c.price,
                                          "currency": c.currency} for c in f.classes]} for f in res.flights]}

    return api
