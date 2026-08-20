from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after: int


class RateLimiter(Protocol):
    distributed: bool
    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision: ...
    async def ping(self) -> bool: ...


class InMemoryRateLimiter:
    distributed = False

    def __init__(self) -> None:
        self._windows: dict[str, tuple[int, int]] = {}

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = int(time.time())
        window = now // window_seconds
        count_window, count = self._windows.get(key, (window, 0))
        count = count + 1 if count_window == window else 1
        self._windows[key] = (window, count)
        retry_after = window_seconds - (now % window_seconds)
        return RateLimitDecision(count <= limit, max(limit - count, 0), retry_after)

    async def ping(self) -> bool:
        return True


class RedisRateLimiter:
    distributed = True
    _SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""

    def __init__(self, client=None, *, url: Optional[str] = None) -> None:
        self._client = client
        self._url = url

    @property
    def client(self):
        if self._client is None:
            from redis.asyncio import Redis
            self._client = Redis.from_url(self._url, encoding="utf-8", decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        return self._client

    @classmethod
    def from_url(cls, url: str):
        return cls(url=url)

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        count, ttl = await self.client.eval(self._SCRIPT, 1, key, window_seconds)
        count, ttl = int(count), max(int(ttl), 1)
        return RateLimitDecision(count <= limit, max(limit - count, 0), ttl)

    async def ping(self) -> bool:
        return bool(await self.client.ping())


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
