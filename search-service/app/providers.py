"""Provider adapter layer.

The only wired data source today is the monolith offer pool (internal supplier
inventory). Real external carriers/bedbanks are declared as ports with explicit
capabilities and fail closed -- they never fabricate inventory or a successful
response. A failed provider degrades to a truthful partial result, it does not
fail the whole search.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

import httpx

from . import config
from .domain import PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE


@dataclass(frozen=True)
class ProviderError:
    """Normalized provider error -- every adapter (present or future) reports
    through this shape so the engine never has to understand provider-specific
    exceptions."""
    code: str                      # PROVIDER_TIMEOUT | PROVIDER_UNAVAILABLE | ...
    provider: str
    vertical: str
    correlation_id: str
    retryable: bool = False
    detail: str = ""


@dataclass(frozen=True)
class ProviderCapabilities:
    search: bool = True
    recheck: bool = False
    reserve: bool = False          # reservation stays in the commerce domain regardless
    fuzzy_match: bool = False
    geo: bool = False


class SearchProviderPort(Protocol):
    key: str
    verticals: tuple[str, ...]
    connected: bool

    def status(self) -> dict[str, Any]: ...
    def fetch(self, vertical: str, req) -> list[dict]: ...   # returns raw offer rows


class _DisabledExternalProvider:
    """Fail-closed real-provider port. No credentials/contract -> not_connected,
    empty pool, never an invented offer."""

    def __init__(self, key: str, verticals: tuple[str, ...]) -> None:
        self.key = key
        self.verticals = verticals
        self.connected = False
        self.capabilities = ProviderCapabilities(search=False)

    def status(self) -> dict[str, Any]:
        return {"provider": self.key, "status": "not_connected",
                "detail": "No authorized external provider connection.", "offer_count": 0,
                "capabilities": self.capabilities.__dict__}

    def fetch(self, vertical: str, req) -> list[dict]:
        return []


DisabledFlightProvider = _DisabledExternalProvider("flight_carrier", ("flight",))
DisabledHotelProvider = _DisabledExternalProvider("hotel_bedbank", ("hotel",))
DisabledRailProvider = _DisabledExternalProvider("rail_carrier", ("train",))
DisabledBusProvider = _DisabledExternalProvider("bus_carrier", ("bus",))

EXTERNAL_PROVIDERS = (DisabledFlightProvider, DisabledHotelProvider, DisabledRailProvider, DisabledBusProvider)


class OfferPoolProvider:
    """Wired: pulls the real internal supplier offer pool for a vertical from the
    monolith (single owner of the DB + tenant identity)."""

    key = "karenseir_supplier_pool"
    verticals = tuple()          # serves any vertical
    connected = True

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=config.MONOLITH_BASE_URL, timeout=config.PROVIDER_TIMEOUT_SECONDS)

    def status(self) -> dict[str, Any]:
        try:
            r = self._client.get("/health", timeout=2.0)
            ok = r.status_code == 200
        except Exception:
            ok = False
        return {"provider": self.key, "status": "available" if ok else "unavailable", "offer_count": 0}

    def fetch(self, vertical: str, req) -> list[dict]:
        payload = {"service_type": vertical, "public": req.public}
        if req.tenant_ref:
            payload["tenant_ref"] = req.tenant_ref
        headers = {"X-Internal-Token": config.INTERNAL_TOKEN, "X-Correlation-ID": req.correlation_id}
        r = self._client.post("/internal/search/offer-pool", json=payload, headers=headers)
        if r.status_code == 503:
            raise RuntimeError("offer_pool_unavailable")
        r.raise_for_status()
        body = r.json()
        return body.get("offers", [])


_POOL = OfferPoolProvider()


def fan_out(req) -> tuple[dict[str, list[dict]], list[dict]]:
    """Bounded-concurrency provider fan-out with per-provider + total timeout.
    Returns (pools_by_vertical, provider_diagnostics)."""
    pools: dict[str, list[dict]] = {}
    meta: list[dict] = []
    deadline = time.monotonic() + config.TOTAL_TIMEOUT_SECONDS

    tasks = [(v, _POOL) for v in req.verticals]
    with ThreadPoolExecutor(max_workers=min(config.MAX_CONCURRENCY, max(1, len(tasks)))) as ex:
        futures = {ex.submit(p.fetch, v, req): (v, p) for v, p in tasks}
        for fut, (v, p) in list(futures.items()):
            remaining = max(0.1, deadline - time.monotonic())
            try:
                rows = fut.result(timeout=min(config.PROVIDER_TIMEOUT_SECONDS, remaining))
                pools[v] = rows
                meta.append({"provider": p.key, "status": "available", "offer_count": len(rows), "vertical": v})
            except FutureTimeout:
                fut.cancel()
                pools.setdefault(v, [])
                meta.append({"provider": p.key, "status": PROVIDER_TIMEOUT, "offer_count": 0, "vertical": v})
            except Exception:
                pools.setdefault(v, [])
                meta.append({"provider": p.key, "status": PROVIDER_UNAVAILABLE, "offer_count": 0, "vertical": v})

    # external carrier ports -- declared, fail-closed, reported truthfully
    for prov in EXTERNAL_PROVIDERS:
        for v in req.verticals:
            if not prov.verticals or v in prov.verticals:
                meta.append(prov.status() | {"vertical": v})
    return pools, meta
