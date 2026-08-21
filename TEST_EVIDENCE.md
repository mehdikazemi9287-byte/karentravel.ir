# Test Evidence

## Professional Search UX — 2026-08-21

| Check | Result |
|---|---|
| Search interaction E2E | autocomplete, origin/destination, dates, passengers, trip type, submit, results, filter, sort, compare and edit PASS |
| Chromium full regression | `16/16 passed`; `.last-run.json` status `passed`, zero failed IDs |
| Backend Search focused | `6/6 passed`, including public autocomplete typo and tenant-data exclusion |
| Backend local regression | `83 passed, 5 skipped`; skips are the existing PostgreSQL/Redis runtime gates; prior real integration evidence remains valid |
| Frontend | ESLint PASS; strict TypeScript PASS; production build PASS (32 routes) |
| Security | unauthenticated autocomplete is public geo-only; authenticated tenant Offer results; no frontend-authoritative price/availability |
| Screenshots | six PNG files in `artifacts/search-ux/`: Homepage Search Desktop, autocomplete, date picker, passenger picker, results Desktop and results Mobile |
| Homepage identity | Header, Hero, imagery, section order, typography, palette and footer unchanged; Search Box footprint/style retained |
| npm audit / Python compile / diff check | `0 vulnerabilities` / PASS / PASS |

## Unified Search + Checkout increment — 2026-08-21

| Check | Result |
|---|---|
| Real PostgreSQL 16 + Redis full backend | `87/87 passed`, `0 skipped` on clean disposable DB |
| Search/Checkout/Review/ZarinPal focused | `14/14 passed`; ZarinPal uses contract fake transport only, not sandbox certification |
| Migration | upgrade empty DB → `20260820_13`; Alembic current/check and no drift PASS |
| Pre-migration backup | custom dump SHA-256 `9339362ef26582d7142fea14c0f72337fd43d6c12161d8951ca0b741ea7c4211` |
| PostgreSQL tenant protection | `67/67` RLS + FORCE; missing context, own tenant, cross-tenant read/write PASS |
| Roles | API NOBYPASSRLS and worker SELECT/UPDATE-only outbox contract PASS |
| Frontend | ESLint PASS; strict TypeScript PASS; production build PASS (32 routes) |
| Chromium E2E | `15/15 passed` after fixing the reload-session regression; includes Search/session, saved travel, and Homepage Desktop/Mobile visual regression |
| Homepage freeze | `app/page.tsx`, `app/globals.css`, `public/images` source diff zero; Desktop/Mobile screenshot gate PASS |
| Python compile / npm audit / diff check | PASS / `0 vulnerabilities` / PASS |
| External providers | no real provider, map, SMS or ZarinPal sandbox success claimed |

## Saved Travel ecosystem increment — 2026-08-20T09:34:20Z

| Check | Result |
|---|---|
| Full credential-independent backend | `73 passed, 5 skipped`؛ skipها فقط PostgreSQL/Redis/worker integration نیازمند runtime هستند |
| New Saved Trip/Review/Destination/Itinerary API tests | `3/3 passed`؛ own/cross-tenant، idempotency، verified forgery، moderation RBAC، supplier response integrity و live-availability fallback |
| Deterministic comparison awards | PASS؛ شش award و `deterministic-v1` تست شد |
| Alembic isolated upgrade/current/check | PASS؛ `20260820_11 (head)` و no drift روی SQLite disposable |
| PostgreSQL migration/RLS for migration 11 | BLOCKED؛ `docker`, `postgres` و `psql` در میزبان حاضر نیستند؛ evidence پیشین head 10 و `56/56` جایگزین این آزمون نشده است |
| ESLint / strict TypeScript / Next build | PASS / PASS / PASS؛ ۲۶ route |
| Chromium E2E | `14/14 passed`؛ شامل Saved Travel/Itinerary/Destination/Map fallback |
| Frozen Homepage regression | PASS؛ Desktop 1440×1000 و Mobile 390×844، RTL و landmarkها؛ هیچ source file بصری Homepage تغییر نکرد |
| npm dependency audit | PASS؛ `0 vulnerabilities` از registry رسمی |
| `git diff --check` | PASS |
| ZarinPal TEST | BLOCKED BY CREDENTIAL و adapter اختصاصی هنوز internal remaining؛ هیچ success جعلی ثبت نشد |

## Ecosystem Search increment — 2026-08-20T09:07:00Z

| Check | Result |
|---|---|
| Search 2.0 + booking focused backend | `13/13 passed` |
| Full credential-independent backend | `70 passed, 5 skipped` (the five existing PostgreSQL/Redis/worker integration gates retain prior real-staging PASS evidence) |
| Search vertical/normalization/freshness/filter/map/tenant tests | `5/5 passed` |
| ESLint / strict TypeScript / Next production build | PASS / PASS / PASS, 22 routes |
| Chromium E2E | `13/13 passed` in 54.9s |
| Frozen Homepage Desktop/Mobile | PASS at 1440×1000 and 390×844; rendered screenshots non-empty, RTL and approved structural landmarks present; no UI source diff |
| Python compile | PASS with isolated pycache |
| npm production audit | PASS, 0 vulnerabilities |
| ZarinPal sandbox purchase | BLOCKED BY CREDENTIAL; no request/verify success claimed |

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
## Search UX operational evidence — 2026-08-21T13:49:55Z

| Check | Result |
|---|---|
| Visible Search journey | PASS: Persian typo/autocomplete → date/flexibility → passengers/trip type → structured submit → results/edit/filter/sort |
| Real result actions | PASS: Wishlist and Trip Basket POST to SavedTrip APIs; price/availability recheck POSTs to authoritative Offer endpoint; selected Offer IDs feed Compare |
| Focused backend | `15/15 passed` across Unified Search v2, ecosystem Search and Saved Travel |
| Full local backend | `84 passed, 5 infrastructure-skipped`; no new skips. The five require live isolated Redis/PostgreSQL/worker URLs; prior real certificate remains `87/87`, RLS/FORCE `67/67` |
| Frontend | ESLint PASS; strict `tsc --noEmit` PASS; Next.js 16 production build PASS (32 routes) |
| Chromium | focused Search UX PASS; full regression `16/16 PASS` after deterministic selector/state corrections |
| Security | authenticated tenant results/mutations; no frontend-authoritative price/availability; Search Box contains no Mock/demo success; npm audit `0 vulnerabilities` |
| Screenshots | nine reviewed PNGs: Homepage default, origin autocomplete, destination autocomplete, date picker, passenger picker, results Desktop, filter panel, comparison and results Mobile |
| Homepage identity | Desktop/Mobile structure, Header, Hero, imagery, palette, typography, section order and Footer unchanged |
| Migration | unchanged `20260820_13`; no database mutation in this UI phase |
## Travel Commerce evidence — 2026-08-21T14:24:38Z

| Check | Result |
|---|---|
| Vacation Rental/Tour/Visa/Cruise backend | `3/3 PASS`: idempotency، own/cross-tenant، overlap، oversell، human document review، PII non-disclosure و cruise fail-closed |
| Full local backend | `87 passed, 5 infrastructure-skipped`; skip جدیدی اضافه نشد. پنج gate به PostgreSQL/Redis/worker واقعی نیاز دارند |
| Migration | empty isolated SQLite → `20260821_14`; Alembic current/check و no drift PASS |
| PostgreSQL head 14 RLS | BLOCKED on this host: `docker` و `postgres` نصب نیستند؛ evidence پیشین head 13 (`67/67`) جایگزین validation دوازده جدول جدید نشده است |
| Frontend | ESLint PASS؛ strict TypeScript PASS؛ Next.js 16 build PASS (35 generated pages/routes) |
| Chromium | `17/17 PASS`؛ Search UX، Homepage Desktop/Mobile و Travel Commerce workflow |
| Travel Commerce screenshots | ۹ PNG: Villa results/detail، Tour results/detail/booking، Visa detail/application/timeline، Cruise fail-closed state |
| Homepage source protection | `app/page.tsx`، Hero/Header/assets و section order بدون diff؛ structural Desktop/Mobile regression PASS |
| Security | cross-tenant negative، RBAC review، hashed passport reference، no unpaid voucher، no fake Cruise/Payment success PASS |
# Latest travel-commerce closure evidence — 2026-08-21

- Backend: `87 passed, 5 skipped` (the five are pre-existing infrastructure gates; no new skip).
- Travel commerce regression: `3/3 PASS`, including Tour→Visa ownership link and `tour_linked` timeline event, villa overlap/idempotency and truthful cruise blocking.
- Browser: full Chromium `17/17 PASS`; focused Search interaction PASS. Fresh artifacts include `villa-search-state.png` and `tour-search-state.png`, plus refreshed desktop/mobile and popover captures.
- Migration: isolated SQLite `20260821_15` upgrade/current/check, downgrade to `20260821_14`, and re-upgrade PASS. PostgreSQL Head 14/15 direct validation is not claimed without a runtime.
