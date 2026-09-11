"""karenseir-assistant : Travel Assistant / Travel Copilot service --
Phase A vertical slice: conversational search.

Boundary (master prompt sec 1): this service owns conversation/session
state, goal planning, the tool registry, and the permission/audit layer. It
consumes karenseir-search as a TOOL over HTTP; it never reimplements Search
internals (Query Intelligence, orchestration, ranking, dedup). It owns no
booking/payment/commerce state -- those stay in the existing monolith.

Model provider abstraction (sec 52): goal planning and reply composition
are deterministic (planner.py) in this slice. No LLM is called, no
credentials exist for one, and none is required for this to function --
matching the same "deterministic is the production default, AI is optional
and never mandatory" policy already established in Search Phase 4."""
from __future__ import annotations

import time
import uuid

from fastapi import Body, FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import config, db, planner, tools

app = FastAPI(title="karenseir-assistant", version=config.SERVICE_VERSION)


class MessageIn(BaseModel):
    conversation_id: str | None = None
    text: str = Field(max_length=500)
    public: bool = True
    tenant_ref: str | None = Field(default=None, max_length=120)


@app.get("/health")
def health():
    return {"status": "ok", "service": "karenseir-assistant"}


@app.get("/ready")
def ready():
    dbh = db.health()
    ok = dbh.get("ok", False)
    return JSONResponse(status_code=200 if ok else 503,
                         content={"status": "ready" if ok else "degraded", "db": dbh})


@app.get("/version")
def version():
    return {"service": "karenseir-assistant", "version": config.SERVICE_VERSION,
            "git_commit": config.BUILD_COMMIT, "environment": config.ENVIRONMENT}


def _get_or_create_conversation(conversation_id: str | None, public: bool, tenant_ref: str | None) -> str:
    c = db.conn()
    if conversation_id:
        row = c.execute("SELECT id FROM conversations WHERE id = %s", (conversation_id,)).fetchone()
        if row:
            return str(row[0])
    new_id = str(uuid.uuid4())
    c.execute("INSERT INTO conversations (id, public, tenant_ref) VALUES (%s,%s,%s)",
              (new_id, public, tenant_ref))
    return new_id


def _append_message(conversation_id: str, role: str, text: str, data: dict | None) -> None:
    import json
    db.conn().execute(
        "INSERT INTO messages (conversation_id, role, text, data) VALUES (%s,%s,%s,%s)",
        (conversation_id, role, text, json.dumps(data or {}, ensure_ascii=False)),
    )


def _record_tool_call(conversation_id: str, tool_name: str, level: int, status: str,
                       latency_ms: float, error_code: str | None) -> None:
    db.conn().execute(
        "INSERT INTO tool_calls (conversation_id, tool, permission_level, status, latency_ms, error_code) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (conversation_id, tool_name, level, status, latency_ms, error_code),
    )


def _get_last_plan(conversation_id: str) -> dict | None:
    row = db.conn().execute("SELECT last_plan FROM conversations WHERE id = %s", (conversation_id,)).fetchone()
    return row[0] if row and row[0] else None


def _set_last_plan(conversation_id: str, plan: dict) -> None:
    import json
    db.conn().execute("UPDATE conversations SET last_plan = %s WHERE id = %s",
                       (json.dumps(plan, ensure_ascii=False), conversation_id))


def _run_search_tool(text: str, plan: dict, public: bool, tenant_ref: str | None, overrides: dict) -> tuple:
    args = {"text": text, "public": public, "tenant_ref": tenant_ref, "vertical": plan.get("vertical")}
    args.update(overrides)
    return tools.call_tool("search_travel", args)


@app.post("/v1/conversation/message")
def post_message(data: MessageIn = Body(...), x_correlation_id: str | None = Header(default=None)):
    corr = x_correlation_id or str(uuid.uuid4())
    try:
        conversation_id = _get_or_create_conversation(data.conversation_id, data.public, data.tenant_ref)
        last_plan = _get_last_plan(conversation_id) if data.conversation_id else None
    except Exception:
        # conversation state is real product state, not best-effort -- a DB
        # outage is a real, truthful error, never a fabricated conversation.
        return JSONResponse(status_code=503, content={"code": "ASSISTANT_STORAGE_UNAVAILABLE", "correlation_id": corr})

    _append_message(conversation_id, "user", data.text, None)

    goal_result = planner.plan_goal(data.text, public=data.public, tenant_ref=data.tenant_ref)
    refined = False
    overrides: dict = {}
    if goal_result["goal"] != planner.GOAL_SEARCH and last_plan:
        # Live Conversational Search (master prompt sec 4): a follow-up like
        # "صبح نباشه" rarely re-states the vertical/route on its own. Retry
        # planning with the PREVIOUS turn's resolved vertical/route/dates as
        # explicit structured overrides -- never inventing a new one, only
        # carrying forward what was already genuinely resolved -- before
        # falling back to whatever the bare new text alone produced.
        overrides = planner.context_overrides(last_plan)
        if overrides:
            retry = planner.plan_goal(data.text, public=data.public, tenant_ref=data.tenant_ref, overrides=overrides)
            if retry["goal"] == planner.GOAL_SEARCH:
                goal_result = retry
                refined = True
    goal, plan = goal_result["goal"], goal_result["plan"]

    tool_result = None
    if goal == planner.GOAL_SEARCH:
        tool_result, latency_ms = _run_search_tool(data.text, plan, data.public, data.tenant_ref, overrides if refined else {})
        _record_tool_call(conversation_id, "search_travel", tools.LEVEL_READ, tool_result.status, latency_ms, tool_result.error_code)
        if tool_result.status == "ok" and tool_result.data.get("executed"):
            _set_last_plan(conversation_id, tool_result.data["result"].get("plan", plan))

    reply_text, reply_data = planner.compose_reply(goal, plan, tool_result)
    if refined:
        reply_data["refined"] = True
    _append_message(conversation_id, "assistant", reply_text, reply_data)
    db.conn().execute("UPDATE conversations SET updated_at = now(), active_goal = %s WHERE id = %s", (goal, conversation_id))

    return {
        "conversation_id": conversation_id,
        "correlation_id": corr,
        "goal": goal,
        "refined": refined,
        "message": {"role": "assistant", "text": reply_text, "data": reply_data},
    }


@app.get("/v1/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    c = db.conn()
    conv = c.execute("SELECT id, public, tenant_ref, active_goal FROM conversations WHERE id = %s", (conversation_id,)).fetchone()
    if not conv:
        return JSONResponse(status_code=404, content={"code": "CONVERSATION_NOT_FOUND"})
    rows = c.execute("SELECT role, text, data, created_at FROM messages WHERE conversation_id = %s ORDER BY created_at", (conversation_id,)).fetchall()
    return {
        "conversation_id": str(conv[0]), "public": conv[1], "tenant_ref": conv[2], "active_goal": conv[3],
        "messages": [{"role": r[0], "text": r[1], "data": r[2], "created_at": r[3].isoformat()} for r in rows],
    }
