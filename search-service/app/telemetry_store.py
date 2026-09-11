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
    # Phase 4: Query Intelligence telemetry -- a separate table (not columns
    # bolted onto search_telemetry) since a /query/plan call has no search
    # result to report. No raw query text is stored -- only derived,
    # non-identifying signals (intent, confidence, counts).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_plan_telemetry (
            id BIGSERIAL PRIMARY KEY,
            correlation_id TEXT NOT NULL,
            ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            planner_version TEXT NOT NULL,
            intent TEXT[],
            vertical TEXT,
            confidence TEXT NOT NULL,
            plan_status TEXT NOT NULL,
            plan_valid BOOLEAN NOT NULL,
            multi_intent BOOLEAN NOT NULL,
            ambiguity_count INT NOT NULL,
            unsupported_constraint_count INT NOT NULL,
            planning_latency_ms NUMERIC NOT NULL,
            executed BOOLEAN NOT NULL,
            public BOOLEAN NOT NULL,
            tenant_ref TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_query_plan_telemetry_ts ON query_plan_telemetry (ts)")
    # Phase 5: explainability counts -- additive, nullable.
    for stmt in (
        "ALTER TABLE search_telemetry ADD COLUMN IF NOT EXISTS raw_offer_count INT",
        "ALTER TABLE search_telemetry ADD COLUMN IF NOT EXISTS normalized_offer_count INT",
        "ALTER TABLE search_telemetry ADD COLUMN IF NOT EXISTS offer_dedup_removed INT",
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
                providers_succeeded, ranking_version, avg_provider_latency_ms,
                raw_offer_count, normalized_offer_count, offer_dedup_removed)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (event["correlation_id"], event["verticals"], event["public"], event.get("tenant_ref"),
             event["result_count"], event["partial_results"], event["providers_requested"],
             event["providers_failed"], event["elapsed_ms"], event.get("cache"), event.get("failure_code"),
             event.get("providers_succeeded"), event.get("ranking_version"), event.get("avg_provider_latency_ms"),
             event.get("raw_offer_count"), event.get("normalized_offer_count"), event.get("offer_dedup_removed")),
        )
    except Exception:
        # a telemetry outage degrades observability, never search itself
        global _POOL
        _POOL = None


def record_plan(event: dict) -> None:
    """Best-effort, like record() -- a telemetry outage never fails or slows
    query planning. No raw query text; only derived signals."""
    conn = _conn()
    if conn is None:
        return
    try:
        conn.execute(
            """INSERT INTO query_plan_telemetry
               (correlation_id, planner_version, intent, vertical, confidence, plan_status, plan_valid,
                multi_intent, ambiguity_count, unsupported_constraint_count, planning_latency_ms,
                executed, public, tenant_ref)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (event["correlation_id"], event["planner_version"], list(event.get("intent") or []),
             event.get("vertical"), event["confidence"], event["plan_status"], event["plan_valid"],
             event["multi_intent"], event["ambiguity_count"], event["unsupported_constraint_count"],
             event["planning_latency_ms"], event["executed"], event["public"], event.get("tenant_ref")),
        )
    except Exception:
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
