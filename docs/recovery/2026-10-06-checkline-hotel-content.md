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

## Update 2026-10-07 — migration 38, state, matching, reference places (candidate only)
- Chain audit on a throwaway restore of the production dump: 34 → 35 → 36 → 37 → 38 applied, then 38 → 34 reverted; column fingerprint identical to the start, bookings/users row counts unchanged. API role after upgrade: SELECT/INSERT/UPDATE on hotels, no DELETE.
- Every hotel now reports `state` = catalogued / content_complete / rate_available / bookable / published / source / last_verified_at. `rate_available` and `bookable` are false for all hotels: no live rate source is connected; `catalog_hotel_provider_mappings` (admin-entered, unverified by default) is the only future entry point.
- Reference places added by the CheckLine import, with provenance: 14 countries (`source=iso3166-1`, ISO code as ref) and 36 cities (`source=checkline`, `geography/<id>`), no coordinates. Tehran, Kish and Qeshm were absent from the OSM-derived catalog.
- CheckLine: 706 of 722 imported as drafts (was 511); 56 without a city (51 Turkey rows have no city in the source); 16 preserved in staging only (7 without a country, 9 country/city conflicts).
- Duplicates: 53 pairs found by exact name within the same city. 3 also share address number + distinctive word and are linked automatically (`duplicate_of`, never public, never deleted); 50 are `proposed` and wait for a reviewer in the panel (confirm = link + fill empty fields of the canonical record; reject is remembered across re-imports).
- Public UI: baseline 682f5eb vs candidate, 11 pages x desktop/mobile, byte-identical screenshots. The policy filter is URL/API-only until it has an approved design.
- Admin panel QA (Playwright, 26 checks x desktop/mobile): all pass.

### Production rollout — additional gate found
This branch sits on 791d007 plus the uncommitted homepage/catalog work, while production runs d2ba674. Deploying the web image from this branch would also replace the live homepage and other customer pages. Decide between (a) full release of this branch, or (b) API + migrations + data only, leaving the current web image, in which case `/admin/catalog` and the public catalog pages are not reachable from the live site yet.
Rollback for 38: `alembic downgrade 20261006_37` (drops match pairs / provider mappings and the four state columns), then the 37 procedure above.
