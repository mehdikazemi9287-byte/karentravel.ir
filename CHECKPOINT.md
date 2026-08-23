# KarenSeir Checkpoint


## PRODUCTION GATES + RC RESUME FROM HERE

### 2026-08-23 closure update

- Timestamp: `2026-08-23T04:20:00Z`; branch `main`; HEAD `3589b24e419749a640719a363544890983d97d71` (prior HEAD `4debabe369f77f6532621695e3e698118c8cdc6a`).
- Migration head: `20260822_17`. Full chain verified twice on real PostgreSQL 16: once on a fresh disposable DB, once restored from an actual `pg_dump` of the live production database (checksum `98decea27ac242de9e5a83b0176fc71429fa8f0569ca125271ee03172904c400`) — data preserved exactly, rollback/re-upgrade clean, zero drift both times. Production database itself was never written to.
- Found and fixed a real bug in migration `20260821_15`'s `downgrade()` (dropped a hardcoded FK constraint name that only matched one of two possible creation paths; SQLite-only testing had masked it — surfaced by real Postgres rollback validation).
- Villa vacation-rental pricing completed: seasonal/weekend/min-stay pricing (`migration 20260822_16`, `_villa_stay_pricing` in `app/main.py`) and cancellation-quote wiring reusing the existing generic `_verified_cancellation_quote`/`/reservations/{id}/cancellation-quote` pipeline — no new endpoints needed. Dedicated test added and passing on real Postgres.
- Search results page (`UnifiedSearchView.tsx`) now surfaces `ranking_explanation`, recent searches (`GET /search/recent`), and saved searches (`GET/DELETE /search/saved`) — all backend contracts already existed and were tested, frontend never consumed them until now. Homepage/Hero/Search visual identity untouched; diff is scoped to the results component + additive-only CSS.
- **Production Gate 1 (public API routing)** — CLOSED. Same-origin `/api` nginx routing proven end-to-end on an isolated stack: `location /api/ { proxy_pass http://<api>:8000/; }` alongside the existing `location /`. Frontend built with `NEXT_PUBLIC_API_URL=/api` (relative, same-origin, no CORS needed for the primary path). Verified: `curl` through nginx to `/`, `/api/health`, `/api/search/v2`; client bundle contains no `localhost:8000` and does contain `/api`.
- **Gate 2 (CORS/HTTPS)** — MECHANISM CLOSED, deploy blocked externally. CORS_ORIGINS enforces exact-match allowlist (not wildcard) — verified via curl: matching Origin gets echoed back in `Access-Control-Allow-Origin`, non-matching Origin gets no header at all (browser then blocks it). **External blocker**: this host has no domain/TLS at all (only port 80 listening; confirmed via `ss -ltnp`), and current source's `validate_production_config()` requires HTTPS-only CORS origins in `ENVIRONMENT=production` — a real, correct guardrail, not a bug. The currently-live `karenseir-api-1` never hits this check only because it's a stale Aug-15 image built before the check existed. A true production-mode deploy of current source needs a domain + TLS cert (e.g. Let's Encrypt) first; cannot be fabricated.
- **Gate 3 (identity lookup / RLS)** — CLOSED. `dev-login`'s cross-tenant email lookup (the only such unscoped lookup in the codebase — `/auth/otp/request` was already correctly tenant-scoped) now goes through `find_login_identity(email)`, a `SECURITY DEFINER` SQL function owned by a new `karenseir_identity_resolver` role that is `NOLOGIN BYPASSRLS` (nobody can connect as it) with an explicit, minimal `GRANT SELECT ON users` — `BYPASSRLS` alone does not grant table access, that was the first fix needed. Function returns only `id/tenant_id/name/role`. `EXECUTE` granted only to `karenseir_api` via `deploy/provision-api-role.sql`. `dev_login` now also calls `set_tenant_context()` after resolving identity, fixing a second latent bug (refresh-session insert was failing RLS because tenant context was never set for this unauthenticated path). Verified: valid lookup works, unknown email fails closed (no error, no leak), cross-tenant emails resolve to their own correct tenant only, direct `SELECT * FROM users` by `karenseir_api` still returns 0 rows without context (general RLS unweakened). Permanent test added: `test_identity_lookup_function_is_narrow_and_does_not_weaken_rls` in `test_production_controls.py`.
- Also fixed (found via real Postgres testing this session, not previously exercised): `Dockerfile` never accepted `NEXT_PUBLIC_API_URL` as a build arg (Next.js inlines `NEXT_PUBLIC_*` at build time; docker-compose was passing it at runtime, which does nothing) — every prior frontend image, including the currently-live public one, has `localhost:8000` baked into its client bundle and cannot reach any API from a real visitor's browser. `playwright.config.ts` had a macOS-only `/private/tmp` path and a hardcoded port that collided with an unrelated running container on this Linux host, both blocking E2E here.
- Tests: local backend `88 passed, 6 skipped` (6th skip is the new identity-lookup test's own Postgres-only gate, same pattern as the existing 5); RLS matrix `85/85` + generic RLS/worker suite `4/4`, run on both a fresh disposable DB and the real production-clone; focused travel-commerce `4/4` on real Postgres (incl. new villa pricing test); full E2E `17/17` on a fresh dev-server DB, `15/17` on the repeatedly-reused RC clone (2 failures root-caused precisely to the RC clone's own repeated-run contamination — a hardcoded `suffix='manage'` default in the E2E fixture, not a code defect); lint/typecheck/build clean; `git diff --check` clean.
- **Production deployment**: NOT executed. Explicitly held per instruction. Full controlled deploy plan written (backup → migrate → API → frontend → nginx switch → smoke tests → rollback conditions) and awaiting explicit approval. Rollback tag `karenseir-ui-preview:rollback-pre-20260822` created; production backup + checksum saved at `/home/ubuntu/release-candidate-evidence/production_backup_20260822.dump`.
- Remaining internal: none blocking a production deploy once HTTPS exists. Supplier operational mutation UI, Trip Operations/Timeline projection for linked tour/visa, and provider fan-out performance/cache certification remain documented-incomplete but are not gates.
- External blockers: **domain name + TLS certificate** (new, specific, blocking finding this session — needed for `ENVIRONMENT=production` CORS to start at all); ZarinPal sandbox merchant; contracted Flight/Hotel/Tour/Cruise provider credentials; SMS/OTP; Secret Manager; monitoring/alerting collector.
- Completion: ecosystem ~95% by internal implementation gates (up from 94%); all three internally-controllable production gates closed; Production remains **NO-GO** pending the TLS/domain external dependency and explicit deploy approval.
- NEXT EXACT ACTION: obtain a domain name pointed at `95.38.184.209` and a TLS certificate (e.g. via `certbot --nginx`), OR get explicit approval to proceed with the written deploy plan once that exists. No further internal work blocks deployment.


## KARENSEIR TRAVEL COMMERCE RESUME FROM HERE

### 2026-08-21 closure update

- Search UI visibly upgraded inside the existing Hero Search component: eight vertical tabs, context-aware labels/descriptions, responsive tab layout, and fresh Browser evidence for default/autocomplete/date/passenger/villa/tour/results desktop/mobile. Homepage identity remains unchanged.
- Incremental migration `20260821_15` links tenant-owned `VisaApplication.tour_reservation_id` to `TourReservation`; isolated SQLite upgrade/check/downgrade/re-upgrade to head PASS. Direct PostgreSQL Head 14/15 validation remains blocked because no PostgreSQL runtime is available on this host.
- Tour detail/reservation now expose explicit visa status and visa applications can be linked to the caller-owned tour reservation; a `tour_linked` timeline event is recorded. Cross-tenant/foreign ownership is denied.
- Tests: backend `87 passed, 5 skipped`; travel-commerce `3/3`; full Chromium `17/17`; Search interaction focused PASS; lint/typecheck/build and migration check PASS.
- Remaining internal: direct PostgreSQL RLS/backup/restore evidence; villa seasonal/weekend/min-stay/cancellation settlement; supplier operational mutation UI; full Trip Operations event projection for linked tour/visa. External: ZarinPal merchant, contracted travel/cruise providers, SMS/OTP, Secret Manager, monitoring, DNS/TLS and target deployment/security certification.
- NEXT EXACT ACTION: provision isolated PostgreSQL 16, back up before `20260821_15`, run RLS/FORCE/missing-context/own/cross-tenant/concurrency checks, then implement villa pricing/settlement and supplier mutations.

- Timestamp: `2026-08-21T15:14:00Z`; branch `main`; HEAD `214b2bd2ea1cd6357c61eba93a611689735f7757`.
- Migration head: `20260821_15`. Isolated SQLite upgrade/current/check, downgrade to `20260821_14`, and re-upgrade PASS. Direct PostgreSQL validation for the new tenant tables is **not claimed** because this host has neither Docker nor a PostgreSQL runtime.
- Search state: Browser-visible Search Box/results flow remains PASS and mock-free; autocomplete/date/passengers/trip type/filter/sort/compare/save/recheck work. Homepage identity remains unchanged.
- Villa state: property/unit catalog، date-range reservation، overlap/double-booking protection، idempotency، tenant ownership، Reservation/Checkout handoff and list/detail UI PASS.
- Tour state: product/departure inventory، capacity/deadline، room surcharge، oversell prevention، Reservation/Checkout handoff and list/detail/booking UI PASS. Unpaid voucher remains null by design.
- Cruise state: catalog/domain/API/UI foundation PASS; live booking returns fail-closed `LIVE_PROVIDER_UNAVAILABLE` until a contracted Provider is configured.
- Visa state: timestamped source، application، multiple applicants، hashed passport reference، documents، human-only review and system/human timeline PASS. Embassy/VAC submission and decision are external.
- Tests: local backend `87 passed, 5 existing infrastructure skips`; Travel Commerce `3/3`; ESLint/strict type/build PASS; isolated Alembic PASS; Chromium `17/17`; Homepage Desktop/Mobile PASS; screenshots saved under `artifacts/search-ux/` and `artifacts/travel-commerce/`.
- Remaining internal: disposable PostgreSQL head-14 RLS/FORCE/backup/restore/rollback validation; seasonal rental calendar and cancellation settlement; supplier management UI; deeper Tour↔Visa↔Trip Timeline linkage.
- Credentials required: ZarinPal sandbox merchant، Flight/Hotel/Tour/Cruise Provider contracts، SMS/OTP، Map، external Secret Manager and monitoring collector.
- Completion: ecosystem `94%` by internal implementation gates; Production **NO-GO**.
- NEXT EXACT ACTION: provision an isolated PostgreSQL 16 runtime, backup it, upgrade to `20260821_14`, then run missing-context/own/cross-tenant/write/FORCE-RLS and concurrency tests for all twelve new tables before any provider credential work.


## SEARCH UX RESUME FROM HERE — operational browser gate

- Timestamp: `2026-08-21T13:49:55Z`; branch `main`; baseline HEAD `ecbfae349a5a9cd4384ede22b42b09cb71aa9ef1`; final source/evidence commits are recorded below after save.
- Migration: unchanged `20260820_13`. This UI phase did not mutate PostgreSQL or weaken RLS/RBAC.
- Search UX: **PASS**. No Mock/demo success remains inside the Search Box/results flow. Autocomplete, Persian typo UX, date flexibility, trip type, passengers, URL-restorable submit, results, filters, sort, selected-Offer comparison, Wishlist/Trip Basket and authoritative recheck are Browser-visible.
- PASS: focused backend `15/15`; local backend `84 passed`; frontend lint/strict type/build; npm audit 0; Search UX focused E2E; full Chromium `16/16`; nine screenshots manually reviewed; Homepage Desktop/Mobile identity unchanged; `git diff --check`.
- Infrastructure note: five local backend tests are environment gates and were skipped because live isolated Redis/PostgreSQL/worker URLs were unavailable. No new skip exists; last real PostgreSQL/Redis evidence remains `87/87` and RLS/FORCE `67/67` at this migration head.
- Screenshots: `homepage-search-desktop.png`, `homepage-autocomplete.png`, `destination-autocomplete.png`, `date-picker.png`, `passenger-picker.png`, `search-results-desktop.png`, `filter-panel.png`, `comparison.png`, `search-results-mobile.png` under `artifacts/search-ux/`.
- External blockers: authorized Flight/Hotel/Tour/rail Provider credentials and contracts; ZarinPal merchant; SMS/OTP; map; public DNS/TLS; Secret Manager; monitoring/alerting collector; target deployment and independent security certification.
- Remaining internal: no blocker for the requested Search UX gate. Provider fan-out performance/price-calendar/alerts cannot be certified without real authorized transports.
- NEXT EXACT ACTION: inject one authorized sandbox travel-provider credential through the external Secret Manager, then run provider timeout/partial-failure and Search/provider P50/P95 certification without changing Homepage.


## SEARCH UX RESUME FROM HERE

- Timestamp: `2026-08-21T12:49:21Z`; branch `main`; source implementation commit `8e7bfe04b630392f5d231d9ac844bb0663a1ab07`.
- Search UX: **PASS**. Homepage layout/hero/header/sections/identity remain unchanged; only the existing Search Box interaction and its dedicated results route were enhanced.
- Visible flows PASS: typed public-safe autocomplete with city/airport/IATA/typo recovery; round-trip/one-way/multi-city entry; exact/±1/±3 date selection; adult/child/infant/room/cabin picker; URL-restorable structured submit; edit/filter/sort/compare/save on results; loading/zero/error/unauthorized/stale/mobile states.
- Security: public autocomplete contains no tenant Offer/entity data; results remain authenticated and tenant-aware. Price, availability and refundability come only from backend Offer data.
- Evidence: six screenshots under `artifacts/search-ux/`; Chromium `16/16`; focused Search backend `6/6`; full local backend `83 passed, 5 infrastructure-skipped`; prior real PostgreSQL/Redis evidence remains `87/87`, now plus the isolated public-autocomplete test.
- Frontend: ESLint, strict TypeScript and 32-route production build PASS; npm audit `0 vulnerabilities`; Python compile and `git diff --check` PASS.
- Migration head unchanged: `20260820_13`.
- NEXT EXACT ACTION: obtain an authorized sandbox travel-provider credential and run Search provider fan-out/P50/P95 certification; then add a real price calendar only when the Provider exposes dated fares.

## SEARCH ENGINE RESUME FROM HERE

- Timestamp: `2026-08-21T12:02:00Z`; branch `main`; implementation commit `83a49b8` (final evidence commit follows).
- Search version: `unified-search-v2`; migration head: `20260820_13`.
- Completion: Search `88%`; expanded ecosystem `92%`; Production remains **NO-GO**.
- Completed: Persian/Arabic digit/character/punctuation normalization; safe Tehran/Shiraz/IATA aliases and typo matching; typed autocomplete ranking; fourteen-vertical shared Offer contract; normalized price/freshness/availability output; deterministic entity deduplication; explainable ranking; flexible-date intent; filters/map bounds; zero-result recovery; tenant-scoped recent/saved searches; deterministic natural-language structuring; live-inventory-only budget candidates; price tamper recheck; dedicated `/search/results`; session resume; Search metrics; review/checkout/ZarinPal credential-independent foundations; public SEO routes.
- PostgreSQL: empty disposable PostgreSQL 16 upgraded through head 13 after backup checksum `9339362ef26582d7142fea14c0f72337fd43d6c12161d8951ca0b741ea7c4211`; Alembic current/check PASS; `67/67` tenant tables RLS+FORCE RLS. API NOBYPASSRLS, missing context, own/cross-tenant and worker least privilege PASS.
- Tests PASS: backend `87/87`, focused Search/Checkout/ZarinPal `14/14`, Chromium E2E `15/15`, lint, strict TypeScript, 32-route build, Python compile, npm audit 0, and Homepage Desktop/Mobile visual regression.
- External blockers: contracted Flight/Hotel/Tour/rail/destination providers, ZarinPal sandbox merchant, SMS/OTP, map provider, public DNS/TLS, Secret Manager, monitoring collector/alerting, target deployment and independent certification.
- Remaining internal: bounded concurrent live-provider fan-out/load benchmark with real adapters; distributed provider-result cache hit telemetry; real price-calendar feed; price/availability alert scheduler after notification transport; broader city/station/POI catalog ingestion. No fabricated offers or alerts exist.
- NEXT EXACT ACTION: obtain an authorized sandbox travel-provider credential and execute provider timeout/partial-failure/P50/P95 contract certification against `/search/v2`.

### RESUME FROM HERE

- Last work: Unified Search v2, real PostgreSQL migration/RLS validation, Review/Checkout/ZarinPal internal adapter and independent results route.
- Last Git HEAD: `83a49b8` before final evidence commit.
- Last migration: `20260820_13`.
- PASS: backend 87/87, PostgreSQL/RLS 67/67, frontend lint/type/build, Search focused 14/14, Chromium E2E 15/15, Homepage regression, npm audit.
- BLOCKED: external live provider latency/caching benchmarks and ZarinPal sandbox purchase require credentials; Production dependencies remain absent.
- Completion: Search 88%, ecosystem 92%.
- First next action: provide an authorized sandbox travel-provider credential; then run the provider contract certification suite against `/search/v2`.

## Saved-travel ecosystem checkpoint

- Timestamp: `2026-08-20T09:34:20Z`
- Branch: `main`
- Baseline commit: `08de094bc193b26ee8e3ee56c7b1062ff0d85ab8`
- Migration head: `20260820_11`; isolated Alembic upgrade/current/check PASS. Direct PostgreSQL validation for this new head is not claimed because no PostgreSQL/Docker runtime is installed.
- Completion: `84%`; phase gates passed `10/16`. Phases 7, 8 and 16 remain blocked on the direct PostgreSQL head-11 RLS gate; 13–15 retain documented work/credential gates.
- Completed: saved trips/wishlist/basket domain and connected UI; verified-review anti-forgery and moderation domain; destination hierarchy/routes; editable itinerary lifecycle; deterministic vertical comparison awards; map/list credential-free fallback.
- QA: backend `73 passed, 5 skipped`; lint/typecheck/build PASS (26 routes); Chromium `14/14`; Homepage Desktop/Mobile regression PASS; npm audit 0; Alembic no drift; diff check PASS.
- UI Freeze: no Homepage/CSS/asset file changed and visual structural screenshot gate remained green.
- Remaining internal: direct PostgreSQL migration/RLS validation head 11; review UI; unified resumable checkout; ZarinPal-specific request/verify adapter and tests; SEO/CWV/RTL matrix; final security suite and release evidence refresh after those gates.
- External blockers: ZarinPal sandbox merchant, map provider, SMS/OTP, Flight/Hotel/Tour provider credentials, public DNS/TLS, Secret Manager, external monitoring/alerting, target deployment and independent security certification.
- Production readiness: **NO-GO**.
- Exact next action: run migration 11 on a disposable PostgreSQL staging with pre-backup, then execute missing-context/own/cross-tenant/FORCE RLS tests for all seven new tables and rerun backend with zero skips.
- Source implementation commit: `29e114471262e1f9f407690f459a918f197f3f82`; final provenance commit is reported after saving this checkpoint.

- Timestamp: `2026-08-20T09:07:00Z`
- Branch: `main`
- Baseline commit: `2054b84a29a14d18d28786c1220e2c0612496f18`
- Migration head: `20260820_10` (unchanged)
- Completion: `76%` of expanded Travel Ecosystem scope; prior production-hardening scope remains 97%.
- Phases passed: `6/16` — Product Audit, Search 2.0 internal contract, Trip Operations/Timeline, Organizational Travel, Supplier/Agency ecosystem, Security/Financial QA.
- Search: 14 verticals, Persian normalization, tenant-safe autocomplete/recent history, flexible-date intent, filters/map bounds/sorts, provider/timestamp/TTL/freshness, transparent totals and stale fail-closed.
- UI Freeze: no Homepage, CSS, image or approved presentation file changed. Desktop 1440×1000 and mobile 390×844 structural screenshot render gate PASS.
- QA: backend `70 passed, 5 skipped`; focused Search+booking `13/13`; frontend lint/typecheck/build PASS (22 routes); Chromium `13/13`; compile and npm audit 0 PASS.
- Remaining internal: destination catalog/discovery routes; persisted review/moderation; editable itinerary; Trip Basket/wishlist/share; map/list route; vertical comparison awards; cohesive checkout; full RTL/date/CWV/SEO matrix.
- External blockers: ZarinPal sandbox merchant credential (`PAYMENT TEST — BLOCKED BY CREDENTIAL`), map/places credential, travel provider credentials, SMS/OTP, public DNS/TLS, Secret Manager, monitoring, target deployment and security certification.
- Production readiness: **NO-GO**; no sandbox/provider/payment success is claimed.
- Exact next action: add an incremental tenant-RLS migration for Trip Basket/Wishlist and Verified Review, with PostgreSQL cross-tenant/idempotency tests, without touching Homepage.
- Source checkpoint commit: `d5013e70116435b6d96cda1c0013c6f283d5cf22`; tree checksum is recorded in `RELEASE_MANIFEST.json`. Final provenance-doc HEAD is reported after commit.

## PRODUCTION DB MIGRATION GATE — 2026-08-23

- Backup path: /home/ubuntu/preview-deploy-evidence/production_backup_gate.dump
- Backup checksum: 4c1d9f7e4af554096a8a031ad618eba36b53681a8288a9a2366db1dd63066df5
- Backup readable: PASS (pg_restore --list, 63 TOC entries, 74 lines)
- Current migration state: pre-Alembic baseline, no alembic_version table
- Target migration head: 20260822_17
- Row counts: tenants=2 users=3 hotels=3 bookings=1 ledger_entries=1 audit_events=2
- Live API image: sha256:42390b86320a (container karenseir-api-1)
- Live frontend image: karenseir-ui-preview:20260818 / sha256:7bf7a9e1ce5b (container karenseir-ui-preview)
- Exact migration command: docker run --rm --network karenseir_default -v /home/ubuntu/karenseir-current/backend:/app -w /app -e DATABASE_URL=postgresql+psycopg://karenseir:REDACTED@db:5432/karenseir karenseir-api sh -lc "python -m alembic upgrade head"
- Rollback application images ready: YES (karenseir-ui-preview:rollback-pre-20260822 = sha256:7bf7a9e1ce5b; karenseir-api-1 image sha256:42390b86320a untouched and unremoved)
- Ready for approval: YES

## PUBLIC SEARCH PREVIEW — 2026-08-23

- Public URL http://95.38.184.209/ now serves the redesigned premium navy/turquoise Search box (verified via real Playwright screenshots against the actual public IP, not localhost/RC). Frontend container: karenseir-ui-preview:20260823-search4 (host image tag), NEXT_PUBLIC_API_URL=http://95.38.184.209:8000, ALLOW_HTTP_PREVIEW=1 baked in at build time.
- Two real bugs found and fixed, both specific to HTTP-only (no-TLS) deployment: (1) production CSP always set upgrade-insecure-requests, silently breaking every asset request when no HTTPS exists; (2) crypto.randomUUID() is undefined outside secure contexts, crashing the app on first API call. Both fixed with narrow, explicit, documented opt-outs/fallbacks -- neither weakens a real HTTPS deployment.
- Verified interactively on the public site: all 8 vertical tabs switch with correct context-specific fields, free-text destination entry works, search submit navigates to /search/results and correctly shows the designed fail-closed unauthorized gate (not a crash).
- Autocomplete and full results still blocked: NEXT_PUBLIC_API_URL points at the OLD live API (Aug 15 build, unmigrated DB, CORS_ORIGINS=http://localhost:3000), which lacks /search/v2 etc. and rejects this origin. This is the same, previously-flagged, approval-pending API+DB deploy gap -- not new.
- Rollback: karenseir-ui-preview-pre-uuid-fix (immediately prior working container) and the original karenseir-ui-preview:rollback-pre-20260822 (Aug 19 baseline) both retained, untouched.
- Production database: UNCHANGED. Live karenseir-api-1: UNCHANGED. Only the frontend-serving container was swapped.
- Source commits: 0f88daf (Search redesign + preview fixes), 56b92f9 (screenshots).
- NEXT EXACT ACTION: your call -- approve the pending production DB migration (gate already evidenced) to unlock full Search results on the public preview, or leave as visual-only preview.
