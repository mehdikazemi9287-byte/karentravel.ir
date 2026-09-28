# Accommodation domain acceptance

Only the isolated operational QA harness is supported. Web localhost:3340; API
localhost:18082. Browser intercepts the compiled public API origin and routes every
request to QA. gateway.invalid is intercepted; no real payment, supplier or SMS.

Prepare /qa/fixtures.json in the established SQLite QA API; run accommodation_fixture.py
inside that QA container. It refuses non-SQLite databases. No production seeding.
Run accommodation-host.cjs and accommodation-discovery.cjs from this repository.
The latter exercises catalog filters and empty state. Host journey tests calendar,
fees, host approval with response loss/retry, checkout, test payment, supplier issue,
voucher and My Trips at desktop/mobile widths. JSON/screenshots remain under
/tmp/karen-operational-e2e. check_accommodation_db.py runs inside QA and verifies
single approval/payment/voucher plus Trip. Harness provisioning is reused, not
included here; these scripts are not generic production smoke tests.

Trip basket: local web :3341 and the same QA API. trip_basket_fixture.py creates one
explicit Mock QA offer in SQLite; trip-basket.cjs verifies customer-authored notes,
real offer linkage, repeat-add idempotency, recheck, reload and offer-detail handoff
at both widths. It does not initiate payment. Backend test additionally changes
stored price and expiry and verifies no silent substitution or duplicate audit.
