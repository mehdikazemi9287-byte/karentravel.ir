<div dir="rtl">

# وضعیت پیاده‌سازی (PR #6)

محیط: **فقط کد منبع (Source)**. هیچ تغییری در production و هیچ استقراری انجام نشده است.
شاخه: `feature/sales-desk-revenue-safarsaz-app` ← `production`

| # | قابلیت | بک‌اند | جدول‌ها (RLS) | صفحه | آزمون |
| --- | --- | --- | --- | --- | --- |
| ۱ | میز گفتگو و فروش | `backend/app/sales_desk.py` | `sales_desk_cases`، `sales_desk_activities`، `sales_desk_agents`، `sales_desk_settings` (مهاجرت `20261102_53`) | `/admin/sales-desk` | `tests/test_sales_desk.py` |
| ۲ | سود/کمیسیون هر رزرو به‌عنوان درآمد | `backend/app/markup_revenue.py` + فراخوانی در ثبت رزرو | `commerce_applied_markups` (مهاجرت `20261102_54`) | `/finance/markup-revenue` | `tests/test_markup_revenue.py` |
| ۳ | سفرساز | `backend/app/safarsaz.py` | `safarsaz_tours`، `safarsaz_departures` (مهاجرت `20261102_55`) | `/admin/safarsaz` | `tests/test_safarsaz.py` |
| ۴ | اپ مشتری (PWA) | از APIهای موجود `/me/*` | — | `/app`، `/app/trips`، `/app/wallet`، `/app/account` | — |

## رفتارهای کلیدی

- **میز فروش:** ۱۳ کانال، ۸ مرحله با انتقال مجاز (لغو با دلیل، بازگشایی به «جدید»)، ارجاع نوبتی بین کارشناس‌های حاضر، مسئول شکایت، مهلت پاسخ و انتقال خودکار، پیش‌فاکتور با مهلت و متن پیام از قالب، اتصال به رزرو واقعی همان مستأجر، شاخص‌های امروز و هدف ماهانه.
- **درآمد:** هر رزروی که قانون فروش رویش اعمال شده، خالص/فروش/تعدیل/قانون را به تفکیک خدمت نگه می‌دارد و یک سند `revenue` با کلید یکتای `markup:<رزرو>` در دفتر صندوق می‌خورد (سود = بستانکار، تخفیف = بدهکار). همان مشکل «کمیسیون صفر» چک‌لاین.
- **سفرساز:** پنج منبع مجاز، هتل و نوع سرویس، برنامه‌ی روزانه، مدارک، پلکان کنسلی، بیعانه، حرکت‌ها با نرخ نوع اتاق × نوع مسافر، چک‌لیست ۹ موردی؛ انتشار به `tour_products` / `tour_departures` موجود (دوتخته = پایه، بقیه = اختلاف نرخ) تا رزرو و پرداخت از مسیر آزموده‌ی فعلی برود. تور بدون حرکت باز به پیش‌نویس برمی‌گردد.
- **اپ مشتری:** manifest نصب‌شدنی، نوار پایین مطابق فیگما؛ سطح حلقه‌ی همسفران و کد معرف چون در بک‌اند نیستند «در دسترس نیست» نمایش داده می‌شوند.

## افزوده‌ها

- **برگشت سند درآمد:** با لغو، شکست، انقضا یا استرداد رزرو، سند معکوس خودکار ثبت می‌شود (کلید مشترک با برگشت دستی، پس دوبار نمی‌خورد) و گزارش، رزروهای برگشت‌خورده را جدا نشان می‌دهد.
- **فرم «درخواست سفر» در `/contact`:** پرونده‌ی `web_form` در میز فروش می‌سازد. برای فعال شدن باید متغیر `SALES_DESK_PUBLIC_TENANT` روی سرور برابر نامک مستأجر گیرنده تنظیم شود؛ تا آن موقع بسته است.

## دور سوم

| قابلیت | بک‌اند | جدول‌ها (RLS) | صفحه | آزمون |
| --- | --- | --- | --- | --- |
| حلقه‌ی همسفران | `backend/app/loyalty.py` | `loyalty_settings`، `loyalty_accounts`، `loyalty_entries` (`20261102_56`) | `/admin/loyalty`، `/app/account` | `tests/test_loyalty.py` |
| کمپین پیامکی | `backend/app/sms_campaigns.py` | `sms_campaigns`، `sms_campaign_recipients`، `sms_opt_outs` (`20261102_57`) | `/admin/sms-campaigns` | `tests/test_sms_campaigns.py` |
| ورود اکسل و خروجی فرانگر | `backend/app/data_exchange.py`، `backend/app/tabular.py` | `accounting_code_map` (`20261102_58`) | زبانه‌ی «ورود اکسل» در میز فروش، `/finance/journal-export` | `tests/test_data_exchange.py` |
| ورودی واتس‌اپ/بله/سانترال | در `sales_desk.py` | — | — | `tests/test_sales_desk.py` |
| نرخ کودک/نوزاد تور | `main.py` (استعلام و رزرو تور) | — | — | `tests/test_safarsaz.py` |
| حالت آفلاین اپ | `public/sw.js`، `public/offline.html` | — | `/app` | — |

متغیرهای محیطی لازم برای روشن شدن ورودی‌ها: `SALES_DESK_PUBLIC_TENANT`، `SALES_DESK_WHATSAPP_APP_SECRET`، `SALES_DESK_WHATSAPP_VERIFY_TOKEN`، `SALES_DESK_BALE_WEBHOOK_TOKEN`، `SALES_DESK_PBX_SECRET`.

## محدودیت‌های فعلی

- فرم رزرو تور در سایت هنوز فیلد کودک/نوزاد ندارد (API دارد).
- کمپین پیامکی تا اتصال سرویس پیامک چیزی نمی‌فرستد.
- خروجی فرانگر قالب عمومی سند است و باید با نمونه‌ی قالب ورود فرانگر منطبق شود.

</div>
