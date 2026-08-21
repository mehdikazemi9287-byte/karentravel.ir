# ADR-020 — Travel commerce domains: rentals, tours, cruises and visas

Status: Accepted for credential-independent implementation

## Context and benchmark findings

KarenSeir keeps one commerce lifecycle while preserving vertical-specific inventory rules. Product patterns were reviewed from public material for Jajiga and Iranian tour operators, Airbnb booking/filter guidance, Royal Caribbean and Norwegian Cruise Line fare/availability terms, and the official France-Visas, German Consular Services Portal and Canada immigration processes. The reusable findings are domain rules, not visual designs:

- Vacation rentals require date-and-guest eligibility, property/unit separation, explicit fees/rules and inventory locking; confirmed or pending reservations must block overlapping inventory.
- Tours require dated departures, capacity, transport/hotel/service disclosure, room/passenger pricing and explicit visa assistance state.
- Cruise fares are sailing/cabin-specific and port fees/taxes are separate; live availability cannot be inferred without a contracted provider.
- Visa applications are document- and human-review workflows. Biometrics, processing and the final decision remain external-authority actions; KarenSeir must never promise approval or an unverified processing time.

## Decision

- Add tenant-scoped `vacation_*`, `tour_*`, `cruise_*` and `visa_*` tables through one additive migration. Every table receives PostgreSQL RLS and FORCE RLS.
- Inventory mutations lock the authoritative unit/departure row, validate the complete date/capacity request and use a tenant-scoped command id for idempotency.
- Customer-facing prices are server-calculated from stored component snapshots. Clients cannot set availability, verification, visa decisions, voucher issuance or payment capture.
- Cruise search/detail may expose configured catalog records, but live booking fails closed until a contracted provider adapter is enabled.
- Visa timelines distinguish `system`, `human_agent` and `external_authority`; applicant uploads cannot mark a document accepted.
- Existing Search v2 remains the shared discovery contract. New verticals extend its service-type vocabulary; they do not create a parallel search engine.
- Homepage identity and section layout remain frozen. Dedicated routes host the new workflows.

## Acceptance

- Own-tenant reads/writes pass; cross-tenant and missing PostgreSQL tenant context fail.
- Rental overlap and tour oversell attempts fail under locked transactions; duplicate commands return the original reservation.
- Visa eligibility is explicitly advisory and source-timestamped; decision and document review require BackOffice/Support roles.
- Cruise live booking returns a fail-closed provider-unavailable response when no contracted adapter exists.
- Browser tests cover Search interaction plus rental, tour, cruise and visa routes without using fake live inventory.

## Rollback

- Take and checksum a PostgreSQL backup before upgrade.
- Disable the new routes, then downgrade only revision `20260820_14`; no existing commerce table is altered or dropped.
- External providers and payment modes remain disabled throughout rollback.
