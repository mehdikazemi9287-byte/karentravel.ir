# ADR-014: Authenticated Frontend Read Models

## Decision

Approved pages consume only authenticated, tenant-scoped API read models. A root client provider keeps access and rotating refresh tokens in memory across client navigation; tokens are never written to local/session storage. Only a non-sensitive random device identifier is session-scoped. Full reload intentionally requires login again until an HttpOnly BFF session is introduced.

Trips, notifications and organization overview receive dedicated read-only endpoints. Supplier, Agency, BackOffice and finance pages reuse their existing permission-guarded endpoints. UI states distinguish loading, empty, unauthorized, forbidden, provider unavailable and generic error. Demo fixtures remain only on explicitly identified sample identifiers and are never presented as live data.

## Acceptance and rollback

API tests cover tenant isolation and role denial. Playwright covers authenticated navigation, empty/success views and panel RBAC. No schema or production data changes are made. Rollback is the previous frontend/backend image.
