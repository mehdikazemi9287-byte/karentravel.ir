"""Load catalog files into the catalog_* tables (additive, idempotent upsert).

Source ownership: a row is only written by the source that created it. Hotels edited in the admin
panel (updated_by set) are never touched. Rows absent from the input are kept; removal needs the
explicit --prune flag and is still limited to unedited rows of the sources present in the input.

Run with a role that may write the catalog tables (the API role only has SELECT):
  DATABASE_URL=... python scripts/catalog/import_catalog.py [catalog_data_dir] [--dry-run]
Never touches tenant, offer, price or booking tables.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import delete, insert, select, update  # noqa: E402

from app.catalog import CATALOG_MODELS  # noqa: E402
from app.database import SessionLocal  # noqa: E402

ORDER = ["places", "hotels", "airlines", "airports", "rail_operators", "rail_stations", "venues"]
KIND_RANK = {"country": 0, "region": 1, "city": 2}


def main(data_dir: str, dry_run: bool, prune: bool = False) -> dict:
    report = {}
    with SessionLocal() as db:
        for name in ORDER:
            model = CATALOG_MODELS[name]
            columns = {c.name for c in model.__table__.columns}
            with gzip.open(Path(data_dir) / f"{name}.json.gz", "rt", encoding="utf-8") as fh:
                rows = [{k: v for k, v in row.items() if k in columns} for row in json.load(fh)]
            limits = {c.name: c.type.length for c in model.__table__.columns if getattr(c.type, "length", None)}
            for row in rows:  # sources are free text: keep values inside column limits; an over-long URL is dropped, not cut
                for key, limit in limits.items():
                    value = row.get(key)
                    if isinstance(value, str) and len(value) > limit:
                        row[key] = None if key.endswith(("_url", "website")) else value[:limit]
                if "image_url" in row and not row["image_url"]:
                    row["image_credit"] = None
            if name == "places":  # parents before children for the self-reference
                rows.sort(key=lambda r: KIND_RANK[r["kind"]])
            sources = {r.get("source") or "" for r in rows}
            owned = select(model.id).where(model.source.in_(sources))
            if hasattr(model, "updated_by"):
                owned = owned.where(model.updated_by.is_(None))
            existing = set(db.scalars(owned))
            foreign = set(db.scalars(select(model.id))) - existing  # other source or admin-owned: never written here
            skipped = [r for r in rows if r["id"] in foreign]
            rows = [r for r in rows if r["id"] not in foreign]
            incoming = {r["id"] for r in rows}
            if len(incoming) != len(rows):
                raise SystemExit(f"{name}: duplicate ids in data file")
            new = [r for r in rows if r["id"] not in existing]
            current = {r.id: r for r in db.scalars(select(model).where(model.id.in_(existing & incoming)))} if existing & incoming else {}
            # An empty incoming value never erases a stored one: another source or a reviewer may have completed it.
            kept = lambda r: {k: v for k, v in r.items() if not (v is None and getattr(current[r["id"]], k) is not None)}  # noqa: E731
            changed = [kept(r) for r in rows if r["id"] in existing and any(getattr(current[r["id"]], k) != v for k, v in kept(r).items())]
            db.expunge_all()
            stale = (existing - incoming) if prune else set()
            report[name] = {"inserted": len(new), "updated": len(changed), "removed": len(stale), "kept_absent": len(existing - incoming) - len(stale), "protected_skipped": len(skipped)}
            if dry_run:
                continue
            for i in range(0, len(new), 1000):
                db.execute(insert(model), new[i:i + 1000])
            for i in range(0, len(changed), 1000):
                db.execute(update(model), changed[i:i + 1000])
            if stale:
                ids = sorted(stale)
                for i in range(0, len(ids), 500):
                    db.execute(delete(model).where(model.id.in_(ids[i:i + 500])))
            db.flush()
        if not dry_run:
            db.commit()
    print(json.dumps({"dry_run": dry_run, **report}))
    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else str(Path(__file__).resolve().parents[2] / "catalog_data"), "--dry-run" in sys.argv, "--prune" in sys.argv)
