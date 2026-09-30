# UI recovery: reference gate, not a completed candidate

## Proven deployment and history
Public frontend d2ba674be607a5908bac15a46d385a0b63b26b10, image d27e90f03dc9f3b9cec15277b76f1651a209d7d62852dc438a79435d99288528, Next build f2RCNeisrtn7IzoGKDsyg. Container identity is recorded under evidence/ui-recovery-20260930/identity.json. No rollback, build, deployment, migration or runtime edits performed.

2255a05 introduced MarketplaceHome, changed app/page.tsx routing to it, added scoped marketplace CSS and reused HomeSearchExperience in a feature release. ADR024 explicitly records a user-requested switch from plum/coral to navy/turquoise. That is the origin of the current visual structure, NOT proof it is a regression from an approved design. 916c6fe subsequently changed its slogan only. Search later changed in3f0a33a. No pre-existing CSS lines were removed between2255a05 and publicd2ba674; appended selectors still require visual inspection, so this is not proof of absence of CSS interference.

Current MarketplaceHome, HomeSearchExperience and globals.css are byte-identical to their versions at publicd2ba674. There is no evidence that the Worker publication changed Homepage. Worker4d9f0c3 remains healthy/reaper disabled. Source71801f8 booking changes and cd0cd4e recovery evidence retained.

## Missing reference — exact blocker
Figma connector authentication succeeds. No project fileKey/nodeId or Figma design/file URL was found in repository documents or supplied text attachments. get_design_context cannot run without these required identifiers; this is NOT a proven account-access denial. MASTER_GAP_MATRIX explicitly says Figma source unspecified. DESIGN_SYSTEM contains an older contradictory plum/coral section; ADR024 has the later explicit navy/turquoise instruction.

Existing repository screenshots (hotel-phase0-20260929 and artifacts/search-ux) and the2255a05 source establish historical implementations, not a documented last-approved UI. No approval can be inferred from a screenshot filename. Therefore LAST_APPROVED_UI_BASELINE and FIGMA_MATCH are UNKNOWN/BLOCKED. Required input: approved project Figma Desktop/Mobile frame URL(s), or identification of a specific approved repository commit/artifact. The asynchronous question remains pending. No new design was invented, and no candidate is represented as recovered or release-ready.

## Current sections — presence inventory, not visual MATCH
| Area | Current finding |
|---|---|
| Header/navigation | Present; mobile menu opens. Header CTA remains login. |
| Hero | Existing Yazd image; desktop450px/mobile335px; comparison to intended crop requires reference. |
| Search/tabs | Flight, hotel, package, train, bus, tour, accommodation tabs respond at1440/390. More menu exposes restaurant, attraction, sport, venue, car, cruise, visa, transport, guide. |
| Flight/hotel/train/tour | Existing search/entry routes retained; no live provider outcome claimed. |
| Package/bus | Explicit unavailable message and contact alternative; no fake success. |
| Accommodation/car/restaurant/sport/events/venue/attraction/guide/transport/handicrafts | Homepage service links retained; 14 equal-weight cards. Product-wide E2E not asserted. |
| Destination discovery | Four editorial cards; no price/availability assertions. Yazd repeats hero asset. Whether repetition is intended is unverified. |
| Accommodation discovery | Category links; no accommodation photography/cards here. |
| Inspiration | Four text cards; no imagery. |
| AI | Large separate dark section, prompt deep links present; conversation backend not re-tested. |
| Organization | Intro + CTA + three detail-entry cards; public prominence requires comparison. |
| Wallet/trips | Organization links plus primary My Trips link retained. |
| Trust/support | Three support/account/informed-choice blocks; phone link retained. No verified accreditation claim. |
| Footer | Present, shallow and constrained; intended treatment requires reference. |

Requested MATCH/REGRESSION classifications cannot honestly be assigned without a reference. Presence is not MATCH. No section is declared visually approved.

## Measured issues and checks
- Desktop1280/1440/1600/1920: wrap1200px at all sizes; at1920 leaves360px per side. Hero450px/search276.69px. This substantiates the narrow large-display concern, not an inferred Figma dimension.
- Mobile360/390/430: wrap332/362/402px; hero335px; search636.56/595.19/569.19px. Search dominates the initial mobile journey.
- All seven widths: no document horizontal overflow; all rendered images loaded. Full screenshots saved. Desktop1920 and mobile390 renders inspected; no blanket seven-size visual PASS.
- Desktop1440/mobile390 interactive tab/menu checks: no observed page errors or HTTP>=400 responses. This limited check does not certify all console/network behavior for the product.
-31 unique Homepage-linked paths fetched: no HTTP>=400. This is a link-health result, NOT route workflow PASS.
-72 page route files before/after, unchanged; dynamic route auth/ownership behavior not exhaustively re-run.
- Existing fresh isolated hotel E2E from immediately preceding stage remains under worker-production-20260930/preview-fresh-journey.json: two rooms/four guests, lost-response replay, test payment, supplier issuance, voucher, account/back/refresh at1440/390. Not repeated because no code changed; it is not a test of a new UI candidate or real provider integration.

## Boundaries and next action
API/DB/Worker unchanged; no migration/permission change, no real payment/SMS. Rollbacks retained. No frontend/backend source edits. Source files and production snapshots are checked after documentation work. UI recovery cannot be completed faithfully until approved reference identity is supplied. Once available, compare reference→historical baseline→candidate, limit changes to frontend, then run requested visual and product-integrity QA; seek explicit approval before Production.

## Follow-up: real discovery attempts and historical component mapping

Latest directive permits frontend deployment ONLY after all candidate gates pass. No such PASS or deployment has occurred.

Discovery evidence:
- Enumerated every available Figma tool: figma-tool-inventory.json. There is no account/team/project design-file listing/search method. get_libraries/search_design_system/use_figma/get_metadata all require an existing fileKey. Library asset search is not account file search. No guessed key, new design file or mutated design used to bypass this limitation.
- Authenticated connector whoami previously returned the connected team. Actual browser navigation to its files/team/.../recents-and-sharing URL redirects to https://www.figma.com/login?is_not_gen_0=true&resource_type=team, title Login | Figma. Evidence: figma-browser-discovery.json and figma-login.png. Connector authentication does not provide a signed-in browser session. No credential/session extraction attempted.
- All available git history searched for figma.com/design, /file and /proto URL changes in document/code files: none. Repository and attachments had no file URL. public/reference/README.md identifies expected asset19204EA5-4649-4726-9AF0-50AD4F478FC6.jpeg and explicitly records its absence. Exact filename/.fig searches in supplied attachments, public assets and accessible temporary files found none.
- Actual accessible files/pages/frames could NOT be enumerated with these capabilities. This is not a claim that no project exists or that the Figma account has no files. Required dependency: a browser session authorized to list the team's files, an API capability to enumerate them, or one known project file key. No user frame choice is necessary once the file can be opened.

Historical parent76bea5c is an IMPLEMENTATION baseline, not authenticated approved Figma:

| Section | Current | Historical76bea5c | Source change | Safe correction boundary |
|---|---|---|---|---|
| Header/navigation | mk-header/main nav/mobile menu | HomeHeader/HomeMobileNav incl nearby link |2255a05 Home switches to MarketplaceHome| Preserve current routes; recover geometry once actual reference is accessible |
| Hero |450px desktop/335px mobile, square shell|ref-hero650px desktop, media590/520px, curved bottom|2255a05| Confirm intended crop/height; do not blindly restore plum layout |
| Search/tabs/controls |HomeSearchExperience; turquoise wrapper|Same search component in ReferenceHero with prior palette|2255a05 wrapper/tokens;3f0a33a hotel entry changes| Preserve Date/Guest/Room contracts; visual dimensions remain reference-dependent |
| Service shortcuts |14 equal cards|HomeServicesHub|2255a05| Keep every vertical entry; presentation unresolved |
| Destinations |4 equal cards270px desktop|DestinationMosaic590px, uneven3-column/2-row layout|2255a05| Recover intended composition, not guessed layout |
| Promotions/content/cards |text-led inspiration/stay categories|ReferenceTrips/LocalExperiences/CompareBand|2255a05| Preserve current data honesty and product links |
| Trust/organization |compact trust; org intro and3 entries|TrustSection/ReferenceOrganization|2255a05| Do not restore illustrative financial claims as live data |
| Footer |mk-footer shallow constrained block|ReferenceFooter full-width multi-column with decorative curve|2255a05| Reference comparison needed for restoration |
| Assistant/floating |inline AI with prompt handoff|SmartCompanion plus FloatingAssistant|2255a05| Preserve conversation draft behavior; no automatic booking/payment |
| Width/responsive |mk-wrap max1200|ref-container max1184|2255a05, older width already narrow| Rollback is NOT a solution for1920; reference-dependent responsive candidate needed |

Source reference is the exact Home() JSX replacement in2255a05 and styles of parent76bea5c. These prove structural changes; they do not prove approval of every historical section. No code changes, candidate builds or redundant E2Es performed while reference-dependent restoration is blocked. Existing verified reservation71801f8 and worker4d9f0c3 remain intact.
