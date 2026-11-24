"""Mahan Air (W5) MRS as one flight supplier behind `flight_port` — search → revalidate (FareQuote) → hold (Book/PNR).

Switch: MAHAN_MODE = disabled (default) | qaa | live.
* disabled, an unknown value, or missing credentials → this provider returns no flights and a reason; nothing is invented.
* qaa  → Mahan's test system. Its PNRs are test bookings, so only staff (`backoffice:read`) may search/hold; customers get
         `qaa_test_only`. On QAA only IKA-BKK is priceable (docs/integrations/mahan/README.md).
* live → Mahan production. Mahan has NOT granted production access yet; until it does, live has no credentials and fails closed.

Rules kept on purpose:
* No ticket issuance here. A hold stops at the PNR; `issue` is a guarded, disabled path until the owner approves it.
* Availability prices are indicators only; the price a customer can hold is the FareQuote price after the tenant's commerce
  markup rule (`commerce.quote`, the same rule the existing flight price-check uses) and never above the Civil Aviation
  (CAO) adult cap configured for the route and date (`charter_blocks.cap_for`, owner rule L5).
* VAT is on our commission only (the markup), at the dated rate of `agency_b2b.vat_rate_on`; it is recorded internally
  and not added to the airline fare. No new VAT rule is introduced.
* No network call happens while a DB transaction is open: every DB step commits before Mahan is called.
* Hold is idempotent: `Idempotency-Key` + request hash in `idempotency_keys` (no new table, no migration). The same key
  with a different body is refused; a lost Book answer is never retried (a PNR may exist) — it is reported for reconciliation.
* Retries are per operation: availability/FareQuote (read-only) retry on network/503/timeout; Book never retries.
* Secrets only from env (via MahanClient). Supplier cost, PNR internals and markup are never in customer responses.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import operations as m
from .flight_port import FareOffer, FlightContractViolation, FlightSearchQuery, FlightSegment, Pnr, ScheduleChange
from .mahan_mrs import AIRLINE, MahanClient, MahanError, Quote, docs_text, money

MODES = ("disabled", "qaa", "live")
PROVIDER_KEY = "mahan"
OFFER_TTL = timedelta(minutes=20)
MAX_OFFERS = 60
READ_RETRIES = 2                        # extra attempts for read-only calls (availability, FareQuote)
RETRYABLE = {"NETWORK", "UNAVAILABLE", "TIMEOUT"}
AGE_TYPES = {"ADT": "AD", "CHD": "CH", "INF": "IN"}
PAX_KEY = {"AD": "adult", "CH": "child", "IN": "infant"}
STAFF_PERMISSION = "backoffice:read"
HOLD_SCOPE = "mahan.hold"

REASONS_FA = {
    "disabled": "پرواز ماهان در این سایت هنوز فعال نشده است.",
    "invalid_mode": "تنظیم اتصال ماهان نامعتبر است؛ اتصال بسته است.",
    "missing_credentials": "اتصال ماهان پیکربندی نشده است.",
    "qaa_test_only": "اتصال ماهان فعلاً فقط آزمایشی است و برای مشتری فعال نیست.",
    "provider_error": "پاسخ ماهان دریافت نشد؛ کمی بعد دوباره تلاش کنید.",
}


# ------------------------------------------------------------------------------------------------ configuration
def mahan_mode() -> tuple[str, Optional[str]]:
    raw = (os.getenv("MAHAN_MODE") or "disabled").strip().lower()
    if raw not in MODES:
        return "disabled", "invalid_mode"
    return raw, ("disabled" if raw == "disabled" else None)


def missing_credentials(mode: str) -> list[str]:
    """Names (never values) of the env settings this mode still needs. MAHAN_QAA_* for qaa, MAHAN_* for live."""
    prefix = "MAHAN_QAA_" if mode == "qaa" else "MAHAN_"
    out = []
    if not ((os.getenv(prefix + "API_KEY") or "").strip() or (os.getenv(prefix + "API_KEY_B64") or "").strip()):
        out.append(prefix + "API_KEY")
    for name in ("OFFICE_USER", "OFFICE_PASS"):
        if not (os.getenv(prefix + name) or "").strip():
            out.append(prefix + name)
    return out


def provider_status() -> dict:
    mode, reason = mahan_mode()
    missing: list[str] = []
    if reason is None:
        missing = missing_credentials(mode)
        if missing:
            reason = "missing_credentials"
    return {"provider": PROVIDER_KEY, "mode": mode, "enabled": reason is None, "reason": reason or "ok",
            "missing_settings": missing, "test_inventory": mode == "qaa", "ticket_issuance": "disabled_pending_owner_approval"}


def _transport() -> Optional[Callable]:
    """HTTP transport for MahanClient; None = real httpx. Tests replace this with a fake — they never reach Mahan."""
    return None


def _timeout() -> float:
    try:
        return max(3.0, min(60.0, float(os.getenv("MAHAN_TIMEOUT_SECONDS") or 25)))
    except ValueError:
        return 25.0


# ------------------------------------------------------------------------------------------------ signed offer reference
class OfferRefError(ValueError):
    pass


class OfferSigner:
    """The offer reference carries the selection (flights, classes, passenger mix, expiry) — never a price — and is
    HMAC-signed so the client cannot alter it. Prices are always re-read from Mahan (FareQuote)."""

    def __init__(self, secret: str):
        self.key = hmac.new(secret.encode(), b"karenseir-mahan-offer-v1", hashlib.sha256).digest()

    def sign(self, body: dict) -> str:
        raw = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
        sig = base64.urlsafe_b64encode(hmac.new(self.key, raw.encode(), hashlib.sha256).digest()[:24]).decode().rstrip("=")
        return f"{raw}.{sig}"

    def verify(self, ref: str, now: datetime) -> dict:
        try:
            raw, sig = ref.split(".", 1)
            good = base64.urlsafe_b64encode(hmac.new(self.key, raw.encode(), hashlib.sha256).digest()[:24]).decode().rstrip("=")
            if not hmac.compare_digest(sig, good):
                raise OfferRefError("signature")
            body = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        except OfferRefError:
            raise
        except Exception as exc:  # malformed token
            raise OfferRefError("malformed") from exc
        if body.get("p") != PROVIDER_KEY or int(body.get("exp", 0)) < int(now.timestamp()):
            raise OfferRefError("expired")
        return body


# ------------------------------------------------------------------------------------------------ adapter (no DB)
@dataclass(frozen=True)
class PricedQuote:
    currency: str
    net_total: int
    net_unit: dict          # {"adult": int, "child": int, "infant": int} — per passenger, only for present types
    counts: dict            # {"adult": n, ...}
    cabin: str


def _parse_local(value: Any, tz: Optional[str]) -> Optional[datetime]:
    if not value or not tz:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("T", " ")[:19])
        return dt.replace(tzinfo=ZoneInfo(tz)) if dt.tzinfo is None else dt
    except (ValueError, ZoneInfoNotFoundError):
        return None


def _whole(v: Optional[Decimal]) -> Optional[int]:
    if v is None or v <= 0 or v != v.to_integral_value():
        return None
    return int(v)


def priced_quote(q: Quote, counts: dict) -> PricedQuote:
    """Per-passenger net amounts from FareQuote's PassengerBreakdown, accepted only if they add up to TotalPrice.
    Adults-only parties can be split from the total. Anything else is refused (fail closed), never estimated."""
    if (q.currency or "").upper() != "IRR":
        raise MahanError("FareQuote currency is not IRR", code="CURRENCY")
    total = _whole(q.total_price)
    if total is None:
        raise MahanError("FareQuote total is not a positive whole amount", code="BAD_RESPONSE")
    present = {k: v for k, v in counts.items() if v}
    amounts: dict[str, int] = {}
    for b in q.breakdown or []:
        if not isinstance(b, dict):
            continue
        pax = PAX_KEY.get(str(b.get("AgeType") or "").upper())
        if not pax:
            continue
        value = None
        for k in ("TotalPrice", "PassengerTotal", "Total"):
            value = value or money(b.get(k))
        if value is None and money(b.get("Fare") or b.get("BaseFare")) is not None:
            value = money(b.get("Fare") or b.get("BaseFare")) + sum((money(t.get("TotalTaxAmount")) or money(t.get("TaxAmount")) or Decimal(0)) for t in b.get("Taxes") or [] if isinstance(t, dict))
        v = _whole(value)
        if v is not None:
            amounts[pax] = v
    unit: Optional[dict] = None
    if amounts and set(amounts) == set(present):
        if sum(amounts[p] * present[p] for p in present) == total:
            unit = dict(amounts)                                          # breakdown is per passenger
        elif sum(amounts.values()) == total and all(amounts[p] % present[p] == 0 for p in present):
            unit = {p: amounts[p] // present[p] for p in present}         # breakdown is per passenger type
    if unit is None and set(present) == {"adult"} and total % present["adult"] == 0:
        unit = {"adult": total // present["adult"]}
    if unit is None:
        raise MahanError("FareQuote per-passenger amounts could not be verified against the total", code="BREAKDOWN_UNVERIFIED")
    return PricedQuote(currency="IRR", net_total=total, net_unit=unit, counts=present, cabin=q.cabin)


class MahanFlightAdapter:
    """FlightSupplierPort for Mahan. Never registered in FLIGHT_SOURCES at import; built per request only when configured."""
    key = PROVIDER_KEY

    def __init__(self, mode: str, client: MahanClient, signer: OfferSigner, *, sleep: Callable[[float], None] = time.sleep,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        if mode not in ("qaa", "live"):
            raise ValueError("adapter needs qaa or live")
        self.mode, self.client, self.signer, self._sleep, self._now = mode, client, signer, sleep, now

    def _read(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Read-only operations retry on transport-level failures; business refusals are not retried."""
        for attempt in range(READ_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except MahanError as exc:
                if exc.code not in RETRYABLE or attempt == READ_RETRIES:
                    raise
                self._sleep(min(0.5 * (2 ** attempt), 2.0))
        raise AssertionError("unreachable")

    # -- search
    def _legs(self, origin: str, destination: str, day: date, pax: dict, tz: dict) -> list[dict]:
        ad, ch, inf = pax.get("ADT", 0), pax.get("CHD", 0), pax.get("INF", 0)
        flights = self._read(self.client.availability, origin, destination, day.isoformat(), ad, ch, inf)
        legs = []
        for f in flights:
            if f.origin != origin or f.destination != destination:
                continue
            dep, arr = _parse_local(f.departure, tz.get(origin)), _parse_local(f.arrival, tz.get(destination))
            if dep is None or arr is None:
                continue                                                  # no fabricated times
            for c in f.open_classes():
                price = _whole(c.price)
                if c.seats < ad + ch or price is None or (c.currency or "IRR").upper() != "IRR":
                    continue
                legs.append({"seg": FlightSegment(AIRLINE, f.flight_no, origin, destination, dep, arr), "rbd": c.rbd, "seats": c.seats, "indicative": price,
                             "date": dep.date().isoformat()})
        return legs

    def search(self, query: FlightSearchQuery, tz: Optional[dict] = None) -> list[FareOffer]:
        """total_amount on a search offer is Mahan's availability indicator per adult (sum over legs) — indicative only;
        revalidate() gives the bookable price."""
        tz = tz or {}
        now = self._now()
        out_legs = self._legs(query.origin, query.destination, query.depart_on.date(), query.passengers, tz)
        combos: list[list[dict]] = [[o] for o in out_legs]
        if query.return_on is not None and out_legs:
            back = self._legs(query.destination, query.origin, query.return_on.date(), query.passengers, tz)
            combos = [[o, b] for o in out_legs for b in back if b["seg"].departs_at > o["seg"].arrives_at]
        combos.sort(key=lambda c: sum(x["indicative"] for x in c))
        pax = [query.passengers.get("ADT", 0), query.passengers.get("CHD", 0), query.passengers.get("INF", 0)]
        exp = now + OFFER_TTL
        offers = []
        for c in combos[:MAX_OFFERS]:
            ref = self.signer.sign({"p": PROVIDER_KEY, "env": self.mode, "pax": pax, "exp": int(exp.timestamp()),
                                    "segs": [{"o": x["seg"].origin, "d": x["seg"].destination, "fn": x["seg"].flight_number, "dt": x["date"], "rbd": x["rbd"],
                                              "dep": x["seg"].departs_at.isoformat(), "arr": x["seg"].arrives_at.isoformat()} for x in c]})
            offers.append(FareOffer(provider_offer_ref=ref, segments=tuple(x["seg"] for x in c), total_amount=sum(x["indicative"] for x in c), currency="IRR",
                                    fare_basis="/".join(x["rbd"] for x in c), refundable=None, expires_at=exp))
        return offers

    # -- price
    def selection(self, offer_ref: str) -> dict:
        body = self.signer.verify(offer_ref, self._now())
        if body.get("env") != self.mode:
            raise OfferRefError("environment")                            # a QAA offer never books on live, nor the reverse
        return body

    def quote(self, offer_ref: str) -> PricedQuote:
        body = self.selection(offer_ref)
        ad, ch, inf = body["pax"]
        segs = [{"Origin": s["o"], "Destination": s["d"], "FlightClass": s["rbd"], "Departure": s["dt"], "FlightNo": s["fn"]} for s in body["segs"]]
        q = self._read(self.client.fare_quote, segs, ad, ch, inf)
        return priced_quote(q, {"adult": ad, "child": ch, "infant": inf})

    # -- hold (Book). Never retried: a lost answer may still have created a PNR.
    def book(self, offer_ref: str, passengers: list[dict], contact: str) -> str:
        body = self.selection(offer_ref)
        segs = [{"Origin": s["o"], "Destination": s["d"], "FlightNo": s["fn"], "DepartureDate": s["dt"], "FlightClass": s["rbd"]} for s in body["segs"]]
        return self.client.book(segs, mahan_passengers(passengers, segs), contact)

    # -- FlightSupplierPort surface
    def fare_rules(self, offer: FareOffer) -> dict:
        return {}                                                         # MRS client exposes no fare-rule call; shown as unknown

    def revalidate(self, offer: FareOffer) -> Optional[FareOffer]:
        try:
            p = self.quote(offer.provider_offer_ref)
        except (MahanError, OfferRefError):
            return None
        return FareOffer(**{**offer.__dict__, "total_amount": p.net_total})

    def create_pnr(self, offer: FareOffer, passengers: list[dict], idempotency_key: str) -> Pnr:
        locator = self.book(offer.provider_offer_ref, passengers, passengers[0].get("contact", "") if passengers else "")
        return Pnr(record_locator=locator, provider_offer_ref=offer.provider_offer_ref, status="held", total_amount=offer.total_amount, currency=offer.currency)

    def issue(self, record_locator: str, idempotency_key: str) -> Pnr:
        # TODO(owner approval): ticket issuance is financial and irreversible. Enable only after the owner approves it in
        # writing AND payment capture is wired; then call MahanClient.issue once and reconcile (NRSRT/NRSETR) on timeout.
        raise FlightContractViolation("Mahan ticket issuance is disabled pending owner approval")

    def void(self, record_locator: str, idempotency_key: str) -> Pnr:
        raise FlightContractViolation("Mahan void is not enabled")

    def refund(self, record_locator: str, idempotency_key: str) -> tuple[Pnr, int]:
        raise FlightContractViolation("Mahan refund is not enabled")

    def schedule_changes(self, since: datetime) -> list[ScheduleChange]:
        return []


def build_adapter(signing_secret: str) -> tuple[Optional[MahanFlightAdapter], dict]:
    """Adapter when MAHAN_MODE and credentials allow, else (None, status with the reason)."""
    st = provider_status()
    if not st["enabled"]:
        return None, st
    try:
        client = MahanClient(env=st["mode"], transport=_transport(), timeout=_timeout())
    except (MahanError, ValueError):
        return None, {**st, "enabled": False, "reason": "missing_credentials"}
    return MahanFlightAdapter(st["mode"], client, OfferSigner(signing_secret)), st


# ------------------------------------------------------------------------------------------------ passengers
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _ddmmmyy(d: date) -> str:
    return f"{d.day:02d}{MONTHS[d.month - 1]}{d.year % 100:02d}"


def mahan_passengers(passengers: list[dict], segs: list[dict]) -> list[dict]:
    """Customer passengers → MRS Book shape (same shape that booked the QAA certification PNRs): a DOCS SSR per segment,
    an infant is an INFT SSR under its adult, never a passenger of its own."""
    adults = [p for p in passengers if p["type"] == "ADT"]
    infants = [p for p in passengers if p["type"] == "INF"]
    if len(infants) > len(adults):
        raise ValueError("each infant needs an adult")
    out = []
    adult_no = 0
    for p in [p for p in passengers if p["type"] != "INF"]:
        doc = docs_text(p["document_type"], p["nationality"], p["document_number"], p["nationality"], _ddmmmyy(p["birth_date"]), p["gender"],
                        _ddmmmyy(p["document_expiry"]), p["last_name"], p["first_name"])
        ssrs = [{"SSRType": "DOCS", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"], "FreeText": doc} for s in segs]
        if p["type"] == "ADT":
            adult_no += 1
            if adult_no <= len(infants):
                inf = infants[adult_no - 1]
                ssrs += [{"SSRType": "INFT", "FlightNo": s["FlightNo"], "DepartureDate": s["DepartureDate"],
                          "FreeText": f"{inf['last_name'].upper()}/{inf['first_name'].upper()} {_ddmmmyy(inf['birth_date'])}"} for s in segs]
        out.append({"FirstName": p["first_name"].upper(), "LastName": p["last_name"].upper(), "AgeType": AGE_TYPES[p["type"]],
                    "Title": "MS" if p["gender"] == "F" else "MR", "Parent": "", "SSRs": ssrs})
    return out


# ------------------------------------------------------------------------------------------------ pricing (short DB reads)
def sell_price(db: Session, tenant_id: int, user_id: Optional[int], selection: dict, pq: PricedQuote) -> dict:
    """Tenant markup rule (commerce) on per-passenger net amounts, then the CAO adult cap per route/date. Returns internal
    figures too (net, margin, VAT on commission) — callers must only pass `public_price()` to customers."""
    from .agency_b2b import bps_of, vat_rate_on
    from .catalog import CatalogAirport
    from .charter_blocks import cap_for
    from .commerce import quote as commerce_quote
    segs = selection["segs"]
    countries = {a.id: a.country_code for a in db.scalars(select(CatalogAirport).where(CatalogAirport.id.in_({s["o"] for s in segs} | {s["d"] for s in segs})))}
    scope = "domestic" if countries and all(c == "IR" for c in countries.values()) else "international"
    ctx = {"service_type": "flight", "supplier_id": PROVIDER_KEY, "airline_code": AIRLINE, "origin": segs[0]["o"], "destination": segs[0]["d"], "scope": scope}
    fares = {p: {"count": pq.counts[p], "total": pq.net_unit[p]} for p in pq.counts}
    result = commerce_quote(db, tenant_id, ctx, fares, user_id=user_id)
    lines = {ln["pax"]: ln for ln in result["lines"]}
    sell_unit = {p: lines[p]["sell"] for p in pq.counts}
    sell_total = sum(sell_unit[p] * pq.counts[p] for p in pq.counts)
    caps = [cap_for(db, tenant_id, s["o"], s["d"], date.fromisoformat(s["dt"])) for s in segs]
    cap_state, cap_total = "none", None
    if any(c[0] is not None for c in caps):
        if not all(c[0] is not None for c in caps):
            cap_state = "unverifiable"                                    # a cap on one leg only cannot be split from a combined fare
        else:
            cap_total = sum(c[0] for c in caps)
            cap_state = "exceeded" if sell_unit.get("adult", 0) > cap_total else "ok"
    margin = sell_total - pq.net_total
    try:
        rate = vat_rate_on(date.today(), db, tenant_id)
        vat = {"vat_on_commission": bps_of(max(margin, 0), rate.rate_bps), "vat_rate_bps": rate.rate_bps, "vat_reference": rate.legal_reference}
    except Exception:  # an uncovered date is an error in vat_rate_on, never a guess
        vat = {"vat_on_commission": None, "vat_rate_bps": None, "vat_reference": "unavailable"}
    return {"currency": "IRR", "sell_total": sell_total, "sell_unit": sell_unit, "counts": pq.counts, "cabin": pq.cabin,
            "cap_state": cap_state, "cap_unit_irr": cap_total, "cap_refs": [c[1] for c in caps if c[1]],
            "net_total": pq.net_total, "net_unit": pq.net_unit, "margin": margin, "rule_id": (result.get("rule") or {}).get("id"), **vat}


def public_price(p: dict) -> dict:
    return {"total_amount": p["sell_total"], "currency": p["currency"], "per_passenger": [{"type": k, "count": p["counts"][k], "unit_amount": p["sell_unit"][k]} for k in p["counts"]]}


def internal_price(p: dict) -> dict:
    return {k: p[k] for k in ("net_total", "net_unit", "sell_total", "margin", "rule_id", "vat_on_commission", "vat_rate_bps", "vat_reference", "cap_state", "cap_unit_irr", "cap_refs")}


# ------------------------------------------------------------------------------------------------ API
class SearchIn(BaseModel):
    origin: str = Field(pattern=r"^[A-Za-z]{3}$")
    destination: str = Field(pattern=r"^[A-Za-z]{3}$")
    depart_on: date
    return_on: Optional[date] = None
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    infants: int = Field(default=0, ge=0, le=9)


class RevalidateIn(BaseModel):
    offer_ref: str = Field(min_length=20, max_length=4000)
    expected_total: Optional[int] = Field(default=None, gt=0)


class PassengerIn(BaseModel):
    type: str = Field(pattern=r"^(ADT|CHD|INF)$")
    first_name: str = Field(pattern=r"^[A-Za-z][A-Za-z ]{0,39}$")
    last_name: str = Field(pattern=r"^[A-Za-z][A-Za-z ]{0,39}$")
    gender: str = Field(pattern=r"^[MF]$")
    birth_date: date
    document_type: str = Field(pattern=r"^[IP]$")             # I = national ID card, P = passport (MRS DOCS)
    document_number: str = Field(pattern=r"^[A-Za-z0-9]{5,20}$")
    document_expiry: date
    nationality: str = Field(pattern=r"^[A-Z]{3}$")


class HoldIn(BaseModel):
    offer_ref: str = Field(min_length=20, max_length=4000)
    expected_total: int = Field(gt=0)
    contact_phone: str = Field(pattern=r"^\+?[0-9]{10,15}$")
    passengers: list[PassengerIn] = Field(min_length=1, max_length=9)


def _canonical_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _unavailable(st: dict) -> dict:
    return {"provider": PROVIDER_KEY, "status": "unavailable", "reason": st["reason"], "message": REASONS_FA.get(st["reason"], REASONS_FA["disabled"]), "offers": []}


def mahan_flight_router(get_db, current_user, role_has_permission, audit, signing_secret: str) -> APIRouter:
    api = APIRouter(tags=["flight-supplier-mahan"])

    def _is_staff(user) -> bool:
        return role_has_permission(user.role, STAFF_PERMISSION)

    def _gate(user) -> tuple[Optional[MahanFlightAdapter], dict]:
        adapter, st = build_adapter(signing_secret)
        if adapter is not None and st["mode"] == "qaa" and not _is_staff(user):
            return None, {**st, "enabled": False, "reason": "qaa_test_only"}
        return adapter, st

    def _refuse(st: dict, status: int = 503) -> HTTPException:
        return HTTPException(status, {"code": f"MAHAN_{st['reason'].upper()}", "message": REASONS_FA.get(st["reason"], REASONS_FA["disabled"])})

    def _provider_fail(exc: MahanError) -> HTTPException:
        return HTTPException(502, {"code": "MAHAN_PROVIDER_ERROR", "message": REASONS_FA["provider_error"], "retryable": exc.code in RETRYABLE})

    def _price(db: Session, user, adapter: MahanFlightAdapter, offer_ref: str) -> tuple[dict, dict]:
        try:
            selection = adapter.selection(offer_ref)
        except OfferRefError:
            raise HTTPException(409, {"code": "OFFER_EXPIRED", "message": "این پیشنهاد منقضی شده است؛ دوباره جست‌وجو کنید."})
        db.rollback()                                                    # no transaction is open while Mahan is called
        try:
            pq = adapter.quote(offer_ref)
        except MahanError as exc:
            if exc.code in RETRYABLE or exc.code in ("SIGN", "BAD_RESPONSE", None):
                raise _provider_fail(exc)
            raise HTTPException(409, {"code": "FARE_UNAVAILABLE", "message": "این نرخ دیگر قابل رزرو نیست؛ دوباره جست‌وجو کنید."})
        price = sell_price(db, user.tenant_id, user.id, selection, pq)
        db.rollback()
        if price["cap_state"] in ("exceeded", "unverifiable"):
            raise HTTPException(409, {"code": "PRICE_CAP_EXCEEDED" if price["cap_state"] == "exceeded" else "PRICE_CAP_UNVERIFIABLE",
                                      "message": "قیمت این پرواز با سقف اعلامی سازمان هواپیمایی کشوری قابل فروش نیست."})
        return selection, price

    @api.get("/flights/suppliers/mahan/status")
    def status(user=Depends(current_user)) -> dict:
        if not _is_staff(user):
            raise HTTPException(403, "دسترسی ندارید")
        return provider_status()

    @api.post("/flights/suppliers/mahan/search")
    def search(data: SearchIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        from .catalog import CatalogAirport
        from .flight_port import validate_fares, validate_search
        adapter, st = _gate(user)
        if adapter is None:
            return _unavailable(st)
        o, d = data.origin.upper(), data.destination.upper()
        airports = {a.id: a for a in db.scalars(select(CatalogAirport).where(CatalogAirport.id.in_({o, d})))}
        db.rollback()
        tz = {k: a.timezone for k, a in airports.items() if a.timezone}
        midday = lambda day: datetime(day.year, day.month, day.day, 12, tzinfo=ZoneInfo(tz.get(o) or "Asia/Tehran"))  # noqa: E731
        q = FlightSearchQuery(o, d, midday(data.depart_on), {"ADT": data.adults, "CHD": data.children, "INF": data.infants},
                              midday(data.return_on) if data.return_on else None)
        try:
            validate_search(q, airports.__contains__)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if o not in tz or d not in tz:
            return {**_unavailable({"reason": "provider_error"}), "reason": "airport_timezone_missing"}
        try:
            offers = adapter.search(q, tz)
        except MahanError as exc:
            return {**_unavailable({"reason": "provider_error"}), "retryable": exc.code in RETRYABLE}
        offers = validate_fares(q, offers, lambda code: code == AIRLINE, airports.__contains__)   # drop, never repair
        return {"provider": PROVIDER_KEY, "status": "ok", "test_inventory": st["mode"] == "qaa", "price_state": "INDICATIVE",
                "price_note": "قیمت تقریبی از جدول پرواز ماهان (هر بزرگسال)؛ قیمت قطعی پس از استعلام نهایی نمایش داده می‌شود.",
                "offers": [{"offer_ref": x.provider_offer_ref, "indicative_adult_fare": x.total_amount, "currency": x.currency, "booking_class": x.fare_basis,
                            "expires_at": x.expires_at.isoformat(), "refundable": x.refundable,
                            "segments": [{"carrier": s.carrier, "flight_number": s.flight_number, "origin": s.origin, "destination": s.destination,
                                          "departs_at": s.departs_at.isoformat(), "arrives_at": s.arrives_at.isoformat()} for s in x.segments]} for x in offers]}

    @api.post("/flights/suppliers/mahan/revalidate")
    def revalidate(data: RevalidateIn, user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        adapter, st = _gate(user)
        if adapter is None:
            raise _refuse(st)
        _, price = _price(db, user, adapter, data.offer_ref)
        out = {"provider": PROVIDER_KEY, "status": "ok", "test_inventory": st["mode"] == "qaa", "price_state": "RECHECKED", **public_price(price)}
        if data.expected_total is not None and data.expected_total != price["sell_total"]:
            out.update(status="price_changed", previous_amount=data.expected_total, delta=price["sell_total"] - data.expected_total)
        return out

    @api.post("/flights/suppliers/mahan/hold", status_code=201)
    def hold(data: HoldIn, user=Depends(current_user), db: Session = Depends(get_db),
             idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=120)) -> dict:
        adapter, st = _gate(user)
        if adapter is None:
            raise _refuse(st, 403 if st["reason"] == "qaa_test_only" else 503)
        if st["mode"] == "live" and not role_has_permission(user.role, "reservation:create"):
            raise HTTPException(403, "دسترسی ندارید")
        pax = [p.model_dump() for p in data.passengers]
        try:
            selection = adapter.selection(data.offer_ref)
        except OfferRefError:
            raise HTTPException(409, {"code": "OFFER_EXPIRED", "message": "این پیشنهاد منقضی شده است؛ دوباره جست‌وجو کنید."})
        counts = [sum(1 for p in pax if p["type"] == t) for t in ("ADT", "CHD", "INF")]
        if counts != list(selection["pax"]):
            raise HTTPException(422, "تعداد مسافران با پیشنهاد انتخاب‌شده یکسان نیست")
        today = date.today()
        if any(p["document_expiry"] <= today or p["birth_date"] >= today for p in pax):
            raise HTTPException(422, "تاریخ تولد یا اعتبار مدرک مسافر نامعتبر است")
        request_hash = _canonical_hash({"user": user.id, "offer_ref": data.offer_ref, "expected_total": data.expected_total, "contact": data.contact_phone, "passengers": pax})
        # 1) claim the idempotency key in its own short transaction
        prior = db.scalar(select(m.IdempotencyKey).where(m.IdempotencyKey.tenant_id == user.tenant_id, m.IdempotencyKey.scope == HOLD_SCOPE, m.IdempotencyKey.key == idempotency_key))
        if prior is None:
            hold_id = str(uuid.uuid4())                                 # set here: reading row.id after commit would open a transaction
            db.add(m.IdempotencyKey(id=hold_id, tenant_id=user.tenant_id, scope=HOLD_SCOPE, key=idempotency_key, request_hash=request_hash,
                                    response_json=json.dumps({"status": "in_progress"})))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                prior = db.scalar(select(m.IdempotencyKey).where(m.IdempotencyKey.tenant_id == user.tenant_id, m.IdempotencyKey.scope == HOLD_SCOPE, m.IdempotencyKey.key == idempotency_key))
        if prior is not None:
            if prior.request_hash != request_hash:
                raise HTTPException(409, "کلید تکرار برای درخواست دیگری استفاده شده است")
            stored = json.loads(prior.response_json or "{}")
            db.rollback()
            if stored.get("status") == "in_progress":
                raise HTTPException(409, {"code": "HOLD_IN_PROGRESS", "message": "این درخواست در حال انجام است؛ نتیجه را بعداً ببینید."})
            return stored

        def finish(response: dict, internal: dict) -> dict:
            r = db.get(m.IdempotencyKey, hold_id)
            r.response_json = json.dumps(response, ensure_ascii=False)
            audit(db, user, f"flight.mahan.{response['status']}", "flight_supplier_hold", {"hold_id": hold_id, "mode": st["mode"], **internal})
            db.commit()
            return response

        # 2) authoritative price (FareQuote) — network, outside any transaction
        try:
            selection, price = _price(db, user, adapter, data.offer_ref)
        except HTTPException as exc:
            finish({"hold_id": hold_id, "status": "not_held", "provider": PROVIDER_KEY, "error": exc.detail}, {"stage": "price"})
            raise
        flights = [f"{AIRLINE}{s['fn']} {s['o']}-{s['d']} {s['dt']} {s['rbd']}" for s in selection["segs"]]
        if price["sell_total"] != data.expected_total:
            resp = {"hold_id": hold_id, "status": "price_changed", "provider": PROVIDER_KEY, "previous_amount": data.expected_total, **public_price(price)}
            finish(resp, {"stage": "price", "flights": flights, **internal_price(price)})
            raise HTTPException(409, {"code": "PRICE_CHANGED", **resp})
        # 3) Book — exactly once; a lost answer is reconciled, never retried
        try:
            locator = adapter.book(data.offer_ref, pax, data.contact_phone)
        except MahanError as exc:
            if exc.ambiguous or exc.code in RETRYABLE:
                resp = {"hold_id": hold_id, "status": "unknown", "provider": PROVIDER_KEY,
                        "message": "نتیجهٔ رزرو از ماهان نرسید؛ کارشناس وضعیت را بررسی می‌کند. لطفاً دوباره رزرو نکنید."}
                return finish(resp, {"stage": "book", "flights": flights, "error_code": exc.code, "reconcile": "check NRSRT before any retry"})
            resp = {"hold_id": hold_id, "status": "not_held", "provider": PROVIDER_KEY, "error": {"code": "BOOK_REFUSED", "message": "ماهان این رزرو را نپذیرفت."}}
            finish(resp, {"stage": "book", "flights": flights, "error_code": exc.code})
            raise HTTPException(409, resp["error"])
        except ValueError as exc:
            finish({"hold_id": hold_id, "status": "not_held", "provider": PROVIDER_KEY, "error": {"code": "PASSENGERS_INVALID"}}, {"stage": "passengers"})
            raise HTTPException(422, str(exc))
        resp = {"hold_id": hold_id, "status": "held", "provider": PROVIDER_KEY, "test_booking": st["mode"] == "qaa", **public_price(price),
                "ticketing": "not_issued", "issuance": "disabled_pending_owner_approval",
                "message": "صندلی نگه داشته شد؛ بلیت هنوز صادر نشده است."}
        if _is_staff(user):
            resp["record_locator"] = locator
        return finish(resp, {"stage": "book", "flights": flights, "record_locator": locator, **internal_price(price)})

    @api.get("/flights/suppliers/mahan/holds")
    def recent_holds(limit: int = Query(default=30, ge=1, le=100), user=Depends(current_user), db: Session = Depends(get_db)) -> dict:
        """Staff-only list of this tenant's recent Mahan hold attempts, read from the idempotency records the hold endpoint
        already writes (no new table). Only the stored public response is shown: no passenger data, no supplier cost."""
        if not _is_staff(user):
            raise HTTPException(403, "دسترسی ندارید")
        rows = db.scalars(select(m.IdempotencyKey).where(m.IdempotencyKey.tenant_id == user.tenant_id, m.IdempotencyKey.scope == HOLD_SCOPE)
                          .order_by(m.IdempotencyKey.created_at.desc()).limit(limit)).all()
        items = []
        for r in rows:
            try:
                stored = json.loads(r.response_json or "{}")
            except ValueError:
                stored = {}
            err = stored.get("error") if isinstance(stored.get("error"), dict) else {}
            items.append({"hold_id": r.id, "created_at": r.created_at.isoformat() if r.created_at else None, "status": stored.get("status") or "unknown",
                          "record_locator": stored.get("record_locator"), "total_amount": stored.get("total_amount"), "currency": stored.get("currency"),
                          "test_booking": stored.get("test_booking"), "error_code": err.get("code")})
        db.rollback()
        return {"provider": PROVIDER_KEY, "items": items}

    @api.post("/flights/suppliers/mahan/holds/{hold_id}/issue")
    def issue(hold_id: str, user=Depends(current_user)) -> dict:
        # TODO(owner approval): guarded path. Issuing a Mahan ticket is financial and irreversible; it stays disabled until the
        # owner approves it in writing and payment capture + reconciliation (MahanClient.issue → NRSRT/NRSETR) are wired.
        raise HTTPException(423, {"code": "ISSUANCE_DISABLED", "message": "صدور بلیت ماهان تا تأیید مالک غیرفعال است."})

    return api
