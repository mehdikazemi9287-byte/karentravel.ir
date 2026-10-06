# Release record — catalog backend only (2026-10-06 UTC)

Authorized scope: Backend/API + migrations 35→38 + reference/master/catalog data. Frontend not part of the release.

| Item | Before | After |
|---|---|---|
| API image | `karenseir-current-api:visible-slice18-saved-selection` (d2ba674) | `karenseir-current-api:catalog-backend-352684d` |
| Frontend container | `karenseir-current-web:visible-slice18-saved-selection` | same container id, same start time (not recreated) |
| Worker | `worker-reaper-guard-4d9f0c3` | untouched (it has no schema guard; additive schema) |
| alembic | `20260928_34` | `20261007_38` |

## Gates that ran before any production write
1. Fresh `pg_dump -Fc` + container inspect + image ids → `~/backups/release-catalog-backend-20261006T1528Z/` (a second dump, `prod-karenseir-final.dump`, was taken immediately before the migration).
2. Contract gate on two identical throwaway restores of that dump: old image vs new image, 226 operations — none removed, no parameter or body field made required; 1,366 live request comparisons across every role present in production (GET of every parameterless route, guard behaviour of every write route, booking create/replay/invalid) → 0 differences.
3. Browser gate: the current production frontend image driven against the old and the new API — same API calls, same statuses, no JS errors; 33/34 page screenshots identical, the 34th is a static homepage image that had not finished loading (text identical, reproduced as load timing).
4. Trial start of the new image in production mode with the exact production environment, no published port → healthy.

## Result
- Migrations 35, 36, 37, 38 applied in order by a one-off owner-role container.
- Master catalog: 2,273 places, 19,268 hotels, 72 airlines, 174 airports, 3 rail operators, 224 stations, 13,317 venues inserted; 0 removed.
- CheckLine: 706 hotels as drafts, 14 countries and 36 cities added with provenance; re-run 0 inserted / 0 updated.
- Post-deploy: 174 anonymous route results identical to the pre-deploy snapshot; 36 live pages (18 × desktop/mobile) text-identical, 35 pixel-identical (the differing one also differs between two pre-deploy runs); users/bookings/tenants row counts unchanged.

## Rollback (not needed so far)
`~/ks-checkline-work/rollback.sh`: stops the new API, removes only release-created catalog rows that block downgrade 37, `alembic downgrade 20260928_34`, renames `karenseir-api-1-prev-d2ba674` (kept, stopped) back and starts it. The 38→34 path was rehearsed on restores of the production dump (schema identical). Alternative: restore `prod-karenseir-final.dump`.

## Notes for the next release
- In production `karenseir_api` has DELETE on `catalog_hotels` and write on `catalog_places` (it did not on the candidate): production's default privileges grant the API role DML on every new table. No API code path deletes catalog rows; tightening is a one-line REVOKE and needs its own approval.
- The candidate branch is now ahead of production by migration `20261008_39` (reference tour catalog) and the rate port.
