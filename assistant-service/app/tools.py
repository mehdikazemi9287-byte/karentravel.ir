"""Tool registry + permission model (master prompt secs 31-33, Phase 3
secs 3-4, Phase 4 real reservation wiring). Every tool declares name/
version/capability/required_inputs/output_contract/level/idempotent/
approval_required/timeout_seconds.

LEVEL_0/LEVEL_1 tools execute automatically (search, create_booking_draft).
LEVEL_2 tools (price_check_offer, submit_reservation_hold,
release_reservation_hold) now call the REAL monolith commerce endpoints
(confirmed by reading backend/app/main.py: POST /offers/{id}/price-check ->
POST /orchestration/bookings creates a real Reservation(status="reserved");
POST /reservations/{id}/service-requests with request_type="cancel" is the
real rollback path) -- but EVERY one of those endpoints requires a real
signed user Bearer JWT via the monolith's own `current_user` dependency.
This service has no login/session mechanism and MUST NOT mint, hold, or
guess a user credential -- that would be an authorization violation, not a
shortcut. Each LEVEL_2 handler therefore only proceeds when the CALLER
(whatever invokes this service) forwards a real `user_token` in the tool
args; otherwise it returns a truthful "blocked: USER_AUTHENTICATION_REQUIRED"
result, never a simulated success. execute_financial_action (LEVEL_3,
payment/ticketing) remains unimplemented and always blocked -- payment was
never part of this phase's objective. Search is consumed as a TOOL over
HTTP (karenseir-search's existing, unmodified /v1/query/search) -- this
service never reimplements Query Intelligence/orchestration/ranking/dedup."""
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


def _monolith_client(user_token: str) -> httpx.Client:
    return httpx.Client(base_url=config.MONOLITH_BASE_URL, timeout=config.MONOLITH_TIMEOUT_SECONDS,
                         headers={"Authorization": f"Bearer {user_token}"})


def _no_auth_result() -> ToolResult:
    return ToolResult(status="blocked",
                       data={"reason": "no authenticated user session was forwarded to the assistant for this action"},
                       error_code="USER_AUTHENTICATION_REQUIRED")


def _monolith_call(user_token: str, method: str, path: str, *, json_body: dict | None = None,
                    extra_headers: dict | None = None) -> ToolResult:
    try:
        with _monolith_client(user_token) as c:
            r = c.request(method, path, json=json_body, headers=extra_headers)
    except httpx.HTTPError as exc:
        return ToolResult(status="error", data={}, error_code=f"MONOLITH_UNREACHABLE:{type(exc).__name__}")
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = {"raw": r.text[:200]}
        return ToolResult(status="error", data=detail, error_code=f"HTTP_{r.status_code}")
    return ToolResult(status="ok", data=r.json(), error_code=None)


def price_check_offer(args: dict) -> ToolResult:
    """LEVEL_0 per Phase 3's own spec ("price_check" listed as a read/
    compute example) -- confirms the current real price for a real offer_id
    via the monolith's own idempotent (command_id-keyed) endpoint. Does not
    reserve inventory; that only happens in submit_reservation_hold."""
    user_token = args.get("user_token")
    if not user_token:
        return _no_auth_result()
    offer_id = args.get("offer_id")
    if not offer_id:
        return ToolResult(status="error", data={}, error_code="MISSING_OFFER_ID")
    body = {"units": args.get("units", 1), "command_id": args["command_id"]}
    return _monolith_call(user_token, "POST", f"/offers/{offer_id}/price-check", json_body=body)


def submit_reservation_hold(args: dict) -> ToolResult:
    """LEVEL_2. Calls the real monolith POST /orchestration/bookings, which
    creates a real Reservation(status="reserved") from an already-confirmed
    price_check_id -- a genuine inventory hold, not a payment or ticket.
    Requires a real forwarded user_token; without one this is a truthful
    block, never a simulated success (unchanged posture from Phase 3, now
    with a precise reason instead of a blanket "not implemented")."""
    user_token = args.get("user_token")
    if not user_token:
        return _no_auth_result()
    price_check_id = args.get("price_check_id")
    if not price_check_id:
        return ToolResult(status="blocked", data={"reason": "price_check_offer must succeed first"},
                           error_code="PRICE_CHECK_REQUIRED")
    body = {"price_check_id": price_check_id, "command_id": args["command_id"]}
    return _monolith_call(user_token, "POST", "/orchestration/bookings", json_body=body)


def release_reservation_hold(args: dict) -> ToolResult:
    """LEVEL_2 (rollback path for submit_reservation_hold). Calls the real
    monolith POST /reservations/{id}/service-requests with
    request_type="cancel" -- the genuine cancellation path for a reserved
    booking. Not instantaneous (the monolith records it as "submitted" for
    review), but it is the real rollback primitive that exists; nothing
    here fabricates an immediate "cancelled" state."""
    user_token = args.get("user_token")
    if not user_token:
        return _no_auth_result()
    reservation_id = args.get("reservation_id")
    if not reservation_id:
        return ToolResult(status="error", data={}, error_code="MISSING_RESERVATION_ID")
    body = {"request_type": "cancel", "reason": args.get("reason", "assistant_rollback")}
    return _monolith_call(user_token, "POST", f"/reservations/{reservation_id}/service-requests",
                           json_body=body, extra_headers={"Idempotency-Key": args["idempotency_key"]})


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
    "price_check_offer": Tool(
        name="price_check_offer", version="1.0", capability="confirm the real current price of a real offer (read/compute)",
        required_inputs=("offer_id", "command_id", "user_token"), output_contract="monolith POST /offers/{id}/price-check response",
        permission_level=LEVEL_READ, idempotent=True, approval_required=False,
        timeout_seconds=config.MONOLITH_TIMEOUT_SECONDS, handler=price_check_offer,
    ),
    "submit_reservation_hold": Tool(
        name="submit_reservation_hold", version="2.0",
        capability="place a real provider reservation hold via monolith POST /orchestration/bookings",
        required_inputs=("price_check_id", "command_id", "user_token"),
        output_contract="monolith reservation object, or {status: blocked, error_code}",
        permission_level=LEVEL_APPROVAL, idempotent=True, approval_required=True,
        timeout_seconds=config.MONOLITH_TIMEOUT_SECONDS, handler=submit_reservation_hold,
    ),
    "release_reservation_hold": Tool(
        name="release_reservation_hold", version="1.0",
        capability="cancel a reservation hold via monolith POST /reservations/{id}/service-requests (request_type=cancel)",
        required_inputs=("reservation_id", "idempotency_key", "user_token"),
        output_contract="monolith service-request object, or {status: blocked, error_code}",
        permission_level=LEVEL_APPROVAL, idempotent=True, approval_required=True,
        timeout_seconds=config.MONOLITH_TIMEOUT_SECONDS, handler=release_reservation_hold,
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
