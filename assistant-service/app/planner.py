"""Goal/intent planning for the Assistant. Reuses karenseir-search's
existing deterministic Query Intelligence (/v1/query/plan) as the reasoning
step for search-shaped requests, rather than duplicating Persian NLU here
(master prompt: "Assistant must NOT duplicate Search internals"). No LLM is
called -- deterministic only, same policy already established in Search
Phase 4 (a model-provider abstraction is a documented future extension
point, not implemented in this slice; see main.py module docstring)."""
from __future__ import annotations

import httpx

from . import config

GOAL_SEARCH = "search"
GOAL_CLARIFY = "clarify"
GOAL_UNSUPPORTED = "unsupported"
GOAL_UNKNOWN = "unknown"


def plan_goal(text: str, *, public: bool, tenant_ref: str | None) -> dict:
    """Returns {"goal": ..., "plan": <SearchPlan dict or None>, "error_code": ...|None}."""
    try:
        with httpx.Client(base_url=config.SEARCH_SERVICE_URL, timeout=config.SEARCH_TIMEOUT_SECONDS) as c:
            r = c.post("/v1/query/plan", json={"text": text, "public": public, "tenant_ref": tenant_ref})
    except httpx.HTTPError as exc:
        return {"goal": GOAL_UNKNOWN, "plan": None, "error_code": f"SEARCH_UNREACHABLE:{type(exc).__name__}"}
    if r.status_code >= 400:
        return {"goal": GOAL_UNKNOWN, "plan": None, "error_code": f"HTTP_{r.status_code}"}
    plan = r.json()["plan"]
    status = plan["status"]
    if status == "valid":
        goal = GOAL_SEARCH
    elif status in ("ambiguous", "invalid"):
        goal = GOAL_CLARIFY
    elif status == "unsupported":
        goal = GOAL_UNSUPPORTED
    else:
        goal = GOAL_UNKNOWN
    return {"goal": goal, "plan": plan, "error_code": None}


def compose_reply(goal: str, plan: dict | None, tool_result) -> tuple[str, dict]:
    """Deterministic, template-based reply composition -- explicit and
    auditable, no generative text. Returns (message_text, structured_data)."""
    if goal == GOAL_CLARIFY and plan:
        reasons = "، ".join(a["message"] for a in plan.get("ambiguities", []))
        return (f"متوجه نشدم دقیقاً منظورتان چیست: {reasons}" if reasons else
                "می‌شود دقیق‌تر بگویید دنبال چه چیزی هستید؟", {"type": "CLARIFY", "plan": plan})
    if goal == GOAL_UNSUPPORTED and plan:
        reasons = "، ".join(a["message"] for a in plan.get("ambiguities", []))
        return (f"این درخواست هنوز پشتیبانی نمی‌شود: {reasons}", {"type": "UNSUPPORTED", "plan": plan})
    if goal == GOAL_UNKNOWN:
        return ("در حال حاضر امکان پردازش این درخواست نیست.", {"type": "ERROR"})
    if goal == GOAL_SEARCH and tool_result is not None:
        if tool_result.status == "error":
            return ("موتور جست‌وجو موقتاً در دسترس نیست.", {"type": "SEARCH_ERROR", "error_code": tool_result.error_code})
        data = tool_result.data
        if not data.get("executed"):
            return ("این درخواست نیاز به توضیح بیشتر دارد.", {"type": "CLARIFY", "plan": data.get("plan")})
        total = data["result"]["pagination"]["total"]
        if total == 0:
            return ("نتیجه‌ای برای این جست‌وجو یافت نشد.", {"type": "SEARCH_RESULT_CARD", "total": 0, "result": data["result"]})
        return (f"{total} گزینه پیدا شد.", {"type": "SEARCH_RESULT_CARD", "total": total, "result": data["result"]})
    return ("متوجه نشدم، لطفاً دوباره امتحان کنید.", {"type": "ERROR"})
