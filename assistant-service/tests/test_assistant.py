"""Assistant tests. DB is faked in-process (no real Postgres in this
throwaway test container) -- a generic fake that parses the actual SQL
main.py/trip.py issue, covering conversation state, trip state, booking
drafts, and audit log. Live DB writes are verified separately against the
real deployed karenseir_assistant database."""
import json
import os
import re
import uuid

os.environ.setdefault("ASSISTANT_DB_URL", "postgresql://fake")

import pytest
from fastapi.testclient import TestClient


class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []
    def fetchone(self):
        return self._rows[0] if self._rows else None
    def fetchall(self):
        return self._rows


CONV_COLS = ["id", "public", "tenant_ref", "active_goal", "last_plan", "previous_plan",
             "last_result_set", "selected_result", "trip_state_id", "pending_clarification", "status"]


class _FakeConn:
    """Generic-enough fake for this service's small, fixed set of queries."""
    closed = False

    def __init__(self):
        self.conversations = {}
        self.messages = {}
        self.trip_states = {}
        self.booking_drafts = {}
        self.audit_log = []
        self.tool_calls = []
        self.action_plans = {}
        self.approvals = {}

    def execute(self, sql, params=()):
        s = " ".join(sql.split())

        if s.startswith("INSERT INTO conversations"):
            cid, public, tenant_ref = params
            row = {c: None for c in CONV_COLS}
            row.update(id=cid, public=public, tenant_ref=tenant_ref, status="ACTIVE")
            self.conversations[cid] = row
            self.messages[cid] = []
            return _FakeCursor()

        if s.startswith("SELECT id FROM conversations"):
            (cid,) = params
            row = self.conversations.get(cid)
            return _FakeCursor([(row["id"],)] if row else [])

        if s.startswith("SELECT last_plan, previous_plan, last_result_set, selected_result, trip_state_id, status"):
            (cid,) = params
            row = self.conversations.get(cid)
            if not row:
                return _FakeCursor([])
            return _FakeCursor([(row["last_plan"], row["previous_plan"], row["last_result_set"],
                                 row["selected_result"], row["trip_state_id"], row["status"])])

        if s.startswith("UPDATE conversations SET updated_at = now(),"):
            cols = re.findall(r",\s*(\w+)\s*=\s*%s", s)
            cid = params[-1]
            if cid in self.conversations:
                for col, val in zip(cols, params[:-1]):
                    self.conversations[cid][col] = json.loads(val) if isinstance(val, str) and val and val[0] in "{[" else val
            return _FakeCursor()

        if s.startswith("INSERT INTO messages"):
            cid, role, text, data = params
            self.messages.setdefault(cid, []).append({"role": role, "text": text, "data": data})
            return _FakeCursor()

        if s.startswith("INSERT INTO tool_calls"):
            self.tool_calls.append(params)
            return _FakeCursor()

        if s.startswith("INSERT INTO audit_log"):
            self.audit_log.append(params)
            return _FakeCursor()

        if s.startswith("SELECT id, public, tenant_ref, active_goal FROM conversations"):
            (cid,) = params
            row = self.conversations.get(cid)
            return _FakeCursor([(row["id"], row["public"], row["tenant_ref"], row["active_goal"])] if row else [])

        if s.startswith("SELECT role, text, data, created_at FROM messages"):
            (cid,) = params
            from datetime import datetime, timezone
            return _FakeCursor([(m["role"], m["text"], m["data"], datetime.now(timezone.utc)) for m in self.messages.get(cid, [])])

        if s.startswith("SELECT id, status FROM trip_states"):
            (tid,) = params
            row = self.trip_states.get(tid)
            return _FakeCursor([(row["id"], row["status"])] if row else [])

        if s.startswith("SELECT status FROM trip_states"):
            (tid,) = params
            row = self.trip_states.get(tid)
            return _FakeCursor([(row["status"],)] if row else [])

        if s.startswith("INSERT INTO trip_states"):
            tid, cid, status = params
            self.trip_states[tid] = {"id": tid, "conversation_id": cid, "status": status}
            return _FakeCursor()

        if s.startswith("UPDATE trip_states SET selected_transport") or s.startswith("UPDATE trip_states SET selected_accommodation"):
            val, tid = params
            if tid in self.trip_states:
                self.trip_states[tid]["selection"] = json.loads(val)
            return _FakeCursor()

        if s.startswith("UPDATE trip_states SET status = %s, updated_at"):
            status, tid = params
            if tid in self.trip_states:
                self.trip_states[tid]["status"] = status
            return _FakeCursor()

        if s.startswith("SELECT id, status FROM booking_drafts"):
            tid, idem = params
            for d in self.booking_drafts.values():
                if d["trip_state_id"] == tid and d["idempotency_key"] == idem:
                    return _FakeCursor([(d["id"], d["status"])])
            return _FakeCursor([])

        if s.startswith("INSERT INTO booking_drafts"):
            did, tid, vertical, offer_ref, missing, status, idem = params
            self.booking_drafts[did] = {"id": did, "trip_state_id": tid, "vertical": vertical,
                                         "status": status, "idempotency_key": idem}
            return _FakeCursor()

        if s.startswith("SELECT id, goal, status, steps FROM action_plans"):
            (cid,) = params
            candidates = [p for p in self.action_plans.values() if p["conversation_id"] == cid]
            if not candidates:
                return _FakeCursor([])
            latest = candidates[-1]
            return _FakeCursor([(latest["id"], latest["goal"], latest["status"], latest["steps"])])

        if s.startswith("INSERT INTO action_plans"):
            pid, cid, tid, goal, status, steps = params
            self.action_plans[pid] = {"id": pid, "conversation_id": cid, "trip_state_id": tid,
                                       "goal": goal, "status": status, "steps": json.loads(steps)}
            return _FakeCursor()

        if s.startswith("SELECT steps FROM action_plans"):
            (pid,) = params
            row = self.action_plans.get(pid)
            return _FakeCursor([(row["steps"],)] if row else [])

        if s.startswith("UPDATE action_plans SET steps"):
            steps, pid = params
            if pid in self.action_plans:
                self.action_plans[pid]["steps"] = json.loads(steps)
            return _FakeCursor()

        if s.startswith("SELECT id, status FROM approvals WHERE conversation_id"):
            cid, tool, fp = params
            for a in self.approvals.values():
                if a["conversation_id"] == cid and a["tool"] == tool and a["operation_fingerprint"] == fp:
                    return _FakeCursor([(a["id"], a["status"])])
            return _FakeCursor([])

        if s.startswith("INSERT INTO approvals"):
            aid, cid, pid, tool, fp = params
            self.approvals[aid] = {"id": aid, "conversation_id": cid, "plan_id": pid, "tool": tool,
                                    "operation_fingerprint": fp, "status": "PENDING"}
            return _FakeCursor()

        if s.startswith("UPDATE approvals SET status"):
            status, aid = params
            if aid in self.approvals:
                self.approvals[aid]["status"] = status
            return _FakeCursor()

        if s.startswith("SELECT id, status FROM approvals WHERE id"):
            (aid,) = params
            row = self.approvals.get(aid)
            return _FakeCursor([(row["id"], row["status"])] if row else [])

        if s == "SELECT 1":
            return _FakeCursor([(1,)])

        raise AssertionError(f"unexpected query in fake conn: {s}")


@pytest.fixture
def fake_db(monkeypatch):
    from app import db as db_module
    fc = _FakeConn()
    monkeypatch.setattr(db_module, "conn", lambda: fc)
    return fc


@pytest.fixture
def client(fake_db):
    from app.main import app
    return TestClient(app)


def _stub_search_ok(monkeypatch, *, plan, total, entities=None):
    from app import tools as tools_module
    result = {
        "executed": True,
        "result": {
            "pagination": {"total": total},
            "entities": entities or [],
            "plan": plan,
        },
    }
    monkeypatch.setattr(tools_module, "call_tool", lambda name, args: (
        tools_module.ToolResult(status="ok", data=result, error_code=None), 4.0,
    ) if name == "search_travel" else (tools_module.REGISTRY[name].handler(args), 1.0))


def _entity(idx, title, price, entity_id=None):
    return {"entity_id": entity_id or f"e{idx}", "title": title, "provider_count": 1,
            "best_offer": {"offer_id": f"o{idx}", "final_price": price, "currency": "IRR"}}


# ---- basics ----

def test_health_ready(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200


def test_new_search_persists_plan_and_result_set(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "flight", "status": "valid", "origin": {"title": "تهران"}, "destination": {"title": "استانبول"},
            "departure_date": "2026-09-18", "return_date": "2026-09-21", "party": {"travellers": 1}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=2, entities=[_entity(1, "پرواز الف", 100), _entity(2, "پرواز ب", 80)])

    r = client.post("/v1/conversation/message", json={"text": "پرواز تهران استانبول جمعه تا دوشنبه"})
    cid = r.json()["conversation_id"]
    assert r.json()["action"] == "NEW_SEARCH"
    assert fake_db.conversations[cid]["last_plan"]["vertical"] == "flight"
    assert len(fake_db.conversations[cid]["last_result_set"]["items"]) == 2


# ---- multi-turn refinement ----

def test_followup_carries_route_and_dates_unchanged(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "flight", "status": "valid", "origin": {"title": "تهران"}, "destination": {"title": "استانبول"},
            "departure_date": "2026-09-18", "return_date": "2026-09-21", "party": {"travellers": 1}}
    calls = []

    def fake_plan_goal(text, *, public, tenant_ref, overrides=None):
        calls.append(dict(overrides or {}))
        if overrides:
            return {"goal": planner_module.GOAL_SEARCH, "plan": {**plan, **overrides}, "error_code": None}
        return {"goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None}

    monkeypatch.setattr(planner_module, "plan_goal", fake_plan_goal)
    _stub_search_ok(monkeypatch, plan=plan, total=1, entities=[_entity(1, "پرواز الف", 100)])

    r1 = client.post("/v1/conversation/message", json={"text": "پرواز تهران استانبول جمعه تا دوشنبه"})
    cid = r1.json()["conversation_id"]

    r2 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "ارزون‌تر"})
    assert r2.json()["action"] == "REFINE_SEARCH"
    assert r2.json()["refined"] is True
    overrides_used = calls[-1]
    assert overrides_used["origin"] == "تهران" and overrides_used["destination"] == "استانبول"
    assert overrides_used["start_date"] == "2026-09-18" and overrides_used["end_date"] == "2026-09-21"


def test_previous_plan_is_rotated_on_refinement(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan_v1 = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
               "departure_date": None, "return_date": None, "party": {"travellers": 2}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": {**plan_v1, **(kw.get("overrides") or {})}, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan_v1, total=1, entities=[_entity(1, "هتل الف", 100)])

    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش برای دو نفر"})
    cid = r1.json()["conversation_id"]
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "برای سه نفر"})
    assert fake_db.conversations[cid]["previous_plan"]["vertical"] == "hotel"
    assert fake_db.conversations[cid]["last_plan"] is not None


# ---- result selection ----

def test_select_result_by_ordinal(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": {"travellers": 2}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=3, entities=[
        _entity(1, "هتل الف", 300), _entity(2, "هتل ب", 150), _entity(3, "هتل ج", 500),
    ])
    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش برای دو نفر"})
    cid = r1.json()["conversation_id"]

    r2 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "دومی رو انتخاب کن"})
    assert r2.json()["action"] == "SELECT_RESULT"
    assert r2.json()["message"]["data"]["selected"]["entity_id"] == "e2"
    assert fake_db.conversations[cid]["selected_result"]["entity_id"] == "e2"
    assert fake_db.conversations[cid]["trip_state_id"] is not None


def test_select_last_result(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": {}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=3, entities=[_entity(1, "الف", 100), _entity(2, "ب", 200), _entity(3, "ج", 300)])
    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش"})
    cid = r1.json()["conversation_id"]
    r2 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "گزینه آخر"})
    assert r2.json()["message"]["data"]["selected"]["entity_id"] == "e3"


def test_reference_without_prior_results_fails_safely(client):
    r = client.post("/v1/conversation/message", json={"text": "دومی رو انتخاب کن"})
    assert r.json()["action"] == "UNSUPPORTED_ACTION"


def test_reference_to_stale_result_set_does_not_guess(client, monkeypatch, fake_db):
    from app import planner as planner_module, resolver as resolver_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": {}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=1, entities=[_entity(1, "الف", 100)])
    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش"})
    cid = r1.json()["conversation_id"]
    monkeypatch.setattr(resolver_module, "result_set_is_fresh", lambda rs, **kw: False)
    r2 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "دومی رو انتخاب کن"})
    assert r2.json()["action"] == "UNSUPPORTED_ACTION"   # no fresh result set -> classifier treats reference as unresolvable


# ---- ask about a result (hallucination safety) ----

def test_ask_about_result_never_fabricates_missing_field(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "flight", "status": "valid", "destination": {"title": "مشهد"}, "origin": {"title": "تهران"},
            "departure_date": None, "return_date": None, "party": {}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=1, entities=[_entity(1, "پرواز الف", 100)])
    r1 = client.post("/v1/conversation/message", json={"text": "پرواز تهران مشهد"})
    cid = r1.json()["conversation_id"]
    r2 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "اولی بار داره؟"})
    assert r2.json()["action"] == "ASK_ABOUT_RESULT"
    assert "در دسترس نیست" in r2.json()["message"]["text"]   # baggage was never asked of Search -- says unavailable, never invents an answer


# ---- trip state / booking prep ----

def test_booking_prep_creates_draft_with_missing_fields(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": {}}   # no rooms/travellers -> missing fields
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=1, entities=[_entity(1, "هتل الف", 100)])
    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش"})
    cid = r1.json()["conversation_id"]
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "اولی رو انتخاب کن"})
    r3 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "رزروش کن"})
    assert r3.json()["action"] == "START_BOOKING_PREP"
    assert r3.json()["message"]["data"]["readiness"]["ready"] is False
    assert "room_count" in r3.json()["message"]["data"]["readiness"]["missing"]
    draft = next(iter(fake_db.booking_drafts.values()))
    assert draft["status"] == "DRAFT"


def test_booking_prep_without_selection_asks_to_select_first(client):
    r = client.post("/v1/conversation/message", json={"text": "رزروش کن"})
    assert r.json()["action"] == "UNSUPPORTED_ACTION" or r.json()["message"]["data"]["type"] == "CLARIFY"


def test_repeated_booking_prep_is_idempotent_no_duplicate(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": {"travellers": 2, "rooms": 1}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=1, entities=[_entity(1, "هتل الف", 100)])
    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش برای دو نفر یک اتاق"})
    cid = r1.json()["conversation_id"]
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "اولی رو انتخاب کن"})
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "رزروش کن"})
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "رزروش کن"})
    assert len(fake_db.booking_drafts) == 1


# ---- hallucination / financial safety ----

def test_book_it_never_performs_real_booking(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": {"travellers": 2, "rooms": 1}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=1, entities=[_entity(1, "هتل الف", 100)])
    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش برای دو نفر یک اتاق"})
    cid = r1.json()["conversation_id"]
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "اولی رو انتخاب کن"})
    r3 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "رزروش کن"})
    # LEVEL_1 draft only -- never a LEVEL_3 booking/payment action
    assert r3.json()["action"] == "START_BOOKING_PREP"
    assert r3.json()["message"]["data"]["draft"]["status"] == "DRAFT"


def test_pay_for_it_is_blocked_no_side_effect(client, fake_db):
    r = client.post("/v1/conversation/message", json={"text": "پولشو پرداخت کن"})
    assert r.json()["action"] == "BLOCKED_FINANCIAL_ACTION"
    assert fake_db.booking_drafts == {}
    assert fake_db.tool_calls and fake_db.tool_calls[-1][1] == "execute_financial_action"


def test_book_and_pay_combined_is_blocked(client):
    r = client.post("/v1/conversation/message", json={"text": "رزروش کن و پولشو بده"})
    assert r.json()["action"] == "BLOCKED_FINANCIAL_ACTION"


# ---- reset ----

def test_reset_clears_active_plan_but_keeps_audit_log(client, monkeypatch, fake_db):
    from app import planner as planner_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": {}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=1, entities=[_entity(1, "الف", 100)])
    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش"})
    cid = r1.json()["conversation_id"]
    audit_before = len(fake_db.audit_log)
    r2 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "از اول"})
    assert r2.json()["action"] == "CANCEL_CURRENT_FLOW"
    assert fake_db.conversations[cid]["last_plan"] is None
    assert fake_db.conversations[cid]["last_result_set"] is None
    assert len(fake_db.audit_log) == audit_before + 1   # reset itself is audited, nothing erased


# ---- resolver / classifier unit tests ----

def test_resolve_ordinal_cheapest():
    from app.resolver import resolve_ordinal
    rs = {"items": [{"display_index": 1, "price": 300}, {"display_index": 2, "price": 150}, {"display_index": 3, "price": 500}]}
    assert resolve_ordinal(rs, -2)["display_index"] == 2


def test_resolve_ordinal_out_of_range_returns_none():
    from app.resolver import resolve_ordinal
    rs = {"items": [{"display_index": 1, "price": 100}]}
    assert resolve_ordinal(rs, 5) is None


def test_classifier_new_vs_refine():
    from app import classifier as c
    assert c.classify("پرواز تهران کیش", has_active_plan=False, has_result_set=False)["action"] == c.NEW_SEARCH
    assert c.classify("ارزون‌تر", has_active_plan=True, has_result_set=False)["action"] == c.REFINE_SEARCH
    assert c.classify("ارزون‌تر", has_active_plan=False, has_result_set=False)["action"] == c.NEW_SEARCH


def test_classifier_select_vs_ask():
    from app import classifier as c
    assert c.classify("دومی رو انتخاب کن", has_active_plan=True, has_result_set=True)["action"] == c.SELECT_RESULT
    assert c.classify("دومی چه ساعتیه؟", has_active_plan=True, has_result_set=True)["action"] == c.ASK_ABOUT_RESULT


def test_get_unknown_conversation_404(client):
    r = client.get(f"/v1/conversation/{uuid.uuid4()}")
    assert r.status_code == 404


# ================= Phase 3: action plan / approval / execution guard =================

def _search_select_prep(client, monkeypatch, *, party):
    """Helper: search -> select 1st result -> booking prep (draft ready)."""
    from app import planner as planner_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": party}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    _stub_search_ok(monkeypatch, plan=plan, total=1, entities=[_entity(1, "هتل الف", 200)])
    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش برای دو نفر یک اتاق"})
    cid = r1.json()["conversation_id"]
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "اولی رو انتخاب کن"})
    r3 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "رزروش کن"})
    return cid, r3


def test_advance_action_without_ready_trip_is_unsupported(client):
    r = client.post("/v1/conversation/message", json={"text": "ادامه بده"})
    assert r.json()["action"] == "UNSUPPORTED_ACTION"


def test_confirm_without_pending_approval_is_unsupported(client, monkeypatch, fake_db):
    cid, r3 = _search_select_prep(client, monkeypatch, party={"travellers": 2, "rooms": 1})
    assert r3.json()["message"]["data"]["readiness"]["ready"] is True
    r4 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "تایید می‌کنم"})
    assert r4.json()["action"] == "UNSUPPORTED_ACTION"   # never inferred -- nothing was proposed yet


def test_full_advance_then_confirm_flow_is_blocked_at_commerce_not_at_approval(client, monkeypatch, fake_db):
    cid, r3 = _search_select_prep(client, monkeypatch, party={"travellers": 2, "rooms": 1})
    assert r3.json()["trip_state_status"] == "READY_FOR_BOOKING_PREP"

    r4 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "ادامه بده"})
    assert r4.json()["action"] == "ADVANCE_ACTION"
    assert r4.json()["message"]["data"]["requires_approval"] is True
    approval_id = r4.json()["message"]["data"]["pending_approval_id"]
    assert fake_db.approvals[approval_id]["status"] == "PENDING"

    r5 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "تایید می‌کنم"})
    assert r5.json()["action"] == "CONFIRM_PENDING_APPROVAL"
    assert fake_db.approvals[approval_id]["status"] == "APPROVED"
    guard = r5.json()["message"]["data"]["execution_guard"]
    assert guard["allowed"] is True   # approval mechanism itself works end-to-end
    # the tool call was attempted and truthfully blocked -- no user_token was
    # forwarded (the normal case in this session), so the REAL handler
    # reports the precise reason rather than simulating success
    assert fake_db.tool_calls[-1][1] == "submit_reservation_hold"
    assert r5.json()["message"]["data"]["reservation_result"]["error_code"] == "USER_AUTHENTICATION_REQUIRED"
    assert "رزرو شد" not in r5.json()["message"]["text"] and "پرداخت شد" not in r5.json()["message"]["text"]


def test_execution_guard_blocks_without_approval(fake_db):
    from app import approval as approval_module
    guard = approval_module.check_execution_guard(
        tool_name="submit_reservation_hold", args={"trip_state_id": "t1", "selected_item": {"entity_id": "e1"}},
        conversation_id="c1", selected_result={"entity_id": "e1"}, result_set=None, readiness=None,
    )
    assert guard["allowed"] is False and guard["reason"] == "APPROVAL_REQUIRED"


def test_execution_guard_blocks_stale_result_set(monkeypatch):
    from app import approval as approval_module, resolver as resolver_module
    monkeypatch.setattr(resolver_module, "result_set_is_fresh", lambda rs, **kw: False)
    guard = approval_module.check_execution_guard(
        tool_name="submit_reservation_hold", args={"trip_state_id": "t1", "selected_item": {"entity_id": "e1"}},
        conversation_id="c1", selected_result={"entity_id": "e1"}, result_set={"items": []}, readiness=None,
    )
    assert guard["allowed"] is False and guard["reason"] == "RESULT_SET_STALE"


def test_execution_guard_blocks_when_not_ready(monkeypatch):
    from app import approval as approval_module
    guard = approval_module.check_execution_guard(
        tool_name="submit_reservation_hold", args={"trip_state_id": "t1", "selected_item": {"entity_id": "e1"}},
        conversation_id="c1", selected_result={"entity_id": "e1"}, result_set=None, readiness={"ready": False, "missing": ["x"]},
    )
    assert guard["allowed"] is False and guard["reason"] == "BOOKING_NOT_READY"


def test_approval_request_is_idempotent(fake_db):
    from app import approval as approval_module
    a1 = approval_module.request_approval("c1", None, "submit_reservation_hold", "fp1")
    a2 = approval_module.request_approval("c1", None, "submit_reservation_hold", "fp1")
    assert a1["id"] == a2["id"]
    assert len(fake_db.approvals) == 1


def test_stale_or_wrong_approval_blocks_execution(fake_db):
    from app import approval as approval_module
    a1 = approval_module.request_approval("c1", None, "submit_reservation_hold", "fp-old")
    # a material parameter change produces a different fingerprint -- the
    # old (still-pending, never approved) approval must never match it
    guard = approval_module.check_execution_guard(
        tool_name="submit_reservation_hold", args={"trip_state_id": "t1", "selected_item": {"entity_id": "e1", "price": 999}},
        conversation_id="c1", selected_result={"entity_id": "e1", "price": 999}, result_set=None, readiness=None,
    )
    assert guard["allowed"] is False and guard["reason"] == "APPROVAL_REQUIRED"


# ---- price/availability revalidation ----

def test_price_revalidation_detects_change():
    from app.resolver import revalidate_price
    selected = {"entity_id": "e1", "price": 100}
    fresh = {"entities": [{"entity_id": "e1", "best_offer": {"final_price": 150, "currency": "IRR", "offer_id": "o1"}}]}
    result = revalidate_price(selected, fresh)
    assert result["changed"] is True and result["old_price"] == 100 and result["new_price"] == 150


def test_price_revalidation_detects_unavailable():
    from app.resolver import revalidate_price
    selected = {"entity_id": "e1", "price": 100}
    fresh = {"entities": []}
    result = revalidate_price(selected, fresh)
    assert result["available"] is False


def test_booking_prep_blocked_when_live_price_changed(client, monkeypatch, fake_db):
    from app import planner as planner_module, tools as tools_module
    plan = {"vertical": "hotel", "status": "valid", "destination": {"title": "کیش"}, "origin": None,
            "departure_date": None, "return_date": None, "party": {"travellers": 2, "rooms": 1}}
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": plan, "error_code": None,
    })
    call_count = {"n": 0}
    def fake_call_tool(name, args):
        if name != "search_travel":
            return tools_module.REGISTRY[name].handler(args), 1.0
        call_count["n"] += 1
        price = 200 if call_count["n"] == 1 else 350   # price changes between selection and booking-prep revalidation
        data = {"executed": True, "result": {"pagination": {"total": 1}, "entities": [_entity(1, "هتل الف", price)], "plan": plan}}
        return tools_module.ToolResult(status="ok", data=data, error_code=None), 3.0
    monkeypatch.setattr(tools_module, "call_tool", fake_call_tool)

    r1 = client.post("/v1/conversation/message", json={"text": "هتل کیش برای دو نفر یک اتاق"})
    cid = r1.json()["conversation_id"]
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "اولی رو انتخاب کن"})
    r3 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "رزروش کن"})
    assert r3.json()["message"]["data"]["type"] == "CLARIFY"
    reval = r3.json()["message"]["data"]["revalidation"]
    assert reval["changed"] is True and reval["old_price"] == 200 and reval["new_price"] == 350
    assert fake_db.booking_drafts == {}   # never created a draft on top of a stale price


# ---- trip state machine ----

def test_invalid_trip_transition_is_rejected(fake_db):
    from app import trip as trip_module
    ts = trip_module.get_or_create("c1", None)
    with pytest.raises(trip_module.InvalidTransition):
        trip_module.transition(ts["id"], trip_module.STATUS_DRAFT, trip_module.STATUS_BOOKED)


def test_valid_trip_transition_succeeds(fake_db):
    from app import trip as trip_module
    ts = trip_module.get_or_create("c1", None)
    new_status = trip_module.transition(ts["id"], trip_module.STATUS_DRAFT, trip_module.STATUS_PLANNING)
    assert new_status == trip_module.STATUS_PLANNING
    assert fake_db.trip_states[ts["id"]]["status"] == trip_module.STATUS_PLANNING


def test_same_status_transition_is_a_safe_noop(fake_db):
    from app import trip as trip_module
    ts = trip_module.get_or_create("c1", None)
    assert trip_module.transition(ts["id"], trip_module.STATUS_DRAFT, trip_module.STATUS_DRAFT) == trip_module.STATUS_DRAFT


# ---- human handoff ----

def test_human_handoff_request(client, fake_db):
    r = client.post("/v1/conversation/message", json={"text": "میخوام با پشتیبان صحبت کنم"})
    assert r.json()["action"] == "REQUEST_HUMAN_HANDOFF"
    assert "escalation" in r.json()["message"]["data"]
    assert r.json()["message"]["data"]["escalation"]["conversation_id"] == r.json()["conversation_id"]


# ---- action plan ----

def test_action_plan_created_on_booking_prep(client, monkeypatch, fake_db):
    cid, r3 = _search_select_prep(client, monkeypatch, party={"travellers": 2, "rooms": 1})
    plans = [p for p in fake_db.action_plans.values() if p["conversation_id"] == cid]
    assert len(plans) == 1
    assert plans[0]["goal"] == "book_hotel"
    assert len(plans[0]["steps"]) == 1
    assert plans[0]["steps"][0]["tool"] == "create_booking_draft"


# ---- hallucination-safety wording check across the module ----

def test_no_forbidden_success_wording_anywhere_in_source():
    import pathlib
    forbidden = ("رزرو شد", "پرداخت شد", "بلیط صادر شد", "کنسل شد", "استرداد شد")
    src_dir = pathlib.Path(__file__).parent.parent / "app"
    for py in src_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        for phrase in forbidden:
            assert phrase not in text, f"forbidden success wording {phrase!r} found in {py.name}"


# ================= Phase 4: real reservation/hold wiring =================

class _FakeHttpResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body)
    def json(self):
        return self._body


class _FakeMonolithClient:
    """Records exactly what was sent so tests can assert the real request
    shape confirmed by reading backend/app/main.py."""
    def __init__(self, responder):
        self.calls = []
        self._responder = responder
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def request(self, method, path, json=None, headers=None):
        self.calls.append({"method": method, "path": path, "json": json, "headers": headers})
        return self._responder(method, path, json, headers)


def test_price_check_offer_without_token_is_blocked():
    from app import tools as tools_module
    result = tools_module.price_check_offer({"offer_id": "o1", "command_id": "cmd12345"})
    assert result.status == "blocked" and result.error_code == "USER_AUTHENTICATION_REQUIRED"


def test_price_check_offer_calls_real_endpoint_shape(monkeypatch):
    from app import tools as tools_module
    fake = _FakeMonolithClient(lambda m, p, j, h: _FakeHttpResponse(201, {"id": "pc1", "amount": 5000000, "currency": "IRR", "expires_at": "2026-01-01T00:00:00Z"}))
    monkeypatch.setattr(tools_module, "_monolith_client", lambda token: fake)
    result = tools_module.price_check_offer({"offer_id": "o1", "command_id": "cmd12345", "units": 2, "user_token": "tok"})
    assert result.status == "ok" and result.data["id"] == "pc1"
    assert fake.calls[0]["method"] == "POST" and fake.calls[0]["path"] == "/offers/o1/price-check"
    assert fake.calls[0]["json"] == {"units": 2, "command_id": "cmd12345"}


def test_submit_reservation_hold_without_price_check_id_is_blocked():
    from app import tools as tools_module
    result = tools_module.submit_reservation_hold({"user_token": "tok", "command_id": "cmd12345"})
    assert result.status == "blocked" and result.error_code == "PRICE_CHECK_REQUIRED"


def test_submit_reservation_hold_calls_real_orchestration_endpoint(monkeypatch):
    from app import tools as tools_module
    fake = _FakeMonolithClient(lambda m, p, j, h: _FakeHttpResponse(201, {"id": "res1", "status": "reserved"}))
    monkeypatch.setattr(tools_module, "_monolith_client", lambda token: fake)
    result = tools_module.submit_reservation_hold({"user_token": "tok", "command_id": "cmd12345", "price_check_id": "pc1"})
    assert result.status == "ok" and result.data["status"] == "reserved"
    assert fake.calls[0]["path"] == "/orchestration/bookings"
    assert fake.calls[0]["json"] == {"price_check_id": "pc1", "command_id": "cmd12345"}


def test_submit_reservation_hold_propagates_real_http_error(monkeypatch):
    from app import tools as tools_module
    fake = _FakeMonolithClient(lambda m, p, j, h: _FakeHttpResponse(409, {"code": "PRICE_CHANGED"}))
    monkeypatch.setattr(tools_module, "_monolith_client", lambda token: fake)
    result = tools_module.submit_reservation_hold({"user_token": "tok", "command_id": "cmd12345", "price_check_id": "pc1"})
    assert result.status == "error" and result.error_code == "HTTP_409"


def test_release_reservation_hold_without_token_is_blocked():
    from app import tools as tools_module
    result = tools_module.release_reservation_hold({"reservation_id": "res1", "idempotency_key": "k1"})
    assert result.status == "blocked" and result.error_code == "USER_AUTHENTICATION_REQUIRED"


def test_release_reservation_hold_calls_real_cancel_endpoint(monkeypatch):
    from app import tools as tools_module
    fake = _FakeMonolithClient(lambda m, p, j, h: _FakeHttpResponse(202, {"reservation_id": "res1", "request_type": "cancel", "status": "submitted"}))
    monkeypatch.setattr(tools_module, "_monolith_client", lambda token: fake)
    result = tools_module.release_reservation_hold({"reservation_id": "res1", "idempotency_key": "k1", "user_token": "tok"})
    assert result.status == "ok"
    assert fake.calls[0]["path"] == "/reservations/res1/service-requests"
    assert fake.calls[0]["json"]["request_type"] == "cancel"
    assert fake.calls[0]["headers"]["Idempotency-Key"] == "k1"


def test_confirm_with_real_user_token_creates_real_reservation_end_to_end(client, monkeypatch, fake_db):
    from app import tools as tools_module
    cid, r3 = _search_select_prep(client, monkeypatch, party={"travellers": 2, "rooms": 1})
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "ادامه بده"})

    fake = _FakeMonolithClient(lambda m, p, j, h: (
        _FakeHttpResponse(201, {"id": "pc1", "amount": 200, "currency": "IRR"}) if "price-check" in p
        else _FakeHttpResponse(201, {"id": "res1", "status": "reserved"})
    ))
    monkeypatch.setattr(tools_module, "_monolith_client", lambda token: fake)

    r5 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "تایید می‌کنم", "user_token": "real-user-jwt"})
    assert r5.json()["message"]["data"]["reservation_result"]["status"] == "ok"
    assert "درخواست رزرو موقت ثبت شد" in r5.json()["message"]["text"]
    assert fake_db.conversations[cid]["selected_result"]["reservation"]["id"] == "res1"
    # both real calls happened in the right order with the right shapes
    assert fake.calls[0]["path"] == "/offers/o1/price-check"
    assert fake.calls[1]["path"] == "/orchestration/bookings" and fake.calls[1]["json"]["price_check_id"] == "pc1"


def test_reset_with_active_reservation_and_token_calls_real_release(client, monkeypatch, fake_db):
    from app import tools as tools_module
    cid, r3 = _search_select_prep(client, monkeypatch, party={"travellers": 2, "rooms": 1})
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "ادامه بده"})
    fake = _FakeMonolithClient(lambda m, p, j, h: (
        _FakeHttpResponse(201, {"id": "pc1"}) if "price-check" in p
        else _FakeHttpResponse(201, {"id": "res1", "status": "reserved"})
    ))
    monkeypatch.setattr(tools_module, "_monolith_client", lambda token: fake)
    client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "تایید می‌کنم", "user_token": "real-user-jwt"})

    fake.calls.clear()
    fake._responder = lambda m, p, j, h: _FakeHttpResponse(202, {"status": "submitted"})
    r6 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "از اول", "user_token": "real-user-jwt"})
    assert r6.json()["message"]["data"]["release_result"]["status"] == "ok"
    assert fake.calls[0]["path"] == "/reservations/res1/service-requests"
    assert fake_db.conversations[cid]["selected_result"] is None   # state cleared after release
