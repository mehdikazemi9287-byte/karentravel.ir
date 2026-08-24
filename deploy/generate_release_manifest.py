#!/usr/bin/env python3
"""Generate RELEASE_MANIFEST.json from REAL, freshly-inspected deployment state.

This replaces hand-authored manifests. It never trusts a previous manifest's
claims; every field is re-derived from git, the live Docker containers, and
the live production database at run time.

provenance_complete is true ONLY when every required field is present AND
the git commit baked into each running container's build_info.json matches
the current repository HEAD. A missing field or a commit mismatch must
always produce provenance_complete = false - this script has no code path
that sets it true any other way.

Usage (run on the deployment host, as the same user that manages the
containers):
    python3 deploy/generate_release_manifest.py [--write]

Without --write, prints the manifest to stdout only (dry run).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_CONTAINER = "karenseir-frontend-1"
API_CONTAINER = "karenseir-api-1"
DB_CONTAINER = "karenseir-db-1"
DB_NAME = "karenseir"
DB_USER = "karenseir"


def run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=15, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def git_commit() -> str | None:
    return run(["git", "rev-parse", "HEAD"])


def source_checksum() -> str | None:
    tree = run(["git", "ls-tree", "-r", "HEAD"])
    if tree is None:
        return None
    return hashlib.sha256(tree.encode("utf-8")).hexdigest()


def container_image_id(container: str) -> str | None:
    return run(["docker", "inspect", "--format", "{{.Image}}", container])


def container_env(container: str, key: str) -> str | None:
    envs = run(["docker", "inspect", "--format", "{{json .Config.Env}}", container])
    if not envs:
        return None
    try:
        for entry in json.loads(envs):
            if entry.startswith(key + "="):
                return entry.split("=", 1)[1]
    except json.JSONDecodeError:
        return None
    return None


def container_build_info(container: str, path: str) -> dict:
    out = run(["docker", "exec", container, "cat", path])
    if not out:
        return {"git_commit": None, "build_timestamp_utc": None}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"git_commit": None, "build_timestamp_utc": None}
    return {"git_commit": data.get("git_commit"), "build_timestamp_utc": data.get("build_timestamp_utc")}


def migration_head() -> str | None:
    out = run(["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-tAc", "select version_num from alembic_version;"])
    return out or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write RELEASE_MANIFEST.json (default: dry run, stdout only)")
    args = parser.parse_args()

    commit = git_commit()
    checksum = source_checksum()

    frontend_image = container_image_id(FRONTEND_CONTAINER)
    api_image = container_image_id(API_CONTAINER)
    frontend_build = container_build_info(FRONTEND_CONTAINER, "/app/public/build_info.json")
    api_build = container_build_info(API_CONTAINER, "/app/build_info.json")
    head = migration_head()
    environment = container_env(API_CONTAINER, "ENVIRONMENT")

    frontend_matches_source = bool(commit) and frontend_build["git_commit"] == commit
    api_matches_source = bool(commit) and api_build["git_commit"] == commit

    required = [commit, checksum, frontend_image, api_image, head]
    provenance_complete = all(required) and frontend_matches_source and api_matches_source

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "deploy/generate_release_manifest.py",
        "source_checksum_algorithm": "sha256-of-git-ls-tree",
        "source_checksum": checksum,
        "git_commit": commit,
        "migration_head": head,
        "environment": environment,
        "frontend": {
            "container": FRONTEND_CONTAINER,
            "image_id": frontend_image,
            "build_git_commit": frontend_build["git_commit"],
            "build_timestamp_utc": frontend_build["build_timestamp_utc"],
            "matches_source_commit": frontend_matches_source,
        },
        "api": {
            "container": API_CONTAINER,
            "image_id": api_image,
            "build_git_commit": api_build["git_commit"],
            "build_timestamp_utc": api_build["build_timestamp_utc"],
            "matches_source_commit": api_matches_source,
        },
        "provenance_complete": provenance_complete,
        "provenance_incomplete_reasons": [] if provenance_complete else [
            name for name, value in {
                "git_commit missing": not commit,
                "source_checksum missing": not checksum,
                "frontend image_id missing": not frontend_image,
                "api image_id missing": not api_image,
                "migration_head missing": not head,
                "frontend build_info.json missing or commit mismatch (image predates this fingerprint mechanism, or was not rebuilt after a source change)": not frontend_matches_source,
                "api build_info.json missing or commit mismatch (image predates this fingerprint mechanism, or was not rebuilt after a source change)": not api_matches_source,
            }.items() if value
        ],
    }

    print(json.dumps(manifest, indent=2, ensure_ascii=False))

    if args.write:
        (REPO_ROOT / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("\nwrote RELEASE_MANIFEST.json", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
