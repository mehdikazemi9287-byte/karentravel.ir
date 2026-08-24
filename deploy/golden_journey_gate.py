#!/usr/bin/env python3
"""Golden Journey Gate - Control Layer 4.

A release is not DONE because tests pass. It is DONE only when the single
canonical real-user journey works on the SAME PUBLIC URL a user opens:

  Homepage -> Search -> Results -> Compare/Recheck -> Booking -> Funding
  -> Payment -> Confirmation -> My Trips -> Timeline -> Cancellation/Support
  -> Notification

This gate does two things, both read-only, both safe to run against
production with no account and no credentials:

  1. A handful of unauthenticated live HTTP reachability checks against the
     real public URL (is the site actually up, not just "does main.py import").
  2. Walks the golden-journey steps against CAPABILITY_REGISTRY.json (the
     one authoritative capability-truth source) and computes a verdict.

Verdict is one of:
  PASS            - every step is LIVE (or PARTIAL, which warns but does
                     not block - a partial step is still usable).
  BLOCKED_EXTERNAL - the first non-usable step is blocked on a missing
                     external credential/dependency, not a code defect.
  FAIL_INTERNAL   - the first non-usable step is BROKEN, DEMO, or
                     NOT_STARTED - a real internal defect.

This script never fabricates a PASS. If CAPABILITY_REGISTRY.json is
missing or malformed, or a step maps to no known capability, the gate
fails closed (FAIL_INTERNAL), it does not default to PASS.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_BASE = "http://95.38.184.209"
API_BASE = "http://95.38.184.209:8000"

# Ordered golden-journey steps -> the capability_registry keys that gate them.
# A step is as good as the WORST-ranked capability among its keys.
STEPS = [
    ("search", ["search_core"]),
    ("results", ["search_core"]),
    ("compare_recheck", ["compare", "authoritative_recheck"]),
    ("booking", ["booking"]),
    ("funding", ["wallet", "organization_credit", "installments"]),
    ("payment", ["payment_gateway"]),
    ("confirmation", ["booking", "invoice"]),
    ("my_trips", ["my_trips"]),
    ("timeline", ["trip_timeline"]),
    ("cancellation_support", ["cancellation_refund", "human_support"]),
    ("notification", ["in_app_notifications"]),
]

# Worse is later. LIVE/PARTIAL never block the gate by themselves.
RANK = {"LIVE": 0, "PARTIAL": 1, "READY_BLOCKED_EXTERNAL": 2, "DEMO": 3, "NOT_STARTED": 3, "BROKEN": 3}
BLOCKING = {"READY_BLOCKED_EXTERNAL", "DEMO", "NOT_STARTED", "BROKEN"}


def http_check(url: str, timeout: float = 5.0) -> dict:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"url": url, "status": resp.status, "ok": 200 <= resp.status < 400}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": exc.code, "ok": False}
    except Exception as exc:
        return {"url": url, "status": None, "ok": False, "error": str(exc)}


def load_registry() -> dict | None:
    path = REPO_ROOT / "CAPABILITY_REGISTRY.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["capabilities"]
    except Exception:
        return None


def worst(keys: list[str], registry: dict) -> tuple[str, str | None, str | None]:
    worst_status, worst_key, worst_blocker = "LIVE", None, None
    for key in keys:
        entry = registry.get(key)
        if entry is None:
            return "UNKNOWN", key, "capability not found in registry"
        status = entry.get("status", "UNKNOWN")
        if RANK.get(status, 3) > RANK.get(worst_status, 0):
            worst_status, worst_key, worst_blocker = status, key, entry.get("blocker")
    return worst_status, worst_key, worst_blocker


def main() -> int:
    live_checks = [
        http_check(f"{PUBLIC_BASE}/"),
        http_check(f"{PUBLIC_BASE}/search/results"),
        http_check(f"{API_BASE}/health"),
    ]

    registry = load_registry()
    result = {"live_reachability": live_checks}

    if registry is None:
        result.update({"verdict": "FAIL_INTERNAL", "first_break": None, "reason": "CAPABILITY_REGISTRY.json missing or malformed - gate fails closed, never defaults to PASS"})
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    if not all(c["ok"] for c in live_checks):
        failed = [c["url"] for c in live_checks if not c["ok"]]
        result.update({"verdict": "FAIL_INTERNAL", "first_break": "live_reachability", "reason": f"public site unreachable at: {failed}"})
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    steps_evaluated = []
    verdict, first_break, reason = "PASS", None, None
    for step_name, keys in STEPS:
        status, key, blocker = worst(keys, registry)
        steps_evaluated.append({"step": step_name, "status": status, "capability": key})
        if verdict == "PASS" and status in BLOCKING:
            first_break = step_name
            if status == "READY_BLOCKED_EXTERNAL":
                verdict = "BLOCKED_EXTERNAL"
                reason = blocker or f"{key} is READY_BLOCKED_EXTERNAL"
            else:
                verdict = "FAIL_INTERNAL"
                reason = f"{key} is {status}"
        if verdict == "PASS" and status == "UNKNOWN":
            first_break = step_name
            verdict = "FAIL_INTERNAL"
            reason = f"{key}: capability not found in registry"

    result.update({"steps": steps_evaluated, "verdict": verdict, "first_break": first_break, "reason": reason})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if verdict != "FAIL_INTERNAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
