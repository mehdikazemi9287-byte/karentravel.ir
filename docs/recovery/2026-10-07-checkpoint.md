# KarenSeir / Karen Travel — checkpoint 2026-10-07

## Where things are
- Server: `ubuntu@95.38.184.209` · live site `http://95.38.184.209` (nginx :80 → frontend :3000, API :8000)
- Source of truth: git worktree `~/ks-checkline-work/src`, branch `feat/checkline-hotel-catalog-20261006`, HEAD `f1f37d7`
- `~/karenseir-current` (51 uncommitted files) is NOT the working tree — never modify it (only used to run Playwright scripts as `./.ks-ui-check.mjs`, then delete)
- Helper scripts / data: `~/ks-checkline-work/` (ZIP extracted in `zip/`, reference inputs in `ref/`, OSM export in `osm/`)

## Released on Production
- Frontend `karenseir-current-web:release-f1f37d7` (container `karenseir-frontend-1`)
- API `karenseir-current-api:release-e3ac8f4` (container `karenseir-api-1`), DB alembic `20261015_46`; worker and db containers untouched
- Data: 799 CheckLine hotels (586 published), 76 tours (59 published), 165 past dates, 6,389 hotel images, 15 visa guides, 50 countries, 1,503 airports, 489 airlines, 72 old-page routes; price null / RateAvailable false / Bookable false
- Rollback material (stopped containers): `karenseir-frontend-1-prev-3c2653f`, `-prev-1103a51`, `-prev-e3ac8f4`, `-prev-d2ba674`, `karenseir-api-1-prev-352684d`; DB backups `~/backups/release-full-20261007T1037Z/` (verified by full restore); rollback script `deploy/full-release-46/rel_rollback.sh`
- Frontend-only deploy: build from `git archive HEAD` with `NEXT_PUBLIC_API_URL=http://95.38.184.209:8000 NEXT_PUBLIC_SITE_URL=http://95.38.184.209 ALLOW_HTTP_PREVIEW=1`, stop+rename `karenseir-frontend-1`, `docker run -d --name karenseir-frontend-1 --network karenseir_default -p 3000:3000 --restart unless-stopped <image>`

## Approved design
- Reference image (approved look, cream / plum / coral): server `~/karenseir-current/artifacts/C1A7A5F8-5DDC-426E-B4F5-4C05BBDC7E3F.jpg` (729px); higher-res copy of the same render `~/ks-checkline-work/karenseir-reference.jpg` (864px; Mac `~/Downloads/karenseir-reference.jpg`)
- Figma: file `Ei8MUR9VN2yCX6BLOpvTXm` ("KarenSeir — Desktop Homepage", node 44:3). The exported code of that node is `components/marketplace/ApprovedFigmaHome.tsx`
- Homepage code: `components/marketplace/ApprovedFigmaHome.tsx` (header), `ApprovedHomeLower.tsx` (hero, mosaic, trips, assistant, compare, organisation, services strip, light footer), styles appended to `approved-figma.css` (`kh-*`)
- Photos cut from the reference render: `public/images/approved-figma/ref*.jpg`, produced by `deploy/candidate-qa/crop.mjs`

## QA
- Scripts in repo `deploy/candidate-qa/` and `deploy/full-release-46/`: `homeqa.mjs` (homepage, 3 widths), `prodqa.mjs` (read-only production smoke), `siteqa.mjs`, `refqa.mjs` (candidate, sign-in flows), `side.mjs` (reference next to the site), `liveaudit.mjs` (images, data wiring, crawl)
- Last results on Production: homeqa 13/13 ×3 widths, prodqa 35/35 desktop+mobile, live audit: 299 sampled images load, API totals = DB, 235 links crawled / 0 dead, 0 script errors, 0 API 5xx
- Backend tests: 440 passed, baseline 13 failed + 1 error (`~/ks-checkline-work/base.txt`)
- Candidate (loopback only): web `ks-cand37-web` :3396, API `ks-cand37-api` :18137, DB `ks_cand37` in `ks-catalog-scratch-pg`

## Screenshots
- Server: `~/ks-checkline-work/shots/prod3/` (final side-by-side), `shots/home/`, `shots/audit/`
- Mac: `~/Desktop/karenseir-final/` (`final-desktop.png`, `final-mobile.png`, `*-site.png`)

## Open items
1. Figma not readable from the agent session: the Figma MCP server is connected but exposes only documentation/skill resources; its design tools (get_design_context, get_screenshot, get_metadata) are not offered to the session, so no value was re-read from Figma. Needs the Figma tools enabled/authorised in Claude Code.
2. Original photo files (hero arch + traveller, trip photos, organisation devices, destination tiles) and the sun-and-road logo: only the 864px render exists; current photos are 2x upscales of crops.
3. Real social links, app-store links and the 021 phone number: not available; app badges say «به‌زودی», social icons omitted.
4. Prices / ratings shown in the render are not displayed (no live rates). «پشتیبانی ۲۴ ساعته» not claimed.
5. Search fields show default values (تهران / شیراز) instead of the render's «از کجا؟ / به کجا؟» placeholders.
6. `/search/results` uses its own minimal top bar (no shared header/footer) — as before the release.
7. Admin panels on Production were checked only up to the sign-in wall (API answers 401 to anonymous); signed-in panel QA exists on the candidate only.
8. Data: facility-group labels of 586 hotels (not in the ZIP), blog text, live rates, 13 draft hotels with a review note, proposed duplicate pairs awaiting review, image rights of checkline.travel hot-links unverified.

## Continue after /clear
«checkpoint را از ~/ks-checkline-work/CHECKPOINT.md روی ubuntu@95.38.184.209 بخوان و از همان‌جا ادامه بده»

## Panels round (2026-10-08, candidate only — Production untouched)
- Shared panel kit: `components/panel/PanelKit.tsx` + `panel.css` (shell, loader, table, states; site palette), `CustomerPanel.tsx`, `OrganizationPanel.tsx`.
- Customer routes: `/account` (overview), `/account/profile|bookings|visa|payments|refunds|wallet|notifications|support`. Organization routes: `/organization` (overview), `/organization/members|requests|policy|structure|credit|bookings|billing|reports`, `/employee` inside the same shell.
- Backend added in `app/enterprise.py` (no migration): `GET/POST /enterprise/organizations` (tenant admins), `POST /enterprise/organizations/{org}/members`, `POST …/members/{uid}/remove`, `GET …/policy`, `GET …/summary`; members list now returns e-mail. Tests `tests/test_org_panel.py`.
- Removed an invented figure: `/me/dashboard` returned a constant `credit_available`; it is now null.
- QA: `deploy/candidate-qa/panelqa2.mjs` (26 checks × desktop/mobile). Candidate web image `checkline-cand50`.
- Marked unavailable (no real model/credential): online visa application (no visa product), wallet top-up (no gateway), SMS/push, payroll deduction, organization-level statement/settlement, cost report.
- NEXT: Partner/Agency and Supplier panels into the same shell (`/agency`, `/supplier` exist as single pages); organization credit account creation UI for finance; then release decision.

## Panels round 2 (2026-10-08, candidate only — Production untouched)
- All five areas share `PanelShell`: customer (12 sections), organization (11), agency (10, `components/panel/AgencyPanel.tsx`), supplier (10, `SupplierPanel.tsx`), admin (`AdminPanel.tsx`: `/admin/organizations`, `/admin/audit`; `/admin`, `/admin/partners` re-housed).
- Backend added (no migration): `GET /enterprise/organizations/{org}/audit|statement|credit`, member permissions in the members list, `GET /admin/audit-events`.
- QA: `deploy/candidate-qa/panelqa3.mjs` — 20 checks × desktop/tablet/mobile incl. API authorisation matrix. Candidate web image `checkline-cand51`. `panelqa2.mjs` is superseded (its credit expectation predates the credit account now on the QA organization).
- Still unavailable by design (no real model / credential): online visa application, wallet top-up and online settlement (gateway), SMS/push, payroll deduction, agency copies of customer vouchers, hotel rates for catalogue hotels.
- Signed-in panel QA has not been run on Production (no dev login there).
