# Capability / gap audit — candidate 2026-10-07

وضعیت‌ها: WORKING = روی candidate پیاده و آزموده؛ PARTIAL = بخشی موجود (معمولاً API بدون UI یا بدون بازآزمایی)؛ MISSING = وجود ندارد؛ EXTERNAL_BLOCKED = تا مرز سرویس بیرونی آماده.
جمع: WORKING 16 · PARTIAL 18 · MISSING 5 · EXTERNAL_BLOCKED 10 (از 49).

| نقش | قابلیت | وضعیت | شاهد / مانع |
|---|---|---|---|
| Customer | سفرهای من / رزروها | EXTERNAL_BLOCKED | backend و UI موجود؛ ورود واقعی مشتری به OTP زنده وابسته است |
| Customer | واچر و مدارک | EXTERNAL_BLOCKED | صدور به رزرو تأییدشدهٔ تأمین‌کننده وابسته است |
| Customer | پرداخت‌ها | EXTERNAL_BLOCKED | درگاه: merchant و callback روی HTTPS |
| Customer | درخواست لغو/استرداد | EXTERNAL_BLOCKED | ثبت درخواست و quote موجود؛ استرداد واقعی به درگاه وابسته است |
| Customer | پشتیبانی (پرونده و پاسخ انسانی) | WORKING | CAPABILITY_REGISTRY: human_support LIVE |
| Customer | اعلان درون‌برنامه‌ای | WORKING | هر رویداد سفر → اعلان + تلاش تحویل؛ خوانده‌شدن با تأیید رویداد (تست API) |
| Customer | Push / SMS | EXTERNAL_BLOCKED | تلاش تحویل ثبت می‌شود (not_sent)؛ credential پوش و قالب Kavenegar لازم است |
| Customer | Trip Timeline و «چه چیزی تغییر کرده؟» | WORKING | API + UI + مرورگر دسکتاپ/موبایل در این مرحله |
| Organization employee | درخواست سفر سازمانی / مزایا | PARTIAL | enterprise_travel_welfare PARTIAL |
| Organization employee | پیگیری رزرو درخواست تأییدشده | PARTIAL | enterprise_booking_tracking آماده، روی candidate |
| Organization admin | اعضا، سیاست، قالب تأیید | PARTIAL | routeها موجود؛ در این مرحله بازآزمایی نشد |
| Organization admin | اعتبار سازمانی | EXTERNAL_BLOCKED | organization_credit: تسویهٔ واقعی |
| Agency | تعریف آژانس، markup و کمیسیون | PARTIAL | ۳ route موجود |
| Agency | مشتریان، رزروها، quote، صورت کمیسیون، اعتبار، تسویه، گزارش | MISSING | در مدل داده رزرو به آژانس نسبت داده نمی‌شود؛ بدون قاعدهٔ انتساب، هر فهرستی ساختگی می‌بود |
| Partner | White-label | PARTIAL | پیکربندی برند موجود؛ دامنه/TLS خارجی |
| Supplier | محصول و موجودی (offer، واحد اقامتی، تور، تجربه) | PARTIAL | accommodation_marketplace PARTIAL |
| Supplier | نرخ و availability | PARTIAL | نرخ واحد اقامتی موجود؛ feed زنده ندارد |
| Supplier | رزروها/سفارش‌ها و fulfil | PARTIAL | reservations/ready و fulfil موجود |
| Supplier | تسویه‌های من | WORKING | جدید: /supplier/settlements فقط در دامنهٔ عضویت تأمین‌کننده (تست API) |
| Supplier | پروفایل و قراردادها | WORKING | جدید: /supplier/contracts (تست API) |
| Supplier | مدارک | PARTIAL | supplier assets موجود |
| Supplier | نگاشت API/provider به‌صورت سلف‌سرویس | MISSING | نگاشت فقط از سمت ادمین انجام می‌شود |
| Hotel operator | محتوای هتل در کاتالوگ (ادمین) | WORKING | منتشرشده در Production (backend) |
| Hotel operator | نگاشت هتل ↔ اتاق ↔ rate plan | WORKING | جدید: جدول‌ها و API ادمین با اعتبارسنجی (تست API) |
| Hotel operator | قرارداد search/availability/rate/recheck/reserve/confirm/cancel | WORKING | port و قواعد اعتبارسنجی با harness آزمون؛ هیچ منبعی در runtime ثبت نیست |
| Hotel operator | نرخ و موجودی زنده | EXTERNAL_BLOCKED | endpoint، token و قرارداد GRS |
| Tour operator | کاتالوگ مرجع تور (برنامهٔ سفر، هتل، حمل‌ونقل، وعده، قوانین) | PARTIAL | مدل و API ادمین کامل و تست‌شده؛ UI ندارد |
| Tour operator | محصول و تاریخ حرکت قابل‌فروش | PARTIAL | tour_products/departures موجود؛ ایجاد تاریخ گذشته اکنون رد می‌شود |
| Tour operator | تاریخ‌های آینده و نرخ تورهای CheckLine | EXTERNAL_BLOCKED | مالک/tenant و دادهٔ تأمین‌کننده لازم است |
| Flight operator | دادهٔ مرجع ایرلاین/فرودگاه | WORKING | ۷۲ ایرلاین، ۱۷۴ فرودگاه (محدود به ۶ کشور) |
| Flight operator | قرارداد search/fare/revalidate/PNR/issue/void/refund/schedule change | WORKING | flight_port + harness؛ تغییر برنامه به رویداد سفر تبدیل می‌شود |
| Flight operator | جست‌وجو و صدور واقعی | EXTERNAL_BLOCKED | تأمین‌کنندهٔ پرواز وجود ندارد |
| Finance | رکوردهای پرداخت، استرداد، تسویه، فاکتور، دفتر، حساب اعتباری | PARTIAL | جدید: API خواندن + خروجی CSV (تست API، tenant/RBAC)؛ صفحهٔ UI ندارد |
| Finance | مغایرت‌گیری | PARTIAL | موجود |
| Finance | مطالبات/بدهی و ماندهٔ محاسبه‌شده | MISSING | عمداً محاسبه نشده؛ قاعدهٔ حسابداری تأییدشده لازم است |
| Finance | کمیسیون | MISSING | به انتساب آژانس وابسته است |
| Tax/Accounting | فاکتور با مالیات و خروجی | PARTIAL | فیلد مالیات و export موجود |
| Tax/Accounting | گزارش مالیاتی / سامانهٔ مؤدیان | MISSING | طراحی نشده |
| Support | پرونده، تخصیص، پاسخ انسانی، حل | WORKING | LIVE |
| Support | یادداشت داخلی، workspace (زمینهٔ رزرو/مشتری/سفر)، SLA، ارجاع | PARTIAL | جدید: API کامل و تست‌شده؛ UI ندارد |
| Support | تفکیک پیام AI و انسانی | PARTIAL | در workspace برچسب author_kind دارد؛ پیام AI در رشتهٔ پرونده ذخیره نمی‌شود |
| Trip Operations | ثبت رویداد سفر (۱۰ دسته) با زمان، ثبت‌کننده، منبع، مقدار قبلی/جدید، رزرو، اهمیت | WORKING | API + UI + مرورگر |
| Trip Operations | مرکز عملیات: شمارنده‌ها، فیلتر، دیده‌نشده‌ها | WORKING | API + UI + مرورگر |
| Trip Operations | تأیید دیدن توسط مشتری و audit | WORKING | API + UI + مرورگر |
| Trip Operations | ورود خودکار رویداد از تأمین‌کننده | EXTERNAL_BLOCKED | webhook/قرارداد تأمین‌کننده |
| Platform admin | کاربران و نقش‌ها | WORKING | موجود |
| Platform admin | مدیریت کاتالوگ هتل | WORKING | پنل فقط در وب candidate |
| Platform admin | مدیریت تور مرجع و نگاشت‌ها | PARTIAL | API کامل؛ UI ندارد |
| Platform admin | حداقل دسترسی نقش دیتابیس | PARTIAL | migration 41 روی candidate اثبات شد؛ اجرا در Production مجوز جدا می‌خواهد |

## Notification architecture
رویداد سفر (`trip_events`) → `notifications` (گیرنده، قالب/topic، deep link، وضعیت خوانده‌شدن) → `notification_delivery_attempts` به ازای هر کانال (in_app برای Web و App، push، sms) با شمارهٔ تلاش، وضعیت، خطا، زمان‌بندی و رسید. ترجیحات کاربر کانال را حذف می‌کند. رویداد داخلی اعلان نمی‌سازد. تأیید رویداد توسط مشتری اعلان را خوانده‌شده می‌کند. دید عملیاتی: `GET /operations/notification-deliveries`. در این مرحله هیچ پیامک یا پوش واقعی ارسال نشد.

## Trip change log
یک منبع: `trip_events`. نوشتن: `POST /operations/trips/{id}/events` (و مسیر قدیمی backoffice که اکنون همان فیلدها را پر می‌کند). خواندن: مشتری `/trips/{id}/changes`، کارکنان `/operations/trip-events` و `/operations/trips/{id}/timeline`، پشتیبانی درون workspace، دستیار `/ai/trip-changes-context` (فقط رویداد ثبت‌شده؛ فهرست خالی یعنی «تغییری ثبت نشده»).

## Multi-tenant / RBAC (routeهای جدید)
آزمون خودکار: کارمند، تأمین‌کننده، آژانس، مالی و مدیر سازمان نمی‌توانند رویداد ثبت کنند یا مرکز عملیات را ببینند؛ کارشناس tenant الف سفر tenant ب را نه می‌بیند نه می‌نویسد (۴۰۴)؛ مشتری دیگرِ همان tenant و مشتری tenant دیگر به تغییرها، تأیید و context دستیار دسترسی ندارند (۴۰۴)؛ رزرو مشتری دیگر به سفر وصل نمی‌شود (۴۲۲)؛ دادهٔ مالی tenant دیگر در فهرست و CSV نیست؛ یادداشت داخلی در هیچ پاسخ مشتری نیست. candidate با نقش دیتابیس غیر superuser اجرا شد (RLS فعال).

## DB least privilege (karenseir_api روی جدول‌های کاتالوگ)
- یافته: در Production نقش API روی `catalog_*` مجوز DELETE و روی `catalog_places` مجوز نوشتن دارد (default privileges).
- نیاز واقعی برنامه: والدها (هتل، تور، تطبیق، نگاشت‌ها) SELECT/INSERT/UPDATE؛ فرزندهای جایگزین‌شونده (تصویر، نوع اتاق، روز برنامه، هتل تور) به‌علاوهٔ DELETE؛ مرجع‌ها فقط SELECT؛ snapshot نرخ SELECT/INSERT. تنها `delete(` در کد برنامه روی همین چهار جدول فرزند است.
- اثبات روی candidate: با همان مجوزهای گستردهٔ Production شروع شد، migration `20261010_41` اجرا شد، API با نقش محدود بالا آمد؛ ذخیرهٔ کامل هتل (جایگزینی ۴ تصویر و ۴ اتاق)، ثبت و تأیید رویداد سفر و QA مرورگر بدون هیچ `permission denied` روی جدول انجام شد؛ `DELETE catalog_hotels`، `UPDATE catalog_places`، `DELETE catalog_tours`، `DELETE catalog_hotel_provider_mappings` و `UPDATE catalog_tour_departures` با نقش API رد شدند.
- Runbook برای Production (نیازمند مجوز): ۱) backup و ثبت `\dp catalog_*`؛ ۲) استقرار API این شاخه همراه migration 39→41 (migration 41 فقط GRANT/REVOKE است)؛ ۳) smoke: ذخیرهٔ یک هتل در پنل، `/catalog/summary`، نبود `permission denied` در log؛ ۴) rollback: `alembic downgrade 20261009_40` (مجوز گستردهٔ قبلی را برمی‌گرداند) یا `GRANT SELECT, INSERT, UPDATE, DELETE ON <table> TO karenseir_api`. importerها با نقش owner اجرا می‌شوند و اثری نمی‌بینند.
- باقی‌مانده: default privileges خود Production تغییر نکرده، پس جدول‌های آینده هم باید در migration خودشان محدود شوند.
