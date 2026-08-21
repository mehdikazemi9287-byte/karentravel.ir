# ADR-019 — Review UI, resumable checkout, ZarinPal contract and public destination SEO

Status: Accepted for credential-independent implementation

## Decision

- Homepage, its CSS, assets and approved layout remain frozen. New capability is isolated to dedicated routes and backend contracts.
- Reviews are paginated by the backend. `verified_booking` is read-only and derived from an owned issued/completed reservation. Reports are tenant-aware, idempotent and audited.
- Checkout state is persisted server-side and owned by tenant/user. The backend alone performs price/availability recheck, policy validation, funding validation and PaymentIntent creation. Client amounts are never authoritative.
- ZarinPal is a dedicated payment adapter with disabled/sandbox/production modes. Missing merchant/callback configuration fails closed. Callback parameters never capture funds; only server-side verify may record RefID and capture once.
- Public destination reads use an explicit tenant slug, set PostgreSQL tenant context before querying and expose only published catalog data. Dynamic search URLs remain non-indexable.
- Unified Search v2 extends the existing Offer/SearchRequest foundation rather than creating vertical-specific engines. Entity catalog and saved searches are tenant-scoped; normalized provider offers remain the transactional source.

## Acceptance

- Review list/create/report pagination and supplier response display pass UI/API tests; verified forgery and cross-tenant access fail.
- Checkout create/resume and ordered steps reject stale price, missing policy acknowledgement, foreign travellers, amount tampering and cross-tenant IDs.
- ZarinPal adapter contract tests cover request, verify, amount/authority mismatch, duplicate verification and missing credentials without claiming a sandbox purchase.
- Destination metadata, canonical, OpenGraph, sitemap, robots and JSON-LD are emitted without modifying Homepage.
- PostgreSQL migration is additive, has RLS/FORCE RLS and rollback removes only newly introduced state after backup.

## Rollback

- Revert dedicated routes/API wiring and downgrade only the additive migration after a verified backup.
- Keep external payment modes disabled during rollback; never reinterpret callback data as a successful payment.
