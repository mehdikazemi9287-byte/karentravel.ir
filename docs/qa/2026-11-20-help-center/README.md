# QA — help center family (/support, /contact, /services) — 2026-11-20

- No Stitch screen exists for support/contact/services (checked all 55 screens in design/stitch/INDEX.md),
  so these pages use the same hero family as /flights, /hotels, /trains (fl-hero) plus cards/FAQ in the
  Stitch palette. Copy is factual only: no office hours, address or response-time promises.
- Clean local build (Next 16.4.3), 1440px and 390px screenshots in this folder.
- Homepage regression check: homepage still links its stylesheet (kh-bento) and renders unchanged (hc-d-home.png).
- Typecheck clean; eslint: 0 errors (1 pre-existing <img> warning in ConnectedViews.tsx).
- e2e impact: /contact still shows the trip-request form heading «درخواست سفر و مشاوره» (new-modules.spec).

Lesson recorded: an "unlinked homepage stylesheet" seen locally was a stale `next-server` process still
serving an old build after `.next` was rebuilt (`pkill -f "next start"` does not match `next-server`).
Always `pkill -f next-server` before restarting a local preview.
