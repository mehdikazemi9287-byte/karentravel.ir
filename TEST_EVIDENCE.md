# Test Evidence

Timestamp: `2026-08-20T07:17:20Z`

| Check | Result |
|---|---|
| Backend credential-independent suite | `64 passed, 5 skipped` in 2.05s |
| Real PostgreSQL + Redis + worker suite (latest isolated staging) | `59 passed` |
| PostgreSQL RLS/FORCE RLS | latest real staging `52/52`; migration head 10 declares RLS/FORCE for 4 new tables, metadata total `56` |
| ESLint | PASS |
| TypeScript strict (`tsc --noEmit`) | PASS |
| Next.js 16.3.1 production build | PASS, 22 routes |
| Playwright Chromium critical E2E | `12/12 passed` in 49.0s |
| Domain/RBAC/cross-tenant focused suite | PASS, 4 tests covering invoice, support, installment, settlement and admin role negatives |
| Python compile | PASS with isolated pycache |
| Alembic fresh upgrade/check | PASS on isolated SQLite, head `20260820_10`, no new operations |
| npm production audit | `0 vulnerabilities` |
| Load smoke baseline | 500/500, 0 errors, p95 184.29ms |
| Backup/restore isolated PostgreSQL | PASS, dump SHA-256 `4955a47c6357e6d540f2bd1969cfc82e7e3ef7ca0a0af7e2e54badef05c0cef5` |
| Release pointer rollback | PASS, v1→v2→v1 |

The five local skips are the real PostgreSQL/Redis/worker tests; head 09 has separate passing isolated-staging evidence above. Head 10 was upgraded and schema-checked on an isolated SQLite database; its four-table PostgreSQL RLS/FORCE SQL is present but has not been applied to a real target in this pass. Browser evidence also covers the human-support thread and finance RBAC state. Backend negative tests verify invoice ownership, cross-tenant support, finance role denial and admin privilege-escalation denial. Public-provider or external-transfer success was not tested or claimed because credentials do not exist.
