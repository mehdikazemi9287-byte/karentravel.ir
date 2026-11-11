# QA — باقی‌ماندهٔ فاز ۱ + امنیت (۲۰–۲۱ آبان ۱۴۰۵)

محیط: Source، روی کد شاخهٔ `feat/phase1-rest-security` (پس از merge با `feat/phase2-b2b-charter` = `cdc0139` که production `d251835` را دارد). همهٔ اجراها محلی؛ روی سرور production چیزی اجرا نشد.

| بررسی | نتیجه | شاهد |
|---|---|---|
| pytest کامل (SQLite) | ۸۴۰ پاس، ۷ skip، ۰ خطا | `pytest-full.txt` |
| pytest روی PostgreSQL 16 مهاجرت‌شده (فایل‌های مرتبط) | ۲۰۱ پاس | `pytest-postgres-subset.txt` |
| تست‌های تازه `backend/tests/test_phase1_rest.py` | ۱۵ پاس (داخل دو اجرای بالا) | — |
| alembic upgrade → check → downgrade -1 → upgrade → check | یک head: `20261111_76`؛ بدون drift | `alembic-up-down-up.txt` |
| RLS: ۸ جدول تازهٔ tenant با ENABLE + FORCE؛ `sms_destination_counters` عمداً سراسری | نقش API با tenant دیگر ردیفی نمی‌بیند؛ بدون tenant صفر ردیف | `rls-probe.txt` |
| تست drift مجوزها (`test_panel_access_registry.py`) | سبز (مجوز تازه‌ای اضافه نشد) | در pytest |
| `tests/unit/panel-access.cjs` | PASS | `unit-panel-access.txt` |
| `npx tsc --noEmit` / `npm run lint` / `npm run build` | ۰ خطا / ۰ خطا (فقط هشدارهای قبلی) / موفق | `frontend-checks.txt` |
| CSP با nonce | همهٔ scriptها nonce دارند؛ هیچ violation در e2e | `csp-check.txt` |
| e2e (یکی‌یکی، dev server، chrome) | role-smoke ۸/۸، critical-flows ۱۷/۱۷، refund-loop ۱/۱، agency-credit ۱/۱، charter-block ۱/۱، public-auth ۲/۲، payment-handoff ۵/۵، search-ordering ۱/۱، new-modules ۱۲/۱۲ | خروجی‌ها در گزارش PR |
| axe (wcag2a/aa، ۲۹ بازدید صفحه در ۷ نقش) | هیچ یافتهٔ critical/serious (و در این اجرا هیچ یافته‌ای) | `axe-findings.json` |

CI (اولین اجرا روی PR #82) دو شکست در `role-smoke` نشان داد که هر دو اصلاح شد: (۱) در پایگاه دادهٔ مشترک e2e، `charter-block.spec` حساب `org-admin@` را آژانس همکار می‌کند، پس smoke برای سازمان از `welfare@` (مدیر سازمان) استفاده می‌کند؛ (۲) صفحه‌های تازه داخل `div.as` نبودند و رنگ متن دکمه (`--pn-action-ink`) تعریف نمی‌شد (کنتراست ۳٫۵:۱)؛ اکنون همه داخل `.as` هستند. اجرای محلی `charter-block` + `role-smoke` پس از اصلاح: ۹/۹.

تغییر در specهای موجود فقط به خاطر جدا شدن ناحیه‌های کارکنان: در `critical-flows.spec.ts` نام منوی کارشناس عملیات اکنون «عملیات» است (قبلاً «مدیریت مجموعه»)، و مالی از سوئیچ بخش به «مالی» می‌رود.

## محدودیت‌ها
- e2e روی dev server اجرا شد (مثل CI)، نه روی build تولیدی؛ CSP build تولیدی با `next start` و curl بررسی شد.
- axe فقط صفحه‌هایی را که در smoke باز می‌شوند و فقط در عرض ۱۴۴۰ بررسی کرد؛ حالت‌های دیالوگ و فرم‌های باز بررسی نشده‌اند.
- اسکرین‌شات‌ها (`screens/`) با دادهٔ seed توسعه گرفته شده‌اند و بیشتر صفحه‌ها حالت خالی را نشان می‌دهند.
