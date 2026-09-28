# Live prerequisites — 2026-09-27

Environment: Production read-only investigation; isolated rollback verification; Source documentation only. Reference server 95.38.184.209, repository /home/ubuntu/karenseir-current, HEAD 6494d96a822212d3b06c27cdf13579b651cda3da. Existing release and 42/42, 25/25 QA evidence reused; suites were not rerun.

## Completed and usable

- Deployed frontend image remains afc42e7580e1b9b35190ee8f3e8f6a5aa5598938a79b8bb2947d652eff4d8554 and is healthy. Public homepage and build_info.json returned HTTP 200. Live release_delta.json application hashes match the current source files.
- API /ready returned HTTP 200: database ok, distributed rate limiter, external providers fail_closed. No new runtime, database, Nginx, secret or provider settings were changed.
- Retained rollback image b2fab9f4f9c74c23ea012482b86ee9a30267eb40cb655d16e5bf8ce67fb80a1b was booted in a disposable --network none container; its homepage returned HTTP 200. Original rollback container remains stopped. Its retained Docker health label is not a current running-health claim; the independent boot is the recovery evidence.
- Customers can open the existing HTTP site and its deployed forms. Real OTP delivery, live supplier search and payment are not certified as usable. No new functional release could be prepared without the external inputs below; the healthy existing release was preserved.

## Exact blockers and inputs

1. Domain/HTTPS: the approved primary domain is **karentravel.ir**, recorded in karentravel-master-spec-v3.1-FROZEN.md:14 and the baseline document. Direct DNS queries to 1.1.1.1 (A) and 8.8.8.8 (NS) returned SERVFAIL, No Reachable Authority. Responses identify authoritative REFUSED replies, including 46.245.76.14 and 91.107.249.244. api.karentravel.ir A also returns SERVFAIL. This is not merely an absent local Nginx server_name. Active vhost still serves only the IP on port 80; public TCP 443 returns errno 111 and /etc/letsencrypt/live is absent. Required: access to this domain's registrar/DNS hosting or correction by its owner of the delegation/authoritative zone, then A records for the approved website/API hostnames to 95.38.184.209. No domain was invented. TLS and a public HTTPS callback remain dependent on working DNS.
2. Hotel: running API has no GRS_CLIENT_TOKEN, GRS_BASE_URL or GRS_MONEY_UNIT; GRS_MODE is unset/disabled. The checked project .env, project secret locations, runtime configuration and relevant GRS dry-run directory contain no usable connection supplied for activation. Required: contracted GRS production/test base URL, valid client token, explicit IRR/IRT money unit and any supplier-side IP authorization for this server. Search-only activation does not authorize booking or financial transactions.
3. Flight: FLIGHT_PROVIDER_MODE is disabled. Provider selection has no concrete live flight transport: its generic sandbox adapter explicitly has no authorized transport. Required: selected contracted flight supplier, API specification/search contract, credentials, endpoint and IP allowlist requirements. Credentials alone do not implement an absent transport.
4. Payment/callback: ZARINPAL_MERCHANT_ID and ZARINPAL_CALLBACK_URL are absent; adapter remains disabled. Existing callback route is /payments/zarinpal/callback. Required: valid authorized merchant ID, agreed sandbox/production mode and registered HTTPS callback on the working API domain. The proposed URL https://api.karentravel.ir/payments/zarinpal/callback is conditional on provisioning that hostname/TLS; it is not currently live. No payment request or financial transaction was made.
5. OTP: Kavenegar key/template are present and match the existing local key file; no accidental env-assignment/quote loading fix or valid base64-to-hex key correction was found. Read-only HTTPS account/info requests using GET and POST from the running API both returned HTTP/provider 404, message «متد نامشخص است». Do not misclassify this as proven invalid credentials: the official reference defines 404 as unknown method and 403 as invalid key. No approved test recipient was found in the checked configuration; no OTP was sent. Required: confirm the current API key/account's supported endpoint/access in the Kavenegar console/support, confirm the active Verify/Lookup template, and provide an explicitly approved test mobile number so a single real OTP and delivery status can be verified. No customer phone number or demo fixture number was repurposed as a test recipient.

Official Kavenegar references used only to select the non-sending account probe and interpret errors: https://kavenegar.com/rest.html and https://github.com/kavenegar/kavenegar-python/blob/master/kavenegar.py . A 404 account probe is not proof of SMS delivery failure or success.

## Final checkpoint

Completed: all currently available targeted prerequisite checks and isolated rollback boot.
Verified: current source/deploy delta, public HTTP 200, API readiness, exact DNS failure, safe Kavenegar error, missing live inputs.
Changed: this report and structured evidence only; existing worktree changes preserved.
Production changed: no. No ready runtime change could resolve the missing inputs.
Git HEAD: 6494d96.
Deployment fingerprint: 6494d96a822212d3b06c27cdf13579b651cda3da-worktree-23748b1d4839.
Tests: no repeated suites; targeted probes only.
Functional completion: available checks complete; live commerce remains blocked by the listed external inputs.
Production readiness: existing HTTP Web healthy; no live purchase/OTP readiness claim.
NEXT EXACT ACTION: repair authoritative DNS through the domain account, then provision HTTPS; independently supply the contracted supplier/payment inputs and approved OTP test recipient.
