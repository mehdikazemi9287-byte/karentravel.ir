"""Deterministic relative Persian date parsing -> canonical ISO dates.

No Jalali calendar library is introduced -- none exists anywhere in
search-service or is needed here, and output is always Gregorian ISO
(YYYY-MM-DD), the same convention the existing structured /v1/search
check_in/check_out filters already use. Only a closed, enumerated set of
relative expressions/weekday names is recognized; this is not a general
calendar parser.

Phase 5: adds weekday-name resolution (for round-trip phrasing like "جمعه
برم شیراز یکشنبه برگردم") on top of the existing single-day relative
expressions. Weekday keywords are written in their POST-normalize_text form
(space instead of نیم‌فاصله/ZWNJ, e.g. "سه شنبه" not "سه‌شنبه") since that is
the form they will actually appear in by the time this module sees them."""
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

# Python weekday() convention: Monday=0 .. Sunday=6.
_WEEKDAYS = (
    ("دوشنبه", 0), ("سه شنبه", 1), ("چهارشنبه", 2), ("پنجشنبه", 3),
    ("جمعه", 4), ("شنبه", 5), ("یکشنبه", 6),
)

# normalize_text strips punctuation to spaces, so an explicit "2026-09-15" in
# the raw query survives normalization as "2026 09 15" -- match that shape.
_EXPLICIT_DATE_RE = re.compile(r"\b(\d{4})\s+(\d{2})\s+(\d{2})\b")


def _next_weekday(today: date, target_weekday: int) -> date:
    # Always a future date (1-7 days ahead), never "today" itself -- "جمعه"
    # is read as an upcoming Friday, not "if today happens to be Friday".
    days_ahead = (target_weekday - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


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
        d = _next_weekday(today, 4)
        return DateRange(start_date=d.isoformat(), end_date=d.isoformat(), source="relative")
    weekdays = find_weekday_dates(normalized_text, today)
    if weekdays:
        d = weekdays[0]
        return DateRange(start_date=d, end_date=d, source="relative")
    return None


def find_weekday_dates(normalized_text: str, today: date) -> list[str]:
    """Returns ISO dates for every distinct weekday name mentioned, in the
    order they appear in the text -- used to detect a departure+return pair
    like "جمعه ... یکشنبه ..." without inventing either date.

    The second (and any later) date is resolved on/after the previous one,
    not independently from `today` -- otherwise a departure weekday that
    happens to equal today's weekday jumps a full week ahead (per
    _next_weekday's "never today" rule) while a return weekday just 1-2 days
    out would land BEFORE it, inverting departure/return chronology."""
    found: list[tuple[int, int]] = []   # (position, weekday)
    seen_weekdays: set[int] = set()
    for phrase, wd in _WEEKDAYS:
        idx = normalized_text.find(phrase)
        if idx != -1 and wd not in seen_weekdays:
            found.append((idx, wd))
            seen_weekdays.add(wd)
    found.sort(key=lambda t: t[0])

    out: list[str] = []
    anchor = today
    for _, wd in found:
        d = _next_weekday(anchor, wd)
        out.append(d.isoformat())
        anchor = d
    return out


def resolve_explicit_date(normalized_text: str) -> DateRange | None:
    m = _EXPLICIT_DATE_RE.search(normalized_text)
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return DateRange(start_date=d.isoformat(), end_date=d.isoformat(), source="explicit")
