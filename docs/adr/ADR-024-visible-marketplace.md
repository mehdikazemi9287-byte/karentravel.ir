# ADR-024 — Visible marketplace slices

Explicit user priority supersedes Homepage design freeze: preserve KarenSeir identity,
Vazirmatn and RTL, replace beige/orange/purple homepage treatment with navy/turquoise.
Use the proven current repository and deployment path; do not repeat forensic audit.
Migration 20260928_34 already applied under prior approval; no migration in Slice 1.

Slice 1: visible homepage marketplace, complete service navigation, editorial destination
and accommodation category discovery, prominent assistant prompt handoff, existing
vertical search widget reused. Editorial guides do not claim popularity/rating/price,
and no product cards or availability are fabricated. Assistant drafts require explicit
send; no automatic conversational/transactional operation. Search preserves existing
backend contracts; richer result/booking work remains in subsequent slices.

QA: production build, desktop/mobile browser, tab-specific controls, real route handoffs,
assistant prefill, navigation, public image/asset proof and screenshots. No SMS or money.
Rollback: preserve currently served frontend container/image; frontend-only replacement.
Master gap matrix remains cumulative; unreviewed baseline capabilities are not marked complete.

Slice 2 scope: use existing Offer/recheck/checkout contracts. Show flight number,
carrier, route, duration, stops, cabin, baggage and supplier only from supplied data;
missing stops must never silently mean nonstop. Replace generic empty result dead end
with date changes, editable criteria, transport alternatives and assistant handoff.
Flight landing uses actual search controls. No invented supplier result or hold.

Master autonomous directive is cumulative. Slice 2 also adopts the explicitly requested slogan «تمام سفر، در یک مسیر». Flight facts remain provider supplied; missing stops are unknown. QA uses isolated offers only. No schema change or live financial operation.

### Slice 3 — stay discovery and continuity
Public browser baseline: /hotels only ServiceIntro, /villas category context leads to authentication without usable filter form. Replace /hotels entry with hotel-default search and genuine category/editorial discovery. Accommodation filters/dates/guest count persist through login, property detail, refresh and return. Keep tenant-scoped catalog authorization; no public cross-tenant inventory exposure. Reuse quote/reservation/calendar APIs, no schema change. Render only supplied property amenities/media/rules. Desktop/mobile QA with isolated property + public empty/login handoff, then deploy frontend retaining current rollback.

### Slice 4 — tours and rail
Live browser /tours from homepage at desktop/mobile exposes a generic intro and login gate, without date/party filtering. Complete tour entry, preserve destination/date/party through account and PDP, reuse existing departures/quote/reservation, show supplied itinerary/inclusions only. Rail uses existing homepage search and contracted-offer API; improve rail-specific facts rather than make a parallel inventory model. Keep tenant scope and all external-provider gates. No schema or financial activation.
Slice 4 requires an API delta (not a schema change): optional tour date/party filters use a scoped departure EXISTS with capacity and booking deadline. The date is interpreted as a Tehran calendar day (+03:30), matching displayed departure dates. API test covers midnight boundary, capacity, deadline, invalid party and tenant exclusion. Tour retry command persists across refresh after a lost response. Preview visual review also exposed an auth-hydration race resetting edited catalog criteria; URL initialization is now independent of session loading and controls wait until initialization. No real transactions.

### Slice 5a — restaurant/experience continuity
Live browser verified restaurant editor selects flight because restaurant is absent from options. Search engine filters dated sessions for other leisure verticals but omits restaurant; 27 search application files match live source exactly. Correct category/date filtering, carry actual selected session and guest criteria to PDP/login, display real place amenities/rules and cancellation policy, and retain ticket selection across refresh. Restaurant copy describes scheduled service/admission, not a table assignment unsupported by the current model. No new table-inventory fiction, financial behavior, or migration. Search/API changes are additive/targeted; preserve both old containers when publishing.

Leisure quote/reservation retains only price-check ID and command ID in an account-scoped pending record before sending the booking command. After a lost response, refresh exposes a resume action with the exact original command; it does not silently create a new quote/booking. Backend replay now enforces original PriceCheck.user_id, closing a same-tenant cross-user replay gap. Tests: backend 2 PASS (owner isolation + Tehran date boundary); search 1 PASS across all four leisure verticals. No database migration.

Production search uses Redis (observed). Bump cache-key namespace with the changed date-filter semantics; retain old keys for natural TTL/rollback, never flush Redis. This is a search-only follow-up to the Slice 5a bundle, with frontend/API still built from 9cc109b.

### Slice 5b — pool/sport entry
Replace the legacy pool entry with destination/date/party discovery, embedded results and honest session-condition guidance. Reuse existing leisure detail, recheck and booking APIs; no new inventory model or schema. Validate URL party counts to safe form defaults. Isolated QA pool sessions and public anonymous desktop/mobile verification; retain frontend rollback.

Slice 5b visual gate found a shared search CSS defect: `.result-price .button.primary` consumes --coral, but JourneyShell does not define that legacy token. Browser computed background was transparent with white text (clickability tests alone missed it). Define navy/teal search tokens locally, preserving approved layout. Regression asserts computed opaque teal CTA plus desktop/mobile screenshot review; also covers restaurant and flight result contexts without new booking transactions.

### Slice 5c — attraction entry and ticket conditions
Observed public desktop/mobile attraction route has duplicate h1 and no dedicated search form. Reuse pool discovery form with an explicit service configuration; keep pool route and labels unchanged. Display only API-supplied ticket minimum/maximum ages and entry_rules beside each ticket. These are conditions, not a new age-verification promise. No new API/schema/provider behavior. Verify isolated attraction session-to-booking and pool form regression, then public anonymous journey.

### Slice 5d — event discovery and human inquiry
Public event route has duplicate headings and no inquiry handoff. Add event discovery on shared form and an explicit human inquiry path using existing support/cases API, not a new RFQ/booking model. Product-specific inquiry loads scoped product facts first. Customer receives a support case ID and real messages; no price, capacity, hold or response-time promise. Persist exact pending payload/command per account/service/product for ambiguous response retry. BackOffice already consumes the same cases. All submissions/replies in verification use isolated QA; no production SMS/payment.

QA contract correction: support fields are nullable, but _owned_support_scope requires exactly one trip/reservation. Permit only SERVICE_INQUIRY with both absent; all supplied references still undergo unchanged ownership checks, all ordinary cases still require one anchor. Existing authenticated user ownership, replay payload matching and scoped case listing remain enforced. No schema change. Targeted contract test required before API/worker release.

### Slice 6 — customer case navigation and reply
Public frontend with isolated authenticated API shows support cards with zero links and raw in_progress status. Add scoped case detail and owned customer reply using existing SupportThreadMessage, IdempotencyKey and OutboxEvent tables. Lock case for serialization; replay original response before checking closed state, reject altered payload. Closed/resolved cases remain read-only. No financial decision, schema change or real notification test. Customer→case→reply→Ops and refresh/replay/ownership targeted verification required.

### Slice 7 — generic booking continuity
Public frontend + scoped QA confirms generic result links omit criteria and detail back link drops search. Generic detail command exists only in memory; inline results generate a fresh command each attempt. Share one account-scoped pending booking record across result/detail surfaces, retaining exact price-check/command through ambiguous response and refresh. Disable new recheck/booking until resolved; backend consumed-price-check/ownership gates unchanged. Carry search context in generic detail links and back link; persist explicitly chosen unit count, without inferring infant fares or group pricing. Normalize scoped leisure/support desktop heading size found during visual review. Frontend-only; no real transaction.

Slice 7 follow-up: preserve explicit offer query through ErrorState login redirect (other callers keep existing default). Invalidated price checks remove previous confirmation/continue action and require recheck. If sessionStorage cannot retain the pending command, do not send a booking mutation; display recovery guidance.

### Slice 8 — in-app support response notification
QA baseline has six cases with human replies and zero linked inbox notifications. Reuse notification fanout with optional channel restriction (default unchanged), explicitly web/app only for support response. Add semantic support_reply_received template and case deep link. Add owned, idempotent mark-read endpoint using existing status field; worker must preserve read instead of overwriting it with transport status. UI delivery does not imply reading, shows Persian topics and explicit read action. No external delivery attempt for support response; no migration or production test messages.

### Slice 9 — supplied transport times and contextual recovery
Format valid ISO transport dates with the supplied wall clock and offset; never browser-local conversion or guessed airport timezone. Bare times retain no-zone disclosure, invalid/missing dates remain unavailable. Preserve original ISO in datetime. Share flight/rail renderer; anonymous offer wrapper retains navy/teal and back-to-search context. Notification count describes only the loaded latest50, not all historical unread records. No booking mutation/API/schema change.

### Slice 10 — durable human support reply
Reuse case lock and existing idempotency table for supplied human-reply keys, hashing actor/body and replaying before closed-state guard. Optional header preserves older clients during API-first release; new UI always supplies durable key. Atomic audit/message/in-app notice/outbox; no external channels. New account-scoped Ops composer retains exact case/body/key through ambiguous response/refresh. Storage failure blocks any new reply POST, including existing customer composer. No schema change. Verify response-loss replay produces one message/notice/audit.

### Slice 11 — rental date-range continuity
Public1440/390 accepts reverse rental dates. Validate actual calendar dates and end>=start at entry and shared search before API requests; same-day remains allowed because no new rental policy is inferred. Preserve return for non-flight verticals regardless of inherited one-way flight flag. Clear stale results on invalid rental range, expose truthful corrective error. No inventory/price/booking/backend change.

### Product Slice 12 — flight party integrity through post-booking
Priority supersedes standalone saved-search bug. Close one-way adult flight journey using existing authoritative per-seat contract: search party→detail/recheck units→exact distinct passengers→checkout→isolated payment→manual supplier confirmation/voucher→trips/timeline→cancellation request. Never infer child/infant fares or a return leg from one offer; these requests require explicit separate quote and retain search context. Save/replay criteria in the same slice. Existing supplier/payment/OTP boundaries remain externally blocked in production. No schema or financial policy change. Acceptance requires full isolated browser journey at desktop/mobile, adverse-count/replay/permission tests, public build proof, screenshot comparison. A passing partial checkout is not full-slice completion.

Slice12 self-review: complete isolated flight happy path exposed stale post-request status and no persistent customer request list. Add owner-scoped request history on existing table, enforce owner/hash before replay and prevent multiple submitted requests. Refresh authoritative state after request; retain exact pending request across ambiguous failure/refresh, fail closed if browser cannot persist it. Pending cancellation/refund means review, never completed refund or newly unissued documents. No change to cancellation policy or voucher validity rules.

Operations boundary: an owned customer request must be visible to authorized support staff. Add paginated tenant-scoped review queue and idempotent begin-review action, audited through existing outbox and visible in customer timeline. This only acknowledges review; no cancellation decision, financial approval, refund execution, supplier confirmation or SMS is performed. Unknown statuses remain explicitly unknown.

### Major accommodation journey follow-up (2026-09-29)
Live hotel discovery leads to an authentication wall before any catalog. Add anonymous read-only accommodation discovery/detail using only the existing dedicated karenseir-public catalog identity; never fall back to corporate/consumer inventory or copy offers across tenants. Public output is a strict presentation allowlist without rates, capacity counts or private supplier fields. Authenticated quote/booking remains scoped to the customer's own tenant; absent account entitlement has an explicit recovery path, not a fabricated booking bridge. Gallery/host presentation uses only explicitly supplied presentation fields, with no invented images/ratings. Close durable stay booking response-loss/refresh recovery, storage failure and stale quote handling within the same journey. No schema migration or production seed. Acceptance: tenant-isolation API tests, actual desktop/mobile catalog/detail/recheck/host decision/checkout/trip QA, empty/unavailable public recovery, existing rollback preserved.

### Major Tour journey follow-up (2026-09-29)
Close public program discovery, actual selectable departure/room pricing, durable reservation recovery and full owned checkout/voucher/trip flow. Base tour price retains its existing default double-room contract; other room types require an explicitly supplied integer surcharge (including explicit zero), never an inferred free upgrade. Expired departures are not selectable. Anonymous projection uses only the existing public catalog identity and program/date presentation, not private rates or supplier payloads. No cross-tenant purchase entitlement is inferred. Price expiry, changing quote inputs and storage failures fail closed. Acceptance: room/deadline/tenant/replay API checks plus desktop/mobile isolated customer journey through distinct travellers, payment test destination, voucher and after-sales tracking. No migration or real financial/SMS operation.

### Major Train group journey follow-up (2026-09-29)
Public frontend + isolated QA proved two searched adults produce a one-seat inline quote and one-seat detail at both widths. Propagate the adult party through inline and detail quote→reserved units→distinct checkout travellers and server-calculated total. Add optional train_party to the existing price-check contract with the same count validation as flight; no child/infant/roundtrip fare or seat-number allocation is inferred. Preserve generic durable booking and after-sales paths. Acceptance includes full isolated two-person rail checkout/payment/voucher/trip/Operations journey and unsupported-party recovery; flight validator regression only, not unrelated suites. No migrations or real financial/SMS operations.

### Major scheduled restaurant admission journey (2026-09-29)
Public frontend + isolated QA reproduced validating ticket A, editing the input while validation was pending, then sending ticket B for redemption. Both widths reproduced; redemption was intercepted and never executed. Close the whole restaurant scheduled-ticket journey: durable booking, group QR context, supplier validation bound to the checked ticket, single-use admission and customer timeline. Add a body-based no-store validation route so the active UI no longer sends the bearer QR in a URL. Retain the legacy GET contract and existing time/permission rules; do not invent table inventory or early-admission policy. Show server-backed product/place/session and immutable booked item quantities; one generated QR covers the reservation, not one separately allocated seat/person. Add optional expected_ticket_id to redeem for fail-closed mismatches. Customer QR loading failures remain recoverable without hiding other ticket information. All tests use isolated fixtures and non-financial adapters; no Production redemption, payment, SMS or migration.
