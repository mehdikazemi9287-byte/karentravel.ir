# Backup and Recovery

هدف پیشنهادی اولیه: `RPO <= 15m` با WAL/PITR و `RTO <= 2h`. این اعداد فقط پس از drill روی target تعهد عملیاتی می‌شوند.

- backup روزانه full و WAL پیوسته، encryption با KMS بیرونی، retention حداقل ۳۵ روز و یک کپی account/region جدا.
- `deploy/backup.sh` checksum تولید می‌کند؛ `deploy/restore-verify.sh` فقط نام DB ایزوله را می‌پذیرد.
- verification شامل Alembic head، row counts کنترل‌شده، RLS/FORCE RLS، نقش worker، ledger totals و نمونه cross-tenant denial است.
- restore روی Production فقط پس از توقف writerها، ثبت نقطه بازیابی و تأیید Incident Commander انجام می‌شود. dump یا کلید encryption داخل repository نگهداری نمی‌شود.
