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

        if s.startswith("INSERT INTO trip_states"):
            tid, cid, status = params
            self.trip_states[tid] = {"id": tid, "conversation_id": cid, "status": status}
            return _FakeCursor()

        if s.startswith("UPDATE trip_states SET selected_transport") or s.startswith("UPDATE trip_states SET selected_accommodation"):
            val, status, tid = params
            if tid in self.trip_states:
                self.trip_states[tid]["status"] = status
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
