# Owner approvals for protected surfaces

The KarenSeir Homepage and Search visual experience are protected (see `AGENTS.md`).
Each entry below is an explicit owner approval. The scope is exact: nothing outside
it is approved, and the rest of the protected surface stays as it was.

## 1405-08-18 (2026-11-09) — Homepage D11 + D13

- Approved by: owner (Mehdi Kazemi), in chat, 1405-08-18.
- Source: customer-journey QA `docs/reports/qa-journeys-1405-08-18/REPORT.md`, defects D11 and D13.
- Scope:
  - **D13 — support phone at the top of the homepage.** The homepage header
    (`ApprovedFigmaHome`, Figma node 45:3) shows «پشتیبانی ۰۹۱۹۱۲۵۸۰۰۹» as a `tel:`
    link (from `lib/site-contact.ts`), styled like the header nav links, with an
    accessible label. At ≤900px it sits on its own centred row under the nav.
  - **D11 — trip type outside the date picker.** The «رفت‌وبرگشت / یک‌طرفه / چندمسیره»
    control moves out of the date popover to above the search fields of the flight
    tab (existing `.fs-seg` segmented style, `role="radiogroup"`, arrow keys).
    Default stays رفت‌وبرگشت. With یک‌طرفه the return date shows «—» and «پیدا کن»
    submits to `/search/results?…&trip_type=one_way` without `return`.
- Files touched: `components/marketplace/ApprovedFigmaHome.tsx`,
  `components/marketplace/approved-figma.css`, `components/search/HomeSearchExperience.tsx`.
- Not in scope: the shared `ApprovedHeader` used on other pages, any other homepage or
  search visual change.
- Figma: the two changes are drawn on a copy of the homepage frame on page
  «Approved changes 1405-08-18» of file `Ei8MUR9VN2yCX6BLOpvTXm`; the original frames
  are unchanged: https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=214-1278
- Evidence (local, not committed): Playwright 1440/390 before/after screenshots; one-way flow
  reached `/search/results?…&trip_type=one_way` with no `return` param and no calendar popup.

## 1405-09-02 (2026-11-23) — PROPOSED, pending owner confirmation: one-way default + suggestion rows

- Status: **pending owner confirmation** (requested by the supervisor after the owner's «مثل علی‌بابا / مستربلیط» complaint; not yet approved by the owner).
- Scope (behaviour only, no visual redesign):
  - Flight trip type defaults to **یک‌طرفه** instead of رفت‌وبرگشت (changes the D11 line «Default stays رفت‌وبرگشت»).
    A link that already carries `return` still opens as round trip. Segmented control order and style unchanged.
  - Origin/destination suggestion rows: city name primary, «فرودگاه …» secondary, IATA code small at the end; a city whose
    airports are listed reads «همهٔ فرودگاه‌ها» without a duplicate code. Same dropdown, same styles otherwise.
- Files: `components/search/HomeSearchExperience.tsx`, `app/globals.css` (two `.fs-pop--auto` rules).
- Evidence: `docs/qa/2026-11-23-normal-ota/` (before/after 1440 + 390). Rollback: revert those hunks.

## 1405-09-03 (2026-11-24) — APPROVED by the owner: «پنل سازمان» in the shared header account menu

- Status: **approved by the owner** (Launch V1 item 8.3 decision, 2026-11-24), relayed by the supervisor.
- Scope: one menu item only. `AccountMenu` in `components/marketplace/ApprovedFigmaHome.tsx` reads `/enterprise/context`
  and passes the memberships to `roleLinks` (`lib/panel-access.ts`), which adds «پنل سازمان» (→ `/organization` for a
  person with an organization-records grant, else `/employee`) only for a person with an organization membership or a
  legacy organization role. A plain customer's menu is unchanged. No other change to that file, the homepage visuals,
  the search page or `globals.css`.
- Files: `components/marketplace/ApprovedFigmaHome.tsx` (`AccountMenu` + two imports), `lib/panel-access.ts` (`roleLinks`).
- Evidence: `tests/unit/panel-context.cjs` (roleLinks cases). Rollback: revert those hunks.

## 1405-09-07 (2026-11-27) — APPROVED by the owner: merge to `main` deploys to production without a separate approval

- Status: **approved by the owner** in chat (answers: «دسترسی کامل به سرور» and «نه، بدون تأیید منتشر شود»).
- Scope: the auto-deploy poller in `deploy/autodeploy/` runs the verified `/root/deploy.sh --check` then `/root/deploy.sh`
  when `origin/main` moves ahead of `/opt/karenseir/DEPLOYED`. The owner's merge on GitHub is the per-release approval.
  One-way GitHub → server; not a command channel. Never deletes; a failed commit is not retried.
- Standing owner rule (same day): nothing is ever deleted — on servers, repos, hosts.
