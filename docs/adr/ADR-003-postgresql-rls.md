# ADR-003: PostgreSQL Row-Level Tenant Isolation

**Status:** Accepted

## Decision

تمام جدول‌های دارای `tenant_id` در PostgreSQL با RLS و `FORCE ROW LEVEL SECURITY` محافظت می‌شوند. policy مشترک، `tenant_id` را با `current_setting('app.tenant_id', true)` مقایسه می‌کند و نبود context هیچ ردیفی را قابل خواندن/نوشتن نمی‌کند. API tenant را فقط از access token امضاشده می‌گیرد و با `set_config(..., true)` در transaction جاری قرار می‌دهد.

Migration فقط policy اضافه می‌کند، داده را بازنویسی یا حذف نمی‌کند. seed توسعه در Production اجرا نمی‌شود. تست مستقیم PostgreSQL باید خواندن، درج و تغییر cross-tenant را رد کند.

## Rollback

پیش از migration از PostgreSQL backup گرفته می‌شود. downgrade فقط policy/RLS این migration را غیرفعال می‌کند و هیچ داده‌ای را حذف نمی‌کند. image قبلی همراه migration downgrade یا restore آزموده‌شده مسیر rollback است.

