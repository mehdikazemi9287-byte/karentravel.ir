"""Deterministic vertical-intent detection. Keyword-substring matching only
-- no ML/AI. Ordering is fixed and iteration-stable so the same input always
produces the same output (required for cache-key/plan determinism)."""
from __future__ import annotations

from ..domain import ALLOWED_VERTICALS
from ..normalization import normalize_text

# Every key here MUST be in ALLOWED_VERTICALS (checked by a startup assertion
# below) -- Query Intelligence must never invent a vertical the orchestrator
# does not already know how to route.
SUPPORTED_VERTICAL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "flight": ("پرواز", "بلیط هواپیما", "هواپیما"),
    "hotel": ("هتل",),
    "train": ("قطار",),
    "bus": ("اتوبوس",),
    "tour": ("تور",),
    "accommodation": ("اقامتگاه", "محل اقامت"),
    "vacation_rental": ("اجاره ویلا", "ویلا"),
    "car_rental": ("اجاره ماشین", "اجاره خودرو", "کرایه ماشین"),
}
assert set(SUPPORTED_VERTICAL_KEYWORDS) <= ALLOWED_VERTICALS

# Recognized vocabulary for verticals Search does not support yet. Detecting
# one of these must never route to a fake provider -- it is surfaced as an
# explicit unsupported intent instead (planner.py / STATUS_UNSUPPORTED).
RESERVED_UNSUPPORTED_KEYWORDS: dict[str, tuple[str, ...]] = {
    "restaurant": ("رستوران",),
    "pool_sport": ("استخر", "باشگاه ورزشی"),
    "attraction": ("جاذبه گردشگری", "بازدید از"),
    "event": ("رویداد", "کنسرت"),
    "experience": ("تجربه محلی",),
}

_NORM_SUPPORTED = {v: tuple(normalize_text(k) for k in ks) for v, ks in SUPPORTED_VERTICAL_KEYWORDS.items()}
_NORM_UNSUPPORTED = {v: tuple(normalize_text(k) for k in ks) for v, ks in RESERVED_UNSUPPORTED_KEYWORDS.items()}


def _matches(keyword: str, normalized_text: str, tokens: frozenset[str]) -> bool:
    # A single-word keyword must match a WHOLE token, never a raw substring:
    # "تور" (tour) is a literal substring of "رستوران" (restaurant), and a
    # naive "in" check would misdetect a restaurant query as a tour query.
    # Multi-word phrases still use substring containment (that already
    # requires the words to appear adjacent, in order).
    if " " in keyword:
        return keyword in normalized_text
    return keyword in tokens


def detect_supported_intents(normalized_text: str) -> tuple[str, ...]:
    tokens = frozenset(normalized_text.split())
    return tuple(v for v, kws in _NORM_SUPPORTED.items() if any(_matches(kw, normalized_text, tokens) for kw in kws))


def detect_unsupported_intents(normalized_text: str) -> tuple[str, ...]:
    tokens = frozenset(normalized_text.split())
    return tuple(v for v, kws in _NORM_UNSUPPORTED.items() if any(_matches(kw, normalized_text, tokens) for kw in kws))
