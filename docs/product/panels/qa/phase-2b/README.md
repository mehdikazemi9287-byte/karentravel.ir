# QA — فاز ۲ب: تسویهٔ دوره‌ای آژانس، اعتراض، بازگشت به اعتبار، تغییر و لغو چارتر (۲۲ آبان ۱۴۰۵)

محیط: **Source**، شاخهٔ `feat/phase2b-settlement-charter-ops` (از `production` در `50c1bab`). همهٔ اجراهای این فایل **محلی** هستند؛ روی سرور production چیزی اجرا نشد. نتیجهٔ GitHub CI در توضیح PR ثبت می‌شود.

| بررسی | نتیجهٔ محلی | شاهد |
|---|---|---|
| pytest کامل (SQLite) | ۸۵۱ پاس، ۷ skip، ۰ خطا | `pytest-full-sqlite.txt` |
| pytest روی PostgreSQL 16 مهاجرت‌شده (فایل‌های مرتبط، DB تازه به ترتیب CI) | ۲۰۳ پاس، ۱ skip (Redis واقعی) | `pytest-postgres-subset.txt` |
| تست‌های تازه: `test_agency_settlement.py` (۷)، `test_charter_changes.py` (۴) | داخل دو اجرای بالا سبز | — |
| alembic: upgrade از `20261104_69` → head → check → downgrade -1 → upgrade → check؛ و یک بار با نقش API از پیش موجود | یک head: `20261112_77`؛ بدون drift | `alembic-up-down-up.txt` |
| RLS: ۷ جدول تازه با ENABLE + FORCE؛ نقش API با tenant دیگر یا بدون tenant صفر ردیف؛ درج ردیف tenant دیگر رد می‌شود؛ UPDATE/DELETE روی ردیف‌های صورت، روند و تغییر چارتر `permission denied` (پس از اجرای دوبارهٔ `provision-api-role.sql` هم) | سبز | `rls-probe.txt`، `alembic-up-down-up.txt` |
| تست RLS سراسری (`test_postgresql_all_tenant_tables_force_rls`) با نقش API | سبز | در اجرای PostgreSQL |
| `tests/unit/panel-access.cjs` | PASS (۴۸ صفحهٔ کارکنان؛ صفحهٔ هر آیتم منو موجود) | `frontend-checks.txt` |
| `tsc --noEmit` / `npm run lint` / `npm run build` | ۰ خطا / ۰ خطا (۴۴ هشدار قبلی در فایل‌های دیگر) / موفق | `frontend-checks.txt` |
| e2e (dev server، chrome، پورت‌های 8140/3141/8142، به‌صورت گروهی) | agency-settlement ۱/۱، charter-change ۱/۱، role-smoke (با صفحه‌های تازه زیر axe) ۸/۸؛ در اجرای ترکیبی: agency-credit ۱/۱، charter-block ۱/۱، refund-loop ۱/۱ | `e2e-results.txt` |
| اسکرین‌شات‌ها (۱۴۴۰ و ۳۹۰) از اجرای e2e با دادهٔ آزمون محلی | ۱۳ فایل | `screens/` |

## نکته‌ها و محدودیت‌ها
- **اجرای ترکیبی همهٔ specهای پنل** با تنظیمات پیش‌فرض محلی (timeout ۳۰ ثانیه، بدون retry) روی ماشین دوهسته‌ای شکست خورد: دو spec تازه هنگام اولین کامپایل مسیر تازه timeout شدند و سپس dev server به درخواست‌ها پاسخ نداد (`ECONNREFUSED`). همان specها در اجرای گروهی سبز هستند. با `CI=1` (۹۰ ثانیه، یک retry) هر دو spec تازه با retry سبز شدند (flaky در تلاش اول)، ولی refund-loop و role-smoke به سرور خاموش‌شده خوردند. علت: **OOM killer گروه حافظهٔ sandbox محلی** (`dmesg`: «Memory cgroup out of memory: Killed process … chrome»)، نه خطای برنامه. معیار نهایی اجرای GitHub CI است (`e2e-results.txt`، بخش `e2e-panels-ci`).
- PostgreSQL محلی منطقهٔ زمانی `Europe/Berlin` دارد؛ یک assert تست که UTC فرض کرده بود اصلاح شد (کد برنامه همهٔ زمان‌ها را آگاه از منطقه ذخیره می‌کند).
- اجرای دوبارهٔ مجموعهٔ تست روی همان DB حفظ‌شده (`PRESERVE_MIGRATED_TEST_DATABASE=1`) برای سه تست قدیمی (`test_phase1_rest`، `test_approval_engine`) تکرارپذیر نیست؛ نتیجهٔ بالا روی DB تازه است.
- اسکرین‌شات‌ها دادهٔ آزمون e2e هستند (نه دادهٔ واقعی)؛ مقایسه با Figma: فریم `245:120` از MCP و بقیه از پیش‌نمایش‌های PNG شاخهٔ `docs/figma-p3`. تفاوت‌های آگاهانه در `08-phase2b-settlement-charter-ops.md` بخش ۲.
- هیچ پیامکی ارسال نشد؛ اعلان‌ها فقط در جدول اعلان و outbox ثبت شدند.
