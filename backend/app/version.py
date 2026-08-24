from __future__ import annotations

import json
import os

BUILD_INFO_PATH = os.getenv("BUILD_INFO_PATH", "/app/build_info.json")

_UNKNOWN = {"git_commit": "unknown", "build_timestamp_utc": "unknown"}


def read_build_info() -> dict:
    """Read build-time provenance baked into the image by the Dockerfile.

    Returns the documented 'unknown' defaults when the file is absent (e.g.
    local/dev runs not built via the production Dockerfile). Never raises -
    a missing/corrupt build_info.json must never crash the service, it must
    just make the deployment fingerprint honestly report 'unknown'.
    """
    try:
        with open(BUILD_INFO_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return dict(_UNKNOWN)
    return {
        "git_commit": data.get("git_commit") or "unknown",
        "build_timestamp_utc": data.get("build_timestamp_utc") or "unknown",
    }
