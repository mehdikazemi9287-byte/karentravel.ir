# CheckLine hotel content — candidate (2026-10-06)

Branch `feat/checkline-hotel-catalog-20261006` (worktree `~/ks-checkline-work/src`). Production untouched: still d2ba674 images, DB at alembic `20260928_34`.

## What changed vs. the catalog candidate (ADR-028)
- Migration `20261006_37` (on `20261003_36`): hotel policies, publication `status`, admin ownership (`updated_by/updated_at`), `stars_status`, nullable coordinates; tables `catalog_hotel_images` (licence mandatory) and `catalog_hotel_room_types` (descriptive only). No price/availability/inventory column anywhere.
- ADR-028 addendum: the API role may write hotel content, only through `/admin/catalog/*` (platform_admin, backoffice_expert), each save audited. It still cannot delete hotels or write any other catalog table.
- `import_catalog.py` is additive: absent rows are kept (`--prune` is explicit and still source-scoped), other-source and admin-edited hotels are never written, unchanged rows are not rewritten.
- `import_checkline.py`: staged CheckLine hotels become `draft` rows `cl-<legacy id>`; unknown stays NULL; nothing published automatically.

## Candidate evidence (throwaway DB `ks_cand37` in `ks-catalog-scratch-pg`)
- upgrade 36→37 and downgrade 37→36 on a copy: column fingerprint identical before/after, 19,268 hotels intact.
- downgrade refuses while CheckLine/admin hotels exist (no silent data loss).
- CheckLine: 722 input → 511 drafts, 211 quarantined (country absent from master catalog), 213 of the 511 without an exact city match (city left NULL). Second run: 0 inserted / 0 updated.
- OSM re-import (full, repeated, and a 100-row partial input): 0 removed, 0 rewritten, admin-edited rows skipped.
- Sample: ibis Yerevan Center enriched on the existing OSM record through the admin API (official Accor page + 4 Wikimedia Commons images with author/licence). CheckLine holds this hotel twice (7779, 18825); both stay drafts.

## Production rollout (NOT executed — needs explicit approval)
1. `pg_dump -Fc` of production, verify with `pg_restore -l`.
2. Deploy API image built from this branch; `alembic upgrade head` (34 → 37; 35 and 36 are also not yet applied in production).
3. Load master catalog (`import_catalog.py`), then `import_checkline.py <staged dir>`.
4. Rollback: remove `source in (checkline, karenseir)` hotels and hotels without coordinates, `alembic downgrade 20261003_36` (or restore the dump), redeploy previous images.
