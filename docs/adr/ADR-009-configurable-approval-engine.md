# ADR-009: Approval Engine قابل‌تنظیم

## تصمیم

هر tenant می‌تواند template نسخه‌دار شامل stepهای مرتب Expert، Manager، Finance و CEO بسازد. workflow از template snapshot می‌گیرد؛ تغییر template روی گردش جاری اثر ندارد. هر step status و SLA مستقل دارد. تصمیم فقط برای role همان step یا Platform Admin مجاز است، rejection reason اجباری است و escalation history حذف نمی‌شود.

Department، Cost Center و Employee Assignment tenant-scoped هستند. تمام تصمیم‌ها، escalationها و پایان workflow outbox/audit event دارند.

Migration فقط افزایشی است. rollback با application image قبلی و حفظ تاریخچه انجام می‌شود.
