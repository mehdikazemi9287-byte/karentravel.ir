# اتصال ونداپی («پرداخت با ونداپی») — KarenSeir

> وضعیت: ساخته و آزمون‌شده با MOCK؛ **خاموش** (D15). پرداخت واقعی فقط پس از قرارداد PSP و نظر حقوقی. تصمیم معماری: [ADR-024](../adr/ADR-024-vandapay-payment-gateway.md) + [ADR-029](../adr/ADR-029-federated-org-credit-and-vandapay-hardening.md) (پیاده‌سازی واحد) + [ADR-021](../adr/ADR-021-vandapay-payment-provider.md).

## نوع اتصال
API سمت سرور (redirect به صفحهٔ پرداخت میزبانی‌شدهٔ ونداپی). وقتی `VANDAPAY_MODE` روشن و کامل باشد، ونداپی درگاه `POST /payments/{id}/initiate` است (ADR-024)؛ `PAYMENT_PROVIDER=sandbox` در QA/staging مقدم است.

## جریان
1. Checkout تا مرحلهٔ `awaiting_payment` ← Payment Intent با مبلغ backend.
2. صفحهٔ Checkout از `GET /payments/methods` می‌پرسد؛ فقط وقتی ونداپی روشن باشد دکمهٔ «پرداخت با ونداپی» (و در کلید آزمایشی، برچسب «حالت آزمایشی») دیده می‌شود.
3. `POST /payments/{id}/initiate` ← `POST /payment_intents` ونداپی با `Idempotency-Key` قطعی ← هدایت به `checkout_url`.
4. بازگشت: `GET /payments/vandapay/return?state=…` ← بازخوانی intent از API ← «پرداخت شد» / «ناموفق» / «در حال بررسی».
5. وب‌هوک: `POST /payments/vandapay/webhook` (سرآیند `VandaPay-Signature`) — منبع نهایی حقیقت.

## پیکربندی (فقط env؛ هرگز در کد یا git)
| متغیر | توضیح |
| --- | --- |
| `VANDAPAY_MODE` | `disabled` (پیش‌فرض) / `test` / `live`؛ باید با پیشوند کلید بخواند |
| `VANDAPAY_BASE_URL` | آدرس https سرور ونداپی (مثلاً `https://<دامنهٔ ونداپی>/api/v1`)؛ الزامی |
| `VANDAPAY_SECRET_KEY` | `sk_test_…` یا `sk_live_…` (یا `VANDAPAY_SECRET_KEY_FILE`) |
| `VANDAPAY_WEBHOOK_SECRET` | رمز امضای وب‌هوک از پنل پذیرنده (یا `*_FILE`) |
| `VANDAPAY_INTENT_EXPIRES_IN_SECONDS` | اختیاری (VP-01)؛ خالی = TTL پیش‌فرض ونداپی |
| `VANDAPAY_FEDERATED_CREDIT_ORGANIZATION_IDS` | اختیاری؛ سازمان‌هایی که اعتبارشان در دفتر ونداپی است (ADR-029) |
| `VANDAPAY_RETURN_URL` | آدرس https عمومی `/payments/vandapay/return` |

آدرس وب‌هوک برای ثبت در پنل پذیرندهٔ ونداپی: `https://<api-domain>/payments/vandapay/webhook`.

## آزمون
`cd backend && pytest tests/test_vandapay.py tests/test_vandapay_hardening.py` — ۳۱ آزمون با MOCK (پیکربندی fail-closed، بردارهای امضا، یک route بازگشت و یک وب‌هوک، idempotency، استرداد، لغو intent، late capture، تأیید سازمان، اعتبار فدرال). استرداد مالی: `POST /refunds/{id}/review` سپس `POST /refunds/{id}/execute`.

## باقی‌مانده (پیش از روشن کردن)
- قرارداد PSP و نظر حقوقی (D15)؛ استقرار سرور/دامنهٔ ونداپی؛ پذیرش KarenSeir/تاژبان به‌عنوان پذیرنده و کلید `sk_test_`.
- آزمون سرتاسری با sandbox واقعی ونداپی (استرداد/لغو/تأیید سازمان فقط با MOCK آزموده شده‌اند — ADR-022).
- ادغام VP-01 (`expires_in_seconds`) در ونداپی؛ تا آن زمان `VANDAPAY_INTENT_EXPIRES_IN_SECONDS` را خالی بگذارید.
- K8 (`reverse_capture` اعتبار داخلی در استرداد پس از صدور)؛ منبع موبایل تأییدشده برای `customer_phone`.
- تصمیم مالک دربارهٔ redirect به صفحهٔ ونداپی یا پرداخت جاسازی‌شده (`docs/integration-plans/karenseir.md` در مخزن ونداپی).
