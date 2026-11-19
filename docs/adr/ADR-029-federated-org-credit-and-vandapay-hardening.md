# ADR-029 (در شاخهٔ قدیمی: ADR-022) — اعتبار سازمانی فدرال (یک دفتر مالک برای هر برنامهٔ اعتبار) و سخت‌سازی اتصال ونداپی

وضعیت: پذیرفته‌شده — ۱۴۰۵/۰۸/۲۷ (۲۰۲۶-۱۱-۱۸). تکمیل‌کنندهٔ ADR-021 (جایگزین آن نیست).


## Port to main — 2026-11-19 (one VandaPay implementation)
Status: **ported onto `main`** (PR "VandaPay: one implementation"). Supersedes the simpler PR #87 code path described in
[ADR-024](ADR-024-vandapay-payment-gateway.md); main keeps exactly **one** VandaPay implementation:

- Code: `backend/app/vandapay.py` (client, `Idempotency-Key`, HMAC webhook verification with the shared vectors in
  `backend/tests/fixtures/vandapay_webhook_vectors.json`, intent evaluation) + the VandaPay block in `backend/app/main.py`
  (initiate, settle, refunds, late capture, org approval, hold-release cancel sweep) + `operations.request_external_payment_void`
  + the outbox-worker sweep. `providers.VandaPayAdapter` is only a health shell for the `ADAPTERS["payment"]` slot so a
  misconfigured VandaPay fails closed (503) instead of falling back to ZarinPal; it never moves money.
- Routes: initiation is the single generic `POST /payments/{id}/initiate` (the old `/payments/{id}/vandapay/initiate` is
  **not** ported); exactly one `GET /payments/vandapay/return` and one `POST /payments/vandapay/webhook`; `GET /payments/methods`
  (label / test-mode label); `POST /payments/{id}/verify` re-reads VandaPay server-side.
- Configuration adapted to main (ADR-024 names): `VANDAPAY_MODE=disabled|test|live` (default **disabled**; replaces
  `VANDAPAY_ENABLED`), `VANDAPAY_BASE_URL` (replaces `VANDAPAY_API_BASE`; required, no hard-coded default),
  `VANDAPAY_SECRET_KEY` / `VANDAPAY_WEBHOOK_SECRET` via `read_secret` (`*_FILE` supported), `VANDAPAY_RETURN_URL` (https).
  Key prefix must match the mode; `sk_live_` only in production; `sk_test_` in production only with `DEMO_MODE`.
  `PAYMENT_PROVIDER=sandbox` (QA/staging gateway) takes precedence. `VANDAPAY_CATEGORY` is gone (explicit category map).
- Return state: main's per-purpose key (`_signing_key("payment_state")` / `_decode_payment_state`), aud
  `karenseir-vandapay-callback`, claims include `amount` (must equal the intent). Browsers are redirected to `/payments/{id}`.
- Capture also posts to the commerce treasury (`commerce.record_payment`) like every other gateway capture on main.
- Item 1 (exclusive funding source) and item 2 (credit-only issuance) are enforced on main by the newer funding plan
  (`funding_references.bank_payable` in `/payments/{id}/initiate`, `fully_funded_without_bank` in
  `_reservation_settlement_ready`); the old `_internal_ledger_funding` guard and the `reservation.funded_by_internal_ledger`
  event were not ported. `metadata.internal_funding_amount` is still sent (information only).
- Item 3 (refunds) uses main's refund review: a customer request is `requested` only with a verified policy quote on a
  cancellation-state reservation, else `pending_review`. The VandaPay refund runs automatically only when the reservation is
  `cancelled`; otherwise finance approves with `POST /refunds/{id}/review` and executes with **`POST /refunds/{id}/execute`**
  (`refund:manage`). (`/finance/refunds/{id}/execute` on main belongs to the after-sales maker-checker, whose `gateway`
  method stays refused — wiring VandaPay into that flow is open work.) `processing` and `manual_review` count against the
  refundable remainder (`REFUND_SETTLED_STATUSES`).
- No migration (status columns are free-text; `organization_credit_ledger` already exists as `20260823_19`).
- Rollback: `VANDAPAY_MODE=disabled` (all VandaPay routes 404, sweep no-op) or revert the commit.

## زمینه
ممیزی گروهی درگاه (`gw-audit/10-tourism.md` ردیف‌های K1–K8 و `VERIFICATION.md` §ب ردیف‌های 35–40، روی `f6af234`) این کمبودها را در کد تأیید کرد:
استرداد ونداپی وصل نبود و `refund.*` فقط لاگ می‌شد (K1)؛ intent باز ونداپی پس از آزاد شدن hold لغو نمی‌شد (K2)؛ `requires_org_approval` رسیدگی صریح نداشت (K3)؛ `customer_phone`، دستهٔ هر محصول و اقلام فرستاده نمی‌شد (K4/K5)؛ خطر خرج یک اعتبار در دو دفتر (K6)؛ رزرو کاملاً اعتباری صادر نمی‌شد و `fulfill` خطای 409 می‌داد (K7).

## تصمیم مالک (۲۰۲۶-۱۱-۱۸) — مدل فدرال اعتبار
- کارن‌سیر می‌تواند **اعتبار سازمانی خودش** را مستقل صادر کند (قرارداد و دفتر خودش: `CreditAccount` + `financial_ledger_entries`) و **اختیاری** آن را به ونداپی وصل کند.
- برای هر **برنامهٔ اعتبار** دقیقاً **یک دفتر مالک** وجود دارد: یا دفتر کارن‌سیر یا دفتر ونداپی. یک اعتبار هرگز در دو دفتر خرج نمی‌شود.
- پیاده‌سازی موقت بدون migration: `VANDAPAY_FEDERATED_CREDIT_ORGANIZATION_IDS` (شناسهٔ سازمان‌هایی که دفتر مالکشان ونداپی است). برای این سازمان‌ها مرحلهٔ `funding` رزرو اعتبار داخلی را با 409 رد می‌کند؛ اعتبارشان فقط در صفحهٔ پرداخت ونداپی خرج می‌شود. پیش‌فرض خالی = همهٔ اعتبارهای داخلی مالِ دفتر کارن‌سیرند. وقتی اتصال واقعی شد، این به ستون `credit_accounts.owning_ledger` (migration جدا با gate) منتقل می‌شود.

## تصمیم‌های فنی (همه پشت `VANDAPAY_MODE`، پیش‌فرض `disabled`)
1. **انتخاب انحصاری منبع پرداخت:** `initiate` ونداپی فقط وقتی مجاز است که `مبلغ intent + مانده‌ٔ متعهد کیف/اعتبار داخلی برای همین رزرو == مبلغ کل رزرو`؛ وگرنه 409 و هیچ فراخوانی به ونداپی. یعنی ونداپی فقط بخشی را می‌گیرد که در دفتر کارن‌سیر نیست. `metadata.internal_funding_amount` برای تطبیق فرستاده می‌شود. رزرو آزادشده (cancelled/failed/expired) قابل پرداخت نیست.
2. **رزرو کاملاً اعتباری (K7):** `fulfill` بدون capture کارت فقط وقتی مجاز است که (الف) checkout سرور `payable_amount=0` ثبت کرده و در `awaiting_fulfillment` است، (ب) خالص رزرو دفتر داخلی برای رزرو دقیقاً برابر مبلغ کل است، (ج) هیچ PaymentIntent غیرناموفقی (ونداپی یا دیگر) برای آن رزرو نیست. رویداد `reservation.funded_by_internal_ledger` با تفکیک کیف/اعتبار ثبت می‌شود (ممیزی). capture اعتبار همان مسیر موجود `settle_reservation_funding` است.
3. **استرداد (K1):** کلاینت `refund()` با `Idempotency-Key = karenseir-{tenant}-refund-{refund_id}` (ثابت در هر تلاش ⇒ تکرار پس از timeout دو بار پول برنمی‌گرداند).
   - **اصلاح دستور بالادستی (supervisor):** `POST /payments/{id}/refunds` را مشتری صدا می‌زند؛ اجرای مستقیم استرداد از آن یعنی مشتری می‌تواند بدون لغو تأمین‌کننده پولش را پس بگیرد. پس اجرای خودکار **فقط** وقتی است که رزرو `cancelled` (لغو نهایی تأمین‌کننده) باشد و مجموع استرداد ≤ `refundable_amount` سیاست امضاشدهٔ لحظهٔ رزرو. در غیر این صورت رکورد `requested` می‌ماند و مالی با `POST /refunds/{id}/review` و سپس `POST /refunds/{id}/execute` (مجوز `refund:manage`؛ نسخهٔ main) اجرا می‌کند.
   - وضعیت‌ها: `requested` (ثبت، بدون مجوز) ← `processing` (مجاز؛ پیش از هر حرکت پول commit می‌شود) ← `succeeded` | `failed` | `manual_review`. `requested/processing/manual_review` همه از ماندهٔ قابل استرداد کم می‌شوند.
   - `201 succeeded` ⇒ ثبت فوری. `202 pending` ⇒ `provider_reference` ذخیره و منتظر وب‌هوک. `422 partial_refund_unsupported`/`split_refund_manual_review` ⇒ `manual_review` + رویداد outbox برای انتقال بانکی دستی. خطای موقت ⇒ `processing` می‌ماند و sweep یا تکرار همان `command_id` با همان کلید دوباره می‌فرستد.
   - وب‌هوک `refund.*`: intent از API بازخوانی و وضعیت استرداد از فهرست `refunds` **پاسخ API** خوانده می‌شود (نه رویداد). `refund.succeeded` که API هنوز تأیید نکرده ⇒ 503. استردادی که بیرون از کارن‌سیر (پنل ونداپی) انجام شده و API تأییدش می‌کند ثبت می‌شود (پول واقعاً برگشته). سقف: `refunded ≤ captured` وگرنه `manual_review`.
4. **لغو intent هنگام آزاد شدن hold (K2):** گذار رزرو به `cancelled/failed/expired` (تنها نقطهٔ مشترک `transition_reservation`) intentهای ونداپی `initiated` را `cancel_pending` + outbox می‌کند (بدون شبکه در `operations.py`). `vandapay_sweep` در حلقهٔ outbox worker، tenant به tenant با `set_tenant_context`، `POST …/cancel` را با کلید ثابت می‌فرستد و وضعیت را از API بازخوانی می‌کند. اگر ونداپی دیگر قابل لغو نبود و پول گرفته شده بود ⇒ **late capture**: capture ثبت می‌شود (پول واقعاً جابه‌جا شده)، رزرو **صادر نمی‌شود** و استرداد کامل خودکار ساخته و اجرا می‌شود.
5. **`requires_org_approval` (K3) — سیاست صریح:** همیشه «در انتظار» است، هرگز پرداخت‌شده؛ PaymentIntent در `initiated` می‌ماند؛ یک رویداد Timeline «در انتظار تأیید سازمان (حداکثر ۴۸ ساعت)» (idempotent) ثبت و بازگشت مرورگر `payment_status=pending_org_approval` نشان می‌دهد. کارن‌سیر hold تأمین‌کننده را نه تمدید می‌کند نه به‌خاطر این وضعیت آزاد می‌کند؛ تا تأیید، `fulfill` 409 است. اگر hold تأمین‌کننده زودتر تمام شود (رزرو expired/cancelled) ⇒ intent لغو می‌شود (ونداپی درخواست سازمان را پس می‌گیرد و holdهایش را آزاد می‌کند)؛ captureای که از این مسابقه رد شود late capture ⇒ استرداد کامل. **Fail-safe: صادر نکن، «در انتظار» نشان بده.**
6. **دسته، موبایل، اقلام (K4/K5):** `category` با نگاشت صریح `flight→travel.flight`، `hotel|accommodation|vacation_rental→travel.hotel`، `tour|package→travel.tour`، `train→travel.train`، `bus|tourist_transportation→travel.bus`؛ هر چیز دیگر `travel` (مقدار قبلی). `customer_phone` فقط اگر شناسهٔ ورود (OTP) کاربر یک موبایل معتبر ایرانی باشد؛ امروز شناسه‌ها ایمیل‌اند پس فرستاده نمی‌شود (هرگز حدس زده نمی‌شود). `items` فقط برای رزرو تک‌قلمی (یک خط = کل مبلغ intent)؛ رزرو چندقلمی تفکیک معتبر ندارد ⇒ بدون اقلام.
7. **انقضای intent:** `VANDAPAY_INTENT_EXPIRES_IN_SECONDS` (اختیاری، ۳۰۰ تا ۲۵۹۲۰۰) ⇒ فیلد `expires_in_seconds` (پیشنهاد VP-01 در مخزن ونداپی؛ هنوز ادغام نشده). خالی/نامعتبر ⇒ فیلد فرستاده نمی‌شود = رفتار فعلی (TTL پیش‌فرض ۳۰ دقیقهٔ ونداپی).

## خارج از دامنه (ثبت‌شده)
- K8: `reverse_capture` سهم اعتبار داخلی هنگام استرداد پس از صدور.
- منبع موبایل تأییدشده (ستون/OTP پیامکی) — SMS هنوز READY_BLOCKED_EXTERNAL است.
- ستون `owning_ledger` (migration).

## پذیرش
`backend/tests/test_vandapay_hardening.py` + `backend/tests/test_vandapay.py` (MOCK برچسب‌خورده؛ پس از port روی main: ۳۱ آزمون) + آزمون‌های مالی موجود.

## Rollback
`VANDAPAY_MODE=disabled` (sweep و همهٔ مسیرهای ونداپی بی‌اثر می‌شوند) یا revert کامیت. بدون migration. تنها تغییر رفتاری بدون پرچم: مسیر fulfill کاملاً اعتباری و رد رزرو اعتبار سازمان‌های فدرال (فقط اگر env تنظیم شود).
