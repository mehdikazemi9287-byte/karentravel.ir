"""Ambiguity/unsupported reason codes shared by planner.py. Machine-readable
codes, never a hidden silent choice -- see planner.py's status derivation."""
from __future__ import annotations

AMBIGUOUS_ROUTE_DIRECTION = "missing_route_direction"
AMBIGUOUS_SINGLE_LOCATION = "single_location_no_direction"
AMBIGUOUS_MULTIPLE_DESTINATIONS = "multiple_possible_destinations"
UNSUPPORTED_INTENT = "unsupported_intent"
UNSUPPORTED_COMBINED_REQUEST = "unsupported_combined_request"
NO_INTENT_DETECTED = "no_intent_detected"
EMPTY_QUERY = "empty_query"
# Phase 5: "soft" ambiguities -- real, worth surfacing for explainability/UI,
# but they do not by themselves block automatic execution (see planner.py's
# HARD_AMBIGUITY_CODES). A one-way flight search is a normal, common,
# executable request; we simply annotate that the return leg was never
# stated rather than silently assuming a round trip.
RETURN_DATE_UNSPECIFIED = "return_date_unspecified"
MULTI_LEG_ROUTE_NOT_SEARCHABLE = "multi_leg_route_not_searchable"

MESSAGES = {
    AMBIGUOUS_ROUTE_DIRECTION: "مبدا و مقصد پرواز/قطار/اتوبوس مشخص نیست",
    AMBIGUOUS_SINGLE_LOCATION: "فقط یک مقصد یافت شد، جهت سفر نامشخص است",
    AMBIGUOUS_MULTIPLE_DESTINATIONS: "بیش از دو مقصد احتمالی یافت شد",
    UNSUPPORTED_INTENT: "این نوع خدمت هنوز پشتیبانی نمی‌شود",
    UNSUPPORTED_COMBINED_REQUEST: "جست‌وجوی ترکیبی چند خدمت هنوز پشتیبانی نمی‌شود",
    NO_INTENT_DETECTED: "نوع خدمت مورد نظر مشخص نشد",
    EMPTY_QUERY: "عبارت جست‌وجو خالی است",
    RETURN_DATE_UNSPECIFIED: "مشخص نیست سفر یک‌طرفه است یا رفت‌وبرگشت",
    MULTI_LEG_ROUTE_NOT_SEARCHABLE: "مسیر چندمقصدی هنوز به‌صورت خودکار جست‌وجو نمی‌شود",
}

# Ambiguity codes that block automatic execution (Step 13 policy, unchanged
# from Phase 4). Anything not listed here is recorded for explainability but
# does not by itself downgrade a plan's status from valid.
HARD_AMBIGUITY_CODES = frozenset({
    AMBIGUOUS_ROUTE_DIRECTION, AMBIGUOUS_SINGLE_LOCATION, AMBIGUOUS_MULTIPLE_DESTINATIONS,
    NO_INTENT_DETECTED, EMPTY_QUERY,
})
