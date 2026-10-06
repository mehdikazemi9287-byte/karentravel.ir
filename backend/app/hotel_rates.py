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

from .catalog import CatalogHotel, CatalogHotelProviderMapping

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
    return {"status": "ok", "price": None, "offers": [{"provider": p, "offer_ref": o.provider_offer_ref, "room_name": o.room_name, "total_amount": o.total_amount, "currency": o.currency,
                                                       "refundable": o.refundable, "expires_at": o.expires_at.isoformat()} for p, o in sorted(offers, key=lambda x: (x[1].currency, x[1].total_amount))]}
