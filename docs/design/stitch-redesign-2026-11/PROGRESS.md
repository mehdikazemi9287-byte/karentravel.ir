# گزارش پیشرفت و QA — بازطراحی Stitch کارن تراول

تاریخ: ۱۴۰۵/۰۸/۲۴ (2026-11-15) · شاخه: `design/stitch-redesign-2026-11`

## SUPERVISOR GATE

```
Decision: ALLOW (design-only)
Current HEAD (main): c09b8dc
Requested scope: بازطراحی در Google Stitch در سه سطح؛ Homepage تا حد امکان حفظ شود؛ انتقال به GitHub؛ سپس Figma و deploy
Existing implementation: Homepage Plum/Coral/Cream (app/page.tsx → Home)، صفحات داخلی با توکن‌های قدیمی سرمه‌ای/فیروزه‌ای
Relevant risks: Homepage محافظت‌شده است → فقط با تأیید صریح مالک (این درخواست) و با حفظ ترتیب/پالت
Scope drift: ندارد — هیچ فایل کد اپلیکیشن، migration یا production تغییر نکرد
Production write required: خیر
Rollback: حذف پوشه docs/design/stitch-redesign-2026-11 یا عدم merge شاخه
```

## انجام‌شده

| # | کار | وضعیت | شواهد |
|---|---|---|---|
| 1 | پروژه Stitch «Karen Travel Persian Booking Platform» با design system برند (کرم/بنفش‌تیره/کورال/طلایی، Vazirmatn، RTL) | ✅ | پروژه 5840488886534725646 در Stitch |
| 2 | Homepage دسکتاپ: ابتدا نسخه Stitch از چیدمان فاصله گرفت؛ اصلاح شد تا ترتیب ۱۲ بخش فعلی (هیرو یزد، جست‌وجو، خدمات، موزاییک مقصدها، سفرهای منتخب، دستیار AI، مقایسه، تجربه‌ها، سازمانی، اعتماد، فوتر) حفظ شود | ✅ | `desktop/01-home.html` |
| 3 | ۱۳ صفحه داخلی دسکتاپ از نو | ✅ | `desktop/02…14` |
| 4 | ۷ صفحه وب موبایل (Homepage با همان ترتیب + bottom nav) | ✅ | `mobile/` |
| 5 | ۷ صفحه اپلیکیشن native | ✅ | `app/` |
| 6 | خروجی کد از Stitch → GitHub (Code to Clipboard → ویرایشگر GitHub → تفکیک و حذف تکراری‌ها با md5) | ✅ | ۲۸ فایل HTML یکتا |
| 7 | یکسان‌سازی توکن‌های Tailwind خروجی با پالت برند (`primary-container=#EF5B3D`، `background=#F5EEE4`، `on-surface=#2A1530`، `tertiary-container=#EFB448`) | ✅ | ۱۳۵ جایگزینی |
| 8 | گالری پیش‌نمایش `index.html` | ✅ | |

## QA

- همه ۲۸ فایل `dir="rtl"` دارند و فونت Vazirmatn بارگذاری می‌کنند.
- Homepage: ۲۴۰ ارجاع به `#2A1530`، ۱۱۱ به `#EF5B3D`، ۶۰ به `#EFB448`، ۴۴ به `#F5EEE4` — پالت حفظ شده است.
- تلفن پشتیبانی در هدر و انتخاب یک‌طرفه/رفت‌وبرگشت بیرون از تقویم (اصلاحات مصوب ۱۴۰۵/۰۸/۱۸) در طرح اعمال شده است.
- محدودیت: فایل‌ها به Tailwind CDN، Google Fonts و تصاویر `lh3.googleusercontent.com` وابسته‌اند؛ برای پیاده‌سازی باید تصاویر واقعی/مجاز جایگزین شوند (عکس‌ها تولیدی Stitch هستند).
- محدودیت: متن‌ها و اعداد نمایشی‌اند؛ در پیاده‌سازی باید برچسب Mock یا داده معتبر سرور جایگزین شود (قانون AGENTS.md).
- برخی عناوین داخلی خروجی Stitch انگلیسی است (مثلاً `Checkout Flow`)؛ در پیاده‌سازی فارسی شود.

## Figma

- فایل: https://www.figma.com/design/R3FvzMWcCVLmgKviiY0lav (تیم Figma متصل: «hamid ansari's team»)
- صفحه‌ها: `📐 Design System` (متغیرهای رنگ/فاصله/شعاع، ۸ text style با Vazirmatn، کامپوننت‌های Button[Primary/Plum/Ghost]، Chip، Badge/Mock، Service Tile) · `🖥 Desktop` (۱۴ فریم) · `📱 Mobile Web` (۷) · `📲 App` (۷).
- همه فریم‌ها لایه‌های قابل ویرایش (auto-layout، متن واقعی، نمونه‌های کامپوننت و رنگ‌های bind‌شده به متغیر) هستند؛ هیچ اسکرین‌شاتی جای طرح نیامده.
- محدودیت: تصاویر عکاسی در Figma به‌صورت قاب placeholder بنفش هستند (Plugin API تصویر خارجی بارگذاری نمی‌کند). نسخه پیکسلی با عکس‌ها در Stitch و GitHub Pages است.
- مسیر جایگزین برای نسخه پیکسل‌به‌پیکسل: در Stitch صفحه را انتخاب کنید → Export → Figma → Copy → در Figma Paste (در محیط خودکار، کپی code.to.design تکمیل نشد).

## Deploy

- پیش‌نمایش طراحی (GitHub Pages، شاخه `gh-pages`): https://mehdikazemi9287-byte.github.io/karentravel.ir/ — بررسی‌شده در مرورگر؛ شواهد در `qa/gallery-*.jpg`.
- Deploy روی سرور production کارن‌سیر انجام **نشد**: (۱) این خروجی طراحی است و هنوز در Next.js پیاده‌سازی نشده؛ (۲) از این محیط دسترسی SSH/کلید به سرور 188.121.123.218 وجود ندارد؛ (۳) طبق AGENTS.md هر تغییر UI/production نیازمند Supervisor Gate، تست و rollback است.

## باقی‌مانده / برنامه بعدی

1. تأیید نهایی طرح‌ها توسط مالک (Stitch / Figma / Pages).
2. جایگزینی عکس‌های تولیدی Stitch با تصاویر مجاز؛ فارسی‌سازی باقی‌مانده عناوین انگلیسی خروجی Stitch.
3. پیاده‌سازی در Next.js صفحه‌به‌صفحه با Supervisor Gate؛ ترتیب پیشنهادی: صفحات داخلی (نتایج → جزئیات → checkout → مدیریت رزرو) سپس هماهنگی Homepage موبایل.
4. Deploy روی سرور production (188.121.123.218) فقط پس از پیاده‌سازی، تست و دسترسی سرور.


## به‌روزرسانی ۱۴۰۵/۰۸/۲۵ — اجرای سه قدم بعدی

### ۱) جایگزینی تصاویر تولیدی Stitch — ✅ (در فایل‌های طراحی و پیش‌نمایش)
- ۹۰ تصویر/پس‌زمینه `lh3.googleusercontent.com` حذف شد: ۱۷ مورد با عکس‌های خود پروژه (`public/images`: یزد، شیراز، قشم، شمال) جایگزین شد، ۵ آواتار با آواتار برند، و ۶۸ مورد (عکس هتل‌ها/اتاق‌ها/استانبول که هتل واقعی را با تصویر ساختگی نشان می‌داد) با قاب برند «تصویر مجاز جایگزین شود».
- فایل‌ها در `assets/`. عکس واقعی هتل‌ها باید از تأمین‌کننده/هتل با مجوز دریافت شود.

### ۲) پیاده‌سازی در Next.js — ✅ (فاز اول: Shell و صفحات داخلی) · ADR-022
- `app/redesign-2026-11.css` + `Shell` جدید در `app/page.tsx` (هدر با تلفن، فوتر بنفش، ناوبری پایین موبایل).
- صفحات اثرپذیر: `/hotels`، `/compare`، `/assistant`، `/organization`، `/employee`، `/white-label`، `/integrations`، `/search/results`. Homepage و JourneyShell دست‌نخورده.
- تست: `tsc --noEmit` ✅ · eslint ✅ · `next build --webpack` ✅ · اسکرین‌شات Chrome headless دسکتاپ/موبایل در `qa/impl/`.

### ۳) Deploy — ⛔ BLOCKED_EXTERNAL
- از این محیط اتصال SSH/HTTPS به سرور 188.121.123.218 و karentravel.ir بسته است.
- بسته آماده: `deploy/patches/0001-…patch` و راهنمای گام‌به‌گام `deploy/REDESIGN_2026-11_DEPLOY.md` (با بررسی و Rollback).
- پیش‌نمایش طراحی روی GitHub Pages به‌روز شد.

### باقی‌مانده
- deploy روی سرور توسط تیم/دسترسی SSH.
- فاز دوم پیاده‌سازی: هماهنگ‌سازی کامل جزئیات صفحات (کارت نتایج، checkout، مدیریت رزرو) با طرح‌های Stitch.
- دریافت عکس‌های مجاز هتل‌ها.


## به‌روزرسانی ۱۴۰۵/۰۸/۲۵ (۲) — پیشنهادهای Stitch

### دور اول پیشنهادها
- انتخاب صندلی: `app/08-seat-map.html` و `app/09-seat-confirm.html`
- فیلترها به‌صورت پنل کشویی از پایین (bottom sheet): `app/10-filters-flight-bottom-sheet.html` و `app/11-filters-hotel-bottom-sheet.html`
- حالت تاریک: `app/12-dark-boarding-pass.html`، `app/13-dark-wallet.html`، `app/14-dark-home.html`

### دور دوم پیشنهادها
- حالت تاریک برای بقیه صفحه‌ها: `app/15-dark-ai-assistant.html`، `app/16-dark-my-trips.html`، `app/17-dark-profile.html`
- نمونه دقیق‌تر مسیر صندلی تا پرداخت: `app/18-seat-map-detailed.html` ← `app/19-ancillaries.html` ← `app/20-payment.html` ← `app/21-booking-confirmed.html`
- مستندات Design System تاریک: `design-system-dark.html`

### نکته فنی درباره حالت تاریک
- Stitch این صفحه‌ها را روی بوم خودش تاریک نشان می‌دهد، ولی کد خروجی را با رنگ‌های روشن تحویل داد.
- رنگ‌های Tailwind این صفحه‌ها را به نسخه تاریک برند برگرداندیم: زمینه `#1A0D1F`، کارت‌ها `#2A1530`، متن `#F5EEE4`، کورال `#F26A4D`.
- ابزار تبدیل: `tools/darkify.py`، در پیام commit ثبت شده است.

### Figma
- برای مجموعه متغیرهای برند یک حالت (mode) «Dark» اضافه شد.
- در صفحه App، نسخه تاریک ۱۰ صفحه ساخته شد:
  - خانه، کارت پرواز، کیف پول، سفرهای من، دستیار، پروفایل
  - صندلی دقیق، خدمات تکمیلی، پرداخت، صدور بلیت
- صفحه‌های جدید روشن: انتخاب صندلی، تأیید صندلی و دو پنل کشویی فیلتر.
- در صفحه Design System یک بورد «Design System · Dark mode» با جدول کنتراست اضافه شد. نسبت‌های کنتراست محاسبه‌شده:
  - کرم روی زمینه تاریک: 16.3:1
  - متن ثانویه: 9.7:1
  - طلایی: 10.1:1
  - دکمه کورال با متن سفید: 3.4:1 (فقط برای متن درشت)

### سرور
- همچنان مسدود است (BLOCKED_EXTERNAL)؛ از این محیط به سرور دسترسی نیست.
- برای تیم آماده است: `deploy/REDESIGN_2026-11_DEPLOY.md` و فایل patch.


## به‌روزرسانی ۱۴۰۵/۰۸/۲۵ (۳) — سه پیشنهاد جدید Stitch
1. انیمیشن‌های تعاملی: `app/22-seat-map-interactive.html` (حالت‌های hover/press/انتخاب صندلی و tooltip قیمت) و `app/23-payment-processing.html` (لودینگ پرداخت: هواپیما روی مسیر، مراحل درگاه/بانک/صدور). انیمیشن‌ها با CSS keyframes ساخته شده‌اند و `prefers-reduced-motion` در هر دو رعایت شده است.
2. تبلت B2B: `tablet/01-b2b-dashboard-portrait.html` (عمودی) و `tablet/02-b2b-dashboard-landscape.html` (افقی). محتوا: اعتبار سازمانی، سیاست سفر، گردش تأیید با SLA، گزارش هزینه و جدول سفرهای کارکنان.
3. کنسلی و استرداد: `app/24-refund-request.html` ← `app/25-refund-tracking.html` ← `app/26-refund-completed.html`. مبلغ استرداد همه‌جا «پس از استعلام از تأمین‌کننده» است و هیچ عددی حدس زده نشده.

### Figma
- صفحه App: `22 Seat Map · Interaction States`، `23 Payment Processing`، `24–26 Refund`.
- صفحه جدید `📋 Tablet`: داشبورد B2B عمودی و افقی.

### سرور
- همچنان BLOCKED_EXTERNAL؛ راهنمای deploy در `deploy/REDESIGN_2026-11_DEPLOY.md` است.


## به‌روزرسانی ۱۴۰۵/۰۸/۲۵ (۴) — سه پیشنهاد جدید Stitch (تبلت افقی B2B)
1. `tablet/03-travel-policy-settings.html` — تنظیمات پالیسی و ضوابط سفر: ماتریس سقف بودجه پرواز/هتل بر اساس رده شغلی، نیاز به تأیید قبلی، شاخص انطباق. چون Stitch برچسب Mock نگذاشته بود، یک نشان ثابت «داده‌های نمایشی (Mock)» به صفحه اضافه شد.
2. `tablet/04-credit-finance.html` — اعتبار و امور مالی: سقف ۵۰٬۰۰۰٬۰۰۰، مانده ۳۰٬۶۰۰٬۰۰۰ (۶۱.۲٪)، بدهی جاری ۱۹٬۴۰۰٬۰۰۰ تومان (همه Mock؛ جمع‌ها کنترل شد)، نمودار ۶ ماهه، تفکیک هزینه، صورتحساب‌ها با مالیات بر ارزش افزوده ۱۰٪.
3. `tablet/05-quick-approve-invoice-modal.html` — داشبورد با مودال «تأیید سریع درخواست و صدور فاکتور رسمی» (خلاصه سفر، انطباق با پالیسی، پیش‌فاکتور).

### Figma
- صفحه `📋 Tablet`: فریم‌های `Credit & Finance`، `Travel Policy Settings` و `Quick Approve + Invoice Modal` (جمع فاکتور کنترل شد: ۳۶٬۳۶۳٬۶۳۶ + ۳٬۶۳۶٬۳۶۴ + ۴۴۰٬۰۰۰٬۰۰۰ = ۴۸۰٬۰۰۰٬۰۰۰ ریال).

### انتقال از Stitch
- این دور، paste فقط با `Cmd+V` (سیستم کاربر macOS) کار کرد؛ طول هر فایل بعد از paste با state ویرایشگر GitHub مقایسه شد (۴۱۸۵۹، ۴۳۰۶۱ و ۲۸۸۹۷ کاراکتر).

### سرور
- همچنان BLOCKED_EXTERNAL؛ راهنما: `deploy/REDESIGN_2026-11_DEPLOY.md`. پیش‌نمایش عمومی: GitHub Pages.
