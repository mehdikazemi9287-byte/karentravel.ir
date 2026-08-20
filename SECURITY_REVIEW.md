# بازبینی امنیت و صحت مالی — پایلوت

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
