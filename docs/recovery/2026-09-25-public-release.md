# Public Web release — 2026-09-25

Target: Production Web at http://95.38.184.209. User explicitly authorized deployment; retain current healthy recovered Web as rollback. Source HEAD 6494d96 plus the four application files matched against existing E2E evidence. Build context is tracked HEAD plus only those four changes and public provenance metadata; unrelated user files are excluded. No API/DB/worker/Nginx/configuration of external providers is changed.

Build configuration: NEXT_PUBLIC_SITE_URL=http://95.38.184.209, NEXT_PUBLIC_API_URL=http://95.38.184.209:8000, ALLOW_HTTP_PREVIEW=1 for the existing HTTP endpoint only. Deployment fingerprint includes an explicit worktree-delta label and SHA256 manifest.

Acceptance: fresh public-config build, brief candidate/public browser smoke (homepage/login/register/search), no JS/asset failures, correct public API origin and provenance; container health. Existing 42/42 and 25/25 are not rerun. Rollback: stop failed new Web, preserve it, rename/start previous healthy Web with original port/network/environment.

Confirmed external limitations: Nginx config names only the existing public IP and listens on 80; TCP 443 returns ECONNREFUSED. No configured production domain/TLS was found in the active vhost. API is ready with external_providers=fail_closed. Kavenegar key/template are present but delivery is unverified. GRS mode/token/base URL/money unit and ZarinPal mode/merchant/callback are absent in running API configuration. These prevent live commerce activation, not replacement of the existing HTTP Web. No real financial transaction or OTP send will be performed.

Status: DEPLOYED_SMOKE_PASS.

## Final checkpoint

Production Web deployed successfully. Eight public-browser checks passed after replacement: homepage, register, login and search at 1440/390 widths; HTTP 200, no JavaScript/asset request failures, RTL/fonts present, no horizontal overflow. Public search API returned HTTP 200 on both viewports. Consumer login no longer requires an organization and its registration link is visible. API, Worker, Assistant and Search remained healthy. No real OTP send, provider purchase or financial transaction was performed.

Image: `sha256:afc42e7580e1b9b35190ee8f3e8f6a5aa5598938a79b8bb2947d652eff4d8554`. Fingerprint: `6494d96a822212d3b06c27cdf13579b651cda3da-worktree-23748b1d4839`. Rollback container `karenseir-frontend-pre-closure-20260925` remains stopped with image `sha256:b2fab9f4f9c74c23ea012482b86ee9a30267eb40cb655d16e5bf8ce67fb80a1b`; rollback was not needed. It retains original port/network/environment.

Build used the existing tested four-file application delta with public HTTP origins, not the QA image. No API/DB/worker/Nginx or external-connection configuration changes. The 42/42 backend and 25/25 browser suites were not rerun.

Remaining live-commerce limitations are evidenced configuration states, not passing smoke claims: OTP `configured_not_verified` (Kavenegar credentials/template present, delivery not tested); hotel/flight/payment adapters `disabled/not_connected`; GRS token/base/money-unit and ZarinPal merchant/callback absent. Active Nginx vhost uses only the IP on port 80; public port 443 refused TCP connection. Enabling payment additionally requires an explicit HTTPS callback under the existing adapter contract. No domain was invented and no credentials were fabricated.

Evidence: `2026-09-25-public-release-evidence.json`. Functional outcome: frontend fixes are live on the existing HTTP site; live OTP delivery, supplier inventory and payment readiness are not certified.

Rollback command sequence if required: stop `karenseir-frontend-1`; rename it to an unused failed-release name; rename `karenseir-frontend-pre-closure-20260925` to `karenseir-frontend-1`; start it and verify health/public HTTP. Do not delete either image or container before the release is accepted.
