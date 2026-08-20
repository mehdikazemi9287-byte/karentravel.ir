# ADR-016: Invoice, support cases, installments and controlled administration

## Decision

Add four tenant-scoped tables: immutable invoice snapshots, support cases, source-labelled support thread messages and installment agreements. PostgreSQL enables and forces the existing fail-closed tenant policy on every new table. Existing settlement records remain the settlement source; posting creates only an auditable pending record and never claims an external transfer.

Invoice issuance is derived from an authoritative reservation price snapshot. Customer reads are owner-scoped. Human support replies require `support:manage`; AI messages cannot be submitted through the human endpoint. Installment agreements are calculated from an active tenant/organization plan and remain `requested` until a finance role activates them. User role changes require `member:manage`, cannot target platform admins, cannot self-escalate and write legacy audit plus outbox evidence.

## Acceptance

- New tables have `tenant_id`, PostgreSQL RLS and FORCE RLS with no-context fail-closed behavior.
- Every mutation is tenant-filtered, RBAC guarded and idempotent where it creates a financial/domain record.
- Invoice totals, installment schedules and settlements are backend-derived; UI cannot submit authoritative totals.
- Human, customer, AI and system thread sources remain distinct.
- Existing and new backend, browser, lint, type and build suites pass.

## Rollback

Revert UI/API code, then downgrade revision `20260820_10`, which drops only the four new unused tables in dependency order. Existing reservations, payments, wallets, settlements, users and security policies are unchanged.

The migration owner provisions `karenseir_api` after initial schema creation. That contract grants current objects and installs default table/sequence privileges so an additive rollback→upgrade cannot silently deny the least-privilege API role access to recreated objects.
