# برنامهٔ Launch V1 کارن تراول — تحلیل شکاف و نقشهٔ کار

> تاریخ: ۲۳ نوامبر ۲۰۲۶ (۲ آذر ۱۴۰۵) · شاخه: `launch-v1/plan-2026-11-23` · پایه: `main` @ `ff43ea7`
> محیط: **Source**. از این جلسه به سرور Production دسترسی نبود؛ هر چیزی دربارهٔ سایت زنده فقط با شواهد تاریخ‌دار داخل مخزن گفته شده و در غیر این صورت **UNVERIFIED_ON_PROD** است.
> طبق قاعدهٔ «انجام شد یعنی روی سایت زنده دیده شد»، `DONE_IN_SOURCE` یعنی کد در `main` هست، نه اینکه روی سایت دیده شده.

## ۰. تعریف «تمام‌شده» در Launch V1 (توافق مالک)

1. karentravel.ir با HTTPS؛ لوگوی نهایی (هنوز انتخاب نشده)؛ طرح Stitch روی صفحه‌های داخلی (صفحهٔ اول محافظت‌شده است).
2. ورود با کد پیامکی (کاوه‌نگار وصل).
3. جست‌وجو و خرید پرواز، اول با Mahan Air MRS بعد از تأیید Production ماهان.
4. هتل از طریق اقامت۲۴ (Eghamat24) — کلیدها پیش مالک است.
5. تورهای آژانس‌های قراردادی.
6. یک درگاه پرداخت (ونداپی یا اینجاست، هر کدام زودتر آماده شد)، تا رسیدن credential بسته (fail-closed).
7. فرم درخواست به‌عنوان جایگزین (فروش آفلاین: درخواست ← CRM/ادمین ← پیشنهاد قیمت) برای هر خدمتی که تأمین‌کنندهٔ زنده ندارد.
8. **الزام جدید مالک:** مصرف‌کنندهٔ عادی (B2C) و مصرف‌کنندهٔ سازمانی (مدیر سازمان، کارمند، اعتبار، تأیید) **پنل جدا** داشته باشند: داشبورد، منو، دسترسی و جریان جدا؛ یک نفر می‌تواند عضو هر دو باشد و باید بدون خراب‌شدن هیچ‌کدام بین آن‌ها جابه‌جا شود.

خارج از V1: قطار، ویلا، پرتال کامل B2B آژانس، دستیار هوشمند.

## ۱. جدول وضعیت

| # | مورد | وضعیت | شواهد (مسیر فایل) | مانده |
|---|---|---|---|---|
| 1 | HTTPS | UNVERIFIED_ON_PROD | `docs/PROGRESS_2026-11-19.md` (درخواست از داخل سرور به `https://karentravel.ir/` از CDN ابرآروان: HTTP/2 200، ۱۹ نوامبر)؛ `CAPABILITY_REGISTRY.json` → `tls` هنوز `READY_BLOCKED_EXTERNAL` با تاریخ سپتامبر (کهنه) | بررسی زنده: گواهی معتبر، ریدایرکت http→https، HSTS؛ سپس به‌روزکردن `tls` در رجیستری |
| 1 | لوگو | BLOCKED_EXTERNAL (تصمیم مالک) | `design/logo/README.md`، `design/logo/stitch-logo-elegant-v2-2026-11-19.png` | انتخاب مالک ← SVG، فاوآیکون، آیکون PWA، هدر/فوتر |
| 1 | Stitch صفحه‌های داخلی | PARTIAL | PR #99 ادغام‌شده (سفرهای من، پروفایل، کیف پول، پرداخت، نتیجهٔ پرداخت، تأیید رزرو)؛ `docs/design/stitch-redesign-2026-11/`؛ `docs/qa/2026-11-23-stitch-account/` | صفحه‌های داخلی باقی‌مانده (هتل، تور، پرواز، پنل سازمان)؛ انتشار و مقایسهٔ زنده کنار PNG طرح |
| 2 | ورود پیامکی کاوه‌نگار | BLOCKED_EXTERNAL | `backend/app/kavenegar_adapter.py`، PR #98 ادغام‌شده، `docs/integrations/kavenegar-sms.md`؛ اجرای تشخیص روی سرور (۲۳ نوامبر): `account/info` ← HTTP 430، قالب `karentest` آزمایشی | روشن‌شدن کد 430 از کاوه‌نگار؛ قالب تولیدی تأییدشده با `%token`؛ یک ارسال آزمایشی به شمارهٔ مالک؛ انتشار #98 |
| 3 | پرواز ماهان MRS | MISSING (اتصال به جریان خرید) + BLOCKED_EXTERNAL (تأیید Production) | `backend/app/mahan_mrs.py` (کلاینت QAA/Live)، `backend/app/mahan_cert.py` و `docs/integrations/mahan/README.md` (سناریوهای ۶–۸ روی QAA رزرو شد، بلیتی صادر نشد). `mahan_mrs` فقط در `mahan_cert.py` استفاده می‌شود؛ به جست‌وجو/checkout وصل نیست | ارسال نتایج به ماهان و گرفتن دسترسی Production؛ آداپتور پرواز ماهان پشت `flight_port` و فلگ، بدون صدور خودکار؛ تست‌های fail-closed |
| 4 | هتل اقامت۲۴ | MISSING + BLOCKED_EXTERNAL | در `backend/app` هیچ آداپتور اقامت۲۴ نیست (جست‌وجوی `eghamat` فقط در `backend/scripts/catalog/import_inhouse_bundle.py` و یک سند تحلیلی). آداپتور GRS موجود است ولی خاموش (`backend/app/grs_adapter.py`، `GRS_MODE=disabled`) | کلید و مستند API از مالک؛ آداپتور پشت همان درگاه هتل (`providers.py`/`hotel_rates.py`)؛ تا آن موقع هتل‌ها با فرم درخواست (مورد ۷) |
| 5 | تور آژانس‌های قراردادی | DONE_IN_SOURCE / UNVERIFIED_ON_PROD | `app/agency/tours`، `app/supplier/tours`، `app/admin/tours`، `app/tours/*`؛ رجیستری `tour_customer_journey` = PARTIAL (خرید ایزوله با پرداخت ایزوله) | ثبت آژانس‌های واقعی و تورهای واقعی آن‌ها در پنل؛ وابسته به درگاه (مورد ۶) برای خرید آنلاین، وگرنه درخواست |
| 6 | درگاه پرداخت | BLOCKED_EXTERNAL (fail-closed) | ونداپی: `backend/app/vandapay.py`، `docs/integrations/vandapay.md` (فقط MOCK، خاموش D15). اینجاست: `backend/app/injast.py`، PR #97 ادغام‌شده، `docs/payments/INJAST_INTEGRATION.md`؛ هیچ پرداخت واقعی | merchant_id اینجاست + ثبت IP سرور + آدرس callback با HTTPS؛ یا قرارداد PSP ونداپی؛ سپس یک تراکنش واقعی با تأیید صریح مالک |
| 7 | فرم درخواست / فروش آفلاین | PARTIAL | `components/customer/TripRequestForm.tsx` ← `POST /public/sales-desk/requests` (`backend/app/sales_desk.py`) ← میز فروش `app/admin/sales-desk` ← پیشنهاد قیمت `/quotes`؛ فرم در `app/contact`، `TourCollections`، `FlightFacts`، `CustomerHelp` | فرم روی صفحهٔ هتل‌ها و هر خدمت بدون تأمین‌کنندهٔ زنده (بیرون از صفحهٔ اول/جست‌وجوی محافظت‌شده)؛ تنظیم `SALES_DESK_PUBLIC_TENANT` روی سرور (بدون آن 503 «هنوز فعال نشده»)؛ یک آزمون سرتاسری درخواست ← کارشناس ← پیشنهاد |
| 8 | جداسازی پنل B2C و سازمانی | PARTIAL (گام اول در همین شاخه) | بخش ۲ | بخش ۲ و ۳ |

موارد ادغام‌شده در `main` ولی منتشرنشده (طبق `docs/PROGRESS_2026-11-23.md` نسخهٔ زنده `35f1c76` بود): #97، #98، #99، #100 (migration `20261112_77` نیاز به تأیید صریح مالک)، #101. وضعیت فعلی سرور از این جلسه **UNVERIFIED** است.

## ۲. مورد ۸ — وضعیت امروز (دقیق)

### مسیرها
- **پنل شخصی (B2C):** `app/account/*` — نمای کلی، رزروها، تغییرات، ویزا، مدارک، پرداخت‌ها، استرداد، تغییر قیمت، کیف پول، **مزایای سازمانی** (`/account/benefits`)، ذخیره‌شده‌ها، اعلان‌ها، امنیت، پشتیبانی، درخواست قطار/همکار. ناحیهٔ `customer` در `lib/panel-access.ts`.
- **پنل سازمان:** `app/organization/*` — نمای کلی، اعضا، درخواست‌ها، سیاست، ساختار، اعتبار، رزروها، صورتحساب، گزارش، ممیزی، مسافران، تعهد مالی؛ به‌اضافهٔ `app/employee` (میز کار کارمند). ناحیهٔ `organization`.
- پوستهٔ مشترک: `components/panel/PanelKit.tsx` (`PanelShell`)؛ محتوا: `components/panel/CustomerPanel.tsx`، `components/panel/OrganizationPanel.tsx`، `components/operational/EmployeePortal.tsx`، `components/operational/EnterpriseWorkspace.tsx`.

### نقش‌ها و دسترسی
- هر کاربر **یک نقش سراسری** دارد: `users.role` (`backend/app/main.py` کلاس `User`) و در JWT (`token_for`). نقش‌های سازمانی: `employee`، `manager`، `welfare_manager`، `organization_admin`.
- مجوزهای نقش: `backend/app/security.py::ROLE_PERMISSIONS` ≡ `lib/role-permissions.json` (آزمون `backend/tests/test_panel_access_registry.py`).
- عضویت سازمانی جدا از نقش است: `employee_assignments` (`backend/app/operations.py::EmployeeAssignment`) + مجوزهای هر سازمان در `enterprise_grants` (`backend/app/enterprise_models.py`). مجوزهای سازمانی: `requests.read_all`، `requests.on_behalf`، `requests.approve`، `policy.manage`، `roles.manage`، `rfq.manage`، `benefits.manage` (`backend/app/enterprise.py::PERMISSIONS`).
- **بک‌اند** همهٔ `/enterprise/*` را با همین عضویت مجاز می‌کند (`permissions()`، `org_reader()`، `summary`)؛ `GET /enterprise/context` فهرست سازمان‌های کاربر و مجوزهایش را برمی‌گرداند.
- **فرانت (پیش از این شاخه)** راهنمای ناحیهٔ سازمان را فقط با نقش سراسری می‌سنجید (`R.orgManager` / `R.orgMember` در `lib/panel-access.ts`).

### شکاف‌ها
1. **کاربر عادی که عضو سازمان هم هست** (نقش `customer` + ردیف `employee_assignments`) با اینکه API به او اجازه می‌دهد، پنل سازمان و میز کار کارمند را «دسترسی ندارید» می‌دید. یعنی «یک نفر در هر دو» عملاً کار نمی‌کرد.
2. **نشت سازمان در پنل شخصی:** `/account/benefits` (`CustomerBenefits`) اعتبار و لینک‌های سازمانی را داخل منوی شخصی نشان می‌دهد.
3. **مدیر سازمان خرید شخصی ندارد:** `organization_admin`، `manager` و `welfare_manager` مجوز `reservation:create` ندارند؛ پس اگر نقش سراسری‌شان سازمانی باشد، رزرو شخصی تور/اقامتگاه (`require_permission("reservation:create")` در `main.py`) برایشان 403 است.
4. جابه‌جاکنندهٔ پنل وجود نداشت؛ فقط لینک «حساب من» / «پنل کاری من» در پایین منو.
5. برخی صفحه‌های سازمان (`structure`، `passengers`، `financial-context`) از endpointهایی می‌خوانند که با نقش سراسری محافظت می‌شوند (`member:manage` و …)، نه با عضویت.
6. «سازمان فعال» فقط در `sessionStorage` (`karenseir-panel-organization`) داخل `OrgScope` انتخاب می‌شود؛ در API نه header و نه claim برای زمینهٔ سازمانی نیست (هر endpoint خودش `org` را در مسیر/پارامتر می‌گیرد — که درست است).

## ۳. مورد ۸ — طراحی جداسازی

### اصل
- **هویت یکی، زمینه دو تا.** هر شخص یک حساب و یک ورود دارد. «حساب شخصی» همیشه هست. «پنل سازمان» از **عضویت** (`employee_assignments` + `enterprise_grants`) می‌آید، نه از نقش سراسری. نقش سراسری فقط برای کارکنان مجموعه (عملیات، مالی، ادمین، آژانس، تأمین‌کننده) و سازگاری قدیمی می‌ماند.
- API مرجع است؛ فرانت فقط راهنما است (همان اصل `lib/panel-access.ts`).
- هیچ ادغام داده‌ای بین دو پنل نیست: رزرو شخصی هرگز در گزارش سازمان نمی‌آید مگر با `EnterpriseBookingLink` صریح؛ اعتبار سازمانی فقط در جریان سازمانی خرج می‌شود.

### گروه‌های مسیر
| زمینه | مسیر | منو | خانه |
|---|---|---|---|
| شخصی | `/account/*` | فقط موارد شخصی (بدون «مزایای سازمانی» در فاز ۲) | `/account` |
| سازمان — کارمند | `/employee`، `/organization/requests`، `/organization/policy` | منوی سازمان، فقط صفحه‌های عضو | `/employee` |
| سازمان — مدیر | `/organization/*` | منوی سازمان بر اساس مجوز سازمانی | `/organization` |

نیازی به تغییر نام مسیرها (`/org`) نیست: `/account` و `/organization` همین الآن جدا هستند و تغییر نام فقط لینک‌ها و تست‌ها را می‌شکند.

### گاردها
- `lib/panel-context.ts` (**در این شاخه ساخته شد**): نگاشت صفحهٔ سازمان → مجوز سازمانی، آینهٔ گارد endpoint همان صفحه:
  - هر عضو: `/employee`، `/organization/requests`، `/organization/policy`
  - `requests.read_all | policy.manage | roles.manage`: `/organization`، `reports`، `bookings`، `credit`، `billing`، `audit`
  - `roles.manage | policy.manage | requests.on_behalf | benefits.manage`: `/organization/members`
  - فقط با نقش (بدون تغییر): `structure`، `passengers`، `financial-context`
- `PanelShell`: دسترسی = گارد نقش **یا** گارد عضویت. تا رسیدن پاسخ `/enterprise/context` «در حال دریافت…» نشان می‌دهد، نه «دسترسی ندارید».

### جابه‌جاکنندهٔ زمینه
- در منوی کناری پنل شخصی و پنل سازمان: «حساب شخصی | پنل سازمان: نام سازمان» (با `aria-current`). فقط وقتی دیده می‌شود که کاربر عضو سازمانی باشد یا نقش سراسری سازمانی داشته باشد؛ مشتری عادی چیزی نمی‌بیند.
- چند سازمان: انتخاب سازمان داخل پنل سازمان با `OrgScope` (موجود) می‌ماند.
- جابه‌جایی فقط ناوبری است: توکن، نشست و سبد عوض نمی‌شود؛ پس هیچ‌کدام از دو طرف خراب نمی‌شود.

### بک‌اند (فازهای بعد)
- مجوز `reservation:create` / `reservation:read` شخصی برای همهٔ نقش‌های سازمانی، یا بهتر: نقش سراسری همهٔ اعضای سازمان `customer` بماند و مدیریت سازمان کاملاً از `enterprise_grants` بیاید (نیاز به migration دادهٔ نقش‌ها ← تأیید مالک).
- انتقال گارد `structure` (departments/cost-centers)، `passengers` و `financial-context` به مجوز سازمانی (`roles.manage`) به‌جای `member:manage` سراسری.
- `GET /me/contexts` اختیاری (همان `/enterprise/context` کافی است؛ endpoint تازه نساختیم).

### فایل‌هایی که باید تغییر کنند
| فاز | فایل | تغییر |
|---|---|---|
| ۸.۱ (انجام شد) | `lib/panel-context.ts` (جدید) | نگاشت مجوز صفحه، `orgAllows`، `orgPagesFor`، `orgHomeFor`، `panelContextsFor` |
| ۸.۱ (انجام شد) | `components/panel/PanelKit.tsx` | گارد عضویت، منو و تب موبایل سازمان بر اساس عضویت، جابه‌جاکننده |
| ۸.۱ (انجام شد) | `tests/unit/panel-context.cjs` (جدید) | آزمون واحد |
| ۸.۲ | `lib/panel-access.ts` | حذف «مزایای سازمانی» از منوی شخصی وقتی پنل سازمان در دسترس است؛ `roleLinks` با لینک پنل سازمان بر اساس عضویت |
| ۸.۲ | `components/panel/CustomerPanel.tsx` (`CustomerBenefits`) | فقط یک کارت «به پنل سازمان بروید»، بدون اعتبار سازمانی در پنل شخصی |
| ۸.۲ | `components/marketplace/ApprovedFigmaHome.tsx` (`AccountMenu`) | آیتم «پنل سازمان» بر اساس عضویت — **منوی هدر مشترک است؛ قبل از تغییر، تأیید مالک طبق `docs/product/approvals.md`** |
| ۸.۳ | `backend/app/security.py` + `lib/role-permissions.json` | `reservation:create`/`reservation:read` برای نقش‌های سازمانی (یا مهاجرت نقش‌ها) + آزمون |
| ۸.۳ | `backend/app/main.py` (departments/cost-centers/approval-templates) | گارد با `roles.manage` سازمانی |
| ۸.۳ | `backend/tests/test_enterprise_*.py` | آزمون «یک نفر: مشتری + کارمند سازمان الف + مدیر سازمان ب» |
| ۸.۴ | `e2e/` | Playwright: ورود یک کاربر دو-زمینه‌ای، رفت‌وبرگشت بین دو پنل، هیچ 403 در صفحه‌های مجاز، هیچ دادهٔ سازمانی در پنل شخصی |

## ۴. فهرست کارها به ترتیب (اندازه: S ≤ نیم روز، M ≤ ۲ روز، L > ۲ روز)

1. **[S] انتشار main فعلی** (#97–#101 و همین شاخه پس از ادغام) با `deploy/karenseir-deploy-server.sh --check` و بعد اجرا — **نیاز به تأیید صریح مالک برای migration 77 و انتشار.**
2. **[S] QA زنده پس از انتشار:** HTTPS (گواهی، ریدایرکت)، `build_info.json` = HEAD، صفحه‌های Stitch کنار PNG.
3. **[S] پیامک:** پیگیری کد 430 و قالب تولیدی (مالک) ← یک ارسال آزمایشی ← `sms_notifications` = LIVE.
4. **[S] مورد ۸.۲:** پاک‌کردن سازمان از پنل شخصی + لینک پنل سازمان در منو.
5. **[M] مورد ۸.۳:** مجوز خرید شخصی برای نقش‌های سازمانی + گاردهای سازمانی بک‌اند + آزمون‌ها.
6. **[S] مورد ۷:** فرم درخواست روی صفحهٔ هتل‌ها و صفحه‌های بدون تأمین‌کننده؛ تنظیم `SALES_DESK_PUBLIC_TENANT`؛ آزمون سرتاسری.
7. **[M] مورد ۶:** با رسیدن merchant_id اینجاست: تنظیم env، تراکنش واقعی کوچک با تأیید مالک، تطبیق.
8. **[M] مورد ۵:** ثبت آژانس‌های قراردادی و تورها؛ خرید تور با درگاه زنده یا درخواست.
9. **[L] مورد ۳:** آداپتور خرید ماهان پشت `flight_port` و فلگ، بعد از دسترسی Production ماهان.
10. **[L] مورد ۴:** آداپتور اقامت۲۴ بعد از رسیدن کلید و مستند.
11. **[M] مورد ۱:** لوگو (بعد از انتخاب) و Stitch بقیهٔ صفحه‌های داخلی.
12. **[M] مورد ۸.۴:** e2e دو-زمینه‌ای.

## ۵. کارهایی که فقط مالک می‌تواند انجام دهد

- تأیید انتشار `main` و migration `20261112_77`.
- کاوه‌نگار: معنی کد 430 از پنل/پشتیبانی، تأیید قالب تولیدی، شمارهٔ مجاز آزمایش.
- اینجاست: merchant_id، ثبت IP `188.121.123.218`، تأیید یک تراکنش واقعی. یا قرارداد PSP و نظر حقوقی ونداپی.
- ماهان: ارسال نتایج گواهی، گرفتن دسترسی Production.
- اقامت۲۴: کلیدها و مستند API.
- فهرست آژانس‌های قراردادی و تورهایشان.
- انتخاب لوگو (کانسپت‌های v2).
- تصمیم دربارهٔ مدل نقش (۸.۳): «همه کاربران `customer` + مجوز سازمانی» یا «افزودن خرید شخصی به نقش‌های سازمانی».
- تأیید هر تغییر در منوی هدر مشترک (`AccountMenu`).

## ۶. معیار پذیرش هر مورد

1. `curl -I http://karentravel.ir` ← 301 به https؛ گواهی معتبر عمومی؛ لوگوی انتخاب‌شده در هدر/فوتر/فاوآیکون؛ هر صفحهٔ داخلی Stitch کنار PNG طرح روی سایت زنده مقایسه و در `docs/qa/` ثبت شده؛ صفحهٔ اول و جست‌وجو بدون تغییر بصری.
2. کاربر واقعی با شمارهٔ خود کد می‌گیرد و وارد می‌شود؛ لاگ ارسال موفق کاوه‌نگار؛ در خطا پیام روشن و بدون قفل سراسری.
3. جست‌وجوی پرواز ماهان با نتیجهٔ واقعی؛ رزرو و پرداخت واقعی و صدور بلیت با تأیید مالک؛ در نبود دسترسی، بسته (fail-closed) با پیام و فرم درخواست.
4. نتایج هتل اقامت۲۴ واقعی با قیمت از سرور؛ رزرو با درگاه؛ تا رسیدن کلید، فرم درخواست.
5. دست‌کم یک آژانس قراردادی با تور واقعی منتشرشده؛ مشتری می‌بیند و می‌خرد یا درخواست می‌دهد.
6. یک تراکنش واقعی موفق و یک ناموفق با تطبیق درست؛ بدون credential، دکمهٔ پرداخت بسته و توضیح‌دار.
7. درخواست از سایت ← پرونده در میز فروش ← پیشنهاد قیمت به مشتری؛ بدون `SALES_DESK_PUBLIC_TENANT` پیام «فعال نشده» (نه موفقیت جعلی).
8. یک کاربر «مشتری + کارمند سازمان الف + مدیر سازمان ب»: در `/account` فقط دادهٔ شخصی؛ جابه‌جاکننده او را به پنل سازمان می‌برد؛ صفحه‌های مجاز بدون 403؛ صفحه‌های غیرمجاز «دسترسی ندارید»؛ برگشت به حساب شخصی بدون خروج و بدون از دست رفتن سبد؛ مشتری عادی هیچ جابه‌جاکننده‌ای نمی‌بیند؛ آزمون واحد و e2e سبز.

## ۷. QA این شاخه

- `node tests/unit/panel-context.cjs` ← PASS؛ `node tests/unit/panel-access.cjs` ← PASS (بدون تغییر رفتار نقش‌ها).
- `tsc --strict` روی `lib/panel-context.ts` و `lib/panel-access.ts` ← بدون خطا. بررسی نحوی `PanelKit.tsx` ← ۰ خطا.
- **اجرا نشد:** `tsc` کامل پروژه، `eslint` و `next build` (`node_modules` در این محیط نصب نیست)؛ e2e؛ بررسی بصری. باید در CI یا روی سرور پروژه اجرا شود.

## ۸. شاخهٔ `feat/launch-v1-panels-requests` (روی همین شاخه، ۲۴ نوامبر ۲۰۲۶ / ۳ آذر ۱۴۰۵)

محیط: **Source**. سرور Production دست نخورد. وضعیت: `DONE_IN_SOURCE` (روی سایت زنده دیده نشده).

- **۸.۲ (پنل شخصی بدون دادهٔ سازمانی):** `lib/panel-access.ts` (`ORG_LINKED_PERSONAL_PAGES`، گزینهٔ `orgPanel` در `navFor`/`mobileTabsFor`): وقتی پنل سازمان برای کاربر وجود دارد «مزایای سازمانی» از منو و تب موبایل پنل شخصی حذف می‌شود. `components/panel/CustomerPanel.tsx`: `CustomerBenefits` فقط یک کارت با لینک پنل سازمان است؛ کارت «اعتبار سازمانی» از کیف پول شخصی هم برداشته شد. `/me/organization-credit` دیگر در پنل شخصی خوانده نمی‌شود (در میز کار کارمند `/employee` می‌ماند).
- **۷ (فرم درخواست فروش آفلاین):** `components/customer/OfflineRequest.tsx` با پیام صریح «رزرو آنلاین … هنوز فعال نیست» روی `/hotels`، صفحهٔ هر هتل (فقط وقتی `request.online_booking` نیست)، `/villas`، `/flights`، `/car-rental`، `/tourist-transport`. سفر دریایی و ویزا از قبل فرم داشتند (`ServiceIntro`). `lib/trip-request.ts`: «درخواست رسید» فقط با پاسخ 2xx و `{received: true}`؛ 503 ← «ثبت آنلاین درخواست هنوز فعال نشده است — درخواست شما ثبت نشد» + تلفن پشتیبانی؛ مقادیر فرم در خطا پاک نمی‌شود.
- صفحهٔ اول، صفحهٔ جست‌وجو، `globals.css`، `ApprovedFigmaHome.tsx` و بک‌اند تغییر نکرد.
- **QA:** `node tests/unit/panel-access.cjs`، `panel-context.cjs`، `trip-request.cjs` (جدید) ← PASS؛ `npx tsc --noEmit` ← ۰ خطا؛ `npm run lint` ← ۰ خطا (فقط هشدارهای قبلی)؛ `npm run build` ← موفق؛ `pytest tests/test_sales_desk.py tests/test_panel_access_registry.py` ← ۸ PASS؛ `next start` محلی: `/hotels`، `/villas`، `/flights`، `/car-rental`، `/tourist-transport` ← 200 با بخش درخواست. **اجرا نشد:** e2e Playwright، بررسی بصری، آزمون سرتاسری با `SALES_DESK_PUBLIC_TENANT` روی سرور.
- **منتظر مالک:** آیتم «پنل سازمان» بر اساس عضویت در منوی هدر مشترک (`AccountMenu` در `ApprovedFigmaHome.tsx`) و `roleLinks`؛ تنظیم `SALES_DESK_PUBLIC_TENANT` روی سرور (یا وجود tenant مشتری)؛ اپ مشتری (`components/customer-app/Screens.tsx`) و checkout هنوز اعتبار سازمانی را نشان می‌دهند — تصمیم جداگانه.

## ۹. شاخهٔ `feat/org-panel-stitch` (روی #105 ← #104، ۲۴ نوامبر ۲۰۲۶ / ۳ آذر ۱۴۰۵)

محیط: **Source**. سرور Production دست نخورد. وضعیت: `DONE_IN_SOURCE`.

- **Stitch پنل سازمان:** داشبورد `/organization` (`b2b_1`/`b2b_2`)، اعتبار `/organization/credit` و صورتحساب `/organization/billing` (`_23`)، تأیید سریع `/organization/requests?request=<id>` (`_26`). فقط دادهٔ API؛ بخش‌هایی که API ندارد حذف شده‌اند. شرح و تصویرها: `docs/qa/2026-11-24-org-panel/`.
- **۸.۴ (انجام شد در Source):** `e2e/panels/dual-context.spec.ts` ← ۴ PASS.
- رفع: «سوابق و گردش تأیید» برای مدیرِ با عضویت دیگر `/organization/overview` (گارد نقش) را صدا نمی‌زند؛ `OrgScope` پیش‌فرض را سازمانی با مجوز لازم می‌گذارد.
- **مانده:** مقایسهٔ صفحهٔ زنده کنار PNG پس از انتشار؛ بازطراحی `/employee` (طرح Stitch جدا ندارد)؛ ۸.۳ بک‌اند.
