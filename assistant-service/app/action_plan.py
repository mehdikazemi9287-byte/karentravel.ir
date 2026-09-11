"""Deterministic Action Plan (Phase 3 sec 3). A plan is a small, explicit
record of the steps taken/available for a goal -- never used to drive
execution by itself (the execution guard + approval model own that); it
exists for explainability and for the additive UI response contract."""
from __future__ import annotations

import json
import uuid

from . import db

STATUS_DRAFT = "DRAFT"
STATUS_ACTIVE = "ACTIVE"
STATUS_COMPLETED = "COMPLETED"


def get_or_create(conversation_id: str, trip_state_id: str | None, goal: str) -> dict:
    row = db.conn().execute(
        "SELECT id, goal, status, steps FROM action_plans WHERE conversation_id = %s ORDER BY created_at DESC LIMIT 1",
        (conversation_id,),
    ).fetchone()
    if row and row[1] == goal:
        return {"id": str(row[0]), "goal": row[1], "status": row[2], "steps": row[3]}
    new_id = str(uuid.uuid4())
    db.conn().execute("INSERT INTO action_plans (id, conversation_id, trip_state_id, goal, status, steps) VALUES (%s,%s,%s,%s,%s,%s)",
                       (new_id, conversation_id, trip_state_id, goal, STATUS_ACTIVE, json.dumps([], ensure_ascii=False)))
    return {"id": new_id, "goal": goal, "status": STATUS_ACTIVE, "steps": []}


def append_step(plan_id: str, order: int, tool: str, level: int, status: str) -> None:
    row = db.conn().execute("SELECT steps FROM action_plans WHERE id = %s", (plan_id,)).fetchone()
    steps = list(row[0]) if row and row[0] else []
    steps.append({"order": order, "tool": tool, "level": level, "status": status})
    db.conn().execute("UPDATE action_plans SET steps = %s, updated_at = now() WHERE id = %s",
                       (json.dumps(steps, ensure_ascii=False), plan_id))


def compact(plan: dict) -> dict:
    """Token-bounded summary for the response contract -- never the raw
    conversation/Search history, just the plan's own small step list."""
    return {"plan_id": plan["id"], "goal": plan["goal"], "status": plan["status"], "steps": plan["steps"]}
