# ADR-015: Customer account and role-panel mutations

## Decision

The approved UI will use the existing in-memory authenticated client for customer profile, owned travellers, personal wallets, payments, notification preferences, support messages, supplier inventory, agency configuration and backoffice supplier status. Every query and mutation includes both tenant and ownership/permission predicates. Financial balances remain derived from the immutable ledger; payment initiation remains fail-closed through the configured adapter.

No schema or migration is introduced. Existing operational tables are sufficient. Supplier, agency and backoffice mutations emit audit/outbox records where they change operational state. Customer support messages are visible only when linked to a trip or reservation owned by the authenticated user.

## Acceptance

- Cross-tenant and IDOR reads/mutations return 404; missing role permissions return 403.
- Duplicate personal-wallet creation is idempotent and does not duplicate ledger state.
- Payment UI can create an intent from an authoritative reservation snapshot but cannot claim provider success when the adapter is unavailable.
- Loading, empty, unauthorized, forbidden, validation/error and success states are rendered without changing the approved RTL/Vazirmatn identity.
- Backend regression, lint, strict TypeScript, production build and browser E2E pass.

## Rollback

Revert the route/components and endpoint commit. No database rollback or data migration is required. Existing rows remain compatible and no production credential or provider mode is changed.
