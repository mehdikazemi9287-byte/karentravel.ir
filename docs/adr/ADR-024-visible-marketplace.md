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
