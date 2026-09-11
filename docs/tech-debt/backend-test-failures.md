# Technical Debt Register: backend test suite (8 known failures)

Status: registered, not fixed (out of scope for the Search microservice work).
First observed: Search Phase 2 baseline audit. Re-confirmed unchanged in
Search Phase 3 (`256 passed, 6 skipped, 8 failed`, identical test names).

## The 8 failures

**`tests/test_booking_orchestration.py` (6 failures)**
- `test_offer_price_check_booking_payment_fulfillment_and_voucher[flight-attributes0]`
- `test_offer_price_check_booking_payment_fulfillment_and_voucher[hotel-attributes1]`
- `test_offer_price_check_booking_payment_fulfillment_and_voucher[tour-attributes2]`
- `test_offer_price_check_booking_payment_fulfillment_and_voucher[package-attributes3]`
- `test_price_check_expiry_cross_tenant_and_unverified_policy_are_rejected`
- `test_fulfillment_requires_captured_payment_and_safe_document_reference`

Cause: interaction between the supplier-membership/RBAC changes committed
earlier in this project and the test suite's SQLite test database (SQLite
does not enforce the same constraint/permission semantics as the production
PostgreSQL + RLS setup, so a behavior that is correct against real Postgres
surfaces as a test failure here). Not caused by, or touched by, Search Phase
1/2/3 work — `backend/app/main.py`'s booking/payment/fulfillment code paths
were not modified by any Search extraction phase.

**`tests/test_outbox_worker.py` (2 failures)**
- `test_sms_outbox_event_is_picked_up_and_processed`
- `test_missing_sms_provider_fails_closed_not_delivered`

Cause: no SMS provider is configured in the test environment (by design --
the test env never has real provider credentials), and the outbox worker's
fail-closed behavior for that case does not fully match what these two tests
currently assert. Independent of Search; the outbox worker code these tests
exercise was touched once, earlier in this project, for an unrelated
`pending_external` channel guard (commit `dca1051`), not since.

## Why these were not fixed here

Each Search phase (1/2/3) was scoped explicitly to Search extraction and
orchestration, with an explicit instruction to classify rather than fix
pre-existing failures unless a phase's own changes directly touched that
code. No Search phase modified `test_booking_orchestration.py`,
`test_outbox_worker.py`, or the production code they exercise
(booking/payment/fulfillment, outbox/SMS). Fixing them here would mix an
unrelated bug-fix change into a Search-scoped commit, making both harder to
review and roll back independently.

## Recommendation

Open a dedicated, narrowly-scoped follow-up (not a Search-service task) to:

1. Reconcile `test_booking_orchestration.py`'s fixtures/assertions with the
   supplier-membership RBAC behavior as it actually runs against SQLite in
   CI vs. Postgres+RLS in production -- likely a test-fixture fix (adjust
   what the SQLite test session sets up) rather than a production code
   change, but needs a real audit to confirm before touching it.
2. Decide the intended behavior for `test_missing_sms_provider_fails_closed_not_delivered`
   (what `outbox_worker.py` should record as delivery status when no SMS
   provider is configured) and align the implementation and the two
   `test_outbox_worker.py` tests to that decision.
3. Re-run the full backend suite and confirm a `0 failed` baseline, then
   treat any new failure introduced by an unrelated change as a real
   regression from that point on (currently, a new failure is easy to miss
   inside a sea of 8 pre-existing ones).

This is intentionally left as a recommendation, not an action taken in this
phase, per the explicit Phase 3 instruction: "Do not fix them in this Search
phase unless the Search changes directly touch them."
