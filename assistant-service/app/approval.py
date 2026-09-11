"""Approval model + execution guard (Phase 3 secs 5-6).

Approval is never inferred from adjacent affirmations ("اوکی", "خوبه", "برو
جلو") -- it must be an explicit approval submission bound to an exact
operation_fingerprint (tool + material parameters). If the action changes
after approval, the fingerprint changes, and the old approval no longer
matches -- it is never silently reused."""
from __future__ import annotations

import uuid

from . import db, tools

PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
CONSUMED = "CONSUMED"   # Phase 5: successfully executed -- a repeat confirm
                         # replays the stored (redacted) result, never re-executes


def request_approval(conversation_id: str, plan_id: str | None, tool: str, fingerprint: str) -> dict:
    """Idempotent: a repeated request for the same (conversation, tool,
    fingerprint) returns the existing approval record, never a duplicate."""
    c = db.conn()
    row = c.execute(
        "SELECT id, status FROM approvals WHERE conversation_id = %s AND tool = %s AND operation_fingerprint = %s",
        (conversation_id, tool, fingerprint),
    ).fetchone()
    if row:
        return {"id": str(row[0]), "status": row[1]}
    new_id = str(uuid.uuid4())
    c.execute("INSERT INTO approvals (id, conversation_id, plan_id, tool, operation_fingerprint) VALUES (%s,%s,%s,%s,%s)",
              (new_id, conversation_id, plan_id, tool, fingerprint))
    return {"id": new_id, "status": PENDING}


def decide_approval(approval_id: str, approved: bool) -> dict:
    c = db.conn()
    status = APPROVED if approved else REJECTED
    c.execute("UPDATE approvals SET status = %s, decided_at = now() WHERE id = %s", (status, approval_id))
    row = c.execute("SELECT id, status FROM approvals WHERE id = %s", (approval_id,)).fetchone()
    return {"id": str(row[0]), "status": row[1]} if row else {"id": approval_id, "status": "NOT_FOUND"}


def find_approval(conversation_id: str, tool: str, fingerprint: str) -> dict | None:
    row = db.conn().execute(
        "SELECT id, status, result_reference FROM approvals WHERE conversation_id = %s AND tool = %s AND operation_fingerprint = %s",
        (conversation_id, tool, fingerprint),
    ).fetchone()
    return {"id": str(row[0]), "status": row[1], "result_reference": row[2]} if row else None


def mark_consumed(approval_id: str, result_reference: dict) -> None:
    """result_reference must already be redacted by the caller -- this
    layer does not know which fields are sensitive for a given tool."""
    import json
    db.conn().execute("UPDATE approvals SET status = %s, result_reference = %s WHERE id = %s",
                       (CONSUMED, json.dumps(result_reference, ensure_ascii=False), approval_id))


def check_execution_guard(*, tool_name: str, args: dict, conversation_id: str,
                           selected_result: dict | None, result_set: dict | None,
                           readiness: dict | None) -> dict:
    """Fail-closed pre-execution validation for LEVEL_2+ tools (sec 6).
    Returns {"allowed": bool, "reason": str|None, "approval": dict|None}."""
    tool = tools.REGISTRY[tool_name]

    if not selected_result:
        return {"allowed": False, "reason": "NO_SELECTED_RESULT", "approval": None}
    if result_set is not None:
        from . import resolver
        if not resolver.result_set_is_fresh(result_set):
            return {"allowed": False, "reason": "RESULT_SET_STALE", "approval": None}
    if readiness is not None and not readiness.get("ready", False):
        return {"allowed": False, "reason": "BOOKING_NOT_READY", "approval": None}

    fingerprint = tools.operation_fingerprint(tool_name, args)
    if tool.approval_required:
        appr = find_approval(conversation_id, tool_name, fingerprint)
        if not appr:
            return {"allowed": False, "reason": "APPROVAL_REQUIRED", "approval": None}
        if appr["status"] != APPROVED:
            return {"allowed": False, "reason": f"APPROVAL_{appr['status']}", "approval": appr}
        return {"allowed": True, "reason": None, "approval": appr}

    return {"allowed": True, "reason": None, "approval": None}
