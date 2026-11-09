# QA فاز ۱ پنل‌ها — حلقهٔ لغو و استرداد (۱۸ آبان ۱۴۰۵)

محیط: **Source** (شاخهٔ `feat/panels-phase1` روی `production`). روی Production دیپلوی **نشده** است؛ migration `20261109_71` هم فقط روی PostgreSQL محلی آزمایشی اجرا شده است.

## چه ساخته شد
- **Backend** `backend/app/after_sales.py`: یک state machine برای درخواست خدمت (`submitted → under_review → waiting_supplier / needs_customer → approved → refund_queued → refund_paid → closed`؛ `rejected`، `withdrawn`) و یکی برای پرداخت استرداد (`pending_finance → awaiting_approval → succeeded`؛ `decline`، `return`). مشتری فقط درخواست می‌دهد (C-1).
- **دو نفره بودن پرداخت:** نفر اول مالی آماده می‌کند، نفر دوم (کاربر دیگر) تأیید می‌کند؛ سرور سازنده را از تأیید منع می‌کند (403). هر POST پولی `Idempotency-Key` دارد و کلید به hash درخواست بسته است.
- **دفتر:** اعتبار کیف پول با `apply_credit_command` (یک بار، `refund-pay:<id>`)، سند دوسطری متوازن `refund_journal_lines`، و سند «برگشت از فروش» در وضعیت `PENDING` با برگشت ارزش افزودهٔ کمیسیون/markup/کارمزد خدمات از روی `PriceBreakdown` (مثال E2E-C: کمیسیون برگشتی ۸۴۰٬۰۰۰، VAT برگشتی ۸۴٬۰۰۰ ریال). بدون تفکیک قیمت، سند با `basis=unavailable` ساخته می‌شود و عددی حدس زده نمی‌شود. چیزی به مودیان ارسال نمی‌شود.
- **تطبیق درگاه:** اتصال/برداشتن اتصال مغایرت به پرداخت یا رزرو و حل با نوع و دلیل؛ همه در `audit_trail` و `audit_events`.
- **Frontend** (`components/panel/aftersales/*`): C-01، C-02، C-03، C-03a (۳ گام، پیش‌نمایش جریمه از سرور)، C-04، C-04a، C-06؛ OPS-02، OPS-03 (dialogهای تأیید/رد/پرسش)؛ FIN-02، FIN-02a (ConfirmMoney با مبلغ به حروف)، FIN-04. متن بدنه ۱۶px، هدف لمسی ۴۴px، رنگ دکمهٔ اصلی `#c9462a`.

## شواهد اجرا
| بررسی | نتیجه |
|---|---|
| `pytest tests/test_after_sales.py` | ۱۳۸ مورد سبز (state machine همهٔ اقدام‌ها × همهٔ وضعیت‌ها، مجوزها، دو نفره، idempotency، جداسازی tenant، ریاضی پول، تطبیق) |
| کل backend | ۲ شکست که روی `production` بدون این تغییرات هم شکست می‌خورند (`test_booking_financial_journey`، `test_final_internal_domains`)؛ بقیه سبز |
| migration روی PostgreSQL 16 محلی | `upgrade head` تا `20261109_71` موفق؛ RLS و FORCE RLS روی هر ۶ جدول فعال؛ جدول رویدادها و سند فقط `SELECT, INSERT` |
| `tsc --noEmit`، `next build`، eslint فایل‌های تغییرکرده | بدون خطا |
| `node tests/unit/panel-access.cjs` | سبز (منوی ops/finance جدا، guard صفحه‌های جزئیات) |
| Playwright `e2e/panels/refund-loop.spec.ts` (درگاه sandbox، `ENVIRONMENT=development`) | سبز: رزرو واقعی → پرداخت sandbox → wizard لغو → تأیید عملیات → نفر اول مالی → نفر دوم → مشتری «پرداخت‌شده» و واریز کیف پول را می‌بیند؛ ۳۹۰px بدون اسکرول افقی |

اسکرین‌شات‌ها در `screens/` (داده‌ها حساب‌های نمونهٔ محیط توسعه‌اند، نه دادهٔ واقعی).

## باقی‌مانده (خارج از این دور)
- `GET /panel/today` و `/me/capabilities`، ناحیه‌های جدای `ops`/`finance` در پوسته، nav-registry با bottom nav موبایل، جست‌وجوی سراسری.
- `propose_change` و `customer-decision` برای تفاوت قیمت تغییر؛ فهرست «پرداخت‌های ناموفق»؛ دستهٔ پرداخت بانکی (FIN-02b)؛ ورود فایل تسویهٔ درگاه؛ برگشت خودکار به کارت (درگاه پشتیبانی نمی‌کند).
- جدول نرخ مالیات تاریخ‌دار (FIN-11)؛ نرخ ۱۰٪ فعلاً ثابت با برچسب منبع.
- SLAها پیش‌فرض‌اند (ساعت) و هنوز قابل تنظیم توسط مالک نیستند.
- axe خودکار و تست نقش‌محور همهٔ ۱۱ نقش.
