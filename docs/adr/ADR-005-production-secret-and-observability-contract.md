# ADR-005: قرارداد Secret و Observability در Production

## وضعیت

پذیرفته‌شده — ۱۴۰۵/۰۵/۲۸

## تصمیم

- سرویس‌ها secret را یا مستقیماً از متغیر محیطی و یا از فایل mount‌شده با پسوند `_FILE` می‌خوانند؛ تعریف هم‌زمان هر دو fail-closed است.
- فایل secret باید regular file، غیر symlink و بدون دسترسی group/other باشد. مقدار secret هرگز log نمی‌شود.
- در `ENVIRONMENT=production` حالت provider برابر `mock` فقط با `DEMO_MODE=true` مجاز است. حالت پیش‌فرض `disabled` می‌ماند و هیچ موفقیت خارجی جعل نمی‌شود.
- قواعد Prometheus برای down بودن API، نرخ 5xx/429 و latency در repository version می‌شوند. اتصال collector و Alertmanager یک gate بیرونی و قابل‌اثبات است.
- validation عمومی DNS/TLS/readiness/metrics با script فقط read-only انجام می‌شود و بدون hostname واقعی PASS اعلام نمی‌شود.

## پذیرش

1. unit test خواندن secret-file، conflict، symlink و permission ناامن را پوشش دهد.
2. Production با provider mock و بدون Demo Mode در startup رد شود.
3. فایل‌های Prometheus با `promtool check rules` در محیط دارای promtool معتبر باشند؛ حداقل syntax YAML در QA محلی بررسی شود.
4. validation عمومی certificate معتبر، hostname، readiness و metrics را بررسی کند و self-signed را نپذیرد.

## Rollback

تغییر schema یا data ندارد. rollback با بازگرداندن image قبلی انجام می‌شود. secretهای mount‌شده تا تأیید سلامت نسخه قبلی حفظ می‌شوند و rotation/revocation فقط پس از rollback موفق انجام می‌شود.
