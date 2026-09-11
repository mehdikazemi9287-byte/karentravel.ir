"""Assistant Phase A slice tests. DB is faked in-process (a real Postgres
isn't available in this throwaway test container) -- covers goal routing,
tool registry/permission recording, and reply composition end-to-end
through the real HTTP endpoint. Live DB writes are verified separately
against the real deployed karenseir_assistant database."""
import os
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


class _FakeConn:
    """Minimal in-memory stand-in for the handful of fixed queries main.py
    issues. Not a general SQL engine -- pattern-matches on the query text."""
    closed = False

    def __init__(self):
        self.conversations = {}
        self.messages = {}

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("INSERT INTO conversations"):
            cid, public, tenant_ref = params
            self.conversations[cid] = {"id": cid, "public": public, "tenant_ref": tenant_ref, "active_goal": None}
            self.messages[cid] = []
            return _FakeCursor()
        if s.startswith("SELECT id FROM conversations"):
            (cid,) = params
            row = self.conversations.get(cid)
            return _FakeCursor([(row["id"],)] if row else [])
        if s.startswith("INSERT INTO messages"):
            cid, role, text, data = params
            self.messages.setdefault(cid, []).append({"role": role, "text": text, "data": data})
            return _FakeCursor()
        if s.startswith("UPDATE conversations SET updated_at"):
            goal, cid = params
            if cid in self.conversations:
                self.conversations[cid]["active_goal"] = goal
            return _FakeCursor()
        if s.startswith("INSERT INTO tool_calls"):
            return _FakeCursor()
        if s.startswith("SELECT id, public, tenant_ref, active_goal FROM conversations"):
            (cid,) = params
            row = self.conversations.get(cid)
            return _FakeCursor([(row["id"], row["public"], row["tenant_ref"], row["active_goal"])] if row else [])
        if s.startswith("SELECT role, text, data, created_at FROM messages"):
            (cid,) = params
            from datetime import datetime, timezone
            return _FakeCursor([(m["role"], m["text"], m["data"], datetime.now(timezone.utc)) for m in self.messages.get(cid, [])])
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


def test_health_ready(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200


def test_conversation_created_and_persisted(client, fake_db):
    r = client.post("/v1/conversation/message", json={"text": "سلام"})
    assert r.status_code == 200
    cid = r.json()["conversation_id"]
    assert cid in fake_db.conversations
    assert len(fake_db.messages[cid]) == 2   # user + assistant


def test_existing_conversation_id_is_reused(client, fake_db):
    r1 = client.post("/v1/conversation/message", json={"text": "سلام"})
    cid = r1.json()["conversation_id"]
    r2 = client.post("/v1/conversation/message", json={"conversation_id": cid, "text": "دوباره"})
    assert r2.json()["conversation_id"] == cid
    assert len(fake_db.messages[cid]) == 4


def test_search_goal_invokes_search_tool(client, monkeypatch):
    from app import tools as tools_module, planner as planner_module

    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": {"vertical": "hotel", "status": "valid"}, "error_code": None,
    })

    calls = {}
    def fake_call_tool(name, args):
        calls["name"] = name
        calls["args"] = args
        return tools_module.ToolResult(status="ok", data={
            "executed": True, "result": {"pagination": {"total": 3}},
        }, error_code=None), 5.0
    monkeypatch.setattr(tools_module, "call_tool", fake_call_tool)

    r = client.post("/v1/conversation/message", json={"text": "هتل کیش"})
    assert r.status_code == 200
    assert calls["name"] == "search_travel"
    body = r.json()
    assert body["goal"] == "search"
    assert body["message"]["data"]["type"] == "SEARCH_RESULT_CARD"
    assert body["message"]["data"]["total"] == 3


def test_search_tool_failure_never_fabricates_a_result(client, monkeypatch):
    from app import tools as tools_module, planner as planner_module
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": {"vertical": "flight", "status": "valid"}, "error_code": None,
    })
    monkeypatch.setattr(tools_module, "call_tool", lambda name, args: (
        tools_module.ToolResult(status="error", data={}, error_code="SEARCH_UNREACHABLE:ConnectError"), 2.0,
    ))
    r = client.post("/v1/conversation/message", json={"text": "پرواز تهران مشهد"})
    body = r.json()
    assert body["message"]["data"]["type"] == "SEARCH_ERROR"
    assert body["message"]["data"]["error_code"] == "SEARCH_UNREACHABLE:ConnectError"


def test_ambiguous_goal_asks_for_clarification(client, monkeypatch):
    from app import planner as planner_module
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_CLARIFY,
        "plan": {"ambiguities": [{"code": "missing_route_direction", "message": "مبدا و مقصد مشخص نیست"}]},
        "error_code": None,
    })
    r = client.post("/v1/conversation/message", json={"text": "تهران مشهد"})
    assert r.json()["message"]["data"]["type"] == "CLARIFY"
    assert "مبدا و مقصد" in r.json()["message"]["text"]


def test_unsupported_goal_never_calls_search_tool(client, monkeypatch):
    from app import tools as tools_module, planner as planner_module
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_UNSUPPORTED,
        "plan": {"ambiguities": [{"code": "unsupported_intent", "message": "پشتیبانی نمی‌شود"}]},
        "error_code": None,
    })
    def boom(name, args):
        raise AssertionError("unsupported goal must never call a tool")
    monkeypatch.setattr(tools_module, "call_tool", boom)
    r = client.post("/v1/conversation/message", json={"text": "رستوران تهران"})
    assert r.json()["message"]["data"]["type"] == "UNSUPPORTED"


def test_tool_permission_level_recorded(client, monkeypatch):
    from app import tools as tools_module, planner as planner_module
    monkeypatch.setattr(planner_module, "plan_goal", lambda text, **kw: {
        "goal": planner_module.GOAL_SEARCH, "plan": {"vertical": "hotel", "status": "valid"}, "error_code": None,
    })
    assert tools_module.REGISTRY["search_travel"].permission_level == tools_module.LEVEL_READ
    assert tools_module.LEVEL_READ <= tools_module.AUTO_EXECUTE_MAX_LEVEL   # read tools auto-execute, no confirmation


def test_get_conversation_returns_history(client, fake_db):
    r1 = client.post("/v1/conversation/message", json={"text": "سلام"})
    cid = r1.json()["conversation_id"]
    r2 = client.get(f"/v1/conversation/{cid}")
    assert r2.status_code == 200
    assert len(r2.json()["messages"]) == 2


def test_get_unknown_conversation_404(client):
    r = client.get(f"/v1/conversation/{uuid.uuid4()}")
    assert r.status_code == 404
