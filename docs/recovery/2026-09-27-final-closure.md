# Karen Travel implementation closure — 2026-09-27

Production reference: http://95.38.184.209 — HEAD `6494d96a822212d3b06c27cdf13579b651cda3da`, preserved dirty worktree. Release `6494d96a822212d3b06c27cdf13579b651cda3da-worktree-b96351d5981f`. This is an HTTP/IP preview, not a verified live sales launch.

## Implemented and released

| Scope | Actual behavior | Verification and limit |
|---|---|---|
| Customer search → booking | Server quote/price acceptance, availability, owned passengers, hold, policy acknowledgement, funding, invoice, payment preparation/recovery, supplier issuance, authenticated voucher and My Trips | Desktop/mobile isolated API+DB E2E; gateway.invalid intercepted. No real provider/payment claim. |
| Customer account | Actual owned trips/bookings/passengers/payments/profile/support/notices/timeline APIs; resume checkout and issued document download | Stage 1–3 evidence reused; live OTP still unverified. |
| Trip operations | Permissioned changes, audit/outbox, customer timeline/notice infrastructure | Stage 4 isolated E2E; recording a change does not amend an external supplier reservation. |
| Admin/Ops | Tenant-scoped customers/bookings/trips/payments/refunds/suppliers/support/changes/notices/audit records | Stage 5 permission/tenant tests and browser evidence. No real refund executed. |
| Organization/agency/supplier | Owned organization dimensions, agency hierarchy, supplier allocations and fulfillment | Stage 6 isolated role E2E. No production credit/contract granted. |
| Train | Contractual route/date/seat allocation, one traveller per seat | Isolated supplier-to-customer booking flow; live rail API external-blocked. |
| Tour | Published departures, authoritative room supplements and capacity, hold expiry | Isolated full payment/issue/voucher/trips journey. |
| Accommodation | Actual unit/date/guest quote, seasonal prices, overlapping reservation capacity | Isolated full journey; no invented production inventory. |
| Car rental | Fixed-interval supplier allocation and explicit deposit/licence/insurance/mileage terms | Isolated full journey; not a live fleet calendar or automated licence validation. |
| Restaurant/QR | Real ticket selection/quotas, issued-only QR, supplier ownership and single-use admission | Isolated full journey; QR rendering/manual code entry tested, physical camera not tested. |
| Event hall | Whole-venue allocation overlap guard, inquiry-only venues cannot be sold | Isolated full journey. |
| Pool/sport | Frozen product/session entry requirements and policy acknowledgement | Isolated full journey. |
| Attraction | Session deadline enforcement, correct ticket-selection handoff, printable QR | Isolated full journey. |
| Guide | Dated group allocation, language/meeting/inclusion terms and group-size limit | Isolated full journey; supplier-declared terms, not licence certification. |
| Tourist transport | Exact route/date, per-vehicle capacity, pickup/dropoff/luggage/accessibility terms in detail and voucher | Isolated full journey; public changed routes verified. |
| Handicraft | Pickup-only stock, one recipient, actual held quantity, payment preparation, supplier-issued pickup document | API/search tests and full desktop/mobile E2E. Document issuance is explicitly not physical delivery. No shipping service. |

Approved homepage visual identity preserved. Guide/transport homepage actions connect to the service search pages. Booking management displays the verified refund estimate in customer language; no raw JSON and no claim that a requested refund has happened.

## Customer links

- [Home](http://95.38.184.209/) · [Services](http://95.38.184.209/services) · [Contact](http://95.38.184.209/contact) · [Support](http://95.38.184.209/support)
- [Tours](http://95.38.184.209/tours) · [Accommodation](http://95.38.184.209/villas) · [Car rental](http://95.38.184.209/car-rental)
- [Restaurants](http://95.38.184.209/restaurants) · [Event halls](http://95.38.184.209/events-venues) · [Pool/sport](http://95.38.184.209/pools-sports) · [Attractions](http://95.38.184.209/attractions)
- [Guides](http://95.38.184.209/travel-guides) · [Transport](http://95.38.184.209/tourist-transport) · [Handicrafts](http://95.38.184.209/handicrafts)
- [Account](http://95.38.184.209/account) · [My Trips](http://95.38.184.209/trips) — require customer authentication; live OTP delivery remains unverified.

Public browsing, truthful availability/empty states and the approved telephone link `09191258009` are available. Displaying a contact number does not prove a call was placed or answered. Production authenticated buying is not claimed usable until the external gates below pass.

## Exact external gates

| Gate | Existing evidence | Required input |
|---|---|---|
| Domain/HTTPS | Baseline authoritative karentravel.ir DNS SERVFAIL/REFUSED; current port 80 preview; HTTPS config prepared, inactive | Registrar/DNS control and working delegation/records, then valid certificate/HTTPS activation |
| Hotel GRS | Required endpoint/token/confirmed currency and original wire specification absent | Contracted base URL, token, IP allowlist, money unit, versioned guest/pricing/policy/hold contract |
| Flight/rail providers | No selected usable live integration contract/credentials | Named contracted supplier, authoritative API specification, credentials and allowlist |
| Payment | No approved live merchant/canonical HTTPS callback; tests intercepted | Authorized ZarinPal merchant/mode and registered HTTPS callback; no real charge requested |
| OTP | Key/template configuration exists; safe account/info probe returned provider 404 unknown method; no delivery proof | Confirmed Kavenegar endpoint/account/template and separately authorized delivery-test recipient |
| Manual service sales | No test inventory inserted in production | Real contracted supplier allocations, prices, capacity, terms and authorized fulfillment accounts |
| Outbound SMS/push | Internal outbox/in-app infrastructure exists; external delivery not demonstrated | Valid delivery configuration/contracts and authorized recipient/device |

## QA and rollback

Evidence: [implementation evidence](2026-09-27-implementation-evidence.json), [operational change record](2026-09-27-operational-closure.md), and repository targeted delta tests. Earlier 42/42 and 25/25 suites were not repeated. Prior media environment failures remain QA_ENV_FIXED with isolated writable temporary storage; production filesystem permissions unchanged.

Final production API, worker, web and search are healthy; public release fingerprint matches. Retained containers `karenseir-api-1-pre-stage7-handicraft`, `karenseir-worker-1-pre-stage7-handicraft`, `karenseir-frontend-1-pre-stage7-handicraft`, `karenseir-search-pre-stage7-handicraft` and their images are present. Rollback is available by stopping/renaming the current affected containers, restoring these prior names and starting them, then checking health/fingerprint. Rollback execution was not needed or tested by disrupting production. No database migration, deletion, financial transaction or real SMS was performed. The original worker legacy-hold cutoff was preserved.

Readiness: INTERNAL_IMPLEMENTATION_VERIFIED=true within the listed acceptance scope; PUBLIC_BROWSING=true; REAL_SALES_READY=false; LIVE_PROVIDER_READY=false; HTTPS_READY=false; LIVE_PAYMENT_VERIFIED=false; OTP_DELIVERY_VERIFIED=false. Physical QR scanning, actual supplier amendments, physical goods delivery and real financial refunds are not claimed verified.
