# ADR-004: Distributed Production Rate Limiting

**Status:** Accepted

## Decision

Production از Redis و فرمان Lua اتمیک برای fixed-window rate limiting استفاده می‌کند. کلید شامل route class و fingerprint هش‌شدهٔ client/auth است؛ token خام ذخیره نمی‌شود. login محدودیت سخت‌تر دارد و پاسخ `429` شامل `Retry-After` است.

در Production نبود `REDIS_URL`، خطای اتصال Redis یا backend غیرتوزیع‌شده باعث fail-closed شدن readiness/startup می‌شود. Development و تست می‌توانند limiter حافظه‌ای صریح داشته باشند.

## Rollback

rate limiter با بازگرداندن image قبلی rollback می‌شود. حذف Redis keyها لازم نیست چون TTL دارند. غیرفعال‌کردن limiter در Production مجاز نیست.

