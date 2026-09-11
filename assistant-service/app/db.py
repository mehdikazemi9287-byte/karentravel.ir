"""Assistant-owned persistence -- a separate database (karenseir_assistant),
not a monolith table, same ownership-boundary pattern already established
for Search's telemetry DB. Unlike telemetry (best-effort), conversation
state is the actual product state: a write failure here is a real error
returned to the caller, never silently swallowed."""
from __future__ import annotations

from typing import Any, Optional

from . import config

_POOL: Optional[Any] = None


def conn():
    global _POOL
    if _POOL is None or _POOL.closed:
        import psycopg
        _POOL = psycopg.connect(config.DB_URL, connect_timeout=3, autocommit=True)
        _bootstrap(_POOL)
    return _POOL


def _bootstrap(c) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            public BOOLEAN NOT NULL,
            tenant_ref TEXT,
            active_goal TEXT,
            last_plan JSONB
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            conversation_id UUID NOT NULL REFERENCES conversations(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            data JSONB
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tool_calls (
            id BIGSERIAL PRIMARY KEY,
            conversation_id UUID NOT NULL REFERENCES conversations(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            tool TEXT NOT NULL,
            permission_level INT NOT NULL,
            status TEXT NOT NULL,
            latency_ms NUMERIC,
            error_code TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_messages_conv ON messages (conversation_id, created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_tool_calls_conv ON tool_calls (conversation_id, created_at)")


def health() -> dict:
    try:
        conn().execute("SELECT 1")
        return {"backend": "postgres", "ok": True}
    except Exception as exc:
        global _POOL
        _POOL = None
        return {"backend": "postgres", "ok": False, "detail": type(exc).__name__}
