# ADR-002: Idempotent Manual Booking Command

**Status:** Accepted

## Context

مسیر پایلوت `POST /bookings` موجودی دستی هتل را کم می‌کند و ledger/audit می‌سازد. تکرار درخواست در اثر retry شبکه یا دوبار کلیک می‌توانست رزرو و کاهش موجودی تکراری ایجاد کند. قیمت و موجودی باید فقط در backend authoritative بمانند.

## Decision

- درخواست ایجاد رزرو باید header صریح `Idempotency-Key` با طول ۸ تا ۱۲۰ نویسه داشته باشد.
- کلید در scope مستأجر و فرمان `legacy-booking.create` ذخیره می‌شود؛ تکرار همان payload همان پاسخ نخست را بدون mutation تازه برمی‌گرداند.
- استفاده دوباره از همان کلید با payload متفاوت با `409` fail-closed می‌شود.
- ردیف هتل هنگام بررسی و کاهش موجودی با `SELECT ... FOR UPDATE` قفل می‌شود (در PostgreSQL؛ SQLite توسعه‌ای این clause را نادیده می‌گیرد).
- این تغییر فقط مسیر دستی پایلوت را سخت‌تر می‌کند و جایگزین مدل provider-neutral `Reservation` یا اتصال Provider نیست.

## Acceptance

- دو درخواست همسان با یک کلید فقط یک Booking، یک ledger، یک audit و یک کاهش موجودی ایجاد کنند.
- همان کلید با تعداد شب متفاوت رد شود.
- tenant scope و سقف اعتبار موجود حفظ شوند.
- lint، typecheck، build و تست backend سبز بمانند.

## Rollback

کد endpoint و ارسال header در صفحه پایلوت قابل بازگشت است. جدول یا migration تازه‌ای ایجاد نمی‌شود و رکوردهای idempotency موجود حذف نمی‌شوند.
