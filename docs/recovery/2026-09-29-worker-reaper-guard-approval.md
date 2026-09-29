# Reviewable worker-only production correction — approval required

Live worker `karenseir-worker-1`, unchanged release d2ba674, periodically exits1:
`psycopg.errors.InsufficientPrivilege: permission denied for table reservations`.
Observed restart count150. Role karenseir_worker is non-superuser/BYPASSRLS;
SELECT and UPDATE reservations are false. This matches the deliberate REVOKE in
`deploy/provision-worker-role.sql`; the unconditional reaper is incompatible with
that security boundary. Do not enlarge the notification worker's DB privileges.

Candidate **4d9f0c3**, branch `fix/worker-reaper-boundary-20260929`, is based on the
actual live d2ba674. Its only application change is outbox_worker.py. It does not
include unpublished Hotel71801f8, enterprise1e6ee5e or migration35. Release checkout:
`/tmp/karen-worker-guard-release`; authoritative parent repository remains
`/home/ubuntu/karenseir-current`. Main candidate includes identical patch7e17fe8.

Image `karenseir-current-api:worker-reaper-guard-4d9f0c3`, exact fingerprint and
file hash in `evidence/worker-reaper-guard/candidate.json`. The reaper now requires
explicit opt-in; proposed rollout sets `RESERVATION_REAPER_ENABLED=0`. Health
reports reaper disabled. Outbox delivery retains the existing role/volumes/settings;
SMS and push remain disabled. This does NOT complete automatic hold expiry.

QA:11 worker/reaper tests on the live-base checkout; built image13 accelerated real
PostgreSQL outbox iterations under a role denied reservation/finance access;
actual isolated HTTPhealth; candidate commit/file hash verified. Promotion script
requires approval before Docker access. Injected health failure restores previous
worker; injected rename failure restarts the original; tests simulate Docker,
not an actual Production rollback. Evidence is in the adjacent verification.json.

## Exact approval requested

Replace **only** karenseir-worker-1 with this image, reaper disabled. Preserve the
old container as `karenseir-worker-1-pre-reaper-guard-4d9f0c3`. No schema migration,
DB grant, reservation expiry, credit, payment, SMS, web/API/search replacement.

Read-only preflight already PASS: `python3 deploy/promote_worker_reaper_guard.py --check-only`.

After explicit approval only:
`python3 deploy/promote_worker_reaper_guard.py --approved`

The script checks source/image identity and disabled external channels, preserves
volumes/environment, verifies HTTPhealth reaper state, and observes210seconds
(longer than the former180second idle crash interval) with zero restarts. It checks
unchanged API/web/search images and rolls back on failure. Prior worker rollback
restores prior behavior, including the known reaper failure; it is not claimed to
cure that original defect. No current rollback/backup has been removed.

Approval origin: AGENTS.md requires explicit confirmation for the specific
Production operation. No Production correction has yet been executed.
