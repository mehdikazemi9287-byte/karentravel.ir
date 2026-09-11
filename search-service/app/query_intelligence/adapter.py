"""AI adapter interface -- Protocol only, per Phase 4 scope.

Production default is DeterministicQueryParser: zero AI/LLM dependency,
always available. A future LLM-backed adapter would implement the same
QueryParserAdapter protocol; none is implemented or called in this phase --
no external AI API, no credentials, no network call, no fabricated result.
Core search availability must never depend on this being replaced."""
from __future__ import annotations

from typing import Protocol

from .models import CanonicalQueryInput, SearchPlan
from .planner import plan_query


class QueryParserAdapter(Protocol):
    def parse(self, data: CanonicalQueryInput) -> SearchPlan: ...


class DeterministicQueryParser:
    def parse(self, data: CanonicalQueryInput) -> SearchPlan:
        return plan_query(data)


DEFAULT_PARSER: QueryParserAdapter = DeterministicQueryParser()
