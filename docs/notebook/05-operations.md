# کارن تراول — استقرار و عملیات

> منبع: مخزن karentravel.ir — تجمیع خودکار برای Gemini Notebook (2026-11-24)


---

## فایل: DEPLOYMENT.md

# استقرار کارن‌سیر — پایلوت

## پیش‌نیاز

Docker Engine و Docker Compose Plugin، یک reverse proxy با TLS، و دامنه‌های تأییدشده لازم است. فایل `.env` را از `.env.example` بسازید، سپس برای `POSTGRES_PASSWORD` و `JWT_SECRET` مقدار تصادفی و قوی قرار دهید. این فایل هرگز نباید commit شود.

در استقرار هدف، secret manager باید فایل‌های private با permission برابر `0600` mount کند و متغیرهای `DATABASE_URL_FILE`، `JWT_SECRET_FILE` و `REDIS_URL_FILE` به آن‌ها اشاره کنند. تعریف هم‌زمان مقدار مستقیم و `_FILE` عمداً startup را متوقف می‌کند. rotation ابتدا روی staging، سپس با image rollback موجود و در نهایت revoke نسخه قبلی انجام می‌شود.

قالب `docker-compose.production-secrets.yml` مقدارهای مستقیم را حذف و Docker secretهای external را mount می‌کند:

```bash
docker compose -f docker-compose.yml -f docker-compose.production-secrets.yml up -d --build
```

## اجرا

```bash
docker compose --env-file .env up -d --build
```

API پس از اجرای migration در `http://localhost:8000` فعال است؛ healthcheck: `GET /health`.
کانتینر API از `backend/entrypoint.sh` استفاده می‌کند و پیش از Uvicorn، `alembic upgrade head` را fail-fast اجرا می‌کند.

## Frontend

در محیط build از Node 20 استفاده کنید:

```bash
npm ci
npm run build
npm run start
```

برای production، reverse proxy باید فقط HTTPS را پذیرفته و `CORS_ORIGINS` را برابر origin واقعی frontend قرار دهد.

## عملیات

- قبل از ارتقا: backup رمزگذاری‌شده PostgreSQL و آزمون restore.
- migration: container API پیش از start، `alembic upgrade head` را اجرا می‌کند.
- credential Provider/OTP/Payment را فقط در secret manager تزریق کنید؛ نبود آن‌ها باید fail-closed بماند.
- endpoint توسعه‌ای `/auth/dev-login` فقط با `ENVIRONMENT=development` فعال است.

## Migration و worker

قبل از start نسخه جدید:

```bash
docker compose run --rm api alembic upgrade head
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:3000/
```

`worker` outbox را پردازش می‌کند. تا وقتی adapter معتبر نصب نشده، deliveryها به retry/dead-letter می‌روند و هیچ SMS/Push واقعی ارسال نمی‌شود.

در Production provider mode برابر `mock` ممنوع است. تنها deployment صریحاً برچسب‌خورده با `DEMO_MODE=true` می‌تواند mock داشته باشد و چنین deploymentی Production rollout محسوب نمی‌شود.

پس از فعال‌شدن RLS، API فقط با نقش بدون `BYPASSRLS` اجرا می‌شود. outbox worker برای polling میان tenantها به `WORKER_DATABASE_URL` با نقش جدا، least-privilege و دارای `BYPASSRLS` نیاز دارد؛ این نقش باید خارج از migration اپلیکیشن توسط DBA ساخته و در secret manager نگهداری شود. استفاده از credential نقش worker در API ممنوع است.

نقش API با `deploy/provision-api-role.sql` به‌صورت `NOBYPASSRLS` و بدون CREATE/role/database privilege ساخته می‌شود. اجرای هر دو template فقط توسط DBA و با password ورودی secret manager مجاز است.

این template علاوه بر grantهای جدول‌های موجود، default privilegeهای owner migration را برای جدول/sequenceهای آینده ثبت می‌کند. پس از هر migration و به‌ویژه پس از downgrade/upgrade باید template دوباره idempotently اجرا و دسترسی جدول‌های جدید با نقش API آزموده شود؛ API هرگز نباید owner یا `BYPASSRLS` باشد.

DBA می‌تواند template کنترل‌شده `deploy/provision-worker-role.sql` را با `psql --set=worker_password='...' --file=...` اجرا کند. password باید از secret manager وارد شود و در shell history یا repository ذخیره نشود. پس از provision، تست `TEST_WORKER_POSTGRES_URL` باید نبود دسترسی users و دسترسی محدود outbox را اثبات کند.

## Backup، restore و rollback

پیش از هر migration، `deploy/preflight.sh` و سپس `deploy/backup.sh` اجرا می‌شود. restore باید ابتدا با `deploy/restore-verify.sh` فقط در یک دیتابیس ایزوله و غیر Production آزموده شود؛ script عمداً نام‌های `karenseir` و دیتابیس‌های سیستمی را رد می‌کند.

هر دو script checksum را با `sha256sum` یا `shasum -a 256` محاسبه/تأیید و در نبود هر دو ابزار fail می‌کنند.

```bash
docker compose exec -T db pg_dump -U karenseir -Fc karenseir > karenseir-before-upgrade.dump
docker compose exec -T db pg_restore --clean --if-exists -U karenseir -d karenseir < karenseir-before-upgrade.dump
```

Rollback امن شامل بازگرداندن image قبلی و restore backup آزموده‌شده است. migration پایه عمداً downgrade مخرب ندارد. reverse proxy باید TLS، محدودیت body، timeout و forwarding امن `X-Request-ID` را اعمال کند.

Migration RLS افزایشی است و داده را تغییر نمی‌دهد. rollback آن policyها را غیرفعال می‌کند؛ restore کامل فقط در صورت شکست migration/data verification و پس از توقف writerها انجام می‌شود. Redis rate-limit keyها TTL دارند و در rollback نیاز به حذف ندارند.

## Reverse proxy و monitoring

قالب Nginx در `deploy/nginx.conf.example` قرار دارد. hostname و مسیر certificate باید فقط با مقادیر مجاز سرور جایگزین شوند؛ این مخزن certificate صادر نمی‌کند. Health/readiness، logهای JSON، `X-Request-ID`، `X-Correlation-ID` و `X-Process-Time` نقاط اتصال monitoring هستند؛ collector واقعی خارج از مخزن پیکربندی می‌شود.

قالب scrape و alert rule در `deploy/monitoring/` قرار دارد. target placeholder باید در سامانه monitoring مستقل جایگزین و Alertmanager/receiver واقعی جداگانه اثبات شود. `deploy/validate-public-production.sh` فقط پس از DNS و certificate عمومی مجاز اجرا می‌شود و certificate نامعتبر را به‌دلیل validation پیش‌فرض curl رد می‌کند.

`/health` فقط liveness است. `/ready` اتصال database و Redis توزیع‌شده را کنترل می‌کند و در Production در خرابی Redis پاسخ `503` می‌دهد. alertهای حداقلی باید روی readiness، نرخ 5xx/429، dead-letter outbox، latency و شکست backup/restore تنظیم شوند.

worker روی شبکه داخلی `/health` و `/metrics` در پورت 9101 ارائه می‌کند؛ این پورت نباید public expose شود. Prometheus از شبکه private آن را scrape می‌کند و backlog/dead-letter alert دارد.

قالب Nginx فقط TLS 1.2/1.3، redirect HTTPS، HSTS، body/timeouts، gzip و request/correlation headers را تعریف می‌کند؛ بقیه‌ی headerهای امنیتی برای پاسخ‌های برنامه فقط از `next.config.mjs` و FastAPI می‌آیند تا هر header یک‌بار فرستاده شود. در پیکربندی تولیدشده‌ی `deploy/karenseir-https.sh` (و `deploy/nginx.karentravel-https.conf`)، nginx سرآیندهای `X-Content-Type-Options`، `X-Frame-Options` و `Referrer-Policy` را فقط روی پاسخ‌های خودش اضافه می‌کند (redirect، ACME، 502/504، 503)، یعنی وقتی upstream آنها را نفرستاده است. روی سرور فعلی (nginx داخل container در `/opt/karenseir`) از `deploy/karenseir-https-container.sh` و `deploy/karenseir-https-container-rollback.sh` استفاده کنید؛ آنجا nginx تنها منبع این چهار سرآیند امنیتی است و نسخه‌ی upstream را با `proxy_hide_header` پنهان می‌کند. `deploy/karenseir-https.sh` فقط برای nginx میزبان است (روش‌ها در README). با تغییر `ZARINPAL_CALLBACK_URL` به `https://karentravel.ir/api/payments/zarinpal/callback`، پیش از فعال کردن پرداخت همین آدرس را در پنل پذیرنده‌ی زرین‌پال هم ثبت کنید. Brotli فقط در صورت module رسمی و تست‌شده روی target فعال می‌شود. CSP پس از inventory دامنه‌های image/API و browser regression test اضافه می‌شود.

## ادامه استقرار روی سرور مجاز

```bash
cp .env.example .env
# مقادیر placeholder را در خود سرور/secret manager جایگزین کنید.
docker compose --env-file .env build
docker compose --env-file .env run --rm api alembic upgrade head
docker compose --env-file .env up -d
docker compose --env-file .env ps
curl --fail https://api.your-domain.example/ready
curl --fail https://your-domain.example/
```

تا وقتی production secret، دامنه HTTPS، PostgreSQL و adapter مجاز فراهم نشده‌اند، اجرای Production باید fail-closed بماند.

## Policy مالیاتی صورتحساب

`INVOICE_TAX_BPS` (basis points) و `INVOICE_TAX_POLICY_REFERENCE` باید از policy حقوقی/مالی تأییدشده target تأمین شوند. در `ENVIRONMENT=production` نبود، منفی/نامعتبر بودن نرخ یا نبود reference باعث `503` هنگام صدور صورتحساب می‌شود. مقدار صفر development صرفاً `development:not_configured` است و مجوز صدور Production محسوب نمی‌شود.

---

## فایل: PRODUCTION_RUNBOOK.md

# Production Runbook

## Gate ورود

DNS عمومی، CA certificate معتبر، secret manager و rotation test، PostgreSQL/Redis managed، collector و alert receiver، image digest و commit provenance، backup/restore و rollback drill باید evidence داشته باشند. `DEMO_MODE` باید false و همه providerهای فعال باید قرارداد و credential معتبر داشته باشند.

## ترتیب استقرار

1. backup رمزگذاری‌شده و restore verification ایزوله؛ ثبت checksum و recovery time.
2. اجرای `deploy/preflight.sh` و migration روی یک job مستقل با همان image release.
3. start API/worker با secretهای mount‌شده، سپس `/health` و `/ready`.
4. smoke test tenant isolation، login، payment fail-closed و metrics.
5. فعال‌سازی release pointer و rollout محدود؛ monitor نرخ 5xx، latency، Redis، outbox و payment/OTP failure.

در outage ابتدا writerها drain، evidence و correlation IDها حفظ و سپس طبق `INCIDENT_RESPONSE.md` عمل شود. هیچ callback یا outbox event دستی بدون idempotency key replay نمی‌شود.

---

## فایل: PRODUCTION_READINESS.md

# Production Readiness

Verdict: **NO-GO**

The credential-independent application and isolated database gates are complete. PostgreSQL migration 10, schema drift, 56/56 FORCE RLS, tenant fail-closed behavior, Redis, least-privilege roles, backup/restore, rollback/re-upgrade, schema integrity, backend, browser and frontend regression all pass with recorded evidence.

## Passing gates

- Real isolated PostgreSQL 16.15 + Redis 7.4.10 backend suite: 70/70; direct RLS/FORCE RLS 56/56.
- Alembic 20260820_10 current/check, backup, isolated restore, downgrade/re-upgrade and restored integrity.
- NOBYPASSRLS API and least-privilege worker; tenant/RBAC/idempotency/audit negative coverage.
- ESLint, strict TypeScript, Next.js build, Chromium E2E 12/12, Python compile and npm audit 0.
- Production-mode health/readiness/metrics with every uncredentialed external adapter fail-closed.

## Unsatisfied production gates

- Public DNS and valid public-CA TLS on the authorized target.
- External Secret Manager, rotation/revocation evidence and production credentials.
- External monitoring collector, Alertmanager receiver and tested escalation path.
- Contracted SMS/OTP, payment and Flight/Hotel/Tour integrations with certification evidence.
- Approved invoice taxation/legal numbering policy (implementation is configurable and Production fail-closed).
- Immutable target image digests, target smoke/backup/rollback drill and controlled rollout evidence.
- Independent penetration/security certification.

No sandbox/mock result is represented as Production success.

---

## فایل: RELEASE_ROLLBACK.md

# Release and Rollback

هر release با version غیرقابل‌تغییر، image digest، source commit، SBOM، migration head و QA evidence ثبت می‌شود. deploy مستقیم source directory ممنوع است.

در workspace فاقد Git، `RELEASE_MANIFEST.json` checksum مستقل source، dependency locks، migration head و timestamp را ثبت می‌کند. تا وقتی commit و image digest واقعی null هستند، manifest صریحاً `provenance_complete=false` است و Production GO نمی‌دهد.

ساختار target:

```text
/opt/karenseir/releases/<version>
/opt/karenseir/current -> /opt/karenseir/releases/<version>
```

`deploy/switch-release.sh` فقط directory موجود زیر release root را با symlink pointer فعال می‌کند. rollback همان command با version قبلی است. migrationهای این repository downgrade مخرب ندارند؛ در ناسازگاری داده، writerها متوقف و backup verify‌شده restore می‌شود.

---

## فایل: BACKUP_RECOVERY.md

# Backup and Recovery

هدف پیشنهادی اولیه: `RPO <= 15m` با WAL/PITR و `RTO <= 2h`. این اعداد فقط پس از drill روی target تعهد عملیاتی می‌شوند.

- backup روزانه full و WAL پیوسته، encryption با KMS بیرونی، retention حداقل ۳۵ روز و یک کپی account/region جدا.
- `deploy/backup.sh` checksum تولید می‌کند؛ `deploy/restore-verify.sh` فقط نام DB ایزوله را می‌پذیرد.
- verification شامل Alembic head، row counts کنترل‌شده، RLS/FORCE RLS، نقش worker، ledger totals و نمونه cross-tenant denial است.
- restore روی Production فقط پس از توقف writerها، ثبت نقطه بازیابی و تأیید Incident Commander انجام می‌شود. dump یا کلید encryption داخل repository نگهداری نمی‌شود.

## Supplier media volume (added 2026-09-10)

Persistent supplier uploads live on the Docker named volume `karenseir_media`
mounted at `/app/media` (`MEDIA_STORAGE_ROOT`). Blob layout:
`tenant/{tenant_id}/supplier/{supplier_id}/{entity_type}/{entity_id}/{uuid}.{ext}`.
Authoritative metadata + access control is the `supplier_assets` table.

Backup:  `docker run --rm -v karenseir_media:/v -v "$PWD":/b busybox tar czf /b/media-$(date +%F).tgz -C /v .`
Restore: `docker run --rm -v karenseir_media:/v -v "$PWD":/b busybox tar xzf /b/media-DATE.tgz -C /v`
A DB dump (`pg_dump -Fc`) must be captured in the same window so `supplier_assets`
rows and blobs stay consistent.

---

## فایل: INCIDENT_RESPONSE.md

# Incident Response

- Severity 1: leakage احتمالی tenant، جعل callback، ledger inconsistency یا secret exposure؛ فوراً rollout متوقف، credential revoke/rotate و Security Lead مطلع شود.
- Severity 2: login/payment/provider outage یا backlog بحرانی؛ fail-closed حفظ و کانال انسانی فعال شود.
- ابتدا زمان، release digest، request/correlation ID، tenant reference و scope ثبت شود؛ secret/OTP/token/PII در ticket قرار نگیرد.
- containment نباید audit/ledger/event history را حذف کند. callback تکراری فقط از payload اصلی و پس از signature validation replay می‌شود.
- recovery با release قبلی و restore آزموده‌شده است. پس از recovery، cross-tenant، ledger reconciliation، queue depth و notification duplication بررسی و postmortem بدون سرزنش ثبت شود.

---

## فایل: STAGING_VALIDATION.md

# Staging Validation — ۱۴۰۵/۰۵/۲۸

## Scope and isolation

Staging محلی و ایزوله با PostgreSQL 16.15 روی `127.0.0.1:55432`، Redis 7.4.10 روی `127.0.0.1:56379` و API TLS روی `127.0.0.1:58443` اجرا شد. دیتابیس `karenseir_staging` و restore target مستقل ساخته شدند؛ دیتابیس فعلی repository به‌عنوان staging استفاده یا migrate نشد.

## Passed evidence

- Alembic تا `20260819_03` روی PostgreSQL واقعی اجرا شد.
- سه تست مستقیم RLS: no-context، own-tenant، cross-tenant read/insert/update و پوشش `FORCE RLS`/policy تمام ۳۶ جدول tenant-scoped پاس شدند.
- Redis Lua rate-limit واقعی، TTL، deny و recovery پاس شد؛ با خاموشی Redis، liveness برابر ۲۰۰، readiness و API برابر ۵۰۳ و پس از restart readiness برابر ۲۰۰ شد.
- API در mode Production با PostgreSQL/Redis و Providerهای fail-closed بالا آمد؛ rate limit واقعی در درخواست یازدهم `429` و `Retry-After` داد.
- نقش worker دارای `BYPASSRLS`، بدون دسترسی users و با SELECT/UPDATE محدود روی جداول outbox/notification آزموده شد. worker واقعی event را به retry با `external_provider_not_configured` برد.
- backup custom-format با checksum ساخته شد؛ restore روی DB ایزوله تا Alembic head، ۱۰ user و ۳۶ policy RLS verify شد.
- TLS staging با certificate موقت self-signed، SAN و TLS 1.2 handshake پاس شد. این certificate مجوز rollout عمومی نیست.
- Playwright با Google Chrome سیستم هر سه critical suite را پاس کرد.

## Rollback

تمام سرویس‌ها و داده‌های staging در `/private/tmp` و پورت‌های غیر Production قرار دارند و با توقف processها قابل جمع‌کردن‌اند. هیچ Provider/OTP/Payment واقعی فعال نشد. Production rollout همچنان به certificate معتبر، دامنه، secret manager، monitoring collector و backup مقصد Production نیاز دارد.


---

## فایل: PORTAL_VERIFICATION.md

# Portal Re-Verification — 2026-09-11

Real-browser + API verification of every portal after the public-media and
notification-foundation deploys. Sessions minted server-side (dev-login is 404 in
prod, OTP provider disabled); temporary role users created and deleted.

## Matrix

| Portal | Route | Connected? | Evidence |
|---|---|---|---|
| Customer / B2C | `/account` | **DONE** | 12 API calls all 200 (`/me/profile,travellers,wallets,payments,reservations,notification-preferences,installment-plans,installments,invoices,trips,notifications`, `/support/cases`); real name/wallet (۵۰۰٬۰۰۰), traveller row, honest "no payment credential" state; empty states; RTL; 0 console errors |
| Customer trips list | `/trips` | **DONE** | `ConnectedTrips`, `/me/trips` 200 |
| Customer trip detail | `/trips/[id]` | **MOCK** | explicit `<MockNotice>` — "رزرو، واچر و مسافران این سفر نمونه" |
| Customer manage-booking | `/manage-booking/[id]` | **PARTIAL** | real UUID → `ConnectedManageBooking` (connected); literal `book1` etc. → mock |
| Customer support | `/support` | **DONE** | `SupportLanding` + `SupportComposer`, `/support/cases` 200 |
| Corporate | `/organization` | **DONE** | `ConnectedOrganization`, `/organization/overview` 200; real org ("سازمان اعتبار عمومی · active"), cost-centre/approval counts, empty states. Minor: page uses the public `<Shell>` header, not the authed header |
| Corporate finance | `/finance` | **CONNECTED (API)** | `ConnectedFinance` → `/finance/reconciliation` 200 for `finance_operator`, 403 for others. Not browser-verified — no finance user seeded in prod |
| B2E / Employee | `/employee` | **MOCK** | `app/page.tsx` `Employee()` → hardcoded `Dashboard` (۴۸٬۰۰۰٬۰۰۰ ریال, every tile labelled "Mock"); **zero API calls**. No employee credit/approval/request component exists |
| Agency / B2B | `/agency` | **PARTIAL** | `/agency/dashboard` 200 + RBAC enforced (agency↔backoffice↔supplier mutually 403); UI is the generic `ConnectedRolePanel` (sub-agency form + JSON dump). No dedicated dashboard / booking / traveller / commission views |
| Supplier | `/supplier` | **DONE** | fully verified in the media workstream — upload/preview/replace/delete, membership scoping, cross-supplier + cross-tenant isolation |
| Admin | `/admin` | **DONE** | `ConnectedAdmin`, `/admin/users` 200; real tenant-1 user list, role change with privilege-escalation guard + audit; cross-tenant → 403 |
| Backoffice / Ops | `/backoffice`, `/integrations` | **DONE** | `ConnectedRolePanel kind=backoffice`, `/backoffice/overview` 200; real reservations (KS-7E01247…, KS-VILLA-…), invoice-issue mutations, supplier-status management, human support reply |
| White-label | `/white-label` | **MOCK** | explicit "Prototype", hardcoded credit figures |

Other mock/demo routes: `/nearby`, `/services`, `/booking/confirmation`, `/assistant`.

## RBAC / tenant isolation — 18/18 API checks pass

- customer token → every admin/ops/agency/backoffice/finance/supplier endpoint = 403
- agency ↔ backoffice ↔ supplier — mutually 403 (no privilege bleed)
- faraz (tenant 2) → aftab admin data = 403
- `_supplier_scope` membership boundary holds (verified separately)

## Prod seeding gap (not a code defect)

Prod tenant `aftab-bank` seeds only `employee, welfare_manager, supplier,
organization_admin`. No `agency_partner / backoffice_expert / finance_operator /
tenant_admin / platform_admin` user exists — those portals can only be exercised
by creating a user. A prod seed/backfill for operator roles is recommended.

## Internally-implementable gaps found

1. **B2E / Employee portal** — replace the mock `Dashboard` with a connected view
   over `/me/*` + org credit + `/approvals` (the APIs already exist).
2. **Agency portal** — dedicated dashboard/bookings/commission UI instead of the
   generic JSON panel.
3. **Trip detail `/trips/[id]`** — wire to `/trips/{id}` + `/trips/{id}/timeline`
   (the "چه چیزی در سفر من تغییر کرده؟" event feed already exists server-side).
4. Corporate `/organization` — use the authenticated shell header.

---

## فایل: TEST_EVIDENCE.md

# Test Evidence



## Booking → payment → financial journey (demo → real) — 2026-08-23

| Check | Result |
|---|---|
| Migration `20260823_19` upgrade/downgrade/upgrade on real Postgres RC clone | PASS |
| Production migration applied: row counts unchanged (reservations=2, financial_ledger_entries/wallets/credit_accounts=0, users=4), `wallet_id`/`credit_account_id` both nullable, new FK+index present, RLS/FORCE unaffected, `karenseir_api` still NOBYPASSRLS | PASS |
| `alembic current == alembic heads`, `alembic check` = no drift on production | PASS |
| Backend regression (SQLite, `ENVIRONMENT=development`) | 92 passed, 6 skipped, 0 failed |
| New `test_booking_financial_journey.py`: real org-credit + wallet reserve→capture on fulfillment, auto-invoice issuance, real Trip Timeline payment.captured event, fail-closed over-limit, tenant isolation; separate release-on-cancellation test | PASS |
| Live public verification (`http://95.38.184.209/`, real seeded accounts): real supplier/offer/authoritative-recheck/booking, real traveller, real wallet allocate + real org credit account via real endpoint, tenant isolation (other tenant sees 0 credit accounts), real funding reserve with live balances, fail-closed over-limit (409), real payment intent, real gateway-initiate fail-closed (503, honest, no fabricated redirect), real cancel-request → real `reservation.cancel_requested` Trip Timeline event | PASS, desktop + mobile |
| Checkout funding UI (real wallet/credit number inputs with live balances) | PASS, desktop + mobile, verified via `input[type="number"]` DOM presence, not just screenshot text |
| Deployment drift check: API and frontend container source parity vs repo | PASS after one real drift caught and fixed mid-verification (frontend rebuild forgotten after a UI edit) |

## Post-booking journey (demo → real) — 2026-08-23

| Check | Result |
|---|---|
| Migration `20260823_18` upgrade/downgrade/upgrade on real Postgres RC clone | PASS |
| Production migration applied: row counts unchanged (reservations 0, trips 0, trip_events 0, users 3, tenants 2), FK 200→201, indexes 387→388, RLS/FORCE unaffected | PASS |
| `alembic current == alembic heads`, `alembic check` = no drift on production | PASS |
| Backend regression (SQLite, `ENVIRONMENT=development`) | 90 passed, 6 skipped, 0 failed |
| New `test_post_booking_journey.py`: real villa booking → real Trip, real tenant-isolated `booking.created` timeline event, real `reservation.cancel_requested` on cancellation, real notification with correct `deep_link` | PASS |
| Live public verification (`http://95.38.184.209/`, real seeded test account, real booking created via real onboarded supplier): My Trips, Trip Detail/Timeline, Manage Booking, Support CTAs, Notifications — all real data, no mock markers | PASS, desktop + mobile |
| Cross-tenant isolation: `/me/trips` empty for other tenant, direct trip/timeline/history access 404s | PASS |
| `npx tsc --noEmit` | clean |
## Production gates + release candidate — 2026-08-23

| Check | Result |
|---|---|
| Migration on real production-clone (pg_dump restore, prod untouched) | upgrade empty→`20260822_17` PASS on fresh disposable AND on a clone restored from an actual `pg_dump` of live production; data preserved exactly; rollback→re-upgrade clean; zero drift both times |
| Production backup | checksum `98decea27ac242de9e5a83b0176fc71429fa8f0569ca125271ee03172904c400`, saved at `/home/ubuntu/release-candidate-evidence/` |
| RLS/FORCE (12 new tenant tables) | `85/85` via `backend/scripts/validate_postgres_rls.py`, run on both the fresh disposable DB and the production-clone |
| RLS/FORCE (generic, all tables incl. original production tables) | `4/4` (`test_production_controls.py -k postgresql`) |
| Identity-lookup security (new) | `1/1` new test `test_identity_lookup_function_is_narrow_and_does_not_weaken_rls`: valid lookup resolves correct tenant, unknown email fails closed, general RLS unweakened after the call |
| Focused travel-commerce (incl. new villa pricing test) | `4/4 PASS` on real PostgreSQL |
| Local backend (SQLite) | `88 passed, 6 skipped`; skips are pre-existing + one new Postgres-only gate for the identity test, same pattern as before |
| Frontend | ESLint PASS; strict TypeScript PASS; Next.js build PASS (36 routes) |
| Full E2E — fresh dev-server DB | `17/17 PASS` |
| Full E2E — RC clone (built API+frontend images, real Postgres) | `15/17`; the 2 failures traced precisely to the RC clone's own repeated-run reuse (E2E fixture's hardcoded `suffix='manage'` default colliding with a stale price-check from an earlier run in this session) — not a code defect; both areas pass cleanly on a fresh DB |
| Same-origin `/api` routing | `curl` verified end-to-end through an isolated nginx instance: `/` → frontend, `/api/health` and `/api/search/v2` → API; client bundle contains no `localhost:8000`, contains `/api` |
| CORS exact-origin enforcement | `curl` OPTIONS preflight: configured origin gets `Access-Control-Allow-Origin` echoed back; unconfigured origin gets no header (browser blocks it) — confirmed not wildcard |
| `git diff --check` | PASS |
| Homepage identity | zero diff on `app/page.tsx`, no CSS selector reused/overridden — new CSS is additive-only, new classes not used elsewhere |

Real-Postgres identity/RLS positive+negative matrix, migration-on-production-clone, and same-origin routing proof are new evidence categories this session, closing all three internally-controllable production gates. Production database and live containers were not modified. External blocker recorded: no domain/TLS on this host, required before `ENVIRONMENT=production` can start with real CORS.


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
