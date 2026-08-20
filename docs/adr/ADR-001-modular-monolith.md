# ADR-001: Modular Monolith for Pilot Foundation

**Status:** Accepted for target architecture (implementation deferred)

## Context

کارن‌سیر دامنه‌های متعدد، multi-tenancy، providerهای ناهمگون و نیاز عملیاتی حساس دارد؛ در عین حال پایلوت باید کنترل‌شده بماند.

## Decision

شروع backend بعد از تأیید UI با FastAPI/Python، PostgreSQL، SQLAlchemy 2.x، Alembic، Pydantic v2، Redis و Docker Compose در Modular Monolith انجام می‌شود. مرز bounded context، outbox، saga، idempotency، JWT access/refresh، OTP adapter، RBAC/policy، audit، health/readiness، observability و RLS از ابتدا طراحی می‌شوند.

## Consequences

توسعه و تراکنش ساده‌تر است و مرزهای کد برای جداسازی آینده باقی می‌ماند. استقلال deploy فوری به‌دست نمی‌آید و باید با module ownership و contract test از monolith نامنظم جلوگیری شود.
