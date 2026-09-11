"""karenseir-search : independently deployable Search microservice.

Owns: query interpretation, provider fan-out, normalization, aggregation,
dedup, filtering, sorting, ranking, search metadata, cache, telemetry,
autocomplete foundation. Does NOT own reservation / payment / trip / identity.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid

from fastapi import Body, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import autocomplete, config, engine, telemetry, telemetry_store
from .cache import CACHE
from .domain import (
    ALLOWED_SORTS, ALLOWED_VERTICALS, INTERNAL_SEARCH_ERROR, INVALID_SEARCH_REQUEST,
    NO_RESULTS, PROVIDER_UNAVAILABLE, SearchError, SearchRequest,
)
from .providers import EXTERNAL_PROVIDERS, _POOL, fan_out

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


def _cache_key(payload: dict) -> str:
    return "kss:v1:" + hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@app.post("/v1/search")
def v1_search(data: SearchIn = Body(...), x_correlation_id: str | None = Header(default=None)):
    started = time.perf_counter()
    corr = x_correlation_id or str(uuid.uuid4())

    bad = [v for v in data.verticals if v not in ALLOWED_VERTICALS]
    if bad:
        raise SearchError(INVALID_SEARCH_REQUEST, f"نوع خدمت معتبر نیست: {', '.join(bad)}", 422)
    if data.sort not in ALLOWED_SORTS:
        raise SearchError(INVALID_SEARCH_REQUEST, "مرتب‌سازی معتبر نیست", 422)

    key = _cache_key(data.model_dump())
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
    pools, meta = fan_out(req)
    for m in meta:
        if m["status"] == "PROVIDER_TIMEOUT":
            telemetry.incr("provider_timeouts")
        elif m["status"] == "PROVIDER_UNAVAILABLE":
            telemetry.incr("provider_unavailable")

    # A total infrastructure failure (every requested vertical's pool provider
    # failed) is never presented as a valid zero-result search.
    pool_meta = [m for m in meta if m["provider"] == _POOL.key]
    if pool_meta and all(m["status"] != "available" for m in pool_meta):
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        telemetry.incr("search_errors")
        telemetry_store.record({
            "correlation_id": corr, "verticals": list(data.verticals), "public": data.public,
            "tenant_ref": None if data.public else data.tenant_ref, "result_count": 0,
            "partial_results": False, "providers_requested": len(pool_meta), "providers_failed": len(pool_meta),
            "elapsed_ms": elapsed, "cache": "n/a", "failure_code": PROVIDER_UNAVAILABLE,
        })
        raise SearchError(PROVIDER_UNAVAILABLE, "موتور جست‌وجو موقتاً در دسترس نیست", 503)

    elapsed = round((time.perf_counter() - started) * 1000, 3)
    result = engine.assemble(req, pools, meta, elapsed)
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
    telemetry_store.record({
        "correlation_id": corr, "verticals": list(data.verticals), "public": data.public,
        "tenant_ref": None if data.public else data.tenant_ref,
        "result_count": result["pagination"]["total"], "partial_results": result["search_metadata"]["partial_results"],
        "providers_requested": result["search_metadata"]["providers_requested"],
        "providers_failed": result["search_metadata"]["providers_failed"],
        "elapsed_ms": elapsed, "cache": "miss", "failure_code": None,
    })

    CACHE.set(key, result, config.CACHE_TTL_SECONDS)
    return result


@app.get("/v1/autocomplete")
def v1_autocomplete(q: str = Query(default="", max_length=120), limit: int = Query(default=8, ge=1, le=20)):
    telemetry.incr("autocomplete_requests")
    key = f"kss:ac:v1:{limit}:{q}"
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
