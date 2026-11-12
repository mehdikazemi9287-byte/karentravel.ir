# ADR-021 — VandaPay («پرداخت با ونداپی») as an additional fail-closed payment provider

وضعیت: پذیرفته‌شده برای پیاده‌سازی مستقل از credential — ۱۴۰۵/۰۸/۲۱ (۲۰۲۶-۱۱-۱۲)

## زمینه
تصمیم‌های مالک در مخزن ونداپی (`docs/DECISIONS.md`): D13 — ونداپی یکی از درگاه‌های همهٔ سایت‌های گروه؛ D14 — ونداپی سرور و دامنهٔ خودش را دارد (آدرس API فقط پیکربندی است)؛ D15 — اتصال‌ها اکنون ساخته و آزمون می‌شوند ولی تا قرارداد PSP و نظر حقوقی **خاموش** می‌مانند.
ونداپی شرکت ثالث از دید KarenSeir است (پذیرنده = KarenSeir)؛ هیچ کد، DB یا UI از 60Online یا مخزن ونداپی import نمی‌شود — فقط قرارداد HTTP عمومی آن.

## تصمیم
- ماژول مستقل `backend/app/vandapay.py` (فقط کتابخانهٔ استاندارد) + چهار endpoint در `main.py`؛ مسیر ZarinPal و `ADAPTERS["payment"]` دست نخورده‌اند.
- پرچم `VANDAPAY_ENABLED` پیش‌فرض خاموش؛ روشن شدن فقط با `VANDAPAY_API_BASE` (https) + `VANDAPAY_SECRET_KEY` + `VANDAPAY_WEBHOOK_SECRET` + `VANDAPAY_RETURN_URL` (https). در غیر این صورت `/payments/methods` آن را فهرست نمی‌کند و همهٔ endpointهای آن 404 می‌دهند.
- `sk_live_` فقط در `ENVIRONMENT=production`؛ `sk_test_` در production فقط با `DEMO_MODE` و همیشه با برچسب «حالت آزمایشی».
- مبلغ فقط از Payment Intent موجود (pricing snapshot رزرو، ریال) — کلاینت مبلغ نمی‌فرستد. `Idempotency-Key` قطعی `karenseir-{tenant}-{intent}-attempt-{n}`.
- بازگشت مرورگر فقط state امضاشده (JWT، aud `karenseir-vandapay-return`) را می‌پذیرد؛ پارامترهای دیگر مثل `status` نادیده گرفته می‌شوند.
- وب‌هوک: HMAC-SHA256 روی بدنهٔ خام، تحمل ۳۰۰ ثانیه، چند `v1`؛ سپس intent از API ونداپی بازخوانی و tenant/intent از metadata **پاسخ API** (نه رویداد) خوانده می‌شود؛ حذف تکراری با `payment_events(provider_key='vandapay', provider_event_id='evt:…')`.
- Capture فقط وقتی: status=`succeeded` + مبلغ دقیق ریالی + `IRR` + mode کلید + metadata ما + بدون استرداد. `unknown`/`processing`/هر وضعیت ناشناخته = «در حال بررسی»، هیچ تغییری. رویداد `succeeded` که API هنوز تأیید نکرده ⇒ 503 تا ونداپی دوباره بفرستد.
- رویدادهای استرداد فقط ثبت و برای بررسی دستی لاگ می‌شوند (استرداد خودکار در این فاز نیست).
- بدون migration: از ستون‌های موجود `provider_key`، `provider_authority`، `provider_capture_reference` استفاده می‌شود.

## پذیرش
`backend/tests/test_vandapay.py` (MOCK برچسب‌خورده): پرچم خاموش، پیکربندی ناقص/ناامن، بردارهای مشترک امضا، idempotency، cross-tenant، خطای موقت، unknown/pending، capture یک‌باره، عدم تطابق مبلغ/ارز/mode/metadata/استرداد، state جعلی، امضای غلط/کهنه، تکرار رویداد.

## Rollback
`VANDAPAY_ENABLED=0` (فوری، بدون deploy کد) یا revert کامیت؛ هیچ migration/داده‌ای برای برگرداندن نیست.
