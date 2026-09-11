"""Tool registry + permission model (master prompt secs 31-33).

Only LEVEL 0 (READ) tools are implemented and wired in this first vertical
slice: search. They execute automatically, no confirmation. Booking/payment/
cancellation/visa tools are NOT implemented here -- inventing them without a
real backend to call would be exactly the fabrication this project
repeatedly forbids. The level constants and dataclass shape exist now so
those tools slot into the same registry later without a redesign.

Search is consumed as a TOOL over HTTP (karenseir-search's existing,
unmodified /v1/query/search) -- this service never reimplements Query
Intelligence/orchestration/ranking/dedup itself."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from . import config

LEVEL_READ = 0
LEVEL_DRAFT = 1
LEVEL_REVERSIBLE = 2
LEVEL_FINANCIAL = 3
LEVEL_HIGH_RISK = 4

# Tools at this level or below execute without an explicit confirmation step.
AUTO_EXECUTE_MAX_LEVEL = LEVEL_READ


@dataclass(frozen=True)
class ToolResult:
    status: str            # "ok" | "error"
    data: dict
    error_code: str | None = None


@dataclass(frozen=True)
class Tool:
    name: str
    permission_level: int
    handler: Callable[[dict], ToolResult]


def _search_client() -> httpx.Client:
    return httpx.Client(base_url=config.SEARCH_SERVICE_URL, timeout=config.SEARCH_TIMEOUT_SECONDS)


def search_travel(args: dict) -> ToolResult:
    """The single generic search tool -- vertical is decided by the
    deterministic Query Planner already inside karenseir-search, not
    duplicated here. Never fabricates a result: a provider outage surfaces
    as a real error_code, not an invented empty/success response."""
    payload = {"text": args.get("text", ""), "public": args.get("public", True), "tenant_ref": args.get("tenant_ref")}
    for k in ("vertical", "origin", "destination", "start_date", "end_date"):
        if args.get(k) is not None:
            payload[k] = args[k]
    try:
        with _search_client() as c:
            r = c.post("/v1/query/search", json=payload)
    except httpx.HTTPError as exc:
        return ToolResult(status="error", data={}, error_code=f"SEARCH_UNREACHABLE:{type(exc).__name__}")
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"raw": r.text[:200]}
        return ToolResult(status="error", data=detail, error_code=detail.get("code", f"HTTP_{r.status_code}"))
    return ToolResult(status="ok", data=r.json(), error_code=None)


REGISTRY: dict[str, Tool] = {
    "search_travel": Tool(name="search_travel", permission_level=LEVEL_READ, handler=search_travel),
}


def call_tool(name: str, args: dict) -> tuple[ToolResult, float]:
    tool = REGISTRY[name]
    started = time.perf_counter()
    result = tool.handler(args)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    return result, latency_ms
