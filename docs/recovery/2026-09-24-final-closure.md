# Final closure delta — 2026-09-24

Source baseline: 6494d96; deployed application 975608f; recovered Web image retained as rollback. Existing recovery documentation edits and untracked backend/debug_voucher.py preserved.

Supervisor gate: ALLOW Source/Preview auth-only fix. Verified deployed image was built from exact application HEAD. No DB/API/Worker changes. Existing B2C tenant is karenseir-consumer. Browser evidence: /login organization field required and empty, registration links=0. This prevents ordinary consumers from completing login without internal knowledge.

Decision: default public login to the existing consumer tenant, keep an explicit organization-login option, provide a registration link preserving the destination, and navigate successful default login to /account. No visual redesign or auth backend changes.
Acceptance: browser register/OTP/profile/logout/login with isolated capturing OTP adapter, consumer role/tenant assertions, organization input retained, same-origin redirect preserved, desktop/mobile bounds, existing backend tests. Production SMS/payment are never simulated as real delivery/success.
Rollback: recover with karenseir-current-web:recovery-975608f-http and its preserved container if a frontend release fails smoke.
Status: Source/Preview E2E closure PASS as of 2026-09-25; see final checkpoint below. These pending changes have not been deployed.

Additional confirmed auth gap: logout API/context existed but no customer-facing logout control was present. Expose that existing action in the account header; no new authentication mechanism.

Checkout handoff defect: successful /payments/{id}/initiate response only set a notice and never followed redirect_url. Fix the existing action to navigate only to a valid HTTPS URL returned by the backend; invalid responses fail closed. Verify with an intercepted provider destination, never a real purchase.


## QA continuation — Source/Preview

- Source HEAD: `6494d96a822212d3b06c27cdf13579b651cda3da`. Committed application files match deployed `975608f`; intervening commits change recovery documentation only. Existing frontend edits remain local.
- Read-only runtime proof: `/build_info.json` reports `975608f5c683bbcc63392fb865c0f90d4ad99122`, timestamp `2026-09-24T14:27:00Z`. Running Web image: `sha256:b2fab9f4f9c74c23ea012482b86ee9a30267eb40cb655d16e5bf8ce67fb80a1b`.
- Clean Docker production build, including TypeScript, PASS. QA image: `karenseir-web-qa:closure-6494d96`, ID `sha256:f1af327bbed8c3021139390b81750b3fa840d2a6e1d00050325c36059b81a3a1`. It contains pending worktree changes and uses loopback QA API/site settings; it is not a public deployment candidate. First build exited 143; only the successful retry is counted.
- Targeted ESLint PASS for the three changed frontend files and both auth/payment test files.
- Playwright: **7 passed** against the built image at `127.0.0.1:3311`: consumer tenant/registration handoff, organization login/challenge reset, HTTPS payment navigation, and rejection of HTTP/javascript/malformed/missing redirect values. API responses and the HTTPS destination are explicitly Mock; no real payment or provider request occurred.
- Reproduce with the isolated config `/tmp/karen-closure-continue.config.ts`; build log `/tmp/karen-closure-build-continue.log`; browser log `/tmp/karen-closure-continue-tests.log`. Test sources: `e2e/public-auth.spec.ts`, `e2e/payment-handoff.spec.ts`.
- Prior isolated `/tmp/karen-closure-e2e/auth.log` records registration, captured OTP, account, logout, consumer login and desktop/mobile bounds passing. This was not repeated and does not establish live SMS delivery. Its script asserts customer role but does not explicitly assert tenant identity.
- Limitations retained: prior workspace typecheck failed in `.next/dev/types` on the `Shell` export; clean build success does not prove that development check is fixed. Prior backend run: 313 passed / 9 failed. Asset retest: 14 passed / 1 failed (`test_content_type_mismatch_denied`, invalid PNG accepted with 201 instead of 422). No unrelated backend fix or full-project QA pass is claimed.
- Production, DB, API, worker and infrastructure configuration unchanged. QA Preview is loopback-only and uses no production Docker network. All pre-existing edits and `backend/debug_voucher.py` preserved.
- Next exact action for broader closure: investigate the asset-validation failure in isolated Backend QA, then resolve or explicitly disposition remaining development/test findings before declaring full closure. Any public release requires a public-config candidate and the project's explicit deployment approval.


## Authorized full E2E continuation

Media classification: **QA_ENV_FIXED**. All nine originally failing tests passed in a network-disabled disposable container with SQLite and MEDIA_STORAGE_ROOT under its temporary /tmp filesystem. The affected backend group (supplier assets, travel commerce, leisure commerce, checkout/reviews/payment, mobile OTP auth) passed **42 tests**. The host test venv lacked declared Pillow; the existing backend image includes the declared dependency, explaining the prior invalid-PNG acceptance in that incomplete test environment. No production permissions, storage or backend validation code changed. Evidence: /tmp/karen-media-nine-isolated.log and /tmp/karen-media-affected-isolated.log.

Next: refresh stale E2E selectors against current UI, retaining behavioral assertions; run the existing browser group on isolated API/search/assistant services and built Preview. All payment initiation browser requests must be intercepted. Restore any test edits if unsupported by current UI evidence. No production deployment authorized.

Confirmed ordinary E2E defect: overlapping Search requests have no response-generation guard. On consumer session hydration, an older anonymous 503 can overwrite a newer authenticated success. Acceptance: a deliberately delayed older failure cannot replace a newer successful response. Fix is limited to request ordering, with no Search visual change. Rollback: revert only the request-generation guard.


## Final closure checkpoint — 2026-09-25

**Source/Preview E2E: PASS. Production release: not performed.** This checkpoint supersedes the earlier open QA findings in this historical report.

- Nine media failures: **QA_ENV_FIXED** (temporary writable storage plus the already-declared Pillow dependency). Nine targeted tests passed, followed by 42 affected backend tests; the nine are included in the 42. Production filesystem permissions/storage and backend product code were unchanged.
- Final combined browser suite: **25/25 passed**, including login, search/autocomplete/Jalali calendar, comparisons, commerce, approval, tenant/RBAC gates, customer account, supplier/agency/backoffice actions, support, finance, saved trips/itineraries/destinations/map fallback, payment handoff and search response ordering.
- Fixed one ordinary product defect discovered during closure: `UnifiedSearchView` now ignores superseded responses and invalidates pending results when its effect is cleaned up. A delayed older anonymous error previously replaced the newer successful response. The deterministic regression failed on the old image and passed on the fixed image. No visual redesign.
- Updated stale E2E labels/calendar interactions, narrowed record selectors, made fixture idempotency keys unique per run, and allowed QA API/screenshot paths to be configured. Reused-database credit exhaustion was eliminated by a fresh isolated database; no product credit limits were weakened. Generated tracked screenshots were archived under /tmp and their previously clean versions restored.
- Fresh consumer journey passed: registration → captured test OTP → account → logout → consumer login. Explicit customer-role and consumer-tenant assertions passed. Flight/Hotel/Tour price-check → booking → idempotency → checkout passed. Leisure fixture fulfillment → RTL voucher and My Trips passed. Payment capture in that helper is an isolated test-database fixture, never a real transaction.
- Twelve additional browser checks (account, search, checkout, trips, booking management, assistant at widths 1440/390) recorded no JavaScript errors or horizontal overflow. Auth screenshots and RTL voucher screenshot were generated; manual image inspection was unavailable because the image viewer hit the sandbox mountinfo failure. These are browser/assertion results, not a claim of manual visual certification.
- Payment-URL verification used an intercepted HTTPS destination and rejected HTTP/javascript/malformed/missing destinations. The account gateway test also intercepts initiation. No financial transaction was initiated.
- Clean fixed-image build and its TypeScript stage PASS; targeted ESLint and diff whitespace checks PASS. Historical `.next/dev/types` workspace artifacts were not modified; validation uses the successful clean build. No additional full backend audit or suite rerun beyond the requested affected group.
- Fixed Preview image: `karenseir-web-qa:closure-race-fixed`, SHA256 `dc31914c833f6e5ee71c0671377e6d70d04442fc93f14206be9cad671fed8a71`, loopback `127.0.0.1:3312`. Its API/site configuration is QA-only; it must not be promoted directly to public Production.
- Production Web image remains `b2fab9f4f9c74c23ea012482b86ee9a30267eb40cb655d16e5bf8ce67fb80a1b`; HEAD remains `6494d96`. Existing login/account/payment edits, recovery documentation and untracked `backend/debug_voucher.py` are preserved. This continuation adds the search race fix, test corrections/regression and closure evidence. No commit, deployment, migration, secrets or Production data change.
- Durable evidence: `docs/recovery/2026-09-25-e2e-evidence.json` records counts, 12 browser checks, image identities, local evidence-log locations and source/test hashes.
- Functional completion: isolated E2E closure passed. Production readiness remains conditional on real external credentials/delivery/provider/payment validation and an explicitly approved public-config release; isolated Mock success is not live-provider success.
- NEXT EXACT ACTION: if a Production release is requested, build and smoke a candidate with the approved public HTTP/site/API configuration, retain the current recovered Web image/container for rollback, then obtain the required explicit approval for that exact deployment.
