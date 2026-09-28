# Customer journey closure — 2026-09-27

Environment: Source/Preview then explicitly authorized Production Web. Baseline HEAD 6494d96; current public release delta matches source. Preserve pre-existing changes and backend/debug_voucher.py. Browser traversed 53 visible-link destinations. Confirmed issues: simulated hotel/pricing/credit/comparison content, mock trip/service/support links, unrelated destination links, internal panels exposed as collaboration pages, unhelpful auth gates and raw technical wording. User confirmed support number 09191258009 in this conversation; no other phone/email/messenger is verified.

Scope: retain approved homepage geometry, imagery and palette; replace fabricated inventory with clearly editorial destination guidance; repair catalogue, destination, contact/support, authentication and empty/error flows; keep real authenticated operations. Do not fabricate prices, purchases or contact delivery. Remove public access to demo booking confirmation/trip branches. No backend/schema change.

Acceptance: browser review of changed paths/actions, no mock prices/success, all customer links have meaningful destinations, phone links use the confirmed number, honest unavailable-service states, desktop/mobile bounds and visual review. Build/lint for changed files only; no old 42/25 suites. Release from isolated context with known application changes and provenance. Retain current Web image/container for rollback.

## Source / Preview QA

- Updated the verified telephone to 09191258009 (`tel:+989191258009`) via shared configuration; no email/messenger ownership or delivery claim.
- Preserved homepage layout, images and palette. Replaced displayed mock hotel/package prices, ratings and wallet balance with destination guidance and comparison criteria; corrected the Yazd caption.
- Replaced demo services/nearby/support, removed fake booking success and mock trip/manage-booking fallbacks. Added meaningful service groups, destination guides, contact, terms and privacy guidance. Existing real UUID booking/timeline components remain available behind authentication.
- Added customer actions to unavailable/auth/empty states, cleaned search copy, normalized Persian/Arabic phone and OTP digits, blocked duplicate submissions and malformed consumer phone numbers.
- Preview crawl: 65 desktop/mobile observations, no page errors, horizontal overflow, missing routes or detected mock/technical copy. Delta interaction review: 33 checks including all 12 search tabs, hotel form → real empty search → verified support, phone normalization/invalid-input checks without sending OTP, responsive screenshots. Visual QA found a mobile support-strip contrast issue; CSS corrected before release. Yazd image was inspected after scroll and loads correctly (full-page screenshot lazy-loading artifact).
- Isolated Docker production build includes successful TypeScript validation. Direct worktree `tsc` saw an old `.next/dev/types` Shell-export artifact; clean release build does not contain that stale generated file. Targeted ESLint has zero new findings; seven existing effect-rule errors and one existing img warning were reproduced from HEAD in the same five files. No lint rules disabled.
- Previous 42/42 and 25/25 suites were not repeated. No backend, database, permissions, DNS, Nginx, financial or SMS operation performed.

## Remaining external inputs

Reuse [live prerequisite evidence](2026-09-27-live-prerequisites.md): working domain delegation/DNS access for karentravel.ir, then HTTPS; contracted hotel GRS endpoint/token/currency; selected flight supplier contract/specification/credentials and live transport implementation; authorized ZarinPal merchant/mode/registered HTTPS callback; Kavenegar endpoint/account/template confirmation and separately approved delivery-test recipient. Support number approval does not authorize a test SMS.

## Release / rollback

Publication is authorized by the user for these Web changes. Candidate application hashes and fingerprint are recorded in the associated customer evidence JSON and public release_delta.json. Previous public image afc42e7580e1b9b35190ee8f3e8f6a5aa5598938a79b8bb2947d652eff4d8554 will be retained as `karenseir-frontend-pre-customer-20260927`; original `karenseir-frontend-pre-closure-20260925` is preserved too. No Git reset, removal of user files or overwrite of pre-existing work.

## Final checkpoint — 3/3

Completed: authorized Web release and customer journey closure. Public browser review: 67 route/viewport observations, no page errors or horizontal overflow, all observed routes HTTP 200. Final mobile support contrast checked after correction. API readiness HTTP 200. Current Web healthy.

Git HEAD: `6494d96a822212d3b06c27cdf13579b651cda3da` (existing dirty worktree retained; no commit/reset).
Deployment fingerprint: `6494d96a822212d3b06c27cdf13579b651cda3da-worktree-b837ab14ea65`.
Image: `sha256:9fcfee1030d377870895d94f233aa48e7534546dda4691c2b128a7f3be82be56`.
Production changed: Web container only. Runtime image corresponds to the recorded application file hashes.
Rollback: retained stopped container `karenseir-frontend-pre-customer-20260927` at `sha256:afc42e7580e1b9b35190ee8f3e8f6a5aa5598938a79b8bb2947d652eff4d8554` verified; original pre-closure rollback also untouched. To recover, stop/rename the current `karenseir-frontend-1`, rename `karenseir-frontend-pre-customer-20260927` to `karenseir-frontend-1`, start it, and check health/build_info. Do not delete either previous image. Automatic rollback was prepared but was not needed.

Functional completion: public guidance, service/destination navigation, honest unavailable states, contact, support and login guidance are usable. Real sale and authenticated delivery remain blocked by the exact external inputs above. A displayed phone link is not a claim that a call was placed or answered.

QA evidence: [customer evidence](2026-09-27-customer-evidence.json). Application Source/build hash comparison and git diff whitespace check passed. Documentation evidence values checked against actual deployment and browser results. Existing user/backend debug file and previous test edits preserved.
NEXT EXACT ACTION: supply the external DNS/provider/payment/OTP inputs; do not repeat the completed public-route review or prior 42/25 suites.
