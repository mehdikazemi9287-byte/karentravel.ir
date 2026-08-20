# Provider Integration Guide

Adapter جدید باید contract موجود `IntegrationAdapter` را پیاده کند و timeout، retry محدود با jitter، circuit breaker، provider rate limit، idempotency، health و correlation ID داشته باشد. credential فقط از secret manager و جدا برای environment/tenant خوانده می‌شود.

- Search response فقط timestamp، currency، expiry و provider reference معتبر برمی‌گرداند.
- Booking/payment/OTP موفقیت را فقط پس از response معتبر provider اعلام می‌کنند.
- Payment callback باید raw-body HMAC، event id یکتا، amount/currency و state transition را verify کند.
- OTP code/token در log ذخیره نمی‌شود؛ delivery reference غیرحساس ذخیره می‌شود.
- sandbox با Production متفاوت است و `DEMO_MODE` مبنای rollout نیست.

پیش از فعال‌سازی: contract test، timeout/retry/circuit test، duplicate/replay test، credential rotation، outage drill، observability و قرارداد تجاری/حریم خصوصی لازم است.
