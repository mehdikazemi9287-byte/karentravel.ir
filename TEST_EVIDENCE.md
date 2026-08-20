# Test Evidence

Timestamp: `2026-08-20T07:52:47Z`

| Check | Result |
|---|---|
| Full backend on real PostgreSQL 16.15 + Redis 7.4.10 + worker role | `70/70 passed` in 2.24s; 0 skipped |
| PostgreSQL RLS/FORCE RLS | `56/56`; own-tenant PASS, cross-tenant read/write denied, missing `app.tenant_id` fail-closed |
| Invoice/Support/Installment/Settlement/Admin focused PostgreSQL suite | `5/5 passed` |
| API and worker least privilege | PASS; API NOBYPASSRLS, worker scoped contract PASS |
| Alembic real PostgreSQL upgrade/current/check | PASS, head `20260820_10`, no schema drift |
| Migration rollback/re-upgrade | PASS, 10→09→10; data preserved and recreated tables retained API grants through default privileges |
| Pre-migration backup | PASS, custom dump verified; SHA-256 `9ccd8d191864d1a8e62f630f238d285b5695b55843760128b9cc31513d6c0ba2` |
| Repository backup/restore scripts | PASS, isolated restore at head 10; SHA-256 `c7caa91a0cffad3d4bfbdabf4625b2824d5e96e4498faeaf5fd62de297f8885a` |
| Restored schema integrity | PASS: 137 FKs, 0 unvalidated constraints, 240 valid/ready indexes, 56 policies |
| Production-mode health/readiness/metrics on isolated services | PASS; providers reported `fail_closed` |
| ESLint / TypeScript strict / Next.js production build | PASS / PASS / PASS (22 routes) |
| Playwright Chromium critical E2E | `12/12 passed` in 53.3s |
| Python compile | PASS with isolated pycache |
| npm production audit | PASS, `0 vulnerabilities` |
| JSON/YAML manifests and deploy shell syntax | PASS |
| Docker/Compose runtime validation | BLOCKED on this host: no Docker-compatible runtime; structural YAML validation PASS |

All database work used disposable databases on localhost ports 55434/56379. Production was not contacted or mutated. The backup was restored to a distinct database; rollback and re-upgrade were performed only on isolated staging. External transports remained disabled/fail-closed and no credential-dependent success is claimed.
