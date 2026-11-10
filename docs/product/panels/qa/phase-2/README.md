# QA فاز ۲ پنل‌ها — B2B آژانس و چارتر (۱۹ آبان ۱۴۰۵)

محیط: **Source** (شاخهٔ `feat/phase2-b2b-charter`). روی Production دیپلوی **نشده** است. migration فقط روی PostgreSQL 16 محلی آزمایشی اجرا شده است. همهٔ داده‌های اسکرین‌شات‌ها حساب‌های seed محیط توسعه‌اند، نه دادهٔ واقعی. پرداخت واقعی، مرجع مجوز واقعی و سامانهٔ چارتر بیرونی صدا زده نشده است.

## نتایج
| بررسی | نتیجه | شاهد |
|---|---|---|
| `pytest` کل backend (SQLite) | **۸۱۸ موفق**، ۷ skipped، ۰ شکست (پایه پیش از فاز: ۷۹۶) | `pytest-full.txt` |
| تست‌های تازه: `test_agency_b2b.py` (۱۶) و `test_charter_blocks.py` (۶) | سبز روی SQLite و روی **PostgreSQL 16 migrate‌شده** (همراه تست ۱۰ نخ هم‌زمان) | `pytest-phase2-postgres.txt` |
| `test_panel_access_registry.py` (drift نقش و مجوز) | سبز | داخل اجرای کامل |
| alembic | یک head (`20261110_74`)؛ `upgrade head`، سپس `downgrade -1` (جدول‌ها و ستون حذف شدند)، سپس دوباره `upgrade head` موفق | `alembic-upgrade.txt` |
| RLS | هر ۹ جدول تازه `relrowsecurity=t` و `relforcerowsecurity=t` با policy `karenseir_tenant_isolation`. نقش غیر superuser با `app.tenant_id=2` صفر ردیف و بدون tenant صفر ردیف می‌بیند | `rls-tables.txt`، `rls-probe.txt` |
| `npm run lint` | ۰ خطا (۴۰ هشدار قدیمی؛ هیچ‌کدام در فایل‌های این فاز نیست) | — |
| `npx tsc --noEmit` | بدون خطا | — |
| `npm run build` | موفق؛ همهٔ ۱۲ مسیر تازه ساخته شدند | — |
| `node tests/unit/panel-access.cjs` | سبز (گروه‌های منوی آژانس، guard صفحه‌های تازه، جداسازی عملیات و مالی) | — |
| Playwright `e2e/panels/agency-credit.spec.ts` | ۱ موفق (۱٫۲ دقیقه) | `e2e-agency-credit.txt` |
| Playwright `e2e/panels/charter-block.spec.ts` | ۱ موفق (۲۳ ثانیه) | `e2e-charter-block.txt` |
| Playwright `e2e/panels/refund-loop.spec.ts` (رگرسیون فاز ۱) | ۱ موفق | `e2e-refund-loop-regression.txt` |

اجرای e2e تکه‌تکه بود (هر spec جدا، با `E2E_PYTHON=/home/claude/venv-base/bin/python`). اجرای کامل همهٔ specها در یک نوبت انجام نشد.

## آنچه e2e پوشش می‌دهد
1. **agency-credit:** مدیر مجموعه آژانس را می‌سازد. مدیر آژانس پروفایل حقوقی (با رقم فارسی) و مجوز بند الف را ثبت و برای احراز ارسال می‌کند. کارشناس عملیات در OPS-09 هر دو مرجع (درگاه ملی و سازمان هواپیمایی) را «منطبق» ثبت و آژانس را فعال می‌کند. کارشناس مالی اول سقف ۵۰ میلیون ریالی را درخواست می‌دهد و تأیید شد که پیش از تأیید سقف صفر می‌ماند. کارشناس مالی دوم تأیید می‌کند. مدیر آژانس قاعدهٔ markup ثابت می‌سازد. در صفحهٔ فروش، استعلام قیمت و تفکیک مبلغ نمای خریدار دیده می‌شود: کمیسیون ۲۴۰٬۰۰۰، ارزش افزودهٔ کمیسیون ۲۴٬۰۰۰ و قیمت مشتری ۲۱٬۰۰۰٬۰۰۰ ریال. سپس رزرو و پرداخت از حساب آژانس انجام می‌شود. صورت حساب HOLD و CAPTURE را نشان می‌دهد و مانده ۳۰٬۰۰۰٬۰۰۰ ریال است. خروجی CSV دانلود می‌شود و صفحه در ۳۹۰px اسکرول افقی ندارد.
2. **charter-block:** دو آژانس فعال (چارترکننده با بند الف، همکار با بند ب) آماده می‌شوند. در فرم CH-02 گزینهٔ «داخلی» دیده می‌شود ولی غیرفعال است. فرم پر می‌شود و برای بازبینی ارسال می‌شود. عملیات با کارمزد ۳۰۰ bps منتشر می‌کند. چارترکننده ۳ صندلی به همکار سهمیه می‌دهد: «۳ از ۳» دیده می‌شود، فروش عمومی ۷ صندلی می‌شود، و نمای فروشنده کارمزد پلتفرم را نشان می‌دهد. همکار سهمیه را در API خود می‌بیند ولی بلوک چارترکننده برایش 404 است. CH-01 در ۳۹۰px اسکرول افقی ندارد.

## اسکرین‌شات‌ها (`screens/`، deviceScaleFactor 1)
`AG-01-today_1440`، `AG-02-profile-licences_1440`، `AG-03-sell-on-credit_1440`، `AG-05-bookings_1440`، `AG-07-markup-commission_1440`، `AG-15-credit-wallet_1440`، `AG-15-credit-wallet_390`، `AG-invoices_1440`، `OPS-09-agency-verification_1440`، `FIN-agency-accounts-checker_1440`، `CH-01-flights-list_1440`، `CH-01-flights-list_390`، `CH-02-seat-block-form_1440`، `CH-03-04-block-detail-allocation_1440`، `OPS-charter-review_1440`.

## محدودیت‌ها و موارد بررسی‌نشده
- اسکرین‌شات‌ها از سرور `next dev` گرفته شده‌اند. نشان «Compiling» و شمارندهٔ «Issues» در گوشهٔ برخی تصویرها از ابزار توسعهٔ Next است، نه بخشی از صفحه. علت آن «Issues» بررسی نشد.
- مقایسهٔ پیکسلی با frameهای Figma انجام نشد؛ چیدمان و محتوا با frameهای P2 هم‌خوان شده است. حالت‌های loading، empty و error فقط به شکل اجزای مشترک پیاده شده‌اند، نه به‌عنوان variantهای جدای Figma.
- axe خودکار اجرا نشد.
- RLS با یک نقش آزمایشی غیر superuser (`ks_rls_probe`) بررسی شد، نه با نقش واقعی `karenseir_api` روی سرور.
- باقی‌مانده‌ها در `../../06-phase2-implementation.md` بخش ۳ فهرست شده‌اند.
