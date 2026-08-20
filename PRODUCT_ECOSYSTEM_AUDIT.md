# KarenSeir Product Ecosystem Audit

Timestamp: 2026-08-20

This audit verifies the current repository at HEAD `2054b84a29a14d18d28786c1220e2c0612496f18`. It does not replace prior security/database evidence.

## Benchmark findings applied without copying UI

- Metasearch patterns: flexible-date intent, transparent provider/source, final-price sorting and explicit freshness.
- Marketplace patterns: destination-led discovery, verified-stay review distinction, amenity/cancellation filters and list/map parity.
- Trip-planning patterns: saved itinerary separated from authoritative inventory; every bookable item re-enters price/availability check.
- Iranian-market requirements: Persian/Arabic character normalization, Jalali/Gregorian boundary clarity, IRR/toman labelling, domestic city/airport/rail recognition and provider-contract constraints.

These are behavior contracts only. KarenSeir keeps its approved Persian RTL/Vazirmatn identity and does not reproduce another product's layout or copy.

## Page and capability inventory

| Area | Verified state | Gap / gate |
|---|---|---|
| Homepage | healthy approved UI; discovery/search presentation partly demo-labelled | unified live ecosystem search results |
| `/hotels` | UI-only legacy prototype and clearly mock-labelled | authenticated Search 2.0 integration, filters/map |
| `/compare` | authenticated real backend plus legacy presentation shell | vertical-specific labels and saved comparison |
| `/assistant` | grounded-context backend exists; UI remains prototype | editable/persisted itinerary and model provider |
| `/trips`, manage booking, timeline | real authenticated API, cancellation/refund/support connected | external notification delivery/provider changes |
| account/payment/invoice | real domain and fail-closed payment adapter | contracted gateway; ZarinPal test credential |
| organization/finance | real RBAC workflows, credit/installment/invoice/reconciliation | target policy/report certification |
| supplier/agency/backoffice/admin | real read/mutation APIs with RBAC | richer analytics; external provider contracts |
| nearby/services | demo-labelled discovery and map fallback | map/places credential and real destination catalog |
| white-label | persistent tenant configuration | DNS verification and target certificate |
| reviews/trust | trust copy only | persisted moderated review domain |
| trip builder/wishlist | domain concepts only | persisted tenant/user-scoped implementation |

## Phase 1 gate

- Repository/status/routes/backend/tests inspected: PASS.
- UI authority preserved: PASS; no visual files changed.
- Security baseline preserved: PASS; no schema or RLS change.
- Mock/provider-dependent areas explicitly identified: PASS.
- Rollback: remove this audit/ADR only; no runtime state changed.

## Phase gates after this increment

| Phase | Gate | Evidence / remaining |
|---|---|---|
| 1 Product audit | PASS | page/domain inventory and explicit authority classification |
| 2 Search Engine 2.0 | PASS (internal contract) | 14 verticals, Persian normalization, autocomplete, filters/map bounds, provider timestamps/TTL, stale fail-closed, recent searches; live inventory remains credential-dependent |
| 3 Discovery | PARTIAL | approved Homepage discovery exists; destination catalog/API and dedicated discovery routes remain internal |
| 4 Trip Assistant | PARTIAL | grounded transactional context PASS; editable persisted itinerary/model integration remains |
| 5 Comparison | PARTIAL | authoritative 2–4 offer comparison PASS for core verticals; vertical-specific awards/schema expansion remains |
| 6 Reviews & Trust | MISSING | persisted verified-review/moderation domain remains |
| 7 Map | PARTIAL | provider interface and fallback exist; real map/list result integration requires internal route work plus external credential |
| 8 Trip Builder | MISSING | persisted trip basket, wishlist/share/collaboration remain |
| 9 Operations/Timeline | PASS | tenant-aware immutable events, deep links, source distinction and notification outbox |
| 10 Organizational Travel | PASS | credit/policy/approval/installment/invoice/reporting and white label |
| 11 ZarinPal test | BLOCKED | generic payment safety foundation exists; ZarinPal-specific certified transport and sandbox merchant credential absent; no fake callback success |
| 12 Checkout | PARTIAL | traveller/price-check/payment/invoice/confirmation domains exist; cohesive dedicated checkout UI remains |
| 13 Supplier/Agency | PASS | inventory/price/status/commission/settlement operations with RBAC/audit |
| 14 Mobile/RTL | PARTIAL | frozen Homepage Desktop/Mobile gate PASS; full calendar/map/date/number visual matrix remains |
| 15 Performance/SEO | PARTIAL | metadata/build/image framework exists; canonical/sitemap/structured destination data and CWV evidence remain |
| 16 Security/Financial | PASS | prior real PostgreSQL 56/56 RLS plus current IDOR/payment/idempotency/RBAC regression |

Passed phases: 6/16. The expanded ecosystem scope is estimated at 76%; the prior 97% remains the completion figure for the narrower production-hardening scope and is not reused to conceal new product gaps.
