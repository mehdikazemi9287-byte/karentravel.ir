# Release readiness continuation — 2026-10-08

Target: Source and isolated tests only; Production unchanged. Baseline a2ccf37, clean working tree. Backend app matches candidate bind-mounted run/app. Existing design is locked; new visual pages or sections require Figma first.

Initial delta: 30 tests passed; one outdated customer payment fixture uses awaiting_payment without an existing intent. The API correctly rejects it with 409; the fixture must use reserved for initial intent creation. Preserve payment guard and tenant ownership assertions. Synthetic data runs only in a separate /tmp SQLite database.

User PDF contains only a title page; substantive proposals remain unavailable. Historical QA requires scoped verification. Commercial credentials and public TLS require verification before a release verdict.

Expanded isolated gate: 54 passed, 2 failed before corrections. The cross-tenant search test incorrectly required an empty tenant, although other tests may create that tenant own offers. Replace with exclusion of the specific foreign offer plus direct price-check denial (409: generic unavailable-offer contract). No production guard or UI changes.

Confirmed source bug: organization statement totals aggregate only the latest 500 returned invoice rows. Correct aggregate totals across the complete tenant-scoped organization set while retaining the bounded item list and the existing UI. Regression: >500 invoices, multiple currencies, and a different organization excluded. Figma detailed role page 129:11966 has 104 native frames and Vazirmatn only; homepage untouched. CheckLine reference used for tenant/financial ownership boundaries.

Statement regression + organization panel: 2 passed in isolated source snapshot. Remaining suite diagnosis: test CORS origin must be configured explicitly for the isolated runner; public discovery tests must scope their missing-tenant condition without relying on test order; payment fixture pending_payment is obsolete (initial payment requires reserved); hotel itinerary recheck without occupancy correctly reports DETAILS_REQUIRED. Preserve all negative assertions and retry/price-change coverage.

Final delta from CheckLine role/audit requirements: organization creation and actual membership additions/removals must write actor-scoped organizational and tenant audit events in the same transaction. Duplicate add and refused cross-tenant access must not produce successful mutation events. No schema migration; three Persian event labels in the existing audit screen, specified in Figma first.

BLOCKER verified on actual Production metadata: licensed_entities, supplier_memberships, sales_channels, price_breakdowns, reconciliation_records have neither enabled nor forced RLS and no policies. Isolated PostgreSQL gates: 20 passed, 1 failed (complete coverage). Prepare migration 20261008_47 for only these five existing tenant tables. No rows are deleted or rewritten. Production application requires explicit approval for this concrete schema hardening. Migration downgrade retains policies, so rollback cannot silently reopen tenant access. Existing API/worker release-guard head compatibility must be tested and prepared before operational approval.

Additional panel delta: agency reports/customer counts/commissions/settlements must not inherit the bookings display limit (500). Stream complete scoped records for aggregates; keep bounded visible booking/commission items. Legacy agency dashboard/update/create-parent routes must respect AgencyMembership (same-tenant object isolation), and new agencies must atomically record creator membership. Supplier settlement amounts must be grouped by currency; mixed currencies never produce a pretend IRR total. Figma supplier overview note was updated before the corresponding text-only hint change. Production still unchanged; RLS approval pending.

## Final verified checkpoint (work started 2026-10-08)
- SOURCE HEAD a2ccf37 plus the explicitly recorded local delta; no commit/push.
- Figma panel page 129:11966: 104 native frames for 52 sections, 9 reusable components; Vazirmatn; selected screenshots and responsive bounds reviewed. This is not a claim of exhaustive pixel parity for every screen.
- Current final source full suite: 460 passed, 7 environment-specific skipped; all 7 covered in the dedicated PostgreSQL/Redis gate.
- Fresh PostgreSQL 16, real NOBYPASSRLS API role: 34 passed (RLS, worker permission, identity lookup, rate limiting, concurrent room capacity, organization totals/audit, same-tenant agency scope, >500 booking totals, >200 settlement totals, mixed currencies).
- Existing candidate signed-in panel E2E: 20 desktop + 20 tablet + 20 mobile passed.
- Final immutable frontend/backend image browser delta: 18 passed, including non-empty separate IRR/USD display. Test harness redirects the baked production API address to synthetic qa_final; it does not prove signed-in Production QA.
- API runtime files and migration inside final image exactly match source SHA256 values.
- Migration 47 was applied only to isolated QA. 106/106 tenant tables FORCE RLS. Downgrade/re-upgrade tested without dropping the protection.
- Final API and compatible rollback images were tested in Production mode against synthetic storage. Latest immutable images, hashes, original container IDs and backup are in panel-release-20261008/release-manifest.json.
- Production API/Web/Worker/DB IDs unchanged; DB revision still 20261015_46; / and /health returned 200.
- Protected homepage files/CSS unchanged. Only existing panel financial text/data and three audit labels changed; no homepage redesign.
- Six interim containers created by this chat removed after evidence capture. Keep final private QA API/Web and isolated PG/Redis until the release decision.
- Kavenegar is configured (special adapter path); do not infer OTP absence from the generic mode field. Live SMS delivery was NOT_RUN.
- Merchant/payment and generic hotel/flight modes are disabled. DNS/TLS, real rate/provider certification, public commercial readiness and separate connector evidence remain external gates.

## Required next action
Wait for the human response explicitly approving Production migration 47 on the five named tables. Do not infer approval from a checkpoint, flag, silence or generic goal.
Once approved, recheck baseline IDs and exact immutable digests, run the prepared deployment script with the approval flag, then do current Production smoke and affected role QA. API/Frontend only; no worker restart, DB container replacement, seed, delete or restore-overwrite.
The rollback uses compatible old API code with migration-47 metadata; protection remains enabled.
The global product is NOT marked commercially releasable until public domain/TLS and live commercial integration evidence are resolved.
