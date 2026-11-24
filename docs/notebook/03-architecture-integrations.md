# کارن تراول — معماری و یکپارچه‌سازی‌ها

> منبع: مخزن karentravel.ir — تجمیع خودکار برای Gemini Notebook (2026-11-24)


---

## فایل: INTEGRATION_ARCHITECTURE.md

# Integration Architecture

هر provider یک Adapter مستقل با contract نرمال‌شده دارد: search، quote، reserve، ticket/confirm، cancel/refund و webhook. Integration Hub credential vault reference، sandbox/production، correlation ID، error rate، latency، quota، circuit breaker، retry، manual disable، routing/failover، commission/cost/quality را نگه می‌دارد.

Adapter بدون endpoint و credential معتبر fail-closed است؛ UI هرگز «connected» یا قیمت زنده جعلی نشان نمی‌دهد. Amadeus، Booking و دیگر نام‌ها صرفاً دسته احتمالی اتصال‌اند، نه قرارداد فعلی. API خروجی و Widget با OAuth/API key، rate limit، tenant scope، idempotency و signed webhook طراحی می‌شوند.

WordPress صرفاً CMS/channel/widget host است؛ منطق رزرو، مالی و policy خارج از آن باقی می‌ماند.

## Contract اجرایی adapter

تمام adapterها context شامل `tenant_id`، `correlation_id` و `idempotency_key` دریافت می‌کنند و contract آن‌ها configuration validation، timeout، retry policy محدود، خطای ساختاریافته و health status را الزام می‌کند. implementation فعلی `DisabledMockAdapter` همواره `not_sent` برمی‌گرداند؛ این رفتار برای Flight، Hotel، Tour+Hotel، Train، Payment، OTP، SMS، Push، Email، Inventory و Issuance عمدی است.

جریان قابل توسعه: `Provider/Admin → TripEvent → OutboxEvent → NotificationDeliveryAttempt → Web/App/Push/SMS/Human Support`. worker فعلی retry با backoff و dead-letter پس از پنج تلاش را مدل می‌کند، ولی هیچ کانال بیرونی متصل نیست.
# الحاقیه Identity و Payment

OTP delivery فقط از Adapter و پس از ایجاد challenge hash-only انجام می‌شود؛ failure هیچ sessionی نمی‌سازد. Payment callback از raw-body HMAC، tenant context امضاشده، provider event id یکتا و state machine استفاده می‌کند. Refund از outbox عبور می‌کند و provider processing consistency تراکنش اصلی را تغییر نمی‌دهد.

Providerها اکنون پشت resilience wrapper توزیع‌شده قرار دارند. Search/booking external فقط پس از response موفق adapter جلو می‌رود؛ manual supplier fulfillment فقط برای supplier فعال و با payment capture/audit مجاز است. Notification worker health/metrics مستقل روی پورت داخلی 9101 دارد.

---

## فایل: PROVIDER_INTEGRATION_GUIDE.md

# Provider Integration Guide

Adapter جدید باید contract موجود `IntegrationAdapter` را پیاده کند و timeout، retry محدود با jitter، circuit breaker، provider rate limit، idempotency، health و correlation ID داشته باشد. credential فقط از secret manager و جدا برای environment/tenant خوانده می‌شود.

- Search response فقط timestamp، currency، expiry و provider reference معتبر برمی‌گرداند.
- Booking/payment/OTP موفقیت را فقط پس از response معتبر provider اعلام می‌کنند.
- Payment callback باید raw-body HMAC، event id یکتا، amount/currency و state transition را verify کند.
- OTP code/token در log ذخیره نمی‌شود؛ delivery reference غیرحساس ذخیره می‌شود.
- sandbox با Production متفاوت است و `DEMO_MODE` مبنای rollout نیست.

پیش از فعال‌سازی: contract test، timeout/retry/circuit test، duplicate/replay test، credential rotation، outage drill، observability و قرارداد تجاری/حریم خصوصی لازم است.

---

## فایل: EXTERNAL_BLOCKERS.md

# External Blockers

All adapters remain fail-closed until these are supplied and validated outside Git:

- `BLOCKED_EXTERNAL_CREDENTIAL`: contracted SMS/OTP transport credential and approved sender.
- `BLOCKED_EXTERNAL_CREDENTIAL`: payment merchant credential, callback secret and provider certification.
- `BLOCKED_EXTERNAL_CREDENTIAL`: contracted Flight, Hotel and Tour provider endpoints/credentials/webhook secrets.
- Public DNS ownership and valid public-CA TLS certificate.
- External secret manager with rotation/revocation evidence.
- External Prometheus-compatible collector and Alertmanager receiver.
- Authorized target infrastructure and security-testing engagement.
- Approved legal/finance invoice tax rate, policy reference and numbering requirements; Production invoice issuance is fail-closed until configured.
- Immutable container image build/digests and target backup/rollback smoke evidence (no container runtime is available on this validation host).

These blockers do not authorize fallback to mock transports in Production.

---

## فایل: RISK_ASSUMPTION_DEPENDENCY_REGISTER.md

# Risk, Assumption & Dependency Register

| نوع | مورد | کنترل/وضعیت |
|---|---|---|
| Assumption | دو سازمان فرضی برای نمایش isolation کافی‌اند | فقط UI؛ backend نیازمند RLS test است |
| Assumption | موجودی و ارقام Prototype Mock هستند | در همه صفحه‌ها برچسب Mock دیده می‌شود |
| Risk | نشت داده بین tenant | RLS، tenant context، audit و penetration test پیش از Production |
| Risk | توهم AI درباره قیمت | ابزار authoritative و fail-closed |
| Risk | provider ناپایدار/بدون قرارداد | adapter، circuit breaker، manual disable و عدم نمایش اتصال |
| Risk | قواعد اعتبار/اقساط | review حقوقی/مالی و ledger server-side |
| Dependency | Provider contracts/credentials | هنوز موجود نیست؛ blocker production integration |
| Dependency | payment/OTP/KYC | adapter و قراردادهای معتبر لازم است |
| Dependency | Brand approval | لوگوی نهایی و مسیر بصری نیازمند تأیید مالک است |

---

## فایل: SECURITY_REVIEW.md

# بازبینی امنیت و صحت مالی — پایلوت

## بازبینی امنیتی ۱۴۰۵/۰۸/۱۷ و رفع‌ها — ۱۴۰۵/۰۸/۱۸

گزارش کامل: `docs/reports/1405-08-17-security-review.md`. تست‌های رگرسیون: `backend/tests/test_security_review_1405_08.py` (۱۹ تست؛ روی کد قبلی ۱۸ مورد رد می‌شد).

### رفع‌شده
- **C-1** `POST /reservations/{id}/commands`: مشتری فقط می‌تواند `cancel_requested` یا `change_requested` بخواهد؛ هر هدف دیگر (confirmed/issued/completed/refunded/cancelled/changed/expired/failed) با 403 رد می‌شود. این انتقال‌ها فقط از مسیرهای کارشناسی (`/fulfill` با پرداخت capture‌شده، میز قطار، تصمیم اقامتگاه با scope تأمین‌کننده)، رویداد پرداخت/تأمین‌کننده یا reaper انجام می‌شوند. سایر فراخوان‌های `transition_reservation` بررسی شدند و نقص مشابهی نداشتند.
- **H-1** شارژ کیف پول، ساخت حساب اعتباری و دستور دستی اعتبار سازمانی فقط با مجوز جدید `credit:fund` (نقش مالی و مدیر پلتفرم)؛ مدیر سازمان و مدیر مستأجر دیگر نمی‌توانند. شارژ کیف پول متعلق به خود کارشناس ممنوع، فقط `allocate` از API پذیرفته می‌شود، سقف هر عملیات `WALLET_FUNDING_MAX_PER_OPERATION` (پیش‌فرض ۵۰۰٬۰۰۰٬۰۰۰ ریال) و سقف حساب اعتباری `CREDIT_ACCOUNT_MAX_LIMIT` (پیش‌فرض ۵٬۰۰۰٬۰۰۰٬۰۰۰ ریال) است و هر عملیات AuditEvent دارد.
- **H-2** در `inventory.py` نقش تأمین‌کننده دیگر از بررسی admin/staff رد نمی‌شود: مسیرها، تأمین‌کننده‌ها، متن قرارداد، لیست مسافران و گزارش فروش فقط برای مدیر/کارمند مجموعه است؛ تأمین‌کننده فقط سری‌ها و پروازهای تأمین‌کننده‌ی خودش را می‌بیند و ویرایش می‌کند. همین الگو در `stays.py` (قراردادهای هتل، اتاق، تقویم) و `charter_quotas.py` (سهمیه‌ی آژانس‌ها) هم بسته شد.
- **/pilot** در build تولیدی 404 است مگر `NEXT_PUBLIC_ENABLE_PILOT=1` یا حالت development؛ در sitemap نبود و در robots همچنان disallow است.
- **M-1** درخواست استرداد: با سیاست کنسلی تأییدشده و رزرو در وضعیت کنسلی/استرداد، سقف = مبلغ کل منهای جریمه (سمت سرور). بدون سیاست تأییدشده، درخواست با وضعیت `pending_review` ثبت می‌شود، callback درگاه نمی‌تواند آن را تسویه کند و مالی با `POST /refunds/{id}/review` مبلغ نهایی (کمتر یا مساوی درخواست) را تأیید یا رد می‌کند. عدد جریمه ساخته نمی‌شود.
- **M-2** `/me/dashboard` فقط رزروهای قدیمی همان کاربر را نشان می‌دهد.
- **M-4** assistant-service و search-service به FastAPI 0.162.0 / Starlette 1.10.0، uvicorn 0.54.0 و pytest 9.0.3 ارتقا یافتند؛ pip-audit بدون آسیب‌پذیری، تست‌ها ۵۲/۵۲ و ۱۲۷/۱۲۷.
- **M-6** سقف روزانه‌ی پیامک برای هر tenant (`SMS_DAILY_CAP_PER_TENANT`، پیش‌فرض ۳۰۰۰) روی ورود OTP و ثبت‌نام؛ پس از رسیدن به سقف پاسخ همان «accepted» عمومی است و پیامکی ارسال نمی‌شود.

### SECURITY_FOLLOWUPS (باقی‌مانده)
- **H-3** HTTPS و `ALLOW_HTTP_*=0` پیش از کاربر واقعی و پرداخت (زیرساخت).
- **H-4** کد آماده: `deploy/karenseir-db-role-check.sh` (بررسی فقط‌خواندنی؛ `--apply` نقش `karenseir_api` را می‌سازد و تغییر `DATABASE_URL` را چاپ می‌کند). تغییر روی سرور با مالک است؛ migrationها با `MIGRATION_DATABASE_URL`.
- **M-3** کد آماده پشت پرچم `AUTH_COOKIE_MODE` (پیش‌فرض خاموش): کوکی httpOnly + CSRF دوتایی. روشن کردن فقط پس از HTTPS با `AUTH_COOKIE_SECURE=1`. CSP با nonce هنوز باز است.
- **M-5** کلیدهای جدا (HKDF از `JWT_SECRET` یا env جدا)؛ پس از انقضای واچرهای قدیمی `SIGNING_LEGACY_FALLBACK=0`.
- **M-7** کد آماده: `deploy/karenseir-demo-data-disable.sh` (غیرفعال‌سازی برگشت‌پذیر داده‌ی نمونه)؛ اجرا روی سرور با مالک. بررسی `ENVIRONMENT=production` روی سرور هنوز لازم است.
- سقف سراسری پیامک بین tenantها (شمارش فعلی زیر RLS برای هر tenant است).

### بسته‌شده در شاخه‌ی fix/security-followups
- **H-1** تأیید دونفره برای شارژ کیف پول، ایجاد حساب اعتباری و تغییر سقف اعتبار (`backend/app/approvals.py`، قابل استفاده‌ی مجدد).
- محدود شدن `/reservations/{id}/fulfill` به تأمین‌کننده/آژانس خود.
- مراحل تأمین‌کننده در `grs_lifecycle` فقط با نقش کارشناس عملیات.

## Orchestration security — ۱۴۰۵/۰۵/۲۹

- Offer/Price Check/Booking و approval/panelها tenant filter، RLS و IDOR tests دارند؛ Price Check با HMAC integrity و مصرف یک‌باره محافظت می‌شود.
- Payment/notification callbackها raw-body HMAC، event replay protection و tenant context امضاشده دارند.
- CSP با `object-src none`، `base-uri/form-action self` و `frame-ancestors none` فعال و browser-tested است. inline script/style فقط به‌دلیل static Next rendering و styleهای موجود مجاز مانده؛ strict nonce CSP نیازمند dynamic rendering و تصمیم معماری جداست.
- Provider keys شامل payload/credential نیستند؛ circuit/throttle state TTLدار و tenant/provider scoped است.

## Identity و Payment security — ۱۴۰۵/۰۵/۲۸

- OTP plaintext ذخیره یا log نمی‌شود؛ HMAC challenge-bound، expiry، row lock، replay denial، attempt limit و account lockout دارد. پاسخ request برای user/provider failure ساختار یکسان دارد.
- JWT claimهای issuer/audience/iat/jti و token type enforce می‌شوند. refresh token hash-only، tenant-scoped، device-bound برای نشست OTP، family-rotated و دارای reuse revocation است؛ logout audit می‌شود.
- callback پرداخت بدون secret خارجی `503` و با signature غلط `401` است. event id یکتا، payload hash، amount match و transition validation مانع forgery/replay/duplicate mutation می‌شوند.
- partial refundهای pending نیز در سقف refundable محاسبه می‌شوند؛ مبلغ از frontend authoritative نیست.
- PostgreSQL واقعی ۴۲/۴۲ tenant table را با RLS+FORCE RLS تأیید کرد. API role `NOBYPASSRLS` و worker role محدود باقی ماندند.
- CSRF بر مسیرهای API مبتنی بر Bearer header اثر cookie-based ندارد؛ CORS explicit است. CSP نهایی وابسته به دامنه/assetهای واقعی است و بدون regression test فعال نشده است.

## کنترل‌های Phase A — ۱۴۰۵/۰۵/۲۸

- secretهای runtime اکنون از mount فایل خصوصی نیز خوانده می‌شوند و direct/file ambiguity، symlink و permission ناامن startup را متوقف می‌کند. مقدار secret log نمی‌شود.
- قالب external Docker secrets برای API، worker، Redis URL و PostgreSQL password اضافه شده است؛ استفاده واقعی و rotation روی target هنوز evidence بیرونی لازم دارد.
- Production provider mock بدون Demo Mode صریح رد می‌شود. Demo Mode هیچ‌گاه مبنای Production GO نیست.
- alert ruleهای نسخه‌شده موجودند، اما تا اتصال collector و receiver واقعی فقط configuration artifact هستند و کنترل عملیاتی فعال محسوب نمی‌شوند.

- Token با expiry امضا می‌شود؛ secret پیش‌فرض فقط برای development است و `.env` commit نمی‌شود.
- tenant از JWT استخراج می‌شود، نه درخواست کاربر؛ بازیابی/approval booking با tenant scope انجام می‌شود و آزمون isolation دارد.
- مبلغ رزرو فقط در backend محاسبه می‌شود؛ frontend فقط نمایش می‌دهد. ثبت اولیه ledger از نوع authorization است، نه capture پرداخت.
- inventory هنگام ایجاد درخواست در transaction کم می‌شود؛ برای production به lock و idempotency key نیاز است.
- Provider و Payment بدون credential معتبر fail-closed هستند.
- خطرهای حل‌نشده پیش از production: RLS/PostgreSQL، rotation secret، TLS/reverse proxy، rate limit، PII retention، audit immutable storage، reconciliation و آزمون امنیت مستقل.

## بازبینی ۱۴۰۵/۰۵/۲۷

- access token به ۱۵ دقیقه محدود و claim نوع token enforce شد؛ refresh token opaque با hash SHA-256، انقضای ۳۰روزه، rotation یک‌بارمصرف و revocation ذخیره می‌شود. اتصال OTP واقعی همچنان غیرفعال است.
- startup در Production روی JWT پیش‌فرض/کوتاه، database غیر PostgreSQL و CORS غیر HTTPS fail-closed می‌شود.
- request ID، correlation ID و process time به پاسخ API افزوده شدند؛ log JSON و redaction کلیدهای token/password/OTP/secret قابل اتصال به collector است. سیاست جامع PII retention هنوز قبل از Production لازم است.
- عملیات رزرو، ledger و TripEvent با tenant scope، idempotency و uniqueness محافظت می‌شوند. ledger با reversal entry اصلاح می‌شود و تاریخچه mutation نمی‌شود.
- Headerهای `nosniff`، frame deny، referrer policy و permissions policy برای Frontend تعریف شده‌اند. CSP نهایی باید پس از تعیین دامنه‌های واقعی asset/API فعال شود.
- PostgreSQL RLS هنوز فعال نیست؛ مسیر پیشنهادی: policy جدا برای هر جدول دارای `tenant_id` با session variable امضاشده از connection middleware، سپس integration test مستقیم PostgreSQL.
- permission map برای نقش‌های Customer/Employee، Manager، Organization Admin، Agency/Partner، Supplier، BackOffice، Finance، Tenant Admin و Platform Admin fail-closed است. تست‌ها دسترسی بین tenantها، mutation مالی و deep link را پوشش می‌دهند؛ authorization سطح دیتابیس هنوز به RLS نیاز دارد.
- hashing رمز عبور با PBKDF2-HMAC-SHA256 و ۶۰۰هزار iteration آماده است؛ UI فعلی login مبتنی بر dev fixture است و در Production route آن 404 می‌شود.
- `npm audit --omit=dev` در ۱۴۰۵/۰۵/۲۷ صفر vulnerability گزارش کرد. اسکن SAST/DAST مستقل و penetration test هنوز انجام نشده است.

## سخت‌سازی Production — ۱۴۰۵/۰۵/۲۸

- migration `20260819_03` روی تمام جدول‌های دارای `tenant_id`، PostgreSQL RLS اجباری و policy fail-closed مبتنی بر `app.tenant_id` می‌سازد. context فقط از tenant claim توکن امضاشده وارد transaction می‌شود و بعد از commit نیز روی transaction بعدی همان session بازاعمال می‌شود.
- refresh token همچنان opaque و hash-only است؛ prefix عددی آن فقط hint انتخاب policy است و دستکاری آن بدون تطابق hash به `401` ختم می‌شود.
- API role نباید `BYPASSRLS` داشته باشد. outbox worker به role جدا و least-privilege نیاز دارد؛ provision این role مسئولیت DBA و blocker rollout است.
- Redis Lua counter برای rate limit توزیع‌شده اضافه شد. Production بدون `REDIS_URL` سالم fail-closed است و `/ready` خرابی آن را `503` گزارش می‌کند؛ token خام در Redis key ذخیره نمی‌شود.
- adapterهای sandbox فقط endpoint صریح HTTPS و secret-manager reference را می‌پذیرند و تا نصب transport مجاز همچنان `not_sent` برمی‌گردانند.
- اجرای مستقیم RLS روی PostgreSQL و Redis واقعی در این میزبان به‌علت نبود Docker/PostgreSQL/Redis ممکن نبود؛ این دو integration test پیش از rollout اجباری‌اند.

## نتیجه staging واقعی — ۱۴۰۵/۰۵/۲۸

- blocker قبلی PostgreSQL/Redis محلی با runtime ایزوله رفع و تست‌های واقعی پاس شدند؛ جملهٔ قبلی فقط تاریخچه وضعیت پیش از این اجرا است.
- API role بدون `BYPASSRLS` و worker role با دسترسی محدود outbox آزموده شدند. cross-tenant read/insert/update و نبود context در سطح DB fail-closed است.
- قطع Redis باعث health=200، readiness=503 و API=503 می‌شود؛ recovery بدون restart API نیز verify شد.
- CORS اکنون `Idempotency-Key` و correlation headerهای لازم را صریح می‌پذیرد؛ wildcard فعال نشده است.
- metrics فقط method/status-class و duration تجمعی را منتشر می‌کند و route/token/PII را label نمی‌کند.
- TLS تستی self-signed برای handshake staging کافی بود، اما Production به certificate معتبر CA، HSTS در reverse proxy و DNS نهایی نیاز دارد.

---

## فایل: PERFORMANCE_BASELINE.md

# Performance Baseline

Baseline محلی فقط برای regression و نه ظرفیت Production است. ابزار `deploy/load-smoke.py` فقط URL محلی را بدون flag اضافه می‌پذیرد، read-only است و p50/p95/max/error rate را گزارش می‌کند.

معیار اولیه API read path: ۵۰۰ درخواست، concurrency=20، خطای صفر و p95 کمتر از ۵۰۰ms روی localhost. ظرفیت واقعی فقط پس از load test شبکه، PostgreSQL/Redis target و provider sandbox تعیین می‌شود.

اجرای ۱۴۰۵/۰۵/۲۹ روی `GET /hotels` و SQLite ایزوله: `500 requests`, `0 errors`, `p50=54.47ms`, `p95=184.29ms`, `max=493.59ms`؛ gate محلی PASS شد.

Query review مسیرهای پرتکرار انجام و indexهای مرکب برای Offer search، reservation list، payment reconciliation و trip timeline افزوده شدند. queryهای list باید pagination محدود داشته باشند؛ endpointهای جدید یا aggregate هستند یا حداکثر ۴ Offer/۵۰ event می‌خوانند.

---

## فایل: docs/integrations/kavenegar-sms.md

# پیامک ورود (کاوه‌نگار) — عیب‌یابی روی سرور

**وضعیت:** کد آماده است؛ ارسال واقعی روی سرور هنوز تأیید نشده (`sms_notifications` = `READY_BLOCKED_EXTERNAL`).

## اسکریپت عیب‌یابی (فقط خواندنی)

`deploy/karenseir-diagnose-sms.sh` چیزی را تغییر نمی‌دهد، پیامک نمی‌فرستد و هیچ رازی را چاپ نمی‌کند.
فقط یک درخواست `account/info.json` به کاوه‌نگار می‌زند تا اعتبار و تاریخ انقضا را ببیند.

اجرا در کنسول ابرآروان (تا وقتی این شاخه در main ادغام و منتشر نشده):

```bash
cd /opt/karenseir && git -C app fetch -q origin fix/sms-kavenegar-diagnose \
  && git -C app show FETCH_HEAD:deploy/karenseir-diagnose-sms.sh > /tmp/diag-sms.sh \
  && bash /tmp/diag-sms.sh
```

بعد از انتشار: `cd /opt/karenseir && bash app/deploy/karenseir-diagnose-sms.sh`

`git fetch` فقط مرجع‌های git را به‌روز می‌کند و فایل‌های در حال اجرا را تغییر نمی‌دهد.

## خواندن خروجی

| بخش | چه باید دید | اگر نبود |
| --- | --- | --- |
| ۳ | `KARENSEIR_SMS_PROVIDER = 'kavenegar'`، نام الگو، و `selected OTP adapter: KavenegarSmsOtpProvider` | متغیرها به کانتینر api نمی‌رسند. فایل compose سرور باید `env_file: .env` یا این نام‌ها را زیر `environment:` داشته باشد. بعد از اصلاح، api دوباره ساخته شود. |
| ۴ | `return.status: 200` و اعتبار بیشتر از صفر | ۴۰۳ یعنی کلید اشتباه است. ۴۰۴ معمولاً یعنی کلید خالی یا آدرس اشتباه است، و همین خطای ثبت‌شده در ۲۷ سپتامبر است. ۴۰۷ یعنی فهرست IP مجاز در تنظیمات امنیتی پنل. ۴۱۸ یعنی اعتبار تمام شده. |
| ۵ | خطایی دیده نشود | `owner_only_test_account` (کد ۵۰۱) یعنی حساب یا الگوی تست فقط به شمارهٔ صاحب حساب پیامک می‌فرستد. `template_unavailable` (۴۲۴) یعنی الگو پیدا نشد یا تأیید نشده. `otp_throttled` محدودیت داخلی سایت است و ربطی به کاوه‌نگار ندارد. |

## اصلاحات کد (شاخهٔ `fix/sms-kavenegar-diagnose`)

- کدهای وضعیت کاوه‌نگار درست نگاشت شدند. ۴۱۴ و ۴۱۵ دیگر «محدودیت نرخ» حساب نمی‌شوند و تکرار نمی‌شوند. ۴۰۷، ۴۳۱، ۴۳۲، ۴۵۱ و ۵۰۱ هم نام دقیق دارند.
- در پاسخ خطای HTTP، کد داخل بدنهٔ JSON خوانده می‌شود.
- پیامی که کاوه‌نگار همان لحظه ناموفق یا مسدود اعلام کند (وضعیت ۶، ۱۱، ۱۳، ۱۴ یا ۱۰۰) دیگر «ارسال‌شده» ثبت نمی‌شود.
- خطاهای مربوط به یک درخواست، مثل شمارهٔ نامعتبر یا حساب تست، دیگر circuit breaker مشترک tenant را باز نمی‌کنند. پیش از این، پنج خطای این‌چنینی در یک دقیقه ورود پیامکی را برای همهٔ کاربران قطع می‌کرد.
- علامت‌های نامرئی جهت‌نما و نیم‌فاصله در شمارهٔ موبایل حذف می‌شوند.
- کد شش‌رقمی با ارقام فارسی هم در `/auth/otp/verify` پذیرفته می‌شود.

## گام‌های بیرونی باقی‌مانده

۱. اجرای اسکریپت روی سرور و ثبت خروجی (بدون راز).
۲. الگوی تأییدشدهٔ تولید (مثلاً `karenotp`) با `%token` در پنل کاوه‌نگار. الگوی `karentest` فقط به شمارهٔ صاحب حساب می‌رسد.
۳. یک درخواست کد ورود با شماره‌ای که صاحبش اجازه داده، و دیدن رسیدن پیامک. فقط پس از این مرحله وضعیت ثبت به LIVE تغییر می‌کند.

---

## فایل: docs/integrations/vandapay.md

# اتصال ونداپی («پرداخت با ونداپی») — KarenSeir

> وضعیت: ساخته و آزمون‌شده با MOCK؛ **خاموش** (D15). پرداخت واقعی فقط پس از قرارداد PSP و نظر حقوقی. تصمیم معماری: [ADR-024](../adr/ADR-024-vandapay-payment-gateway.md) + [ADR-029](../adr/ADR-029-federated-org-credit-and-vandapay-hardening.md) (پیاده‌سازی واحد) + [ADR-021](../adr/ADR-021-vandapay-payment-provider.md).

## نوع اتصال
API سمت سرور (redirect به صفحهٔ پرداخت میزبانی‌شدهٔ ونداپی). وقتی `VANDAPAY_MODE` روشن و کامل باشد، ونداپی درگاه `POST /payments/{id}/initiate` است (ADR-024)؛ `PAYMENT_PROVIDER=sandbox` در QA/staging مقدم است.

## جریان
1. Checkout تا مرحلهٔ `awaiting_payment` ← Payment Intent با مبلغ backend.
2. صفحهٔ Checkout از `GET /payments/methods` می‌پرسد؛ فقط وقتی ونداپی روشن باشد دکمهٔ «پرداخت با ونداپی» (و در کلید آزمایشی، برچسب «حالت آزمایشی») دیده می‌شود.
3. `POST /payments/{id}/initiate` ← `POST /payment_intents` ونداپی با `Idempotency-Key` قطعی ← هدایت به `checkout_url`.
4. بازگشت: `GET /payments/vandapay/return?state=…` ← بازخوانی intent از API ← «پرداخت شد» / «ناموفق» / «در حال بررسی».
5. وب‌هوک: `POST /payments/vandapay/webhook` (سرآیند `VandaPay-Signature`) — منبع نهایی حقیقت.

## پیکربندی (فقط env؛ هرگز در کد یا git)
| متغیر | توضیح |
| --- | --- |
| `VANDAPAY_MODE` | `disabled` (پیش‌فرض) / `test` / `live`؛ باید با پیشوند کلید بخواند |
| `VANDAPAY_BASE_URL` | آدرس https سرور ونداپی (مثلاً `https://<دامنهٔ ونداپی>/api/v1`)؛ الزامی |
| `VANDAPAY_SECRET_KEY` | `sk_test_…` یا `sk_live_…` (یا `VANDAPAY_SECRET_KEY_FILE`) |
| `VANDAPAY_WEBHOOK_SECRET` | رمز امضای وب‌هوک از پنل پذیرنده (یا `*_FILE`) |
| `VANDAPAY_INTENT_EXPIRES_IN_SECONDS` | اختیاری (VP-01)؛ خالی = TTL پیش‌فرض ونداپی |
| `VANDAPAY_FEDERATED_CREDIT_ORGANIZATION_IDS` | اختیاری؛ سازمان‌هایی که اعتبارشان در دفتر ونداپی است (ADR-029) |
| `VANDAPAY_RETURN_URL` | آدرس https عمومی `/payments/vandapay/return` |

آدرس وب‌هوک برای ثبت در پنل پذیرندهٔ ونداپی: `https://<api-domain>/payments/vandapay/webhook`.

## آزمون
`cd backend && pytest tests/test_vandapay.py tests/test_vandapay_hardening.py` — ۳۱ آزمون با MOCK (پیکربندی fail-closed، بردارهای امضا، یک route بازگشت و یک وب‌هوک، idempotency، استرداد، لغو intent، late capture، تأیید سازمان، اعتبار فدرال). استرداد مالی: `POST /refunds/{id}/review` سپس `POST /refunds/{id}/execute`.

## باقی‌مانده (پیش از روشن کردن)
- قرارداد PSP و نظر حقوقی (D15)؛ استقرار سرور/دامنهٔ ونداپی؛ پذیرش KarenSeir/تاژبان به‌عنوان پذیرنده و کلید `sk_test_`.
- آزمون سرتاسری با sandbox واقعی ونداپی (استرداد/لغو/تأیید سازمان فقط با MOCK آزموده شده‌اند — ADR-022).
- ادغام VP-01 (`expires_in_seconds`) در ونداپی؛ تا آن زمان `VANDAPAY_INTENT_EXPIRES_IN_SECONDS` را خالی بگذارید.
- K8 (`reverse_capture` اعتبار داخلی در استرداد پس از صدور)؛ منبع موبایل تأییدشده برای `customer_phone`.
- تصمیم مالک دربارهٔ redirect به صفحهٔ ونداپی یا پرداخت جاسازی‌شده (`docs/integration-plans/karenseir.md` در مخزن ونداپی).
