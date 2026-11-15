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
