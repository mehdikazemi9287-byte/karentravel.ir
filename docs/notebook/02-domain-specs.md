# کارن تراول — مشخصات دامنه‌ها

> منبع: مخزن karentravel.ir — تجمیع خودکار برای Gemini Notebook (2026-11-24)


---

## فایل: DOMAIN_MAP.md

# Domain Map

| Bounded Context | مسئولیت | رویداد/مرز نمونه |
|---|---|---|
| Identity, Tenant, White Label | هویت، عضویت، دامنه و theme | TenantProvisioned |
| Catalog, Inventory, Search | عرضه نرمال‌شده و کشف | OfferUpdated |
| Comparison, Trip Assistant | تصمیم‌یار و ترکیب سفر | ComparisonSaved |
| Booking, Fulfillment | lifecycle رزرو و صدور | BookingConfirmed |
| Corporate Policy, Credit | eligibility، سهمیه، approval | ApprovalRequested |
| Wallet, Payment, Settlement | ledger، پرداخت، refund، تسویه | PaymentCaptured |
| Promotion, Loyalty, CRM | مشوق و ارتباط | PromotionApplied |
| CMS, Reporting, Support | محتوا، گزارش، رسیدگی | CaseOpened |
| Integration Hub, Provider Mgmt | adapter، routing، health | ProviderDegraded |
| Notification, Audit | اطلاع‌رسانی و رخدادهای غیرقابل‌انکار | AuditRecorded |

مرزها از ابتدا در Modular Monolith برقرار می‌شوند تا جداسازی سرویس در آینده براساس بار/مالکیت امکان‌پذیر باشد.
# دامنه‌های افزوده‌شده

- Identity: `OTPChallenge`، `AuthenticationState`، `AuthenticationAudit`، `RefreshTokenSession`
- Finance: `PaymentIntent`، `PaymentEvent`، `RefundRecord`، `Wallet`، `FinancialLedgerEntry`
- Operations: `Trip`، `TripEventRecord`، `NotificationRecord`، `OutboxEvent`
- Commerce: `Offer`، `PriceCheck`، `BookingItem`، `BookingStatusHistory`، `Voucher`
- Corporate: `Department`، `CostCenter`، `EmployeeAssignment`، `ApprovalTemplate` و stepهای instance
- Tenant configuration: `WhiteLabelConfiguration` و Agency hierarchy

---

## فایل: BOOKING_MANAGEMENT_SPEC.md

# Booking Management & After-Sales Specification

## اصل تجربه

پیش از هر تغییر، کنسلی یا استرداد، نتیجه و هزینه باید به کاربر نمایش داده شود. کلیک اولیه هیچ رزروی را تغییر نمی‌دهد. نسخه فعلی صرفاً Mock و fail-closed است.

## دامنه خدمات

پرواز، هتل، اقامتگاه، قطار، تور، اجاره خودرو، ترانسفر، تجربه و سایر خدمات قابل رزرو از یک مدل مشترک استفاده می‌کنند؛ ruleهای هر نوع خدمت و Provider جدا ارزیابی می‌شوند.

## snapshot و policy جاری

- `policyAtBooking`: snapshot تغییرناپذیر قوانین زمان خرید، همراه نسخه و زمان ثبت.
- `currentPolicy`: آخرین policy دریافت‌شده برای ارزیابی شرایط جاری.
- اختلاف این دو باید برای audit حفظ شود و policy جدید نباید بی‌صدا جای تعهد زمان خرید را بگیرد.

## مسیر درخواست

`ثبت درخواست → در حال بررسی → در انتظار تأمین‌کننده → نیازمند اقدام کاربر → تأیید/رد → در حال بازپرداخت → بازپرداخت شد → بسته شد`

مسیرهای voluntary، provider disruption، exceptional و platform/operational error rule path یکسان ندارند.

## Quote و confirmation

هر `CancellationQuote` یا `ChangeQuote` شامل eligibility، deadline، policy source، جریمه و مبلغ قابل استرداد است. اگر Provider معتبر در دسترس نباشد، مبلغ‌ها `unknown` می‌مانند و پیام «نیاز به بررسی قوانین تأمین‌کننده» نمایش داده می‌شود. تأیید نهایی prototype فقط escalation نمایشی می‌سازد و mutation واقعی ندارد.

## AI و پشتیبانی

AI از Booking Context intentهای کنسلی، مبلغ بازگشت، تغییر تاریخ/اتاق/شب، لغو Provider، واچر جدید و وضعیت استرداد را تشخیص می‌دهد؛ عدد یا eligibility تولید نمی‌کند. نبود policy معتبر به hand-off «ارسال برای بررسی کارشناس» ختم می‌شود.

## Visibility و context

SupportDock در gateway و تمام سطوح سفر حضور دارد. AI، کارشناس انسانی، پیگیری رزرو، after-sales و مشکل فوری actionهای مستقل‌اند. وقتی Trip Context موجود است، مقصد در prompt کمک نمایش داده می‌شود؛ disruption ثبت‌شده نیز پیام مستقل و Mock دارد.

برای اقامت، action catalog شامل refundable/non-refundable، deadline، penalty نزدیک check-in، no-show، تغییر تاریخ/اتاق/مهمان/شب، early checkout، late arrival، لغو Provider، voucher mismatch و revised voucher است. برای حمل‌ونقل، voluntary cancellation، disruption/delay، تغییر تاریخ، rebook/reissue، no-show، penalty و refundable amount جدا مدل می‌شوند؛ availability هر مورد از Provider می‌آید.

## پذیرش و Rollback

- `/manage-booking/book1` summary، action selector، policy preview، confirmation و request timeline دارد.
- CTA مدیریت رزرو در My Trip، confirmation، BookingCard، VoucherCard، AI و Support دیده می‌شود.
- شناسه نامعتبر `404` است؛ هیچ درخواست یا transaction واقعی ساخته نمی‌شود.
- Rollback با حذف route/component مدیریت رزرو و مدل‌های policy این فاز انجام می‌شود؛ migration یا داده پایدار ندارد.

## زبان مشتری

اصطلاحات فنی در model باقی می‌مانند اما UI آن‌ها را به «قوانین رزرو»، «امکان انجام درخواست»، «تغییر و صدور مجدد»، «نیاز به بررسی تأمین‌کننده» و «نسخه نمایشی» ترجمه می‌کند. تنها وضعیت جاری timeline تأکید بصری دارد و پیش از تأیید نهایی جمله «تا قبل از تأیید نهایی، رزرو شما تغییری نمی‌کند» نمایش داده می‌شود.

---

## فایل: TRIP_LIFECYCLE_SPEC.md

# Trip Lifecycle Specification

## هدف و مرز فاز

این فاز رزرو را به یک `Trip Context` پایدار وصل می‌کند تا مقصد، تاریخ، مسافران، رزروها و اقدامات مفید دوباره از کاربر پرسیده نشوند. پیاده‌سازی فعلی prototype و داده‌ها Mock هستند؛ هیچ رزرو، واچر، موجودی، قیمت، اعتبار یا پرداخت واقعی ایجاد نمی‌شود.

## چرخه اصلی

`SEARCH → BOOKING → ORDER → VOUCHER → TRIP → BEFORE → DURING → NEARBY → SERVICES → SUPPORT → AFTER`

- **Search:** نیاز ساختاریافته کاربر را جمع می‌کند.
- **Booking/Order:** انتخاب را به سفارش backend-authoritative تبدیل می‌کند.
- **Voucher:** تنها پس از تأیید Provider معتبر صادر می‌شود.
- **Trip:** context مرکزی میان رزرو، مسافر، مقصد، خدمات و پشتیبانی است.
- **Before:** مدارک، اقامت، ترانسفر، بیمه، checklist و reminder.
- **During:** دسترسی سریع به واچر، اقامت، Nearby، حمل‌ونقل و پشتیبانی.
- **After:** رسیدها، بازخورد و پاداش احتمالی بدون ادعای موجودی واقعی.
- **Manage Booking:** preview قوانین و پیامد، confirmation آگاهانه و tracking درخواست؛ بدون تغییر مستقیم پس از اولین کلیک.

## مدل وضعیت

سه stage نمایشی `before | during | after` وجود دارد. stage واقعی باید از زمان backend و وضعیت رزرو محاسبه شود؛ query string فقط برای preview نمونه به کار می‌رود و authority نیست.

## رویدادهای سفر و مرکز زنده سفر

`TripEvent` واحد مشترک تغییرات مهم سفر است و به `Trip` و در صورت نیاز `Booking` متصل می‌شود. منبع رویداد میان سیستم/تأمین‌کننده، دستیار و پشتیبانی انسانی تفکیک می‌شود و وضعیت راستی‌آزمایی آن صریح باقی می‌ماند. جریان هدف:

`Provider / Admin → TripEvent → Trip Timeline → NotificationProvider → In-app / Push / SMS / Web / Human Support`

در prototype فقط رویدادهای نمونه در Web نمایش داده می‌شوند. Push، SMS، webhook تأمین‌کننده، delivery receipt و پیام کارشناس متصل نیستند و provider اعلان برای ارسال، نتیجهٔ `not-sent` برمی‌گرداند. deep link رویداد باید به `/trips/[id]?event=[eventId]`، مدیریت رزرو یا پشتیبانی ختم شود و کاربر را به Homepage نفرستد.

ترجیحات اعلان سبک و چهار موضوع «تغییر مهم سفر»، «به‌روزرسانی رزرو»، «تغییر/استرداد» و «پیام پشتیبانی» را برای کانال‌های app، push و sms مدل می‌کند. ذخیره و اعمال واقعی ترجیحات خارج از این فاز است.

## پذیرش

- `/trips` و `/trips/[id]` برای سفر نمونه شیراز قابل دسترسی‌اند.
- جزئیات سفر timeline، رزرو، واچر، مسافر، تاریخ، خدمت خریداری‌شده و اقدام باقی‌مانده دارد.
- confirmation کاربر را خودکار به تبلیغ منتقل نمی‌کند و انتخاب «ورود به سفر من» را نگه می‌دارد.
- دستیار AI و پشتیبانی انسانی دو مسیر متمایز و context-aware دارند.
- داده Mock در سطح صفحه و اجزای حساس برچسب‌گذاری می‌شود.
- Trip Timeline می‌تواند چند `TripEvent` نمونه را سبک و بدون بازطراحی صفحه نمایش دهد و query پارامتر `event` رویداد مقصد را برجسته کند.

## Rollback

حذف component رویداد، داده نمونه و interface اعلان این افزونه کافی است؛ migration، credential، رکورد مالی یا اتصال خارجی ایجاد نمی‌شود.

---

## فایل: TRIP_ASSISTANT_SPEC.md

# Trip Assistant Specification

دستیار گفت‌وگویی نیاز، زمان، مبدا/مقصد، بودجه، نفرات و ترجیح را جمع می‌کند؛ itinerary ترکیبی پرواز/قطار/اقامت/تور/خودرو/بیمه/تجربه می‌سازد، policy سازمان را اعمال و دلیل پیشنهاد را بیان می‌کند. برنامه ذخیره/اشتراک/ارسال approval و همراهی پیش/حین/پس از سفر دارد.

LLM فقط intent، explanation و orchestration انجام می‌دهد. قیمت، ظرفیت، قانون، eligibility و approval از ابزارهای authoritative خوانده می‌شوند؛ نبود ابزار معتبر به پاسخ «قابل استعلام نیست» ختم می‌شود. guardrail: PII minimization، policy check، human handoff، trace و feedback.

Prototype فقط نمای گفتگو و نقشه مسیر است و هیچ اتصال AI یا نرخ زنده را ادعا نمی‌کند.

---

## فایل: WHITE_LABEL_SPEC.md

# White Label Specification

Tenant-aware: `tenant_id`، domain binding، branding token، content namespace، feature flags، policy namespace، data isolation و audit مستقل. سازمان می‌تواند کاملاً خودگردان یا managed مشترک با کارن‌سیر باشد.

مدیر سازمان کارکنان، واحد، شعبه، خانواده، نقش، تأمین‌کننده، بودجه/اعتبار، approval، محتوا، درخواست، پرداخت/تسویه و گزارش را مدیریت می‌کند. نقش‌ها شامل Organization Admin، Welfare، Finance، Travel Approver و Operator است.

دامنه custom پس از اعتبارسنجی DNS/TLS فعال می‌شود. هیچ tenant با کپی پروژه ساخته نمی‌شود. RLS و تست نفوذ بین‌مستاجری در backend مرحله بعد اجباری است.

---

## فایل: COMPARISON_ENGINE_SPEC.md

# Comparison Engine Specification

کاربر ۲ تا ۴ گزینه پرواز، هتل، تور، قطار، خودرو، بیمه، پکیج یا رفاه را کنار هم می‌بیند. معیارها: قیمت نهایی/کل سفر، کیفیت/امتیاز، value، موقعیت، زمان/مدت/توقف/بار، کلاس/امکانات، کنسلی، کیفیت Provider، policy، کیف پول و سهم نقدی/اقساطی.

نرمال‌سازی واحد پول/مالیات/قانون و timestamp الزامی است. tagها rule-based و explainable هستند: «بهترین قیمت» کمترین total معتبر؛ «بهترین کیفیت» بیشترین quality score با حداقل داده؛ «بهترین ارزش» score وزن‌دار پیکربندی‌شده؛ «بهترین انتخاب سازمانی» منطبق با policy و بودجه. داده ناقص tag قطعی نمی‌گیرد.

---

## فایل: NEARBY_SERVICES_SPEC.md

# Nearby & Services Specification

## Nearby context

`/nearby` یک همراه محلی است، نه صرفاً نقشه. سه context را می‌پذیرد:

1. موقعیت فعلی کاربر، فقط پس از رضایت و مجوز location؛
2. اطراف محل اقامت از Trip Context؛
3. اطراف مقصد سفر از Trip Context.

نسخه فعلی از مختصات نمونه شیراز و `MockPlaceProvider` استفاده می‌کند و هیچ Google/Maps API یا location واقعی فعال نیست.

## تمایز منبع و رابطه تجاری

- `contracted`: شریک نمونه کارن‌سیر؛ فقط با نشان «شریک نمونه».
- `credit-enabled`: پذیرنده نمونه اعتبار؛ با نشان کوتاه «اعتبارپذیر».
- `external`: مکان عمومی منبع Mock؛ بدون نشان شراکت یا مزیت.

نام‌ها، فاصله‌ها، ساعات و مزیت‌ها همگی نمونه‌اند و قرارداد واقعی را القا نمی‌کنند.

## Provider ports

- `PlaceProvider.searchNearby({ latitude, longitude, radius, category, sort })`
- `MapProvider.getViewport(...)`
- `BookingProvider.createBooking(...)`
- `NotificationProvider.listForTrip(...)`
- `PaymentProvider.authorize(...)`

UI فقط به interfaceهای دامنه وابسته است؛ adapter آینده Google Places یا هر Provider دیگر منطق تجاری اختصاصی را وارد component نمی‌کند.

## پذیرش و Rollback

- `/nearby` context selector، category control، map surface و results sheet responsive دارد.
- `/services` خدمات actionable را از مقصدهای الهام‌بخش جدا می‌کند.
- نبود اتصال واقعی صریح، fail-closed و بدون CTA پرداخت/رزرو قطعی است.
- Rollback با حذف routeهای `nearby/services` و module provider Mock انجام می‌شود و داده پایداری را تغییر نمی‌دهد.

---

## فایل: ACCEPTANCE_CRITERIA.md

# Acceptance Criteria

## Production isolation and traffic controls — ۱۴۰۵/۰۵/۲۸

- PostgreSQL بدون `app.tenant_id` هیچ رکورد tenant-scoped را نمایش یا قبول نمی‌کند؛ context مستأجر A، داده مستأجر B را نه می‌خواند و نه mutate می‌کند.
- تمام جدول‌های دارای `tenant_id` به‌صورت خودکار در migration پوشش داده می‌شوند و تست schema از جاافتادن جدول جلوگیری می‌کند.
- Production بدون PostgreSQL، Redis سالم، secret معتبر و HTTPS origin بالا نمی‌آید.
- rate limit بین processها با Redis مشترک است، token خام را در key نگه نمی‌دارد و `429/Retry-After` قابل آزمون دارد.
- adapterهای بدون secret reference و endpoint مجاز هیچ موفقیت Provider/OTP/Payment اعلام نمی‌کنند.
- E2E ورود، جست‌وجو، رزرو، تأیید، dashboard و after-sales را پوشش می‌دهد؛ نبود browser اجرایی صریحاً blocker است.

## سخت‌سازی فرمان رزرو دستی — ۱۴۰۵/۰۵/۲۸

- `POST /bookings` بدون `Idempotency-Key` معتبر fail-closed است.
- retry همان payload در tenant یک رزرو و یک کاهش موجودی ایجاد می‌کند؛ reuse کلید برای payload متفاوت `409` است.
- قیمت نهایی و کنترل موجودی فقط در transaction backend انجام می‌شوند و ردیف موجودی در PostgreSQL lock می‌شود.
- rollback مطابق `ADR-002` بدون حذف داده یا migration است.

## اجرای سه‌فازی تکمیل محصول — ۱۴۰۵/۰۵/۲۶

- Homepage پس از قفل فاز اول فقط یک کارت بنفش فشرده در بخش AI دارد؛ wrapper ثابت تمام‌عرض از Home حذف می‌شود، نوار کورال خالی حفظ می‌شود و Search چهار ورودی اصلی «پرواز»، «هتل»، «تور + هتل» و «تشریفات فرودگاه» را نمایش می‌دهد.
- rollback فاز اول محدود به `app/page.tsx` و قواعد انتهایی Homepage در `app/globals.css` است.
- فاز عملیاتی فقط schema و serviceهای افزایشی tenant-aware، idempotent و fail-closed اضافه می‌کند و جدول‌های پایلوت موجود یا seed فعلی را حذف نمی‌کند.
- فاز Production adapter واقعی را بدون credential فعال نمی‌کند؛ health/readiness، outbox، logging، Docker و runbook باید مستقل از اتصال بیرونی قابل آزمون باشند.
- هر آزمون یا integration غیرقابل اجرا صریحاً blocked ثبت می‌شود و موفق تلقی نمی‌شود.

## Prototype UI

- صفحات خانه، نتایج هتل، comparison، assistant، سازمان، کارمند/اعتبار، White Label و Integration Center در RTL و mobile/desktop قابل دسترسی‌اند.
- همه داده‌های نمونه/مالی و وضعیت‌ها Mock هستند؛ پرداخت و integration حقیقی القا نمی‌شوند.
- دو tenant فرضی با نام/داده و theme جدا قابل‌مشاهده‌اند؛ provider به tenant بدل نشده است.
- comparison حداقل ۲ هتل و rule tagهای explainable دارد.
- assistant محدودیت اتصال و عدم تولید قیمت زنده را صریح نشان می‌دهد.
- `npm run lint` و `npm run build` موفق‌اند.

## قبل از فاز backend

تأیید بصری مالک، تأیید IA و سیاست multi-tenant، و توافق روی acceptance هر ماژول لازم است.
# فاز Homepage یکپارچه — ۱۴۰۵/۰۵/۲۵

## دامنه مصوب

- صفحه اصلی فارسی و RTL با هویت سرمه‌ای/فیروزه‌ای، منطبق با جهت بصری Figma و بدون کپی از محصول ثالث.
- ناوبری، Hero، جست‌وجوی چندخدمتی، سفرهای منتخب، دستیار سفر، مقایسه، خدمات مقصد، راهکار سازمانی، اکوسیستم، شرکا، اعتماد و Footer کامل.
- همه قیمت‌ها و داده‌های نمایشی با برچسب صریح «Mock»؛ هیچ قیمت، موجودی، اعتبار یا policy در frontend معتبر تلقی نمی‌شود.
- مسیرهای موجود `/hotels`، `/compare`، `/assistant`، `/organization`، `/employee`، `/white-label`، `/integrations` و `/pilot` حفظ می‌شوند.

## پذیرش

- در عرض‌های ۳۷۵، ۷۶۸ و ۱۴۴۰ پیکسل overflow افقی، بریدگی متن یا شکست ناوبری وجود نداشته باشد.
- کنترل‌های تعاملی focus-visible، نام دسترس‌پذیر و حداقل کنتراست مناسب داشته باشند.
- حالت‌های loading، empty، error و success برای جست‌وجوی نمایشی قابل مشاهده/آزمایش باشند.
- `npm run lint`، `npx tsc --noEmit` و `npm run build` موفق باشند؛ تست API موجود نیز بدون regression اجرا شود.

## Rollback

بازگشت این فاز فقط با برگرداندن فایل‌های Homepage/design-system و بخش همین سند انجام می‌شود و هیچ migration، credential، provider یا داده پایدار را درگیر نمی‌کند.

## پالایش Human-Centered Homepage

- موتور جست‌وجو در Desktop حدود ۸۰ تا ۹۰ درصد عرض محتوای اصلی را اشغال می‌کند و برای پرواز، اقامت، قطار، تور، بوم‌گردی، خودرو، ترانسفر و خدمات سفر فرم متناسب نشان می‌دهد.
- ورودی زبان طبیعی صرفاً به‌عنوان رابط آماده اتصال نمایش داده می‌شود و تا زمان Provider معتبر با برچسب Mock و رفتار fail-closed باقی می‌ماند.
- سفرهای منتخب اطلاعات تصمیم‌ساز کوتاه، دستیار توضیح‌پذیری و کنترل کاربر، و مقایسه معیارهای قابل فهم دارد.
- بخش سازمانی اعتبار Mock را از سهم شخصی و گردش تأیید تفکیک می‌کند؛ هیچ مانده یا policy در frontend معتبر نیست.
- بخش «با خیال راحت سفر کن» ساختار مجوز، حقوق مسافر، پرداخت و تأمین‌کننده را بدون شماره، نشان یا ادعای ساختگی فراهم می‌کند.
- Homepage همچنان درگاه اکوسیستم است؛ عمق مقصد، تجربه، تجارت سفر، حساب، سازمان و تأمین‌کننده در معماری مسیرهای مستقل حفظ می‌شود.

Rollback این پالایش محدود به اجزای Homepage و CSS مربوط به آن است و هیچ schema، داده پایدار یا اتصال خارجی را تغییر نمی‌دهد.

## Trip Context Prototype

- سفر نمونه تهران به شیراز از confirmation به `/trips/mock-shiraz-1405` متصل است.
- timeline هر سه stage و اقدامات context-aware را بدون پرسش دوباره مقصد/تاریخ/مسافر نمایش می‌دهد.
- Nearby منبع مکان و نوع رابطه تجاری را صریح تفکیک می‌کند.
- badge اعتبار فقط زبان بصری کوتاه است و balance یا authorization را در frontend قطعی نمی‌کند.
- `/services` از grammar کارت مقصد استفاده نمی‌کند و CTAهای اقدام‌محور دارد.
- lint، strict typecheck، تست backend و HTTP 200 تمام routeهای جدید و قبلی الزامی‌اند.

Rollback: حذف فایل‌های route و `lib/domain`/`components/journey` این فاز؛ بدون migration یا تغییر داده موجود.

## Manage Booking & Unified Services

- `/manage-booking/book1` برای پرواز نمونه و معماری policy-neutral قابل اجراست.
- policy زمان خرید از policy جاری جداست و مبلغ جریمه/استرداد بدون Provider معتبر unknown باقی می‌ماند.
- actionهای کنسلی و تغییر ابتدا preview و سپس confirmation صریح نشان می‌دهند.
- timeline درخواست تمام وضعیت‌های استاندارد after-sales را مدل می‌کند.
- Services Hub در Homepage فقط میان Search و مقصدها افزوده می‌شود و ساختار مقصد/سفر منتخب را تغییر نمی‌دهد.
- CTA مدیریت رزرو از Trip، confirmation، booking، voucher، assistant و support قابل دسترسی است.
- شناسه booking/trip نامعتبر 404؛ lint، typecheck، backend tests و route checks موفق باشند.

## Support Visibility & Service-Specific After-Sales

- Header عمومی ورودی «پشتیبانی» دارد و کنار Search یک CTA انسانی بدون ادغام بصری با AI دیده می‌شود.
- SupportDock در Home، Trip، Nearby، Services و Manage Booking پنج اقدام مشخص دارد و در context سفر نام مقصد را نمایش می‌دهد.
- رزرو دارای disruption پیام «تغییری در سفرت پیش آمده؟» را با برچسب Mock نشان می‌دهد.
- `/manage-booking/book1` مسیر حمل‌ونقل و `/manage-booking/book2` مسیر اقامت را با actionها و policy coverage متفاوت نمایش می‌دهند.
- اولین کلیک هیچ mutation ندارد؛ quote و policy نامعتبر مبلغ، جریمه یا eligibility تولید نمی‌کنند.
- تمام ۹ status درخواست شامل حالت ردشده در timeline حضور دارند.
- `/support` مسیرهای AI، کارشناس، پیگیری، واچر، after-sales و مشکل فوری را بدون ادعای availability واقعی جدا می‌کند.

Rollback این مرحله محدود به SupportDock، CTA کنار Search، route پشتیبانی و تنظیمات service-specific صفحه Manage Booking است؛ داده پایدار یا Provider تغییر نمی‌کند.

## Consumer UX Refinement

- UI اصلی after-sales هیچ واژه توسعه‌دهنده‌محور مانند Mock، policy، eligibility، snapshot، rebook/reissue، backend یا SLA نشان نمی‌دهد.
- هر صفحه فقط یک اعلان «نسخه نمایشی — اطلاعات این بخش نمونه است» دارد.
- Manage Booking به‌ترتیب خلاصه رزرو، چهار اقدام، پیش‌نمایش پیامد، قوانین مرتبط، timeline و کمک نمایش داده می‌شود.
- مبلغ، جریمه، مهلت یا زمان بررسی نامعتبر با متن صادقانه «پس از بررسی نمایش داده می‌شود» جایگزین می‌شود.
- timeline هر ۹ وضعیت را نگه می‌دارد اما فقط وضعیت جاری برجسته است.
- AI و کارشناس انسانی خانواده بصری و توضیح نقش متفاوت دارند.
- SupportDock در Desktop فشرده و در Mobile به trigger جمع‌شونده تبدیل می‌شود و CTAهای صفحه را نمی‌پوشاند.

Rollback این refinement فقط CSS و componentهای presentation را برمی‌گرداند؛ model، route، policy snapshot و قابلیت‌های موجود حذف یا تغییر نمی‌کنند.

## Trip Operations Foundation

- `TripEvent` به‌صورت provider-neutral به Trip و Booking اختیاری متصل است و منبع AI با human support یکسان مدل نمی‌شود.
- رویدادهای نمونه در `/trips/mock-shiraz-1405` نمایش داده می‌شوند و deep link با query پارامتر `event` همان رویداد را هدف می‌گیرد.
- `NotificationProvider` کانال‌های in-app، push و sms را می‌شناسد، اما implementation نمونه هیچ پیام واقعی ارسال نمی‌کند.
- تنظیمات ترجیح اعلان فقط مدل دامنه دارد؛ صفحه تنظیمات، webhook، Push، SMS و اتصال realtime در این فاز ساخته نمی‌شود.

Rollback با حذف داده/نمای رویداد و provider نمونه انجام می‌شود و به رزرو، پشتیبانی یا Homepage آسیبی نمی‌زند.

## بازطراحی قطعی Homepage بر اساس مرجع JPEG

- نگاه اول باید Hero معماری یزد، تیتر «سفر را زندگی کن»، زمینه کرم و ترکیب بنفش/کورال را منتقل کند.
- مقصدهای قشم، شیراز، اصفهان و ماسوله با collage نامتقارن و سفرهای منتخب با سه کارت تصویری نمایش داده شوند.
- همراه هوشمند آبی روشن، نوار مقایسه بنفش، بخش سازمانی مصور و Footer منحنی بنفش الزامی‌اند.
- محتوای اکوسیستم، خدمات محلی، وایت‌لیبل، اعتبار سازمانی و تأمین‌کنندگان حذف نشود و در تراکم مرجع ادغام شود.
- در عرض‌های ۱۴۴۰، ۷۶۸ و ۳۷۵ پیکسل overflow افقی و شکست RTL وجود نداشته باشد.
- بلافاصله پس از «سفرهای منتخب» و پیش از مقایسه، بخش فشردهٔ «دستیار هوشمند سفر کارن‌سیر» با badge صریح AI، پنج قابلیت و CTA به `/assistant` قرار گیرد.
- بخش AI فقط از کرم، بنفش و کورال Homepage استفاده کند و از پشتیبانی انسانی متمایز باشد؛ در Mobile یک دکمهٔ ثابت کوچک «دستیار AI» بدون پوشاندن SupportDock نمایش داده شود.
