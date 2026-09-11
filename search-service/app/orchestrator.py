"""Central Search Orchestrator (Phase 3).

The only place that sequences the pipeline:

    request (validated by main.py's SearchIn)
      -> SearchRequest (the SearchContext established at the Phase 2 monolith
         gateway boundary: tenant_ref/public resolved server-side, never a
         raw client claim -- see backend/app/main.py::_search_service_call)
      -> eligible providers (registry.py, per requested vertical)
      -> bounded-concurrency provider fan-out (providers.py::fan_out), each
         provider's failure isolated to its own result slot
      -> normalization / dedup / ranking / filtering / pagination
         (engine.py::assemble, backed by dedup.py + ranking.py)
      -> result, or a fail-closed signal if every eligible connected
         provider failed

Endpoint handlers in main.py stay thin: HTTP parsing, cache lookup/write, and
telemetry emission are their concern, not pipeline sequencing.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from . import engine
from .domain import PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE
from .providers import fan_out


def fan_out_and_assemble(req) -> tuple[Optional[dict[str, Any]], list[dict], float]:
    """Runs fan-out then, unless every eligible connected provider failed,
    assembles the final response. Returns (result, provider_meta, elapsed_ms).

    result is None exactly when every provider that actually attempted a
    fetch (status in {available, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE}) came
    back non-available -- the caller (main.py) must fail closed with an
    explicit 503 PROVIDER_UNAVAILABLE in that case, never a fabricated
    zero-result. Declared-but-disabled external providers (status
    not_connected) never count toward this check -- they never attempted a
    fetch in the first place, so their truthful absence is not a "failure"."""
    started = time.perf_counter()
    pools, meta = fan_out(req)

    attempted = [m for m in meta if m["status"] in ("available", PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE)]
    total_failure = bool(attempted) and all(m["status"] != "available" for m in attempted)
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    if total_failure:
        return None, meta, elapsed

    result = engine.assemble(req, pools, meta, elapsed)
    return result, meta, elapsed
