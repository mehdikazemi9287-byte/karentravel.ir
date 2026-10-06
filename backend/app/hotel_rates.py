"""Hotel rate/availability port (ADR-028 addendum 2).

The master catalog never stores a price. A rate is something a *supplier* says about a hotel it knows by its
own id, for concrete dates. This module is the only door between the two:

  catalog hotel --(verified CatalogHotelProviderMapping)--> provider hotel id --(HotelRateSource.quote)--> offers

No rate source is registered at runtime until a real supplier adapter (GRS or another) is configured with its
contract and credentials, so every hotel reports rate_available=false and the rates endpoint answers
`no_rate_source`. Nothing here fabricates, caches or defaults a price.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import CatalogHotel, CatalogHotelProviderMapping, HotelOfferSnapshot

CURRENCIES = {"IRR", "USD", "EUR", "AED", "TRY"}


@dataclass(frozen=True)
class RateQuery:
    provider_hotel_id: str
    checkin: date
    checkout: date
    adults: int
    children: int = 0


@dataclass(frozen=True)
class RateOffer:
    provider_hotel_id: str
    provider_offer_ref: str
    room_name: str
    total_amount: int          # minor-unit-free integer in `currency`, for the whole stay
    currency: str
    refundable: Optional[bool]  # None = the supplier did not say
    expires_at: datetime        # the supplier's own validity; an offer without one is not sellable


class RateSourceError(RuntimeError):
    """The supplier could not be reached or answered outside its contract. Never turned into an empty/zero price."""


class HotelRateSource(Protocol):
    key: str  # equals CatalogHotelProviderMapping.provider

    def quote(self, query: RateQuery) -> list[RateOffer]: ...


RATE_SOURCES: dict[str, HotelRateSource] = {}  # filled only by a configured, real supplier adapter


def validate_offers(query: RateQuery, offers: list[RateOffer], now: Optional[datetime] = None) -> list[RateOffer]:
    """Contract every adapter must satisfy; a violating offer is dropped, never repaired."""
    now = now or datetime.now(timezone.utc)
    return [o for o in offers if o.provider_hotel_id == query.provider_hotel_id and isinstance(o.total_amount, int) and not isinstance(o.total_amount, bool) and o.total_amount > 0
            and o.currency in CURRENCIES and o.provider_offer_ref and o.room_name and o.expires_at.tzinfo is not None and o.expires_at > now]


def rateable_hotel_ids(db: Session, hotel_ids: set[str]) -> set[str]:
    """Hotels for which a live rate can be requested at all: a verified mapping to a registered source."""
    if not RATE_SOURCES or not hotel_ids:
        return set()
    return set(db.scalars(select(CatalogHotelProviderMapping.hotel_id).where(CatalogHotelProviderMapping.hotel_id.in_(hotel_ids), CatalogHotelProviderMapping.status == "verified",
                                                                             CatalogHotelProviderMapping.provider.in_(set(RATE_SOURCES)))))


def quote_hotel(db: Session, hotel: CatalogHotel, checkin: date, checkout: date, adults: int, children: int = 0) -> dict:
    mappings = db.scalars(select(CatalogHotelProviderMapping).where(CatalogHotelProviderMapping.hotel_id == hotel.id, CatalogHotelProviderMapping.status == "verified")).all()
    usable = [m for m in mappings if m.provider in RATE_SOURCES]
    if not usable:
        return {"status": "no_rate_source", "offers": [], "price": None}
    offers, errors = [], 0
    for m in usable:
        query = RateQuery(m.provider_hotel_id, checkin, checkout, adults, children)
        try:
            offers += [(m.provider, o) for o in validate_offers(query, RATE_SOURCES[m.provider].quote(query))]
        except RateSourceError:
            errors += 1
    if not offers:
        return {"status": "rate_source_unavailable" if errors else "no_availability", "offers": [], "price": None}
    out = []
    for p, o in sorted(offers, key=lambda x: (x[1].currency, x[1].total_amount)):
        snap = HotelOfferSnapshot(hotel_id=hotel.id, provider=p, provider_hotel_id=o.provider_hotel_id, provider_offer_ref=o.provider_offer_ref, room_name=o.room_name, total_amount=o.total_amount,
                                  currency=o.currency, refundable=o.refundable, checkin=checkin, checkout=checkout, adults=adults, children=children, expires_at=o.expires_at, created_at=datetime.now(timezone.utc))
        db.add(snap); db.flush()
        out.append({"snapshot_id": snap.id, "provider": p, "offer_ref": o.provider_offer_ref, "room_name": o.room_name, "total_amount": o.total_amount, "currency": o.currency,
                    "refundable": o.refundable, "expires_at": o.expires_at.isoformat()})
    return {"status": "ok", "price": None, "offers": out}


def _offer_of(s: HotelOfferSnapshot) -> RateOffer:
    expires = s.expires_at if s.expires_at.tzinfo else s.expires_at.replace(tzinfo=timezone.utc)
    return RateOffer(s.provider_hotel_id, s.provider_offer_ref, s.room_name, s.total_amount, s.currency, s.refundable, expires)


def recheck_snapshot(db: Session, snapshot: HotelOfferSnapshot) -> dict:
    source = RATE_SOURCES.get(snapshot.provider)
    mapped = db.scalar(select(CatalogHotelProviderMapping.id).where(CatalogHotelProviderMapping.hotel_id == snapshot.hotel_id, CatalogHotelProviderMapping.provider == snapshot.provider,
                                                                    CatalogHotelProviderMapping.provider_hotel_id == snapshot.provider_hotel_id, CatalogHotelProviderMapping.status == "verified"))
    if source is None or mapped is None or not hasattr(source, "recheck"):
        return {"status": "no_rate_source", "snapshot_id": snapshot.id, "price": None}
    query, shown = RateQuery(snapshot.provider_hotel_id, snapshot.checkin, snapshot.checkout, snapshot.adults, snapshot.children), _offer_of(snapshot)
    try:
        decision = recheck_decision(shown, source.recheck(shown, query), query)
    except RateSourceError:
        return {"status": "rate_source_unavailable", "snapshot_id": snapshot.id, "price": None}
    fresh = decision.pop("offer", None)
    if fresh is not None and decision["status"] == "price_changed":
        new = HotelOfferSnapshot(hotel_id=snapshot.hotel_id, provider=snapshot.provider, provider_hotel_id=fresh.provider_hotel_id, provider_offer_ref=fresh.provider_offer_ref, room_name=fresh.room_name,
                                 total_amount=fresh.total_amount, currency=fresh.currency, refundable=fresh.refundable, checkin=snapshot.checkin, checkout=snapshot.checkout, adults=snapshot.adults,
                                 children=snapshot.children, expires_at=fresh.expires_at, created_at=datetime.now(timezone.utc))
        db.add(new); db.flush()
        decision.update({"new_snapshot_id": new.id, "new_amount": fresh.total_amount, "currency": fresh.currency})
    return {"snapshot_id": snapshot.id, "price": None, **decision}


# ======================================================================================================================
# Full supplier port: search → availability → rate → recheck → reserve → confirm → cancel
# ======================================================================================================================
# Mapping chain persisted in the catalog (all admin-entered, verified against the supplier, never guessed):
#   CatalogHotel ↔ CatalogHotelProviderMapping(provider, provider_hotel_id)
#                 ↔ CatalogHotelRoomMapping(room_type_id ↔ provider_room_id)
#                 ↔ CatalogHotelRatePlanMapping(provider_rate_plan_id, board, refundable)
# A quote shown to a customer is stored as a HotelOfferSnapshot so that recheck/reserve can prove what was offered.

BOARDS = {"RO": "بدون وعده", "BB": "صبحانه", "HB": "نیم‌پانسیون", "FB": "تمام‌پانسیون", "AI": "همه‌چیز رایگان", "UAI": "اولترا آل‌اینکلوسیو"}
RESERVATION_STATES = {"reserved": {"confirmed", "cancelled", "expired"}, "confirmed": {"cancelled"}, "cancelled": set(), "expired": set()}


@dataclass(frozen=True)
class HotelSearchQuery:
    provider_hotel_ids: tuple[str, ...]
    checkin: date
    checkout: date
    adults: int
    children: int = 0


@dataclass(frozen=True)
class ProviderReservation:
    provider_reservation_ref: str
    provider_offer_ref: str
    status: str                 # reserved | confirmed | cancelled | expired
    total_amount: int
    currency: str
    hold_expires_at: Optional[datetime] = None


@dataclass(frozen=True)
class CancellationResult:
    provider_reservation_ref: str
    status: str                 # cancelled
    refund_amount: int
    currency: str


class HotelSupplierPort(HotelRateSource, Protocol):
    """Everything provider-specific lives behind this. The domain only ever sees the dataclasses above."""

    def search(self, query: HotelSearchQuery) -> list[RateOffer]: ...
    def availability(self, query: RateQuery) -> bool: ...
    def recheck(self, offer: RateOffer, query: RateQuery) -> Optional[RateOffer]: ...      # None = no longer available
    def reserve(self, offer: RateOffer, query: RateQuery, idempotency_key: str) -> ProviderReservation: ...
    def confirm(self, provider_reservation_ref: str, idempotency_key: str) -> ProviderReservation: ...
    def cancel(self, provider_reservation_ref: str, idempotency_key: str) -> CancellationResult: ...


class ContractViolation(RuntimeError):
    """The supplier answered outside the contract. The operation fails closed; nothing is repaired or assumed."""


def validate_query(checkin: date, checkout: date, adults: int, children: int = 0, today: Optional[date] = None) -> None:
    today = today or datetime.now(timezone.utc).date()
    if checkin < today: raise ValueError("تاریخ ورود گذشته است")
    if checkout <= checkin or (checkout - checkin).days > 30: raise ValueError("بازهٔ اقامت نامعتبر است")
    if not 1 <= adults <= 12 or not 0 <= children <= 8: raise ValueError("تعداد مهمان نامعتبر است")


def recheck_decision(shown: RateOffer, fresh: Optional[RateOffer], query: RateQuery, now: Optional[datetime] = None) -> dict:
    """What may happen to an offer the customer already saw. A changed price is surfaced, never silently accepted."""
    now = now or datetime.now(timezone.utc)
    if shown.expires_at <= now and fresh is None: return {"status": "expired"}
    if fresh is None: return {"status": "unavailable"}
    if not validate_offers(query, [fresh], now): return {"status": "unavailable", "reason": "contract_violation"}
    if fresh.currency != shown.currency: return {"status": "price_changed", "reason": "currency_changed", "offer": fresh}
    if fresh.total_amount != shown.total_amount: return {"status": "price_changed", "previous_amount": shown.total_amount, "offer": fresh}
    return {"status": "ok", "offer": fresh}


def check_reservation(result: ProviderReservation, offer: RateOffer, expect: str, now: Optional[datetime] = None) -> ProviderReservation:
    now = now or datetime.now(timezone.utc)
    if not result.provider_reservation_ref or result.status != expect: raise ContractViolation(f"expected status {expect}")
    if result.provider_offer_ref != offer.provider_offer_ref: raise ContractViolation("reservation is for another offer")
    if result.total_amount != offer.total_amount or result.currency != offer.currency or result.total_amount <= 0: raise ContractViolation("amount differs from the rechecked offer")
    if expect == "reserved" and (result.hold_expires_at is None or result.hold_expires_at.tzinfo is None or result.hold_expires_at <= now): raise ContractViolation("hold without a valid expiry")
    return result


def check_transition(current: str, target: str) -> None:
    if target not in RESERVATION_STATES.get(current, set()): raise ContractViolation(f"illegal transition {current} -> {target}")


def check_cancellation(result: CancellationResult, reservation: ProviderReservation) -> CancellationResult:
    if result.status != "cancelled" or result.provider_reservation_ref != reservation.provider_reservation_ref: raise ContractViolation("cancellation not acknowledged")
    if not isinstance(result.refund_amount, int) or isinstance(result.refund_amount, bool) or not 0 <= result.refund_amount <= reservation.total_amount or result.currency != reservation.currency:
        raise ContractViolation("refund outside the paid amount")
    return result


def book_through_port(port: HotelSupplierPort, shown: RateOffer, query: RateQuery, idempotency_key: str, now: Optional[datetime] = None) -> ProviderReservation:
    """recheck → reserve → confirm, each step verified. Callable only once a booking flow is approved (BOOKING_FROM_CATALOG_ENABLED)."""
    from .catalog import BOOKING_FROM_CATALOG_ENABLED
    if not BOOKING_FROM_CATALOG_ENABLED: raise PermissionError("booking from the catalog is not enabled")
    if not idempotency_key or len(idempotency_key) < 8: raise ValueError("idempotency key required")
    decision = recheck_decision(shown, port.recheck(shown, query), query, now)
    if decision["status"] != "ok": raise ContractViolation(f"offer not bookable: {decision['status']}")
    held = check_reservation(port.reserve(decision["offer"], query, idempotency_key), decision["offer"], "reserved", now)
    check_transition(held.status, "confirmed")
    return check_reservation(port.confirm(held.provider_reservation_ref, idempotency_key), decision["offer"], "confirmed", now)
