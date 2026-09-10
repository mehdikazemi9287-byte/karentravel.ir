# Backup and Recovery

هدف پیشنهادی اولیه: `RPO <= 15m` با WAL/PITR و `RTO <= 2h`. این اعداد فقط پس از drill روی target تعهد عملیاتی می‌شوند.

- backup روزانه full و WAL پیوسته، encryption با KMS بیرونی، retention حداقل ۳۵ روز و یک کپی account/region جدا.
- `deploy/backup.sh` checksum تولید می‌کند؛ `deploy/restore-verify.sh` فقط نام DB ایزوله را می‌پذیرد.
- verification شامل Alembic head، row counts کنترل‌شده، RLS/FORCE RLS، نقش worker، ledger totals و نمونه cross-tenant denial است.
- restore روی Production فقط پس از توقف writerها، ثبت نقطه بازیابی و تأیید Incident Commander انجام می‌شود. dump یا کلید encryption داخل repository نگهداری نمی‌شود.

## Supplier media volume (added 2026-09-10)

Persistent supplier uploads live on the Docker named volume `karenseir_media`
mounted at `/app/media` (`MEDIA_STORAGE_ROOT`). Blob layout:
`tenant/{tenant_id}/supplier/{supplier_id}/{entity_type}/{entity_id}/{uuid}.{ext}`.
Authoritative metadata + access control is the `supplier_assets` table.

Backup:  `docker run --rm -v karenseir_media:/v -v "$PWD":/b busybox tar czf /b/media-$(date +%F).tgz -C /v .`
Restore: `docker run --rm -v karenseir_media:/v -v "$PWD":/b busybox tar xzf /b/media-DATE.tgz -C /v`
A DB dump (`pg_dump -Fc`) must be captured in the same window so `supplier_assets`
rows and blobs stay consistent.
