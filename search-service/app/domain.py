"""Canonical Search domain model. Provider adapters convert provider-specific
payloads into these shapes; no consumer needs to understand provider formats."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ---- request ----
ALLOWED_VERTICALS = frozenset({
    "flight", "hotel", "train", "bus", "tour", "package", "accommodation",
    "vacation_rental", "cruise", "visa", "car_rental",
})
ALLOWED_SORTS = frozenset({
    "recommended", "lowest_price", "cheapest", "highest_rated",
    "best_location", "most_flexible", "fastest", "best_value", "price_asc", "price_desc", "review_desc",
})
SAFE_FILTER_KEYS = frozenset({
    "min_price", "max_price", "min_review_score", "refundable", "amenities",
    "instant_booking", "map_bounds", "check_in", "check_out",
})


@dataclass(frozen=True)
class SearchRequest:
    verticals: tuple[str, ...]
    query: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    travellers: int = 1
    flexibility: str = "exact"
    sort: str = "recommended"
    filters: dict[str, Any] = field(default_factory=dict)
    include_stale: bool = False
    page: int = 1
    page_size: int = 20
    public: bool = True
    tenant_ref: Optional[str] = None          # slug/id for authenticated context
    correlation_id: str = ""


# ---- failure taxonomy ----
INVALID_SEARCH_REQUEST = "INVALID_SEARCH_REQUEST"
PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
PARTIAL_RESULTS = "PARTIAL_RESULTS"
NO_RESULTS = "NO_RESULTS"
SEARCH_EXPIRED = "SEARCH_EXPIRED"
OFFER_EXPIRED = "OFFER_EXPIRED"
INTERNAL_SEARCH_ERROR = "INTERNAL_SEARCH_ERROR"
# Phase 3 additions -- reserved for provider adapters that need a finer-grained
# classification than PROVIDER_TIMEOUT/PROVIDER_UNAVAILABLE. The existing
# all-providers-down invariant is UNCHANGED: it still raises PROVIDER_UNAVAILABLE
# (never this new ALL_PROVIDERS_UNAVAILABLE constant) so it stays a stable,
# already-tested public contract; ALL_PROVIDERS_UNAVAILABLE exists for callers
# that want to distinguish "one provider down" from "every provider down" in
# their own diagnostics/logging without changing the public HTTP error code.
AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
RATE_LIMITED = "RATE_LIMITED"
MALFORMED_PROVIDER_RESPONSE = "MALFORMED_PROVIDER_RESPONSE"
PROVIDER_INTERNAL_ERROR = "PROVIDER_INTERNAL_ERROR"
TENANT_UNRESOLVED = "TENANT_UNRESOLVED"
ALL_PROVIDERS_UNAVAILABLE = "ALL_PROVIDERS_UNAVAILABLE"


class SearchError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
