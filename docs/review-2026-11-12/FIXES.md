# اصلاحات بازبینی ۱۲ نوامبر ۲۰۲۶ — کارن‌تراول (KarenSeir)

> قبل از کار روی واچر/دفترکل/صف تأمین‌کننده این فایل را بخوانید تا کار تکراری انجام نشود.

- شاخه: `fix/review-2026-11-12` از **`production` @ `a4d37be`** (نه main). merge/استقرار **نشده**؛ سرور دست نخورده.
- SUPERVISOR GATE: ALLOW — تغییر کد محدود و برگشت‌پذیر روی شاخه جدا؛ بدون migration، بدون production write، بدون تغییر هویت بصری.
- **KT-4:** ادغام کامل `fix/audit-urgent-2026-11-10` امتحان شد و **کنار گذاشته شد**: تعارض طراحی در `main.py` (price-breakdown، شارژ کیف پول — production مسیر maker-checker عمومی دارد و fix آستانه جدا)، `deploy/karenseir-deploy-server.sh` (MIGRATION_DATABASE_URL در برابر سرویس migrate + guard) و `next.config.mjs` (CSP nonce در production). به‌جای آن فقط KT-1/2/3 مستقیم روی production بازپیاده شد. **شاخه fix را کامل ادغام نکنید.**
- آزمون: کل suite بک‌اند (SQLite) **842 passed، 7 skipped** + `tests/test_review_2026_11_12.py` (۲ آزمون تازه). PostgreSQL/RLS اجرا نشد.

## انجام‌شده

| کد | مشکل | اصلاح | فایل‌ها |
|---|---|---|---|
| KT-1 | صدور مجدد واچر بدون کنترل ارتباط تأمین‌کننده | همان کنترل `_may_fulfil` مسیر fulfill، **پیش از** خواندن پاسخ تکراری؛ نامرتبط → ۴۰۳ و هیچ سند/نسخه‌ای عوض نمی‌شود؛ همان `command_id` با سند/رزرو دیگر → ۴۰۹ (قبلاً پاسخ موفق بی‌ربط). | `backend/app/main.py` (`reissue_voucher`) |
| KT-2 | کلید تکراری دفترکل با ورودی متفاوت | `post_ledger`: replay فقط وقتی همه فیلدهای مؤثر (کیف/حساب اعتبار، نوع، مبلغ، رزرو، reversal) یکی باشد؛ وگرنه `LedgerCommandConflict` (زیرکلاس ValueError → ۴۰۹ در handlerهای موجود). حلقه تسویه رزرو این حالت را log و رد می‌کند (هرگز هر دو capture و release). | `backend/app/operations.py` |
| KT-3 | LIMIT پیش از فیلتر تأمین‌کننده در صف صدور | فیلتر supplier و `manual_supplier` در SQL پیش از LIMIT؛ ترتیب پایدار؛ `limit` (≤۵۰۰) و `offset`؛ بسته چندقلمی یک‌بار. | `backend/app/main.py` (`/supplier/reservations/ready`) |

## مانده

- KT-3 UI: دکمه «ادامه» صف تأمین‌کننده هنوز به `offset` وصل نیست؛ آزمون خودکار ۲۰۰+ سفارش نامرتبط نوشته نشد.
- KT-4: نگاشت migrationهای شاخه fix (کنترل نقش DB، guard) به production — تصمیم معماری؛ فعلاً production مسیر خودش را دارد.
- KT-5: جریان مالی قبول تغییر قیمت (پرداخت مابه‌التفاوت / استرداد) — طراحی جدا.
- آزمون روی PostgreSQL با RLS و نقش کم‌دسترسی API.
