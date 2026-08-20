# ADR-018 — Saved travel, verified trust, destinations and editable itineraries

Status: accepted for incremental implementation — 2026-08-20

## Decision

Add tenant-scoped persisted domains for saved trips and their wishlist/basket items, customer reviews and immutable supplier responses, destination hierarchy, and editable itineraries. Every table has `tenant_id`, PostgreSQL RLS and `FORCE RLS`. User-owned resources are additionally owner-filtered at API level. Mutations use command IDs and audit/outbox records; moving an item changes state under a row lock rather than copying it.

`verified_booking` is always derived by the backend from an owned, issued/completed reservation matching the review service type. It is never accepted from clients. Supplier responses are separate rows and cannot overwrite customer text. AI analysis remains `not_requested` until a real model and moderation policy exist.

Destination records are tenant-configurable and hierarchical (`country/province/city/district/poi`). Search result counts and inventory are queried from the Search Layer; destination pages never persist invented availability.

Itinerary items may reference a current Offer. The server snapshots only source/timestamp metadata and labels every non-fresh or unlinked item `needs_live_availability_check`. Reorder, move-day, replace and duplicate operations are owner-scoped and idempotent.

The approved Homepage is frozen. New UI is allowed only in dedicated routes; this ADR authorizes no Homepage/CSS/asset changes.

## Acceptance

- Own-user create/read/move/remove/duplicate operations pass; cross-tenant and IDOR access return not found/forbidden.
- Duplicate command IDs replay the same response and conflicting payloads fail.
- Missing PostgreSQL tenant context sees/writes no rows; all new tables have RLS/FORCE RLS.
- Review verification cannot be forged; moderation and supplier response actions are audited.
- Destination hierarchy/slugs/geo and itinerary ordering have constraints.
- Existing security, booking, frontend, E2E and frozen Homepage gates remain green.

## Rollback

Revert application routes, then downgrade only revision `20260820_11`. The migration drops the new empty/additive tables in dependency order and does not alter existing bookings, payments, trips, search offers or Homepage assets. Take and verify a database backup before downgrade on any shared environment.
