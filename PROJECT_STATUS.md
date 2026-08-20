# وضعیت اجرایی پایلوت

## Ecosystem saved travel increment — ۱۴۰۵/۰۵/۲۹

- migration افزایشی `20260820_11` دامنه‌های tenant-aware سفر ذخیره‌شده/علاقه‌مندی/سبد سفر، Review و پاسخ مستقل تأمین‌کننده، کاتالوگ مقصد و itinerary قابل‌ویرایش را اضافه می‌کند. هفت جدول تازه policy استاندارد RLS و FORCE RLS دارند؛ destructive change وجود ندارد.
- APIهای مالکیت کاربر، idempotency و audit/outbox برای ساخت/انتقال/حذف آیتم، چند سفر ذخیره‌شده، review با verified flag مشتق‌شده فقط از رزرو issued/completed، moderation نقش‌محور، پاسخ تأمین‌کننده، hierarchy مقصد و create/add/update/remove/duplicate itinerary تکمیل شد.
- Comparison به schemaهای vertical و شش award قطعی با `deterministic-v1` و event قابل audit توسعه یافت. routeهای مستقل `/saved-trips`، `/itineraries`، `/destinations/[slug]` و `/map` به API واقعی وصل شدند؛ map بدون credential فقط fallback صادقانه فهرست/مختصات است.
- Homepage، CSS، asset و layout تأییدشده تغییر نکرد. visual structural regression دسکتاپ و موبایل در Playwright PASS است.
- QA: backend `73 passed, 5 skipped`؛ lint/typecheck/build برای ۲۶ route PASS؛ E2E `14/14` PASS؛ Alembic upgrade/current/check روی DB ایزوله تا head 11 PASS؛ npm audit صفر و `git diff --check` PASS.
- PostgreSQL runtime/Docker در این میزبان موجود نیست؛ بنابراین اجرای مستقیم migration 11 و RLS/FORCE RLS هفت جدول تازه روی PostgreSQL واقعی **BLOCKED_INTERNAL_ENVIRONMENT** است و phaseهای 7/8 تا اجرای این gate نهایی تلقی نمی‌شوند. evidence قبلی head 10 و 56/56 حفظ شده است.
- ZarinPal adapter اختصاصی، unified checkout، review UI/moderation، SEO/CWV/RTL matrix و security regression مستقیم PostgreSQL برای head 11 کار داخلی باقی‌مانده‌اند. Production همچنان **NO-GO** است.

## Ecosystem Search 2.0 + Product Audit — ۱۴۰۵/۰۵/۲۹

- audit صفحه‌به‌صفحه و phase gate در `PRODUCT_ECOSYSTEM_AUDIT.md` ثبت شد؛ دامنه گسترده جدید completion اکوسیستم را `76%` نشان می‌دهد و عدد 97% قبلی فقط مربوط به hardening scope است.
- Search contract موجود بدون schema/migration موازی به ۱۴ vertical توسعه یافت: normalization فارسی/عربی و نیم‌فاصله، autocomplete tenant-safe، recent search، flexible-date intent، فیلتر قیمت/review/cancellation/amenity/instant، map bounds و sort.
- هر result اکنون provider، observation/availability/price timestamp، TTL، freshness، مالیات/کارمزد/قیمت نهایی، inventory state، policy verification، review/quality/location و ranking explanation data دارد. stale به‌طور پیش‌فرض حذف و در inspection صریح `available=false` برمی‌گردد.
- Homepage و تمام فایل‌های UI/CSS/تصویر مرجع بدون تغییر باقی ماندند. Playwright ساختار frozen Homepage را در 1440×1000 و 390×844 همراه screenshot render، RTL، Header/Hero/Search/AI/Comparison/Footer کنترل کرد.
- QA: backend `70 passed, 5 skipped` در محیط credential-independent؛ focused Search/booking `13/13`؛ lint/typecheck/build 22 route؛ E2E `13/13`؛ compile و npm audit صفر PASS.
- ZarinPal TEST همچنان `BLOCKED BY CREDENTIAL` است و transport/callback موفقیت جعلی نشده است. جزئیات phaseهای PARTIAL/MISSING در audit ثبت شده‌اند.

## Production-readiness closure — ۱۴۰۵/۰۵/۲۹

- PostgreSQL 16.15 و Redis 7.4.10 کاملاً ایزوله اجرا شدند؛ migration `20260820_10` پس از backup اعمال و Alembic head/check بدون drift تأیید شد. هیچ Production target یا داده‌ای لمس نشد.
- تمام ۵۶ جدول tenant-aware دارای RLS و FORCE RLS هستند. آزمون مستقیم own tenant، cross-tenant read/write و نبود `app.tenant_id` PASS شد؛ API با NOBYPASSRLS و worker با least privilege نیز دوباره اثبات شدند.
- backup پیش از migration، restore جداگانه، downgrade 10→09، upgrade 09→10 و restore تا head 10 PASS شدند. integrity نهایی شامل ۱۳۷ foreign key، صفر constraint تأییدنشده و ۲۴۰ index معتبر/ready است.
- نقص واقعی grant جدول‌های بازسازی‌شده در rollback با default privileges نقش API اصلاح و در چرخه دوم rollback/upgrade اثبات شد. checksum scripts اکنون روی Linux و macOS fail-closed کار می‌کند.
- مالیات صورتحساب backend-configurable شد و در Production بدون نرخ و مرجع policy مصوب `503` می‌دهد؛ هیچ نرخ حقوقی/مالیاتی جعل نشده است.
- QA نهایی: backend واقعی `70/70`، domain PostgreSQL `5/5`، Chromium `12/12`، lint/typecheck/build، compile، npm audit صفر، health/readiness/metrics و validation manifestها PASS است.
- Completion واقعی `97%` است. Production به‌دلیل DNS/TLS عمومی، Secret Manager، monitoring خارجی، credentialهای قراردادی، target deployment/image digest، policy قانونی صورتحساب و certification مستقل همچنان **NO-GO** است.

## Final internal domain phase — ۱۴۰۵/۰۵/۲۹

- migration افزایشی `20260820_10` چهار جدول `invoices`، `support_cases`، `support_thread_messages` و `installment_agreements` را با tenant key، PostgreSQL RLS و `FORCE RLS` اضافه می‌کند؛ downgrade فقط همین چهار جدول را برمی‌گرداند و هیچ migration مخربی وجود ندارد.
- صورتحساب backend-derived و idempotent، پرونده/رشته پشتیبانی با منبع صریح `customer`/`human_agent`، اجرای اقساط سازمانی، settlement posting در وضعیت `pending` و workflow تغییر نقش tenant-scoped تکمیل شد.
- UI موجود بدون redesign به invoice read/issue، support thread انسانی، installment decision، settlement posting و Admin role management متصل شد؛ موفقیت انتقال وجه یا provider بیرونی ادعا نمی‌شود.
- QA این pass: backend `64 passed, 5 skipped`، Chromium E2E `12/12`، ESLint، TypeScript strict، build ۲۲ route، Python compile، Alembic upgrade/head/check و `git diff --check` همگی PASS هستند.
- RLS metadata اکنون ۵۶ جدول tenant-scoped دارد. اجرای مستقیم PostgreSQL برای چهار جدول تازه در این pass به target دست نزد؛ policy SQL و تست‌های API cross-tenant سبزند و staging target باید migration/restore drill کنترل‌شده را پیش از rollout تکرار کند.
- Completion داخلی `94%` و وضعیت Production همچنان **NO-GO** است؛ فقط اتصال‌ها و certification بیرونی و validation migration روی PostgreSQL target باقی مانده‌اند.

## Final autonomous checkpoint — ۱۴۰۵/۰۵/۲۹

- فاز Customer/Panel mutation تکمیل شد: `/account` به profile، owned travellers، personal wallet ledger، payment intents/initiation fail-closed، installment eligibility و notification preferences متصل است.
- Supplier onboarding/inventory status، Agency creation/markup، BackOffice supplier status و Finance reconciliation UI با RBAC/tenant scope واقعی متصل شدند. پیام پشتیبانی مشتری فقط برای reservation/trip متعلق به همان حساب ثبت می‌شود.
- schema و migration تغییر نکرد؛ UI تأییدشده redesign نشد. backend برابر `60 passed, 5 skipped`، E2E برابر `10/10` و lint/typecheck/build ۲۱ route PASS است.
- invoice domain، support case thread کامل، installment execution و settlement posting همچنان توسعه داخلی بعدی‌اند؛ Production به‌علت blockerهای بیرونی و certification همچنان **NO-GO** است.

- authenticated client اکنون در root session مشترک است و routeهای `/trips`، Trip Timeline واقعی، `/manage-booking`، `/compare`، `/organization`، `/supplier`، `/agency` و `/backoffice` را بدون redesign به API tenant-scoped متصل می‌کند.
- read modelهای رزرو، سفر، اعلان و سازمان، onboarding idempotent تأمین‌کننده و تست‌های RBAC/cross-tenant افزوده شدند؛ schema یا migration تغییر نکرد.
- QA این pass: backend `57 passed, 5 skipped`، ESLint، TypeScript strict، build ۱۹ route و Chromium E2E `8/8` PASS است.
- Production همچنان **NO-GO** است؛ credential خارجی و certification هدف موجود نیست و پنل‌های mutation-heavy/customer account هنوز کار داخلی بعدی‌اند.

- ممیزی مجدد repository، اسناد، migrations، امنیت، providerها، frontend و QA انجام شد؛ پیش از این pass پوشه `.git` وجود نداشت.
- reconciliation مالی tenant-scoped و read-only برای payment/refund/settlement/wallet افزوده و با RBAC و cross-tenant test پوشش داده شد.
- client مشترک frontend برای OTP واقعی، refresh rotation، logout، correlation ID و request idempotency افزوده شد؛ صفحه `/pilot` بدون redesign به OTP Production fail-closed و dev-login صریح متصل شد.
- QA نهایی این pass: backend `55 passed, 5 skipped`، ESLint، TypeScript، build ۱۶ route، Python compile، Alembic head/check، npm audit صفر و Chromium E2E `3/3` همگی PASS شدند.
- وضعیت عمومی همچنان **NO-GO** است؛ جزئیات دقیق در `FINAL_PROJECT_AUDIT.md`، `PRODUCTION_READINESS.md`، `EXTERNAL_BLOCKERS.md` و `TEST_EVIDENCE.md` ثبت شد.

## Orchestration completion pass — ۱۴۰۵/۰۵/۲۹

- Offer → Price Check → Booking → Payment Gate → Supplier/Provider Confirmation → Voucher برای Flight، Hotel، Tour و Package پیاده شد؛ snapshot، expiry، inventory lock، idempotency، history و outbox دارد.
- Manage Booking به policy معتبر، cancel/change/refund state، partial refund record و voucher reissue نسخه‌دار متصل شد. بدون policy معتبر هیچ مبلغ refund نمایش داده نمی‌شود.
- Approval template چندمرحله‌ای، Department، Cost Center، SLA، escalation، role-bound decision و rejection reason پیاده شد.
- White Label persistent، Agency hierarchy/markup/commission، Supplier/Agency/BackOffice API، Comparison explainable و AI grounded context اضافه شدند.
- Notification preference قبل از ساخت attempt اعمال می‌شود؛ delivery receipt امضاشده و queue/dead-letter metrics worker اضافه شد.
- Provider wrapper شامل Redis throttling tenant/provider، retry، timeout ceiling، circuit breaker و failure isolation است؛ disabled provider همچنان fail-closed است.
- PostgreSQL/Redis/worker suite برابر `59 passed`، RLS/FORCE RLS برابر `52/52` و Alembic head برابر `20260820_09` شد.
- backup/restore جدید PASS: checksum=`4955a47c6357e6d540f2bd1969cfc82e7e3ef7ca0a0af7e2e54badef05c0cef5` و source/restore هر دو head 09، RLS 52/52 و users=10.
- load baseline محلی ۵۰۰ request با error=0 و p95=184.29ms PASS شد. CSP، build، E2E و audit نیز PASS شدند.
- UI مرجع redesign نشد. صفحه‌های نمایشی قدیمی هنوز برای داده واقعی به session/API client مشترک نیاز دارند و به‌عنوان Mock برچسب‌دار باقی مانده‌اند.

## Completion pass — Identity، Payment، CI/CD و Recovery — ۱۴۰۵/۰۵/۲۸

- snapshot منبع پیش از تغییر با SHA-256 برابر `32106145dbd17446c3928c6e94953a519e417611b1f34b3c4740c1ff02f4b4c1` در مسیر موقت ساخته شد؛ UI و دیتابیس repository تغییر نکردند.
- OTP challenge یک‌بارمصرف hash-only، expiry، replay protection، پنج تلاش، lockout، audit، tenant context، device/IP hash و provider fail-closed اضافه شد. access JWT اکنون issuer/audience/iat/jti اجباری دارد؛ refresh family، reuse detection، rotation و logout پیاده شد.
- Payment Intent از snapshot معتبر backend، initiation adapter، callback raw-body HMAC، duplicate event protection، state machine، partial refund limit، refund outbox و cross-tenant/IDOR tests اضافه شدند.
- migrationهای افزایشی `20260819_04` و `20260819_05` روی PostgreSQL staging backup‌شده اجرا شدند. تمام ۴۲ جدول tenant-scoped دارای RLS و FORCE RLS هستند.
- backup/restore تازه پاس شد: checksum `bc7af4c0f19235615056f9001363840cbc809ad0245c29eb4908ae8839424b2c`، source/restore هر دو head=`20260819_05`، tenant tables/RLS=`42/42` و users=`10`.
- backend واقعی PostgreSQL+Redis+worker برابر `42 passed`، Playwright برابر `3 passed`، ESLint/TypeScript/build/compile/Alembic پاس شدند. release pointer v1→v2→v1 واقعاً verify شد.
- CI/CD، API least-privilege role، پنج runbook اجباری، metrics عملیاتی و Nginx TLS/security-header/gzip template اضافه شدند.
- npm audit یک advisory سطح High در Playwright قدیمی یافت؛ Playwright به `1.55.1` ارتقا یافت، audit نهایی `0 vulnerabilities` و E2E پس از ارتقا `3 passed` شد.
- credential واقعی، target deployment و certification بیرونی موجود نیست؛ Production همچنان **NO-GO** است.

## Phase A — Production Infrastructure Hardening — ۱۴۰۵/۰۵/۲۸

- قرارداد ADR-005 برای secret-file، provider mock، observability و rollback ثبت و بدون migration/schema/data/UI اجرا شد.
- `DATABASE_URL`، `JWT_SECRET` و `REDIS_URL` از secret file خصوصی پشتیبانی می‌کنند؛ conflict، symlink، permission ناامن و فایل خالی fail-closed است. Compose override برای external secrets و credential جداگانه worker اضافه شد.
- mock provider در Production بدون `DEMO_MODE=true` رد می‌شود؛ disabled/sandbox همچنان موفقیت خارجی جعل نمی‌کنند.
- Prometheus scrape/alert rules و public DNS/TLS/readiness/metrics validator افزوده شد. validator ورودی local/placeholder را رد می‌کند و curl certificate validation را دور نمی‌زند.
- QA این pass: backend credential-independent برابر `32 passed, 5 skipped`، compile، ESLint، TypeScript strict، Next production build با ۱۶ صفحه، Playwright برابر `3 passed`، YAML و shell syntax پاس شدند. پنج skip مربوط به integrationهای واقعی PostgreSQL/Redis/worker هستند که evidence staging قبلی آن‌ها در بخش بعدی ثبت شده است.
- Phase A روی target کامل نیست: Public DNS، CA certificate عمومی، external secret-manager/rotation evidence، collector/Alertmanager واقعی و deployment target همچنان blocker هستند؛ وضعیت Production **NO-GO** باقی ماند.

## Staging واقعی و QA زیرساخت — ۱۴۰۵/۰۵/۲۸

- PostgreSQL 16.15، Redis 7.4.10 و API Production-mode/TLS روی localhost و دیتابیس‌های ایزوله اجرا شدند؛ دیتابیس فعلی repository migrate نشد.
- RLS واقعی شامل no-context، own-tenant، cross-tenant read/insert/update و policy coverage تمام ۳۶ جدول tenant-scoped برابر `3 passed` شد.
- Redis integration واقعی و نقش worker همراه contract testها مجموعاً `9 passed` شدند. قطع Redis: health=200، ready=503، API=503؛ recovery: ready=200.
- worker واقعی با role مستقل event را بدون ادعای delivery به retry برد. نقص metadata مستقل worker شناسایی و اصلاح شد.
- backup/restore واقعی پاس شد: checksum معتبر، restore head=`20260819_03`، source/restore users=10 و RLS policies=36.
- Google Chrome سیستم برای Playwright استفاده شد و هر سه suite ورود/جست‌وجو/رزرو، approval/dashboard و cancellation/refund پاس شدند. نقص CORS هدر idempotency و selectorهای مبهم تست اصلاح شدند.
- TLS موقت self-signed با SAN و handshake TLS 1.2 پاس شد؛ preflight secrets و metrics Prometheus نیز پاس شدند. certificate عمومی معتبر، secret manager و collector واقعی هنوز blocker Production هستند.
- test harness قدیمی به DB تست صریح قفل شد تا QA دیگر دیتابیس پیش‌فرض backend را drop/create نکند.

## Production hardening pass — ۱۴۰۵/۰۵/۲۸

- PostgreSQL RLS migration افزایشی `20260819_03`، tenant transaction context، refresh-token tenant hint امن و تست مثبت/منفی مستقیم PostgreSQL اضافه شدند. تست مستقیم با `TEST_POSTGRES_URL` ایزوله اجرا می‌شود و در این میزبان به‌علت نبود PostgreSQL skip شد؛ دیتابیس موجود mutate نشد.
- rate limiting توزیع‌شده Redis با Lua اتمیک، fingerprint هش‌شده، `429/Retry-After`، readiness و startup fail-closed اضافه شد. unit/contract tests سبزند؛ integration با Redis واقعی به‌علت نبود runtime محلی blocked است.
- Provider/OTP/Payment حالت‌های disabled/mock/sandbox دارند. sandbox فقط HTTPS و secret-manager reference معتبر را می‌پذیرد و بدون transport مجاز موفقیت جعل نمی‌کند.
- Playwright suite برای login/search/booking، approval/dashboard و cancellation/refund اضافه شد. جریان API approval/dashboard واقعاً پاس شد؛ دو جریان browser به‌علت نبود executable Chromium و نبود browser instance اجرا نشدند.
- preflight secrets، backup با checksum، restore verification فقط روی DB ایزوله، rollback RLS و نقش جداگانه outbox worker مستند/اسکریپت شدند.
- QA: lint، TypeScript، Next build با ۱۶ route، Python compile، `27 passed` backend، Alembic upgrade/check تا head و یک E2E API پاس شدند. یک تست PostgreSQL skip و دو E2E browser blocked هستند؛ بنابراین وضعیت rollout Production فعلاً **NO-GO** است.

## سخت‌سازی رزرو دستی — ۱۴۰۵/۰۵/۲۸

- ممیزی کامل snapshot حاضر انجام شد. پوشهٔ `.git` در workspace موجود نیست؛ بنابراین `git status` قابل اجرا نبود و هیچ ادعایی درباره clean/dirty بودن درخت نمی‌شود. همهٔ فایل‌های موجود حفظ شدند.
- مسیر قدیمی `POST /bookings` اکنون `Idempotency-Key` اجباری، tenant-scoped replay، تشخیص payload متفاوت و row lock موجودی در PostgreSQL دارد. retry همسان رزرو، ledger، audit یا کاهش موجودی تازه ایجاد نمی‌کند.
- صفحه `/pilot` برای هر فرمان رزرو کلید idempotency می‌فرستد. Provider، پرداخت، OTP و اعلان خارجی همچنان fail-closed هستند.
- پذیرش و rollback در `ADR-002` و `ACCEPTANCE_CRITERIA.md` ثبت شده‌اند؛ migration یا جدول تازه‌ای اضافه نشده است.
- QA نهایی: lint موفق؛ TypeScript موفق؛ build رسمی Next.js/Webpack با ۱۶ route موفق؛ backend برابر `23 passed in 0.85s`؛ compile موفق؛ upgrade دیتابیس خالی تا `20260818_02 (head)` و `alembic check` بدون operation تازه موفق.
- دیتابیس محلی موجود هنگام audit در Alembic head نبود و عمداً mutate نشد. PostgreSQL RLS، اتصال‌های بیرونی، rate limiting توزیع‌شده، browser E2E و rollout سرور همچنان کار Production بعدی/وابسته به زیرساخت‌اند.

## ممیزی نهایی عملیاتی — ۱۴۰۵/۰۵/۲۷ (تکمیل credential-independent)

- دامنه این اجرا: QA واقعی Homepage روی پورت ۳۰۰۱، تکمیل شکاف‌های Phase 2 و Phase 3 که به credential خارجی نیاز ندارند، و ثبت شواهد تست/مهاجرت/استقرار.
- پذیرش: نوار بنفش تمام‌عرض وجود نداشته باشد، AI فقط کارت فشرده باشد، نوار کورال خالی حفظ شود، چهار تب Search مصوب باقی بمانند، و lint/typecheck/build/backend/migration/smoke با نتیجه واقعی ثبت شوند.
- rollback: تغییرات این اجرا افزایشی و محدود به اسناد، CSS/کامپوننت‌های مرتبط، مدل‌ها/migrationهای جدید و زیرساخت fail-closed است؛ هیچ داده، migration یا اتصال خارجی حذف یا فعال نمی‌شود.
- QA ایستا Homepage: wrapper بخش AI شفاف و داخل `ref-container` است؛ Grid دسکتاپ ۳۸/۶۲، background بنفش فقط روی کارت `.smart-portrait`، `ServiceRibbon` بدون آیتم داخلی، و چهار تب دقیق «پرواز»، «هتل»، «تور + هتل»، «تشریفات فرودگاه» هستند. همه این متن‌ها در HTML رندرشده روی ۳۰۰۱ حضور دارند. screenshotهای ۱۴۴۰/۷۶۸/۳۹۰ به‌علت نبود browser قابل‌کنترل (`[]`) pending هستند و QA تصویری ادعا نمی‌شود.
- Phase 2: Agency/Profile/RolePermission/RefreshTokenSession/NotificationPreference و abstractionهای installment/pricing/settlement افزوده شدند. access token نوع‌دار ۱۵ دقیقه‌ای، refresh token opaque با hash/rotation/revocation، permission guard fail-closed و password hashing قابل‌حمل PBKDF2-HMAC پیاده شد.
- Finance: فرمان‌های allocate/reserve/capture/release/reverse_capture با tenant scope، row lock، کنترل مانده، unique idempotency و ledger append-only اضافه شدند. Approval endpoint نیز tenant-scoped و permission-based است.
- Trip Operations: TripEvent قابل‌نمایش یک Notification و delivery attemptهای in-app/push/sms می‌سازد؛ Outbox correlation/idempotency، retry backoff، dead-letter timestamp و همگام‌سازی وضعیت attempt را دارد. منبع `system_provider`، `ai` و `human_support` در مدل جدا می‌ماند.
- Phase 3: log ساختاریافته JSON با redaction، request/correlation/process-time headers، exception normalization، graceful engine disposal، health/readiness، adapter contract شامل timeout/retry/structured error/health، migration-on-container-start، reverse-proxy TLS template و production config validation تکمیل شد.
- شواهد نهایی: `npm run lint` موفق؛ `npx tsc --noEmit` موفق؛ `npm run build` با Webpack رسمی Next.js موفق و ۱۶ route تولید شد؛ `npm audit --omit=dev` برابر ۰ vulnerability؛ backend برابر `21 passed in 0.74s` در اجرای نهایی؛ compile موفق؛ Alembic clean upgrade تا `20260818_02 (head)` و `alembic check` بدون operation جدید؛ API smoke برابر health=ok، ready=ready، احراز هویت/refresh موفق و dashboard=200؛ route smoke رابط کاربری روی پورت ۳۰۰۱ برای همه مسیرهای اصلی 200 و مسیرهای نامعتبر 404.
- بسته انتقال آماده شد: `dist/karenseir-phase2-phase3-20260818.tar.gz` (بدون `.env`، `.venv`، `node_modules`، `.next` یا دیتابیس) و checksum در فایل `.sha256` کنار آن. انتشار روی سرور انجام نشده است.
- Route QA روی ۳۰۰۱: `/`, `/trips`, `/trips/mock-shiraz-1405`, `/nearby`, `/services`, `/manage-booking/book1`, `/manage-booking/book2`, `/support`, `/assistant`, `/booking/confirmation`, `/compare`, `/organization` همگی ۲۰۰؛ شناسه‌های نامعتبر manage-booking/trips هر دو ۴۰۴. dev server روی ۳۰۰۱ روشن باقی مانده است.
- Docker روی میزبان نصب نیست؛ build/healthcheck Docker اجراشده تلقی نمی‌شود. اتصال واقعی Provider/Payment/OTP/SMS/Push، production secrets، PostgreSQL RLS فعال، certificate TLS و monitoring collector همچنان externally blocked هستند.

## تلاش انتقال به سرور مجاز — ۱۴۰۵/۰۵/۲۷

- checksum بسته محلی با مقدار مورد انتظار یکسان است: `42e5f833bdbcc6c7b31befc52e72892c09d004c7ca83a98fb72880dc86810146`.
- archive audit محلی انجام شد؛ `.env`، کلید خصوصی، virtualenv، cache، database و `node_modules` داخل بسته نیستند.
- اتصال read-only به `ubuntu@95.38.184.209` با کلید موجود محلی و `BatchMode` با خطای `Permission denied (publickey,password)` رد شد؛ بنابراین disk/service/migration state سرور، backup source/database، upload، migration و restart انجام نشده‌اند.
- deployment عمداً انجام‌نشده و هیچ فایلی روی سرور تغییر نکرده است. برای ادامه فقط باید دسترسی SSH مجاز به همین کاربر/سرور در محیط اجرا فراهم شود؛ نیازی به ارسال secret در گفتگو نیست.

## اجرای سه‌فازی — ۱۴۰۵/۰۵/۲۶

### Phase 1 — Homepage lock

- عامل واقعی نوار بنفش تمام‌عرض (`SupportDock` ثابت در ریشه Home) از Homepage حذف شد؛ Dock مسیرهای عملیاتی حفظ شده است.
- AI در کانتینر مرکزی RTL با ستون ۳۸/۶۲ قرار دارد؛ بنفش فقط کارت گرد AI است و گروه مقابل سفید است. Tablet/Mobile stack می‌شوند.
- Search به چهار ورودی اصلی «پرواز»، «هتل»، «تور + هتل» و «تشریفات فرودگاه» محدود شد؛ معماری مدل‌های آینده در domain/provider باقی است.
- نوار کورال خالی با ارتفاع ثابت حفظ و تمام icon/text/linkهای قبلی آن حذف شد.
- Figma frame موجود قبلاً بخش AI responsive را دریافت کرده است؛ sync دقیق تغییر Search/strip این اجرا انجام نشد چون visual browser QA و Node استاندارد در محیط حاضر موجود نبود.

### Phase 2 — Operational foundation

- schema افزایشی SQLAlchemy برای سازمان/عضویت/تأمین‌کننده/قرارداد، catalog/search، Reservation/Item/Traveller/Ticket/Voucher، after-sales، Wallet/Credit/Ledger/Approval، Trip/TripEvent، Notification/Delivery، Support/AI reference، Idempotency و Outbox اضافه شد.
- state transition، idempotent command، append-only reversal ledger و deduplicated TripEvent با outbox پیاده و تست شدند.
- APIهای tenant-scoped رزرو، command، درخواست after-sales و Trip Timeline اضافه شدند. adapterهای خارجی fail-closed باقی‌اند.

### Phase 3 — Production preparation

- production config validation، request ID، health/readiness، outbox worker، retry/dead-letter، Frontend security headers/error boundary، Docker multi-stage و healthcheckها اضافه شدند.
- Alembic baseline و migration افزایشی `20260818_02` روی دیتابیس خالی و مسیر ارتقا اجرا و با `alembic check` تأیید شدند.
- Node/npm از NVM فعال و production build موفق است. browser control و Docker همچنان در این میزبان موجود نیستند؛ screenshot و Docker healthcheck اجراشده تلقی نمی‌شوند.

## آنچه اکنون وجود دارد

- Homepage کامل RTL و responsive با زبان بصری کرم/بنفش/کورال، Hero معماری یزد، موتور جست‌وجوی چهارخدمتی مصوب، collage مقصدها، سفرهای منتخب، همراه هوشمند، مقایسه، تجربه مقصد، خدمات سازمانی، اعتماد، اکوسیستم و Footer منحنی.
- Next.js 16.3.1، ESLint 9 با flat config، PostCSS 8.5.23 و فونت محلی Vazirmatn؛ audit dependencyهای Production بدون vulnerability شناخته‌شده است.
- جست‌وجوی صفحه اصلی برای هر خدمت فرم متفاوت دارد و حالت‌های loading، success، empty و fail-closed error را پوشش می‌دهد. ورودی زبان طبیعی آماده توسعه است اما اتصال AI یا قیمت زنده را جعل نمی‌کند.
- فرانت‌اند Next.js RTL با هشت صفحه معرفی/عملیاتی و یک صفحه اتصال واقعی API در `/pilot`.
- API FastAPI با جست‌وجوی هتل دستی، JWT، نقش کارمند/مدیر رفاه، tenant scope، جریان درخواست و تأیید، ledger authorization و audit event.
- seed کنترل‌شده برای دو سازمان مستقل («بانک آفتاب» و «صنایع فراز») و سه هتل دستی.
- Dockerfile API، Docker Compose، نمونه متغیر محیطی و runbook استقرار.

## مرزهای فعال و غیرفعال

پرداخت، OTP، Providerهای بیرونی، مالیات، تسویه، RLS PostgreSQL، API partner، Assistant ابزارمحور و گزارش‌های Production هنوز فعال نیستند؛ نبود credential یا contract در UI/API به‌عنوان اتصال واقعی نمایش داده نمی‌شود. توسعه‌گاه `/auth/dev-login` در production غیرفعال است.

## بدهی مهم پیش از Production

اجرای migration نسخه‌ای (Alembic)، PostgreSQL RLS واقعی، refresh-token/OTP provider، secrets manager، idempotency/outbox، payment/settlement قانونی، tax engine، rate limiting، monitoring، backup/restore drill و تست‌های browser E2E لازم‌اند. این موارد به‌دلیل نبود قرارداد/credential/سیاست مالی یا زیرساخت تولید، تکمیل‌شده تلقی نمی‌شوند.

## لایه Trip Context — ۱۴۰۵/۰۵/۲۶

- مدل‌های TypeScript برای Trip، TripSegment، Booking، Voucher، ItineraryItem، Service، Merchant، NearbyPlace، Wallet، Credit، Benefit و Notification اضافه شدند؛ Trip context مرکزی اتصال رزرو به تجربه پس از خرید است.
- مسیرهای `/trips` و `/trips/mock-shiraz-1405` مرکز سفر و timeline قبل/حین/بعد را پیاده می‌کنند. queryهای `?stage=before|during|after` فقط preview هستند و authority وضعیت واقعی نیستند.
- `/booking/confirmation` پیام «رزرو شما با موفقیت ثبت شد»، واچر و انتخاب اختیاری «ورود به سفر من» را ارائه می‌دهد؛ redirect تبلیغاتی خودکار وجود ندارد.
- سفر Mock تهران–شیراز شامل دو مسافر، segment پرواز، دو booking، یک voucher و اقامت در انتظار انتخاب است. همه شناسه‌ها و وضعیت‌ها نمایشی و غیرقابل استفاده واقعی‌اند.
- `/nearby` سه context موقعیت فعلی/اقامت/مقصد، کنترل دسته‌ها، نقشه نمایشی و results sheet دارد. شریک نمونه، اعتبارپذیر و مکان عمومی با badge و منبع جدا نمایش داده می‌شوند.
- `/services` خدمات قبل سفر، ترانسفر، غذا، تجربه، سوغات و خدمات تکمیلی را با CTA اقدام‌محور از Destination discovery جدا می‌کند.
- نشان کوتاه «اعتبارپذیر» ایجاد شد؛ مانده، eligibility و authorization در frontend تولید نمی‌شود.
- دستیار context-aware و ورودی ثابت اما غیرمزاحم پشتیبانی انسانی در صفحات سفر وجود دارد؛ availability شبانه‌روزی ادعا نشده است.
- notificationهای نمونه booking/reminder/arrival با deep linkهای آینده‌نگر تعریف شده‌اند.
- interfaceهای مستقل `PlaceProvider`، `MapProvider`، `BookingProvider`، `NotificationProvider` و `PaymentProvider` ساخته شدند؛ تنها `MockPlaceProvider` فعال است.
- Homepage بازطراحی نشد. فقط لینک‌های ظریف «سفرهای من» و «اطراف من»، اتصال Service Ribbon به `/services` و مسیر Mock رزرو از نتایج اضافه شدند.

### QA این فاز

- `npm run lint`: موفق.
- `npx tsc --noEmit`: موفق.
- تست backend: `2 passed`؛ دو warning قدیمی FastAPI `on_event` باقی است.
- همه مسیرهای قبلی و جدید، شامل confirmation، trips، سه stage سفر، nearby و services روی dev server پاسخ `200` دادند.
- QA مرورگری تصویری ادعا نمی‌شود؛ ابزار browser قابل‌کنترل در محیط موجود نیست. responsive با breakpointهای Desktop/Tablet/Mobile در CSS پیاده و از نظر ساختاری بازبینی شد.

### اتصال واقعی موردنیاز

برای Production باید storage/authorization واقعی Trip، Provider رزرو و واچر، location consent، Map/Places provider، سرویس اعلان، payment/credit backend، قرارداد Merchant، tracking پشتیبانی و صحت ساعات/فاصله‌ها متصل و تست fail-closed شوند.

## Unified Services + Manage Booking — ۱۴۰۵/۰۵/۲۶

- `/manage-booking/book1` برای رزرو پرواز Mock ایجاد شد و summary، انتخاب اقدام/case، policy preview، confirmation صریح، escalation و timeline کامل درخواست دارد.
- معماری تنها مخصوص پرواز نیست: `BookableServiceType` پرواز، هتل، اقامتگاه، قطار، تور، خودرو، ترانسفر، تجربه و سایر خدمات را پوشش می‌دهد.
- مدل‌های `PolicySnapshot`، policyهای cancellation/refund/change/no-show/disruption، quoteهای cancellation/change، درخواست refund/modification، disruption case، refund transaction و support escalation به مدل Booking/Trip موجود متصل شدند.
- `policyAtBooking` و `currentPolicy` snapshot جدا دارند. در Mock فعلی eligibility، جریمه، مبلغ استرداد و مسیر بازپرداخت unknown و نیازمند بررسی Provider هستند.
- CTA «تغییر، کنسلی و استرداد» از My Trip، BookingCard، VoucherCard، confirmation، AI و Support قابل دسترسی است.
- Assistant رزرو نمونه را می‌شناسد، intent کنسلی/استرداد را پاسخ می‌دهد و بدون policy معتبر به کارشناس hand-off می‌کند.
- Homepage بدون تغییر Hero/Search/Bento/Selected Trips، فقط یک Services Hub utility میان Search و مقصدها دریافت کرد. Header به خدمات، سفرهای من، اطراف من و سازمانی ساده شد.
- `/services` به شش گروه و ۱۲ خدمت Mock گسترش یافت؛ CTAها عملیاتی، قابلیت اعتبار نمونه قابل فیلتر و توضیح backend authority یک‌بار نمایش داده می‌شود.
- notificationهای voucher و after-sales با deep link به Trip و Manage Booking افزوده شدند.
- ادعاهای تأییدنشده پشتیبانی ۲۴/۷ و policy قطعی کنسلی از UI نمونه حذف شدند.

### QA این فاز

- `npm run lint`: موفق.
- `npx tsc --noEmit`: موفق.
- backend: `2 passed` و دو warning قدیمی FastAPI `on_event`.
- تمام مسیرهای قبلی و جدید `200`؛ `/manage-booking/not-found` و `/trips/not-found` برابر `404`.
- Browser screenshot QA در دسترس نبود و ادعای بازبینی تصویری نمی‌شود؛ breakpointهای Desktop/Tablet/Mobile و جلوگیری ساختاری از overflow برای componentهای جدید اضافه شده‌اند.

### اتصال Production باقی‌مانده

Policy/quote باید از Provider یا policy store امضاشده دریافت شود؛ request mutation، idempotency، audit، authorization، refund transaction، payment route، supplier workflow، SLA، attachment امن و notification delivery هنوز غیرفعال و fail-closed هستند.

## Support Visibility Completion — ۱۴۰۵/۰۵/۲۶

- Header ورودی پشتیبانی دارد و کنار Search یک CTA انسانی «نیاز به راهنمایی داری؟ / صحبت با کارشناس» افزوده شد؛ AI از این CTA جداست.
- SupportDock در `/`، Trip، Nearby، Services و Manage Booking حضور دارد و پنج اقدام دستیار، کارشناس، پیگیری، after-sales و مشکل سفر را نشان می‌دهد.
- `/support` مسیر انتخاب نوع کمک را با Trip Context شیراز و disruption نمونه فراهم می‌کند؛ availability یا SLA واقعی ادعا نمی‌شود.
- `/manage-booking/book1` پوشش حمل‌ونقل و `/manage-booking/book2` پوشش اقامت را با action catalog متفاوت، policy preview و confirmation غیرمخرب نمایش می‌دهند.
- timeline اکنون هر ۹ status، شامل «رد شد»، را دارد. رزرو disruption نمونه پیام «تغییری در سفرت پیش آمده؟» نشان می‌دهد.
- Assistant هر هشت intent مصوب قوانین/کنسلی/تغییر/واچر/استرداد را سطح UI می‌شناسد و در نبود policy معتبر به بررسی کارشناس hand-off می‌کند.
- QA: lint و typecheck موفق؛ backend `2 passed`؛ همه routeهای قدیمی و جدید `200`؛ booking/trip نامعتبر `404`. پنج action Dock در HTML هر شش سطح و markerهای اقامت/statusها در SSR تأیید شدند.

## نتیجه QA نهایی Homepage

- dev server با `next dev --webpack` روی localhost اجرا شد؛ هر ۹ مسیر اصلی و همه CTAهای Homepage پاسخ `200` دارند و تصاویر Figma و مسیر بهینه‌سازی `next/image` سالم‌اند.
- `npm run lint` و `npx tsc --noEmit` موفق‌اند؛ تست API: `2 passed`.
- `npm audit --omit=dev`: صفر آسیب‌پذیری.
- ابزار مرورگر این محیط هیچ browser instance ارائه نکرد؛ بنابراین screenshot-based review در viewportهای ۱۴۴۰/۷۶۸/۳۷۵ قابل اجرا نبود. قواعد responsive این سه breakpoint به‌صورت کدبازبینی اصلاح شدند، اما browser E2E تصویری همچنان یک کنترل محیطی باقی می‌ماند.
- Node استاندارد سیستم در PATH یا مسیرهای معمول نصب نیست؛ production build با runtime داخلی ChatGPT عمداً معیار پذیرش قرار نگرفت.

## پالایش Human-Centered — ۱۴۰۵/۰۵/۲۶

- Search به حدود ۹۵٪ عرض محتوای اصلی در Desktop افزایش یافت و هشت سرویس با واژگان و فیلدهای متناسب دریافت کردند؛ در Tablet و Mobile تب‌ها اسکرول‌پذیر و فرم به‌ترتیب سه و دو ستون جمع می‌شود.
- سفرهای منتخب اکنون تناسب سفر، موارد همراه، وضعیت قوانین و محدودیت تأمین‌کننده را نشان می‌دهند؛ داده و قیمت همچنان Mock است.
- همراه هوشمند دلیل پیشنهاد را در سه محور بودجه/زمان/حال‌وهوا نمایش می‌دهد و کنترل نهایی کاربر را تصریح می‌کند.
- مقایسه به قابلیت امضای Homepage تبدیل شد و تفاوت‌های تصمیم‌ساز هر گزینه را کنار امتیاز ساختاریافته نشان می‌دهد.
- بخش سازمانی اعتبار، سهم شخصی و گردش تأیید را تفکیک می‌کند و صریحاً backend را مرجع مانده می‌داند.
- بخش اعتماد پیش از Footer برای مجوزها، حقوق مسافر، پرداخت/بازگشت وجه و هویت تأمین‌کننده ساخته شد؛ تا زمان راستی‌آزمایی هیچ شماره، نشان یا ادعای رسمی نمایش داده نمی‌شود.
- نوار اکوسیستم ورودی صنایع‌دستی/سوغات و خدمات پیش از سفر را اضافه کرده است، بدون ادغام با Marketplace مستقل دیگری.
- اجرای زنده تازه روی Next.js 16.3.1: مسیرهای `/`، `/hotels`، `/compare`، `/assistant`، `/organization`، `/employee`، `/white-label`، `/integrations` و `/pilot` همگی `200`؛ lint و TypeScript موفق؛ تست API `2 passed` با دو warning قدیمی deprecation مربوط به FastAPI `on_event`.
- Build همچنان فقط به‌دلیل نبود Node استاندارد سیستم اجرا نشده است (`which -a node` و محیط PATH استاندارد هر دو `node not found`). dev server با WASM fallback و webpack قابل اجراست؛ خطای code-signing SWC native مانع QAهای دیگر نشده است.

## بازطراحی مرجع کرم / بنفش / کورال

- ساختار قبلی سرمه‌ای/فیروزه‌ای Homepage کنار گذاشته شد؛ صفحات عملیاتی موجود مستقل باقی مانده‌اند.
- تصویر Hero اختصاصی معماری یزد و مسافر در `public/images/home/hero-yazd.png` ذخیره و تمام تصاویر Homepage محلی شدند.
- مقصدهای قشم، شیراز، اصفهان و ماسوله در collage نامتقارن؛ سه سفر منتخب؛ همراه هوشمند آبی؛ مقایسه بنفش؛ بخش سازمانی مصور؛ نوار خدمات کورال و Footer منحنی پیاده‌سازی شدند.
- بررسی زنده: Homepage و هشت مسیر وابسته `200`، چهار asset محلی `200` و Image Optimizer `200`؛ لاگ runtime بدون warning تصویر یا route است.
- فایل JPEG مرجع با نام اعلام‌شده در workspace یا مسیرهای موقت موجود نبود؛ پوشه `public/reference` و توضیح وضعیت ایجاد شد و فایل دیگری با نام مرجع جعل نشد.
- browser instance در ابزار مرورگر محیط موجود نیست؛ QA تصویری screenshot-based قابل اجرا نبود و responsive از طریق بازبینی CSS و اجرای زنده HTTP کنترل شد.

## پالایش تجربهٔ مدیریت رزرو و پشتیبانی — ۱۴۰۵/۰۵/۲۶

- صفحه‌های پرواز و اقامت با خلاصهٔ واحد رزرو، چهار اقدام روشن، پیش‌نمایش پیامد، تأیید غیرمخرب و راهنمای متناسب با نوع خدمت بازآرایی شدند؛ مدل‌ها و مسیرهای دامنه تغییر نکردند.
- واژه‌های توسعه‌ای از سطح اصلی مدیریت رزرو، پشتیبانی، دستیار و سفر من حذف و با زبان طبیعی فارسی جایگزین شدند. تنها یک اعلان سطح صفحه، نمونه‌بودن اطلاعات را بیان می‌کند.
- قوانین اقامت به timeline قابل‌خواندن و امکان‌های تغییر به ردیف‌های «نیازمند بررسی» تبدیل شدند؛ حمل‌ونقل نیز تغییر تاریخ، کنسلی، صدور مجدد، اختلال و عدم حضور را با همین زبان پوشش می‌دهد.
- timeline درخواست هر ۹ حالت را حفظ می‌کند، اما فقط مرحلهٔ جاری برجسته است. دستیار هوشمند و کارشناس از نظر متن و خانوادهٔ بصری از هم تفکیک شده‌اند.
- SupportDock در Desktop فشرده و در Mobile یک محرک bottom-sheet جمع‌شونده است؛ فاصلهٔ انتهای صفحه برای جلوگیری از پوشاندن CTAها حفظ شده است.
- QA: lint و TypeScript موفق؛ backend `2 passed` با دو warning قدیمی FastAPI؛ مسیرهای `/manage-booking/book1`، `/manage-booking/book2`، `/support`، `/trips/mock-shiraz-1405`، `/assistant`، `/nearby`، `/services` و `/` برابر `200` و شناسه‌های نامعتبر برابر `404`.

## زیرساخت سبک مرکز زنده سفر — ۱۴۰۵/۰۵/۲۶

- مدل provider-neutral رویداد سفر با اتصال اختیاری به Booking، شدت، منبع، وضعیت راستی‌آزمایی و deep link اضافه شد؛ منبع سیستم/تأمین‌کننده، AI و پشتیبانی انسانی از هم متمایزند.
- سه رویداد نمونه در «سفر من» با نمای سبک نمایش داده می‌شوند و `/trips/mock-shiraz-1405?event=[eventId]` رویداد مقصد را برجسته می‌کند.
- `NotificationProvider` برای in-app، push و sms توسعه یافت؛ implementation نمونه فقط `not-sent` برمی‌گرداند و هیچ پیام واقعی ارسال نمی‌کند.
- مدل سبک ترجیحات اعلان چهار موضوع اصلی را پوشش می‌دهد. UI تنظیمات، SMS، Push، webhook، realtime و delivery confirmation خارج از scope و غیرفعال‌اند.
- QA: lint و TypeScript موفق؛ backend `2 passed` با دو warning قدیمی؛ Trip، deep linkهای رویداد، Manage Booking، Support، Assistant و Homepage برابر `200` و Trip نامعتبر برابر `404`.

## دستیار AI نهایی Homepage — ۱۴۰۵/۰۵/۲۶

- بخش هوشمند موجود، بدون جابه‌جایی سایر بخش‌ها، به «دستیار هوشمند سفر کارن‌سیر» با badge صریح AI، متن مصوب، پنج قابلیت و CTA مستقیم `/assistant` تبدیل شد.
- رنگ آبی قبلی از این بخش حذف و طراحی آن فقط با کرم، بنفش عمیق و کورال Homepage یکپارچه شد؛ ظاهر آن از ورودی پشتیبانی انسانی متمایز است.
- در Mobile دکمهٔ ثابت کوچک «دستیار AI» بالاتر از SupportDock قرار دارد و در Desktop/Tablet مخفی است. breakpointهای Desktop، Tablet و Mobile بدون تغییر layout سایر بخش‌ها تعریف شدند.
- QA: lint و TypeScript موفق؛ backend `2 passed`؛ `/` و `/assistant` برابر `200`. ترتیب زندهٔ DOM برابر Selected Trips → AI Assistant → Comparison تأیید شد. مرورگر تعاملی متصل نبود، بنابراین screenshot QA ادعا نمی‌شود.
