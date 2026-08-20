# ADR-017 — Ecosystem Search Layer

Status: accepted for incremental implementation — 2026-08-20

## Decision

KarenSeir keeps one tenant-aware search contract over the existing `Offer`, `SearchRequest`, provider-adapter and price-check domains. The contract supports flight, hotel, train, tour, accommodation, car rental, restaurant, event/hall, pool/sport, attraction, travel guide, handicraft, tourist transportation and package verticals without duplicating booking logic.

Search responses expose source, observed/availability/price timestamps, expiry, freshness state, inventory state, total price components, verified cancellation policy and vertical attributes. An expired offer is never returned as live. A provider-backed offer without a fresh observation is labelled `provider_required`; it is not promoted to confirmed availability.

Persian query normalization converts Arabic ی/ک, removes diacritics, normalizes whitespace and zero-width characters, and preserves the normalized query in the tenant-scoped search audit record. Filters and ranking operate only on backend offer snapshots. Frontend values are advisory inputs, never authoritative price, availability or policy.

The approved Homepage and its search-box presentation are frozen. Search 2.0 is integrated behind the API and in dedicated result routes only; this ADR does not authorize any Homepage DOM, section order, spacing, typography, color, image or responsive change.

## Acceptance

- All declared verticals use the same endpoint and output envelope.
- Tenant isolation remains enforced in the SQL query and PostgreSQL RLS.
- Expired/stale offers are excluded or explicitly labelled; timestamps are mandatory in every result.
- Price, taxes and fees are backend-derived from the stored offer snapshot.
- Persian normalization, filters, sort, cross-tenant denial and freshness have tests.

## Rollback

The change is API-additive and uses existing tables. Roll back the application commit; no schema downgrade or data deletion is required. Existing minimal `{service_type}` requests remain compatible.
