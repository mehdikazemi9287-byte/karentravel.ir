# Staging Validation — ۱۴۰۵/۰۵/۲۸

## Scope and isolation

Staging محلی و ایزوله با PostgreSQL 16.15 روی `127.0.0.1:55432`، Redis 7.4.10 روی `127.0.0.1:56379` و API TLS روی `127.0.0.1:58443` اجرا شد. دیتابیس `karenseir_staging` و restore target مستقل ساخته شدند؛ دیتابیس فعلی repository به‌عنوان staging استفاده یا migrate نشد.

## Passed evidence

- Alembic تا `20260819_03` روی PostgreSQL واقعی اجرا شد.
- سه تست مستقیم RLS: no-context، own-tenant، cross-tenant read/insert/update و پوشش `FORCE RLS`/policy تمام ۳۶ جدول tenant-scoped پاس شدند.
- Redis Lua rate-limit واقعی، TTL، deny و recovery پاس شد؛ با خاموشی Redis، liveness برابر ۲۰۰، readiness و API برابر ۵۰۳ و پس از restart readiness برابر ۲۰۰ شد.
- API در mode Production با PostgreSQL/Redis و Providerهای fail-closed بالا آمد؛ rate limit واقعی در درخواست یازدهم `429` و `Retry-After` داد.
- نقش worker دارای `BYPASSRLS`، بدون دسترسی users و با SELECT/UPDATE محدود روی جداول outbox/notification آزموده شد. worker واقعی event را به retry با `external_provider_not_configured` برد.
- backup custom-format با checksum ساخته شد؛ restore روی DB ایزوله تا Alembic head، ۱۰ user و ۳۶ policy RLS verify شد.
- TLS staging با certificate موقت self-signed، SAN و TLS 1.2 handshake پاس شد. این certificate مجوز rollout عمومی نیست.
- Playwright با Google Chrome سیستم هر سه critical suite را پاس کرد.

## Rollback

تمام سرویس‌ها و داده‌های staging در `/private/tmp` و پورت‌های غیر Production قرار دارند و با توقف processها قابل جمع‌کردن‌اند. هیچ Provider/OTP/Payment واقعی فعال نشد. Production rollout همچنان به certificate معتبر، دامنه، secret manager، monitoring collector و backup مقصد Production نیاز دارد.

