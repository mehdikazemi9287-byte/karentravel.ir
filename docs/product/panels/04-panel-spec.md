# مشخصات کامل پنل‌های کارن تراول (کارن‌سیر / KarenSeir)

- نسخه: 1.0 (پیش‌نویس برای تأیید مالک)، ۱۷ آبان ۱۴۰۵ (2026-11-08)
- مخزن: `mehdikazemi9287-byte/karentravel.ir`، شاخه `production` (`3c7f504`)
- ورودی‌ها: `docs/product/panels/01-panel-audit` (ممیزی کد)، `02-panel-research` (پژوهش رقبا)، `03-tax-b2b-research` (مالیات، مودیان، مجوز، چارتر، B2B)، `security-review/REPORT.md`، `karentravel-master-spec-v3.1-FROZEN.md`، `INFORMATION_ARCHITECTURE.md`، `DESIGN_SYSTEM.md`، `components/panel/PanelKit.tsx` + `panel.css`، `backend/app/security.py` و مسیرهای backend.
- علامت‌ها: ✅ = endpoint موجود (مسیر واقعی در backend). 🆕 = endpoint پیشنهادی که باید ساخته شود. 🔧 = موجود ولی نیاز به اصلاح (امنیت یا scope). **P0** = لازم برای پایلوت. **P1** = نسخه‌های اول پس از پایلوت. **P2** = بعدتر.
- اصل بالادستی: Spec ≠ Implementation (Master Spec V3.1). هر چیزی که اینجا 🆕 است تا وقتی کد، تست و شواهد QA نداشته باشد «انجام‌شده» گزارش نمی‌شود.

## 0. تصمیم‌های قطعی مالک (قیود همهٔ بخش‌ها)

| # | تصمیم | پیامد در این سند |
|---|---|---|
| D1 | **B2B اولویت درجه‌یک است.** آژانس‌های قراردادی و چارترکننده‌ها پرواز (بلوک صندلی چارتر)، تور و هتل خود را دستی، با فایل یا با وب‌سرویس (API) منتشر می‌کنند. روابط بین‌آژانسی (زیرمجموعه، اعتبار، markup، کمیسیون، تسویه، اختلاف) کامل پوشش داده می‌شود. | §2.6 و §2.7 و فاز ۲ |
| D2 | ارزش افزودهٔ آژانس در **مدل نماینده (AGENT)** فقط روی کمیسیون و کارمزد خدمات است. **مدل اصیل (PRINCIPAL)** (پکیج تور، فروش مجدد چارتر) با پرچم «نیازمند تأیید حسابدار» پیاده می‌شود. مودیان: **الگوی ۶ نوع اول** برای بلیت هواپیما و **برگشت از فروش** برای استرداد، از طریق صف (Outbox). | §3 و §2.10 و فاز ۵ |
| D3 | نام و نشانی آژانس‌های دیگر روی صفحهٔ عمومی تورها نمایش داده **نمی‌شود**. پرسش حقوقی دربارهٔ الزام افشای برگزارکننده باز است (OQ-L2). | قاعدهٔ R-PUB-1 در §2.6؛ تست API |
| D4 | مشتری هرگز به سایت دیگری فرستاده نمی‌شود. همهٔ مراحل (خرید، پرداخت، واچر، پشتیبانی، استرداد) داخل کارن تراول انجام می‌شود. | قاعدهٔ R-OUT-1 در §1 |
| D5 | قیمت و موجودی هرگز ساختگی نیست. دادهٔ نمایشی برچسب «نمونه» دارد. | `Unavailable` و `MockLabel` در §1 |
| D6 | صفحهٔ اصلی و تجربهٔ بصری جست‌وجو (`ApprovedFigmaHome.tsx`، `approved-figma.css`، `HomeSearchExperience.tsx`، `JalaliCalendar.tsx`، `/search/results`) تغییر **نمی‌کنند**. پنل‌ها فقط با توکن‌های PanelKit و `panel.css` (پالت plum و coral) ساخته می‌شوند. | §1.1 |
| D7 | هر صفحهٔ جدید اول در Figma طراحی می‌شود (فایل `Ei8MUR9VN2yCX6BLOpvTXm` KarenSeir)، بعد پیاده‌سازی و دیپلوی. | §5 |
| D8 | فروش چارتر داخلی پشت feature flag `charter_domestic_sale` است و تا تأیید قانونی **خاموش** می‌ماند. | §2.7 و §4 |

---

# ۱. اصول مشترک همهٔ پنل‌ها

## ۱.۱ یک پوستهٔ واحد (Panel Shell)

**وضعیت فعلی:** سه پوسته وجود دارد (`PanelShell`، `JourneyShell` و `Shell` عمومی) و سه پالت. ناوبری به نقش وابسته نیست (ناحیهٔ admin ۳۱ لینک دارد). هیچ guard سمت سرور برای مسیرها وجود ندارد.

**هدف:** همهٔ صفحه‌های پنل (مشتری، سازمان، آژانس، تأمین‌کننده و کارکنان) فقط داخل `PanelShell` رندر می‌شوند. `JourneyShell` فقط برای صفحه‌های عمومی سفر می‌ماند.

| جزء | مشخصات |
|---|---|
| ساختار دسکتاپ (≥ 1024px) | sidebar در **سمت راست** با عرض 264px، چسبان (sticky)، پس‌زمینه `--pn-plum` و آیتم فعال `--pn-coral`. گروه‌بندی منو با عنوان گروه. دکمهٔ جمع‌کردن sidebar (حالت آیکون و برچسب کوتاه، ذخیره در `localStorage`). نوار بالا: عنوان صفحه، breadcrumb، جست‌وجوی سراسری (فقط کارکنان)، زنگ اعلان، انتخاب‌گر حساب یا سازمان یا آژانس (scope picker)، منوی کاربر. |
| تبلت (700 تا 1023px) | sidebar به‌صورت drawer از راست باز می‌شود (دکمهٔ منو). نوار بالا ثابت. |
| موبایل (< 700px) | **نوار پایین ۴ یا ۵ مقصدی** (`mobilePrimary` در registry) به‌علاوهٔ دکمهٔ «بیشتر» که drawer کامل منو را باز می‌کند. اقدام اصلی صفحه (مثلاً «ثبت درخواست استرداد») در یک نوار چسبان بالای bottom nav می‌آید. چیپ‌های افقی ۳۱تایی فعلی حذف می‌شوند. |
| فایل‌ها | `components/panel/PanelKit.tsx` (پوسته)، `components/panel/panel.css` (توکن‌ها)، 🆕 `components/panel/nav-registry.ts`، 🆕 `components/panel/PanelGuard.tsx`، 🆕 `components/panel/{Timeline,StatusChip,Skeleton,Drawer,DataTable,MoneyBreakdown,ConfirmMoney,JalaliDateField,FileImport}.tsx` |
| جداسازی از صفحهٔ محافظت‌شده | `PanelShell` امروز `AccountMenu` را از `ApprovedFigmaHome.tsx` import می‌کند. 🆕 یک `components/panel/PanelAccountMenu.tsx` مستقل ساخته شود (کپی رفتار، نه ویرایش فایل محافظت‌شده). همین کار برای `ApprovedHeader/Footer` در صفحه‌های پنلی که امروز JourneyShell دارند. |

**توکن‌ها:** فقط `--pn-*` موجود (`--pn-ink #2a1530`، `--pn-plum #3a1b3d`، `--pn-coral #ef5b3d`، `--pn-cream #fdf5ea`، `--pn-surface #fffcf9`، `--pn-line #eadfd2`، `--pn-muted #6e5e70`، `--pn-gold #b98319`). 🆕 لایهٔ semantic روی آن‌ها: `--pn-ok`، `--pn-warn`، `--pn-bad`، `--pn-info`، `--pn-focus` و `--pn-radius-*`، تا white label بتواند فقط توکن را عوض کند (DESIGN_SYSTEM §Themeability). `globals.css` و فایل‌های محافظت‌شده دست نمی‌خورند. `DESIGN_SYSTEM.md` با بخش «توکن‌های پنل» به‌روز می‌شود.

**قاعدهٔ R-OUT-1 (D4):** هیچ لینک خروجی به سایت تأمین‌کننده، آژانس یا ایرلاین در پنل مشتری، واچر یا اعلان نمی‌آید. لینک‌های پشتیبانی، پرداخت، واچر و پیگیری همه به دامنهٔ کارن تراول اشاره می‌کنند. یک تست lint (`tests/panel/no-external-links.spec.ts` 🆕) همهٔ `href`های پنل مشتری را بررسی می‌کند و فقط مسیرهای نسبی، `tel:` و `mailto:` پشتیبانی خودمان را مجاز می‌داند.

## ۱.۲ رجیستری واحد ناوبری (Nav Registry)

یک منبع واحد جای `NAV` داخل `PanelKit.tsx` و `roleLinks()` در `lib/role-navigation.ts` و دکمه‌های `/backoffice` را می‌گیرد.

```ts
// components/panel/nav-registry.ts  (🆕)
export type Area = 'customer'|'organization'|'agency'|'supplier'|'ops'|'finance'|'admin';
export type NavItem = {
  id: string;               // 'finance.refunds'
  area: Area;
  group: string;            // 'صف‌ها' | 'مالی' | ...
  label: string;            // برچسب فارسی
  href: string;             // '/finance/refunds'
  capability: string;       // 'refund:approve' — از /me/capabilities
  scope?: 'organization'|'agency'|'supplier';   // نیاز به عضویت فعال در این scope
  featureFlag?: string;     // 'charter_domestic_sale'
  mobilePrimary?: number;   // ترتیب در bottom nav (1..4)
  badge?: 'today'|'notifications'|`queue:${string}`;  // شمارنده از /panel/today
  priority: 'P0'|'P1'|'P2'; // صفحه‌هایی که هنوز ساخته نشده‌اند در build تولید نمایش داده نمی‌شوند
};
```

- `roleHome` و `roleLinks` از همین registry مشتق می‌شوند. `lib/role-navigation.ts` فقط wrapper می‌ماند.
- منو با `capabilities ∩ item.capability` و عضویت scope و flag فیلتر می‌شود. آیتمی که کاربر مجوزش را ندارد **نمایش داده نمی‌شود** (به‌جای 403 بعد از کلیک).
- 🆕 `GET /me/capabilities` → `{role, permissions[], memberships:{organizations[{id,name,grants[]}], agencies[{id,name,role,modules[]}], suppliers[{id,name,role}]}, feature_flags{}, tenant{slug,brand}}`. منبع آن `ROLE_PERMISSIONS` در `security.py` به‌علاوهٔ grants سازمانی (`enterprise.PERMISSIONS`)، `AgencyMembership` و `SupplierMembership` است. پاسخ ۶۰ ثانیه در حافظهٔ کلاینت cache می‌شود.
- تست: `tests/test_nav_registry.py` (هر `capability` در registry باید در `ROLE_PERMISSIONS` یا grants تعریف شده باشد) و یک Playwright smoke برای هر نقش (منو فقط آیتم‌های مجاز را نشان می‌دهد).

## ۱.۳ محافظ مسیر (Route Guard)

| لایه | رفتار |
|---|---|
| سرور (منبع حقیقت) | همان `require_permission`، `require_role`، عضویت‌ها و RLS موجود. هیچ تصمیم امنیتی به frontend سپرده نمی‌شود. |
| 🆕 `middleware.ts` | فقط بررسی وجود نشست برای `/account`, `/organization`, `/employee`, `/agency`, `/supplier`, `/backoffice`, `/finance`, `/admin` و redirect به `/login?redirect=`. پس از مهاجرت به کوکی HttpOnly (M-3)، نقش هم از کوکی امضاشده خوانده می‌شود. |
| 🆕 `PanelGuard` | داخل `PanelShell`. اگر آیتم registry صفحهٔ فعلی با capabilities کاربر نخواند، صفحهٔ «دسترسی ندارید» را نشان می‌دهد: نام مجوز لازم به فارسی، نقش فعلی، و دکمهٔ «بازگشت به خانهٔ پنل من» (الگوی Booking.com). درخواست داده‌ای ارسال نمی‌شود. |
| scope | صفحه‌های سازمان، آژانس و تأمین‌کننده تا انتخاب scope (اگر کاربر چند عضویت دارد) داده بارگذاری نمی‌کنند. scope انتخاب‌شده در `sessionStorage` و در query (`?org=`, `?agency=`) نگه داشته می‌شود. |

## ۱.۴ خانهٔ «امروز / کارهای منتظر» برای هر نقش

هر ناحیه صفحهٔ اول یکسانی دارد: **«امروز»**. بالای صفحه حداکثر ۴ کارت «کار منتظر» (هر کارت: شمارنده، توضیح یک‌خطی، دکمهٔ اقدام)، سپس کارت‌های اطلاعاتی نقش.

- 🆕 `GET /panel/today?area={area}&scope={id}` → `{items:[{key, level:'bad'|'warn'|'info', count, label, href, oldest_at, sla_due_at}], generated_at}`. این endpoint فقط شمارنده‌ها را از جدول‌های موجود جمع می‌کند و دادهٔ تازه نمی‌سازد. الگوی آن همان `GET /ops/dashboard` ✅ است که امروز همین شکل (`key/level/count/label`) را برمی‌گرداند.
- کارت‌ها به ترتیب: `bad` (SLA گذشته)، `warn`، `info`. وقتی هیچ کاری منتظر نیست: «کار منتظری ندارید» و یک اقدام اصلی.
- محتوای «امروز» هر نقش در بخش همان نقش در §۲ آمده است.

## ۱.۵ اجزای مشترک UI

| جزء | قواعد |
|---|---|
| `StatusChip` | واژگان واحد برای هر موجودیت (رزرو، پرداخت، درخواست خدمت، استرداد، تأیید، تسویه، مودیان، مجوز، انتشار موجودی). همیشه **متن + رنگ** (هرگز فقط رنگ). سبز: تأییدشده یا پرداخت‌شده. کهربایی: در انتظار یا در حال بررسی. قرمز: ناموفق یا ردشده. خاکستری: لغو یا منقضی. دیکشنری فعلی `STATUS` در PanelKit توسعه می‌یابد و به `components/panel/status-dictionary.ts` منتقل می‌شود. |
| `Timeline` | عمودی، جدیدترین پایین. هر گام: عنوان، بازیگر (مشتری، کارشناس، مالی، تأمین‌کننده، سیستم)، زمان جلالی و ساعت. **گام بعدی** با خط‌چین، همراه «مسئول» و **ETA** (از SLA). اگر ETA گذشته باشد: چیپ قرمز «تأخیر» و دکمهٔ «پیگیری» که یک case پشتیبانی متصل می‌سازد. برای رزرو، درخواست خدمت، استرداد، تأیید سازمانی، تسویه و انتشار موجودی استفاده می‌شود. |
| `Skeleton` | هم‌شکل با چیدمان (کارت، جدول، timeline). spinner تنها مجاز نیست. هر route یک `loading.tsx` دارد. |
| Empty | توضیح چرایی خالی بودن + یک اقدام اصلی (مثلاً «سفری ندارید ← جست‌وجوی پرواز»). |
| Error | ورودی کاربر حفظ می‌شود. دکمهٔ «تلاش دوباره» و «تماس با پشتیبانی» (با کد پیگیری خطا). پیام خام API نمایش داده نمی‌شود. 401 به ورود، 403 به `PanelGuard`. |
| `Unavailable` (موجود) | وقتی backend مقدار را برنمی‌گرداند یا سرویس بیرونی وصل نیست: «در دسترس نیست» با دلیل. **هرگز عدد ساختگی** (D5). |
| `MockLabel` 🆕 | هر دادهٔ نمونه (seed، دمو) نشان «نمونه، قابل خرید نیست» دارد. backend فیلد `is_sample` (یا `status="sample"` موجود در `Agency`) را برمی‌گرداند. |
| `DataTable` | توسعهٔ `Table` موجود: header چسبان، صفحه‌بندی سمت سرور (`limit/offset` یا cursor)، جست‌وجو، فیلترهای ذخیره‌شده، انتخاب ستون، خروجی CSV/Excel (فقط برای نقش‌های دارای `export:*`)، اقدام گروهی. در موبایل هر ردیف کارت می‌شود (الگوی `data-label` موجود). |
| `MoneyBreakdown` | جدول تفکیک مبلغ خط سفارش (§3) با نمای متفاوت برای هر نقش. |
| `ConfirmMoney` | هر اقدام پولی (استرداد، شارژ کیف پول، تسویه، تعدیل) قبل از ثبت یک خلاصه نشان می‌دهد: مبلغ (عدد و حروف)، مقصد (شبا با نام صاحب حساب، کیف پول یا درگاه)، دلیل، و اگر بالای آستانه باشد «نیازمند تأیید نفر دوم». |
| `JalaliDateField` | تاریخ ورودی جلالی با نمایش میلادی کمکی برای سفر خارجی. ورودی رقم فارسی و لاتین را می‌پذیرد. ذخیره ISO با منطقهٔ زمانی `Asia/Tehran`. جای همهٔ ورودی‌های `type=date` و رشته‌های ISO خام (مثلاً در `SupplierOfferEditor`) را می‌گیرد. از `JalaliCalendar.tsx` محافظت‌شده فقط **import** می‌شود و تغییری در آن داده نمی‌شود. |
| `FileImport` | بارگذاری CSV/XLSX با قالب قابل دانلود، پیش‌نمایش ۲۰ ردیف، اعتبارسنجی ردیف‌به‌ردیف (خطا با شماره ردیف و ستون)، اجرای خشک (dry run)، و سپس ثبت idempotent با `import_id`. |

## ۱.۶ قواعد زبان، عدد و جهت

- `lang="fa" dir="rtl"` در سطح سند (موجود). اعداد UI با `toLocaleString('fa-IR')` (تابع `fa()` موجود). مبالغ با جداکنندهٔ هزارگان و واحد صریح. **واحد ذخیره و محاسبه ریال (عدد صحیح)** است. واحد نمایش برای مشتری «تومان» و برای مالی و مودیان «ریال»، و برچسب واحد همیشه کنار عدد می‌آید.
- `<bdi>` یا `.pn-ltr` (موجود) برای PNR، شمارهٔ بلیت، شبا، شمارهٔ کارت، گذرنامه، ایمیل، کد رهگیری مودیان (تاکس‌آیدی)، شمارهٔ پرواز و کد IATA.
- مسیر پرواز در جهت خواندن است: مبدأ راست، مقصد چپ، و فلش به چپ. لوگو، تیک و ترتیب ارقام آینه نمی‌شوند.
- ورودی کد ملی با اعتبارسنجی checksum. موبایل با `inputmode="tel"`. OTP با `autocomplete="one-time-code"`.

## ۱.۷ دسترس‌پذیری و سالمندپسند

- WCAG 2.1 AA: کنتراست ≥ 4.5:1 برای متن (بررسی رنگ `--pn-muted` روی `--pn-cream` و اصلاح در صورت نیاز)، focus قابل‌مشاهده با `--pn-focus` (حلقهٔ coral با 3px)، کیبورد برای منو، جدول، drawer و dialog، و `aria-label` برای دکمه‌های فقط‌آیکون. نوار پایین با `nav aria-label`.
- سالمندپسند: متن بدنه حداقل 16px در پنل مشتری و کارمند (امروز 13 و 14px است)، هدف لمسی ≥ 44×44px، line-height ≥ 1.7، کلید «بزرگ‌کردن متن» (A+ تا 125٪، ذخیره در `localStorage`)، بدون اقدام فقط با hover، برچسب متنی کنار آیکون‌ها در bottom nav، پیام خطای صریح در کنار فیلد، و زمان‌بندی session با هشدار پیش از خروج.
- `prefers-reduced-motion` رعایت می‌شود. تست خودکار: `@axe-core/playwright` روی همهٔ صفحه‌های P0 در 1440 و 390.

## ۱.۸ مرکز اعلان

- زنگ در نوار بالا (و آیتم «اعلان‌ها» در منو) با شمارندهٔ نخوانده. Drawer با تب‌های «همه / نیازمند اقدام / سیستم». هر اعلان: عنوان، متن کوتاه، زمان نسبی و جلالی، **deep link به همان موجودیت** (رزرو، درخواست، تسویه)، و برچسب «تولیدشده با هوش مصنوعی» اگر AI متن را ساخته است (Master Spec §21).
- endpointها: `GET /me/notifications` ✅، `POST /me/notifications/{id}/read` ✅، 🆕 `POST /me/notifications/read-all`، `GET/PUT /me/notification-preferences` ✅ (PUT امروز فقط در NotificationCenter مرده صدا زده می‌شود؛ به `/account/notifications` منتقل شود)، `GET /me/notification-channels` ✅. پیامک و push تا وقتی وصل نیستند `Unavailable` هستند.
- کارکنان: اعلان رخداد صف (SLA نزدیک، case جدید تخصیص‌یافته) از همان مدل اعلان.

## ۱.۹ جست‌وجوی سراسری کارکنان

- فقط برای نقش‌های دارای `backoffice:read` یا `ledger:read`. میان‌بر `/` و `Ctrl+K`. یک کادر در نوار بالا.
- 🆕 `GET /staff/search?q=&types=` → نتایج گروه‌بندی‌شده: رزرو (کد رزرو، PNR، شمارهٔ بلیت)، مشتری (موبایل، کد ملی با ماسک، نام)، پرداخت (کد پیگیری زرین‌پال، authority)، درخواست خدمت، case، آژانس، تأمین‌کننده، صورتحساب (شماره، تاکس‌آیدی). جست‌وجو tenant-scoped است و هر جست‌وجو با `q` هش‌شده در audit ثبت می‌شود. کد ملی و موبایل در نتیجه ماسک می‌شوند تا کاربر روی ردیف کلیک کند (کلیک = رخداد audit «مشاهدهٔ پروندهٔ مشتری»).
- **P0** (حداقل: کد رزرو، موبایل، PNR).

## ۱.۱۰ گزارش ممیزی (Audit Log)

- همهٔ اقدام‌های تغییردهنده (پول، وضعیت، قیمت، مجوز، نقش، انتشار، flag) یک رخداد audit می‌نویسند: `actor_id`، نقش، `tenant_id`، scope، موجودیت و شناسه، اقدام، **before/after** (JSON diff بدون دادهٔ حساس خام)، IP، user-agent، `request_id` و زمان. append-only (بدون UPDATE و DELETE در سطح نقش دیتابیس).
- موجود: `GET /admin/audit-events` ✅، `/organization/audit` ✅ (`…/audit`)، audit در `PUT /admin/users/{id}/role` ✅. 🆕 فیلتر بر اساس موجودیت و بازیگر و بازهٔ تاریخ، و خروجی CSV برای `audit:read`.
- در هر صفحهٔ جزئیات (رزرو، درخواست، تسویه، آژانس) یک تب «سوابق» همان رخدادهای موجودیت را نشان می‌دهد: 🆕 `GET /audit/entities/{type}/{id}`.

## ۱.۱۱ قواعد عمومی رفتار

- **Maker-Checker:** هر اقدام پولی بالای آستانهٔ قابل تنظیم (`finance.dual_control_threshold_irr`، پیشنهاد پیش‌فرض ۵۰٬۰۰۰٬۰۰۰ ریال) و **همهٔ** شارژهای کیف پول و اعتبار دستی دو نفر لازم دارد. سازنده نمی‌تواند تأییدکنندهٔ خودش باشد (بررسی سمت سرور).
- **Idempotency:** هر POST پولی هدر `Idempotency-Key` دارد (الگوی `command_id` موجود در `RefundRecord` و `Invoice`).
- **منبع حقیقت مالی:** Internal Ledger + تطبیق PSP (ADR-009). وضعیت PAID، REFUNDED یا SETTLED از پاسخ frontend یا تأمین‌کننده قطعی نمی‌شود.
- **حذف static boilerplate:** کارت تکراری «وضعیت و دسترسی» و جملهٔ پایانی از همهٔ صفحه‌ها حذف می‌شود (P2-8 ممیزی).

---

# ۲. مشخصات هر نقش

قالب هر صفحه: **مسیر**، هدف، بخش‌ها و اجزا، داده (فیلدها)، اقدام‌ها (قاعده و مجوز)، حالت‌ها، endpointها، اولویت. برای پرهیز از تکرار: حالت‌های loading، empty و error همیشه طبق §1.5 هستند و فقط حالت‌های خاص صفحه ذکر می‌شوند.

## ۲.۱ مشتری / مسافر (`customer`)، ناحیهٔ `customer`، پایه `/account`

**اهداف:** دیدن سفر بعدی و کارهای منتظر، مدیریت رزرو بدون تماس تلفنی، درخواست لغو، تغییر یا استرداد با پیش‌نمایش جریمه، پیگیری پول با تاریخ مشخص (درس Flightio)، دریافت واچر و فاکتور، کیف پول، مسافران ذخیره‌شده.

**منو (registry):**
- **سفر:** امروز (`/account`) ★۱، سفرها و رزروها (`/account/bookings`) ★۲، تغییرات سفر، ویزا، مدارک مسافران
- **پول:** پرداخت و فاکتور، لغو و استرداد (`/account/refunds`) ★۳، کیف پول و اعتبار، مزایای سازمانی (فقط اگر عضو سازمان باشد)
- **من:** پروفایل و مسافران، ذخیره‌شده‌ها، درخواست‌های قطار و همکار، اعلان‌ها، امنیت ورود، پشتیبانی ★۴

(★ = جایگاه در bottom nav موبایل. ★۵ = «بیشتر»)

**قاعدهٔ امنیتی C-1:** مشتری **هیچ** انتقال وضعیت مستقیمی روی رزرو ندارد. `POST /reservations/{id}/commands` 🔧 برای نقش `customer` و `employee` فقط به `request_cancel` و `request_change` محدود می‌شود (یعنی ساخت `BookingServiceRequest`). انتقال‌های confirmed، issued، completed و refunded فقط با رخداد سیستمی (callback پرداخت، صدور تأمین‌کننده) یا نقش کارکنان انجام می‌شوند. تست رگرسیون: `tests/test_customer_cannot_transition.py`.

### صفحه‌ها

**C-01 `/account` (امروز)**، P0
- بخش‌ها: کارت «سفر بعدی» (مقصد، تاریخ جلالی، روزهای مانده، وضعیت، دکمه‌های واچر و مدیریت رزرو)؛ کارت‌های کار منتظر (پرداخت معوق، تغییر سفری که تأیید نشده، مدرکی که رد شده، درخواست استرداد در جریان با ETA، پرداخت ناموفق «پول کسر شد ولی رزرو نشد»)؛ موجودی کیف پول؛ ۴ اعلان آخر.
- داده: `reservation{id, code, service_type, title, start_at, status}`، `today.items[]`، `wallet.balance_irr`.
- endpointها: `/me/reservations` ✅، `/me/trips` ✅، `/me/notifications` ✅، `/me/wallets` ✅، 🆕 `GET /panel/today?area=customer`. 🔧 `GET /me/dashboard` (M-2: فیلتر به کاربر فعلی) یا حذف آن.

**C-02 `/account/bookings`**، P0
- تب‌ها: پیش رو، گذشته، لغوشده. چیپ نوع خدمت (پرواز، قطار، هتل، تور، اقامتگاه، ویزا، ...). جست‌وجو با کد رزرو و بازهٔ تاریخ. صفحه‌بندی.
- ستون‌ها و کارت: کد رزرو `<bdi>`، عنوان، تاریخ، مسافران (تعداد)، مبلغ کل، وضعیت.
- endpointها: `GET /me/reservations` 🔧 (افزودن `status_group`، `service_type`، `q`، `from`، `to`، `limit`، `offset`).
- یکسان‌سازی: `/trips` و `/saved-trips` به این صفحه و `/account/saved` redirect می‌شوند (P2-7).

**C-03 `/account/bookings/[id]`** (جای `/manage-booking/[id]` در پوستهٔ پنل؛ مسیر قدیم redirect می‌شود)، P0
- بخش‌ها:
  1. سرتیتر: کد رزرو، PNR و شمارهٔ بلیت `<bdi>`، وضعیت، دکمه‌های «واچر» و «فاکتور».
  2. **Timeline رزرو** (ثبت، پرداخت، صدور، تغییر، درخواست، استرداد) با گام بعدی و ETA.
  3. مسافران (نام فارسی و لاتین، نوع ADT/CHD/INF، کد ملی ماسک‌شده).
  4. **تفکیک مبلغ** (`MoneyBreakdown`، نمای مشتری §3.3).
  5. قوانین لغو: سیاست زمان خرید (snapshot) و سیاست جاری.
  6. درخواست‌های خدمت این رزرو با وضعیت و timeline هر کدام.
  7. پشتیبانی: case متصل (قاعدهٔ برنزی: یک case برای هر رزرو) و گفتگو داخل همین صفحه.
- اقدام‌ها:
  - «درخواست لغو یا استرداد»: wizard سه‌مرحله‌ای: انتخاب مسافر یا بخش ← **پیش‌نمایش جریمه** از `GET /reservations/{id}/cancellation-quote` ✅ (محاسبهٔ سمت سرور، M-1) ← مقصد وجه (کیف پول، یا شبای تأییدشده با نام صاحب حساب، یا برگشت به کارت از طریق درگاه اگر پشتیبانی شود) ← تأیید. ثبت: `POST /reservations/{id}/service-requests` ✅ با `request_type=cancel|refund`، `quote_id`، `refund_destination`. سرور باید quote را دوباره محاسبه و قفل کند (اعتبار ۱۵ دقیقه).
  - «درخواست تغییر» (تاریخ، نام، مسیر): `request_type=change` با توضیح. قیمت تفاوت را کارشناس اعلام می‌کند و مشتری در همین صفحه می‌پذیرد یا رد می‌کند: 🆕 `POST /service-requests/{id}/customer-decision`.
  - «انصراف از درخواست» تا وقتی وضعیت `submitted` است: 🆕 `POST /service-requests/{id}/withdraw`.
- حالت‌ها: رزرو غیرقابل لغو (دکمه غیرفعال با دلیل)؛ quote منقضی (محاسبهٔ دوباره)؛ پرواز چارتر (قواعد کنسلی سیستمی شامل آن نیست؛ متن سیاست چارتر نمایش داده می‌شود).
- endpointها: `/reservations/{id}` ✅، `/history` ✅، `/cancellation-quote` ✅، `/voucher` ✅، `GET/POST /service-requests` ✅، `GET /reservations/{id}/price-breakdown` ✅ (امروز بدون فراخوان)، `/me/reservations/{id}/voucher-qr` ✅، 🆕 `GET /reservations/{id}/timeline` (ادغام history، service-requests، refunds و تغییرات سفر).

**C-04 `/account/refunds` (لغو و استرداد)**، P0
- بخش‌ها: «درخواست‌های من» (همهٔ `BookingServiceRequest`های کاربر با وضعیت، مبلغ قابل استرداد، مقصد و ETA)؛ «پرداخت‌های ناموفق» (پرداخت کسرشده بدون رزرو، وضعیت برگشت خودکار و تاریخ)؛ «رزروهای قابل لغو» (لینک به C-03).
- وضعیت‌ها (واژگان واحد درخواست خدمت): `submitted` ثبت‌شده ← `under_review` در حال بررسی ← `waiting_supplier` در انتظار تأمین‌کننده ← `approved` تأییدشده ← `refund_queued` در صف پرداخت ← `refund_paid` پرداخت‌شده (کد پیگیری بانکی) ← `closed` بسته. شاخه‌ها: `rejected` ردشده (با دلیل)، `withdrawn` پس‌گرفته‌شده، `needs_customer` منتظر پاسخ شما.
- ETA: از SLA (بخش ۲.۹) و در صورت `refund_queued`، تاریخ وعدهٔ پرداخت مالی.
- endpointها: 🆕 `GET /me/service-requests?status=&limit=&offset=`، 🆕 `GET /me/refunds` (`RefundRecord`ها با `status`، `amount`، `destination`، `bank_reference`، `paid_at`)، 🆕 `GET /me/payments/failed`، `GET /me/payments` ✅.

**C-05 `/account/payments` (پرداخت و فاکتور)**، P0 برای مشاهده، P1 برای PDF
- جدول پرداخت‌ها (تاریخ، مبلغ، روش، کد پیگیری `<bdi>`، وضعیت)، فاکتورها (شماره، تاریخ، مبلغ قبل از مالیات، ارزش افزوده، جمع، **وضعیت مودیان** و تاکس‌آیدی وقتی ارسال شده باشد)، اقساط.
- اقدام: «دریافت فاکتور» (HTML قابل چاپ و PDF): 🆕 `GET /me/invoices/{id}/document?format=html|pdf`. فاکتور اطلاعات Licensed Entity (نام حقوقی، شمارهٔ مجوز، شناسهٔ مالیاتی، طبق Master Spec §13) را دارد. مشتری حقوقی (شرکت) «درخواست فاکتور رسمی با شناسهٔ ملی و اقتصادی» دارد: 🆕 `PUT /me/invoices/{id}/buyer` (فقط قبل از ارسال به مودیان).
- endpointها: `/me/payments` ✅، `/me/invoices` ✅، `/me/installments` ✅.

**C-06 `/account/wallet`**، P0 برای مشاهده
- موجودی، **تاریخچهٔ تراکنش** (`GET /wallets/{id}` ✅ امروز استفاده نمی‌شود)، اعتبار سازمانی، درخواست‌های خزانه.
- اقدام‌ها: «برداشت به شبا» (درخواست، نه انتقال مستقیم): `POST /me/treasury-requests` ✅ با `type=withdraw`؛ «شارژ آنلاین» از درگاه زرین‌پال وقتی وصل باشد (امروز `Unavailable`). **مشتری و مدیر سازمان هیچ مسیری برای افزایش مستقیم موجودی ندارند** (H-1): `POST /wallets/{id}/commands` 🔧 برای `credit` فقط با نقش `finance_operator` و maker-checker.
- endpointها: `GET/POST /me/wallets` ✅، `GET /wallets/{id}` ✅، `/me/organization-credit` ✅، `GET/POST /me/treasury-requests` ✅.

**C-07 `/account/profile`**، P0
- پروفایل (نام، کد ملی، ایمیل، تاریخ تولد جلالی)، شبای تأییدشده (نام صاحب حساب باید با نام کاربر یکی باشد؛ استعلام بانکی وقتی در دسترس باشد)، **دفتر مسافران**: افزودن، **ویرایش** (`PUT /me/travellers/{id}` ✅ بدون UI امروز)، حذف. فیلدها: نام فارسی و لاتین، کد ملی (checksum)، جنسیت، تاریخ تولد، ملیت، شماره و انقضای گذرنامه.
- بازنویسی روی PanelKit (حذف استایل navy و Tailwind) و بارگذاری تنبل بخش‌ها (امروز ۱۲ endpoint همزمان).
- endpointها: `/me/profile` ✅، `/me/travellers` ✅ (GET/POST/PUT، `/remove`)، `/me/bank-account` ✅.

**C-08 `/account/security`**، P1
- موجود: 2FA (TOTP) و کدهای بازیابی (`/me/2fa*` ✅). 🆕 فهرست نشست‌ها و دستگاه‌ها و «خروج از همه»: `GET /me/sessions`، `POST /me/sessions/revoke-all`.

**C-09 `/account/support`**، P0
- فهرست caseها و **گفتگو داخل پنل** (امروز در `/support` عمومی). ایجاد case از روی رزرو (پیش‌فرض) یا عمومی.
- endpointها: `GET/POST /support/cases` ✅، `GET /support/cases/{id}` ✅، `POST /support/cases/{id}/customer-replies` ✅.

**C-10 سایر صفحه‌های موجود** (ویزا، مدارک، تغییرات سفر، ذخیره‌شده‌ها، قطار، همکار، اعلان‌ها): همان قابلیت موجود، فقط مهاجرت به پوسته و اجزای واحد. موارد افزوده: «علامت همه خوانده» و toggle کانال‌ها در اعلان‌ها (P1)؛ رفع N+1 در تغییرات سفر با 🆕 `GET /me/trip-changes` (P1)؛ ویرایش و حذف itinerary در ذخیره‌شده‌ها (P2). همهٔ این‌ها P1.

**C-11 اپ موبایل `/app/*`** (PWA)، P0 برای رفع لینک مرده
- لینک «جست‌وجو» به `/` (جست‌وجوی صفحهٔ اصلی) یا `/search/results` اشاره کند (P0-5). در P1 اپ همان registry و bottom nav پنل مشتری را به کار می‌گیرد تا دو پوسته نداشته باشیم.

---

## ۲.۲ مدیر سازمان (`organization_admin`، و `welfare_manager`)، ناحیهٔ `organization`، پایه `/organization`

**اهداف:** تعریف کارکنان، سیاست سفر، ساختار و اعتبار؛ دیدن مصرف و صورتحساب؛ گزارش برای مدیریت؛ کنترل تأییدها.

**منو:** امروز ★، درخواست‌ها و تأییدها ★، رزروهای سازمان ★، کارکنان و دسترسی‌ها، سیاست سفر، واحدها و مراکز هزینه، قالب‌های تأیید، اعتبار و اقساط، صورتحساب و تسویه ★، گزارش‌ها، سوابق.

**قاعدهٔ امنیتی H-1:** مدیر سازمان **نمی‌تواند** کیف پول شارژ کند، حساب اعتباری بسازد یا سقف اعتبار تغییر دهد. این‌ها فقط با درخواست به مالی انجام می‌شوند: 🆕 `POST /organizations/{id}/credit-requests` (افزایش سقف، شارژ). `POST /organizations/{id}/credit-accounts` 🔧 و `POST /organization-credit/{id}/commands` 🔧 برای اقدام‌های افزایشی به `finance_operator` + maker-checker محدود می‌شوند. مدیر سازمان فقط **توزیع** اعتبار موجود بین واحدها و کارکنان را انجام می‌دهد (`PUT /enterprise/organizations/{org}/grants` ✅) و این توزیع از سقف قرارداد بیشتر نمی‌شود.

| کد | مسیر | هدف و بخش‌ها | داده و اقدام‌ها | endpointها | اولویت |
|---|---|---|---|---|---|
| O-01 | `/organization` | امروز: تأییدهای منتظر، اعتبار مصرف‌شده از سقف (نوار پیشرفت)، صورتحساب سررسیدشده، کارکنانی که امروز در سفرند (duty of care) | شمارنده‌ها | `/enterprise/context` ✅، `/enterprise/organizations/{org}/summary` ✅، 🆕 `/panel/today?area=organization&scope=org` | P0 |
| O-02 | `/organization/members` | کارکنان و خانواده: افزودن تکی، **ورود از فایل** (CSV/XLSX: نام، موبایل، کد ملی، واحد، مرکز هزینه، نقش، مدیر مستقیم)، غیرفعال‌سازی، نقش (`traveller`، `approver`، `purchasing_officer`، `org_finance`، `org_admin`) | `FileImport` با dry run | `GET/POST …/members` ✅، `…/members/{uid}/remove` ✅، `PUT …/grants` ✅، 🆕 `POST …/members/import` (dry_run=true|false)، 🆕 `POST …/members/{uid}/dependents` | P1 (import P1، فهرست P0) |
| O-03 | `/organization/policy` | سیاست سفر با **ویرایش در همین صفحه** (امروز در `/requests` است): خدمات مجاز، سقف بودجه، کلاس پرواز، ستارهٔ هتل، حداقل روز پیش از سفر، حداکثر روز، مقصدهای مجاز، نیاز به تأیید، تأییدکننده‌ها. نسخه‌ها و diff | `version`، `rules{}` | `GET/PUT …/policy` ✅، 🆕 `GET …/policy/versions` | P1 |
| O-04 | `/organization/structure` | واحدها و مراکز هزینه: فهرست، ویرایش، غیرفعال (امروز فقط فرم ایجاد) | | `POST /organizations/{id}/departments` ✅، `/cost-centers` ✅، 🆕 `GET/PUT/DELETE …/departments/{id}` و `…/cost-centers/{id}` | P1 |
| O-05 | `/organization/approval-templates` | قالب تأیید: مراحل (مدیر مستقیم، مدیر واحد، مالی سازمان)، آستانهٔ مبلغ برای مرحلهٔ بعد (Approve & Forward)، جانشین در غیبت | | `POST /organizations/{id}/approval-templates` ✅ (بدون UI)، 🆕 `GET/PUT …/approval-templates/{tid}` | P1 |
| O-06 | `/organization/requests` | همهٔ درخواست‌های سفر سازمان: فیلتر وضعیت، واحد، متقاضی. جزئیات با timeline تأیید | | `GET /enterprise/requests` ✅، `/{rid}` ✅ | P0 |
| O-07 | `/organization/bookings` | همهٔ رزروهای سازمان (نه فقط به تفکیک درخواست): مسافر، خدمت، تاریخ، مرکز هزینه، مبلغ، وضعیت. خروجی Excel | | 🆕 `GET /enterprise/organizations/{org}/bookings?from&to&cost_center&status` | P1 |
| O-08 | `/organization/credit` | سقف، مصرف، مانده، به تفکیک مرکز هزینه؛ تاریخچهٔ حرکات؛ دکمهٔ «درخواست افزایش سقف» (به مالی) | | `…/credit` ✅، `/me/installment-plans` ✅، 🆕 `POST …/credit-requests` | P0 |
| O-09 | `/organization/billing` | صورت‌حساب: فاکتورهای ماهانهٔ تجمیعی و تک‌رزرو، وضعیت پرداخت، **PDF** و Excel، وضعیت مودیان (نوع اول با شناسهٔ ملی و اقتصادی سازمان) | | `…/statement` ✅، 🆕 `GET …/statements/{period}/document`، `/finance/receivables` ✅ از سمت مالی | P1 |
| O-10 | `/organization/reports` | هزینه بر اساس کارمند، مرکز هزینه، خدمت و ماه؛ درون‌سیاست یا خارج سیاست؛ بازهٔ تاریخ و خروجی | | `…/summary` ✅ 🔧 (افزودن `from/to/group_by`) | P1 |
| O-11 | `/organization/audit` | گردش تأیید و سوابق | | `…/audit` ✅ | P0 (موجود) |
| O-12 | `/organization/profile` | پروفایل حقوقی: نام حقوقی، **شناسهٔ ملی، شمارهٔ اقتصادی، کد پستی (اجباری برای فاکتور نوع اول)**، قرارداد، مدیران | فقط خواندنی برای مدیر سازمان؛ ویرایش با `tenant_admin` یا عملیات | 🆕 `GET/PUT /enterprise/organizations/{org}/profile` | P0 |

`/organization/financial-context` به تب «سوابق مالی» در O-08 منتقل و با واژگان غیرفنی بازنویسی می‌شود (P2).

## ۲.۳ تأییدکننده / مدیر (`manager`)، ناحیهٔ `organization` با منوی محدود

**اهداف:** یک صندوق تأیید سریع با دلیل اجباری برای رد، و ارجاع به مرحلهٔ بعد.

**منو:** امروز (صندوق تأیید) ★، تاریخچهٔ تصمیم‌ها ★، سفرهای تیم من ★، سفرهای من (لینک به `/account`).

| کد | مسیر | جزئیات | endpointها | اولویت |
|---|---|---|---|---|
| A-01 | `/organization/approvals` | صندوق: هر ردیف متقاضی، مقصد، تاریخ، مبلغ برآوردی، **درون یا خارج سیاست** (با دلیل)، مانده اعتبار مرکز هزینه، مهلت تصمیم. اقدام‌ها: تأیید، رد (**دلیل اجباری**)، برگشت برای اصلاح (دلیل اجباری)، ارجاع به مرحلهٔ بالاتر. تصمیم گروهی فقط برای درخواست‌های درون‌سیاست. موبایل: کارت‌های swipe ممنوع؛ دکمه‌های صریح. | `POST /enterprise/requests/{rid}/decision` ✅، `POST /approvals/{id}/decision` ✅ و `/escalate` ✅ (بدون UI)، `/me/approval-workflows` ✅، 🆕 `GET /me/approvals/inbox` (ادغام هر دو نوع تأیید) | P0 (در فاز ۳) |
| A-02 | `/organization/approvals/history` | تصمیم‌های گذشته با فیلتر | 🆕 `GET /me/approvals/history` | P1 |
| A-03 | `/organization/team-trips` | چه کسی امروز کجاست؛ شمارهٔ تماس اضطراری (duty of care) | 🆕 `GET /enterprise/organizations/{org}/travelling-now` | P2 |
| A-04 | جانشینی | تعیین جانشین در بازهٔ مرخصی | 🆕 `PUT /me/approval-delegation` | P2 |

قاعده: تأییدکننده نمی‌تواند درخواست خودش را تأیید کند (سرور). درخواست تأییدنشده پس از مهلت به مرحلهٔ بعد ارجاع یا منقضی می‌شود (تنظیم قالب).

## ۲.۴ کارمند / مسافر سازمانی (`employee`)، پایه `/employee`

**اهداف:** ثبت درخواست سفر یا رفاهی، دیدن وضعیت تأیید، رزرو از اعتبار سازمان، سفرهای خودش. **منوی محدود** (امروز ۱۲ لینک مدیر را می‌بیند و بیشترش 403 است).

**منو:** امروز ★، درخواست سفر جدید ★، درخواست‌های من ★، اعتبار من، سفرهای من (`/account/bookings`) ★.

| کد | مسیر | جزئیات | endpointها | اولویت |
|---|---|---|---|---|
| E-01 | `/employee` | امروز: اعتبار من، درخواست‌های منتظر تأیید با گام بعدی (نام تأییدکننده و مهلت)، درخواست تأییدشده که هنوز رزرو نشده (دکمهٔ «رزرو کن») | `/me/organization-credit` ✅، `/me/approval-workflows` ✅، `/me/reservations` ✅ | P0 (فاز ۳) |
| E-02 | `/employee/requests/new` | فرم: نوع (سفر کاری یا رفاهی)، مقصد، تاریخ جلالی، تعداد، خدمات، بودجه، هدف سفر، مرکز هزینه. **بررسی زندهٔ سیاست** پیش از ارسال (هشدار خارج سیاست با دلیل) | `POST /enterprise/organizations/{org}/requests` ✅، 🆕 `POST …/requests/policy-check` | P0 (فاز ۳) |
| E-03 | `/employee/requests/[rid]` | timeline تأیید، گزینه‌های رزرو (booking candidates) با قیمت زنده، انتخاب و رزرو از اعتبار | `/enterprise/requests/{rid}` ✅، `/booking-candidates` ✅، `POST /bookings` ✅ | P0 (فاز ۳) |

## ۲.۵ مأمور خرید (`purchasing_officer`، grant سازمانی `requests.on_behalf`)

**اهداف:** رزرو برای چند نفر به نمایندگی (سفر گروهی، مهمان سازمان، تیم)، تقسیم هزینه به مرکز هزینه، و پیگیری همه تا صدور. در backend این قابلیت با grant `requests.on_behalf` در `enterprise.py` وجود دارد (`people` و `headcount`)، ولی نقش و UI جدا ندارد.

**مدل:** نقش جدید در ROLE_PERMISSIONS لازم نیست؛ `employee` یا `manager` با grant `requests.on_behalf` (و در صورت نیاز `rfq.manage`) در سازمان. registry آیتم‌های این بخش را با `scope=organization` و grant نشان می‌دهد.

**منو:** امروز ★، رزرو گروهی جدید ★، سبد‌های من ★، مسافران سازمان، درخواست قیمت (RFQ)، گزارش خرید.

| کد | مسیر | جزئیات | endpointها | اولویت |
|---|---|---|---|---|
| PO-01 | `/organization/purchasing` | امروز: سبدهای ناتمام، درخواست‌های منتظر تأیید، رزروهایی که مهلت پرداخت یا تکمیل نام دارند، پیشنهادهای RFQ رسیده | 🆕 `/panel/today?area=organization&role=purchasing` | P1 |
| PO-02 | `/organization/purchasing/new` | wizard: ۱) مسافران: انتخاب چندتایی از کارکنان، افزودن مهمان (نام، کد ملی یا گذرنامه، موبایل)، یا **ورود از فایل**؛ ۲) خدمت و جست‌وجو (همان موتور جست‌وجو، بدون تغییر بصری جست‌وجوی محافظت‌شده؛ نتایج در پنل با `UnifiedSearchView` موجود)؛ ۳) تخصیص هر مسافر به مرکز هزینه؛ ۴) بررسی سیاست برای هر مسافر؛ ۵) ارسال برای تأیید (یک درخواست با چند مسافر) یا رزرو مستقیم اگر سیاست اجازه دهد | `POST …/requests` ✅ (`people[]`, `headcount`)، 🆕 `POST …/requests/{rid}/travellers/import`، `POST /enterprise/requests/{rid}/bookings` ✅ | P1 |
| PO-03 | `/organization/purchasing/baskets/[rid]` | وضعیت هر مسافر (تأیید، رزرو، صدور، واچر)؛ اقدام گروهی: پرداخت از اعتبار، دانلود همهٔ واچرها (ZIP)، ارسال واچر به موبایل هر مسافر | 🆕 `GET /enterprise/requests/{rid}/travellers`، 🆕 `POST /enterprise/requests/{rid}/vouchers/send` | P1 |
| PO-04 | `/organization/purchasing/rfq` | درخواست قیمت از تأمین‌کنندگان برای گروه بزرگ: دعوت، مقایسهٔ پیشنهادها، انتخاب، انصراف | `/requests/{rid}/invitations` ✅، `/quotes` ✅، `/selection` ✅، `/withdraw` ✅ (همه بدون UI) | P1 |
| PO-05 | `/organization/purchasing/reports` | خرید به تفکیک مسافر و مرکز هزینه، خروجی Excel | از O-10 | P2 |

قواعد: مأمور خرید فقط در محدودهٔ واحدهایی که grant دارد عمل می‌کند (بررسی موجود در `enterprise.py:226`). مسافر مهمان (غیرکارمند) کد ملی یا گذرنامه لازم دارد. هر مسافر یک واچر جدا دارد و مأمور خرید نمی‌تواند به‌جای مسافر درخواست استرداد نقدی به شبای شخصی ثبت کند. استرداد به اعتبار سازمان برمی‌گردد.

---

## ۲.۶ آژانس همکار (B2B خریدار و فروشنده) و زیرمجموعه‌ها (`agency_partner`)، ناحیهٔ `agency`، پایه `/agency`

**وضعیت فعلی:** صفحه‌های فروش، رزرو، کمیسیون، اعتبار و تسویه خواندنی هستند. تورهای آژانس در `/supplier/tours` (Safarsaz) قرار دارند و SupplierMembership لازم دارند، پس آژانس 403 می‌گیرد. ایجاد زیرمجموعه فقط در `AgencyPortal` مرده است. مدل `Agency` فیلدهای `parent_agency_id`، `markup_bps`، `commission_bps`، `credit_account_id` و `supplier_id` دارد.

**دو نقش در یک پنل:**
- **آژانس خریدار (فروش موجودی ما):** موجودی کارن تراول را با markup خودش به مشتری خودش می‌فروشد، از اعتبار یا کیف پول آژانس پرداخت می‌کند و کمیسیون می‌گیرد.
- **آژانس فروشنده (موجودی خودش):** تور، هتل یا بلوک صندلی خودش را منتشر می‌کند. کارن تراول (تحت مجوز Licensed Entity) به مسافر می‌فروشد و با آژانس تسویه می‌کند.

**تصمیم مدل داده (رفع P0-4):** هر `Agency` که مجوز فروشنده دارد به‌طور خودکار یک `Supplier` مرتبط دارد (`Agency.supplier_id` موجود). دسترسی Safarsaz و موجودی برای کاربر عضو `AgencyMembership` با نقش ماژول `inventory` از طریق همین پیوند پذیرفته می‌شود (`safarsaz.py:236-250` 🔧). آژانس **هرگز** منوی تأمین‌کننده را نمی‌بیند. صفحه‌های موجودی زیر `/agency/inventory/*` قرار می‌گیرند و همان اجزای Safarsaz را بازاستفاده می‌کنند.

**نقش‌های داخلی آژانس** (الگوی Booking.com): `agency_owner` (همه چیز، از جمله کاربران و مالی)، `agency_sales` (فروش و رزرو)، `agency_inventory` (موجودی و قیمت)، `agency_finance` (اعتبار، تسویه، اختلاف). روی `AgencyMembership` 🆕 ستون `modules[]`. صفحه‌ای که ماژولش را ندارد با نام ماژول لازم بسته می‌شود.

**منو:**
- **امروز** ★
- **فروش (خریدار):** جست‌وجو و فروش ★، پیشنهادهای قیمت، رزروهای من ★، مشتریان من، قواعد markup من
- **موجودی من (فروشنده):** تورها، هتل و اقامت، پرواز و بلوک صندلی، ورود از فایل، وب‌سرویس (API)، رزروهای دریافتی ★، مانیفست
- **مالی:** حساب و اعتبار، کمیسیون، تسویه‌ها، اختلاف‌ها، فاکتورها
- **شبکه:** زیرمجموعه‌ها، کاربران آژانس
- **پروفایل و مجوزها**، پشتیبانی

### صفحه‌ها

**AG-01 `/agency` (امروز)**، P0
- کارت‌های منتظر: رزرو on-request دریافتی با تایمر SLA تأیید، مجوز در آستانهٔ انقضا (۳۰، ۱۵ و ۱ روز)، تسویهٔ منتظر تأیید دوطرفه، اختلاف باز، اعتبار نزدیک سقف (≥ ۸۰٪)، بلوک صندلی که release آن نزدیک است، تور ردشده در بازبینی.
- اطلاعات: فروش ۷ و ۳۰ روز، مانده اعتبار، کمیسیون معوق.
- endpointها: `/agency/workspace` ✅، `/agency/{id}/report` ✅، `/credit` ✅، 🆕 `/panel/today?area=agency&scope=agency`.

**AG-02 `/agency/profile` (پروفایل و مجوزها)**، P0
- پروفایل حقوقی: نام حقوقی، نام تجاری (فقط داخلی)، شناسهٔ ملی، شمارهٔ اقتصادی، کد پستی، مدیرعامل، مدیر فنی، شبا، قرارداد امضاشده (نسخه و فایل)، وضعیت (`PENDING_KYC` ← `ACTIVE` ← `SUSPENDED` / `TERMINATED`).
- **مجوزها** (`agency_license`): نوع (`BAND_ALEF`، `BAND_BE`، `BAND_PE`، `ONLINE_SALES_CAO`، `ONLINE_SALES_MCTH`، `ENAMAD`، `IATA`)، شماره `<bdi>`، مرجع، تاریخ صدور و انقضا (جلالی)، فایل اسکن، وضعیت تأیید (منتظر، تأییدشده، ردشده، منقضی).
- اقدام‌ها: بارگذاری یا تمدید مجوز (آژانس)؛ تأیید یا رد (فقط عملیات، OPS-12). ویرایش فیلدهای حقوقی پس از `ACTIVE` فقط با درخواست تغییر و تأیید عملیات.
- **قاعدهٔ سخت انتشار:** بدون `BAND_BE` معتبر تور منتشر نمی‌شود. بدون `BAND_ALEF` پرواز یا چارتر منتشر نمی‌شود. بدون `BAND_PE` تور زیارتی منتشر نمی‌شود. با انقضا، موجودی وابسته به‌طور خودکار `suspended` می‌شود (job روزانه) و آژانس و عملیات اعلان می‌گیرند.
- endpointها: `PUT /agency/agencies/{id}` ✅ 🔧 (فقط فیلدهای غیرحقوقی برای آژانس)، 🆕 `GET/POST /agency/{id}/licenses`، 🆕 `POST /agency/{id}/licenses/{lid}/files`، 🆕 `POST /agency/{id}/profile-change-requests`.

**AG-03 `/agency/sell` (جست‌وجو و فروش برای مشتری خودم)**، P1 (هستهٔ B2B خریدار)
- جست‌وجو در موجودی کارن تراول (همان API جست‌وجو، با `channel=agency&agency_id=`). در نتایج سه عدد نمایش داده می‌شود: **قیمت خالص آژانس** (net)، **markup من** (قابل ویرایش در همین سفارش در محدودهٔ قواعد)، **قیمت به مشتری**. سقف قیمت (`price_cap`) اعمال می‌شود و اگر قیمت مشتری از سقف بالاتر رود، فروش مسدود و پیام نمایش داده می‌شود.
- مسافران: انتخاب از «مشتریان من» یا ورود دستی.
- پرداخت: از **اعتبار یا کیف پول آژانس** (hold ← capture در صدور ← release در شکست)، یا لینک پرداخت داخل کارن تراول برای مشتری (D4: مشتری به سایت دیگری نمی‌رود؛ صفحهٔ پرداخت با برند آژانس فقط در حالت white label، فاز ۶).
- خروجی: واچر به نام مسافر. در واچر نام آژانس فروشنده (خریدار B2B) فقط اگر خودش بخواهد و قرارداد اجازه دهد.
- endpointها: `POST /search/v3` ✅ 🔧 (پارامتر کانال آژانس و بازگرداندن `net_irr`)، `/agency/{id}/offers` ✅، `POST /agency/{id}/quotes` ✅، `/quotes/{qid}/link-booking` ✅، 🆕 `POST /agency/{id}/bookings` (رزرو مستقیم با پرداخت از اعتبار، idempotent)، 🆕 `POST /agency/{id}/bookings/{rid}/payment-link`.

**AG-04 `/agency/sales` (پیشنهادهای قیمت)**، P0 (موجود)
- موجود: ایجاد، لغو، اتصال به رزرو. افزوده: نمایش net، markup و قیمت مشتری در هر پیشنهاد؛ انقضای پیشنهاد.

**AG-05 `/agency/bookings` و `/agency/bookings/[id]`**، P0
- فهرست رزروهای فروخته‌شده با فیلتر، و صفحهٔ جزئیات (امروز وجود ندارد): timeline، مسافران، **تفکیک مبلغ نمای آژانس خریدار** (§3.3)، وضعیت صدور، واچر (دانلود برای آژانس مجاز است چون فروشنده به مشتری خودش است؛ تصمیم امروز «فقط مشتری» با این تغییر می‌کند و نیاز به تأیید مالک دارد: OQ-O5).
- اقدام: «درخواست لغو یا تغییر برای مشتری» (همان `BookingServiceRequest` با `requested_by_agency=true`). استرداد به **اعتبار آژانس** برمی‌گردد، نه به مسافر؛ آژانس با مشتری خودش تسویه می‌کند.
- endpointها: `/agency/{id}/bookings` ✅، 🆕 `GET /agency/{id}/bookings/{rid}`، `POST /reservations/{id}/service-requests` ✅ 🔧 (پذیرش آژانس مالک فروش).

**AG-06 `/agency/customers`**، P1. موجود به‌علاوهٔ پروفایل مشتری (مسافران ذخیره‌شده آژانس، جدا از حساب کارن تراول مشتری). 🆕 `GET/POST /agency/{id}/customers/{cid}/travellers`.

**AG-07 `/agency/pricing` (قواعد markup من)**، P1
- قواعد markup آژانس برای مشتری خودش: به تفکیک نوع محصول، ایرلاین یا تأمین‌کننده، مسیر و بازهٔ تاریخ، درصد (bps) یا مبلغ ثابت، و حداقل و حداکثر. پیش‌نمایش روی یک نمونه قیمت واقعی.
- قاعده: markup آژانس هیچ‌گاه قیمت را از `price_cap` بالاتر نمی‌برد. markup تعریف‌شده توسط کارن تراول برای آژانس (`Agency.markup_bps` / `commission_bps`) فقط خواندنی است.
- endpointها: 🆕 `GET/POST/PUT /agency/{id}/pricing-rules`. سمت کارکنان: `/admin/commerce` ✅ (markup rules موجود).

**AG-08 `/agency/inventory/tours`**، P0 (فاز ۲)
- همان Safarsaz (`partner` mode) داخل پوستهٔ آژانس: ایجاد، کپی، ویرایش، برنامهٔ روزبه‌روز، خدمات شامل و غیرشامل، هتل هر شهر، حمل‌ونقل، تصاویر (بارگذاری فایل، نه فقط URL)، سیاست کنسلی ساختاریافته (`refund_policy`: پله‌های ساعت پیش از حرکت و درصد جریمه، `non_refundable`)، مدارک لازم، **`tax_role`** (پیش‌فرض `PRINCIPAL` برای پکیج، با برچسب «نیازمند تأیید حسابدار»)، و **`vat_category` هر جزء** (هتل ≤۳ ستاره معاف، قطار و اتوبوس معاف، پرواز داخلی مشمول، ...).
- حرکت‌ها (departures): تاریخ جلالی، ظرفیت، قیمت اتاق (یک‌تخته، دوتخته، کودک با تخت و بدون تخت، نوزاد)، مهلت تکمیل نام، توقف فروش.
- چرخهٔ انتشار: `draft` ← `submitted` (ارسال برای بازبینی) ← `published` یا `rejected` (با دلیل) ← `unpublished` / `expired`. بازبینی با عملیات (`/admin/safarsaz` ✅).
- **R-PUB-1 (D3):** API عمومی تور (`/catalog/tours*`، صفحهٔ تور، نتایج جست‌وجو، sitemap، JSON-LD) هیچ فیلدی از هویت آژانس (نام، نام تجاری، نشانی، تلفن، لوگو، شمارهٔ مجوز آژانس) برنمی‌گرداند. فروشندهٔ رسمی نمایش‌داده‌شده Licensed Entity (تاژبان) است. نام برگزارکننده فقط در قرارداد و واچر پس از خرید، **اگر** پاسخ پرسش حقوقی OQ-L2 آن را الزامی بداند. تست: `tests/test_public_tour_no_agency_identity.py` (پاسخ را برای همهٔ فیلدهای `Agency` و `Supplier` scan می‌کند).
- endpointها: `/safarsaz/tours*` ✅ (GET/POST/PUT، `/departures` ✅، `/submit` ✅، `/copy` ✅، DELETE departure ✅) 🔧 (پذیرش AgencyMembership)، 🆕 `POST /safarsaz/tours/{id}/media` (بارگذاری)، 🆕 `PUT /safarsaz/tours/{id}/departures/{dep}` (ظرفیت و توقف فروش).

**AG-09 `/agency/inventory/stays` (هتل و اقامت آژانس)**، P1
- قراردادهای اتاق آژانس با هتل (allotment): هتل از کاتالوگ مرجع، نوع اتاق، تقویم نرخ و ظرفیت، حداقل اقامت، release، سیاست کنسلی، `tax_role` (AGENT اگر به نام هتل فروخته شود؛ PRINCIPAL اگر آژانس خریده و ریسک کرده باشد) و `vat_category` (ستارهٔ هتل).
- endpointها: `/stays/contracts*` ✅ و `/stays/rooms/{id}/calendar` ✅ (امروز staff) 🔧 (scope به `owner_agency_id`؛ رفع H-2: تأمین‌کننده و آژانس فقط موجودی خودشان را می‌بینند).

**AG-10 `/agency/inventory/flights` (پرواز و بلوک صندلی، برای چارترکننده‌ها نیز)**، P0 (فاز ۲)، جزئیات در §2.7.

**AG-11 `/agency/inventory/import` (ورود از فایل)**، P1
- قالب‌های CSV/XLSX: `tour_departures`، `stay_rates`، `flight_seats` (پرواز، تاریخ، ساعت، کلاس، ظرفیت، نرخ ADT/CHD/INF، release). جریان `FileImport` (§1.5): بارگذاری ← اعتبارسنجی ← dry run با diff (چه چیزی ایجاد یا به‌روز می‌شود) ← ثبت. هر import یک `import_id`، گزارش خطا و قابلیت بازگشت (rollback تا پیش از اولین فروش) دارد.
- endpointها: 🆕 `POST /agency/{id}/inventory/imports` (multipart، `kind`، `dry_run`)، 🆕 `GET /agency/{id}/inventory/imports/{iid}`، 🆕 `POST …/imports/{iid}/commit`، 🆕 `POST …/imports/{iid}/rollback`. منطق مشترک با `data_exchange.py` ✅ و `/sources/{id}/import` ✅ موجود بازاستفاده شود.

**AG-12 `/agency/inventory/api` (وب‌سرویس)**، P1
- برای آژانس‌هایی که موجودی را از سامانهٔ خودشان (یا سپهر یا چارتر۷۲۴) **push** می‌کنند: کلیدهای API (ایجاد، چرخش، ابطال؛ نمایش فقط یک‌بار)، محیط sandbox، IP مجاز، webhook برای رخداد فروش و لغو، rate limit، لاگ ۱۰۰ درخواست آخر با کد پاسخ، و مستندات OpenAPI مخصوص شرکا.
- API شریک (🆕، نسخه‌دار `/partner/v1`): `PUT /partner/v1/flights/{external_id}` (بلوک صندلی)، `PUT /partner/v1/tours/{external_id}/departures/{external_id}`، `PUT /partner/v1/stays/{external_id}/calendar`، `GET /partner/v1/bookings?since=`، `POST /partner/v1/bookings/{id}/confirm|reject`. همهٔ ورودی‌ها از همان اعتبارسنجی پنل و همان قاعدهٔ مجوز می‌گذرند و موجودی تا تأیید اولیهٔ عملیات منتشر نمی‌شود (پس از تأیید اولیه، به‌روزرسانی ظرفیت و قیمت خودکار است؛ تغییر قیمت بالای آستانه دوباره بازبینی می‌شود).
- مدیریت کلید: 🆕 `GET/POST /agency/{id}/api-keys`، `POST /agency/{id}/api-keys/{kid}/revoke`، `GET/PUT /agency/{id}/webhooks`. کلید به‌صورت هش ذخیره می‌شود.
- API خروجی (آژانس از موجودی ما جست‌وجو و رزرو کند): P2، همان `/partner/v1/search|book|cancel`.

**AG-13 `/agency/inventory/bookings` (رزروهای دریافتی روی موجودی من)**، P0
- فهرست رزروهای مسافران روی تور، اتاق یا صندلی آژانس: کد، محصول، حرکت، مسافران، مبلغ خالص آژانس، وضعیت. برای موارد on-request: **تأیید یا رد با تایمر SLA** (پیش‌فرض ۲ ساعت کاری؛ پس از گذشت، case خودکار برای عملیات).
- **حریم مسافر:** آژانس فروشنده فقط اطلاعات لازم برای اجرا را می‌بیند (نام، نوع مسافر، کد ملی یا گذرنامه برای مانیفست، موبایل فقط اگر اجرای خدمت به آن نیاز دارد). ایمیل و سابقهٔ خرید مسافر نمایش داده نمی‌شود (H-2).
- endpointها: 🆕 `GET /agency/{id}/inventory/bookings`، 🆕 `POST /agency/{id}/inventory/bookings/{rid}/decision`، `POST /reservations/{id}/fulfill` ✅ 🔧 (scope مالک).

**AG-14 `/agency/inventory/manifest`**، P0
- مانیفست هر حرکت یا پرواز: مسافران، نوع، کد ملی یا گذرنامه، اتاق‌بندی؛ خروجی Excel و PDF؛ قفل مانیفست پس از مهلت تغییر نام.
- endpointها: `GET /inventory/flights/{id}/manifest` ✅ 🔧 (scope مالک، رفع H-2)، 🆕 `GET /safarsaz/tours/{id}/departures/{dep}/manifest`.

**AG-15 `/agency/credit` (حساب و اعتبار)**، P0
- سقف، مصرف، hold، مانده، تاریخچهٔ حرکات (`TOPUP`، `HOLD`، `CAPTURE`، `RELEASE`، `REFUND`، `COMMISSION`، `SETTLEMENT`). اقدام: «درخواست شارژ» (ثبت واریز بانکی با شمارهٔ پیگیری و تصویر رسید، یا پرداخت آنلاین) و «درخواست افزایش سقف». **شارژ فقط پس از تأیید مالی و maker-checker** (FIN-07) ثبت می‌شود.
- endpointها: `/agency/{id}/credit` ✅، 🆕 `POST /agency/{id}/topup-requests`، 🆕 `POST /agency/{id}/credit-limit-requests`. سمت کارکنان: `PUT /admin/partners/agencies/{id}/credit-account` ✅ 🔧 (maker-checker).

**AG-16 `/agency/commissions`**، P0 (موجود) + اقدام «اعتراض به ردیف» (به AG-18) و «درخواست صورتحساب کمیسیون».

**AG-17 `/agency/settlements` و `/agency/settlements/[id]`**، P0 (فاز ۲)
- تسویهٔ دوره‌ای (هفتگی، دوهفتگی یا ماهانه طبق قرارداد): ناخالص فروش، استردادها، کمیسیون کارن تراول، ارزش افزودهٔ کمیسیون، کسورات (جریمهٔ SLA، اختلاف)، **خالص قابل پرداخت به آژانس** (برای فروشنده) یا **بدهی آژانس** (برای خریدار اعتباری). ردیف‌به‌ردیف با لینک رزرو.
- **تأیید دوطرفه:** مالی صورت تسویه را صادر می‌کند ← آژانس «تأیید» یا «اعتراض» (ردیف‌به‌ردیف) ← پس از تأیید، مالی پرداخت را ثبت می‌کند (شمارهٔ پیگیری بانکی) ← بسته. مهلت تأیید آژانس (پیش‌فرض ۵ روز کاری) و پس از آن تأیید ضمنی (طبق قرارداد، OQ-O6).
- صورتحساب مودیان B2B (نوع اول) برای کمیسیون یا خرید بین آژانس‌ها در صف مودیان.
- endpointها: `/agency/{id}/settlements` ✅، 🆕 `GET /agency/{id}/settlements/{sid}` (ردیف‌ها)، 🆕 `POST /agency/{id}/settlements/{sid}/accept`، 🆕 `POST /agency/{id}/settlements/{sid}/disputes`.

**AG-18 `/agency/disputes`**، P1
- ثبت اختلاف (روی ردیف تسویه، رزرو، کمیسیون یا markup): دسته، مبلغ مورد اختلاف، شرح، پیوست. وضعیت: `open` ← `assigned` ← `waiting_agency` / `waiting_finance` ← `resolved` (با نوع حل: اصلاح، رد، تقسیم) ← `closed`. SLA طبق جدول case. ارتباط با Case Management (§2.9).
- endpointها: 🆕 `GET/POST /agency/{id}/disputes`، 🆕 `POST /disputes/{id}/messages`، 🆕 `POST /disputes/{id}/resolve` (مالی یا عملیات).

**AG-19 `/agency/network` (زیرمجموعه‌ها)**، P1
- ایجاد زیرمجموعه (امروز فقط در `AgencyPortal` مرده): نام، مدیر، **سقف اعتبار تخصیصی از اعتبار والد** (جمع سقف‌های زیرمجموعه ≤ مانده والد)، **قاعدهٔ تقسیم کمیسیون** (`commission_split_rule`: درصد سهم زیرمجموعه از کمیسیون والد)، markup اضافه‌شده توسط زیرمجموعه، وضعیت (فعال یا معلق).
- گزارش فروش هر زیرمجموعه، مانده اعتبار و بدهی. والد زیرمجموعه را معلق می‌کند؛ زیرمجموعه داده‌های والد یا هم‌سطحان را نمی‌بیند. عمق حداکثر ۲ سطح در P1.
- زیرمجموعه **مجوز جدا لازم دارد** اگر خودش موجودی منتشر کند؛ اگر فقط می‌فروشد، زیر مجوز والد یا Licensed Entity (OQ-L9).
- endpointها: `POST /agency/sub-agencies` ✅ (بدون UI)، `PUT /agency/agencies/{id}` ✅، 🆕 `GET /agency/{id}/sub-agencies`، 🆕 `PUT /agency/{id}/sub-agencies/{sid}/credit`، 🆕 `PUT …/commission-split`.

**AG-20 `/agency/users`**، P1. کاربران آژانس و ماژول‌ها. endpointها: `POST /agency/{id}/members` ✅، `DELETE /admin/partners/agencies/{id}/members/{uid}` ✅ (staff)، 🆕 `GET /agency/{id}/members`، 🆕 `PUT /agency/{id}/members/{uid}/modules`، 🆕 `DELETE /agency/{id}/members/{uid}` (فقط `agency_owner`).

**AG-21 `/agency/reports`**، P1. فروش به تفکیک محصول، حرکت و زیرمجموعه؛ ضریب اشغال؛ استردادها؛ بازهٔ تاریخ؛ خروجی. `/agency/{id}/report` ✅ 🔧 (`from/to/group_by`).

**AG-22 `/agency/support`**، P1. انواع case مخصوص آژانس: مشکل صدور، اختلاف قیمت، تغییر مانیفست، درخواست فنی API.

حذف: `/agency/workspace` (تکراری) به `/agency` redirect می‌شود (P2-7).

## ۲.۷ چارترکننده / مالک موجودی پرواز (`agency_partner` با مجوز `BAND_ALEF` و ماژول `inventory`)

چارترکننده در این سامانه یک آژانس با ماژول موجودی پرواز است (نه نقش جدا). صفحه‌ها زیر `/agency/inventory/flights`.

**موجود در backend:** `inventory.py` با `FlightSeries` (`flight_type=charter|system`، `supplier_id`، نرخ‌ها، ظرفیت)، `FlightInstance`، `generate`، مانیفست، و `charter_quotas.py` با `SeatQuota` (سهمیهٔ صندلی برای آژانس‌ها با `release_at`). این‌ها امروز فقط برای staff هستند (`/admin/inventory` و `/admin/charter-quotas`). بررسی admin/staff در `inventory.py:246-254` اجازهٔ ورود تأمین‌کننده را می‌دهد (H-2) که باید اصلاح شود.

| کد | مسیر | جزئیات | endpointها | اولویت |
|---|---|---|---|---|
| CH-01 | `/agency/inventory/flights` | فهرست سری‌ها و پروازهای من: مسیر، ایرلاین (چارتردهنده)، شمارهٔ پرواز `<bdi>`، تاریخ و ساعت، ظرفیت، فروخته‌شده، hold، مانده، release، وضعیت انتشار، **پرچم «چارتر داخلی: فروش آنلاین خاموش»** وقتی flag خاموش است | `GET /inventory/flight-series` ✅، `/inventory/flights` ✅ 🔧 (scope به `owner_agency_id`) | P0 |
| CH-02 | `/agency/inventory/flights/new` | فرم بلوک صندلی: مسیر (فرودگاه‌های مرجع)، ایرلاین چارتردهنده، شمارهٔ پرواز، نوع هواپیما، کابین و کلاس، بازهٔ تاریخ و روزهای هفته (سری) یا تاریخ تکی، ساعت، **ظرفیت قراردادی**، نرخ ADT/CHD/INF (هر جزء: نرخ پایه، مالیات و عوارض به تفکیک کد، جمع)، بار مجاز، **سیاست استرداد** (پله‌ها؛ و قاعدهٔ اجباری: لغو یا تأخیر بیش از ۲ ساعت از طرف ایرلاین = استرداد کامل)، مهلت تغییر نام، `release_at` (زمان برگشت صندلی‌های نفروخته)، `route_scope` (DOMESTIC یا INTERNATIONAL)، `tax_role=PRINCIPAL` (پیش‌فرض برای چارتر، با برچسب «نیازمند تأیید حسابدار»)، `vat_category`، **قرارداد چارتر با ایرلاین** (فایل) | `POST /inventory/flight-series` ✅ 🔧 (پذیرش آژانس مالک، اعتبارسنجی مجوز `BAND_ALEF`)، `/generate` ✅، 🆕 `POST /inventory/flight-series/{id}/contract-file` | P0 |
| CH-03 | `/agency/inventory/flights/[id]` | جزئیات پرواز: نمودار ظرفیت (فروخته، hold، سهمیهٔ آژانس‌ها، آزاد)، فروش‌ها، مانیفست، تغییر ظرفیت (کاهش فقط تا تعداد فروخته‌شده)، **توقف فروش**، اعلام **تغییر ساعت یا لغو پرواز** (که خودکار case برای همهٔ رزروها در Trip Operations Center می‌سازد و اعلان به مسافران می‌فرستد)، تغییر قیمت (برای فروش‌های بعدی؛ رزروهای قبلی snapshot دارند) | `PUT /inventory/flights/{id}` ✅ 🔧، `GET /inventory/flights/{id}/manifest` ✅ 🔧، 🆕 `POST /inventory/flights/{id}/disruption` (`type=time_change|cancel`, `new_time`) | P0 |
| CH-04 | `/agency/inventory/flights/[id]/quotas` | **سهمیه برای آژانس‌های دیگر** (فروش B2B بلوک به همکاران): آژانس گیرنده، تعداد، قیمت B2B، release | `GET/POST /charter-quotas` ✅، `/charter-quotas/{id}/release` ✅، `/charter-quotas/flights/{iid}` ✅ 🔧 (امروز فقط admin؛ مالک پرواز هم مجاز شود) | P1 |
| CH-05 | ورود از فایل و API | قالب `flight_seats` در AG-11 و `PUT /partner/v1/flights/{external_id}` در AG-12 | — | P1 |

**قواعد چارتر:**
- **FLAG `charter_domestic_sale` (D8):** وقتی خاموش است (پیش‌فرض)، پرواز `is_charter=true` و `route_scope=DOMESTIC` در جست‌وجو و فروش آنلاین B2C نمایش داده **نمی‌شود** و `POST /bookings` آن را رد می‌کند (کد خطای `CHARTER_DOMESTIC_DISABLED`). ثبت و نگهداری موجودی در پنل مجاز است و برچسب «فروش آنلاین غیرفعال تا تأیید قانونی» دارد. سهمیهٔ B2B بین آژانس‌ها (CH-04) هم برای چارتر داخلی پشت همین flag است. تغییر flag فقط با `platform_admin`، با دلیل و audit. تست: `tests/test_charter_domestic_flag.py`.
- نرخ کامل روی بلیت و واچر درج می‌شود (پایه، عوارض، جمع) و سیاست استرداد پیش از پرداخت به مسافر نمایش داده می‌شود (دستورالعمل چارتر).
- `price_cap` فعال: قیمت فروش (با markup کارن تراول و آژانس خریدار) از سقف اعلامی سازمان هواپیمایی بیشتر نمی‌شود.
- بلیت هم‌زمان با دریافت وجه صادر می‌شود؛ اگر صدور ممکن نشود، وجه کامل و بدون جریمه برمی‌گردد (case بحرانی خودکار).
- صندلی hold‌شده تا `release_at` و صندلی نفروخته پس از آن به‌طور خودکار release می‌شود (job موجود `released_reason`).

## ۲.۸ تأمین‌کننده / میزبان (هتل، ویلا، راهنمای تور، جاذبه)، `supplier`، پایه `/supplier`

**قاعدهٔ امنیتی H-2:** تأمین‌کننده فقط منابع خودش (از طریق `SupplierMembership`) را می‌بیند و تغییر می‌دهد. هیچ مسیر staff-only (`inventory.py:246-254`، قالب قرارداد، گزارش فروش کامل، مانیفست دیگران) برای نقش `supplier` باز نیست. تست: `tests/test_supplier_scope.py` (تأمین‌کنندهٔ A به منبع B → 404).

**منو:** امروز ★، خدمات و قیمت ★، تقویم و ظرفیت ★، سفارش‌ها و تأیید ★، کنترل ورود، درخواست‌های سازمانی (RFQ)، نظرها، تسویه و قرارداد، گزارش، پروفایل و مدارک، پشتیبانی.

| کد | مسیر | جزئیات | endpointها | اولویت |
|---|---|---|---|---|
| S-01 | `/supplier` | امروز: درخواست‌های on-request با تایمر، سفارش‌های پرداخت‌شدهٔ منتظر اجرا، ورودهای امروز (check-in)، تسویهٔ منتظر تأیید، مدرک یا قرارداد منقضی، نظر بی‌پاسخ | `/supplier/dashboard` ✅، `/supplier/reservations/ready` ✅، 🆕 `/panel/today?area=supplier` | P0 |
| S-02 | `/supplier/onboarding` | ثبت تأمین‌کننده: اطلاعات حقوقی، شناسهٔ ملی و اقتصادی، مجوز (بند ب برای راهنما و تور، مجوز بهره‌برداری اقامتگاه)، شبا، قرارداد، مدارک. وضعیت تا تأیید عملیات «در انتظار» است و موجودی منتشر نمی‌شود | `POST /supplier/onboarding` ✅ (فقط در UI مرده)، `PUT /backoffice/suppliers/{id}/lifecycle-status` ✅ (سمت عملیات) | P1 |
| S-03 | `/supplier/services` و `/supplier/services/[id]` | فهرست خدمات با **ویرایش، غیرفعال‌سازی و توقف فروش** (امروز فقط خواندنی). ویرایشگرها (`/supplier/offers/new` و انواع) داخل پوستهٔ پنل با `JalaliDateField` به‌جای ISO خام. تصاویر با بارگذاری فایل | `POST /supplier/offers` ✅، `PUT /supplier/offers/{id}` ✅ (UI مرده)، `/supplier/{sid}/assets` ✅، `PUT/DELETE /supplier/assets/{id}` ✅ | P1 |
| S-04 | `/supplier/accommodation` | اقامتگاه و ویلا: ملک‌ها، **ایجاد واحد** (امروز UI ندارد)، تقویم نرخ و دسترس‌پذیری (باز و بسته، نرخ شبانه، حداقل اقامت)، محتوا و تصاویر، پذیرش یا رد درخواست با SLA | `/supplier/vacation-units` ✅، `PUT …/rates` ✅، `/supplier/vacation-requests` ✅، `POST /reservations/{id}/accommodation-decision` ✅، `POST /supplier/vacation-properties/{id}/units` ✅ (بدون UI) | P0 برای تقویم و تأیید (موجود)، P1 برای ایجاد واحد |
| S-05 | `/supplier/hotels` | هتل‌های من در کاتالوگ مرجع، نگاشت ارائه‌دهنده، و اگر قرارداد مستقیم دارد: تقویم اتاق | `/supplier/hotels` ✅، `/stays/*` ✅ 🔧 (scope) | P1 |
| S-06 | `/supplier/experiences` | راهنمای تور و جاذبه: مکان، محصول تجربه، جلسه‌ها و ظرفیت، نوع بلیت | `POST /supplier/places` ✅، `/places/{id}/experience-products` ✅، `/experience-products/{id}/sessions` ✅، `/ticket-types` ✅ (همه بدون UI) | P2 |
| S-07 | `/supplier/fulfillment` | سفارش‌های پرداخت‌شده: اجرا و صدور، رد با دلیل (case خودکار) | `/supplier/reservations/ready` ✅، `POST /reservations/{id}/fulfill` ✅ | P0 (موجود) |
| S-08 | `/supplier/admission` | اسکن QR با دوربین (`BarcodeDetector` با fallback ورود دستی) | `/admission-tickets/validate` ✅، `/redeem` ✅ | P1 |
| S-09 | `/supplier/rfqs` | درخواست‌های سازمانی با **ارسال پیشنهاد قیمت** | `/enterprise/supplier/rfqs` ✅، `POST /enterprise/requests/{rid}/quotes` ✅ (بدون UI) | P1 |
| S-10 | `/supplier/reviews` | نظرها و پاسخ تأمین‌کننده | `POST /reviews/{id}/supplier-response` ✅ (بدون UI) | P2 |
| S-11 | `/supplier/settlements` و `/[id]` | صورت تسویه ردیف‌به‌ردیف (مبلغ خالص تأمین‌کننده = مبنای تأمین‌کننده + مالیات تأمین‌کننده − کمیسیون)، تأیید یا اعتراض، **بارگذاری صورتحساب تأمین‌کننده** (و تاکس‌آیدی آن برای اعتبار خرید)، وضعیت پرداخت با کد پیگیری | `/supplier/settlements` ✅، `/supplier/contracts` ✅، 🆕 `GET /supplier/settlements/{id}`، 🆕 `POST …/{id}/accept`، 🆕 `POST …/{id}/disputes`، 🆕 `POST …/{id}/supplier-invoice` | P0 (فاز ۲، همراه تسویه آژانس) |
| S-12 | `/supplier/reports` | فروش، اشغال، استرداد، با بازهٔ تاریخ | 🔧 `/supplier/dashboard` یا 🆕 `GET /supplier/reports?from&to` | P2 |
| S-13 | `/supplier/users` | کاربران تأمین‌کننده با ماژول‌ها (رزرو، قیمت، مالی، کاربران) | 🆕 `GET/POST/PUT /supplier/{sid}/members` | P2 |

---

## ۲.۹ پشتیبانی و عملیات (`backoffice_expert`)، ناحیهٔ جدید `ops`، پایه `/backoffice`

**وضعیت فعلی:** `/backoffice` یک JSON dump است. صف درخواست‌ها فقط «شروع بررسی» دارد. صفحه‌ها در JourneyShell هستند و منوی ۳۱تایی admin قرض گرفته می‌شود. این نقش `ledger:read` ندارد ولی لینک‌های مالی را می‌بیند.

**اهداف:** هیچ رزرو پرداخت‌شده‌ای بدون صدور نماند؛ هر درخواست مشتری مالک و SLA داشته باشد؛ اختلال سفر پیش از مسافر کشف شود؛ یک case برای هر رزرو (قاعدهٔ برنزی).

**منو:**
- **امروز** (Trip Operations Center) ★
- **صف‌ها** ★: صدور ناموفق، تأیید تأمین‌کننده، درخواست‌های لغو، تغییر و استرداد، تغییرات برنامهٔ پرواز، on-request اقامت، مدارک مسافران، بازبینی موجودی و مجوز
- **پرونده‌ها (Cases)** ★، پشتیبانی (گفتگو)
- **مشتری ۳۶۰** ★ (جست‌وجو)
- **کاتالوگ و موجودی:** بازبینی تور (Safarsaz)، پرواز و موجودی، سهمیهٔ همکاران، هتل‌ها، ویزا
- **شرکا:** آژانس‌ها و مجوزها، تأمین‌کنندگان
- **ابزار:** میز قطار، خدمات همکار، میز فروش، اعلان‌ها، پروندهٔ قرارداد، داده‌های مرجع

### صفحه‌ها

**OPS-01 `/backoffice` (Trip Operations Center، امروز)**، P0 (فاز ۴؛ نسخهٔ حداقلی در فاز ۱)
- ستون‌های وضعیت: برای هر صف، شمارنده، تعداد نقض SLA، قدیمی‌ترین مورد. فید رخداد زندهٔ سفر (تأخیر، لغو، تغییر). «سفرهای امروز و فردا» با ریسک (پرواز با تغییر ساعت، هتل on-request تأییدنشده، مدرک ناقص). کارهای من (assigned to me).
- endpointها: `GET /ops/dashboard` ✅ (الگو)، `/operations/trip-events` ✅، 🆕 `GET /ops/queues/summary`.

**OPS-02 `/backoffice/queues/[queue]` (صف‌ها با SLA)**، P0 (صف درخواست خدمت در فاز ۱؛ بقیه فاز ۴)
- هر صف: `DataTable` با ستون‌های مالک، SLA مانده (چیپ سبز، کهربایی یا قرمز)، شدت، نوع، کد رزرو، مشتری، مبلغ، وضعیت. فیلترهای ذخیره‌شده، «برداشتن» (assign to me)، تخصیص گروهی (سرپرست).
- صف‌ها و منبع داده:

| صف | منبع | SLA پیش‌فرض |
|---|---|---|
| `failed_issuance` (پرداخت‌شده، صادرنشده) | رزرو `paid` بدون `issued` پس از X دقیقه | CRITICAL |
| `service_requests` (لغو، تغییر، استرداد) | `BookingServiceRequest` | HIGH برای استرداد، MEDIUM برای تغییر |
| `supplier_confirmation` (on-request) | درخواست‌های اقامت و تور در انتظار تأمین‌کننده | HIGH |
| `schedule_changes` | trip-events از نوع تغییر یا لغو | HIGH |
| `documents` | `/ops/documents` ✅ | MEDIUM |
| `inventory_review` | تورهای `submitted`، موجودی جدید آژانس، مجوزهای منتظر | MEDIUM |
| `failed_payments` (کسر وجه بدون رزرو) | PSP callbackهای بدون رزرو موفق | HIGH |

- endpointها: `GET /backoffice/booking-requests` ✅، 🆕 `GET /ops/queues/{queue}?assignee=&sla=&limit=&offset=`، 🆕 `POST /ops/queues/{queue}/items/{id}/assign`.

**OPS-03 `/backoffice/requests/[id]` (رسیدگی به درخواست لغو، تغییر یا استرداد)**، **P0 (فاز ۱، بستن حلقهٔ پس از فروش)**
- بخش‌ها: خلاصهٔ رزرو، quote زمان درخواست و quote جاری (محاسبهٔ دوباره)، سیاست زمان خرید، `MoneyBreakdown` (نمای عملیات)، timeline، وضعیت تأمین‌کننده، یادداشت داخلی، پیام به مشتری (قالب‌ها).
- اقدام‌ها (هر کدام با audit و اعلان به مشتری):
  - `start_review` ✅ (موجود)
  - `request_supplier` 🆕: ثبت ارسال به تأمین‌کننده (یا API تأمین‌کننده)، وضعیت `waiting_supplier`
  - `record_supplier_response` 🆕: مبلغ قابل استرداد تأمین‌کننده، جریمهٔ تأمین‌کننده، مرجع
  - `approve` 🆕: با **مبلغ نهایی استرداد** (پیش‌فرض = quote سرور؛ تغییر آن دلیل اجباری دارد و اگر از quote بیشتر باشد، تأیید سرپرست لازم است)، مقصد وجه، و انتقال وضعیت رزرو (`cancel_requested` ← `cancelled`). خروجی: ایجاد `RefundRecord(status=pending_finance)` و ورود به صف مالی.
  - `reject` 🆕: دلیل اجباری؛ رزرو به وضعیت قبلی برمی‌گردد.
  - `need_customer` 🆕: سؤال از مشتری (وضعیت `needs_customer`؛ SLA متوقف می‌شود).
  - `propose_change` 🆕 (برای تغییر): قیمت تفاوت، گزینه‌ها؛ مشتری در C-03 می‌پذیرد.
  - `close` 🆕
- endpointها: `POST /backoffice/booking-requests/{id}/review` ✅، 🆕 `POST /backoffice/booking-requests/{id}/actions` با `{action, amount_irr?, destination?, reason?, supplier_ref?, idempotency_key}`. سرور state machine را اعمال می‌کند (انتقال غیرمجاز = 409). مجوز: `reservation:manage` برای همه به‌جز `approve` با مبلغ بالای quote (`refund:override` 🆕 برای سرپرست).

**OPS-04 `/backoffice/cases` و `/backoffice/cases/[id]` (مدیریت پرونده)**، P1 (فاز ۴)
- مدل `TripCase` در Master Spec §20 (نوع، شدت، وضعیت، مالک، اعلان‌ها، نوع حل). یک case برای هر رزرو (قاعدهٔ برنزی): پیام پشتیبانی، درخواست خدمت، اختلال و اختلاف به همان case متصل می‌شوند.
- جزئیات: گفتگوی مشتری، یادداشت داخلی، ارجاع، تغییر شدت، حل با نوع حل، و جدول SLA (اختصاص، اولین پاسخ، حل) طبق Master Spec.
- endpointها: موجود در `/support/cases*` ✅ (workspace، human-replies، internal-notes، escalate، resolve)، `PUT /support/cases/{id}/assignment` ✅ (بدون UI). 🆕 `POST /support/cases/{id}/link` (پیوند به رزرو، درخواست یا اختلاف)، 🆕 `PUT /support/cases/{id}/severity`. انتقال `/backoffice/support` به پوستهٔ پنل.

**OPS-05 `/backoffice/customers/[id]` (مشتری ۳۶۰)**، P1
- پروفایل (ماسک‌شده تا کلیک «نمایش» با audit)، رزروها، پرداخت‌ها، کیف پول (فقط خواندنی)، caseها، مدارک، سوابق ورود (OTP). اقدام: ورود به‌جای مشتری **ممنوع**؛ ثبت رزرو تلفنی از طریق میز فروش.
- endpointها: 🆕 `GET /staff/customers/{uid}/360`، جست‌وجو از §1.9.

**OPS-06 `/backoffice/reservations/[id]` (رزرو از دید عملیات)**، P1
- همهٔ اطلاعات C-03 به‌علاوهٔ اقدام‌های دستی: **صدور دستی** (ثبت شمارهٔ بلیت یا کد تأیید تأمین‌کننده)، **صدور دوبارهٔ واچر** (`POST /reservations/{id}/voucher/reissue` ✅ بدون UI)، صدور فاکتور (`POST /reservations/{id}/invoice` ✅)، ایجاد case. **هیچ اقدام پولی مستقیم** (شارژ کیف پول، استرداد) در دست عملیات نیست؛ فقط درخواست به مالی.
- endpointها: موجود + 🆕 `POST /backoffice/reservations/{id}/manual-issue` (دلیل، مرجع، پیوست).

**OPS-07 `/backoffice/trip-events`**، P0 (موجود، انتقال به پوسته). اعلام اختلال برای یک پرواز یا حرکت که برای همهٔ رزروهای متأثر case و اعلان می‌سازد: 🆕 `POST /operations/disruptions` (`scope: flight_instance|departure|hotel`).

**OPS-08 `/backoffice/catalog/review` (بازبینی موجودی شرکا)**، P0 (فاز ۲)
- صف تورها، پروازها و اقامت‌های ارسال‌شده توسط آژانس‌ها: پیش‌نمایش صفحهٔ عمومی (بدون هویت آژانس، R-PUB-1)، checklist کیفیت (برنامه، تصاویر، سیاست کنسلی، قیمت در سقف، مجوز معتبر، `tax_role` و `vat_category` پر شده)، انتشار یا رد با دلیل.
- endpointها: `/safarsaz/tours/{id}/publish|reject|unpublish` ✅، 🆕 `POST /inventory/flight-series/{id}/review` (`publish|reject`)، 🆕 `POST /stays/contracts/{id}/review`.

**OPS-09 `/backoffice/partners/agencies` و `/[id]`**، P0 (فاز ۲)
- فهرست آژانس‌ها با وضعیت KYC، مجوزها (منقضی، نزدیک انقضا)، اعتبار، فروش. جزئیات: پروفایل، **تأیید مجوز** (روش: بررسی مدرک یا استعلام از مرجع؛ ثبت `verified_by` و `verified_at`)، فعال یا معلق کردن، کاربران، کانال فروش.
- endpointها: `/admin/partners/*` ✅، `POST /admin/partners/agencies` ✅، `/sales-channel` ✅، 🆕 `POST /admin/partners/agencies/{id}/licenses/{lid}/verify`، 🆕 `PUT /admin/partners/agencies/{id}/status`.

**OPS-10 `/backoffice/partners/suppliers`**، P1. چرخهٔ عمر تأمین‌کننده: `PUT /backoffice/suppliers/{id}/lifecycle-status` ✅ (بدون UI).

**OPS-11 `/backoffice/visa`**، P1. محصول ویزا و بازبینی مدارک: `POST /backoffice/visa-products` ✅، `PUT /backoffice/visa-documents/{id}` ✅ (هر دو بدون UI).

**OPS-12 ابزارهای موجود** (میز قطار، خدمات همکار، میز فروش، اعلان‌ها، پروندهٔ قرارداد، صف مدارک، کاتالوگ هتل، داده‌های مرجع، سفرساز، موجودی، سهمیه، محتوا): بدون تغییر قابلیت، انتقال به ناحیهٔ `ops` با registry. نظارت بر نظرها (`PUT /reviews/{id}/moderation` ✅) و قالب اعلان‌ها (`GET/PUT /admin/notification-templates` ✅) در P2.

## ۲.۱۰ مالی (`finance_operator`)، ناحیهٔ جدید `finance`، پایه `/finance`

**اهداف:** هیچ پولی بی‌مالک نماند؛ استرداد با تاریخ مشخص پرداخت شود؛ تطبیق زرین‌پال روزانه بسته شود؛ تسویهٔ آژانس و تأمین‌کننده با تأیید دوطرفه؛ صورتحساب‌ها ظرف مهلت به مودیان برسند؛ گزارش ارزش افزوده فصلی آماده باشد.

**منو:**
- **امروز** ★
- **صف‌ها** ★: صف استرداد، صف شارژ و تعدیل (maker-checker)، تطبیق درگاه، صف مودیان
- **تسویه** ★: آژانس‌ها، تأمین‌کنندگان، مطالبات سازمان‌ها، کمیسیون‌ها، اختلاف‌ها
- **دفاتر:** دفتر کل، صندوق و بانک، کیف پول‌ها
- **مالیات:** گزارش ارزش افزوده، نرخ‌ها و دسته‌ها، تنظیمات مودیان
- **گزارش‌ها:** فروش، درآمد markup و کمیسیون، درگاه، خروجی فرانگر

| کد | مسیر | جزئیات | endpointها | اولویت |
|---|---|---|---|---|
| FIN-01 | `/finance` | امروز: استردادهای تأییدشدهٔ منتظر پرداخت (با قدیمی‌ترین و مجموع مبلغ)، درخواست‌های شارژ منتظر checker، مغایرت‌های باز درگاه، صورتحساب‌های مودیان نزدیک مهلت ۱۲ روزه (از روز ۸ هشدار) و ردشده، تسویه‌های منتظر | `GET /finance/reconciliation` ✅، 🆕 `/panel/today?area=finance` | P0 |
| FIN-02 | `/finance/refunds` | **صف استرداد** (P0-2): ردیف‌ها `RefundRecord` با وضعیت `pending_finance`: کد رزرو، مشتری یا آژانس یا سازمان، مبلغ، **مقصد** (کیف پول، شبا با نام صاحب حساب، برگشت به درگاه، اعتبار سازمان، اعتبار آژانس)، تأییدکنندهٔ عملیات، سن. اقدام‌ها: **پرداخت به کیف پول** (فوری، ledger)، **ثبت پرداخت بانکی دستی** (کد پیگیری پایا یا ساتنا، تاریخ، پیوست)، **دستهٔ پرداخت** (چند شبا با خروجی فایل گروهی بانک)، برگشت به درگاه (وقتی زرین‌پال پشتیبانی کند)، رد یا برگشت به عملیات (دلیل). بالای آستانه: maker-checker. پس از پرداخت: ledger (`REFUND`)، صورتحساب برگشت از فروش در صف مودیان، اعلان به مشتری با کد پیگیری | 🆕 `GET /finance/refunds?status=`، 🆕 `POST /finance/refunds/{id}/execute` (`method: wallet|bank_transfer|gateway`, `bank_reference`, `paid_at`)، 🆕 `POST /finance/refunds/{id}/approve` (checker)، 🆕 `POST /finance/refunds/{id}/return`، 🆕 `POST /finance/refunds/batches`. همه با `require_permission("refund:manage")` (امروز هیچ‌جا بررسی نمی‌شود). `POST /payments/{id}/refunds` ✅ 🔧 (فقط مسیر داخلی، نه مشتری) | **P0** |
| FIN-03 | `/finance/funding` | **شارژ کیف پول و اعتبار با maker-checker** (H-1): درخواست‌ها از آژانس، سازمان و مشتری (واریز بانکی) و تعدیل دستی. maker ثبت می‌کند، checker (کاربر دیگر) تأیید می‌کند. سقف روزانه برای هر کاربر | `GET/POST /commerce/treasury-requests` ✅ و `/decide` ✅، `POST /commerce/users/{uid}/adjust` ✅ 🔧 (maker-checker)، `POST /wallets/{id}/commands` ✅ 🔧، 🆕 `GET /finance/funding-requests`، 🆕 `POST /finance/funding-requests/{id}/approve` | P0 |
| FIN-04 | `/finance/reconciliation` | تطبیق زرین‌پال: فایل یا API تسویهٔ روزانهٔ درگاه در برابر `PAYMENT_IN` در ledger. ستون‌ها: authority و ref_id `<bdi>`، مبلغ، تاریخ، رزرو، وضعیت (`UNMATCHED`، `MATCHED`، `DISPUTED`، `RESOLVED`). اقدام‌ها: **تطبیق دستی** (انتخاب رزرو)، **حل** (نوع: برگشت به مشتری، ثبت رزرو، کارمزد درگاه، اشتباه بانک) با دلیل. دستهٔ «پرداخت موفق بدون رزرو» مستقیم به صف `failed_payments` عملیات هم می‌رود | `GET /finance/reconciliation` ✅، `POST /finance/reconciliation/match` ✅ و `/{id}/resolve` ✅ (هر دو بدون UI: P0-6)، 🆕 `POST /finance/reconciliation/imports` (فایل تسویهٔ زرین‌پال)، `GET /commerce/reports/gateway` ✅ (بدون UI) | P0 |
| FIN-05 | `/finance/settlements/agencies` و `/[id]` | دورهٔ تسویه هر آژانس: ایجاد صورت تسویه (خودکار در پایان دوره)، ردیف‌ها، وضعیت دوطرفه (`draft` ← `issued` ← `accepted` / `disputed` ← `paid` ← `closed`)، ثبت پرداخت یا دریافت (کد پیگیری)، صورتحساب B2B در صف مودیان | `/agency/{id}/settlements` ✅، `/finance/commissions*` ✅ (accrue، approve، settle، reverse)، 🆕 `POST /finance/settlements/agencies/run` (`period`)، 🆕 `POST /finance/settlements/{id}/issue`، 🆕 `POST /finance/settlements/{id}/pay` | P0 (فاز ۲) |
| FIN-06 | `/finance/settlements/suppliers` | همان جریان برای تأمین‌کنندگان، به‌علاوهٔ تطبیق با صورتحساب خرید تأمین‌کننده و تاکس‌آیدی آن | `/supplier/settlements` ✅، `POST /finance/reservations/{id}/settlements` ✅، `/commerce/suppliers/{id}/reconcile` ✅، `/finance/suppliers` ✅ | P0 (فاز ۲) |
| FIN-07 | `/finance/receivables` | مطالبات سازمان‌ها (موجود) + صدور صورت‌حساب تجمیعی ماهانه | `/receivables/organizations*` ✅ | P1 (موجود) |
| FIN-08 | `/finance/disputes` | اختلاف‌های آژانس و تأمین‌کننده (مشترک با AG-18) | 🆕 `/disputes*` | P1 |
| FIN-09 | `/finance/moadian` | **صف مودیان**: هر سند مالیاتی (`tax_invoice`) با الگو و نوع (الگوی ۱ کارمزد، **الگوی ۶ نوع اول** بلیت هواپیما، نوع اول B2B)، موضوع (`MAIN`، `CORRECTION`، `CANCEL`، `RETURN`)، مرجع (`ref_tax_id`)، وضعیت (`PENDING` ← `QUEUED` ← `SENT` ← `ACCEPTED` / `REJECTED` / `FAILED`)، تاکس‌آیدی `<bdi>`، **روزهای مانده تا مهلت ۱۲ روزه** (چیپ کهربایی از روز ۸، قرمز از روز ۱۱)، تعداد تلاش، پاسخ خام. اقدام‌ها: ارسال دوباره (retry)، اصلاح دادهٔ خریدار و ارسال صورتحساب اصلاحی، ابطال (فقط برای خطای صدور و در پنجرهٔ مجاز)، صدور دستی برگشت از فروش. وضعیت سامانه: تا اتصال شرکت معتمد، `READY_BLOCKED_EXTERNAL` و صف فقط داخلی پر می‌شود (بدون ادعای ارسال) | `GET/PUT /ops/moadian/settings` ✅، `POST /ops/contracts/{rid}/moadian` ✅ (تک‌سند)، 🆕 `GET /finance/moadian/documents?status=&due_before=`، 🆕 `POST /finance/moadian/documents/{id}/retry`، 🆕 `POST /finance/moadian/documents/{id}/correction`، 🆕 `POST /finance/moadian/documents/{id}/cancel`. پشت آن: Outbox (`outbox_worker.py` ✅) با adapter `MoadianAdapter` (TSP اول، API مستقیم بعد) | P0 برای صف داخلی و ساخت سند، P1 برای ارسال واقعی (وابسته به TSP) |
| FIN-10 | `/finance/vat` | **گزارش ارزش افزوده فصلی**: فروش به تفکیک `tax_role` و `vat_category`؛ مبنای مشمول (کارمزد و کارمزد خدمات در AGENT؛ کل فروش در PRINCIPAL)، ارزش افزودهٔ فروش، اعتبار خرید (از صورتحساب تأمین‌کنندگان با تاکس‌آیدی)، برگشت‌ها، خالص قابل پرداخت. پرچم سطرهایی که `tax_role=PRINCIPAL` «تأییدنشده توسط حسابدار» هستند. خروجی Excel برای حسابدار | 🆕 `GET /finance/tax/vat-report?period=1405Q3` | P1 |
| FIN-11 | `/finance/tax-config` | نرخ‌های تاریخ‌دار (`tax_rates`: نرخ bps، `valid_from`، `valid_to`، `legal_reference`) و دسته‌های معافیت (`vat_category`)، شناسه‌های کالا و خدمت مودیان (۱۳ رقمی) برای هر نوع خدمت. تغییر فقط با maker-checker و audit. نرخ ۱۴۰۵ = ۱۰٪ با یادداشت «تأیید متن قانون بودجه» | 🆕 `GET/POST /finance/tax/rates`، 🆕 `GET/PUT /finance/tax/categories`، 🆕 `GET/PUT /finance/tax/service-ids` | P0 (داده و جدول؛ بدون آن تفکیک §3 ممکن نیست) |
| FIN-12 | `/finance/ledger`، `/finance/treasury`، `/finance/markup-revenue`، `/finance/reports`، `/finance/journal-export`، `/finance/records`، `/finance/accounting` | موجود؛ انتقال به ناحیهٔ `finance` و پوستهٔ واحد. `ledger:read` برای عملیات حذف از منو | `/ledger/*` ✅، `/commerce/*` ✅، `/finance/records/*` ✅ | P1 (مهاجرت) |
| FIN-13 | `/finance/invoices` | صدور و ابطال فاکتور مشتری (امروز دکمه ندارد)، پیوند به سند مودیان | `POST /reservations/{id}/invoice` ✅، 🆕 `POST /invoices/{id}/void` | P1 |
| FIN-14 | `/finance/integrity` | بدهی‌ها و منابع تطبیق یکپارچگی مالی | `/debts*` ✅، `/sources*` ✅ (بدون UI) | P2 |

## ۲.۱۱ مدیر پلتفرم، مدیر tenant و white label (`platform_admin`، `tenant_admin`)، ناحیهٔ `admin`، پایه `/admin`

**اهداف:** مدیریت کاربران و نقش‌ها، tenantها و برندهای white label، feature flagها، تنظیمات سراسری، ممیزی.

**منو:** امروز (سلامت سامانه) ★، کاربران و نقش‌ها ★، سازمان‌ها، شرکا (به ops پیوند)، tenantها (فقط platform)، white label ★، feature flagها (فقط platform)، تنظیمات (آستانه‌ها، SLA، کانال‌ها)، قالب اعلان‌ها، یکپارچگی‌ها، سوابق ممیزی ★.

| کد | مسیر | جزئیات | endpointها | اولویت |
|---|---|---|---|---|
| AD-01 | `/admin` | سلامت: وضعیت یکپارچگی‌ها (زرین‌پال، پیامک، مودیان، سپهر، ...)، خطاهای صف Outbox، تعداد کاربران فعال، هشدارهای امنیتی (ورود ناموفق) | `/ops/dashboard` ✅، `/integrations` (صفحه)، 🆕 `GET /admin/health` | P1 |
| AD-02 | `/admin/users` | جست‌وجو، صفحه‌بندی، **دعوت یا ایجاد کاربر**، تغییر نقش (با دلیل، audit)، **غیرفعال‌سازی**، الزام 2FA برای نقش‌های کارکنان، بازنشانی نشست‌ها. قاعده: `tenant_admin` نقش `platform_admin` نمی‌دهد؛ هیچ‌کس نقش خودش را بالا نمی‌برد | `GET /admin/users` ✅ 🔧 (`q/limit/offset`)، `PUT /admin/users/{id}/role` ✅، 🆕 `POST /admin/users/invite`، 🆕 `POST /admin/users/{id}/deactivate`، 🆕 `PUT /admin/security/policy` (الزام 2FA) | P0 (فهرست و نقش موجود؛ غیرفعال‌سازی و 2FA در P0)، دعوت P1 |
| AD-03 | `/admin/tenants` | فقط `platform_admin`؛ ایجاد tenant با اولین مدیر و ردیف white label | `/platform/tenants*` ✅ | P1 (موجود) |
| AD-04 | `/admin/white-label` | انتقال `/white-label` از پوستهٔ عمومی به پنل. **۱۲ بُعد قرارداد WL** (Master Spec §14): صاحب برند، صاحب مجوز، Merchant of Record، Seller of Record، صادرکنندهٔ فاکتور، دریافت‌کنندهٔ وجه، مسئول استرداد، پشتیبانی سطح ۱، revenue share، مدل کمیسیون (و دو بُعد ثابت: واچر و پشتیبانی سطح ۲ همیشه Platform). برند: نام، لوگو، **توکن‌های رنگ** (روی لایهٔ semantic پنل؛ کنتراست AA پیش از ذخیره بررسی می‌شود)، دامنهٔ اختصاصی و وضعیت آن، خدمات فعال، پیش‌نمایش. قاعده: هیچ بُعدی از روی نام برند استنباط نمی‌شود | `GET/PUT /tenant/white-label` ✅ 🔧 (افزودن ابعاد قرارداد)، 🆕 `POST /tenant/white-label/preview` | P1 (فاز ۶) |
| AD-05 | `/admin/flags` | feature flagها با scope (سراسری، tenant، آژانس): `charter_domestic_sale` (پیش‌فرض خاموش)، `moadian_live_send`، `agency_api_push`، `agency_outbound_api`، `wallet_online_topup`، `refund_gateway_reversal`، `principal_tax_mode`. تغییر فقط `platform_admin`، دلیل اجباری، audit، و برای flagهای قانونی (`charter_domestic_sale`، `principal_tax_mode`) پیوست مدرک تأیید (نامهٔ وکیل یا حسابدار) | `feature_flags` در white label ✅ (فقط سطح tenant)، 🆕 `GET/PUT /platform/feature-flags` | P0 برای flag چارتر (فاز ۲) |
| AD-06 | `/admin/settings` | آستانهٔ maker-checker، جدول SLA صف‌ها، مهلت تأیید تسویه، سقف هزینهٔ پیامک (M-6)، ساعات کاری | 🆕 `GET/PUT /admin/settings` | P1 |
| AD-07 | `/admin/audit` | ممیزی با فیلتر و خروجی (§1.10) | `/admin/audit-events` ✅ 🔧 | P0 (موجود) |
| AD-08 | `/admin/organizations`، `/admin/partners`، `/admin/ecosystem` | موجود؛ انتقال به registry | ✅ | P1 |

`/pilot` (ورود آزمایشی) در build تولید حذف یا پنهان می‌شود (P2-9 و گزارش امنیت).

---

## ۲.۱۲ جریان‌های سرتاسری (End-to-End)

نماد: `[نقش] اقدام → endpoint → وضعیت`.

### E2E-A: خرید با اعتبار سازمانی و تأیید
1. `[کارمند]` درخواست در E-02 با بررسی زندهٔ سیاست ← `POST …/requests` ✅ ← `pending_approval`. اگر خارج سیاست است، دلیل اجباری.
2. سیستم: مسیر تأیید از قالب (O-05) و آستانهٔ مبلغ. اعلان به تأییدکنندهٔ اول با مهلت.
3. `[تأییدکننده]` در A-01 تأیید، رد (دلیل)، برگشت (دلیل) یا ارجاع ← `POST /enterprise/requests/{rid}/decision` ✅. اگر مبلغ از حد تأییدکننده بیشتر است، خودکار به مرحلهٔ بعد.
4. `[کارمند]` پس از تأیید، انتخاب گزینه از booking candidates (قیمت زنده؛ اگر قیمت از مبلغ تأییدشده بیشتر شد بیش از حد مجاز، تأیید دوباره لازم است) ← `POST /enterprise/requests/{rid}/bookings` ✅.
5. سیستم: hold اعتبار مرکز هزینه ← پرداخت از اعتبار (ledger `SALE` + `CREDIT_USE`) ← صدور ← واچر به کارمند.
6. سیستم: فاکتور به نام **سازمان** (نوع اول، شناسهٔ ملی و اقتصادی از O-12؛ بدون آن صدور فاکتور مسدود و case ایجاد می‌شود) ← صف مودیان.
7. `[مالی]` پایان ماه: صورت‌حساب تجمیعی (FIN-07) ← سازمان در O-09 می‌بیند ← تسویه `POST /receivables/organizations/{org}/settlements` ✅. کسر از حقوق: `Unavailable` (مدل داده ندارد؛ OQ-O3).
- آزمون‌ها: درون‌سیاست، خارج سیاست، اعتبار تمام‌شده (رزرو مسدود با پیام)، رد با دلیل، ارجاع با آستانه، تأییدکننده = متقاضی (رد سرور).

### E2E-B: مأمور خرید برای چند نفر
1. `[مأمور خرید]` PO-02: انتخاب ۱۲ کارمند + ۳ مهمان (فایل) ← بررسی کد ملی و گذرنامه ← تخصیص مرکز هزینه.
2. جست‌وجو و انتخاب (مثلاً ۱۵ صندلی پرواز + ۸ اتاق). سیستم موجودی را برای همه hold می‌کند (یا همه یا هیچ، با گزینهٔ «ادامه با موجودی جزئی» که صریح است).
3. بررسی سیاست برای هر مسافر؛ موارد خارج سیاست علامت می‌خورند. ارسال یک درخواست با `people[]` ← تأیید (E2E-A مرحلهٔ ۳).
4. پس از تأیید، رزرو گروهی از اعتبار ← صدور هر مسافر جدا ← PO-03 وضعیت هر نفر ← ارسال واچر به موبایل هر مسافر.
5. فاکتور تجمیعی به نام سازمان با ردیف هر مسافر و مرکز هزینه.
- قواعد: استرداد هر مسافر جداگانه و به اعتبار سازمان. مأمور خرید نمی‌تواند مقصد استرداد را شبای شخصی بگذارد.

### E2E-C: چرخهٔ لغو و استرداد (مشتری ← عملیات ← مالی ← تأمین‌کننده ← مودیان)، با ارزش افزوده روی کمیسیون

| گام | بازیگر | اقدام | endpoint | وضعیت درخواست | وضعیت رزرو |
|---|---|---|---|---|---|
| 1 | مشتری | پیش‌نمایش جریمه در C-03 | `GET /reservations/{id}/cancellation-quote` ✅ | — | `issued` |
| 2 | مشتری | ثبت درخواست با quote قفل‌شده و مقصد وجه | `POST /reservations/{id}/service-requests` ✅ 🔧 | `submitted` | `cancel_requested` |
| 3 | عملیات | برداشتن از صف، شروع بررسی | `…/review` ✅ | `under_review` | — |
| 4 | عملیات | ارسال به تأمین‌کننده (API یا دستی) | 🆕 `…/actions {request_supplier}` | `waiting_supplier` | — |
| 5 | تأمین‌کننده یا عملیات | ثبت پاسخ: مبلغ قابل استرداد تأمین‌کننده، جریمهٔ تأمین‌کننده | 🆕 `{record_supplier_response}` (یا AG-13 / S-07 برای موجودی شرکا) | `under_review` | — |
| 6 | عملیات | تأیید با مبلغ نهایی (= محاسبهٔ سرور) | 🆕 `{approve}` | `approved` → `refund_queued` | `cancelled` |
| 7 | مالی | پرداخت (کیف پول، شبا یا درگاه)؛ maker-checker بالای آستانه | 🆕 `POST /finance/refunds/{id}/execute` | `refund_paid` | `refunded` (یا `partially_refunded`) |
| 8 | سیستم | ledger: معکوس فروش + جریمه به‌عنوان درآمد | Ledger | — | — |
| 9 | سیستم | صورتحساب **برگشت از فروش** با ارجاع به تاکس‌آیدی اصلی، در صف مودیان | Outbox | — | — |
| 10 | سیستم | اعلان به مشتری با کد پیگیری؛ بستن درخواست | — | `closed` | — |

**محاسبهٔ ارزش افزوده در استرداد (مدل AGENT، مثال بلیت سیستمی داخلی):**
- فروش اولیه: مبنای تأمین‌کننده ۴۰٬۰۰۰٬۰۰۰، مالیات و عوارض تأمین‌کننده (شامل VAT ایرلاین) ۴٬۰۰۰٬۰۰۰، کمیسیون آژانس از ایرلاین ۱٬۲۰۰٬۰۰۰ (داخل قیمت ایرلاین)، کارمزد خدمات کارن تراول ۵۰۰٬۰۰۰، VAT آژانس = ۱۰٪ × (۱٬۲۰۰٬۰۰۰ + ۵۰۰٬۰۰۰) = ۱۷۰٬۰۰۰. مشتری پرداخت کرده است: ۴۴٬۰۰۰٬۰۰۰ + ۵۰۰٬۰۰۰ + VAT کارمزد خدمات ۵۰٬۰۰۰ = ۴۴٬۵۵۰٬۰۰۰ ریال (VAT کمیسیون ۱۲۰٬۰۰۰ از سهم آژانس پرداخت می‌شود و به مشتری اضافه نمی‌شود).
- استرداد با جریمهٔ ۳۰٪ ایرلاین: ایرلاین ۷۰٪ از ۴۴٬۰۰۰٬۰۰۰ را برمی‌گرداند. کمیسیون آژانس به نسبت برگشت تعدیل می‌شود (طبق قرارداد ایرلاین؛ فرض: کمیسیون روی بخش جریمه حفظ می‌شود). کارمزد خدمات **قابل استرداد نیست** مگر در لغو از سوی ایرلاین (قاعدهٔ قابل تنظیم `service_fee_refundable_on_carrier_cancel=true`).
- اسناد: صورتحساب الگوی ۶ بلیت (اگر آژانس صادرکننده است، OQ-A3) ← برگشت از فروش به نسبت ۷۰٪. صورتحساب کارمزد آژانس (الگوی ۱) ← برگشت از فروش جزئی فقط برای بخش کمیسیونی که برگشت خورده؛ VAT روی همان بخش معکوس می‌شود. کارمزد خدمات بدون برگشت.
- در مدل PRINCIPAL (پکیج تور): برگشت از فروش روی کل مبلغ با تفکیک اجزای معاف و مشمول؛ جریمهٔ باقی‌مانده درآمد مشمول. **با برچسب «نیازمند تأیید حسابدار»** (OQ-A2، OQ-A7).
- همهٔ این محاسبه سمت سرور انجام می‌شود (M-1) و در `MoneyBreakdown` نمای مالی ردیف‌به‌ردیف نشان داده می‌شود.
- آزمون‌ها: استرداد کامل، جزئی، لغو از سوی ایرلاین (بدون جریمه، کارمزد خدمات برمی‌گردد)، چارتر، رد درخواست، پرداخت دوبار (idempotency ← یک بار)، مشتری تلاش انتقال مستقیم (403، C-1).

### E2E-D: آژانس صندلی چارتر منتشر می‌کند ← مشتری می‌خرد ← تسویه با آژانس
1. `[آژانس/چارترکننده]` مجوز `BAND_ALEF` معتبر (AG-02؛ تأیید OPS-09).
2. CH-02: ثبت سری پرواز با ظرفیت ۵۰، نرخ‌ها، سیاست استرداد، `release_at`، `route_scope=INTERNATIONAL` (چارتر داخلی پشت flag)، `tax_role=PRINCIPAL`.
3. `[عملیات]` OPS-08 بازبینی (نرخ در سقف، سیاست کامل، قرارداد ایرلاین پیوست) ← انتشار.
4. `[مشتری]` جست‌وجو؛ پرواز با برند کارن تراول و بدون نام آژانس نمایش داده می‌شود (R-PUB-1). قیمت = نرخ آژانس + markup کارن تراول. سیاست استرداد پیش از پرداخت نمایش داده می‌شود.
5. پرداخت زرین‌پال ← ledger `PAYMENT_IN` ← `seats_sold +1` (اتمی؛ تست هم‌زمانی) ← صدور بلیت: آژانس در AG-13 شمارهٔ بلیت را ثبت می‌کند یا با API می‌فرستد؛ SLA صدور (پیش‌فرض ۳۰ دقیقه، چون دستورالعمل صدور هم‌زمان با دریافت وجه را می‌خواهد). اگر صادر نشود ← case بحرانی ← استرداد کامل.
6. ledger: بدهی به آژانس (`PURCHASE` = نرخ آژانس) و درآمد markup کارن تراول.
7. پایان دوره: FIN-05 صورت تسویه: ناخالص به نرخ آژانس − استردادها − کمیسیون یا کارمزد پلتفرم (طبق قرارداد) − VAT کارمزد پلتفرم = خالص به آژانس ← آژانس در AG-17 تأیید ← مالی پرداخت ← صورتحساب B2B کارمزد پلتفرم به آژانس (نوع اول) در صف مودیان. آژانس صورتحساب فروش خودش (اصیل) را به ما ارائه می‌دهد (S-11 / AG-17 بارگذاری) برای اعتبار خرید.
8. پس از `release_at`: صندلی‌های نفروخته به آژانس برمی‌گردند (از فروش آنلاین خارج می‌شوند).

### E2E-E: آژانس موجودی ما را با markup و اعتبار آژانس به مشتری خودش می‌فروشد
1. `[مالی]` حساب اعتباری آژانس با سقف (maker-checker) ← `PUT /admin/partners/agencies/{id}/credit-account` ✅ 🔧.
2. `[آژانس]` AG-03: جست‌وجو؛ نمایش net (قیمت کارن تراول منهای کمیسیون آژانس، یا قیمت عمومی با `Agency.commission_bps`)، markup آژانس از AG-07، قیمت مشتری (≤ `price_cap`).
3. رزرو ← **hold** روی اعتبار آژانس به مبلغ net ← صدور ← **capture** ← اگر صدور شکست خورد، **release**.
4. واچر به نام مسافر؛ صورتحساب کارن تراول به **آژانس** (B2B نوع اول، net). آژانس مسئول صورتحساب خودش به مشتری با markup است.
5. کمیسیون (اگر مدل کمیسیونی است، نه net): `POST /finance/commissions/accrue` ✅ ← approve ← settle.
6. استرداد: درخواست از AG-05 ← E2E-C با مقصد **اعتبار آژانس**.
7. پایان دوره: صورت بدهی آژانس (فروش net − استرداد − کمیسیون) ← آژانس تسویه می‌کند یا از پیش‌پرداخت کسر می‌شود.
8. زیرمجموعه: اگر فروشنده زیرمجموعه است، hold روی سقف تخصیصی زیرمجموعه و سقف والد هر دو؛ کمیسیون طبق `commission_split_rule` تقسیم می‌شود.

### E2E-F: پرداخت به تأمین‌کننده (هتل، ویلا، راهنما)
1. رزرو مشتری ← تأمین‌کننده تأیید (S-04/S-07) ← اجرا (check-in یا redeem).
2. ledger: بدهی به تأمین‌کننده = مبنای تأمین‌کننده + مالیات تأمین‌کننده − کمیسیون (اگر کمیسیون کسر از مبدأ است).
3. پایان دوره: FIN-06 صورت تسویه ← S-11 تأمین‌کننده تأیید یا اعتراض می‌کند و **صورتحساب خرید با تاکس‌آیدی** بارگذاری می‌کند ← مالی پرداخت (maker-checker بالای آستانه) با کد پیگیری ← وضعیت `paid` در پنل تأمین‌کننده.
4. پرداخت بدون صورتحساب تأمین‌کننده‌ای که مشمول است مجاز ولی با هشدار «بدون اعتبار خرید» (قاعدهٔ قابل تنظیم).
5. کسورات (جریمهٔ عدم اجرا، no-show تأمین‌کننده) از caseهای مرتبط با دلیل و پیوست.

---

# ۳. تفکیک مالی خط سفارش (Order-line Financial Breakdown)

## ۳.۱ مدل داده

مبنا: `PriceBreakdown` در Master Spec §6.2 (موجود به‌صورت مفهومی؛ endpoint `GET /reservations/{id}/price-breakdown` ✅ موجود است) به‌علاوهٔ فیلدهای مالیاتی پژوهش. 🆕 جدول `order_line_financials` (یک ردیف برای هر خط سفارش، و برای هر مسافر اگر قیمت مسافران فرق دارد). **همهٔ مبالغ عدد صحیح ریال؛ نرخ‌ها به basis point؛ بدون float.** پس از صدور snapshot و غیرقابل تغییر است؛ تغییر فقط با ردیف تعدیلی جدید.

| فیلد | توضیح | منبع |
|---|---|---|
| `line_id`, `reservation_id`, `passenger_type` (ADT/CHD/INF/null) | شناسه | Booking |
| `price_source` | `PUB` / `CTR` / `CHR` / `ALT` / `NEG` / `CRP` / `PRM` | Rate Engine (موجود در `inventory.py`: `CHR`/`CTR`) |
| `inventory_owner_type`, `inventory_owner_id` | `airline_api` / `supplier` / `agency` / `platform` | Inventory |
| `supplier_base_amount` | قیمت پایهٔ عرضه‌کننده (fare پایه، نرخ اتاق، قیمت خرید تور) | پاسخ وب‌سرویس یا قرارداد؛ **هرگز محاسبهٔ خودمان** |
| `supplier_taxes[]` | `[{code, label_fa, amount}]` مالیات و عوارض عرضه‌کننده به تفکیک کد (سهم فرودگاه، YQ/YR، ...) | دقیقاً همان که وب‌سرویس می‌دهد |
| `supplier_vat_amount` | ارزش افزوده‌ای که عرضه‌کننده روی صورتحساب خودش آورده (برای اعتبار خرید) | صورتحساب یا پاسخ تأمین‌کننده |
| `agency_commission_amount` | کمیسیون دریافتی کارن تراول از عرضه‌کننده (کمیسیون ایرلاین، کمیسیون هتل) | قرارداد یا قاعده |
| `platform_markup_amount` | markup کارن تراول روی قیمت عرضه‌کننده (در مدل net) | `/commerce` markup rules ✅ |
| `service_fee_amount` | کارمزد خدمات که مستقیم از مشتری گرفته می‌شود | قاعدهٔ کارمزد |
| `channel_agency_id`, `channel_markup_amount`, `channel_commission_amount` | آژانس فروشندهٔ B2B: markup آژانس به مشتری خودش و کمیسیون پرداختی ما به آژانس | AG-07، `Agency.commission_bps` |
| `sub_agency_split[]` | `[{agency_id, amount}]` تقسیم کمیسیون زیرمجموعه | `commission_split_rule` |
| `wl_channel_id`, `wl_revenue_share_amount` | سهم white label | WL contract |
| `discount_amount`, `discount_source` | تخفیف (کد، وفاداری، سازمانی) و اینکه از سهم چه کسی کسر می‌شود | Promotion |
| `tax_role` | `AGENT` / `PRINCIPAL` | از موجودی (`inventory_item.tax_role`)؛ PRINCIPAL با `principal_tax_mode` flag و برچسب `accountant_confirmed=false` |
| `vat_category` | `TAXABLE_DOMESTIC_AIR`، `DISPUTED_INTL_AIR`، `EXEMPT_RAIL_ROAD_SEA`، `EXEMPT_LODGING_LE3`، `TAXABLE_LODGING_4_5`، `INBOUND_TOURISM_EXEMPT`، `OUTBOUND_UNKNOWN`، `VISA_UNKNOWN`، `INSURANCE_EXEMPT_UNCONFIRMED`، `AGENCY_SERVICE_TAXABLE` | جدول FIN-11 |
| `agency_vat_base` | **AGENT:** `agency_commission_amount + platform_markup_amount + service_fee_amount` (درآمد خود ما). **PRINCIPAL:** مبلغ فروش اجزای مشمول (اجزای معاف جدا). | محاسبهٔ سرور |
| `agency_vat_rate_bps`, `tax_rate_id` | نرخ (۱۴۰۵: ۱۰۰۰ bps) با ارجاع به جدول تاریخ‌دار و `legal_reference` | FIN-11 |
| `agency_vat_amount` | `round_half_up(agency_vat_base × rate / 10000)` | سرور |
| `vat_collected_from_customer` | بخشی از VAT آژانس که به قیمت مشتری اضافه شده (معمولاً VAT کارمزد خدمات و markup)؛ VAT کمیسیون از سهم آژانس پرداخت می‌شود | سرور |
| `customer_total` | جمعی که مشتری می‌پردازد | سرور |
| `agency_net_revenue` | درآمد خالص کارن تراول پس از VAT و سهم کانال و WL | سرور |
| `supplier_payable` | بدهی به عرضه‌کننده یا آژانس مالک موجودی | سرور |
| `currency`, `fx_rate`, `fx_source`, `amount_irr` | برای ارزی؛ مودیان همیشه ریال | سرور (منبع نرخ: OQ-A10) |
| `moadian_service_id` | شناسهٔ ۱۳ رقمی کالا و خدمت | FIN-11 |
| `calculated_by`, `override_reason`, `approved_by` | `SYSTEM` / `MANUAL_OVERRIDE` | Audit |

**قید ثبات:** `customer_total = supplier_base + Σ supplier_taxes + platform_markup + service_fee + channel_markup + vat_collected_from_customer − discount` (برای مدل net). تست واحد: `tests/test_order_line_breakdown.py` با مثال‌های E2E-C و مدل‌های AGENT و PRINCIPAL و هر `vat_category`.

## ۳.۲ اسناد مالیاتی که از هر خط ساخته می‌شوند

| مورد | AGENT | PRINCIPAL (نیازمند تأیید حسابدار) |
|---|---|---|
| بلیت هواپیما (سیستمی) | صورتحساب **الگوی ۶ نوع اول** با اطلاعات مسافر، اگر آژانس صادرکننده باشد (OQ-A3)؛ و صورتحساب **کارمزد آژانس** (الگوی ۱) روی `agency_vat_base` | — |
| صندلی چارتر (خرید و فروش با ریسک) | — | صورتحساب کل فروش (الگوی ۶ یا ۱، OQ-A6) با اعتبار خرید از صورتحساب چارتردهنده |
| هتل به نام هتل | کارمزد آژانس (الگوی ۱) | — |
| پکیج تور | — | کل فروش با اقلام تفکیک‌شدهٔ معاف (هتل ≤۳★، قطار، اتوبوس) و مشمول (پرواز داخلی، هتل ۴–۵★، کارمزد) |
| خریدار سازمانی | **نوع اول** با شناسهٔ ملی، شمارهٔ اقتصادی و کد پستی خریدار (اجباری) | همان |
| B2B بین آژانس‌ها | نوع اول: کارمزد پلتفرم به آژانس، یا فروش net به آژانس خریدار | همان |
| استرداد | **برگشت از فروش** (کامل یا جزئی) با ارجاع به تاکس‌آیدی مرجع | همان |
| خطای صدور | **ابطالی** یا **اصلاحی** در پنجرهٔ مجاز | همان |

مدل `tax_invoice` 🆕 (گسترش `ops_moadian_records` ✅): `id, source_type(invoice|refund|settlement), source_id, pattern, invoice_type, subject(MAIN|CORRECTION|CANCEL|RETURN), ref_tax_id, buyer{type, national_id, economic_code, postal_code, name}, passengers[] (برای الگوی ۶), lines[{service_id, qty, unit_irr, discount_irr, vat_bps, vat_irr}], totals, serial, tax_id, status, attempts, due_at (issued_at + 12 روز), sent_at, response_raw`. نگهداری حداقل به مدت قانونی (OQ-A13).

## ۳.۳ نمایش در هر پنل

| پنل | آنچه دیده می‌شود | آنچه دیده **نمی‌شود** |
|---|---|---|
| مشتری (C-03, C-05) | قیمت پایه و مالیات و عوارض عرضه‌کننده (جمع، با باز شدن جزئیات کدها)، کارمزد خدمات، ارزش افزودهٔ کارمزد خدمات، تخفیف، **جمع پرداختی**؛ در استرداد: مبلغ پرداختی، جریمه (به تفکیک جریمهٔ عرضه‌کننده و کارمزد غیرقابل استرداد)، **مبلغ قابل استرداد** | کمیسیون، markup، سهم آژانس، درآمد خالص |
| سازمان (O-07, O-09) | مثل مشتری + مرکز هزینه، شمارهٔ فاکتور، شناسهٔ ملی و اقتصادی خریدار، وضعیت مودیان | کمیسیون و markup |
| آژانس خریدار (AG-05) | **net آژانس**، markup آژانس، قیمت مشتری، کمیسیون دریافتی (در مدل کمیسیونی)، VAT روی آن، سهم زیرمجموعه | markup کارن تراول و قیمت عرضه‌کننده |
| آژانس فروشنده و چارترکننده (AG-13, AG-17) | نرخ آژانس (مبنای خودش)، کارمزد یا کمیسیون پلتفرم، VAT کارمزد پلتفرم، کسورات، خالص قابل پرداخت | قیمت فروش به مشتری و markup کارن تراول (OQ-O7: آیا آژانس قیمت فروش نهایی را ببیند؟ پیش‌فرض: خیر) |
| تأمین‌کننده (S-11) | مبنای تأمین‌کننده، مالیات تأمین‌کننده، کمیسیون کسرشده، خالص، وضعیت پرداخت | قیمت مشتری و markup |
| عملیات (OPS-03, OPS-06) | جمع مشتری، اجزای عرضه‌کننده، کارمزد خدمات، سیاست جریمه، quote استرداد؛ **بدون** حاشیهٔ سود | `agency_net_revenue`، سهم WL |
| مالی (FIN-*) | **همهٔ فیلدها** شامل `tax_role`، `vat_category`، `tax_rate_id`، اسناد مودیان مرتبط، و ردیف‌های ledger | — |
| ادمین | فقط از طریق نقش مالی | — |

جزء `MoneyBreakdown` یک prop `view: 'customer'|'organization'|'agency_buyer'|'agency_seller'|'supplier'|'ops'|'finance'` می‌گیرد، ولی **فیلتر سمت سرور** انجام می‌شود: 🆕 `GET /reservations/{id}/price-breakdown?view=` فقط فیلدهای مجاز آن نقش را برمی‌گرداند (frontend فیلد پنهان را دریافت نمی‌کند).

---

# ۴. ماتریس مجوز (نقش × قابلیت)

نقش‌ها: **C** مشتری، **E** کارمند، **AP** تأییدکننده (`manager`)، **OA** مدیر سازمان (`organization_admin`/`welfare_manager`)، **PO** مأمور خرید (grant `requests.on_behalf`)، **AG** آژانس (`agency_partner`؛ ماژول در پرانتز)، **SAG** زیرمجموعهٔ آژانس، **SU** تأمین‌کننده، **OPS** عملیات (`backoffice_expert`)، **FIN** مالی (`finance_operator`)، **TA** مدیر tenant، **PA** مدیر پلتفرم.
علامت: ✓ مجاز؛ **own** فقط منابع خودش؛ **scope** در محدودهٔ سازمان یا آژانس یا واحد؛ **req** فقط درخواست (نه اجرا)؛ **MC** با maker-checker؛ — ممنوع.

| قابلیت (permission پیشنهادی) | C | E | AP | OA | PO | AG | SAG | SU | OPS | FIN | TA | PA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| مشاهدهٔ رزرو (`reservation:read`) | own | own | scope | scope | scope | own (فروش و موجودی) | own | own (موجودی) | ✓ | ✓ | ✓ | ✓ |
| ایجاد رزرو (`reservation:create`) | ✓ | ✓ (سیاست) | — | — | scope | ✓ (sales) | ✓ | — | ✓ (میز فروش) | — | — | ✓ |
| **انتقال وضعیت رزرو** (`reservation:transition`) 🔧 C-1 | — | — | — | — | — | — | — | تأیید یا اجرای own | ✓ (به‌جز وضعیت‌های پولی) | — | — | ✓ |
| درخواست لغو یا تغییر (`service_request:create`) | own | own | — | scope | scope | own (sales) | own | — | ✓ | — | — | ✓ |
| رسیدگی و تأیید درخواست (`service_request:decide`) 🆕 | — | — | — | — | — | — | — | پاسخ own | ✓ | — | — | ✓ |
| تأیید مبلغ استرداد بالاتر از quote (`refund:override`) 🆕 | — | — | — | — | — | — | — | — | سرپرست | ✓ | — | ✓ |
| اجرای استرداد (`refund:manage`) | — | — | — | — | — | — | — | — | — | ✓ (MC بالای آستانه) | — | ✓ |
| **شارژ کیف پول یا اعتبار** (`wallet:fund`) 🔧 H-1 | req | — | — | req | — | req | req (از والد) | — | — | **MC** | — | MC |
| ایجاد حساب اعتباری و سقف (`credit:limit`) 🔧 H-1 | — | — | — | req | — | req | — (والد تخصیص می‌دهد در سقف خودش) | — | — | **MC** | — | MC |
| توزیع اعتبار موجود (`credit:allocate`) | — | — | — | scope (≤ سقف) | — | زیرمجموعه (≤ مانده) | — | — | — | ✓ | — | ✓ |
| برداشت کیف پول به شبا (`wallet:withdraw`) | req (own) | — | — | — | — | req | — | — | — | ✓ اجرا | — | ✓ |
| تصمیم تأیید سفر (`approval:decide`) | — | — | scope (نه خودش) | scope | — | — | — | — | — | — | — | — |
| مدیریت کارکنان و سیاست (`member:manage`, `policy.manage`) | — | — | — | scope | — | — | — | — | — | — | ✓ | ✓ |
| رزرو برای دیگران (`requests.on_behalf`) | — | — | — | scope | scope | — | — | — | — | — | — | — |
| ایجاد و ویرایش موجودی (`inventory:manage`) 🔧 H-2 | — | — | — | — | — | own (inventory) | own (اگر مجوز دارد) | own | ✓ | — | — | ✓ |
| انتشار موجودی (`inventory:publish`) 🆕 | — | — | — | — | — | — (فقط ارسال) | — | — | ✓ | — | — | ✓ |
| خواندن مانیفست (`manifest:read`) 🔧 H-2 | — | — | — | — | — | own | own | own | ✓ | — | — | ✓ |
| تغییر قالب قرارداد عمومی (`contract_template:manage`) 🔧 H-2 | — | — | — | — | — | — | — | — | ✓ | — | ✓ | ✓ |
| گزارش فروش کامل پلتفرم (`sales_report:read`) 🔧 H-2 | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ |
| کلید API شریک (`partner_api:manage`) 🆕 | — | — | — | — | — | own (owner) | — | own | — | — | — | ✓ |
| قواعد markup آژانس (`agency_pricing:manage`) 🆕 | — | — | — | — | — | own (owner/sales) | own (≥ markup والد) | — | — | — | — | ✓ |
| قواعد markup و کمیسیون پلتفرم (`commerce:manage`) | — | — | — | — | — | — | — | — | — | ✓ (MC) | ✓ | ✓ |
| زیرمجموعه (`agency:manage`) | — | — | — | — | — | own (owner) | — | — | ✓ (مشاهده) | — | — | ✓ |
| تأیید مجوز آژانس (`license:verify`) 🆕 | — | — | — | — | — | — | — | — | ✓ | — | — | ✓ |
| تسویه: صدور (`settlement:manage`) | — | — | — | — | — | — | — | — | — | ✓ | — | ✓ |
| تسویه: پذیرش یا اعتراض (`settlement:accept`) 🆕 | — | — | — | — | — | own (finance) | own | own | — | — | — | — |
| تطبیق درگاه (`reconciliation:manage`) | — | — | — | — | — | — | — | — | — | ✓ | — | ✓ |
| صف مودیان و فاکتور (`invoice:manage`, `tax:submit` 🆕) | — | — | — | — | — | — | — | — | فاکتور (صدور) | ✓ | — | ✓ |
| نرخ و دستهٔ مالیات (`tax:config` 🆕) | — | — | — | — | — | — | — | — | — | MC | — | MC |
| دفتر کل (`ledger:read`/`ledger:post`) | — | — | — | — | — | — | — | — | — | ✓ | — | ✓ |
| جست‌وجوی سراسری و مشتری ۳۶۰ (`backoffice:read`) | — | — | — | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ |
| case و پشتیبانی (`support:manage`) | own | own | — | — | — | own | own | own | ✓ | — | — | ✓ |
| کاربران و نقش‌ها (`user:manage`) | — | — | — | — | — | own (اعضای آژانس) | — | own | — | — | tenant (نه PA) | ✓ |
| white label (`tenant:manage`) | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ |
| feature flag (`platform:flags` 🆕) | — | — | — | — | — | — | — | — | — | — | — | ✓ (دلیل + مدرک) |
| ممیزی (`audit:read`) | — | — | — | scope | — | own | — | — | ✓ | ✓ | ✓ | ✓ |

**تغییرات `security.py`** (فاز ۱ و ۲):
- `customer` و `employee`: حذف امکان انتقال وضعیت در `/reservations/{id}/commands`؛ فقط `service_request:create`.
- `organization_admin`: حذف هر مسیر افزایش موجودی کیف پول یا اعتبار (H-1)؛ `credit:manage` به `credit:allocate` محدود می‌شود.
- `supplier`: جدا کردن از بررسی staff در `inventory.py:246-254` (H-2)؛ همهٔ queryها با `SupplierMembership` یا `owner_agency_id`.
- `agency_partner`: افزودن `inventory:manage:own`، `settlement:accept`، `partner_api:manage` (همه منوط به عضویت و ماژول).
- `backoffice_expert`: افزودن `service_request:decide`، `inventory:publish`، `license:verify`؛ **عدم** دسترسی به `refund:manage` و `wallet:fund`.
- `finance_operator`: `refund:manage` واقعاً بررسی شود؛ `wallet:fund`، `credit:limit`، `tax:config`، `tax:submit` با maker-checker.
- `platform:manage` super-permission می‌ماند ولی اقدام‌های MC برای PA هم دو نفره‌اند (PA نمی‌تواند checker اقدام خودش باشد).
- تست: `tests/test_permission_matrix.py` جدول بالا را به‌صورت داده می‌خواند و برای هر خانه یک درخواست (مجاز ← 2xx، ممنوع ← 403/404) می‌فرستد.

---

# ۵. برنامهٔ Figma

فایل: `https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir`. یک page جدید برای هر فاز: `Panels / P1 Shell+Refund`، `Panels / P2 B2B`، ... . هر frame در دو اندازه: **Desktop 1440** و **Mobile 390**. نام‌گذاری: `PNL/{area}/{code}-{name}/{1440|390}` (مثلاً `PNL/customer/C-04-refunds/390`). ابتدا library اجزا (فاز ۰)، سپس صفحه‌ها. هر frame باید حالت‌های loading (skeleton)، empty، error و (در صورت وجود) «بدون دسترسی» را به‌صورت variant داشته باشد. هیچ frame صفحهٔ اصلی و جست‌وجو را تغییر نمی‌دهد؛ فقط از آن‌ها رنگ و تایپوگرافی گرفته می‌شود.

**فاز ۰، کتابخانهٔ پنل** (`Panels / Library`): توکن‌های `--pn-*` و semantic به‌صورت Figma variables (حالت روشن + یک تم نمونهٔ white label)؛ اجزا: Sidebar (باز، جمع، drawer)، TopBar (با جست‌وجوی کارکنان و بدون آن)، BottomNav (۴ مقصد + بیشتر)، ScopePicker، TodayCard (bad/warn/info)، StatusChip (همهٔ واژگان)، Timeline (گام انجام‌شده، جاری، بعدی با ETA، تأخیر)، DataTable (دسکتاپ و کارت موبایل، صفحه‌بندی، فیلتر، اقدام گروهی)، Skeletonها، Empty، Error، Unavailable، MockLabel، NoAccess، MoneyBreakdown (۷ view)، ConfirmMoney dialog، JalaliDateField، FileImport (۴ گام)، NotificationDrawer، GlobalSearch (Ctrl+K).

| ترتیب | فاز | frameها (هر کدام 1440 + 390) |
|---|---|---|
| 1 | P1 | `customer/C-01-today`، `C-02-bookings`، `C-03-booking-detail`، `C-03a-cancel-wizard` (۳ گام)، `C-04-refunds`، `C-04a-refund-timeline`، `C-05-payments-invoices`، `C-06-wallet`، `C-07-profile-travellers`، `C-09-support-thread` |
| 2 | P1 | `ops/OPS-01-today-min`، `OPS-02-queue-service-requests`، `OPS-03-request-handling` (با dialogهای approve/reject/need_customer) |
| 3 | P1 | `finance/FIN-01-today`، `FIN-02-refund-queue`، `FIN-02a-execute-refund` (ConfirmMoney + MC)، `FIN-02b-refund-batch`، `FIN-03-funding-mc`، `FIN-04-reconciliation` |
| 4 | P1 | `common/no-access`، `common/notification-drawer`، `common/staff-search` |
| 5 | P2 | `agency/AG-01-today`، `AG-02-profile-licenses`، `AG-08-tours-list`، `AG-08a-tour-editor` (برنامه، حرکت‌ها، سیاست، مالیات)، `AG-10/CH-01-flights`، `CH-02-seat-block-form`، `CH-03-flight-detail` (ظرفیت، اختلال)، `CH-04-quotas`، `AG-11-file-import`، `AG-12-api-keys-webhooks`، `AG-13-received-bookings`، `AG-14-manifest`، `AG-15-credit`، `AG-17-settlement-detail`، `AG-18-disputes`، `AG-19-sub-agencies`، `AG-03-sell-search-result` (net/markup/customer) |
| 6 | P2 | `ops/OPS-08-inventory-review` (با پیش‌نمایش عمومی بدون هویت آژانس)، `OPS-09-agency-kyc`؛ `finance/FIN-05-agency-settlements`، `FIN-06-supplier-settlements`؛ `supplier/S-01-today`، `S-11-settlement`؛ `admin/AD-05-flags` (charter) |
| 7 | P3 | `organization/O-01-today`، `O-02-members-import`، `O-03-policy-editor`، `O-05-approval-templates`، `O-08-credit`، `O-09-billing`، `O-12-legal-profile`؛ `approver/A-01-inbox` (+ dialog رد با دلیل)؛ `employee/E-01-today`، `E-02-new-request` (بررسی زندهٔ سیاست)، `E-03-request-detail`؛ `purchasing/PO-02-group-wizard` (۵ گام)، `PO-03-basket`، `PO-04-rfq-compare` |
| 8 | P4 | `ops/OPS-01-trip-operations-center` (کامل)، `OPS-02-queues` (هر ۷ صف به‌عنوان variant)، `OPS-04-case-detail`، `OPS-05-customer-360`، `OPS-06-reservation-ops`، `OPS-07-disruption`، `OPS-11-visa` |
| 9 | P5 | `finance/FIN-09-moadian-queue` (با چیپ مهلت)، `FIN-09a-moadian-document`، `FIN-10-vat-report`، `FIN-11-tax-config`، `FIN-13-invoices`؛ `customer/C-05a-invoice-print` (A4) |
| 10 | P6 | `admin/AD-01-health`، `AD-02-users`، `AD-04-white-label` (۱۲ بُعد + پیش‌نمایش تم)، `AD-06-settings`، `AD-07-audit`؛ یک تم white label نمونه روی `C-01` و `AG-03` |

قاعدهٔ اجرا: هر frame پیش از کدنویسی در Figma تأیید مالک می‌گیرد (کامنت «تأیید» روی frame)؛ شمارهٔ node در PR و در `docs/product/panels/FIGMA_MAP.md` 🆕 ثبت می‌شود. پس از پیاده‌سازی، اسکرین‌شات Playwright در 1440 و 390 کنار frame در گزارش QA می‌آید.

---

# ۶. فازهای تحویل، معیار پذیرش و آزمون‌ها

قواعد عمومی هر فاز: طراحی Figma تأییدشده ← پیاده‌سازی ← تست واحد backend (pytest) ← Playwright نقش‌محور در 1440 و 390 ← axe (بدون خطای serious/critical) ← گزارش QA و شواهد در `docs/product/panels/qa/phase-N/` ← commit و push به GitHub ← دیپلوی روی production با چک‌لیست `PRODUCTION_RUNBOOK.md` ← به‌روزرسانی `PROJECT_STATUS.md` (انجام‌شده، باقی‌مانده، گام بعد). هیچ فازی بدون شواهد QA «انجام‌شده» گزارش نمی‌شود. فایل‌های محافظت‌شده در هیچ فازی diff ندارند (تست CI: `git diff --name-only` روی فهرست محافظت‌شده باید خالی باشد).

## فاز ۰ (پیش‌نیاز امنیتی، هم‌زمان با فاز ۱)
- رفع C-1، H-1، H-2 با تست رگرسیون؛ HTTPS (H-3)؛ بررسی نقش دیتابیس بدون superuser (H-4)؛ M-1 (جریمه سمت سرور)؛ M-2 (فیلتر `/me/dashboard`)؛ پنهان کردن `/pilot`.
- **پذیرش:** `test_customer_cannot_transition`، `test_org_admin_cannot_fund`، `test_supplier_scope`، `test_refund_penalty_server_side` سبز؛ probeهای `security-review/` تکرار و رد شوند.

## فاز ۱: پوسته + رجیستری ناوبری + حلقهٔ لغو و استرداد مشتری + صف استرداد مالی
- **دامنه:** §1 کامل (shell، registry، `GET /me/capabilities`، PanelGuard، `middleware.ts`، Today endpoint، اجزای مشترک، اعلان، جست‌وجوی سراسری حداقلی، audit entity tab)؛ ناحیه‌های `ops` و `finance` جدا؛ C-01 تا C-07 و C-09؛ OPS-01 (حداقلی)، OPS-02 (صف `service_requests` و `failed_payments`)، OPS-03؛ FIN-01، FIN-02، FIN-03، FIN-04؛ رفع لینک مردهٔ PWA؛ مهاجرت صفحه‌های JourneyShell پنلی به PanelShell.
- **endpointهای 🆕:** `/me/capabilities`، `/panel/today`، `/me/service-requests`، `/me/refunds`، `/me/payments/failed`، `/reservations/{id}/timeline`، `/service-requests/{id}/withdraw|customer-decision`، `/backoffice/booking-requests/{id}/actions`، `/ops/queues/*`، `/finance/refunds*`، `/finance/funding-requests*`، `/finance/reconciliation/imports`، `/staff/search`، `/me/notifications/read-all`، `/audit/entities/{type}/{id}`.
- **معیار پذیرش:**
  1. هر یک از ۱۱ نقش پس از ورود به خانهٔ خودش می‌رود و فقط آیتم‌های مجاز را می‌بیند؛ هیچ آیتم منو 403 نمی‌دهد (Playwright برای هر نقش همهٔ لینک‌های منو را باز می‌کند).
  2. ورود مستقیم به URL غیرمجاز صفحهٔ NoAccess با نام مجوز را نشان می‌دهد و درخواست داده نمی‌فرستد.
  3. سناریوی کامل E2E-C (گام ۱ تا ۱۰، بدون مودیان واقعی) روی staging: مشتری درخواست می‌دهد، عملیات تأیید می‌کند، مالی به کیف پول و با ثبت پرداخت بانکی اجرا می‌کند، مشتری در C-04 کد پیگیری و وضعیت «پرداخت‌شده» را می‌بیند، ledger متوازن است.
  4. استرداد بالای آستانه بدون checker اجرا نمی‌شود؛ maker نمی‌تواند checker باشد.
  5. تکرار POST اجرای استرداد با همان کلید ← یک ledger entry.
  6. هر گام timeline بازیگر، زمان جلالی و گام بعدی با ETA دارد؛ SLA گذشته چیپ قرمز نشان می‌دهد.
  7. تطبیق: یک مغایرت نمونه match و resolve می‌شود.
  8. موبایل 390: bottom nav، wizard لغو و صف استرداد بدون اسکرول افقی کار می‌کنند؛ متن بدنه ≥ 16px در پنل مشتری.
  9. axe بدون خطای serious روی همهٔ صفحه‌های فاز.
- **آزمون‌ها:** `tests/test_nav_registry.py`، `test_capabilities_endpoint.py`، `test_service_request_state_machine.py` (همهٔ انتقال‌ها و 409ها)، `test_refund_queue.py` (MC، idempotency، مقصدها)، `test_reconciliation_actions.py`؛ `e2e/panels/role-smoke.spec.ts` (۱۱ نقش × ۲ اندازه)، `e2e/panels/refund-loop.spec.ts`، `e2e/panels/a11y.spec.ts`، `tests/panel/no-external-links.spec.ts`.

## فاز ۲: B2B آژانس و چارتر
- **دامنه:** AG-01، AG-02، AG-04، AG-05، AG-08، AG-10 / CH-01 تا CH-03، AG-13، AG-14، AG-15، AG-16، AG-17؛ OPS-08، OPS-09؛ FIN-05، FIN-06؛ S-11؛ AD-05 (flag چارتر)؛ مدل `agency_license`، `refund_policy`، `price_cap`، `inventory_item.tax_role/vat_category/owner_agency_id`؛ پیوند Agency↔Supplier و Safarsaz با AgencyMembership؛ ماژول‌های عضویت آژانس. سپس در همین فاز (موج دوم): AG-03 (فروش با markup)، AG-07، AG-11 (فایل)، AG-12 (API push)، CH-04، AG-18، AG-19، AG-20.
- **معیار پذیرش:**
  1. E2E-D کامل روی staging با یک آژانس آزمایشی (برچسب «نمونه»): ثبت مجوز ← تأیید ← ثبت بلوک ۱۰ صندلی بین‌المللی ← بازبینی و انتشار ← خرید مشتری ← صدور ← مانیفست ← صورت تسویه ← تأیید آژانس ← پرداخت.
  2. آژانس بدون `BAND_ALEF` معتبر نمی‌تواند پرواز ثبت یا ارسال کند (422 با پیام)؛ انقضای مجوز موجودی را معلق می‌کند (job تست‌شده با زمان جعلی).
  3. چارتر داخلی با flag خاموش در جست‌وجو نمی‌آید و رزرو آن 409 `CHARTER_DOMESTIC_DISABLED` می‌دهد؛ فقط PA می‌تواند flag را با دلیل و پیوست تغییر دهد.
  4. پاسخ API عمومی تور و پرواز و HTML صفحهٔ تور هیچ فیلد هویتی آژانس ندارد (R-PUB-1).
  5. آژانس A موجودی، رزرو، مانیفست و تسویهٔ آژانس B را نمی‌بیند (404)؛ آژانس هرگز منوی تأمین‌کننده نمی‌بیند.
  6. فروش هم‌زمان آخرین صندلی توسط دو مشتری: فقط یکی موفق.
  7. قیمت بالاتر از `price_cap` مسدود می‌شود.
  8. E2E-E: فروش با markup آژانس از اعتبار آژانس، hold/capture/release، استرداد به اعتبار آژانس.
  9. import فایل ۲۰۰ ردیف با ۳ ردیف خطادار: dry run خطاها را با شمارهٔ ردیف نشان می‌دهد و commit فقط ردیف‌های سالم را (یا هیچ، طبق گزینه) ثبت می‌کند؛ rollback پیش از فروش کار می‌کند.
  10. API push: کلید ابطال‌شده 401؛ rate limit 429؛ webhook فروش با امضا ارسال می‌شود.
- **آزمون‌ها:** `test_agency_license_rules.py`، `test_charter_domestic_flag.py`، `test_public_tour_no_agency_identity.py`، `test_agency_isolation.py`، `test_seat_concurrency.py`، `test_price_cap.py`، `test_agency_credit_hold_capture.py`، `test_inventory_import.py`، `test_partner_api_auth.py`، `test_settlement_two_sided.py`؛ `e2e/panels/charter-flow.spec.ts`، `agency-sell.spec.ts`.

## فاز ۳: سازمان، مأمور خرید و تأییدها
- **دامنه:** O-01 تا O-12 (P0 و P1)، A-01، A-02، E-01 تا E-03، PO-01 تا PO-04؛ `/me/approvals/inbox`؛ درخواست اعتبار به مالی.
- **معیار پذیرش:** E2E-A با ۶ آزمون فهرست‌شده و E2E-B با ۱۵ مسافر (۳ مهمان از فایل) سبز؛ کارمند فقط منوی ۵ آیتمی می‌بیند؛ مدیر سازمان هیچ مسیری برای افزایش اعتبار ندارد (فقط درخواست)؛ فاکتور سازمان بدون شناسهٔ ملی و اقتصادی صادر نمی‌شود؛ رد بدون دلیل ممکن نیست؛ import ۵۰۰ کارمند در کمتر از ۳۰ ثانیه با گزارش خطا.
- **آزمون‌ها:** `test_approval_routing.py` (آستانه، ارجاع، خودتأییدی)، `test_on_behalf_scope.py`، `test_org_credit_request_only.py`، `test_members_import.py`؛ `e2e/panels/org-approval.spec.ts`، `purchasing-group.spec.ts`.

## فاز ۴: مرکز عملیات سفر
- **دامنه:** OPS-01 کامل، OPS-02 (هر ۷ صف)، OPS-04 تا OPS-07، OPS-10، OPS-11؛ case per booking؛ SLA engine با جدول Master Spec؛ اعلام اختلال گروهی.
- **معیار پذیرش:** رزرو پرداخت‌شدهٔ صادرنشده پس از X دقیقه در صف `failed_issuance` با شدت CRITICAL ظاهر می‌شود؛ اعلام لغو یک پرواز برای همهٔ رزروهای آن case و اعلان می‌سازد و در فید دیده می‌شود؛ هر رزرو حداکثر یک case باز دارد و پیام‌ها و درخواست‌ها به آن متصل‌اند؛ نقض SLA اعلان سرپرست می‌فرستد؛ مشتری ۳۶۰ با جست‌وجوی موبایل در کمتر از ۲ ثانیه باز می‌شود و نمایش کد ملی audit ثبت می‌کند؛ صدور دستی و صدور دوبارهٔ واچر کار می‌کنند.
- **آزمون‌ها:** `test_case_bronze_rule.py`، `test_sla_engine.py`، `test_disruption_fanout.py`، `test_staff_search_masking.py`؛ `e2e/panels/ops-center.spec.ts`.

## فاز ۵: مالی و مودیان
- **دامنه:** FIN-09 تا FIN-14، جدول `order_line_financials` برای همهٔ رزروهای جدید، `tax_invoice` و Outbox مودیان با adapter TSP (ارسال واقعی پشت flag `moadian_live_send`)، گزارش VAT فصلی، چاپ فاکتور مشتری و صورت‌حساب سازمان (C-05، O-09).
- **معیار پذیرش:** هر فروش و هر استرداد سند مالیاتی درست (الگو، نوع، موضوع، مرجع) در صف می‌سازد؛ مثال‌های §3 و E2E-C عدد به عدد با تست برابرند؛ از روز ۸ هشدار و از روز ۱۱ قرمز؛ retry با backoff و بدون سند تکراری (idempotent بر اساس serial)؛ تغییر نرخ فقط با MC و تاریخ اعتبار آینده؛ گزارش VAT یک فصل نمونه با جمع ledger برابر است؛ PRINCIPAL تأییدنشده در گزارش علامت دارد؛ با flag خاموش هیچ درخواستی به بیرون نمی‌رود و وضعیت «آمادهٔ ارسال، اتصال برقرار نیست» صادقانه نمایش داده می‌شود.
- **آزمون‌ها:** `test_order_line_breakdown.py`، `test_tax_rates_effective_dated.py`، `test_moadian_document_builder.py` (الگوی ۱، الگوی ۶، نوع اول B2B، برگشت از فروش جزئی و کامل، اصلاحی)، `test_moadian_outbox_retry.py`، `test_vat_report.py`؛ `e2e/panels/finance-moadian.spec.ts`.

## فاز ۶: ادمین و white label
- **دامنه:** AD-01 تا AD-08، انتقال `/white-label` به پنل با ۱۲ بُعد، تم توکنی برای پنل‌ها، دعوت و غیرفعال‌سازی کاربر، الزام 2FA کارکنان، تنظیمات آستانه و SLA، و در صورت نیاز پرداخت با برند آژانس داخل کارن تراول.
- **معیار پذیرش:** یک tenant نمونه با تم دیگر روی پنل‌ها (بدون تغییر کد و بدون تغییر صفحهٔ اصلی) نمایش داده می‌شود و کنتراست AA حفظ می‌شود؛ ابعاد WL روی صادرکنندهٔ فاکتور، دریافت‌کنندهٔ وجه و مسئول استرداد اثر واقعی دارند (تست)؛ TA نمی‌تواند نقش PA بدهد؛ کارکنان بدون 2FA نمی‌توانند وارد ناحیه‌های ops و finance شوند؛ کاربر غیرفعال‌شده همهٔ نشست‌هایش باطل می‌شود.
- **آزمون‌ها:** `test_white_label_contract.py`، `test_role_escalation.py`، `test_staff_2fa_required.py`؛ `e2e/panels/white-label-theme.spec.ts`.

## پس از فازها (P2 باقی‌مانده)
تجربه‌ها و جاذبه‌ها (S-06)، نظرها (S-10)، duty of care (A-03)، جانشینی، API خروجی آژانس، اعتبار پویا از سابقهٔ تسویه، یکپارچه‌سازی و حذف کیت‌های قدیمی (`ConnectedViews`، `PanelViews`، ...)، کوکی HttpOnly (M-3)، گزارش‌های پیشرفته.

---

# ۷. پرسش‌های باز

## برای مالک (OQ-O)
1. **OQ-O1:** پایلوت با کدام آژانس‌ها و چارترکننده‌های واقعی؟ (برای دادهٔ staging و قرارداد)
2. **OQ-O2:** آستانهٔ maker-checker (پیشنهاد ۵۰ میلیون ریال) و سقف روزانهٔ شارژ هر کاربر مالی.
3. **OQ-O3:** کسر از حقوق کارکنان در فاز ۳ لازم است یا فقط تسویهٔ ماهانهٔ سازمان؟
4. **OQ-O4:** مدل درآمد B2B پیش‌فرض: net + markup آژانس، یا قیمت عمومی + کمیسیون به آژانس؟ (هر دو پشتیبانی می‌شوند؛ پیش‌فرض قرارداد لازم است)
5. **OQ-O5:** آیا آژانس خریدار واچر مسافر خودش را دانلود کند؟ (امروز فقط مشتری)
6. **OQ-O6:** مهلت تأیید تسویه توسط آژانس و تأمین‌کننده و قاعدهٔ تأیید ضمنی.
7. **OQ-O7:** آیا آژانس فروشنده قیمت فروش نهایی به مسافر را ببیند؟ (پیش‌فرض: خیر)
8. **OQ-O8:** SLA تأیید on-request و صدور برای موجودی آژانس‌ها (پیشنهاد ۲ ساعت کاری و ۳۰ دقیقه).
9. **OQ-O9:** کارمزد خدمات در لغو از سوی ایرلاین برگشت داده شود؟ (پیشنهاد: بله)

## برای حسابدار / مشاور مالیاتی (OQ-A)
1. **OQ-A1:** در فروش سیستمی (AGENT)، VAT آژانس فقط روی کمیسیون و کارمزد خدمات است؟ ثبت قرارداد حق‌العمل‌کاری در مودیان لازم است؟
2. **OQ-A2:** پکیج تور (PRINCIPAL): مبنا کل قیمت یا حاشیه؟ تفکیک اجزای معاف؛ وضعیت تور ورودی و خروجی.
3. **OQ-A3:** صادرکنندهٔ الگوی ۶ نوع اول (ایرلاین یا آژانس)؟ شمارهٔ الگو در راهنمای فنی جاری هنوز ۶ است؟
4. **OQ-A4:** شناسه‌های ۱۳ رقمی کالا و خدمت برای کارمزد خدمات مسافرتی، تور داخلی و خارجی، رزرو هتل، ویزا.
5. **OQ-A5:** VAT پرواز بین‌المللی امروز (شماره و تاریخ بخشنامه).
6. **OQ-A6:** چارترکننده اصیل است؟ اعتبار خرید از ایرلاین چگونه تا مالیات دوبار حساب نشود؟ کدام الگو برای فروش چارتر؟
7. **OQ-A7:** استرداد: برگشت از فروش یا ابطالی؟ صورتحساب جدا برای جریمه؟ مهلت ثبت برگشت و تأیید خریدار.
8. **OQ-A8:** مهلت ارسال در آبان ۱۴۰۵ هنوز ۱۲ روز است؟
9. **OQ-A9:** نرخ ۱۴۰۵: ۱۰٪ یا ۱۲٪ (بند قانون بودجه).
10. **OQ-A10:** نرخ تبدیل ارز برای تور خارجی.
11. **OQ-A11:** مالیات تکلیفی (ماده ۱۰۴) در پرداخت به آژانس‌ها و راهنمایان.
12. **OQ-A12:** TSP یا API مستقیم؛ حافظهٔ مالیاتی به نام کدام شخص حقوقی (کارن تراول یا تاژبان)؟
13. **OQ-A13:** مدت نگهداری اسناد و پاسخ خام مودیان.

## برای وکیل / امور صنفی (OQ-L)
1. **OQ-L1:** کارن تراول با مجوز کدام شخص حقوقی (تاژبان؟) و کدام بندها فعالیت می‌کند؟ مجوز فروش آنلاین سازمان هواپیمایی و سامانهٔ فروش آنلاین وزارت میراث وجود دارد؟
2. **OQ-L2:** شیوه‌نامهٔ سامانهٔ فروش آنلاین گردشگری **نمایش نام و مجوز برگزارکننده** را روی صفحهٔ تور الزامی کرده است؟ (تعارض با D3؛ تا پاسخ، R-PUB-1 برقرار است و نام برگزارکننده فقط در قرارداد و واچر پس از خرید در صورت الزام می‌آید)
3. **OQ-L3:** مسئولیت پلتفرم در برابر مسافر هنگام فروش موجودی آژانس همکار؛ بندهای لازم قرارداد همکاری (غرامت، بیمه، ضمانت‌نامه).
4. **OQ-L4:** وضعیت فعلی ممنوعیت فروش چارتری پرواز داخلی (شرط روشن کردن `charter_domestic_sale`) و الزامات چارتر خارجی.
5. **OQ-L5:** سقف قیمت فعلی سازمان هواپیمایی و تبعیت markup بین‌آژانسی از آن.
6. **OQ-L6:** قواعد تغییر نام و نرخ کودک و نوزاد در چارتر.
7. **OQ-L7:** مرجع رسمی استعلام مجوز آژانس‌ها (برای خودکار کردن `license:verify`).
8. **OQ-L8:** اعتبار آیین‌نامهٔ ۱۳۸۰ یا جایگزین آن.
9. **OQ-L9:** زیرمجموعه‌ای که فقط می‌فروشد می‌تواند زیر مجوز والد یا Licensed Entity فعالیت کند؟
10. **OQ-L10:** نگهداری و افشای دادهٔ مسافر به آژانس فروشنده (کد ملی و گذرنامه در مانیفست): مبنای قانونی و حداقل داده.

---

## پیوست: نگاشت به گپ‌های ممیزی

| گپ ممیزی | پوشش در این سند |
|---|---|
| P0-1 حلقهٔ پس از فروش | OPS-03، C-03، C-04، E2E-C، فاز ۱ |
| P0-2 صف استرداد مالی | FIN-02، فاز ۱ |
| P0-3 ناوبری نقش‌محور و guard | §1.2، §1.3، فاز ۱ |
| P0-4 ورود تورهای آژانس | AG-08، پیوند Agency↔Supplier، فاز ۲ |
| P0-5 لینک مردهٔ PWA | C-11، فاز ۱ |
| P0-6 اقدام تطبیق | FIN-04، فاز ۱ |
| P1-1 فاکتور و صدور دوبارهٔ واچر | C-05، OPS-06، FIN-13 |
| P1-2 / P1-3 مشتری ۳۶۰، داشبورد، case | OPS-01، OPS-04، OPS-05 |
| P1-4 / P1-5 تأمین‌کننده و مانیفست | S-03، AG-13، AG-14 |
| P1-6 / P1-7 RFQ و تأییدکننده | PO-04، S-09، A-01، O-05 |
| P1-8 ویزا | OPS-11 |
| P1-9 مشتری (ویرایش مسافر، اعلان، تراکنش، نشست) | C-06، C-07، C-08، C-10 |
| P1-10 کاربران ادمین | AD-02 |
| P1-11 چرخهٔ عمر تأمین‌کننده و نظرها | OPS-10، S-10 |
| P2-1 تا P2-10 | §1 (کیت واحد، توکن، پوسته)، فاز ۶ و «پس از فازها» |
| امنیت C-1، H-1، H-2، M-1، M-2 | فاز ۰، §4 |
