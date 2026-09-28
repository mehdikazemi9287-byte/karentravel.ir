# Final production readiness — 2026-09-28

Baseline web b96351d5981f, HEAD 6494d96; source hashes match runtime. Target: Source → isolated QA → Production API/worker only; preserve web/search, design and all rollback containers. No migration, real payment, SMS or provider booking authorized/executed.

SUPERVISOR GATE: ALLOW. Existing quote/callback/OTP evidence reused. Scoped defects: different command keys can create multiple payment intents per reservation; an ambiguous initiate timeout permits another external initiation; exception stack logging could expose provider details. Fix by reservation-lock reuse, durable initiation attempt marker and sanitized event logging. No architecture change or duplicate feature. Rollback uses retained API/worker containers. Acceptance: targeted duplicate/retry/timeout tests and affected isolated payment browser journey only.

External baseline: authoritative DNS remains SERVFAIL/REFUSED, TCP443 refused; GRS endpoint/token/unit and payment merchant/callback absent. Kavenegar configured but delivery unverified; no new SMS attempt. Payment production stays disabled.

## Completed independent work

Payment endpoints now serialize on the reservation, reuse the existing intent across different command keys and the checkout endpoint, and reject mismatched payable amounts. Initiation writes a durable attempt marker before contacting the provider. A successful retry returns the same redirect; a timeout/crash/ambiguous outcome requires reconciliation rather than another initiation. This fail-closed case intentionally requires operations assistance if no authority was returned. There is no automatic resend or automatic charge. Disabled providers do not consume an attempt. Unexpected provider exceptions no longer add stack details at the payment call site. No new mock provider, migration or speculative supplier wire format was introduced.

QA: 4 new payment guard tests + 4 affected callback/verification/cancel tests passed, isolated network-none storage. Desktop/mobile affected payment browser flow passed against the isolated actual API/DB and intercepted gateway.invalid destination. Initial browser startup returned socket hang-up before login; after API readiness it passed. Prior 42/42, 25/25 and unrelated vertical suites not repeated. Existing callback state/authority/amount checks, single captured event and server-owned voucher/confirmation boundaries preserved. Payment confirmation never fabricates supplier confirmation.

OTP targeted review reused the existing Kavenegar POST Verify/Lookup implementation, numeric message-reference validation, one send attempt, stored validated mobile recipient, challenge hash/persistence on accepted send, and rollback on rejection. Key/template are configured; prior account/info 404 means unknown method, not proof of a bad credential. No repeat provider probe or SMS send was warranted without corrected account access and an authorized recipient.

## Adapter inventory and contract boundary

| Adapter | Classification | Exact limit/input |
|---|---|---|
| GRS hotel | IMPLEMENTED-BUT-NO-CREDENTIAL | Search/transport exists. Need GRS_BASE_URL, GRS_CLIENT_TOKEN, confirmed GRS_MONEY_UNIT=IRR or IRT, server IP allowlist, original versioned search/rate/guest/policy/hold/book/confirmation/voucher contract. Live booking integration is not claimed implemented solely because a generic transport exists. |
| Flight, rail, bus external ports | MISSING | Disabled external ports/generic sandbox do not implement a contracted live carrier. Need named supplier, base URL, auth method/credential, versioned search/availability/reprice/hold/book/status/voucher and idempotency/reconciliation contract. |
| Internal supplier pool | CONNECTED | Real internal DB connection; public search flight/hotel/train returned zero entities, no fake live offer. This does not prove external inventory. |
| Manual tour/accommodation/car/restaurant/venue/sport/attraction/guide/transport/handicraft | CONNECTED | Internal supplier allocation/fulfillment only. Require real contracted stock, price, capacity, policy, validity and responsible supplier account. Physical service/delivery not simulated in production. |
| Generic mock modes | MOCK | Existing DisabledMockAdapter fails closed; no successful fabricated inventory or booking. No new mock integration added. |

## Four owner actions only

1. **Domain — Talahost DNS panel for karentravel.ir, and IRNIC delegation if the current hosting account no longer owns the zone.** Parent .ir returns dns1.talahost.com, dns2.talahost.com, dns3.talahost.com, dns4.talahost.com; these delegated servers return REFUSED. Activate/restore the authoritative `karentravel.ir` zone on that service, keeping delegation consistent. Set `@ A 95.38.184.209` and `api A 95.38.184.209`, TTL 300; remove conflicting A/AAAA for these two names if present. No replacement nameservers are invented. Verify authoritative SOA with AA/NOERROR and both A answers through 1.1.1.1 and 8.8.8.8. Then the prepared proxy configuration can be activated with valid certificates for karentravel.ir and api.karentravel.ir, HTTPS redirects, canonical frontend/API URLs and loopback upstream bindings. Final test: trusted-certificate HTTPS web root and API /ready; payment must remain disabled until this passes.
2. **Supplier — contracted supplier's technical/account panel.** Supply the hotel GRS values and versioned contract above, or one selected live flight/rail supplier with the exact equivalent API/auth/allowlist contract. Allowlist source IP `95.38.184.209` where required. Specify one genuinely available offer, authoritative price/currency, cancellation conditions and permission for a controlled hold/booking. Verify search→availability→reprice read-only first, then authorized booking/status/voucher; missing transports must be implemented from that real contract, not guessed.
3. **Payment — authorized ZarinPal merchant panel.** Supply `ZARINPAL_MERCHANT_ID`, approved mode, and register `https://api.karentravel.ir/payments/zarinpal/callback`. Keep `ZARINPAL_MODE=disabled` until HTTPS passes. After verified supplier availability, explicitly approve the particular real purchase/maximum amount and payer; no present instruction authorizes a real charge. Verify returned Authority against the stored intent and server amount, server-side verification/RefID, one payment event, and replay without a second charge/booking.
4. **OTP — Kavenegar account/Verify template panel or support.** Confirm this account/API key may POST to `https://api.kavenegar.com/v1/{API_KEY}/verify/lookup.json`, confirm the active `KAVENEGAR_OTP_TEMPLATE` and token/receptor policy, and provide one explicitly authorized test mobile. Provision secrets through protected runtime secret files, never Git/chat/logs. Then perform one send, confirm real delivery and message reference, and verify the persisted challenge once. The approved support number is not an approved SMS test recipient.

## Final readiness interpretation

| Criterion | Result |
|---|---|
| DOMAIN_HTTPS | BLOCKED |
| SUPPLIER_REAL_DATA | BLOCKED |
| OTP_DELIVERY | BLOCKED |
| PAYMENT_REAL | BLOCKED |
| REAL_SEARCH | BLOCKED |
| REAL_BOOKING | BLOCKED |
| VOUCHER | BLOCKED — real supplier document |
| CUSTOMER_ACCOUNT | PASS — existing internal API/DB and isolated role/browser acceptance; real OTP access blocked |
| TRIP_OPERATIONS | PASS — existing internal audit/timeline/operations acceptance; no real supplier change claimed |
| DESKTOP | PASS — affected isolated payment path; real Golden Path blocked |
| MOBILE | PASS — affected isolated payment path; real Golden Path blocked |
| SECURITY_SMOKE | PASS — bounded secret/anonymous-access checks; HTTPS remains separately BLOCKED |
| ROLLBACK | READY — original rollback retained plus pre-readiness API/worker images |

Security scope: configured secret literals absent from pending source files, deployed frontend static assets and the sampled recent API log; no private key blocks in pending files. Valid anonymous requests: production dev-login 404, account 401, backoffice records 401, internal pool 401. This is not a full penetration test or a claim that HTTP is secure. No localhost/internal URL was introduced into the unchanged public frontend. Runtime flags remain fail-closed. No actual end-to-end production purchase, supplier issuance or OTP delivery was performed. The full real Desktop/Mobile Golden Path is dependency-blocked and must not inherit PASS from isolated fixtures.

Final state: **EXTERNAL_BLOCKED**.

Deployment: API/worker image `sha256:8c4e91fb32f2000a78a23bc92f79947ace607726cb8067a6000bc08c4291c772`; web fingerprint remains `b96351d5981f`, search image unchanged. Four services healthy; API source hash matches runtime. Both pre-readiness containers and all original pre-handicraft rollback containers/images verified present. No rollback executed, no DB migration.
