# Enterprise / finance / gift Source checkpoint — 2026-09-28

Target: Source and isolated Preview/QA. Production is unchanged: deployed 5a714cb,
API/worker e4bace796f3f, web 6809c6a51d6e. Existing rollback containers are preserved.
Baseline Source aeac353; implementation committed as 01adfcb. User-owned backend/debug_voucher.py is excluded.

## Implemented increment
- Nine request use cases; persisted requirements, frozen policy version/outcomes,
  ordered approval decisions and audit/outbox events; no fake reservation.
- Explicit organization membership and configurable capability grants. Requesters
  see their own requests; approvers and travel desk require scoped permissions.
- Supplier invitations, redacted requirements, immutable quote revisions, expiry
  and latest-revision selection checks. Selected quote is not a contract/payment.
- Bulk employee benefit campaign DRAFT with membership validation, immutable proposed
  allocation snapshot, server-calculated total, dates/services/restrictions/message.
  No funding, issued credit, delivery or redemption token is created.
- /organization/requests Preview UI: request form/list/history, policy configuration,
  approval action, campaign creation/list. Employee portal links to this workspace.
  Original Homepage/Search design is untouched.

## Actual QA
- Targeted API/DB tests: four tests passed cumulatively. Initial request/policy/
  approval and campaign tests passed; RFQ test expected 403 for an uninvited supplier,
  corrected to actual privacy-preserving 404, then RFQ passed. After total-limit
  guard change the affected campaign test passed again (1 passed, 3 deselected).
- Clean Docker Next build passed. Workspace tsc found stale generated .next/dev
  export constraints in the pre-existing app/page; clean build passed its type gate.
- Real Chromium, desktop 1440 and mobile 390: request → persisted list → refresh →
  manager decision; employee cannot see campaign form; manager creates bulk draft,
  server total displayed. No pageerror or horizontal overflow, HTML RTL.
- PostgreSQL isolated database: upgrade 33→34, seven FORCE RLS tables, tenant and
  missing-context SELECT isolation; isolated downgrade→upgrade passed.
- No test touched production data, sent SMS or performed a financial transaction.
- Browser screenshots remain /tmp/karen-operational-e2e/enterprise-{1440,390}.png;
  interaction/bounds checks passed. Visual screenshot inspection tool was blocked
  by sandbox helper, so no separate perceptual review is claimed.
- Old 42/42 and 25/25 suites were not repeated.

## Release boundary / reviewable operation
Production actual Alembic revision read-only check: 20260922_33.
Pending migration: 20260928_34; seven additive tables, no existing table alteration.
Pending release must apply migration before routing to new API/UI. No automatic
schema creation on Production is authorized by this checkpoint.

After specific approval: take a recoverable production DB backup, apply exactly
`alembic upgrade 20260928_34` using the candidate code and migration role, verify
revision/RLS, switch API/worker/web to candidate images, check changed authenticated
routes with no test data insertion and service health. Retain all old containers.
Rollback restores old application images; retain additive tables and their audit
records. Do not execute a production downgrade/drop. New routes must not be published
before the migration and matching API are in place.

## Explicit unfinished internal work
This is not the full enterprise, finance or gift engine. Full matrix is ADR-023.
Still required: subsidiary/branch/project hierarchy; richer fare/grade/policy and
conditional approval rules; travel desk RFQ browser UI; request→reservation binding;
recurring/group rooming/guest workflow; funded campaign issuance, consumer gifting,
secure claim/redeem/expiry/revocation; wallet/ledger atomic funding linkage and split
refunds; facility/receivable/payable/settlement infrastructure; HR and scoped finance
reports; assistant structured campaign/group handoff. Do not label these external.

Only actual external dependencies remain DNS/TLS, supplier contract/credentials,
ZarinPal and Kavenegar. Approved financial policy is additionally required before
real liability activation; absent policy does not justify inventing balances.
Jabama business URL retrieval failed; no unobserved competitor claims were made.

Next: obtain specific approval for additive migration/release of this tested increment;
continue remaining internal enterprise/finance/gift implementation with isolated QA.

Candidate web image: karenseir-current-web:enterprise-preview-20260928 (9f458b8601bb); source delta fingerprint aeac353d1c85ce0846e5f1bd7b58662fa547fff6-worktree-56bb81f6ce5f. Backend candidate: karenseir-current-api:enterprise-01adfcb. Five live services were read-only checked healthy; seven prior rollback containers still exist. Local compile initially could not write a cache owned by another user; rerun with PYTHONPYCACHEPREFIX under /tmp passed without permission changes.
Final candidate QA: rebuilt backend image b495c4ad774a3837ec7d0e2493783ac71d8fc0c27e1c83c40ac68b54634ebf35; all four targeted tests passed against the candidate image's own /app code (only tests mounted, isolated SQLite/media, no network). This repeat was required to validate the newly built runtime dependencies. Candidate web and backend are prepared, not deployed. Documentation/evidence links and git diff whitespace checks passed.
