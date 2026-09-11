"""Query Intelligence & Search Planning (Phase 4).

Deterministic layer in front of the existing Search Orchestrator:

    text/structured input -> normalize -> intent -> entities -> dates ->
    constraints -> ambiguity -> SearchPlan -> (existing) Orchestrator

Production default has ZERO AI/LLM dependency -- see adapter.py. This
package never calls a provider directly; it only produces a SearchPlan that
main.py hands to the existing orchestrator.fan_out_and_assemble via a
SearchRequest, exactly like the structured /v1/search path already does.
"""
from .adapter import DEFAULT_PARSER, DeterministicQueryParser, QueryParserAdapter
from .models import CanonicalQueryInput, PLANNER_VERSION, SearchPlan
from .planner import plan_query

__all__ = [
    "plan_query", "PLANNER_VERSION", "SearchPlan", "CanonicalQueryInput",
    "DEFAULT_PARSER", "DeterministicQueryParser", "QueryParserAdapter",
]
