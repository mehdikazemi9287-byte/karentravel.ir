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

CACHE_KEY_VERSION = "v2"


def search_cache_key(payload: dict) -> str:
    envelope = {"cache_key_version": CACHE_KEY_VERSION, "ranking_version": RANKING_VERSION, **payload}
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f"kss:{CACHE_KEY_VERSION}:{digest}"


def autocomplete_cache_key(q: str, limit: int) -> str:
    return f"kss:ac:{CACHE_KEY_VERSION}:{limit}:{q}"
