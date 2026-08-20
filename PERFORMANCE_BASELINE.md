# Performance Baseline

Baseline محلی فقط برای regression و نه ظرفیت Production است. ابزار `deploy/load-smoke.py` فقط URL محلی را بدون flag اضافه می‌پذیرد، read-only است و p50/p95/max/error rate را گزارش می‌کند.

معیار اولیه API read path: ۵۰۰ درخواست، concurrency=20، خطای صفر و p95 کمتر از ۵۰۰ms روی localhost. ظرفیت واقعی فقط پس از load test شبکه، PostgreSQL/Redis target و provider sandbox تعیین می‌شود.

اجرای ۱۴۰۵/۰۵/۲۹ روی `GET /hotels` و SQLite ایزوله: `500 requests`, `0 errors`, `p50=54.47ms`, `p95=184.29ms`, `max=493.59ms`؛ gate محلی PASS شد.

Query review مسیرهای پرتکرار انجام و indexهای مرکب برای Offer search، reservation list، payment reconciliation و trip timeline افزوده شدند. queryهای list باید pagination محدود داشته باشند؛ endpointهای جدید یا aggregate هستند یا حداکثر ۴ Offer/۵۰ event می‌خوانند.
