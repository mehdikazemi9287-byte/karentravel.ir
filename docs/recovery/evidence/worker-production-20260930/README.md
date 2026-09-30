# Approved Worker-only release 2026-09-30

Scope: Production Worker4d9f0c3 only. Before/after snapshots and promotion log record actual state; original Worker retained as rollback. Existing API/Web/search/DB container identity and schema/role/ACL digest compare equal. Worker healthy with zero restarts beyond prior180s crash cycle; no new log errors.

Public smoke is anonymous/read-only Chromium Desktop1440/Mobile390. Checkout confirms login gate, not a real reservation. Fresh full booking journey is isolated Preview3378/API18082 with labeled QA fixtures, intercepted gateway.invalid, supplier UI issuance and downloaded voucher, recovery/back/refresh. No real financial/SMS effect. Full journey is not deployed Production hotel evidence.

Rollback, only if regression: stop canonical Worker, rename it to a distinct failed-release name, rename karenseir-worker-1-pre-reaper-guard-4d9f0c3 back to karenseir-worker-1, start it. This restores old behavior including its known permission crash; no DB reversal needed. Do not replace API/Web or run compose over unpublished root source. Original container ID is in result.json/before.json.

QA: fresh deployment guards/210s observation/public browser smoke/isolated booking journey passed; JSON parsed and git diff --check passed. Evidence collection initially needed SQL shell quoting correction; read-only query only, no database mutation. Mobile is Chromium emulation, not physical-device testing. Schema35, hotel publication, real supplier/payment/OTP and reservation auto-expiry remain outside this release.
