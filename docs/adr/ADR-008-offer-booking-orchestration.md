# ADR-008: Orchestration از Offer تا Voucher

## وضعیت

پذیرفته‌شده — ۱۴۰۵/۰۵/۲۸

## تصمیم

- Offer فقط توسط supplier مجاز و برای tenant همان supplier ثبت می‌شود؛ قیمت، موجودی و policy در frontend authoritative نیست.
- Price Check یک snapshot immutable با expiry و hash می‌سازد. Booking فقط از Price Check معتبر و مصرف‌نشده ساخته می‌شود.
- Flight، Hotel، Tour و Package از state machine مشترک استفاده می‌کنند؛ itemهای package snapshot مستقل دارند.
- confirmation خارجی فقط پس از payment captured و response موفق provider انجام می‌شود. inventory داخلی supplier با fulfillment دستی و audit قابل تأیید است.
- Voucher فقط توسط supplier/backoffice پس از confirmation و با document reference غیرحساس صادر می‌شود.
- هر transition history، outbox، actor و idempotency tenant-scoped دارد.
- cancellation/refund estimate فقط از policy snapshot دارای `verified=true` محاسبه می‌شود؛ در غیر این صورت پاسخ `409` است.

## پذیرش و rollback

تست service typeها، expiry، replay، cross-tenant، payment gate، provider failure، manual fulfillment، voucher و policy quote اجباری است. Migration فقط table/column/index اضافه می‌کند و downgrade مخرب نیست.
