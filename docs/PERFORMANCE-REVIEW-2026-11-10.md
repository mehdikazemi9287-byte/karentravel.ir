# بازبینی عملکرد کارن‌تراول — ۲۰۲۶-۱۱-۱۰

مبنا: `ac379c1a1a92b0a15a857a9d5e9ba14bb556f501` از main، checkout پاک.
دامنه: بررسی هدفمند درخواست بهینه‌سازی عملکرد؛ بدون اصلاح کد برنامه، DB، سرویس یا سایت زنده. گزارش‌های LIVE و baseline قدیمی اثبات استقرار فعلی نیستند. Deployment fingerprint فعلی UNKNOWN.

## نتیجه مدیریتی
پیاده‌سازی کامل نیست. چند امکان درست از قبل وجود دارد، ولی نقص‌های مشخص در کلاینت، جست‌وجو و کوئری‌های فهرست باقی مانده‌اند. از کد فعلی نمی‌توان مسئولیت خطا را به Claude یا عامل مشخصی نسبت داد.

## یافته‌ها به ترتیب اولویت

### ۱. بالا — تمدید هم‌زمان نشست می‌تواند باعث ابطال نشست شود
`lib/api/karenseir-client.ts:80` و `:97`: هر پاسخ 401 مستقلاً refresh را اجرا می‌کند؛ promise مشترک یا قفل refresh وجود ندارد.
آزمون ایزوله با دو درخواست هم‌زمان، **دو refresh با یک refresh token** ثبت کرد.
`backend/app/main.py:653` استفاده مجدد از توکن چرخانده‌شده را شناسایی و خانواده نشست را revoke می‌کند. بنابراین با رسیدن درخواست دوم پس از تکمیل اول، خروج ناخواسته/خطای نشست ممکن است. اثر روی سرور زنده بازتولید نشده است.
اصلاح پیشنهادی: یک refresh در حال اجرا به‌ازای نشست، بررسی هویت نشست قبل از اعمال پاسخ و آزمون concurrency با rotation واقعی.

### ۲. بالا — N+1 و خواندن تکراری Offerها در مقصدها
`backend/app/main.py:2736` در _destination_output تمام Offerهای فعال tenant را می‌خواند و در Python شمارش می‌کند.
`:2745` و `:2763` این تابع را برای هر مقصد فراخوانی می‌کنند: برای D مقصد و O پیشنهاد، تقریباً D بار خواندن O پیشنهاد؛ مسیر عمومی نیز درگیر است.
`:2516` فهرست پشتیبانی هم برای هر پرونده یک کوئری پیام جدا دارد.
شاهد: کنترل جریان مستقیم کد؛ benchmark/EXPLAIN اجرا نشده.
اصلاح پیشنهادی: aggregation/batch tenant-scoped یک‌باره، projection ستون‌های لازم و تست بودجه تعداد کوئری.

### ۳. متوسط — درخواست تکراری و انتظار بدون سقف در کلاینت
`lib/api/karenseir-client.ts:86-106`: fetch مرکزی نه dedup دارد، نه timeout و نه مسیر عمومی برای لغو درخواست.
آزمون واقعی همین کلاس با fetch شبیه‌سازی‌شده: دو GET همسان => **۲ فراخوانی شبکه**؛ AbortSignal ارسال‌شده => **false**.
timeout بعضی providerها و Nginx جای timeout مرورگر تا پایان دریافت body را نمی‌گیرد.
اصلاح پیشنهادی: dedup فقط خواندن‌ها با هویت نشست، deadline قابل‌کنترل، cancellation و invalidation پس از نوشتن؛ پرداخت بدون retry خودکار.

### ۴. متوسط — صفحه‌بندی پاسخ با صفحه‌بندی DB یکی نیست
`backend/app/main.py:1594` تمام Offerهای واجد شرایط را با all() وارد حافظه می‌کند.
`:1710` صفحه‌بندی search/v2 پس از پردازش و grouping در Python است؛ response صفحه‌بندی دارد ولی بار DB محدود نشده.
`:746` رزروها، `:752` سفرها، `:831` پرداخت‌ها نیز بدون limit/offset خوانده می‌شوند.
اصلاح پیشنهادی: قرارداد pagination سازگار با UI، SQL محدود و sort پایدار؛ API مالی بدون تغییر خاموش شکل پاسخ.

### ۵. متوسط — محافظ پاسخ قدیمی جست‌وجوی اصلی کامل نیست
`components/operational/UnifiedSearchView.tsx:48-49`: تغییر query/filter تابع execute را با setTimeout صفر دوباره اجرا می‌کند؛ فراخوانی قبلی نه abort می‌شود و نه generation guard دارد. پاسخ قدیمی می‌تواند بعد از پاسخ جدید setData کند. این مشاهده با خواندن کد تأیید شده، نه تست مرورگر.
autocomplete جدا در `HomeSearchExperience.tsx:58` debounce ۱۸۰ms و request counter دارد؛ این حفاظت به جست‌وجوی اصلی تعمیم نمی‌یابد.
اصلاح پیشنهادی: debounce برای تایپ، اجرای فوری submit، لغو/شناسه نسل و تست پاسخ‌های خارج از ترتیب.

### ۶. متوسط — cache_policy فقط برچسب JSON است
`backend/app/main.py:1452,1467` مقادیر private_tenant_30s و public_5m را داخل JSON برمی‌گرداند؛ در این handlerها cache واقعی یا Cache-Control متناظر وجود ندارد. وجود Redis در rate-limit/circuit-breaker اثبات cache نتیجه جست‌وجو نیست.
اصلاح پیشنهادی: فقط داده عمومی مجاز، کلید tenant-aware، TTL و invalidation تست‌شده؛ قیمت/موجودی نهایی همچنان recheck شود.

### ۷. تکمیل‌نشده — پایش مورد درخواست
`backend/app/observability.py` counter، مدت تجمعی و log ساختاریافته دارد؛ OpenTelemetry span/exporter و RUM/Web Vitals در مسیرهای بررسی‌شده پیدا نشد. trace درخواست کند و سرعت واقعی کاربران هنوز تأیید نشده‌اند.

## چیزهایی که واقعاً در سورس موجودند
- اسکلت نتایج: `UnifiedSearchView.tsx:19`.
- autocomplete با debounce ۱۸۰ms.
- Promise.all برای چند خواندن مستقل حساب/رزرو.
- engine و sessionmaker ماژولی SQLAlchemy؛ اتصال جدید برای هر query ساخته نمی‌شود، ولی تنظیم ظرفیت pool واقعی بررسی نشده.
- migration چهار ایندکس مرکب: `backend/alembic/versions/20260820_09_performance_indexes.py`؛ اعمال روی DB زنده تأیید نشده.
- Outbox worker و تست‌های مرتبط؛ زنده‌بودن worker فعلی بررسی نشده.
- فونت محلی پکیج vazirmatn در `app/layout.tsx`.
- gzip در `deploy/nginx.conf.example`؛ مثال کانفیگ اثبات فعال‌بودن روی سرور نیست.
- Next App Router/standalone؛ SSR و route splitting چارچوب موجود است، بهینه‌بودن تمام bundleها ادعا نمی‌شود.
- محدودیت زمان در برخی providerها و Redis برای resilience/rate-limit.

## باقی موارد فهرست
AVIF سراسری/تبدیل تصاویر قدیمی، CDN داخلی فعال، حذف پکیج بلااستفاده، virtualization، optimistic UI مناسب، streaming واقعی AI، هم‌مکانی DB، توزیع بار و تست موبایل/شبکه کند با شواهد فعلی تأیید نشده‌اند. «تأیید نشد» با «قطعاً وجود ندارد» یکسان نیست.

## شواهد قابل بازتولید
پس از نصب devDependencies، از ریشه مخزن:
`node docs/qa/performance-review-20261110/client-observations.cjs .`

خروجی ثبت‌شده: `client-observations.json`.
فقط fetch آزمایشی و داده مصنوعی مشخص دارد؛ هیچ شبکه واقعی، credential، کاربر یا DB واقعی استفاده نشده.
assertها مشاهده نقص فعلی را تأیید می‌کنند؛ گذشتن این script به معنی سالم‌بودن عملکرد برنامه نیست.

NOT_RUN: تست‌های backend، DB واقعی/PostgreSQL/Redis، کل build، benchmark قبل/بعد، بررسی live، مرورگر.
baseline محلی قدیمی ۵۰۰ درخواست و p95=184.29ms، تنها شاهد تاریخی مسیر hotels است و به مسیرهای دیگر/وضعیت فعلی تعمیم ندارد.

## اولویت اصلاح بعدی
ابتدا refresh هم‌زمان؛ سپس N+1 مقصدها/پشتیبانی؛ بعد deadline/dedup و ترتیب پاسخ جست‌وجو. هر اصلاح با تست مستقل و حفظ tenant isolation، fail-closed و ظاهر تأییدشده انجام شود.

