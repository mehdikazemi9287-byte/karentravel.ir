"""Cache abstraction. Redis when configured; a bounded in-memory TTL map as a
non-critical fallback. A cache miss NEVER produces a result -- callers refetch."""
from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any, Optional

from . import config


class _InMemory:
    def __init__(self, max_entries: int = 2000) -> None:
        self._d: dict[str, tuple[float, str]] = {}
        self._max = max_entries
        self._lock = Lock()
        self.backend = "memory"

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            row = self._d.get(key)
            if not row:
                return None
            exp, payload = row
            if exp < time.time():
                self._d.pop(key, None)
                return None
            return json.loads(payload)

    def set(self, key: str, value: Any, ttl: int) -> None:
        with self._lock:
            if len(self._d) >= self._max:
                now = time.time()
                for k in [k for k, (e, _) in self._d.items() if e < now][: self._max // 4]:
                    self._d.pop(k, None)
                if len(self._d) >= self._max:
                    self._d.pop(next(iter(self._d)), None)
            self._d[key] = (time.time() + ttl, json.dumps(value))

    def ping(self) -> bool:
        return True


class _Redis:
    def __init__(self, url: str) -> None:
        import redis  # type: ignore
        self._r = redis.Redis.from_url(url, socket_timeout=1.5, socket_connect_timeout=1.5)
        self.backend = "redis"

    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            self._r.setex(key, ttl, json.dumps(value))
        except Exception:
            pass

    def ping(self) -> bool:
        try:
            return bool(self._r.ping())
        except Exception:
            return False


def build_cache():
    if config.REDIS_URL:
        try:
            c = _Redis(config.REDIS_URL)
            if c.ping():
                return c
        except Exception:
            pass
    return _InMemory()


CACHE = build_cache()
