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

قالب Nginx فقط TLS 1.2/1.3، redirect HTTPS، HSTS، headerهای امنیتی، body/timeouts، gzip و request/correlation headers را تعریف می‌کند. Brotli فقط در صورت module رسمی و تست‌شده روی target فعال می‌شود. CSP پس از inventory دامنه‌های image/API و browser regression test اضافه می‌شود.

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
