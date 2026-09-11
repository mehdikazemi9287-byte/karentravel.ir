"""Deterministic numeric constraint + basic filter extraction. Operates on
normalize_text-normalized text (Persian/Arabic digits already converted to
Latin). Only recognizes explicit, unambiguous signals -- never invents a
default; defaults belong to a separate policy layer, not here."""
from __future__ import annotations

import re

from ..domain import SAFE_FILTER_KEYS

# Persian spelled-out numbers 1-10 -- travel phrases commonly use these
# ("سه شب", "یک اتاق") rather than digits. Only matched immediately before a
# unit word (نفر/اتاق/شب), so "نه" (nine) is never confused with the
# unrelated negation particle "نه" ("no") in ordinary text.
_NUMBER_WORDS = {"یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5,
                 "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10}
_NUMBER_ALT = r"(\d+|" + "|".join(_NUMBER_WORDS) + r")"

_TRAVELLERS_RE = re.compile(_NUMBER_ALT + r"\s*(نفر|بزرگسال|مسافر)")
_ROOMS_RE = re.compile(_NUMBER_ALT + r"\s*اتاق")
_NIGHTS_RE = re.compile(_NUMBER_ALT + r"\s*شب")
_CHILDREN_RE = re.compile(_NUMBER_ALT + r"\s*(کودک|بچه)")
_STAR_RE = re.compile(r"(\d+)\s*ستاره")
# زیر/حداکثر/تا سقف = an explicit ceiling; حدود = "around" -- both are read
# conservatively as a soft ceiling (max_price), never as inventing a minimum.
_PRICE_RE = re.compile(r"(?:زیر|حداکثر|تا سقف|حدود)\s*" + _NUMBER_ALT + r"\s*(میلیون|هزار)?")

_REFUNDABLE_PHRASES = ("قابل استرداد", "استرداد پذیر")
_BREAKFAST_PHRASES = ("صبحانه",)
_DIRECT_PHRASES = ("مستقیم",)
_NEARBY_PHRASES = ("نزدیک",)
_CHEAPEST_PHRASES = ("ارزان ترین", "ارزانترین", "ارزون ترین", "ارزونترین")
_CHEAP_PHRASES = ("ارزان", "ارزون")   # ارزون: common colloquial pronunciation of ارزان
_BEST_PHRASES = ("بهترین",)
_ONE_WAY_PHRASES = ("یک طرفه", "یکطرفه", "فقط رفت")
_ROUND_TRIP_PHRASES = ("رفت و برگشت", "رفت برگشت")
_CABIN_KEYWORDS = (
    ("بیزینس", "business"),
    ("فرست کلاس", "first"), ("درجه یک", "first"),
    ("اکونومی", "economy"), ("اقتصادی", "economy"),
)

_PRICE_MULTIPLIER = {"میلیون": 1_000_000, "هزار": 1_000}


def _to_int(token: str) -> int:
    return _NUMBER_WORDS.get(token, 0) or int(token)


def extract_travellers(normalized_text: str) -> int | None:
    m = _TRAVELLERS_RE.search(normalized_text)
    return _to_int(m.group(1)) if m else None


def extract_children(normalized_text: str) -> int | None:
    m = _CHILDREN_RE.search(normalized_text)
    return _to_int(m.group(1)) if m else None


def extract_rooms(normalized_text: str) -> int | None:
    m = _ROOMS_RE.search(normalized_text)
    return _to_int(m.group(1)) if m else None


def extract_nights(normalized_text: str) -> int | None:
    m = _NIGHTS_RE.search(normalized_text)
    return _to_int(m.group(1)) if m else None


def extract_cabin(normalized_text: str) -> str | None:
    for phrase, cabin in _CABIN_KEYWORDS:
        if phrase in normalized_text:
            return cabin
    return None


def extract_nearby_allowed(normalized_text: str) -> bool:
    return any(p in normalized_text for p in _NEARBY_PHRASES)


def extract_sort_hint(normalized_text: str) -> str | None:
    """Deterministic keyword -> sort mapping. "بهترین" maps to the existing
    "recommended" default rather than a fabricated new sort mode."""
    if any(p in normalized_text for p in _CHEAPEST_PHRASES) or any(p in normalized_text for p in _CHEAP_PHRASES):
        return "price_asc"
    if any(p in normalized_text for p in _BEST_PHRASES):
        return "recommended"
    return None


def extract_trip_type(normalized_text: str) -> str | None:
    if any(p in normalized_text for p in _ONE_WAY_PHRASES):
        return "one_way"
    if any(p in normalized_text for p in _ROUND_TRIP_PHRASES):
        return "round_trip"
    return None


def extract_filters_and_unsupported(normalized_text: str) -> tuple[dict, tuple[str, ...]]:
    """Returns (filters, unsupported_constraints). `filters` only ever
    contains keys already in domain.SAFE_FILTER_KEYS -- anything recognized
    but not mappable to an existing Search capability is reported in
    unsupported_constraints instead, never silently dropped or half-applied."""
    filters: dict = {}
    unsupported: list[str] = []

    if any(p in normalized_text for p in _REFUNDABLE_PHRASES):
        filters["refundable"] = True
    if any(p in normalized_text for p in _BREAKFAST_PHRASES):
        filters["amenities"] = ["صبحانه"]
    if any(p in normalized_text for p in _DIRECT_PHRASES):
        unsupported.append("direct_flight_only")     # no existing Search filter maps to this
    star = _STAR_RE.search(normalized_text)
    if star:
        unsupported.append(f"star_rating_{star.group(1)}")   # no existing Search filter maps to this

    price = _PRICE_RE.search(normalized_text)
    if price:
        amount = _to_int(price.group(1)) * _PRICE_MULTIPLIER.get(price.group(2) or "", 1)
        filters["max_price"] = amount   # same raw-number convention the structured frontend path already sends

    assert set(filters) <= SAFE_FILTER_KEYS
    return filters, tuple(unsupported)
