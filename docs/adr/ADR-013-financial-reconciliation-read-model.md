# ADR-013: Financial Reconciliation Read Model

## Decision

Finance users receive a tenant-scoped, read-only reconciliation view derived from immutable payment, refund, settlement and wallet-ledger records. The view never repairs balances automatically and never accepts an amount from the frontend. It reports per-payment captured/refunded totals, pending refund exposure, provider-reference gaps, settlement totals and ledger balances, plus explicit discrepancies.

Only `ledger:read` may access this view. Every query includes tenant scope and remains protected by PostgreSQL RLS. Cross-tenant identifiers are not accepted as input.

## Acceptance and rollback

Tests cover balanced and mismatched refunds, pending exposure, tenant isolation and role denial. This change has no migration or data mutation; rollback is the prior application image.
