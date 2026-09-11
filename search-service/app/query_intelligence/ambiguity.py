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

MESSAGES = {
    AMBIGUOUS_ROUTE_DIRECTION: "مبدا و مقصد پرواز/قطار/اتوبوس مشخص نیست",
    AMBIGUOUS_SINGLE_LOCATION: "فقط یک مقصد یافت شد، جهت سفر نامشخص است",
    AMBIGUOUS_MULTIPLE_DESTINATIONS: "بیش از دو مقصد احتمالی یافت شد",
    UNSUPPORTED_INTENT: "این نوع خدمت هنوز پشتیبانی نمی‌شود",
    UNSUPPORTED_COMBINED_REQUEST: "جست‌وجوی ترکیبی چند خدمت هنوز پشتیبانی نمی‌شود",
    NO_INTENT_DETECTED: "نوع خدمت مورد نظر مشخص نشد",
    EMPTY_QUERY: "عبارت جست‌وجو خالی است",
}
