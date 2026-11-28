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

## 1405-09-08 (2026-11-28) — SEO baseline on the homepage (non-visual only)

- Status: **pending owner confirmation** — requested as the group SEO rule (`docs/group-knowledge/SEO_BASELINE.md`), relayed by the supervisor; scope limited to changes with no visual effect.
- Scope: homepage route split into a server wrapper (`app/page.tsx`) and the unchanged client body (`app/root-pages.tsx`) so it can export metadata
  (title, description, canonical); Persian `alt` on the four destination tiles, the organization image and the two hotel thumbnails; JSON-LD data block in the root layout.
  The rendered homepage HTML was compared before/after: only the `alt` values differ. Search page: a pass-through `app/search/layout.tsx` adds `noindex` only.
- Files: `app/page.tsx`, `app/root-pages.tsx`, `components/marketplace/ApprovedHomeLower.tsx`, `components/marketplace/ApprovedFigmaHome.tsx` (alt only), `app/layout.tsx`, `app/search/layout.tsx`, `app/globals.css` (one appended rule `.cat-head h1.cat-list-h1`, used only on /tours/search and /tours/destination/*; not on the homepage or search).
- Evidence: `tests/seo/seo-check.mjs`; report `docs/seo/SEO_REPORT_2026-11-28.md`. Rollback: revert those hunks.

## 1405-09-08 (2026-11-28) — APPROVED by the owner: Niira/Mahan flights in public search with «درخواست رزرو»

- Status: **approved by the owner** (Mehdi Kazemi), in chat, 1405-09-08, relayed by the supervisor. Owner's words:
  «پروازهای نیرا (و ماهان) در جست‌وجوی عمومی سایت با قیمت فروش نشان داده شوند و مشتری به‌جای خرید آنلاین "درخواست رزرو" بزند؛ کارشناس تماس می‌گیرد و بلیت را صادر می‌کند.»
- Scope (behaviour; no visual redesign — only existing components and classes):
  - Flight search results (`/search/results`, vertical=flight, public and signed-in) also list **live** Niira (`NIRA_MODE=live`) and
    Mahan (`MAHAN_MODE=live`) flights for the searched route and departure day. Sandbox/QAA inventory never appears here.
  - Price shown = indicative **sell** price per adult (tenant markup for the caller's price group, `flight_pricing.py`); flights
    above the CAO cap are not listed (PR #119 rule). Net/supplier price never leaves the monolith.
  - **The one change to the login-for-price rule:** for these request-only flights the indicative sell price is shown to visitors
    who are not signed in too (labelled «قیمت تقریبی»). Every other result keeps «ورود برای قیمت و رزرو».
  - These results carry `booking_mode: "request"`. Their card shows one «درخواست رزرو» button (existing `button primary`) instead of
    price-check/reserve, wishlist/basket and the `/offers/{id}` detail link. It opens the existing sales-desk request form
    (`TripRequestForm`, `/public/sales-desk/requests`) in place; the request carries a server-signed flight spec (airline, flight
    number, date/time, route, class, sell price shown) and lands as a `web_form` case in `/admin/sales-desk`.
    Confirmation text: «درخواست شما ثبت شد؛ کارشناس کارن تراول به‌زودی تماس می‌گیرد.» No payment, hold or ticket issue happens.
- Not in scope: online purchase/issue of Niira or Mahan tickets; any homepage or search-form visual change; other verticals.
- Rollback: set `SEARCH_LIVE_FLIGHT_SUPPLIERS=0` on the search service (provider off), or revert the PR.
