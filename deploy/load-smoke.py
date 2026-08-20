from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from urllib.parse import urlparse

import httpx


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8200/hotels")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--p95-ms", type=float, default=500)
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if not args.allow_remote and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("remote load requires --allow-remote")
    if not 1 <= args.concurrency <= 200 or not 1 <= args.requests <= 100_000:
        raise SystemExit("unsafe load parameters")
    semaphore = asyncio.Semaphore(args.concurrency)
    latencies: list[float] = []
    errors = 0

    async with httpx.AsyncClient(timeout=5) as client:
        async def one() -> None:
            nonlocal errors
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(args.url)
                    if response.status_code >= 400:
                        errors += 1
                except Exception:
                    errors += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)
        await asyncio.gather(*(one() for _ in range(args.requests)))
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(f"requests={len(ordered)} errors={errors} p50_ms={statistics.median(ordered):.2f} p95_ms={p95:.2f} max_ms={max(ordered):.2f}")
    return 0 if errors == 0 and p95 <= args.p95_ms else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
