# ADR-024 — Visible marketplace slices

Explicit user priority supersedes Homepage design freeze: preserve KarenSeir identity,
Vazirmatn and RTL, replace beige/orange/purple homepage treatment with navy/turquoise.
Use the proven current repository and deployment path; do not repeat forensic audit.
Migration 20260928_34 already applied under prior approval; no migration in Slice 1.

Slice 1: visible homepage marketplace, complete service navigation, editorial destination
and accommodation category discovery, prominent assistant prompt handoff, existing
vertical search widget reused. Editorial guides do not claim popularity/rating/price,
and no product cards or availability are fabricated. Assistant drafts require explicit
send; no automatic conversational/transactional operation. Search preserves existing
backend contracts; richer result/booking work remains in subsequent slices.

QA: production build, desktop/mobile browser, tab-specific controls, real route handoffs,
assistant prefill, navigation, public image/asset proof and screenshots. No SMS or money.
Rollback: preserve currently served frontend container/image; frontend-only replacement.
Master gap matrix remains cumulative; unreviewed baseline capabilities are not marked complete.

Slice 2 scope: use existing Offer/recheck/checkout contracts. Show flight number,
carrier, route, duration, stops, cabin, baggage and supplier only from supplied data;
missing stops must never silently mean nonstop. Replace generic empty result dead end
with date changes, editable criteria, transport alternatives and assistant handoff.
Flight landing uses actual search controls. No invented supplier result or hold.

Master autonomous directive is cumulative. Slice 2 also adopts the explicitly requested slogan «تمام سفر، در یک مسیر». Flight facts remain provider supplied; missing stops are unknown. QA uses isolated offers only. No schema change or live financial operation.

### Slice 3 — stay discovery and continuity
Public browser baseline: /hotels only ServiceIntro, /villas category context leads to authentication without usable filter form. Replace /hotels entry with hotel-default search and genuine category/editorial discovery. Accommodation filters/dates/guest count persist through login, property detail, refresh and return. Keep tenant-scoped catalog authorization; no public cross-tenant inventory exposure. Reuse quote/reservation/calendar APIs, no schema change. Render only supplied property amenities/media/rules. Desktop/mobile QA with isolated property + public empty/login handoff, then deploy frontend retaining current rollback.
