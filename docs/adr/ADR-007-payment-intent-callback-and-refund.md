# ADR-007: Payment Intent، Callback و Refund

## وضعیت

پذیرفته‌شده — ۱۴۰۵/۰۵/۲۸

## تصمیم

- مبلغ Payment Intent فقط از pricing snapshot رزرو و در transaction backend ساخته می‌شود.
- create/initiate/refund با idempotency tenant-scoped و row lock اجرا می‌شوند.
- callback شامل tenant و event id است، ولی فقط بعد از HMAC-SHA256 روی raw body پذیرفته می‌شود؛ بدون secret معتبر fail-closed است.
- event callback immutable و provider event id یکتا است. state machine transition نامعتبر را رد می‌کند.
- refund یک رکورد مستقل و outbox event می‌سازد؛ موفقیت فقط بعد از callback معتبر ثبت می‌شود و جمع refund از captured amount بیشتر نمی‌شود.

## پذیرش و rollback

تست create، duplicate، callback جعلی/تکراری، transition و over-refund اجباری است. Migration فقط جدول اضافه می‌کند و downgrade مخرب نیست؛ rollback با image قبلی انجام می‌شود.
