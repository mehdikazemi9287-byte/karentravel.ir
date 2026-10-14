ROOT_CAUSE: Home() was replaced by MarketplaceHome in 2255a05 (2026-09-28 17:50 UTC); Production serves d2ba674, image d27e90f03dc9, build f2RCNeisrtn7IzoGKDsyg. Later historical c8b8c72 deliberately retained several redesigns; Figma-labelled 791d007 had no verified frame parity.
LAST_GOOD_UI: 76bea5c, documented authorized historical reference in ADR027; independent Figma approval unverified.
RECOVERY_METHOD: Copy current dirty Source into isolated /tmp candidate; port historical homepage composition/editorial arrays; scope historical CSS to Homepage. Correct measured input line-height and duplicate body padding from scoping. Existing search, route dispatch, Backend/DB/catalog/trip operations/panels remain. 346 application files checked; only app/page.tsx and app/globals.css differ.
HOMEPAGE_RESTORED: YES in isolated Preview. All 13 section geometries and headings match; full-page raw RGB screenshot bytes identical at 390, 768, 1440, 1920.
FIGMA_PARITY: UNVERIFIED. Ei8MUR9VN2yCX6BLOpvTXm metadata twice and frame44:3 context returned authentication/retry notices; no frame content obtained.
FEATURES_PRESERVED: Source-level byte preservation of all other application files; all historical homepage links retained. 7 primary Search tabs and 9 More items exercised at four widths; date/guest overlays fit viewport and close with Escape; six main routes return200 with no homepage CSS scope. No reservation/payment/DB writes. Full booking E2E not repeated.
DESKTOP_VISUAL_QA: PASS against historical reference at1440/1920; no overflow, pageerrors or broken images.
MOBILE_VISUAL_QA: PASS against historical reference at390/768; no overflow, pageerrors or broken images. Chromium viewport emulation.
PRODUCTION_CHANGED: NO. No deploy, restart, migration or data rollback.
REMAINING_GAPS: Independent Figma frame inventory/parity; public IP intentionally remains unchanged. Candidate is not a whole-repository release approval.
