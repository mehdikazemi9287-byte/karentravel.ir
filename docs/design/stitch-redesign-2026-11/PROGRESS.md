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
- Deploy روی سرور production کارن تراول انجام **نشد**: (۱) این خروجی طراحی است و هنوز در Next.js پیاده‌سازی نشده؛ (۲) از این محیط دسترسی SSH/کلید به سرور 188.121.123.218 وجود ندارد؛ (۳) طبق AGENTS.md هر تغییر UI/production نیازمند Supervisor Gate، تست و rollback است.

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

## به‌روزرسانی ۱۴۰۵/۰۸/۲۵ (۵) — استقرار روی سرور (karenseir-prod، 188.121.123.218)
- دسترسی از طریق کنسول وب ابرک (ArvanCloud) و اسکریپت `deploy/redesign-2026-11-deploy.sh`.
- ۵ فایل ویرایش‌شده‌ی commit‌نشده روی سرور (admin/commerce، admin/inventory، contract/[reservationId]، finance/reports، finance/treasury) که از قبل داخل image زنده بودند، دور ریخته نشدند و به‌صورت commit `e1035be` روی سرور ثبت شدند.
- پشتیبان: `pre-redesign-HEAD.txt` = `e1035be` و image `karenseir-web:pre-redesign-20261116-190552`.
- ۷۹ فایل طراحی (همه صفحه‌ها، assets، QA، مستندات) + ADR-022 + ابزارها روی سرور در `/opt/karenseir/app/docs/design/stitch-redesign-2026-11` و commit `02e1420`.
- **کد ADR-022 اعمال نشد (Supervisor):** شاخه `production` (که سرور روی آن است) برای صفحات داخلی از `ApprovedShell` (هدر/فوتر مصوب Figma) استفاده می‌کند؛ patch ما روی `main` قدیمی ساخته شده بود و هدر/فوتر مصوب را بازنویسی می‌کرد. لازم است بازطراحی روی پایه `production` دوباره پیاده شود.
- گالری از روی دامنه سرو نشد: CSP تولید (`script-src 'self'`، `X-Frame-Options: DENY`) Tailwind CDN و iframeها را مسدود می‌کند. پیش‌نمایش عمومی همچنان GitHub Pages است.
- سایت زنده تغییری نکرد (rebuild/restart انجام نشد). نکته موجود از قبل: کانتینر `karenseir-worker-1` وضعیت unhealthy دارد.

## به‌روزرسانی ۱۴۰۵/۰۸/۲۶ (۶) — پیاده‌سازی دوباره روی پایه production (ADR-023)
- شاخه `feat/inner-redesign-on-production` (از `25d43ea`، همان پایه سرور) و PR #87 به `production`.
- فقط محتوای ۱۷ صفحه‌ای که با `ApprovedShell` رندر می‌شوند (خدمات، تماس، قوانین، ثبت‌نام، تأیید رزرو و…) اصلاح شد؛ صفحه اول، هدر/فوتر مصوب و صفحات JourneyShell دست‌نخورده.
- شواهد: tsc پاک، build موفق، صفحه اول قبل/بعد پیکسل‌به‌پیکسل یکسان؛ تصویر قبل/بعد: `qa/impl/services-before-after.png`.
- patch جدید: `deploy/patches/0002-ADR-023-inner-pages-refinement-on-production.patch`؛ patch قدیمی 0001 دیگر استفاده نمی‌شود.

## KARENSEIR CHECKPOINT — استقرار ADR-023 (۱۴۰۵/۰۸/۲۶، 2026-11-16 19:35 UTC)
- **Production changed: بله** — سرویس `web` روی karenseir-prod با image جدید بالا آمد (healthy).
- Server HEAD: `09cd898` (= `e1035be` snapshot ویرایش‌های زنده + `02e1420` اسناد طراحی + ADR-023).
- پشتیبان: `pre-redesign-HEAD.txt=e1035be`، imageهای `karenseir-web:pre-redesign-20261116-190552` و `…-193343`. Rollback: `bash /opt/karenseir/app/deploy/redesign-2026-11-rollback.sh`.
- Verify (مستقیم روی کانتینر web:3000): `/` 200 و ks-inner=0 (صفحه اول دست‌نخورده)، `/services` 200 و ks-inner=1، `/contact` 200 و ks-inner=1، `/hotels` 200، `/flights` 200؛ nginx:80 → 200.
- نکته: بررسی https داخل اسکریپت از خود سرور 000 داد (curl از host به دامنه خودش وصل نمی‌شود)؛ خطای سایت نیست.
- PR: #87 (`feat/inner-redesign-on-production` → `production`).
- باز: `karenseir-worker-1` از قبل unhealthy است (مرتبط با این کار نیست).

### Figma — کنترل کامل بودن (2026-11-16 19:40 UTC)
فایل https://www.figma.com/design/R3FvzMWcCVLmgKviiY0lav شامل همه صفحه‌های Stitch است: دسکتاپ ۱۴/۱۴، موبایل ۷/۷، اپ ۲۶/۲۶ (۱۱ روشن، ۱۰ تاریک، ۵ تعاملی/استرداد)، تبلت ۵/۵، به‌علاوه Design System روشن و تاریک.

## KARENSEIR CHECKPOINT — صفحات JourneyShell (2026-11-16 19:52 UTC)
- Production changed: بله — patch `0003` (لایه یکدستی ۴۷ صفحه JourneyShell) مستقر شد؛ `karenseir-web-1` healthy.
- Server HEAD: `e8c095a` (روی `f1942bb` = patch 0003). Image پشتیبان قبل از این مرحله: `karenseir-web:pre-redesign-20261116-194930`.
- Verify روی web:3000: `/`, `/services`, `/trips`, `/tours`, `/hotels`, `/flights`, `/support` همه 200؛ nginx:80 → 200.
- Local QA: صفحه اول، /hotels، /flights، /account، /manage-booking، /restaurants پیکسل‌به‌پیکسل بدون تغییر؛ فقط دکمه‌های /trips، /tours، /support.
- PR #87 شامل هر دو commit است (`43e344b`، `35a5e34`).
- باز: ادغام PR #87؛ `karenseir-worker-1` unhealthy (از قبل).

## ۱۴۰۵/۰۸/۲۶ — اصلاح نام برند و کنترل صفحه اول
- نام برند در همه صفحه‌های Stitch (۲۰ فایل، ۷۳ مورد) و فیگما (۲۸ متن) از «کارن‌سیر» به **«کارن تراول»** اصلاح شد؛ GitHub Pages به‌روز شد. (کارن‌سیر فقط نام داخلی مسیرها/مخزن می‌ماند.)
- کنترل صفحه اول روی سرور (`deploy/compare-homepage.sh`): HTML رندرشده‌ی image قبل از بازطراحی و نسخه زنده مقایسه شد — `/`، `/hotels`، `/flights` متن و کلاس‌ها **یکسان**؛ تنها تفاوت `/services` کلاس `ks-inner` است (عمدی).

## ۱۴۰۵/۰۸/۲۷ — پیاده‌سازی واقعی طراحی Stitch: صفحه نتایج جست‌وجو (patch 0004)
- `/search/results` به طراحی Desktop/02 و Mobile/02 استیچ درآمد: کارت خلاصه، فیلتر چسبان، کارت پرواز (نشان ایرلاین، ساعت درشت، خط مسیر، برچسب توقف)، دکمه قرمز تمام‌عرض.
- فقط ظاهر؛ داده، قیمت (فقط پس از ورود) و منطق رزرو بدون تغییر. QA با API نمایشی محلی (Mock): `qa/impl/flight-results-*-mock.png`.
- بعدی: نتایج هتل، جزئیات هتل، پرداخت، داشبورد.
- **مستقر شد (2026-11-18 08:48 UTC):** server HEAD `3b25575`، `karenseir-web-1` healthy؛ `/`، `/search/results`، `/services`، `/flights`، `/hotels` همه 200 (بررسی مستقیم روی کانتینر). PR #87 هم به‌روز شد.
- **patch 0005:** فهرست هتل/کاتالوگ، جزئیات هتل، پرداخت و داشبورد مشتری به طراحی استیچ (فقط ظاهر). QA: `qa/impl/hotels-stitch.png`، `qa/impl/account-checkout-stitch.png`.
- **patch 0006:** صفحه ورود/OTP به شکل کارت استیچ، مدیریت رزرو و تأیید رزرو. QA: `qa/impl/login-stitch.png`.

## KARENSEIR CHECKPOINT — طراحی استیچ روی صفحات سایت (2026-11-18 09:30 UTC)
- مستقر: patchهای 0004 (نتایج جست‌وجو)، 0005 (فهرست هتل/کاتالوگ، جزئیات هتل، پرداخت، داشبورد)، 0006 (ورود/OTP، مدیریت و تأیید رزرو). Server HEAD `c89c77d`، web healthy.
- Verify روی کانتینر: `/`، `/login`، `/hotels`، `/search/results`، `/account`، `/services`، `/flights` = 200. (`/manage-booking` بدون شناسه از قبل 404 است؛ مسیر واقعی `/manage-booking/[id]`.)
- نگاشت صفحات Stitch دسکتاپ → سایت: 02 و 08 → `/search/results`؛ 05 → `/hotels`؛ 03 و 07 → جزئیات کاتالوگ (`.cat-detail`)؛ 04 → `/account`؛ 09 و 10 → `/checkout/[id]`؛ 11 و 12 → مدیریت/تأیید رزرو؛ 06 و 13 → مقایسه و دستیار (لایه ADR-023)؛ 14 → `/login`. صفحه اول (01) طبق دستور دست‌نخورده. صفحات موبایل وب با قواعد واکنش‌گرا. صفحات «اپ» و «تبلت» مربوط به اپلیکیشن/پنل B2B هستند و در سایت جایی ندارند.
- باز: دیدن ظاهر زنده با داده واقعی توسط مالک؛ ادغام PR #87.
- **patch 0007 (بازبینی زنده):** چیدمان واقعی Desktop/05 در /hotels (فیلتر کناری + کارت افقی هتل)، رنگ کادر قیمت جزئیات هتل، رفع فشرده شدن فرم «نتیجه‌ای نبود» در /search/results. پیش‌نمایش با تزریق CSS روی سایت زنده بررسی شد.
- **مستقر و دیده‌شده روی سایت زنده (2026-11-18 10:40 UTC):** server HEAD `8b2b7f9`، web healthy. /hotels روی karentravel.ir با چیدمان Desktop/05 (فیلتر کناری + کارت افقی) دیده شد؛ صفحه اول بدون تغییر.
- ممیزی کامل سایت: `SITE-AUDIT-2026-11-18.md`.
- **0008 مستقر (2026-11-18 11:08 UTC):** server HEAD `9faee19`، web healthy؛ نتایج هتل جایگزین روی سایت زنده با عرض کامل دیده شد.

## ۱۴۰۵/۰۸/۲۷ — رفع موارد ممیزی (patch 0009)
- تاریخ شمسی: کامپوننت `JalaliDateInput` (روز/ماه/سال) جای ۱۶ فیلد تاریخ میلادی را گرفت (تور، درخواست کارشناس، هتل، رستوران، اجاره خودرو، پرواز+هتل، جاذبه‌ها، ترنسفر، مدارک مسافر…)؛ مقدار ذخیره‌شده مثل قبل ISO است.
- هدر اصلی سایت روی `/search/results`؛ مسیر تکراری حذف شد.
- نتایج هتل جایگزین: اول هتل‌های همان شهر/استان؛ هتل‌های شهرهای دیگر که فقط در نام شبیه‌اند حذف می‌شوند.
- کارت جست‌وجوی تور به سبک استیچ؛ جای عکس خالی با طرح گرافیکی استیچ.
- PR #87 عمداً ادغام نشد: `deploy-production.yml` با ادغام در `production` استقرار خودکار می‌کند و آن شاخه تغییرات مستقرنشده (از جمله مهاجرت دیتابیس) دارد — تصمیم مالک.
- **0009 مستقر (2026-11-18 11:27 UTC):** server HEAD `90bb525`، web healthy. بازبینی چشمی روی سایت زنده در این نوبت انجام نشد (افزونه مرورگر روی karentravel.ir خطا داد)؛ QA محلی: `qa/impl/tours-jalali.png`، `qa/impl/search-results-with-header.png`.

## ۱۴۰۵/۰۸/۲۷ — تلاش فعال‌سازی HTTPS
- اسکریپت `deploy/https-container.sh` (nginx داخل کانتینر، Let's Encrypt webroot، بلوک TLS، ریدایرکت فقط برای دامنه، تمدید خودکار) + `https-container-rollback.sh`.
- اجرا روی سرور: DNS هر دو دامنه به 188.121.123.218 درست است، مسیر ACME محلی 200 است، فایروال آروان 80/443 را برای همه باز دارد؛ اما **Let's Encrypt از خارج به پورت 80 سرور نمی‌رسد** (Timeout during connect) — محدودیت ورودی بین‌المللی. هیچ تغییری در nginx/‎.env اعمال نشد (شکست قبل از مرحله ۴). فقط بسته certbot نصب و حساب LE ثبت شد.
- راه‌های جایگزین: (۱) CDN آروان با SSL رایگان — تغییر NS دامنه در طلاهاست به آروان؛ (۲) چالش DNS (رکورد TXT در طلاهاست، تمدید دستی هر ۹۰ روز)؛ (۳) گواهی خریداری‌شده (طلاهاست/مرجع داخلی) با `CERT_FULLCHAIN`/`CERT_KEY`.

## KARENSEIR CHECKPOINT — HTTPS via ArvanCloud CDN (1405/08/27 · 2026-11-18)

**Status: HTTPS live for users in Iran.** `https://karentravel.ir` and `https://www.karentravel.ir` serve through the Arvan CDN.

What was changed (Arvan panel, domain karentravel.ir):
1. SSL/TLS → origin servers: protocol to origin = **HTTP** (origin nginx has no TLS; edge→origin on port 80).
2. DNS: cloud proxy **ON** for both A records (`@`, `www` → 188.121.123.218).
3. SSL/TLS → edge servers: **HTTPS enabled** with Arvan-managed Let's Encrypt cert (karentravel.ir + *.karentravel.ir, auto-renewed by Arvan).
4. Caching: left at default (with QueryString; Arvan caches static assets only, HTML/API are not cached).

Verification (check-host.net, 8 Iranian nodes Tehran/Qom/Shiraz/Isfahan):
- `https://karentravel.ir/` → 200 on all 8
- `https://www.karentravel.ir/hotels` → 200 on all 8
- `https://karentravel.ir/api/health` → 200 on all 8
- Nodes outside Iran: timeout/504 — **same as before** (the origin was already unreachable from abroad; that is also why Let's Encrypt HTTP-01 on the server failed).

Note: a first attempt showed 504 because the test browser exits outside Iran; the proxy was briefly reverted (~10 min), then re-enabled after the Iranian-node test.

Not done yet (needs server console):
- `.env`: `PUBLIC_WEB_URL=https://karentravel.ir`, add `https://karentravel.ir,https://www.karentravel.ir` to `CORS_ORIGINS`, then `docker compose up -d --no-deps api`. Required before payment returns (VandaPay).
- Then enable **«پیش‌فرض‌شدن HTTPS»** (HTTP→HTTPS redirect) in Arvan edge settings.
- Server console tty is stuck on a `docker compose exec … tail /dev/stdout` (needs one Ctrl+C typed by a human in the Arvan console). Site unaffected.

Rollback: Arvan DNS → turn cloud OFF for `@` and `www` (direct HTTP to origin returns, TTL 2 min). Optionally disable HTTPS on edge.

## KARENSEIR CHECKPOINT — Round 5: flight results to Stitch Desktop/02 (2026-11-18)

User feedback: «طراحی صفحه‌ها عوض نشده». Compared live /search/results (flight) with Stitch 02 rendered locally (Tailwind compiled offline): the summary bar, sort, filters and card did not match.

Changed (production code branch `feat/inner-redesign-on-production` → commit 7f29e33, patch `deploy/patches/0010-flight-results-stitch-card.patch`):
- Summary chip row (route · date · passengers/cabin · trip type) + «تغییر جست‌وجو», replacing the generic hero for flights.
- Date strip moved above results; result count «N پرواز X به Y یافت شد»; sort as pill tabs (پیشنهاد کارن / ارزان‌ترین / سریع‌ترین / بهترین).
- Filters: stops as checkboxes, departure-time tiles (صبح/عصر/شب/بامداد, real client-side filter on `departure_time`), airlines as checkbox list with counts.
- New flight card: badges row, carrier logo tile + big departure/arrival clocks + duration/stops line, price/CTA column, footer (baggage, party, «جزئیات پرواز و قوانین بار»).
- No data invented: unknown values show «—»; prices still only for signed-in users; Mock badge kept.
- Homepage untouched (no homepage files in the diff).

QA: `qa/impl/r5-flight-results-desktop.png`, `r5-flight-results-mobile.png`, reference `r5-stitch-02-reference.png`. `tsc` clean, `next build --webpack` OK.

Deploy: pending — server console is stuck (needs one Ctrl+C by a human), then `REDESIGN deploy` with the new script (0010 applied idempotently). Rollback: `deploy/redesign-2026-11-rollback.sh` or `git revert` of the 0010 commit on the server.

## KARENSEIR CHECKPOINT — Round 5 deployed + HTTPS finalized (2026-11-19)

- Server console unstuck (Ctrl+C sent from the Arvan noVNC page).
- `.env` (backup in `/opt/karenseir/backups/env-<ts>`): `PUBLIC_WEB_URL=https://karentravel.ir`; `CORS_ORIGINS=http://188.121.123.218,https://karentravel.ir,https://www.karentravel.ir`. `api` recreated → healthy.
- Deploy script at 598fc33: 0010 applied (server commit 1f889d5, docs 7fbc23f), web rebuilt → `RESULT: DEPLOY OK`, homepage check `ks-inner on / = 0 (want 0)`, web healthy. Log `/root/rd-0010.log`.
- Arvan: «پیش‌فرض‌شدن HTTPS» ON. Verified from 8 Iranian nodes: `http://karentravel.ir/` → 301; `https://karentravel.ir/search/results?vertical=flight` → 200.
- Rollback: redirect toggle off in Arvan edge settings; `.env` from backup + `docker compose up -d --no-deps api`; web via `deploy/redesign-2026-11-rollback.sh`.
- Remaining external: Eghamat24 credentials, VandaPay gateway specs, OTP test number; international (non-Iran) access to the origin is closed at the network level (Arvan ticket needed if required).

## KARENSEIR CHECKPOINT — VandaPay gateway in code (2026-11-19)

- Source: VandaPay repo `docs/integration-plans/karenseir.md` + `integrations/sdk-python` (API contract, webhook signature).
- Code commit 9052936 on `feat/inner-redesign-on-production`; patch `deploy/patches/0011-vandapay-payment-gateway.patch`; ADR-024.
- Behaviour: disabled by default; with `VANDAPAY_MODE=test|live` + `VANDAPAY_SECRET_KEY` + `VANDAPAY_WEBHOOK_SECRET` the existing checkout starts a VandaPay intent and redirects to its checkout; capture only after server-side GET shows `succeeded` (same amount + order_ref). Return `/api/payments/vandapay/return`, webhook `/api/payments/vandapay/webhook`.
- Tests: 7 new VandaPay tests + existing payment tests (20) green; full backend 593 passed, 2 failures pre-existing on base.
- **Not deployed yet** (backend/api rebuild needed; inert without keys). Deploy together with the first `sk_test_` key.
- Needed from owner/VandaPay: merchant account for Karen Travel (legal entity + SHEBA), `sk_test_` key + webhook secret, decision hosted vs embedded checkout, payment expiry vs supplier hold time.

## KARENSEIR CHECKPOINT — Stitch round 6 to GitHub (2026-11-19)

Owner prompt in Stitch: «عالیه انجام بده هرسه» → 3 new screens (tour ecosystem), exported via Stitch *Code to Clipboard* → GitHub editor, split and verified (byte length identical to clipboard):
- `desktop/15-route-simulator-flight-transfer.html` — شبیه‌ساز سه‌بعدی مسیر پرواز و ترانسفر تور
- `desktop/16-local-experience-host-portal.html` — پورتال تأمین‌کنندگان تجربیات بومی و کارگاه‌ها (درآمد میزبان، مسترکلاس‌ها، ورود کاروان‌ها، کیف پول تسویه آنی)
- `mobile/08-tour-360-showcase-package-builder.html` — شوکیس ۳۶۰ درجه و پکیج‌ساز تور
Gallery (`index.html`) and `SCREENS.md` updated; previews in `qa/round6/`. All numbers in these designs are Mock.
Note: Stitch exports max 10 screens per export; the Stitch canvas holds more screens/variants than the 55 files in GitHub — a full sync (batches of 10, md5 de-dup) is a separate step if wanted.
Next: Figma (same file R3FvzMWcCVLmgKviiY0lav), then implementation decisions (these are new features, not restyles — need backend: 360 media, package builder pricing, host portal/payout via VandaPay).

## KARENSEIR CHECKPOINT — Round 6 implemented (backend + interactive UI) (2026-11-19)

Owner: «اینا رو ببر و بکندش و تعاملی و دکمه‌هاش کار کنه، فعال بشه».
Code (branch `feat/inner-redesign-on-production`): 807cdb8 (backend), a72425d (UI). Deploy patch `deploy/patches/0012-stitch-round6-tours-experiences.patch` (+0011 VandaPay). Deploy script now rebuilds `api`+`worker` when backend patches apply (backup image tags, health wait). **No DB migration**: new data lives in existing JSON fields.

| Stitch screen | Live route | Backend | Interactive |
|---|---|---|---|
| mobile/08 Tour 360 showcase + package builder | `/tours/{id}` (inside tour page) | `details.media_360[]` (+hotspots), `details.narration`, departure `pricing.addons[]` (code/title/price/unit/category, organiser-priced); `/tour-departures/{id}/quote?addons=` and booking `addons[]` re-priced server-side; add-ons stored in booking snapshot `package_addons` | drag/arrow 360 rotation, scene tabs, hotspots, audio narration, add-on checkboxes → re-quote → breakdown → book |
| desktop/15 route simulator | `/tours/{id}/route` | itinerary items may carry `day,time,place,mode,lat,lng,note` (validated in public projection) | play/pause, prev/next stop, scrub, 1×/2×/4×, click stop, timeline |
| desktop/16 host portal | `/supplier/experiences` (supplier nav) | `GET /supplier/experience-portal` — supplier-scoped places/products/ticket types/sessions/arrivals/KPIs counted from stored reservations | add session (existing POST), arrivals today/tomorrow, capacity bars, payout state (VandaPay not configured → explicit unavailable) |

Rules kept: no price/media invented (empty states when organiser has not supplied data); anonymous users see add-on titles without prices; homepage untouched.
Tests: `backend/tests/test_stitch_round6_backend.py` (3) + full suite 596 passed (2 pre-existing failures unrelated). UI QA screenshots `qa/impl/r6-*.png` (mock data, labelled Mock).
Next: owner/organisers enter real add-ons, 360 images and stop coordinates for tours; Figma frames for the three screens.

- 2026-11-19 20:52 UTC: owner asked to merge — PR #90 merged into `main` as 4d62042 (CI quality running). Live after the next `main` deploy. Stitch 10-min sync stopped at owner request.
