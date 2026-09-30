# Historical Homepage recovery — frontend Candidate, not Production

## Scope and baseline
User's latest directive explicitly permits historical reconstruction independently of Figma and prohibits Production deployment. Source base92af832; existing debug_voucher.py left untouched. Historical76bea5c equals the exact parent of2255a05. Three distinct historical versions executed in independent loopback-only containers3381/3382/3383; no redundant fourth build for the identical parent. Current Production frontend image is reused for the isolated d2ba674 reconstruction. All four versions including Candidate are captured at1366/1440/1536/1920/360/390/430. Exact image/container/Next build IDs are in evidence/historical-ui-recovery-20260930/builds.json.

Candidate3384 image e36d23716ee902157a4b8dc7af5eabb83be6f9f21644e9a2228be9829213e24e; build metadata identifies92af832-ui-recovery-final, a worktree snapshot, not a falsely claimed committed build. Exact three frontend file SHA256 values map that snapshot to the final source. No additional backend/DB/worker application delta.

## Component-level recovery map
All original replacements below originate in2255a05. Before is historical76bea5c; after is currentd2ba674; status describes this Candidate, not a Figma match.

| Component | Before → after | Source file | Candidate status |
|---|---|---|---|
| Header | HomeHeader → mk-header | app/page.tsx / MarketplaceHome.tsx | Current header retained to preserve newer assistant/discovery/trips/menu destinations; same brand/RTL |
| Navigation | historical mobile bottom links → mobile expandable menu | same | Current mobile menu retained;44px interaction target; no route removed |
| Hero |650px/520px curved hero →450px/335px shell | app/page.tsx / globals.css | Original ReferenceHero DOM/crop/badge/curve restored; navy palette and current slogan intentional |
| Search | ReferenceHero search shell → mk-search | HomeSearchExperience.tsx / globals.css | Original overlapping reference shell restored around unchanged current Search logic; no old provider/booking engine copied |
| Search tabs | same shared Search, old palette → turquoise | HomeSearchExperience.tsx | Current vertical tabs/More/unavailable states retained |
| Date/Guest/Room | shared controls with subsequent fixes | HomeSearchExperience.tsx | Functionality byte-unchanged; seven-width keyboard/overlay tests |
| Service categories |6 grouped service rows →14 uniform tiles | app/page.tsx / MarketplaceHome.tsx | Original HomeServicesHub recovered; all14 current direct service URLs remain as secondary shortcuts |
| Mosaic/grid | uneven590px mosaic → four270px equal cards | DestinationMosaic / globals.css | Exact historical tile placement and assets recovered; responsive mobile grid retained |
| Destination/editorial cards | ReferenceTrips → text-led ideas | app/page.tsx | ReferenceTrips restored as editorial guides; current idea links retained; unused historical price/rating fields excluded |
| Promotional comparison | CompareBand removed | app/page.tsx | Original comparison band recovered; existing /compare workflow preserved |
| Accommodation discovery | later current category links | MarketplaceHome.tsx | All property-type links retained, not rolled back |
| AI | SmartCompanion + floating → inline prompt section | app/page.tsx / MarketplaceHome.tsx | Current prompt suggestions/context links retained after editorial section; original FloatingAssistant reinstated |
| Trust/benefits | old4-card information section → current3 factual blocks | same | Current truthful trust/account/support blocks retained; no invented accreditation or payment promise |
| Organization | historical illustration → current operational links | same | Current organization/request/credit/trip links retained; no illustrative credit or balance introduced |
| Footer | multi-column full-width curved → shallow constrained | ReferenceFooter / globals.css | Original full footer recovered with real support phone and legal/provider links |
| Floating assistant | scroll-aware component removed | app/page.tsx | Same implementation recovered; visible on mobile after search clears, not over input overlays |
| Spacing/container |1184/1120 old widths →1200 current | globals.css | Historical component spacing restored;1920 content max1480 under explicit large-screen correction, not global stretching |
| Typography/colors | plum/coral historical → navy/turquoise | globals.css | Current palette/RTL/Vazirmatn retained; headline sized for approved slogan rather than old short text |
| Images | same tracked assets; fewer image sections rendered | public | No deleted/changed asset files; original image slots restored |
| Responsive rules | reference650/590/520 hero and mosaic breakpoints replaced | globals.css | Historical650 desktop/520 phone measured; current mobile menu and Search fixes preserved |
| Empty ServiceRibbon | historical blank decorative strip | app/page.tsx | Not reinstated as a placeholder; no functional section removed |

Presentation functions were extracted from preserved historical implementations in app/page.tsx into HistoricalPresentation.tsx; route logic and backend contracts were not reverted. Existing customer/organization/operations functionality is not replaced with historical mock versions.

## Assets and imagery
Git tree comparison76bea5c→current:5 public assets, zero added/deleted/modified. All-history public deletion search empty. No binary recovery/download was necessary. Original Yazd, Qeshm, Shiraz and northern-travel assets are used. Repetition is intentional historical editorial reuse: a destination mosaic entry and a guide to that same destination; Yazd hero and its destination tile. No unrelated card is assigned a new generic photo. There is no new price, availability, rating or supplier-success claim. Exact screenshot/load evidence is recorded, not inferred from HTTP200.

## Verification
- Clean historical and Candidate production builds completed including TypeScript. Root direct tsc initially included stale .next/dev types referencing the already-existing Shell export; isolated clean builds passed without weakening config or changing that route.
- Search and booking71801f8 functionality preserved. Fresh final-image isolated Desktop1440/Mobile390 journey begins at Homepage, selects hotel/destination, opens dates, changes room count and restores it, searches, selects result, verifies stay snapshot, recovers a deliberately dropped booking response without a second reservation, enters four travellers, follows intercepted gateway.invalid test handoff, verifies test payment, issues via supplier UI, downloads date/room-bearing voucher, and verifies My Trips/back/refresh. SQLite QA only; no Production data writes, real money or SMS.
- Initial extended harness clicked Hotel and assumed destination persisted; existing tab behavior defaults to Yazd. The harness now chooses Shiraz as an actual customer does; this was not mislabeled a recovery regression or patched outside scope.
- Date/guest controls Enter/Escape and panel bounds at all7 widths; mobile menu and recovered floating assistant tested360/390/430.
- Login/Register form rendering without submission; authenticated account, notifications, support, trips/timeline; customer denial and staff entry for Backoffice Trips at1440/390. This is scoped route/role smoke, not a new exhaustive backend permission audit.
-72 route files unchanged. Every original Homepage href remains present; additional recovered guide/comparison/footer links are intentional.
- Snapshot scripts initially encountered lazy-image painting and smooth-scroll screenshot coordinate artifacts. Final captures use natural image scrolling+decode, network idle, instant return to top, document-relative geometry and stable screenshots. No artificial placeholder was substituted. PIL comparison output needed the temporary directory owner's UID; no Production permission was changed.

## Visual acceptance and deliberate differences
The accepted comparison is historical/current/Candidate, not Figma. Hero hierarchy, mosaic asymmetry, grouped service rows, editorial imagery, full footer and scroll-aware assistant are restored. Header/mobile navigation, AI prompts, accommodation types and organizational entry keep current capabilities. The historical palette, shorter slogan and empty ribbon are deliberately not restored. Full-page and annotated top/mosaic/footer comparison images are recorded for each requested viewport. Search retains current room/date semantics; brand colors change from historical coral to turquoise intentionally. Mobile is Chromium emulation, not physical Safari/device proof.

## Release boundary
This is a previewed frontend recovery patch, not authorization to publish the root repository wholesale. Source still contains previously unpublished hotel71801f8/enterprise35 work. E2E uses the existing matching QA API; it does not prove that publishing all current source against unchanged publicd2ba674 API is compatible. Any later Production package must explicitly account for those pending dependencies and preserve the standalone worker4d9f0c3. No schema35, backend image or worker rollout is bundled in this UI patch. Figma validation remains independently pending; real supplier/OTP/payment remain externally blocked.

Production Web/API/search/worker/DB container identities, schema34 and DB role/ACL fingerprint match the pre-task baseline. Reaper disabled. Rollback containers/images preserved. Candidate can be discarded independently without modifying Production.


## Final QA disposition
Historical-recovery UI patch: READY_FOR_RELEASE (bounded patch), Figma validation pending. This is not a whole-repository Production readiness claim; the release boundary above remains mandatory. Remaining implementable gaps in this recovery scope:0.

All7 annotated comparisons reviewed: desktop1366/1440/1536 retain650px hero and original mosaic/footer hierarchy;1920 additionally has1480px content width. Mobile360/390/430 retains520px historical hero, asymmetric stacked mosaic, readable full footer, original scroll-aware assistant without reverting the current menu. Footer is actually hidden in publicd2ba674 on all3 phone widths and visible in Candidate; sections.json records this regression recovery. Current Search shell/notes remain to preserve newer behavior. Full desktop/mobile editorial sections separately inspected.

28 full-page captures are retained for traceability. Chromium full-page compositing intermittently omits an offscreen reused image despite successful decode; these raw images are not used to assert imagery PASS. Annotated comparisons explicitly stitch the TOP crop and actual in-viewport destination/footer captures. The hidden current mobile footer is labeled as hidden, not fabricated. Actual section images show all original destination imagery. All7 candidate image-load/console/page-error/network-error/overflow checks passed; actual section painting was reviewed independently. No substituted imagery.

33 Homepage-linked route responses without HTTP error; all previous hrefs retained.72 page files unchanged. No new E2E claim for real supplier/payment/OTP. Final booking/other-route tests are against the matching isolated QA API. Build-checks.json records clean compile/TypeScript/image-build evidence.
