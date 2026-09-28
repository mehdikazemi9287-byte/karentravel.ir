"""Cache key construction -- audited (Phase 3 Step 10) to fold in every
result-changing dimension of a search:

  verticals, normalized query/origin/destination, travellers, flexibility,
  sort, filters (incl. check_in/check_out dates), page/page_size,
  include_stale, public vs tenant_ref (authenticated context), plus the
  cache-key schema version and the ranking version.

`public`/`tenant_ref` are ordinary hashed fields of the payload, so a public
request and an authenticated (tenant-scoped) request for the same query
always land on different keys -- they can never collide, and two different
tenants always land on different keys. `ranking_version` is folded in so a
ranking change invalidates old cached entries instead of serving a stale
scoring shape under a new algorithm. Locale/currency are not modeled yet
(the service has none) and are intentionally omitted rather than faked.

The cache is an optimization only: every code path here is also exercised on
a cache miss, and Redis/in-memory failures are swallowed by cache.py -- a
cache outage degrades to slower search, never incorrect or missing search."""
from __future__ import annotations

import hashlib
import json

from .ranking import RANKING_VERSION

CACHE_KEY_VERSION = "v3-leisure-day"


def search_cache_key(payload: dict) -> str:
    envelope = {"cache_key_version": CACHE_KEY_VERSION, "ranking_version": RANKING_VERSION, **payload}
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f"kss:{CACHE_KEY_VERSION}:{digest}"


def autocomplete_cache_key(q: str, limit: int) -> str:
    return f"kss:ac:{CACHE_KEY_VERSION}:{limit}:{q}"


def query_plan_cache_key(payload: dict, planner_version: str, provider_set: tuple[str, ...] = ()) -> str:
    """Phase 4: for the natural-language /v1/query/search execution path.
    Keyed from the canonical, already-resolved SearchPlan fields (vertical,
    origin/destination entity ids, date_range, party, filters, public,
    tenant_ref) rather than the raw query wording, so spacing/digit-format
    variants that resolve to the same plan share a cache entry. Folds in
    planner_version (on top of cache_key_version + ranking_version) so a
    planner change invalidates stale cached plans/results instead of
    silently reusing an incompatible shape. public/tenant_ref remain
    ordinary hashed fields -- the same collision-proof pattern as
    search_cache_key, so tenant isolation holds here identically.

    Phase 5: also folds in provider_set (the sorted keys of currently
    CONNECTED providers) -- when a provider comes online/offline the set of
    entities a query can return changes, so a stale cached result from a
    different provider composition must never be served."""
    envelope = {
        "cache_key_version": CACHE_KEY_VERSION, "ranking_version": RANKING_VERSION,
        "planner_version": planner_version, "provider_set": sorted(provider_set), **payload,
    }
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f"kss:qp:{CACHE_KEY_VERSION}:{digest}"
