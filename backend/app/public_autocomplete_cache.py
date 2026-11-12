"""Bounded cache for public geography suggestions only; never tenant/price data."""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Callable


class PublicAutocompleteCache:
    def __init__(self, redis_client=None, *, ttl: int = 300, capacity: int = 256, clock=time.monotonic):
        self.redis = redis_client
        self.ttl, self.capacity, self.clock = ttl, capacity, clock
        self._local: OrderedDict[str, tuple[float, list]] = OrderedDict()
        self._lock = threading.Lock()
        self._retry_after = 0.0

    def get(self, normalized: str, catalog_version: str, compute: Callable[[], list]) -> list:
        key = "karenseir:public-geo:v1:" + hashlib.sha256((catalog_version + "\0" + normalized).encode()).hexdigest()
        now = self.clock()
        with self._lock:
            item = self._local.get(key)
            if item and item[0] > now:
                self._local.move_to_end(key)
                return copy.deepcopy(item[1])
            self._local.pop(key, None)
        result = None
        # A Redis outage must not repeatedly add a network timeout to every keystroke.
        if self.redis is not None and now >= self._retry_after:
            try:
                value = self.redis.get(key)
                if value is not None:
                    decoded = json.loads(value)
                    ttl_left = self.redis.ttl(key)
                    if isinstance(decoded, list) and all(isinstance(x, dict) for x in decoded) and ttl_left > 0:
                        self._remember(key, decoded, now + min(ttl_left, self.ttl))
                        return copy.deepcopy(decoded)
            except Exception:
                self._retry_after = now + 30
        result = compute()
        if self.redis is not None and now >= self._retry_after:
            try:
                self.redis.setex(key, self.ttl, json.dumps(result, ensure_ascii=False))
            except Exception:
                self._retry_after = now + 30
        self._remember(key, result, self.clock() + self.ttl)
        return copy.deepcopy(result)

    def _remember(self, key: str, value: list, expiry: float) -> None:
        with self._lock:
            self._local[key] = (expiry, copy.deepcopy(value))
            self._local.move_to_end(key)
            while len(self._local) > self.capacity:
                self._local.popitem(last=False)


def configured_cache(redis_url: str) -> PublicAutocompleteCache:
    if not redis_url:
        return PublicAutocompleteCache()
    from redis import Redis
    return PublicAutocompleteCache(Redis.from_url(redis_url, decode_responses=True,
        socket_connect_timeout=0.15, socket_timeout=0.15))
