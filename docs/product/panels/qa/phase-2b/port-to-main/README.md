# انتقال فاز 2b به main — شواهد QA (۲۰۲۶-۱۱-۲۳)

- مبنا: `origin/main` در `62db0d3` (پس از یکی‌شدن شاخه‌ها در ۲۰۲۶-۱۱-۱۹). PR قبلی #86 روی `production` بود.
- روش: فقط پنج commit خود #86 (بدون merge commit) با `cherry-pick` روی main آمدند؛ تعارضی پیش نیامد، چون همهٔ commitهای `production` در main هستند.
- محیط: فقط Source. هیچ deploy، migration روی سرور یا merge انجام نشده است.

## migration
- `20261112_77` با `down_revision = "20261111_76"`؛ `alembic heads` فقط یک head دارد.
- PostgreSQL 16 محلی و خالی: upgrade head → downgrade -1 → upgrade head → `alembic check` («No new upgrade operations detected»). فایل `alembic-pg-up-down-up-check.txt`.
- اجرای دوبارهٔ `deploy/provision-api-role.sql` روی جدول‌های append-only مجوز UPDATE/DELETE را برنمی‌گرداند (بررسی‌شده با `information_schema.role_table_grants`).

## اصلاحات بازبینی (LESSONS.md)
1. کلید تکرار بازگشت به اعتبار آژانس: همان کلید با مبلغ، رزرو یا منشأ دیگر اکنون خطای تعارض می‌دهد و نتیجهٔ قبلی را بی‌صدا تکرار نمی‌کند.
2. اجرای بازگشت به اعتبار: ردیف رزرو آژانس پیش از کنترل «جمع ≤ مبلغ خرید» قفل می‌شود تا دو تأیید هم‌زمان از سقف عبور نکنند.
3. فهرست مالی بازگشت به اعتبار: فیلتر وضعیت پیش از LIMIT در SQL اعمال می‌شود.
4. نمای آژانس از اعتراض: نام کارمند مالی تصمیم‌گیرنده و شناسهٔ تأیید داخلی نمایش داده نمی‌شود.
5. نمای مشتری درخواست استرداد: شناسهٔ تأیید داخلی حذف شد.
6. تکرار درخواست صدور/تسویه با همان کلید اکنون از مسیر مشترک maker-checker و مقایسهٔ hash عبور می‌کند.
7. خواندن نام آژانس مالک در پیش‌نمایش تغییر چارتر به tenant مقید شد.

برای هر مورد آزمون منفی در `backend/tests/test_agency_settlement.py` اضافه شد.

## نتایج
- کل backend با SQLite: `pytest-full-sqlite.txt`.
- کل backend با آزمون‌های RLS روی PostgreSQL (مثل CI: migrate، seed، نقش‌های محدود): `pytest-full-with-postgres-rls.txt`.
- frontend: `frontend-checks.txt`.
- e2e (Playwright) در این محیط دوباره اجرا نشد؛ نتیجهٔ قبلی روی production در `../e2e-results.txt` است.
