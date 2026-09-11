"""Human handoff foundation (Phase 3 sec 15). No fake support ticket system
is implemented -- this only builds the structured escalation contract a
real support system would consume, and a deterministic trigger check. AI
and human messages stay distinguishable in messages.role (existing "user"/
"assistant" roles; a future human-agent channel would add a third role,
not implemented here since no real human-support backend is wired)."""
from __future__ import annotations

def build_escalation(conversation_id: str, state: dict, reason: str) -> dict:
    return {
        "conversation_id": conversation_id,
        "reason": reason,
        "trip_state_id": state.get("trip_state_id"),
        "current_plan_summary": {
            "vertical": (state.get("current_plan") or {}).get("vertical"),
            "status": (state.get("current_plan") or {}).get("status"),
        } if state.get("current_plan") else None,
        "selected_result": state.get("selected_result"),
        "customer_visible_status": "درخواست شما برای یک کارشناس انسانی ثبت شد.",
    }
