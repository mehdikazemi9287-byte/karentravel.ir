"""Canonical Query Intelligence models. The SearchPlan is the contract
between this package and the existing orchestrator -- raw natural-language
text never reaches a provider adapter, only a SearchPlan's resolved fields
do (main.py converts a valid SearchPlan into the existing SearchRequest)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

PLANNER_VERSION = "v1-deterministic"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

STATUS_VALID = "valid"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_UNSUPPORTED = "unsupported"
STATUS_INVALID = "invalid"          # blank/malformed input, nothing usable parsed


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
    rooms: Optional[int] = None
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
    rooms: Optional[int] = None


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
    date_range: DateRange
    party: Party
    filters: dict[str, Any]
    unsupported_constraints: tuple[str, ...]
    public: bool
    tenant_ref: Optional[str]
    confidence: str
    status: str
    ambiguities: tuple[Ambiguity, ...]
    planner_version: str = PLANNER_VERSION
    correlation_id: str = ""
