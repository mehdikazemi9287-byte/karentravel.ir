# Test Evidence

Timestamp: `2026-08-20T02:19:41Z`

| Check | Result |
|---|---|
| Backend credential-independent suite | `55 passed, 5 skipped` in 1.65s |
| Real PostgreSQL + Redis + worker suite (latest isolated staging) | `59 passed` |
| PostgreSQL RLS/FORCE RLS | `52/52` tenant tables |
| ESLint | PASS |
| TypeScript strict (`tsc --noEmit`) | PASS |
| Next.js 16.3.1 production build | PASS, 16 routes |
| Playwright Chromium critical E2E | `3/3 passed` in 13.3s |
| Python compile | PASS with isolated pycache |
| Alembic fresh upgrade/check | PASS, head `20260820_09`, no new operations |
| npm production audit | `0 vulnerabilities` |
| Load smoke baseline | 500/500, 0 errors, p95 184.29ms |
| Backup/restore isolated PostgreSQL | PASS, dump SHA-256 `4955a47c6357e6d540f2bd1969cfc82e7e3ef7ca0a0af7e2e54badef05c0cef5` |
| Release pointer rollback | PASS, v1→v2→v1 |

The five local skips are the real PostgreSQL/Redis/worker tests; they have separate passing isolated-staging evidence above. Public-provider success was not tested or claimed because credentials do not exist.
