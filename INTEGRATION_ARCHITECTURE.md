# Integration Architecture

هر provider یک Adapter مستقل با contract نرمال‌شده دارد: search، quote، reserve، ticket/confirm، cancel/refund و webhook. Integration Hub credential vault reference، sandbox/production، correlation ID، error rate، latency، quota، circuit breaker، retry، manual disable، routing/failover، commission/cost/quality را نگه می‌دارد.

Adapter بدون endpoint و credential معتبر fail-closed است؛ UI هرگز «connected» یا قیمت زنده جعلی نشان نمی‌دهد. Amadeus، Booking و دیگر نام‌ها صرفاً دسته احتمالی اتصال‌اند، نه قرارداد فعلی. API خروجی و Widget با OAuth/API key، rate limit، tenant scope، idempotency و signed webhook طراحی می‌شوند.

WordPress صرفاً CMS/channel/widget host است؛ منطق رزرو، مالی و policy خارج از آن باقی می‌ماند.

## Contract اجرایی adapter

تمام adapterها context شامل `tenant_id`، `correlation_id` و `idempotency_key` دریافت می‌کنند و contract آن‌ها configuration validation، timeout، retry policy محدود، خطای ساختاریافته و health status را الزام می‌کند. implementation فعلی `DisabledMockAdapter` همواره `not_sent` برمی‌گرداند؛ این رفتار برای Flight، Hotel، Tour+Hotel، Train، Payment، OTP، SMS، Push، Email، Inventory و Issuance عمدی است.

جریان قابل توسعه: `Provider/Admin → TripEvent → OutboxEvent → NotificationDeliveryAttempt → Web/App/Push/SMS/Human Support`. worker فعلی retry با backoff و dead-letter پس از پنج تلاش را مدل می‌کند، ولی هیچ کانال بیرونی متصل نیست.
# الحاقیه Identity و Payment

OTP delivery فقط از Adapter و پس از ایجاد challenge hash-only انجام می‌شود؛ failure هیچ sessionی نمی‌سازد. Payment callback از raw-body HMAC، tenant context امضاشده، provider event id یکتا و state machine استفاده می‌کند. Refund از outbox عبور می‌کند و provider processing consistency تراکنش اصلی را تغییر نمی‌دهد.

Providerها اکنون پشت resilience wrapper توزیع‌شده قرار دارند. Search/booking external فقط پس از response موفق adapter جلو می‌رود؛ manual supplier fulfillment فقط برای supplier فعال و با payment capture/audit مجاز است. Notification worker health/metrics مستقل روی پورت داخلی 9101 دارد.
