# Incident Response

- Severity 1: leakage احتمالی tenant، جعل callback، ledger inconsistency یا secret exposure؛ فوراً rollout متوقف، credential revoke/rotate و Security Lead مطلع شود.
- Severity 2: login/payment/provider outage یا backlog بحرانی؛ fail-closed حفظ و کانال انسانی فعال شود.
- ابتدا زمان، release digest، request/correlation ID، tenant reference و scope ثبت شود؛ secret/OTP/token/PII در ticket قرار نگیرد.
- containment نباید audit/ledger/event history را حذف کند. callback تکراری فقط از payload اصلی و پس از signature validation replay می‌شود.
- recovery با release قبلی و restore آزموده‌شده است. پس از recovery، cross-tenant، ledger reconciliation، queue depth و notification duplication بررسی و postmortem بدون سرزنش ثبت شود.
