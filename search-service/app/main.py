"""karenseir-search : independently deployable Search microservice.

Owns: query interpretation, provider fan-out, normalization, aggregation,
dedup, filtering, sorting, ranking, search metadata, cache, telemetry,
autocomplete foundation. Does NOT own reservation / payment / trip / identity.
"""
from __future__ import annotations

import uuid

from fastapi import Body, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import autocomplete, config, orchestrator, telemetry, telemetry_store
from .cache import CACHE
from .cache_keys import autocomplete_cache_key, search_cache_key
from .domain import (
    ALLOWED_SORTS, ALLOWED_VERTICALS, INTERNAL_SEARCH_ERROR, INVALID_SEARCH_REQUEST,
    NO_RESULTS, PROVIDER_UNAVAILABLE, SearchError, SearchRequest,
)
from .providers import EXTERNAL_PROVIDERS, _POOL
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
