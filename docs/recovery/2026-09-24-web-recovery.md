# Web recovery — 2026-09-24

## Baseline and scope
- Source: `/home/ubuntu/karenseir-current`, application HEAD `975608f5c683bbcc63392fb865c0f90d4ad99122`.
- Existing user file `backend/debug_voucher.py` remains untouched and untracked.
- API runtime Python files: 19/19 hashes match source. DB reports `20260922_33`.
- Web/API runtime fingerprints before recovery report `unknown`; image tags alone are not provenance proof.
- No application source changes. Rebuild exact tracked HEAD via `git archive` with corrected build arguments. No DB, API, Worker, Assistant, Nginx or design changes.

## Root cause
Public HTTP responses contain `upgrade-insecure-requests` and a CSP API origin of `http://localhost:8000`. Public browsers request HTTPS assets from an HTTP-only server, receiving `ERR_CONNECTION_REFUSED`. Registration/login remain blank because their client-rendered forms cannot hydrate. Loopback-only checks hide the regression.

## Candidate and acceptance
Image: `karenseir-current-web:recovery-975608f-http`, SHA256 `b2fab9f4f9c74c23ea012482b86ee9a30267eb40cb655d16e5bf8ce67fb80a1b`.
Build arguments: `ALLOW_HTTP_PREVIEW=1`, `NEXT_PUBLIC_API_URL=http://95.38.184.209:8000`, `NEXT_PUBLIC_SITE_URL=http://95.38.184.209`, `GIT_COMMIT=975608f5c683bbcc63392fb865c0f90d4ad99122`, `BUILD_TIMESTAMP=2026-09-24T14:27:00Z` (build initiation marker).
The HTTP opt-out is specific to the established HTTP endpoint; a future HTTPS deployment must omit it and use matching HTTPS API settings. Runtime environment overrides cannot repair already-inlined NEXT_PUBLIC values.

QA before release:
- Production frontend build and typecheck PASS.
- Backend: 316 passed in fresh migrated isolated PostgreSQL; the 6 skipped infrastructure tests subsequently passed (5 + 1) with isolated Redis and least-privilege roles. Total 322 distinct tests passed, not one 322-test invocation.
- Candidate browser smoke: homepage, registration, login, Search results, unauthenticated My Trips and Assistant; desktop 1440 and mobile 390, all HTTP 200, no JS/asset failures, no horizontal overflow. Public-origin requests intercepted to loopback candidate to preserve CSP semantics. Search v3 public API returned 200 on both viewports. Screenshots visually inspected.
- Authenticated production booking/payment/voucher/timeline writes have not been executed; prior accepted baseline and isolated backend tests are retained as evidence, not represented as a new live end-to-end transaction.

## Release and rollback plan
Authorized recovery replaces only Web after candidate verification.
Keep original container stopped under `karenseir-frontend-pre-recovery-20260924` and original image `karenseir-current-web:closure-975608f` (SHA256 `948b539c2620b0e3a0248aa812e238703a9f35107ac048b09409cba508bc62c6`).
Replacement retains port 3000, `karenseir_default` network and `unless-stopped` policy. No volumes/secrets are attached to the original Web container.
Rollback if public browser verification fails: stop and rename replacement to a failed-release name, rename original back to `karenseir-frontend-1`, start original. This restores the pre-recovery state, including its known CSP defect.

## Preservation and limitations
Git fetch failed: SSH `Permission denied (publickey)`. Remote divergence cannot be refreshed; no push/PR attempted. A dedicated local recovery branch preserves closure source.
Payment activation and live supplier credentials remain external limitations. Reservation reaper remains `DEFERRED_ARCHITECTURE_FIX`; notification worker privileges unchanged.
Production rollout: BLOCKED_APPROVAL. Automatic approval review rejected the container replacement because it requires explicit approval for this exact Production deployment and brief service interruption. No deployment command ran. Approval has been requested.
Final document QA: checked source HEAD, image identities, test counts, browser results and rollback sequence against captured evidence. No runtime success is claimed.

Artifacts: `docs/recovery/2026-09-24-preview-smoke.json`; build/test logs remain in `/tmp/karen-recovery-*.log`. Preview remains available only on `127.0.0.1:3310`.
Next exact action after explicit approval: replace only `karenseir-frontend-1` with the verified image, preserve the original container as above, run the same public-origin desktop/mobile browser smoke without interception, and roll back on failure.

## Approved production deployment — completed
The user explicitly approved this exact frontend replacement after the earlier automatic rejection. The approval block above is resolved.
- Deployed the existing verified `karenseir-current-web:recovery-975608f-http` image without rebuilding.
- Environment, port bindings and network membership match the prior container; original retained stopped as `karenseir-frontend-pre-recovery-20260924`.
- Web healthy. Twelve public browser checks passed at 1440/390 widths: `/`, `/login`, `/register`, `/search/results`, `/trips`, `/assistant`. CSS/JS loaded without asset or runtime exceptions; RTL, fonts and horizontal bounds passed. Production desktop/mobile screenshots visually checked.
- Public CSP no longer upgrades assets to unavailable HTTPS or points to localhost. Browser Search calls reached `http://95.38.184.209:8000/search/v3/public` with HTTP 200.
- Assistant gateway forwarded an empty validation probe and returned expected HTTP 422; no conversational or booking action requested.
- API, Worker and Assistant remain healthy. No DB, migrations, Worker privileges, reaper, payment, secrets, other projects or GitHub reconciliation changes.
- Rollback was not needed. Original image/container remain available; rollback would restore the known pre-recovery CSP defect.
- Targeted recovery QA PASS; no remaining P0 detected within frontend recovery scope. This is not a new full authenticated purchase verification.
- Detailed browser evidence: `/tmp/karen-production-smoke.json`; production screenshots: `/tmp/karen-production-1440.jpg`, `/tmp/karen-production-390.jpg`.
