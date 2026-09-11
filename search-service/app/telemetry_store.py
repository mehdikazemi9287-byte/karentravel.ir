"""Search-owned telemetry persistence. A separate database (not a monolith
table) is the ownership boundary: Search can evolve/rotate/prune this data
without any monolith migration. Best-effort -- a telemetry write failure must
never fail or slow a search beyond a short bounded timeout."""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from . import config

_POOL: Optional[Any] = None
_DISABLED = False


def _conn():
    global _POOL, _DISABLED
    if _DISABLED or not config.TELEMETRY_DB_URL:
        return None
    if _POOL is None:
        try:
            import psycopg
            _POOL = psycopg.connect(config.TELEMETRY_DB_URL, connect_timeout=2, autocommit=True)
            _bootstrap(_POOL)
        except Exception:
            _DISABLED = True
            return None
    return _POOL


def _bootstrap(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS search_telemetry (
            id BIGSERIAL PRIMARY KEY,
            correlation_id TEXT NOT NULL,
            ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            verticals TEXT[] NOT NULL,
            public BOOLEAN NOT NULL,
            tenant_ref TEXT,
            result_count INT NOT NULL,
            partial_results BOOLEAN NOT NULL,
            providers_requested INT NOT NULL,
            providers_failed INT NOT NULL,
            elapsed_ms NUMERIC NOT NULL,
            cache TEXT,
            failure_code TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_search_telemetry_ts ON search_telemetry (ts)")
    # Phase 3: additive columns only -- existing rows/readers are unaffected,
    # nullable so a partially-migrated reader/writer pair never breaks.
    for stmt in (
        "ALTER TABLE search_telemetry ADD COLUMN IF NOT EXISTS providers_succeeded INT",
        "ALTER TABLE search_telemetry ADD COLUMN IF NOT EXISTS ranking_version TEXT",
        "ALTER TABLE search_telemetry ADD COLUMN IF NOT EXISTS avg_provider_latency_ms NUMERIC",
    ):
        conn.execute(stmt)


def record(event: dict) -> None:
    """No PII, no user id, no raw query text -- tenant_ref is a slug, not an
    identity claim. Never raises."""
    conn = _conn()
    if conn is None:
        return
    try:
        conn.execute(
            """INSERT INTO search_telemetry
               (correlation_id, verticals, public, tenant_ref, result_count, partial_results,
                providers_requested, providers_failed, elapsed_ms, cache, failure_code,
                providers_succeeded, ranking_version, avg_provider_latency_ms)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (event["correlation_id"], event["verticals"], event["public"], event.get("tenant_ref"),
             event["result_count"], event["partial_results"], event["providers_requested"],
             event["providers_failed"], event["elapsed_ms"], event.get("cache"), event.get("failure_code"),
             event.get("providers_succeeded"), event.get("ranking_version"), event.get("avg_provider_latency_ms")),
        )
    except Exception:
        # a telemetry outage degrades observability, never search itself
        global _POOL
        _POOL = None


def health() -> dict:
    conn = _conn()
    if conn is None:
        return {"backend": "disabled" if not config.TELEMETRY_DB_URL else "unavailable"}
    try:
        conn.execute("SELECT 1")
        return {"backend": "postgres", "ok": True}
    except Exception:
        return {"backend": "postgres", "ok": False}
