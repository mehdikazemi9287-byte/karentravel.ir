"""Canonical Query Intelligence models. The SearchPlan is the contract
between this package and the existing orchestrator -- raw natural-language
text never reaches a provider adapter, only a SearchPlan's resolved fields
do (main.py converts a valid SearchPlan into the existing SearchRequest).

Phase 5 (Search Intelligence): the contract is expanded additively (new
fields, sensible defaults) to cover trip type, passenger breakdown, budget,
and explicit/inferred/unresolved field provenance -- required for
explainability ("was this field explicit or guessed?"). Nothing here removes
or renames a Phase 4 field; date_range/party/filters keep their existing
shape so main.py's /v1/query/search execution path is unchanged."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

PLANNER_VERSION = "v2-deterministic"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

STATUS_VALID = "valid"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_UNSUPPORTED = "unsupported"
STATUS_INVALID = "invalid"          # blank/malformed input, nothing usable parsed

TRIP_ONE_WAY = "one_way"
TRIP_ROUND_TRIP = "round_trip"
TRIP_UNSPECIFIED = "unspecified"


@dataclass(frozen=True)
class CanonicalQueryInput:
    """Structured fields ALWAYS take precedence over anything the parser
    infers from `text` -- see planner.py. None means "not supplied"."""
    text: str = ""
    vertical: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    passengers: Optional[int] = None
    adults: Optional[int] = None
    children: Optional[int] = None
    infants: Optional[int] = None
    rooms: Optional[int] = None
    quantity: Optional[int] = None
    cabin: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    trip_type: Optional[str] = None     # "one_way" | "round_trip" -- explicit override
    sort: Optional[str] = None
    flexibility: Optional[str] = None
    filters: dict[str, Any] = field(default_factory=dict)
    locale: Optional[str] = None        # accepted, not yet acted on -- no locale logic exists in Search today
    currency: Optional[str] = None      # accepted, not yet acted on -- no currency conversion exists in Search today
    public: bool = True
    tenant_ref: Optional[str] = None
    correlation_id: str = ""


@dataclass(frozen=True)
class ResolvedEntity:
    id: str
    title: str
    type: str
    code: Optional[str] = None


@dataclass(frozen=True)
class DateRange:
    start_date: Optional[str] = None    # ISO yyyy-mm-dd
    end_date: Optional[str] = None
    source: str = "none"                # "explicit" | "relative" | "none"


@dataclass(frozen=True)
class Party:
    travellers: Optional[int] = None
    adults: Optional[int] = None
    children: Optional[int] = None
    infants: Optional[int] = None
    rooms: Optional[int] = None
    quantity: Optional[int] = None


@dataclass(frozen=True)
class Ambiguity:
    code: str
    message: str


@dataclass(frozen=True)
class SearchPlan:
    query_id: str
    original_text: str
    normalized_text: str
    intent: tuple[str, ...]             # every vertical detected, deterministic order
    vertical: Optional[str]             # primary vertical when single-intent and resolvable
    multi_intent: bool
    origin: Optional[ResolvedEntity]
    destination: Optional[ResolvedEntity]
    intermediate_stops: tuple[ResolvedEntity, ...]
    date_range: DateRange
    departure_date: Optional[str]
    return_date: Optional[str]
    nights: Optional[int]
    trip_type: str
    party: Party
    cabin: Optional[str]
    budget_min: Optional[int]
    budget_max: Optional[int]
    currency: Optional[str]
    filters: dict[str, Any]
    sort: str
    flexibility: str
    nearby_allowed: bool
    unsupported_constraints: tuple[str, ...]
    inferred_fields: tuple[str, ...]
    explicit_fields: tuple[str, ...]
    unresolved_fields: tuple[str, ...]
    public: bool
    tenant_ref: Optional[str]
    confidence: str
    status: str
    ambiguities: tuple[Ambiguity, ...]
    locale: Optional[str] = None
    planner_version: str = PLANNER_VERSION
    correlation_id: str = ""
