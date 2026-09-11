"""Deterministic relative Persian date parsing -> canonical ISO dates.

No Jalali calendar library is introduced -- none exists anywhere in
search-service or is needed here, and output is always Gregorian ISO
(YYYY-MM-DD), the same convention the existing structured /v1/search
check_in/check_out filters already use. Only a closed, enumerated set of
relative expressions is recognized; this is not a general calendar parser."""
from __future__ import annotations

import re
from datetime import date, timedelta

from .models import DateRange

# Checked longest-phrase-first so "پس فردا" (day after tomorrow) is never
# misread as "فردا" (tomorrow) just because "فردا" is a substring of it.
_RELATIVE_SINGLE_DAY = (
    ("پس فردا", 2),
    ("فردا", 1),
    ("امروز", 0),
)

# normalize_text strips punctuation to spaces, so an explicit "2026-09-15" in
# the raw query survives normalization as "2026 09 15" -- match that shape.
_EXPLICIT_DATE_RE = re.compile(r"\b(\d{4})\s+(\d{2})\s+(\d{2})\b")


def resolve_relative_date(normalized_text: str, today: date) -> DateRange | None:
    for phrase, offset in _RELATIVE_SINGLE_DAY:
        if phrase in normalized_text:
            d = (today + timedelta(days=offset)).isoformat()
            return DateRange(start_date=d, end_date=d, source="relative")
    if "این هفته" in normalized_text:
        return DateRange(start_date=today.isoformat(), end_date=(today + timedelta(days=6)).isoformat(), source="relative")
    if "آخر هفته" in normalized_text:
        # Deliberate simplification: the next Friday as a single-day
        # approximation, documented rather than presented as more precise
        # than it is.
        days_ahead = (4 - today.weekday()) % 7 or 7
        d = (today + timedelta(days=days_ahead)).isoformat()
        return DateRange(start_date=d, end_date=d, source="relative")
    return None


def resolve_explicit_date(normalized_text: str) -> DateRange | None:
    m = _EXPLICIT_DATE_RE.search(normalized_text)
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return DateRange(start_date=d.isoformat(), end_date=d.isoformat(), source="explicit")
