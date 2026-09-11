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

    # Phase 2: additive columns -- existing rows/readers unaffected.
    for stmt in (
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS previous_plan JSONB",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS last_result_set JSONB",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS selected_result JSONB",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS trip_state_id UUID",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS pending_clarification JSONB",
        "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ACTIVE'",
    ):
        c.execute(stmt)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trip_states (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status TEXT NOT NULL DEFAULT 'DRAFT',
            destination_context JSONB,
            origin_context JSONB,
            travelers JSONB,
            outbound JSONB,
            "return" JSONB,
            transport_preferences JSONB,
            stay_preferences JSONB,
            budget_preferences JSONB,
            selected_transport JSONB,
            selected_accommodation JSONB,
            selected_experience JSONB,
            unresolved_items JSONB,
            booking_readiness JSONB
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS booking_drafts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            trip_state_id UUID NOT NULL REFERENCES trip_states(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            vertical TEXT NOT NULL,
            selected_offer_ref JSONB,
            traveler_requirements JSONB,
            missing_fields JSONB,
            price_snapshot_reference JSONB,
            search_request_reference JSONB,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            idempotency_key TEXT NOT NULL,
            UNIQUE (trip_state_id, idempotency_key)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id BIGSERIAL PRIMARY KEY,
            conversation_id UUID NOT NULL,
            turn_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            action TEXT NOT NULL,
            tool TEXT,
            input_reference JSONB,
            output_reference JSONB,
            state_before_hash TEXT,
            state_after_hash TEXT,
            result TEXT NOT NULL,
            error_code TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_trip_states_conv ON trip_states (conversation_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_booking_drafts_trip ON booking_drafts (trip_state_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_conv ON audit_log (conversation_id, created_at)")


def health() -> dict:
    try:
        conn().execute("SELECT 1")
        return {"backend": "postgres", "ok": True}
    except Exception as exc:
        global _POOL
        _POOL = None
        return {"backend": "postgres", "ok": False, "detail": type(exc).__name__}
