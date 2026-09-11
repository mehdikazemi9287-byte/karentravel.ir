"""karenseir-search : independently deployable Search microservice.

Owns: query interpretation, provider fan-out, normalization, aggregation,
dedup, filtering, sorting, ranking, search metadata, cache, telemetry,
autocomplete foundation. Does NOT own reservation / payment / trip / identity.
"""
from __future__ import annotations

import time
import uuid

from fastapi import Body, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import autocomplete, config, orchestrator, telemetry, telemetry_store
from .cache import CACHE
from .cache_keys import autocomplete_cache_key, query_plan_cache_key, search_cache_key
from .domain import (
    ALLOWED_SORTS, ALLOWED_VERTICALS, INTERNAL_SEARCH_ERROR, INVALID_SEARCH_REQUEST,
    NO_RESULTS, PROVIDER_UNAVAILABLE, SearchError, SearchRequest,
)
from .providers import EXTERNAL_PROVIDERS, _POOL
from .query_intelligence import CanonicalQueryInput, PLANNER_VERSION, plan_query
from .query_intelligence.models import STATUS_VALID
from .ranking import RANKING_VERSION
from .registry import REGISTRY

app = FastAPI(title="karenseir-search", version=config.SERVICE_VERSION)


class SearchIn(BaseModel):
    verticals: list[str] = Field(min_length=1, max_length=4)
    query: str | None = Field(default=None, max_length=200)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    travellers: int = Field(default=1, ge=1, le=20)
    flexibility: str = Field(default="exact", max_length=32)
    sort: str = Field(default="recommended", max_length=32)
    filters: dict = Field(default_factory=dict)
    include_stale: bool = False
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=100)
    public: bool = True
    tenant_ref: str | None = Field(default=None, max_length=120)


class QueryPlanIn(BaseModel):
    """Canonical input for /v1/query/plan and /v1/query/search. Structured
    fields always take precedence over anything inferred from `text` -- see
    query_intelligence/planner.py. `sort` default is None (not a fixed
    "recommended" string) so the planner can distinguish "not supplied,
    infer a hint from text" from "explicitly requested"."""
    text: str = Field(default="", max_length=300)
    vertical: str | None = Field(default=None, max_length=32)
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    start_date: str | None = Field(default=None, max_length=32)
    end_date: str | None = Field(default=None, max_length=32)
    passengers: int | None = Field(default=None, ge=1, le=20)
    adults: int | None = Field(default=None, ge=1, le=20)
    children: int | None = Field(default=None, ge=0, le=20)
    infants: int | None = Field(default=None, ge=0, le=20)
    rooms: int | None = Field(default=None, ge=1, le=20)
    quantity: int | None = Field(default=None, ge=1, le=50)
    cabin: str | None = Field(default=None, max_length=32)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    trip_type: str | None = Field(default=None, max_length=16)
    filters: dict = Field(default_factory=dict)
    locale: str | None = Field(default=None, max_length=16)
    currency: str | None = Field(default=None, max_length=8)
    public: bool = True
    tenant_ref: str | None = Field(default=None, max_length=120)
    sort: str | None = Field(default=None, max_length=32)
    flexibility: str | None = Field(default=None, max_length=32)
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=100)


def _entity_out(e) -> dict | None:
    return None if e is None else {"id": e.id, "title": e.title, "type": e.type, "code": e.code}


def _plan_to_dict(plan) -> dict:
    return {
        "query_id": plan.query_id, "original_text": plan.original_text, "normalized_text": plan.normalized_text,
        "intent": list(plan.intent), "vertical": plan.vertical, "multi_intent": plan.multi_intent,
        "origin": _entity_out(plan.origin), "destination": _entity_out(plan.destination),
        "intermediate_stops": [_entity_out(e) for e in plan.intermediate_stops],
        "date_range": {"start_date": plan.date_range.start_date, "end_date": plan.date_range.end_date, "source": plan.date_range.source},
        "departure_date": plan.departure_date, "return_date": plan.return_date, "nights": plan.nights,
        "trip_type": plan.trip_type,
        "party": {"travellers": plan.party.travellers, "adults": plan.party.adults, "children": plan.party.children,
                  "infants": plan.party.infants, "rooms": plan.party.rooms, "quantity": plan.party.quantity},
        "cabin": plan.cabin, "budget_min": plan.budget_min, "budget_max": plan.budget_max, "currency": plan.currency,
        "filters": plan.filters, "sort": plan.sort, "flexibility": plan.flexibility, "nearby_allowed": plan.nearby_allowed,
        "unsupported_constraints": list(plan.unsupported_constraints),
        "inferred_fields": list(plan.inferred_fields), "explicit_fields": list(plan.explicit_fields),
        "unresolved_fields": list(plan.unresolved_fields),
        "public": plan.public, "tenant_ref": plan.tenant_ref, "confidence": plan.confidence, "status": plan.status,
        "ambiguities": [{"code": a.code, "message": a.message} for a in plan.ambiguities],
        "locale": plan.locale, "planner_version": plan.planner_version,
    }


def _record_plan_telemetry(plan, latency_ms: float, *, executed: bool) -> None:
    key = {"valid": "query_plan_valid", "ambiguous": "query_plan_ambiguous",
           "unsupported": "query_plan_unsupported", "invalid": "query_plan_invalid"}.get(plan.status, "query_plan_invalid")
    telemetry.incr(key)
    telemetry.observe_planning_duration(latency_ms)
    telemetry_store.record_plan({
        "correlation_id": plan.correlation_id, "planner_version": plan.planner_version,
        "intent": list(plan.intent), "vertical": plan.vertical, "confidence": plan.confidence,
        "plan_status": plan.status, "plan_valid": plan.status == STATUS_VALID, "multi_intent": plan.multi_intent,
        "ambiguity_count": len(plan.ambiguities), "unsupported_constraint_count": len(plan.unsupported_constraints),
        "planning_latency_ms": latency_ms, "executed": executed, "public": plan.public, "tenant_ref": plan.tenant_ref,
    })


@app.exception_handler(SearchError)
async def _search_error(_: Request, exc: SearchError):
    telemetry.incr("search_errors")
    return JSONResponse(status_code=exc.http_status, content={"code": exc.code, "message": exc.message})


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    telemetry.incr("search_errors")
    telemetry.log_event("internal_error", error=type(exc).__name__)
    return JSONResponse(status_code=500, content={"code": INTERNAL_SEARCH_ERROR, "message": "خطای داخلی جست‌وجو"})


@app.get("/health")
def health():
    return {"status": "ok", "service": "karenseir-search"}


@app.get("/ready")
def ready():
    pool = _POOL.status()
    cache_ok = CACHE.ping()
    # Ready if we can reach the offer pool. Cache degradation alone does not
    # mark the service dead (in-memory fallback keeps search valid).
    ok = pool["status"] == "available"
    body = {
        "status": "ready" if ok else "degraded",
        "offer_pool": pool["status"],
        "cache": {"backend": getattr(CACHE, "backend", "unknown"), "ok": cache_ok},
        "telemetry": telemetry_store.health(),
        "external_providers": {p.key: p.status()["status"] for p in EXTERNAL_PROVIDERS},
    }
    return JSONResponse(status_code=200 if ok else 503, content=body)


@app.get("/version")
def version():
    return {"service": "karenseir-search", "version": config.SERVICE_VERSION,
            "git_commit": config.BUILD_COMMIT, "build_timestamp": config.BUILD_TIME,
            "environment": config.ENVIRONMENT}


@app.get("/metrics")
def metrics():
    return telemetry.snapshot()


@app.post("/v1/search")
def v1_search(data: SearchIn = Body(...), x_correlation_id: str | None = Header(default=None)):
    corr = x_correlation_id or str(uuid.uuid4())

    bad = [v for v in data.verticals if v not in ALLOWED_VERTICALS]
    if bad:
        raise SearchError(INVALID_SEARCH_REQUEST, f"نوع خدمت معتبر نیست: {', '.join(bad)}", 422)
    if data.sort not in ALLOWED_SORTS:
        raise SearchError(INVALID_SEARCH_REQUEST, "مرتب‌سازی معتبر نیست", 422)

    key = search_cache_key(data.model_dump())
    cached = CACHE.get(key)
    if cached is not None:
        telemetry.incr("cache_hit")
        cached = dict(cached)
        cached.setdefault("search_metadata", {})["cache"] = "hit"
        return cached
    telemetry.incr("cache_miss")

    req = SearchRequest(
        verticals=tuple(data.verticals), query=data.query, origin=data.origin, destination=data.destination,
        travellers=data.travellers, flexibility=data.flexibility, sort=data.sort, filters=data.filters or {},
        include_stale=data.include_stale, page=data.page, page_size=data.page_size,
        public=data.public, tenant_ref=data.tenant_ref, correlation_id=corr,
    )

    # Central Search Orchestrator (orchestrator.py): fan-out -> normalize ->
    # dedup -> rank -> filter -> paginate. result is None exactly when every
    # eligible connected provider failed -- fail closed, never a fake zero-result.
    result, meta, elapsed = orchestrator.fan_out_and_assemble(req)
    for m in meta:
        if m["status"] == "PROVIDER_TIMEOUT":
            telemetry.incr("provider_timeouts")
        elif m["status"] == "PROVIDER_UNAVAILABLE":
            telemetry.incr("provider_unavailable")

    if result is None:
        attempted = [m for m in meta if m["status"] in ("available", "PROVIDER_TIMEOUT", "PROVIDER_UNAVAILABLE")]
        telemetry.incr("search_errors")
        telemetry_store.record({
            "correlation_id": corr, "verticals": list(data.verticals), "public": data.public,
            "tenant_ref": None if data.public else data.tenant_ref, "result_count": 0,
            "partial_results": False, "providers_requested": len(attempted), "providers_failed": len(attempted),
            "elapsed_ms": elapsed, "cache": "n/a", "failure_code": PROVIDER_UNAVAILABLE,
            "providers_succeeded": 0, "ranking_version": RANKING_VERSION, "avg_provider_latency_ms": None,
        })
        raise SearchError(PROVIDER_UNAVAILABLE, "موتور جست‌وجو موقتاً در دسترس نیست", 503)

    result["search_metadata"]["cache"] = "miss"

    telemetry.incr("search_requests")
    telemetry.observe_duration(elapsed)
    telemetry.observe_result_count(result["pagination"]["total"])
    if not result["entities"]:
        telemetry.incr("search_zero_result")
    if result["search_metadata"]["partial_results"]:
        telemetry.incr("search_partial")
    telemetry.log_event("search", corr=corr, verticals=list(data.verticals), public=data.public,
                        total=result["pagination"]["total"], elapsed_ms=elapsed,
                        partial=result["search_metadata"]["partial_results"])
    latencies = [v for v in result["search_metadata"]["provider_latency_ms"].values() if v is not None]
    telemetry_store.record({
        "correlation_id": corr, "verticals": list(data.verticals), "public": data.public,
        "tenant_ref": None if data.public else data.tenant_ref,
        "result_count": result["pagination"]["total"], "partial_results": result["search_metadata"]["partial_results"],
        "providers_requested": result["search_metadata"]["providers_requested"],
        "providers_failed": result["search_metadata"]["providers_failed"],
        "elapsed_ms": elapsed, "cache": "miss", "failure_code": None,
        "providers_succeeded": result["search_metadata"]["providers_succeeded"],
        "ranking_version": RANKING_VERSION,
        "avg_provider_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        **{k: result["search_metadata"]["result_counts"][k] for k in
           ("raw_offer_count", "normalized_offer_count", "offer_dedup_removed")},
    })

    CACHE.set(key, result, config.CACHE_TTL_SECONDS)
    return result


@app.get("/v1/autocomplete")
def v1_autocomplete(q: str = Query(default="", max_length=120), limit: int = Query(default=8, ge=1, le=20)):
    telemetry.incr("autocomplete_requests")
    key = autocomplete_cache_key(q, limit)
    cached = CACHE.get(key)
    if cached is not None:
        telemetry.incr("cache_hit")
        return cached
    telemetry.incr("cache_miss")
    out = autocomplete.suggest(q, limit)
    CACHE.set(key, out, config.AUTOCOMPLETE_CACHE_TTL)
    return out


@app.get("/v1/providers")
def v1_providers():
    return {
        "wired": [{"provider": _POOL.key, **_POOL.status()}],
        "external": [p.status() | {"verticals": list(p.verticals)} for p in EXTERNAL_PROVIDERS],
    }


@app.get("/v1/diagnostics")
def v1_diagnostics():
    """Operations-facing diagnostics -- not gatewayed to the public internet
    (the service only binds 127.0.0.1:8090 on the host; the monolith gateway
    proxies /v1/search and /v1/autocomplete only, never this route). No
    secrets/tokens/provider URLs are included."""
    return {
        "providers_enabled": len(REGISTRY.all()),
        "providers_connected": sum(1 for p in REGISTRY.all() if p.connected),
        "capability_matrix": REGISTRY.capability_matrix(),
        "cache": {"backend": getattr(CACHE, "backend", "unknown"), "ok": CACHE.ping()},
        "telemetry": telemetry_store.health(),
        "ranking_version": RANKING_VERSION,
        "recent_metrics": telemetry.snapshot(),
    }


def _canonical_input(data: QueryPlanIn, corr: str) -> CanonicalQueryInput:
    return CanonicalQueryInput(
        text=data.text, vertical=data.vertical, origin=data.origin, destination=data.destination,
        start_date=data.start_date, end_date=data.end_date, passengers=data.passengers,
        adults=data.adults, children=data.children, infants=data.infants, rooms=data.rooms,
        quantity=data.quantity, cabin=data.cabin, budget_min=data.budget_min, budget_max=data.budget_max,
        trip_type=data.trip_type, sort=data.sort, flexibility=data.flexibility,
        filters=data.filters or {}, locale=data.locale, currency=data.currency,
        public=data.public, tenant_ref=data.tenant_ref, correlation_id=corr,
    )


@app.post("/v1/query/plan")
def v1_query_plan(data: QueryPlanIn = Body(...), x_correlation_id: str | None = Header(default=None)):
    """Phase 4: parses text/structured input into a SearchPlan. Never
    executes a provider call -- planning only. Additive: does not replace or
    alter /v1/search in any way."""
    corr = x_correlation_id or str(uuid.uuid4())
    started = time.perf_counter()
    plan = plan_query(_canonical_input(data, corr))
    latency = round((time.perf_counter() - started) * 1000, 3)
    _record_plan_telemetry(plan, latency, executed=False)
    return {"plan": _plan_to_dict(plan)}


@app.post("/v1/query/search")
def v1_query_search(data: QueryPlanIn = Body(...), x_correlation_id: str | None = Header(default=None)):
    """Phase 4: plans, then executes through the EXISTING, unmodified
    orchestrator only when the plan is valid -- ambiguous/unsupported/invalid
    plans return a structured (200) clarification response instead of ever
    calling a provider with a knowingly invalid plan. Raw query text never
    reaches a provider adapter; only the plan's resolved fields do, via the
    same SearchRequest contract /v1/search already uses."""
    corr = x_correlation_id or str(uuid.uuid4())
    started = time.perf_counter()
    plan = plan_query(_canonical_input(data, corr))
    planning_latency = round((time.perf_counter() - started) * 1000, 3)

    if plan.status != STATUS_VALID:
        _record_plan_telemetry(plan, planning_latency, executed=False)
        return JSONResponse(status_code=200, content={"plan": _plan_to_dict(plan), "executed": False})

    telemetry.incr("query_nl_search_executed")
    if plan.multi_intent:
        telemetry.incr("query_multi_intent")

    plan_filters = dict(plan.filters)
    if plan.date_range.start_date:
        plan_filters.setdefault("check_in", plan.date_range.start_date)
    if plan.date_range.end_date:
        plan_filters.setdefault("check_out", plan.date_range.end_date)

    provider_set = tuple(sorted(p.key for p in REGISTRY.all() if p.connected))
    cache_payload = {
        "vertical": plan.vertical, "origin_id": plan.origin.id if plan.origin else None,
        "destination_id": plan.destination.id if plan.destination else None,
        "destination_title": plan.destination.title if plan.destination else None,
        "date_range": {"start": plan.date_range.start_date, "end": plan.date_range.end_date},
        "party": {"travellers": plan.party.travellers, "rooms": plan.party.rooms},
        "filters": plan_filters, "sort": plan.sort, "page": data.page, "page_size": data.page_size,
        "public": plan.public, "tenant_ref": plan.tenant_ref,
    }
    key = query_plan_cache_key(cache_payload, PLANNER_VERSION, provider_set)
    cached = CACHE.get(key)
    if cached is not None:
        telemetry.incr("cache_hit")
        cached = dict(cached)
        cached.setdefault("search_metadata", {})["cache"] = "hit"
        cached["plan"] = _plan_to_dict(plan)
        _record_plan_telemetry(plan, planning_latency, executed=True)
        return {"result": cached, "executed": True}
    telemetry.incr("cache_miss")

    req = SearchRequest(
        verticals=(plan.vertical,), destination=plan.destination.title if plan.destination else None,
        origin=plan.origin.title if plan.origin else None, travellers=plan.party.travellers or 1,
        sort=plan.sort, flexibility=plan.flexibility, filters=plan_filters, page=data.page, page_size=data.page_size,
        public=plan.public, tenant_ref=plan.tenant_ref, correlation_id=corr,
    )
    result, meta, elapsed = orchestrator.fan_out_and_assemble(req)
    for m in meta:
        if m["status"] == "PROVIDER_TIMEOUT":
            telemetry.incr("provider_timeouts")
        elif m["status"] == "PROVIDER_UNAVAILABLE":
            telemetry.incr("provider_unavailable")

    if result is None:
        attempted = [m for m in meta if m["status"] in ("available", "PROVIDER_TIMEOUT", "PROVIDER_UNAVAILABLE")]
        telemetry.incr("search_errors")
        telemetry_store.record({
            "correlation_id": corr, "verticals": [plan.vertical], "public": plan.public,
            "tenant_ref": None if plan.public else plan.tenant_ref, "result_count": 0,
            "partial_results": False, "providers_requested": len(attempted), "providers_failed": len(attempted),
            "elapsed_ms": elapsed, "cache": "n/a", "failure_code": PROVIDER_UNAVAILABLE,
            "providers_succeeded": 0, "ranking_version": RANKING_VERSION, "avg_provider_latency_ms": None,
        })
        _record_plan_telemetry(plan, planning_latency, executed=True)
        raise SearchError(PROVIDER_UNAVAILABLE, "موتور جست‌وجو موقتاً در دسترس نیست", 503)

    result["search_metadata"]["cache"] = "miss"
    telemetry.incr("search_requests")
    telemetry.observe_duration(elapsed)
    telemetry.observe_result_count(result["pagination"]["total"])
    if not result["entities"]:
        telemetry.incr("search_zero_result")
    if result["search_metadata"]["partial_results"]:
        telemetry.incr("search_partial")
    latencies = [v for v in result["search_metadata"]["provider_latency_ms"].values() if v is not None]
    telemetry_store.record({
        "correlation_id": corr, "verticals": [plan.vertical], "public": plan.public,
        "tenant_ref": None if plan.public else plan.tenant_ref,
        "result_count": result["pagination"]["total"], "partial_results": result["search_metadata"]["partial_results"],
        "providers_requested": result["search_metadata"]["providers_requested"],
        "providers_failed": result["search_metadata"]["providers_failed"],
        "elapsed_ms": elapsed, "cache": "miss", "failure_code": None,
        "providers_succeeded": result["search_metadata"]["providers_succeeded"],
        "ranking_version": RANKING_VERSION,
        "avg_provider_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        **{k: result["search_metadata"]["result_counts"][k] for k in
           ("raw_offer_count", "normalized_offer_count", "offer_dedup_removed")},
    })
    _record_plan_telemetry(plan, planning_latency, executed=True)

    CACHE.set(key, result, config.CACHE_TTL_SECONDS)
    result["plan"] = _plan_to_dict(plan)
    return {"result": result, "executed": True}
