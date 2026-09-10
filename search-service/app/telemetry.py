from __future__ import annotations

import json
import logging
import sys
import time
from threading import Lock

_lock = Lock()
COUNTERS = {
    "search_requests": 0, "search_zero_result": 0, "search_partial": 0, "search_errors": 0,
    "provider_timeouts": 0, "provider_unavailable": 0, "cache_hit": 0, "cache_miss": 0,
    "autocomplete_requests": 0,
}
DURATIONS: list[float] = []

logger = logging.getLogger("karenseir.search")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)


def incr(name: str, n: int = 1) -> None:
    with _lock:
        COUNTERS[name] = COUNTERS.get(name, 0) + n


def observe_duration(ms: float) -> None:
    with _lock:
        DURATIONS.append(ms)
        if len(DURATIONS) > 500:
            del DURATIONS[: len(DURATIONS) - 500]


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({"ts": time.time(), "event": event, **fields}, ensure_ascii=False))


def snapshot() -> dict:
    with _lock:
        d = sorted(DURATIONS)
        pct = lambda p: d[min(len(d) - 1, int(len(d) * p))] if d else 0.0
        return {
            "counters": dict(COUNTERS),
            "duration_ms": {"count": len(d), "p50": round(pct(0.5), 2), "p95": round(pct(0.95), 2), "max": round(d[-1], 2) if d else 0.0},
        }
