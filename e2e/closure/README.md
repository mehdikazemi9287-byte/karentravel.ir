# Isolated closure browser scenarios
Run only with the existing isolated QA API at 127.0.0.1:18082 and a local built Web preview (KAREN_QA_WEB_URL, default 127.0.0.1:3338). Every browser request to the compiled public API URL is intercepted and forwarded to the isolated API. gateway.invalid is intercepted; no real gateway or SMS transport is used.

`workflows.cjs`: isolated supplier hotel fixture, employee/supplier/backoffice and organization test accounts; real assistant/search services pointed exclusively at QA DBs. Search → assistant hold → checkout → intercepted payment → issue → voucher/trips; support lost response, retry, human response, role boundaries, notification recovery and logout.
`auth-states.cjs`: local OTP capture at /tmp/karen-operational-e2e/closure-otp.json; no real SMS. Registration/invalid-code/verification/profile/retry/redirect/logout/login.
`payment-states.cjs`: isolated payment fixtures in closure-payments.json, local initiation call log and timeout target file; no new initiation after ambiguous timeout, cancellation→verification-only reconciliation.

These reuse the session QA harness and are not standalone production tests. Never copy QA fixture users, prices, OTPs or gateway states into Production. Detailed executed results are in docs/recovery/2026-09-28-independent-closure.json. No stored OTP or signed callback token belongs in Git.
