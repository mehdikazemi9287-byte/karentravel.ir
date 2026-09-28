# Operational E2E closure — active work

Baseline: customer-journeys report and public fingerprint 6494d96-worktree-b837ab14ea65. Source/public Web hashes match; all 19 deployed API app Python files match Source. Existing dirty files and backend/debug_voucher.py preserved. Scope authorized by pasted request: operational gaps, all credential-independent implementation, isolated end-to-end verification and reversible deployment. No live financial transaction, unsolicited SMS, destructive action or production migration.

## Targeted gap register

| Gap | Evidence | Action / acceptance |
| --- | --- | --- |
| OTP accepts incomplete success response | kavenegar_adapter.execute returns ok on return.status=200 even without messageid | Require provider message reference, handle malformed body, redact transport details, use POST form, explicit error mapping; controlled provider contract tests and API/DB rollback on delivery rejection |
| OTP ambiguous retries | provider has max_attempts=2 without provider idempotent-send guarantee | One send attempt; no blind duplicate on unknown timeout |
| Payment browser callback dead end | GET callback returns JSON after DB capture | Browser return page derives state only from authenticated API/DB; callback HTML redirect, JSON API contract preserved; failure/duplicate tests in isolated DB, no real gateway |
| HTTPS deployment template placeholders | nginx.conf.example travel.example, api.travel.example | Prepare canonical karentravel.ir host config with fixed redirects and validation; no activation without real DNS/cert |
| Role/vertical completeness | prior 25-browser and 42-backend results exist; registry statuses stale | Reuse pass evidence, inspect only unproven details/recovery/auth/contract gaps; maintain matrix distinguishing isolated evidence from live connection |

## External boundaries

Reuse 2026-09-27-live-prerequisites.md: DNS SERVFAIL; GRS endpoint/token/money-unit absent; flight provider not selected and no vendor transport spec; ZarinPal merchant/callback absent; Kavenegar account/info unknown-method 404; Push/notification provider credentials not supplied. Cannot claim an unknown vendor transport is configuration-only without its API specification. Support phone is approved for display, not test-message delivery.

Kavenegar official contract checked: https://kavenegar.com/rest.html (verify/lookup, account/info; 404 unknown method, 405 HTTP-method mismatch, success entries contain messageid). Changes below address independently proven implementation gaps; they are not claimed to resolve live account access or prove delivery.

## Validation plan

No repeated full audit or prior PASS suite. Isolated temporary writable media + dedicated test DB; mock transport labelled as such and blocked from Production. New regressions must fail on old code and pass after repair. Browser/API/DB deltas for changed flows; reuse previous role/commerce/voucher evidence where unchanged. Build, targeted source checks, deployment manifest and rollback. Final matrix uses PASS/PARTIAL/BLOCKED and explicit production/booking/payment/OTP readiness flags.

## Checkpoint 1 — Source P0 deltas

Production remains at b837ab14ea65; no goal-stage deployment yet. OTP regressions: 16 fail/3 pass before fix, all related 59 tests pass after fix in network-disabled disposable container with /tmp media/SQLite. Provider result requires positive numeric messageid; no repeated ambiguous send; secrets no longer echoed; formal POST body and canonical digits. Real Kavenegar delivery remains unverified.

Payment delta + affected group: 8 tests pass (controlled gateway, isolated API/DB). HTML callback redirects only to configured HTTPS PUBLIC_WEB_URL and contains no signed state/success claim. Customer GET/verify endpoints enforce owner+tenant; late NOK cannot undo captured payment; verify recovery never initiates a charge. New PaymentReturn route derives status/receipt from DB and distinguishes payment capture from voucher issuance.

Additional proven gaps being closed: checkout traveller creation/selection and policy visibility, taxed-price recheck consistency; generic offer detail route missing; GRS synthetic search IDs do not map to Offer/PriceCheck and lifecycle reserve/book functions are not called by main API. Generic provider-mode offers currently pass local inventory checks without an external hold; must fail closed until a verified connector quote/hold path is wired. These are internal gaps, not external-credential excuses. Unknown flight vendor contract remains a real external specification blocker.

Next: targeted browser/API/DB verification for new flows; GRS contract wiring; canonical HTTPS deployment preparation; remaining role/vertical deltas; build/deploy/recovery and final matrix. No repeat of previous 25/42 suites.

Prepared canonical DNS/TLS files: deploy/nginx.karentravel.conf + deploy/karentravel.production.env.example. Fixed-host HTTPS redirects, ACME challenge path, loopback upstreams, headers and callback query-log suppression. Not installed on the running server: authoritative DNS and certificates remain missing. The current public IP/HTTP profile is not a production-commerce readiness claim. API startup now checks schema revision read-only in production rather than executing migrations implicitly; application JSON request logs remain while Uvicorn query-string access logs are disabled. New release_guard requires isolated testing before promotion.

Confirmed auth gap: concurrent panel requests with expired access token each rotate the same refresh token, invoking backend reuse revocation. Deterministic regression fails before fix. Single in-flight refresh plus delayed-401 token comparison will be verified in isolated browser/API/DB.

GRS search delta: full stay must contain each night, reject incomplete/closed dates, sum all daily rates and explicitly convert confirmed IRT into IRR. Suggestion is not a verified quote/policy/hold; online supplier purchase stays blocked. Original versioned GRS financial/guest/policy contract is not available locally; adapter comments alone cannot define authoritative total/taxes/guests. Customer receives support route instead of synthetic-ID detail/checkout 404. Exact vendor specification remains required for live booking wiring.

## Checkpoint 2 — promotion blocked by pre-existing worker drift

New scoped QA: OTP 59, payment 8, offer/schema 3, provider retry 53 and GRS stay 15 tests passed (separate affected groups; no repeat of previous 42/25 suites). Next production build, API image build and targeted frontend lint passed. Isolated browser → API → SQLite verified concurrent expired-token refresh, offer detail → reservation → inline traveller → policy → invoice → intercepted non-financial gateway, verify-only recovery and late NOK callback. New routes rendered without JS errors/overflow at 1440 and 390; payment mobile screenshot visually reviewed. Production DB Alembic head 20260922_33 matches source; no migration needed or run.

**STOP / not deployed:** worker `karenseir-worker-1` still runs `karenseir-current-api:search2`. Its providers.py hash starts 299976d2dbf3 versus deployed API/HEAD 6dd97430e468. Its outbox_worker.py hash starts 7a3930cc033b versus source/HEAD/API 6e83d9bccd25. These differences predate this task: worker lacks Kavenegar adapter wiring and reservation expiration sweeping present in HEAD. Promoting the current worker would begin periodic expiration processing against existing reservations; this is not an innocuous UI-only restart. AGENTS.md requires STOP + REPORT on definite runtime source/production mismatch and prohibits automatic deploy/reset/overwrite to reconcile it. No public containers or database were changed.

Built candidates: `karenseir-current-web:operational-20260927` (worktree fingerprint 99b41f565788) and `karenseir-current-api:operational-20260927`. Existing stopped rollback containers remain preserved. See operational-evidence.json for actual hashes and browser outcomes. New Source changes have not passed public verification because promotion is blocked. Role-navigation browser delta and remaining production promotion checks are unfinished; existing prior role/voucher/account evidence remains valid only for unchanged behavior.

Required next authorization: reconcile the specifically identified pre-existing worker drift with the reviewed source, including reservation expiration processing; then finish outstanding scoped QA and reversible coordinated release. No destructive DB operation, real financial transaction or live SMS is proposed.

External inputs still required independently: authoritative DNS/registrar access for karentravel.ir and api.karentravel.ir; valid TLS issuance after DNS; original versioned GRS financial/guest/policy API specification plus endpoint/token/confirmed currency and IP allowlist; selected contracted flight vendor/API credentials; ZarinPal merchant and approved HTTPS callback; Kavenegar account/API-method resolution plus approved test recipient to establish actual delivery.

## Implementation continuation — explicit user direction
User directs staged implementation and reversible deployment without further ordinary permission gates; public baseline preserved. Known worker drift will not be silently overwritten: stage 1 promotes the reviewed Web/API delta only; existing worker remains untouched until its expiration side effects are handled explicitly. First new repair: search result PRICE_CHANGED can now be explicitly accepted and rechecked with the revised amount; previously it resent the stale amount indefinitely. No fabricated production inventory or live financial transaction.

Next product delta: account payment actions now navigate to authoritative receipt/recovery and resumable checkout. Removed the old account initiate action that discarded redirect_url and bypassed the guided checkout. Confirmed checkout includes reservation/documents handoff; capture is still not falsely equated with voucher issuance. Acceptance: real isolated account payment link → authenticated DB-backed receipt and checkout continuation; old checkout/payment backend evidence reused unchanged.

Trip operations implementation: /backoffice/trips uses real Trip records, records a customer-visible change notice through existing TripEventRecord + NotificationRecord/fanout, with immutable Outbox audit payload (actor, before, after, reason, source reference). trip:event:create permission, tenant binding and replay conflict checks apply. This records supplied confirmed information; it does not pretend to execute a provider amendment. No schema migration or invented production facts.

Admin/Ops records: ten real DB projections with tenant-scoped backoffice permission, server pagination, explicit safe columns (no tokens, provider raw payloads or personal documents). UI tables replace the need to inspect raw JSON; existing action workflows remain linked. Acceptance: seeded isolated records visible, unauthorized role denied, cross-tenant data absent, all tabs render on desktop/mobile.

Stages 1–5 promoted with reversible retained API/Web/worker containers, isolated browser/API/DB evidence and public changed-route checks. Worker now uses current code; RESERVATION_REAPER_NOT_BEFORE preserves all pre-rollout holds, and paid/ambiguous/funded/provider-referenced reservations never auto-expire. Stage 6 partner forms/API mutations passed isolated E2E; fixing lint-only loading callback before promotion.

First next vertical: Train. Real internal supplier pool already exists; new route/time filters reject incomplete, wrong-route/wrong-date and past train offers; price-check and passenger cardinality guards prevent invalid holds. Contractual supplier entry supplies actual metadata/terms; rail carrier transport stays disconnected. No train record is created in Production by QA.

## Tour closure delta
Tour departure quotes and explicit revised-price acceptance connect to real checkout, passenger count, held capacity expiry and supplier-owned fulfillment. Catalogue errors remain distinct from empty inventory. Supplier issuance requires captured payment and internal document reference, including ownership on replay. QA uses isolated SQLite and intercepted gateway.invalid only; no production inventory or transactions created. No schema migration. Rollback retains Train containers.

## Accommodation closure delta
Real date-range availability and seasonal/nightly quote feed search, detail, explicit price acceptance and checkout. Existing VacationReservation/Unit/Property models are reused; supplier ownership and replay payload are checked. Expired unpaid holds release overlap reservations; captured/ambiguous payments remain protected. No migration, production fixture or real financial test.

## Car rental allocation delta
Contracted car-class allotments require a future fixed pickup/return interval, locations, deposit/license/insurance/mileage terms. Existing supplier-owned Offer/PriceCheck/Reservation/checkout/payment/voucher storage is reused, not a fleet-management claim. Search requires the exact offered dates; customer sees the entire interval price and separate deposit terms. No live rental provider, automatic license verification or deposit collection is claimed. No migration or production test records.

## Restaurant and admission delta
Mixed ticket selections recheck current ticket prices and pricing rules instead of multiplying the cheapest generic offer. Customer-issued tickets expose owner-only QR SVG; supplier validation/redemption is limited to assigned places, with single-use state, audit outbox and customer trip event. No production ticket is created or redeemed by QA. Existing leisure models are reused; qrcode 8.2 adds only document encoding, no external QR service.

## Event hall closure delta
Event-hall search is accepted and filters its selected date. Whole-venue fixed packages have one capacity and reject overlapping allocations at the same place under a place row lock. Discovery/inquiry products cannot create payable price checks; customer detail routes them to support. Existing event-ticket, checkout and QR admission models are reused. No migration or production test booking.

## Pool/sport closure delta
Pool/sport searches now reach the existing ticket/session catalog and honor a selected session date. Provider-authored product and session entry rules appear before booking and are frozen into the booking policy for explicit checkout acknowledgement. No inferred admission rules, health guarantees, production fixtures or real payments.

## Attraction closure delta
Attraction search now honors the chosen date. Leisure price checks expire no later than session closure, booking rechecks the live session, and generic offer price checks cannot bypass ticket selection/quotas. Saved generic leisure offer links redirect to the actual product detail. Printable vouchers now embed locally encoded QR SVG alongside the code; no external QR service or production test ticket.

## Travel guide closure delta
Supplier-authored dated guide allotments expose guide/team, languages, meeting point, group capacity and included/excluded services. Exact-date search and checkout enforce capacity; price is for a whole group. Existing offer/hold/payment/voucher/trip models are reused. No claim of live guide calendars or automatic credential verification, and no production fixture or financial transaction.

## Tourist transport closure delta
Dated supplier allotments specify operator, route, pickup/dropoff, vehicle class, seats, luggage and accessibility terms. Search matches route/date/party size; checkout enforces seats. Customer vouchers include operator and pickup/return points. This is contracted allocation booking, not a claim of live fleet dispatch. No production fixture, migration or financial test.

## Handicraft delta
Pickup-only supplier stock uses existing Offer/Reservation records. Require disclosed artisan/material/pickup terms, one recipient, authoritative stock hold, no shipping promise. Acceptance: isolated API stock/recipient checks and Desktop/Mobile order through intercepted payment and pickup document. Rollback: retained transport containers; no migration.
