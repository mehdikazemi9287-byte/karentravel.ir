"""karenseir-assistant : Travel Assistant / Travel Copilot service.

Phase A: conversational search (goal routing via Search's own planner).
Phase 2: conversational STATE -- multi-turn refinement, result-set memory,
entity selection, Trip State, LEVEL_1 booking-draft prep. Search remains the
sole source of truth for query planning/execution (secs 12-13): this file
only classifies the ACTION of a turn and carries structured context into
Search's existing contract; it never re-parses dates/passengers/cabin.

No LLM is called anywhere in this service -- classification (classifier.py)
and reply composition (planner.py) are deterministic, matching the
established "deterministic is the production default" policy."""
from __future__ import annotations

import json
import time
import uuid

from fastapi import Body, FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import action_plan, approval, classifier, config, db, handoff, planner, resolver, tools, trip

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


# ---------------------------------------------------------------- state ----

def _load_state(conversation_id: str) -> dict:
    row = db.conn().execute(
        "SELECT last_plan, previous_plan, last_result_set, selected_result, trip_state_id, status "
        "FROM conversations WHERE id = %s", (conversation_id,)
    ).fetchone()
    return {
        "current_plan": row[0], "previous_plan": row[1], "last_result_set": row[2],
        "selected_result": row[3], "trip_state_id": str(row[4]) if row[4] else None, "status": row[5],
    } if row else {}


def _save_state(conversation_id: str, **fields) -> None:
    cols, vals = [], []
    for k, v in fields.items():
        cols.append(f"{k} = %s")
        vals.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
    vals.append(conversation_id)
    db.conn().execute(f"UPDATE conversations SET updated_at = now(), {', '.join(cols)} WHERE id = %s", vals)


def _get_or_create_conversation(conversation_id: str | None, public: bool, tenant_ref: str | None) -> str:
    c = db.conn()
    if conversation_id:
        row = c.execute("SELECT id FROM conversations WHERE id = %s", (conversation_id,)).fetchone()
        if row:
            return str(row[0])
    new_id = str(uuid.uuid4())
    c.execute("INSERT INTO conversations (id, public, tenant_ref) VALUES (%s,%s,%s)", (new_id, public, tenant_ref))
    return new_id


def _append_message(conversation_id: str, role: str, text: str, data: dict | None) -> None:
    db.conn().execute("INSERT INTO messages (conversation_id, role, text, data) VALUES (%s,%s,%s,%s)",
                       (conversation_id, role, text, json.dumps(data or {}, ensure_ascii=False)))


def _audit(conversation_id: str, turn_id: str, action: str, tool: str | None, input_ref: dict,
           output_ref: dict, before_hash: str, after_hash: str, result: str, error_code: str | None) -> None:
    db.conn().execute(
        """INSERT INTO audit_log (conversation_id, turn_id, action, tool, input_reference, output_reference,
           state_before_hash, state_after_hash, result, error_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (conversation_id, turn_id, action, tool, json.dumps(input_ref, ensure_ascii=False, default=str),
         json.dumps(output_ref, ensure_ascii=False, default=str), before_hash, after_hash, result, error_code),
    )


def _record_tool_call(conversation_id: str, tool_name: str, level: int, status: str,
                       latency_ms: float, error_code: str | None) -> None:
    db.conn().execute(
        "INSERT INTO tool_calls (conversation_id, tool, permission_level, status, latency_ms, error_code) "
        "VALUES (%s,%s,%s,%s,%s,%s)", (conversation_id, tool_name, level, status, latency_ms, error_code),
    )


def _revalidate_selected(selected: dict, current_plan: dict | None, public: bool, tenant_ref: str | None) -> dict | None:
    """Re-runs Search for the current plan and compares the selected
    entity's price. Returns None if there's no plan context to revalidate
    against (never blocks on a missing plan -- the caller decides)."""
    if not current_plan or not current_plan.get("vertical"):
        return None
    overrides = planner.context_overrides(current_plan)
    args = {"text": "", "public": public, "tenant_ref": tenant_ref, **overrides}
    result, _ = tools.call_tool("search_travel", args)
    if result.status != "ok" or not result.data.get("executed"):
        return {"changed": True, "available": False, "old_price": selected.get("price"), "new_price": None, "new_item": None}
    return resolver.revalidate_price(selected, result.data["result"])


# ------------------------------------------------------------ handlers ----

def _handle_search(text: str, state: dict, public: bool, tenant_ref: str | None, refine: bool) -> dict:
    overrides = planner.context_overrides(state.get("current_plan")) if refine else {}
    goal_result = planner.plan_goal(text, public=public, tenant_ref=tenant_ref, overrides=overrides)
    refined = bool(overrides) and goal_result["goal"] == planner.GOAL_SEARCH
    if not refined and refine:
        # carried context didn't help -- fall back to the bare turn alone
        goal_result = planner.plan_goal(text, public=public, tenant_ref=tenant_ref)

    goal, plan = goal_result["goal"], goal_result["plan"]
    tool_result = None
    if goal == planner.GOAL_SEARCH:
        args = {"text": text, "public": public, "tenant_ref": tenant_ref, "vertical": plan.get("vertical")}
        if refined:
            args.update(overrides)
        tool_result, latency_ms = tools.call_tool("search_travel", args)
        yield_tool = ("search_travel", tools.LEVEL_READ, tool_result.status, latency_ms, tool_result.error_code)
    else:
        yield_tool = None

    reply_text, reply_data = planner.compose_reply(goal, plan, tool_result)
    new_result_set = None
    if goal == planner.GOAL_SEARCH and tool_result and tool_result.status == "ok" and tool_result.data.get("executed"):
        resolved_plan = tool_result.data["result"].get("plan", plan)
        new_result_set = resolver.compact_result_set(tool_result.data["result"], vertical=resolved_plan.get("vertical", ""))
    if refined:
        reply_data["refined"] = True
    return {"goal": goal, "reply_text": reply_text, "reply_data": reply_data,
            "new_plan": (tool_result.data["result"].get("plan") if tool_result and tool_result.status == "ok"
                         and tool_result.data.get("executed") else plan),
            "new_result_set": new_result_set, "tool_call": yield_tool, "refined": refined}


@app.post("/v1/conversation/message")
def post_message(data: MessageIn = Body(...), x_correlation_id: str | None = Header(default=None)):
    corr = x_correlation_id or str(uuid.uuid4())
    turn_id = str(uuid.uuid4())
    try:
        conversation_id = _get_or_create_conversation(data.conversation_id, data.public, data.tenant_ref)
        state = _load_state(conversation_id)
    except Exception:
        return JSONResponse(status_code=503, content={"code": "ASSISTANT_STORAGE_UNAVAILABLE", "correlation_id": corr})

    before_hash = resolver.state_hash(state)
    _append_message(conversation_id, "user", data.text, None)

    result_set = state.get("last_result_set")
    fresh_result_set = result_set if resolver.result_set_is_fresh(result_set) else None
    cls = classifier.classify(data.text, has_active_plan=bool((state.get("current_plan") or {}).get("vertical")),
                               has_result_set=bool(fresh_result_set))
    action = cls["action"]
    reply_data: dict = {"type": action}
    tool_used = None
    error_code = None
    refined = False

    if action == classifier.CANCEL_CURRENT_FLOW:
        _save_state(conversation_id, last_plan=None, previous_plan=None, last_result_set=None, selected_result=None)
        reply_text = "باشه، از اول شروع می‌کنیم."

    elif action == classifier.BLOCKED_FINANCIAL_ACTION:
        result, latency_ms = tools.call_tool("execute_financial_action", {})
        _record_tool_call(conversation_id, "execute_financial_action", tools.LEVEL_FINANCIAL, result.status, latency_ms, result.error_code)
        tool_used, error_code = "execute_financial_action", result.error_code
        reply_text = "پرداخت یا رزرو نهایی در حال حاضر توسط دستیار انجام نمی‌شود. این کار نیاز به تأیید و مسیر رسمی رزرو دارد."
        reply_data["blocked_level"] = tools.LEVEL_FINANCIAL

    elif action == classifier.SELECT_RESULT:
        item = resolver.resolve_ordinal(fresh_result_set, cls["ordinal_ref"])
        if not item:
            reply_text = "متوجه نشدم منظورتان کدام گزینه از نتایج قبلی است، یا نتایج قبلی دیگر معتبر نیستند."
            reply_data["type"] = "CLARIFY"
        else:
            item = {**item, "vertical": fresh_result_set["vertical"]}
            ts = trip.get_or_create(conversation_id, state.get("trip_state_id"))
            trip.update_from_selection(ts["id"], fresh_result_set["vertical"], item)
            _save_state(conversation_id, selected_result=item, trip_state_id=ts["id"])
            reply_text = f"گزینه {item['display_index']} ({item.get('title') or ''}) انتخاب شد."
            reply_data["selected"] = item

    elif action == classifier.ASK_ABOUT_RESULT:
        item = resolver.resolve_ordinal(fresh_result_set, cls["ordinal_ref"])
        if not item:
            reply_text = "متوجه نشدم منظورتان کدام گزینه است."
            reply_data["type"] = "CLARIFY"
        else:
            reply_text = (f"گزینه {item['display_index']}: {item.get('title') or 'نامشخص'} -- "
                          f"قیمت {item.get('price')} {item.get('currency') or ''}. "
                          "سایر جزئیات (مانند بار مجاز یا امکانات) در حال حاضر در دسترس نیست.")
            reply_data["item"] = item

    elif action == classifier.START_BOOKING_PREP:
        selected = state.get("selected_result")
        if not selected:
            reply_text = "اول باید یکی از گزینه‌ها را انتخاب کنید."
            reply_data["type"] = "CLARIFY"
        else:
            # Phase 3 sec 11: revalidate price/availability before any
            # booking-sensitive transition. Same entity, fresh data only --
            # never silently substituted for a different offer.
            reval = _revalidate_selected(selected, state.get("current_plan"), data.public, data.tenant_ref)
            if reval and not reval["available"]:
                _save_state(conversation_id, selected_result=None)
                reply_text = "این گزینه دیگر در دسترس نیست. لطفاً دوباره جست‌وجو کنید یا گزینه دیگری انتخاب کنید."
                reply_data["type"] = "CLARIFY"
                reply_data["revalidation"] = reval
            elif reval and reval["changed"]:
                _save_state(conversation_id, selected_result=reval["new_item"])
                reply_text = (f"قیمت این گزینه تغییر کرده: قبلاً {reval['old_price']}، الان {reval['new_price']}. "
                              "اگر با قیمت جدید موافقید دوباره بگویید «رزروش کن».")
                reply_data["type"] = "CLARIFY"
                reply_data["revalidation"] = reval
            else:
                ts = trip.get_or_create(conversation_id, state.get("trip_state_id"))
                party = (state.get("current_plan") or {}).get("party") or {}
                sel_vertical = selected.get("vertical") or "unknown"
                readiness = trip.evaluate_readiness(sel_vertical, selected, party)
                plan_row = action_plan.get_or_create(conversation_id, ts["id"], f"book_{sel_vertical}")
                draft_result, latency_ms = tools.call_tool("create_booking_draft", {
                    "trip_state_id": ts["id"], "vertical": sel_vertical,
                    "selected_item": selected, "missing_fields": readiness["missing"],
                })
                _record_tool_call(conversation_id, "create_booking_draft", tools.LEVEL_DRAFT, draft_result.status, latency_ms, draft_result.error_code)
                action_plan.append_step(plan_row["id"], len(plan_row["steps"]) + 1, "create_booking_draft", tools.LEVEL_DRAFT, draft_result.status)
                tool_used = "create_booking_draft"
                reply_data.update({"readiness": readiness, "draft": draft_result.data, "plan_id": plan_row["id"]})
                reply_text = ("پیش‌نویس رزرو آماده شد؛ این فقط یک پیش‌نویس داخلی است، هیچ رزرو یا پرداختی انجام نشده. "
                              if readiness["ready"] else
                              f"پیش‌نویس رزرو ساخته شد ولی موارد ناقص دارد: {', '.join(readiness['missing'])}.")

    elif action == classifier.REQUEST_HUMAN_HANDOFF:
        escalation = handoff.build_escalation(conversation_id, state, "user_requested")
        reply_text = escalation["customer_visible_status"]
        reply_data["escalation"] = escalation

    elif action == classifier.ADVANCE_ACTION:
        ts_id = state.get("trip_state_id")
        ts_row = db.conn().execute("SELECT status FROM trip_states WHERE id = %s", (ts_id,)).fetchone() if ts_id else None
        selected = state.get("selected_result")
        if not selected or not ts_row or ts_row[0] != trip.STATUS_READY_FOR_BOOKING_PREP:
            reply_text = "چیزی برای ادامه دادن آماده نیست؛ اول باید جست‌وجو، انتخاب و آماده‌سازی رزرو انجام شود."
            reply_data["type"] = classifier.UNSUPPORTED_ACTION
            action = classifier.UNSUPPORTED_ACTION
        else:
            args = {"trip_state_id": ts_id, "selected_item": selected}
            fp = tools.operation_fingerprint("submit_reservation_hold", args)
            appr = approval.request_approval(conversation_id, None, "submit_reservation_hold", fp)
            try:
                trip.transition(ts_id, ts_row[0], trip.STATUS_APPROVAL_NEEDED)
            except trip.InvalidTransition:
                pass   # approval request itself still stands; state machine just didn't advance
            reply_text = (f"برای درخواست رزرو موقت روی «{selected.get('title')}» با قیمت {selected.get('price')} "
                          "نیاز به تأیید شماست. برای تأیید دقیقاً بگویید «تایید می‌کنم».")
            reply_data.update({"pending_approval_id": appr["id"], "requires_approval": True,
                               "operation_fingerprint": fp})

    elif action == classifier.CONFIRM_PENDING_APPROVAL:
        selected = state.get("selected_result")
        ts_id = state.get("trip_state_id")
        fp = tools.operation_fingerprint("submit_reservation_hold", {"trip_state_id": ts_id, "selected_item": selected}) if selected and ts_id else None
        pending = approval.find_approval(conversation_id, "submit_reservation_hold", fp) if fp else None
        if not pending or pending["status"] != approval.PENDING:
            # not unambiguously bound to a real pending action -- never inferred
            reply_text = "در حال حاضر چیزی برای تأیید وجود ندارد."
            reply_data["type"] = classifier.UNSUPPORTED_ACTION
            action = classifier.UNSUPPORTED_ACTION
        else:
            approval.decide_approval(pending["id"], approved=True)
            guard = approval.check_execution_guard(
                tool_name="submit_reservation_hold", args={"trip_state_id": ts_id, "selected_item": selected},
                conversation_id=conversation_id, selected_result=selected,
                result_set=state.get("last_result_set"), readiness=None,
            )
            reply_data["execution_guard"] = guard
            if guard["allowed"]:
                result, latency_ms = tools.call_tool("submit_reservation_hold", {"trip_state_id": ts_id, "selected_item": selected})
                _record_tool_call(conversation_id, "submit_reservation_hold", tools.LEVEL_APPROVAL, result.status, latency_ms, result.error_code)
                tool_used, error_code = "submit_reservation_hold", result.error_code
                reply_text = "تأیید شما ثبت شد؛ اما در حال حاضر امکان تکمیل رزرو نهایی از طریق دستیار وجود ندارد و نیاز به مسیر رسمی رزرو دارد."
                reply_data["blocked_level"] = tools.LEVEL_APPROVAL
            else:
                reply_text = f"تأیید ثبت نشد: {guard['reason']}"
                reply_data["type"] = "CLARIFY"

    else:   # NEW_SEARCH / REFINE_SEARCH / UNSUPPORTED_ACTION
        if action == classifier.UNSUPPORTED_ACTION:
            reply_text, reply_data = ("این درخواست را متوجه نشدم.", {"type": classifier.UNSUPPORTED_ACTION})
        else:
            outcome = _handle_search(data.text, state, data.public, data.tenant_ref, refine=(action == classifier.REFINE_SEARCH))
            reply_text, reply_data, refined = outcome["reply_text"], outcome["reply_data"], outcome["refined"]
            if outcome["tool_call"]:
                tname, level, status, latency_ms, err = outcome["tool_call"]
                _record_tool_call(conversation_id, tname, level, status, latency_ms, err)
                tool_used, error_code = tname, err
            if outcome["goal"] == planner.GOAL_SEARCH:
                save_kwargs = {"last_plan": outcome["new_plan"]}
                if state.get("current_plan"):
                    save_kwargs["previous_plan"] = state["current_plan"]
                if outcome["new_result_set"]:
                    save_kwargs["last_result_set"] = outcome["new_result_set"]
                    save_kwargs["selected_result"] = None
                _save_state(conversation_id, **save_kwargs)

    _append_message(conversation_id, "assistant", reply_text, reply_data)
    final_state = _load_state(conversation_id)
    after_hash = resolver.state_hash(final_state)
    _audit(conversation_id, turn_id, action, tool_used, {"text": data.text}, {"reply_type": reply_data.get("type")},
           before_hash, after_hash, "ok" if not error_code else "error", error_code)

    # Additive structured response contract (Phase 3 sec 8) -- existing
    # fields (conversation_id/action/refined/message) are unchanged so
    # existing consumers keep working.
    available_actions = []
    ts_id = final_state.get("trip_state_id")
    ts_status = None
    if ts_id:
        row = db.conn().execute("SELECT status FROM trip_states WHERE id = %s", (ts_id,)).fetchone()
        ts_status = row[0] if row else None
        if ts_status == trip.STATUS_READY_FOR_BOOKING_PREP:
            available_actions.append({"action_id": "advance_to_reservation_hold", "label": "درخواست رزرو موقت",
                                       "level": tools.LEVEL_APPROVAL, "requires_approval": True})
        elif ts_status == trip.STATUS_APPROVAL_NEEDED:
            available_actions.append({"action_id": "confirm_pending_approval", "label": "تأیید درخواست رزرو",
                                       "level": tools.LEVEL_APPROVAL, "requires_approval": True})

    return {
        "conversation_id": conversation_id, "correlation_id": corr, "turn_id": turn_id,
        "action": action, "intent": action, "refined": refined,
        "trip_state_id": ts_id, "trip_state_status": ts_status,
        "message": {"role": "assistant", "text": reply_text, "data": reply_data},
        "actions": available_actions,
        "warnings": (reply_data.get("readiness") or {}).get("warnings", []),
        "missing_information": (reply_data.get("readiness") or {}).get("missing", []),
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
