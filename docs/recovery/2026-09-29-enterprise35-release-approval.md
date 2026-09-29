# Reviewable release — enterprise request booking tracking

SOURCE/PREVIEW package `1e6ee5e` is ready; PRODUCTION remains `d2ba674`, schema `20260928_34`. The four core services are healthy. Existing rollbacks and user debug_voucher.py preserved. No real financial/SMS operation.

## Change and acceptance
Approved request → requester's existing owned reservation of a requested service → organization status/reference visibility → customer voucher/Trip timeline. This is tracking, not organization funding authorization, creation of a booking, delegated booking or guaranteed fulfillment of group requirements. Dates/travellers require user reconciliation; >20-person request is not silently reduced to a smaller individual search.

New tenant-scoped `enterprise_booking_links` table has FK and unique tenant/reservation constraint. Assigned request viewers cannot impersonate customer or open their voucher/payment APIs. Mutations require the active member/requester, an approved request and owned compatible nonterminal booking. Exact replay and duplicate link create one link/event. Existing contracts/policies/prices/credit remain unchanged.

SQLite targeted API1 PASS, PostgreSQL targeted API1 PASS. PostgreSQL isolated 34→35→34→35 PASS; RLS enabled/forced, actual non-superuser own-row visibility, other/unscoped isolation and cross-tenant update denial PASS. Initial missing Trip destination argument fixed before package; test fixture's unrelated existing reservation assertion corrected. Initial PostgreSQL fixture lacked historical identity resolver; provisioned existing migration17 helper only in disposable DB, then test passed.

Browser1440/390: actual requester form→manager approval→search criteria→existing issued isolated reservation→lost link response/refresh/same-command recovery→customer voucher CTA→manager status without customer link→single audit→Trip timeline PASS. No new payment. Initial harness exact select labels and requests-list URL corrected. Customer mobile and manager desktop screenshots reviewed. Evidence: `evidence/major-enterprise-link-19`.

## Immutable candidate
- Frontend `karenseir-current-web:visible-slice19-enterprise-link`, SHA `85884d44cd100fe97165e6125374f7e881b37106b170a397f4058733efe10dae`.
- API/worker `karenseir-current-api:visible-slice19-enterprise-link`, SHA `f24bb074a8c559cf793f88fbfe83ccb9c5cb88e545a091e81f5cdeb448597599`.
- Both application source commit `1e6ee5e`; documentation-only follow-up commit does not change package.
- Migration `backend/alembic/versions/20260929_35_enterprise_booking_links.py`, parent34, creates only the new link table/RLS/grants. No destructive Production downgrade is proposed.

## Explicit approval required before execution
AGENTS.md requires explicit approval for the particular Production migration. Requested operation: backup/restore-proof → migration35 → candidate API/worker/frontend release → targeted public identity/health and changed-route check. No real SMS/payment/credit.

1. Confirm current public d2ba674, core images d27e90f03dc9/73dc3430edb6, schema34 and no concurrent source/runtime changes.
2. Take a fresh custom-format `pg_dump` from `karenseir-db-1` into a restricted backup file; retain current backups. Verify checksum/archive and restore to disposable isolated PostgreSQL before migration. Never print secrets or expose backup publicly.
3. Preserve current Web/API/worker containers and images. Run only `alembic upgrade 20260929_35` with the candidate API and protected current DB configuration. Stop on any failure. Transactional DDL failure must leave34; verify explicitly.
4. Promote candidate API/worker then Web; preserve old containers. Verify `/ready`, core health, migration35, candidate public `/build_info.json`, and changed organization route. No live fixture or financial action.
5. On health failure, restore old binaries/containers and retain additive schema35 (old runtime does not reference the new table). Do not drop the table or restore over new live data without explicit approval. Failed transactional migration: leave old runtime and confirm34. Keep prior rollback generations.

Public verification of candidate has NOT occurred; candidate is Preview only. Broader P0/P1, public selling entitlement and four external integration boundaries remain open.
