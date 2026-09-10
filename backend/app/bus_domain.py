"""Normalized intercity-bus domain contract.

There is no selected bus/transport provider (master spec: "Transport Provider
… UNSELECTED"), so this module defines the *shape* a real adapter must satisfy
and a fail-closed default that never fabricates inventory. Bus itself is not a
parallel vertical: bus supply is ordinary ``Offer`` rows with
``service_type="bus"`` and books through the same price-check / orchestration
path as every other service. This contract only normalizes the bus-specific
attributes that live in ``Offer.attributes_json``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

BUS_SERVICE_TYPE = "bus"
BUS_SEAT_CLASSES = ("standard", "vip", "vip_25", "vip_28", "sleeper")


@dataclass(frozen=True)
class BusSearchQuery:
    origin: str
    destination: str
    depart_date: str                     # ISO date
    passengers: int = 1
    seat_class: Optional[str] = None


@dataclass(frozen=True)
class NormalizedBusOffer:
    offer_ref: str                       # internal Offer.id or provider offer id
    operator: str
    origin_terminal: str
    destination_terminal: str
    depart_at: Optional[str]             # ISO datetime
    arrive_at: Optional[str]
    bus_type: str                        # e.g. "VIP 2+1"
    seat_class: str
    seats_available: int
    base_price: int
    currency: str
    amenities: Sequence[str] = field(default_factory=tuple)
    refundable: bool = False
    provider_key: str = "manual_supplier"
    source: str = "internal_supplier"    # internal_supplier | external_provider | fixture

    def as_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d["amenities"] = list(self.amenities)
        return d


@runtime_checkable
class BusProviderPort(Protocol):
    """Interface a real bus provider adapter must implement to plug into the
    generic Offer/Reservation flow. No implementation may fabricate a
    successful external result without an authorized transport."""

    key: str
    mode: str

    def health(self) -> Mapping[str, Any]: ...
    def search(self, query: BusSearchQuery) -> Sequence[NormalizedBusOffer]: ...
    def recheck(self, offer_ref: str) -> Optional[NormalizedBusOffer]: ...
    def reserve(self, offer_ref: str, passengers: int, context: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def confirm(self, reservation_ref: str, context: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def cancel(self, reservation_ref: str, context: Mapping[str, Any]) -> Mapping[str, Any]: ...


def _not_configured(operation: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "not_connected",
        "operation": operation,
        "reason": "external_bus_provider_not_configured",
        "detail": "No authorized bus/transport provider is selected (master spec: UNSELECTED).",
    }


class DisabledBusProvider:
    """Fail-closed default. Implements BusProviderPort; never returns inventory
    or a successful reservation."""

    key = "bus"

    def __init__(self, mode: str = "disabled") -> None:
        self.mode = mode

    def health(self) -> dict[str, Any]:
        return {"key": self.key, "mode": self.mode, "status": "not_connected",
                "detail": "Bus provider UNSELECTED; external bus search/booking is unavailable."}

    def search(self, query: BusSearchQuery) -> Sequence[NormalizedBusOffer]:
        return ()

    def recheck(self, offer_ref: str) -> Optional[NormalizedBusOffer]:
        return None

    def reserve(self, offer_ref: str, passengers: int, context: Mapping[str, Any]) -> dict[str, Any]:
        return _not_configured("reserve")

    def confirm(self, reservation_ref: str, context: Mapping[str, Any]) -> dict[str, Any]:
        return _not_configured("confirm")

    def cancel(self, reservation_ref: str, context: Mapping[str, Any]) -> dict[str, Any]:
        return _not_configured("cancel")


def normalize_offer_row(offer: Any) -> NormalizedBusOffer:
    """Map a generic bus ``Offer`` row to the normalized contract. Bus-specific
    fields come from ``attributes_json``; anything absent is reported honestly
    rather than invented."""
    import json

    attrs = {}
    try:
        attrs = json.loads(offer.attributes_json or "{}")
    except (TypeError, ValueError):
        attrs = {}
    policy = {}
    try:
        policy = json.loads(offer.policy_json or "{}")
    except (TypeError, ValueError):
        policy = {}
    seat_class = str(attrs.get("seat_class") or "standard")
    if seat_class not in BUS_SEAT_CLASSES:
        seat_class = "standard"
    amenities = attrs.get("amenities")
    amenities = tuple(str(a) for a in amenities) if isinstance(amenities, list) else ()
    return NormalizedBusOffer(
        offer_ref=offer.id,
        operator=str(attrs.get("operator") or offer.title),
        origin_terminal=str(attrs.get("origin_terminal") or attrs.get("origin") or ""),
        destination_terminal=str(attrs.get("destination_terminal") or attrs.get("destination") or ""),
        depart_at=attrs.get("depart_at"),
        arrive_at=attrs.get("arrive_at"),
        bus_type=str(attrs.get("bus_type") or "unspecified"),
        seat_class=seat_class,
        seats_available=int(offer.available_units),
        base_price=int(offer.amount),
        currency=offer.currency,
        amenities=amenities,
        refundable=bool(policy.get("refundable", False)),
        provider_key=offer.provider_key,
        source="internal_supplier",
    )


def build_search_query(payload: Mapping[str, Any]) -> BusSearchQuery:
    return BusSearchQuery(
        origin=str(payload.get("origin") or "").strip(),
        destination=str(payload.get("destination") or "").strip(),
        depart_date=str(payload.get("depart_date") or "").strip(),
        passengers=max(1, min(int(payload.get("passengers", 1) or 1), 20)),
        seat_class=(str(payload["seat_class"]) if payload.get("seat_class") in BUS_SEAT_CLASSES else None),
    )
