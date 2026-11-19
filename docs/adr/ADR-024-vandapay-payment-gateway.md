# ADR-024 — VandaPay as KarenSeir payment gateway (2026-11-19)

**Status:** Implemented in code, **disabled** until credentials (owner: VandaPay merchant onboarding).

## Context
Owner decision (1405-08-27): KarenSeir payments go through VandaPay (the group gateway). VandaPay plan:
`vandapay/docs/integration-plans/karenseir.md` (server-side API, hosted checkout, signed webhook, issue only after `succeeded`).
KarenSeir already had a provider-neutral Payment Intent flow (intent → initiate → return/verify → capture → ledger/outbox) wired to ZarinPal.

## Decision
- New `VandaPayAdapter` (backend/app/providers.py) behind the same `ADAPTERS["payment"]` slot. Selected when `VANDAPAY_MODE` ∈ {test, live}; takes precedence over ZarinPal.
- Fail-closed: mode/key prefix must match (`sk_test_`/`sk_live_`), base/return URLs must be HTTPS, otherwise health = `configuration_error` and `/payments/{id}/initiate` returns 503 before any attempt is recorded.
- Initiate: `POST /payment_intents` with `order_ref` = KarenSeir payment intent id, `Idempotency-Key` = intent command id, `return_url` carrying a signed short-lived state (aud `karenseir-vandapay-callback`).
- **Success is decided only server-side:** `GET /payment_intents/{id}` must return `succeeded` with the same amount and `order_ref`. Browser return (`GET /payments/vandapay/return`) and webhook (`POST /payments/vandapay/webhook`, HMAC `VandaPay-Signature`, 300 s tolerance) are only triggers.
- Pending (`processing`, `card_pending`, `unknown`…) → nothing captured, customer can re-check via `/payments/{id}/verify`. Failed/cancelled → intent `failed`.
- Capture reuses the existing ledger path (`commerce.record_payment`, PaymentEvent dedupe, Outbox, trip timeline). **Ticket issuance is unchanged: only after capture.**
- No price/amount is computed in the frontend; the amount is the reservation's bank-payable allocation.

## Not yet (owner decisions / VandaPay side)
- Merchant legal entity + SHEBA (Tazheban?), keys, webhook registration.
- Cancel VandaPay intent when a supplier hold expires (`cancel` operation exists in adapter; hook to hold-release job pending).
- Refunds via VandaPay (partial only for credit share; card share full only — see VandaPay merchant guide §7).
- Hosted page vs embedded checkout (owner: customers should not leave the site → embedded option exists in VandaPay).

## Test evidence
`backend/tests/test_vandapay_payment.py` (7 tests): fail-closed config, idempotent initiate, amount tampering rejected, pending/failed not captured, signed webhook required and outcome re-read from API, cross-user isolation, single PaymentEvent. Full suite: 593 passed, 2 pre-existing failures unrelated (also fail on base).

## Rollback
`VANDAPAY_MODE=disabled` + `docker compose up -d --no-deps api` (ZarinPal/disabled path unchanged).
