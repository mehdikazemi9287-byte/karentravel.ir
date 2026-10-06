"""Citysoft gateway contract (the flight/hotel web service documented in the CheckLine bundle).

Source: provider_contracts/citysoft_api_fields.json = technical/api-official-fields.json of the bundle, itself an
extract of https://doc.citysoft.ir/ ("examples are not complete validation schemas; no operation executed").
This module turns that documentation into: the operation map onto KarenSeir's supplier ports, request builders,
response parsers and an adapter that speaks through an injected transport. Nothing here opens a connection,
holds a credential or is registered as a rate/fare source; that needs the real contract, sandbox and credentials.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from zoneinfo import ZoneInfo

from .flight_port import FareOffer, FlightSearchQuery, FlightSegment
from .hotel_rates import RateOffer, RateQuery, RateSourceError

KEY = "citysoft"
_SPEC = json.loads((Path(__file__).parent / "provider_contracts" / "citysoft_api_fields.json").read_text(encoding="utf-8"))
# documented operation -> KarenSeir port capability (None = documented, no port yet)
OPERATIONS = {("POST", "/authenticate"): "auth.token", ("POST", "/flights/search"): "flight.search", ("POST", "/flights/rules"): "flight.fare_rules", ("POST", "/flights/baggage"): "flight.baggage",
              ("POST", "/flights/captcha"): None, ("GET", "/airlines"): "reference.airlines", ("GET", "/airportlist"): "reference.airports", ("GET", "/hotels/smartsearch"): "hotel.autocomplete",
              ("POST", "/hotels/search"): "hotel.search", ("POST", "/hotels/rooms"): "hotel.rate", ("POST", "/bookingengine/book"): "booking.reserve", ("GET", "/bookingengine/ticket"): "booking.confirm_issue",
              ("POST", "/ticketing/ticket"): "flight.issue", ("GET", "/report/ticket/pdf"): "documents.ticket_pdf", ("GET", "/contractlist"): "reconciliation.contracts", ("GET", "/ledgers"): "finance.ledger",
              ("GET", "/ledgers/budget"): "finance.budget", ("GET", "/currencyconvert"): "finance.currency_rates", ("GET", "/cip/airports"): "cip.airports", ("POST", "/cip/search"): "cip.search",
              ("GET", "/cip/flightlist"): "cip.flights", ("POST", "/cip/rules"): "cip.rules", ("POST", "/cip/cancel"): "cip.cancel", ("POST", "/cip/precancel"): "cip.precancel",
              ("POST", "/insurance/search"): "insurance.search", ("POST", "/insurance/markup/insuranceinfo"): "insurance.info"}


def documented(method: str, path: str, kind: str) -> set[str]:
    """All field paths the documentation shows for an operation (kind: request | response)."""
    out: set[str] = set()
    for op in _SPEC:
        if op["method"] == method and op["http_path"] == path:
            out |= {f["path"] for f in op[f"{kind}_example_fields"]}
    return out


def operations() -> list[dict]:
    seen, out = set(), []
    for op in _SPEC:
        k = (op["method"], op["http_path"])
        if k in seen: continue
        seen.add(k)
        out.append({"method": k[0], "path": k[1], "capability": OPERATIONS.get(k), "request_fields": len(documented(*k, "request")), "response_fields": len(documented(*k, "response")),
                    "required_parameters": [p["name"] for p in op["parameters"] if p.get("required_marker")]})
    return out


def paths_of(value: Any, prefix: str = "") -> set[str]:
    """Field paths of a payload in the documentation's notation (lists as [])."""
    out: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            p = f"{prefix}.{k}" if prefix else k
            out |= paths_of(v, p) or {p}
    elif isinstance(value, list):
        for item in value:
            out |= paths_of(item, prefix + "[]") if isinstance(item, (dict, list)) else {prefix}
        if not value: out.add(prefix)
    else:
        out.add(prefix)
    return out


def flight_search_request(query: FlightSearchQuery, lang: str = "FA") -> dict:
    return {"Lang": lang, "TravelerInfoSummary": {"AirTravelerAvail": {"PassengerTypeQuantity": [{"Code": code, "Quantity": int(n)} for code, n in query.passengers.items() if int(n) > 0]}},
            "OriginDestinationInformations": [{"OriginLocation": {"LocationCode": query.origin}, "DestinationLocation": {"LocationCode": query.destination}, "DepartureDateTime": query.depart_on.date().isoformat()}]
            + ([{"OriginLocation": {"LocationCode": query.destination}, "DestinationLocation": {"LocationCode": query.origin}, "DepartureDateTime": query.return_on.date().isoformat()}] if query.return_on else [])}


def hotel_rooms_request(query: RateQuery, lang: str = "FA", nationality: str = "IR", currency: str = "IRR") -> dict:
    """provider_hotel_id is the supplier's CitynetCode (the value stored in the verified catalog mapping)."""
    return {"Lang": lang, "CheckInDate": query.checkin.isoformat(), "CheckOutDate": query.checkout.isoformat(), "CitynetCode": query.provider_hotel_id, "GuestNationality": nationality, "PreferredCurrencyCode": currency,
            "RoomGuests": [{"AdultCount": query.adults, "ChildAge": [0] * query.children}]}


def _when(text: Any, zone: Optional[ZoneInfo]) -> Optional[datetime]:
    if not isinstance(text, str) or not text.strip(): return None
    try: value = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError: return None
    if value.tzinfo is None:
        if zone is None: return None  # a wall-clock time without a stated zone is not guessed
        value = value.replace(tzinfo=zone)
    return value


def parse_flight_search(payload: Mapping[str, Any], *, offer_ttl: timedelta, zone: Optional[ZoneInfo] = None, now: Optional[datetime] = None) -> list[FareOffer]:
    """Documented /flights/search response -> domain fares. Items that miss a documented mandatory value are skipped, never repaired."""
    now = now or datetime.now(timezone.utc)
    if payload.get("Success") is not True: return []
    offers = []
    for item in payload.get("Items") or []:
        itinerary = (item.get("AirItinerary") or [{}])[0]
        fare = (item.get("AirItineraryPricingInfo") or {}).get("ItinTotalFare") or {}
        ref = ":".join(str(itinerary.get(k)) for k in ("SessionId", "CombinationId", "RecommendationId", "SubsystemId"))
        options = (item.get("OriginDestinationInformation") or {}).get("OriginDestinationOption") or []
        segments = []
        for option in options:
            for s in option.get("FlightSegment") or []:
                dep, arr = _when(s.get("DepartureDateTime"), zone), _when(s.get("ArrivalDateTime"), zone)
                carrier = (s.get("MarketingAirline") or {}).get("Code")
                if dep is None or arr is None or not carrier: segments = None; break
                segments.append(FlightSegment(str(carrier), str(s.get("FlightNumber") or ""), str((s.get("DepartureAirport") or {}).get("LocationCode") or ""), str((s.get("ArrivalAirport") or {}).get("LocationCode") or ""), dep, arr))
            if segments is None: break
        total = fare.get("TotalFare")
        if not segments or "None" in ref or not isinstance(total, (int, float)) or isinstance(total, bool) or total != int(total): continue
        offers.append(FareOffer(provider_offer_ref=ref, segments=tuple(segments), total_amount=int(total), currency=str(fare.get("Currency") or ""), fare_basis=str((options[0].get("FlightSegment") or [{}])[0].get("ResBookDesigCode") or ""),
                                refundable=None, expires_at=now + offer_ttl))
    return offers


def parse_hotel_rooms(payload: Mapping[str, Any], query: RateQuery, *, offer_ttl: timedelta, zone: Optional[ZoneInfo] = None, now: Optional[datetime] = None) -> list[RateOffer]:
    """Documented /hotels/rooms response -> one offer per room combination; the amount is the sum of the rooms' documented totals."""
    now = now or datetime.now(timezone.utc)
    if payload.get("Success") is not True: return []
    offers = []
    for item in payload.get("Items") or []:
        info = item.get("HotelInfo") or {}
        if str(info.get("CitynetCode") or "") != query.provider_hotel_id: continue
        expires = _when(item.get("expiredAt"), zone) or now + offer_ttl
        for combo in item.get("Combinations") or []:
            it, rooms = combo.get("HotelItinerary") or {}, combo.get("Rooms") or []
            fares = [((r.get("HotelItineraryPricingInfo") or {}).get("ItinTotalFare") or {}) for r in rooms]
            totals, currencies = [f.get("Total") for f in fares], {f.get("Currency") for f in fares}
            ref = ":".join(str(it.get(k)) for k in ("SessionId", "CombinationId", "RecommendationId", "SubsystemId"))
            if not rooms or "None" in ref or len(currencies) != 1 or any(not isinstance(t, (int, float)) or isinstance(t, bool) or t != int(t) for t in totals): continue
            offers.append(RateOffer(provider_hotel_id=query.provider_hotel_id, provider_offer_ref=ref, room_name=" + ".join(str(r.get("RoomTypeName") or r.get("RoomType") or "") for r in rooms).strip(" +"),
                                    total_amount=int(sum(totals)), currency=str(next(iter(currencies)) or ""), refundable=None, expires_at=expires))
    return offers


class CitysoftAdapter:
    """HotelRateSource/flight search over an injected transport: transport(method, path, json_body, token) -> dict.
    Construct it only with a real base contract; it is never registered by this codebase."""
    key = KEY

    def __init__(self, *, transport: Optional[Callable[[str, str, Optional[dict], Optional[str]], Mapping[str, Any]]], username: str = "", password: str = "", offer_ttl_seconds: int = 0, provider_timezone: str = ""):
        self.transport, self.username, self.password = transport, username, password
        self.offer_ttl = timedelta(seconds=offer_ttl_seconds)
        self.zone = ZoneInfo(provider_timezone) if provider_timezone else None
        self._token: Optional[str] = None

    def validate_configuration(self) -> None:
        missing = [n for n, v in (("transport", self.transport), ("username", self.username), ("password", self.password), ("offer_ttl_seconds", self.offer_ttl.total_seconds() > 0)) if not v]
        if missing: raise RateSourceError("citysoft adapter is not configured: " + ", ".join(missing))

    def _call(self, method: str, path: str, body: Optional[dict]) -> Mapping[str, Any]:
        self.validate_configuration()
        if self._token is None:
            auth = self.transport("POST", "/authenticate", {"username": self.username, "password": self.password}, None)
            if auth.get("Success") is not True or not auth.get("token"): raise RateSourceError("citysoft authentication was not accepted")
            self._token = str(auth["token"])
        return self.transport(method, path, body, self._token)

    def quote(self, query: RateQuery) -> list[RateOffer]:
        return parse_hotel_rooms(self._call("POST", "/hotels/rooms", hotel_rooms_request(query)), query, offer_ttl=self.offer_ttl, zone=self.zone)

    def search(self, query: FlightSearchQuery) -> list[FareOffer]:
        return parse_flight_search(self._call("POST", "/flights/search", flight_search_request(query)), offer_ttl=self.offer_ttl, zone=self.zone)
