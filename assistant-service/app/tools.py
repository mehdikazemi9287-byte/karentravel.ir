"""Tool registry + permission model (master prompt secs 31-33, Phase 3
secs 3-4). Every tool declares name/version/capability/required_inputs/
output_contract/level/idempotent/approval_required/timeout_seconds.

LEVEL_0/LEVEL_1 tools execute automatically (search, create_booking_draft).
LEVEL_2 ("submit_reservation_hold") and LEVEL_3 ("execute_financial_action")
are DECLARED -- the approval-gating and execution-guard mechanism around
them is real and tested -- but their handlers always return a truthful
BLOCKED result. No real commerce/payment/PNR call exists from this service
in this phase; inventing one (or simulating success) would be exactly the
fabrication this project forbids. Search is consumed as a TOOL over HTTP
(karenseir-search's existing, unmodified /v1/query/search) -- this service
never reimplements Query Intelligence/orchestration/ranking/dedup itself."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from . import config

LEVEL_READ = 0          # LEVEL_0: read/compute, auto-executes
LEVEL_DRAFT = 1          # LEVEL_1: reversible local preparation, auto-executes, idempotent
LEVEL_APPROVAL = 2       # LEVEL_2: explicit approval required before execution
LEVEL_FINANCIAL = 3      # LEVEL_3: sensitive/irreversible/financial -- blocked this phase
LEVEL_HIGH_RISK = 4

AUTO_EXECUTE_MAX_LEVEL = LEVEL_DRAFT   # LEVEL_0/1 need no confirmation; LEVEL_2+ need approval


@dataclass(frozen=True)
class ToolResult:
    status: str            # "ok" | "error" | "blocked"
    data: dict
    error_code: str | None = None


@dataclass(frozen=True)
class Tool:
    name: str
    version: str
    capability: str
    required_inputs: tuple[str, ...]
    output_contract: str
    permission_level: int
    idempotent: bool
    approval_required: bool
    timeout_seconds: float
    handler: Callable[[dict], ToolResult]


def operation_fingerprint(tool: str, args: dict) -> str:
    """Deterministic identity of "this exact operation with these exact
    material parameters" -- used for both idempotency (retry -> same
    fingerprint -> same outcome, no duplicate) and approval matching (an
    approval is only valid for the fingerprint it was granted against;
    any material parameter change invalidates it)."""
    payload = json.dumps({"tool": tool, "args": args}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _search_client() -> httpx.Client:
    return httpx.Client(base_url=config.SEARCH_SERVICE_URL, timeout=config.SEARCH_TIMEOUT_SECONDS)


def search_travel(args: dict) -> ToolResult:
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


def create_booking_draft_tool(args: dict) -> ToolResult:
    from . import trip
    result = trip.create_booking_draft(args["trip_state_id"], args["vertical"], args["selected_item"], args["missing_fields"])
    return ToolResult(status="ok", data=result, error_code=None)


def submit_reservation_hold(args: dict) -> ToolResult:
    """LEVEL_2. No production-safe commerce integration is wired from this
    service in this phase (Phase 2/3 both explicitly forbid real booking).
    Always returns a truthful blocked result -- proves the approval-gating
    and execution-guard mechanism end-to-end without ever attempting or
    simulating an external mutation."""
    return ToolResult(status="blocked", data={"reason": "no authorized commerce integration wired in this phase"},
                       error_code="BLOCKED_LEVEL2_NO_COMMERCE_INTEGRATION")


def blocked_financial_action(args: dict) -> ToolResult:
    """LEVEL_3+. Always blocked -- no payment/PNR/wallet/refund call exists.
    Never simulates success; every attempt is truthfully audited as blocked."""
    return ToolResult(status="blocked", data={"reason": "financial/irreversible actions are not implemented"},
                       error_code="BLOCKED_LEVEL3_NOT_IMPLEMENTED")


REGISTRY: dict[str, Tool] = {
    "search_travel": Tool(
        name="search_travel", version="1.0", capability="search karenseir-search for the current turn's goal",
        required_inputs=("text",), output_contract="karenseir-search /v1/query/search response",
        permission_level=LEVEL_READ, idempotent=True, approval_required=False,
        timeout_seconds=config.SEARCH_TIMEOUT_SECONDS, handler=search_travel,
    ),
    "create_booking_draft": Tool(
        name="create_booking_draft", version="1.0", capability="create/reuse a LEVEL_1 local booking draft",
        required_inputs=("trip_state_id", "vertical", "selected_item", "missing_fields"),
        output_contract="{id, status, duplicate}", permission_level=LEVEL_DRAFT,
        idempotent=True, approval_required=False, timeout_seconds=3.0, handler=create_booking_draft_tool,
    ),
    "submit_reservation_hold": Tool(
        name="submit_reservation_hold", version="1.0", capability="place a provider reservation hold (NOT IMPLEMENTED)",
        required_inputs=("trip_state_id", "selected_item"), output_contract="{status: blocked, reason}",
        permission_level=LEVEL_APPROVAL, idempotent=True, approval_required=True,
        timeout_seconds=5.0, handler=submit_reservation_hold,
    ),
    "execute_financial_action": Tool(
        name="execute_financial_action", version="1.0", capability="payment/ticketing/refund (NOT IMPLEMENTED)",
        required_inputs=(), output_contract="{status: blocked, reason}", permission_level=LEVEL_FINANCIAL,
        idempotent=True, approval_required=True, timeout_seconds=5.0, handler=blocked_financial_action,
    ),
}


def call_tool(name: str, args: dict) -> tuple[ToolResult, float]:
    tool = REGISTRY[name]
    started = time.perf_counter()
    result = tool.handler(args)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    return result, latency_ms
