# ADR-012: Performance Baseline و Index Budget

Index فقط برای queryهای واقعی tenant-first اضافه می‌شود. migration افزایشی است و قبل از Production باید زمان build/size روی clone داده واقعی اندازه‌گیری شود. rollback indexها را خودکار حذف نمی‌کند؛ image rollback امن است.
