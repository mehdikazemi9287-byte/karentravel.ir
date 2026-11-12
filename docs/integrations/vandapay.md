# اتصال ونداپی («پرداخت با ونداپی») — KarenSeir

> وضعیت: ساخته و آزمون‌شده با MOCK؛ **خاموش** (D15). پرداخت واقعی فقط پس از قرارداد PSP و نظر حقوقی. تصمیم معماری: [ADR-021](../adr/ADR-021-vandapay-payment-provider.md).

## نوع اتصال
API سمت سرور (redirect به صفحهٔ پرداخت میزبانی‌شدهٔ ونداپی). ونداپی یک روش پرداخت **اضافه** کنار ZarinPal است.

## جریان
1. Checkout تا مرحلهٔ `awaiting_payment` ← Payment Intent با مبلغ backend.
2. صفحهٔ Checkout از `GET /payments/methods` می‌پرسد؛ فقط وقتی ونداپی روشن باشد دکمهٔ «پرداخت با ونداپی» (و در کلید آزمایشی، برچسب «حالت آزمایشی») دیده می‌شود.
3. `POST /payments/{id}/vandapay/initiate` ← `POST /payment_intents` ونداپی با `Idempotency-Key` ← هدایت به `checkout_url`.
4. بازگشت: `GET /payments/vandapay/return?state=…` ← بازخوانی intent از API ← «پرداخت شد» / «ناموفق» / «در حال بررسی».
5. وب‌هوک: `POST /payments/vandapay/webhook` (سرآیند `VandaPay-Signature`) — منبع نهایی حقیقت.

## پیکربندی (فقط env؛ هرگز در کد یا git)
| متغیر | توضیح |
| --- | --- |
| `VANDAPAY_ENABLED` | `1` برای روشن کردن؛ پیش‌فرض خاموش |
| `VANDAPAY_API_BASE` | آدرس https سرور ونداپی (مثلاً `https://<دامنهٔ ونداپی>/api/v1`) |
| `VANDAPAY_SECRET_KEY` | `sk_test_…` یا `sk_live_…` |
| `VANDAPAY_WEBHOOK_SECRET` | رمز امضای وب‌هوک از پنل پذیرنده |
| `VANDAPAY_RETURN_URL` | آدرس https عمومی `/payments/vandapay/return` |

آدرس وب‌هوک برای ثبت در پنل پذیرندهٔ ونداپی: `https://<api-domain>/payments/vandapay/webhook`.

## آزمون
`cd backend && pytest tests/test_vandapay.py` — ۱۵ آزمون با MOCK؛ کل مجموعه: ۲۲۶ موفق، ۶ skip، ۳ شکست قدیمی و نامرتبط در `test_outbox_worker.py` (پیش از این تغییر هم بود).

## باقی‌مانده (پیش از روشن کردن)
- قرارداد PSP و نظر حقوقی (D15)؛ استقرار سرور/دامنهٔ ونداپی؛ پذیرش KarenSeir/تاژبان به‌عنوان پذیرنده و کلید `sk_test_`.
- آزمون سرتاسری با sandbox واقعی ونداپی؛ استرداد خودکار از طریق ونداپی (فعلاً رویداد استرداد فقط ثبت و بررسی دستی).
- تصمیم مالک دربارهٔ redirect به صفحهٔ ونداپی یا پرداخت جاسازی‌شده (`docs/integration-plans/karenseir.md` در مخزن ونداپی).
