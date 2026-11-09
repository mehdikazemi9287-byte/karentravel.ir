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
