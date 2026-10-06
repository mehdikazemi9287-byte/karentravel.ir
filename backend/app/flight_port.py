"""Flight supplier port. Provider-specific logic (GDS, NDC, charter APIs) stays behind FlightSupplierPort;
the domain sees only these dataclasses. No source is registered at runtime, so no fare or seat ever appears
without a real supplier. Reference data (airlines, airports) comes from the master catalog.

  search → fare (rules) → revalidate → create_pnr → issue → void | refund ; schedule changes arrive as events
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Protocol

CURRENCIES = {"IRR", "USD", "EUR", "AED", "TRY"}
PASSENGER_TYPES = ("ADT", "CHD", "INF")
PNR_STATES = {"held": {"ticketed", "cancelled", "expired"}, "ticketed": {"voided", "refunded", "schedule_changed"}, "schedule_changed": {"ticketed", "refunded"},
              "voided": set(), "refunded": set(), "cancelled": set(), "expired": set()}


@dataclass(frozen=True)
class FlightSegment:
    carrier: str            # IATA airline code, must exist in catalog_airlines
    flight_number: str
    origin: str             # IATA airport code, must exist in catalog_airports
    destination: str
    departs_at: datetime    # timezone-aware
    arrives_at: datetime


@dataclass(frozen=True)
class FlightSearchQuery:
    origin: str
    destination: str
    depart_on: datetime
    passengers: dict        # {"ADT": 1, "CHD": 0, "INF": 0}
    return_on: Optional[datetime] = None


@dataclass(frozen=True)
class FareOffer:
    provider_offer_ref: str
    segments: tuple[FlightSegment, ...]
    total_amount: int
    currency: str
    fare_basis: str
    refundable: Optional[bool]
    expires_at: datetime
    baggage: Optional[str] = None


@dataclass(frozen=True)
class Pnr:
    record_locator: str
    provider_offer_ref: str
    status: str             # see PNR_STATES
    total_amount: int
    currency: str
    ticket_time_limit: Optional[datetime] = None
    ticket_numbers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleChange:
    record_locator: str
    old_segment: FlightSegment
    new_segment: Optional[FlightSegment]   # None = flight cancelled by the carrier
    reported_at: datetime


class FlightContractViolation(RuntimeError):
    pass


class FlightSupplierPort(Protocol):
    key: str

    def search(self, query: FlightSearchQuery) -> list[FareOffer]: ...
    def fare_rules(self, offer: FareOffer) -> dict: ...
    def revalidate(self, offer: FareOffer) -> Optional[FareOffer]: ...
    def create_pnr(self, offer: FareOffer, passengers: list[dict], idempotency_key: str) -> Pnr: ...
    def issue(self, record_locator: str, idempotency_key: str) -> Pnr: ...
    def void(self, record_locator: str, idempotency_key: str) -> Pnr: ...
    def refund(self, record_locator: str, idempotency_key: str) -> tuple[Pnr, int]: ...
    def schedule_changes(self, since: datetime) -> list[ScheduleChange]: ...


FLIGHT_SOURCES: dict[str, FlightSupplierPort] = {}  # filled only by a configured, real supplier adapter


def validate_search(query: FlightSearchQuery, airport_exists: Callable[[str], bool], now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    if query.origin == query.destination or not airport_exists(query.origin) or not airport_exists(query.destination): raise ValueError("مبدأ یا مقصد در فهرست فرودگاه‌ها نیست")
    if query.depart_on.tzinfo is None or query.depart_on.date() < now.date() or (query.return_on is not None and query.return_on < query.depart_on): raise ValueError("تاریخ پرواز نامعتبر است")
    counts = {k: int(query.passengers.get(k, 0)) for k in PASSENGER_TYPES}
    if set(query.passengers) - set(PASSENGER_TYPES) or counts["ADT"] < 1 or sum(counts.values()) > 9 or counts["INF"] > counts["ADT"] or min(counts.values()) < 0: raise ValueError("ترکیب مسافران نامعتبر است")


def validate_fares(query: FlightSearchQuery, offers: list[FareOffer], airline_exists: Callable[[str], bool], airport_exists: Callable[[str], bool], now: Optional[datetime] = None) -> list[FareOffer]:
    """A fare that breaks any rule is dropped, never repaired: unknown carrier/airport, broken chronology, wrong route, non-positive or non-integer price, unknown currency, expired or timezone-less validity."""
    now = now or datetime.now(timezone.utc)

    def ok(o: FareOffer) -> bool:
        if not o.provider_offer_ref or not o.segments or not o.fare_basis or o.currency not in CURRENCIES: return False
        if not isinstance(o.total_amount, int) or isinstance(o.total_amount, bool) or o.total_amount <= 0: return False
        if o.expires_at.tzinfo is None or o.expires_at <= now: return False
        if o.segments[0].origin != query.origin or o.segments[0].departs_at.date() != query.depart_on.date(): return False
        if query.destination not in {s.destination for s in o.segments}: return False
        previous = None
        for s in o.segments:
            if s.departs_at.tzinfo is None or s.arrives_at.tzinfo is None or s.arrives_at <= s.departs_at or s.arrives_at - s.departs_at > timedelta(hours=24): return False
            if not airline_exists(s.carrier) or not airport_exists(s.origin) or not airport_exists(s.destination) or s.origin == s.destination or not s.flight_number: return False
            if previous is not None and (s.origin != previous.destination or s.departs_at < previous.arrives_at): return False
            previous = s
        return True
    return [o for o in offers if ok(o)]


def revalidate_decision(shown: FareOffer, fresh: Optional[FareOffer], now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if fresh is None: return {"status": "expired" if shown.expires_at <= now else "unavailable"}
    if fresh.segments != shown.segments: return {"status": "schedule_changed", "offer": fresh}
    if fresh.total_amount != shown.total_amount or fresh.currency != shown.currency: return {"status": "price_changed", "previous_amount": shown.total_amount, "offer": fresh}
    return {"status": "ok", "offer": fresh}


def check_pnr(pnr: Pnr, offer: FareOffer, expect: str, now: Optional[datetime] = None) -> Pnr:
    now = now or datetime.now(timezone.utc)
    if not pnr.record_locator or pnr.status != expect or pnr.provider_offer_ref != offer.provider_offer_ref: raise FlightContractViolation(f"expected {expect} PNR for this offer")
    if pnr.total_amount != offer.total_amount or pnr.currency != offer.currency: raise FlightContractViolation("amount differs from the revalidated fare")
    if expect == "held" and (pnr.ticket_time_limit is None or pnr.ticket_time_limit.tzinfo is None or pnr.ticket_time_limit <= now): raise FlightContractViolation("PNR without a valid ticketing time limit")
    if expect == "ticketed" and (not pnr.ticket_numbers or any(not t for t in pnr.ticket_numbers)): raise FlightContractViolation("issued PNR without ticket numbers")
    return pnr


def check_transition(current: str, target: str) -> None:
    if target not in PNR_STATES.get(current, set()): raise FlightContractViolation(f"illegal transition {current} -> {target}")


def check_refund(amount: int, pnr: Pnr) -> int:
    if not isinstance(amount, int) or isinstance(amount, bool) or not 0 <= amount <= pnr.total_amount: raise FlightContractViolation("refund outside the paid amount")
    return amount


def schedule_change_event(change: ScheduleChange) -> dict:
    """Translate a carrier schedule change into the single trip-event shape (category, old value, new value). No guessing: only what the supplier reported."""
    def seg(s: FlightSegment) -> dict:
        return {"پرواز": f"{s.carrier}{s.flight_number}", "مسیر": f"{s.origin}-{s.destination}", "حرکت": s.departs_at.isoformat(), "رسیدن": s.arrives_at.isoformat()}
    if change.new_segment is None:
        return {"category": "cancellation", "severity": "critical", "source": "provider", "old_value": seg(change.old_segment), "new_value": None, "requires_action": True, "affected_reference": change.record_locator}
    shift = abs(change.new_segment.departs_at - change.old_segment.departs_at)
    return {"category": "schedule_change", "severity": "critical" if shift >= timedelta(hours=3) or change.new_segment.departs_at.date() != change.old_segment.departs_at.date() else "warning", "source": "provider",
            "old_value": seg(change.old_segment), "new_value": seg(change.new_segment), "requires_action": shift >= timedelta(hours=3), "affected_reference": change.record_locator}
