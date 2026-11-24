# کارن تراول — محصول، کسب‌وکار و برند

> منبع: مخزن karentravel.ir — تجمیع خودکار برای Gemini Notebook (2026-11-24)


---

## فایل: PRODUCT_VISION.md

# Product Vision — کارن‌سیر

کارن‌سیر یک اکوسیستم سفر، رفاه سازمانی، تجربه و فرهنگ مقصد است؛ نه یک فروشگاه تور یا هتل. In-house پلتفرم دیجیتال سفر و رفاه، تاژبان گشت پارس اپراتور خدمات سازمانی و گردشگری، و پادویرا بازوی فرهنگی/هنری/رویدادی اکوسیستم هستند. هر یک هویت مستقل دارند. 60Online/70Online فروشگاهی مستقل است و فقط در آینده می‌تواند از API/Event مرزی استفاده کند.

## چشم‌انداز

تبدیل‌شدن به زیرساخت قابل‌اعتماد و چندمستاجری برای طراحی، خرید، تأیید، رزرو، پرداخت و پشتیبانی سفر و رفاه؛ برای سازمان‌ها، کارکنان، آژانس‌ها، مسافران و تأمین‌کنندگان.

## اصول محصول

- سفر کامل، نه فروش تک‌محصولی؛ تصمیم‌ها از جست‌وجو تا بازگشت پوشش داده می‌شوند.
- اولویت تجاری با رفاه و گردشگری سازمانی، بدون حذف B2C، Partner و API.
- اعتمادپذیری عملیاتی: قیمت، ظرفیت و قانون قطعی فقط از منبع معتبر می‌آید.
- استقلال برند، tenant و provider؛ نه کپی کد و نه اختلاط داده.
- تجربه فارسی RTL، mobile-first و متناسب با کار هر نقش.

## شاخص‌های موفقیت پایلوت

درک سریع ارزش سازمانی، وضوح موجودی/قیمت Mock، اثبات tenant isolation در تجربه UI، رزرو و تأیید قابل‌ردگیری، و مقایسه قابل‌تصمیم‌گیری هتل.

---

## فایل: BUSINESS_MODEL.md

# Business Model

## بخش‌ها و ارزش

سازمان: سیاست، بودجه، approval و گزارش. کارکنان: تجربه ساده و اعتبار شفاف. آژانس/Provider: توزیع، رزرو و تسویه استاندارد. شریک API/Widget: سفر composable با کنترل مصرف. مسافر B2C: مقایسه و سفر کامل.

## درآمد و کنترل

فروش مستقیم، commission، subscription، setup White Label، transaction fee، API metering، affiliate، managed service، آموزش/پشتیبانی، promotion و افزونه‌ها ثبت‌پذیرند. اعتبار و اقساط صرفاً با مجوز و سیاست قانونی/مالی فعال می‌شوند. تحلیل سازمانی فقط aggregate و مجاز است.

## فرض تجاری پایلوت

ارزش اولیه با دو سازمان فرضی و هتل دستی نشان داده می‌شود؛ هیچ ادعایی درباره نرخ conversion، قرارداد یا درآمد واقعی وجود ندارد.

---

## فایل: BRAND_ARCHITECTURE.md

# Brand Architecture

## سه Concept پیشنهادی

1. **مسیرهای آرام (انتخاب‌شده)**: سرمه‌ای عمیق، فیروزه‌ای دریایی و کهربایی محدود؛ حس جهت‌یابی، اعتماد و کیفیت برای سفر و سازمان. مناسب RTL، داده‌های عملیاتی و White Label.
2. **افق فرهنگی**: زغالی، خاک رس و فیروزه ایرانی؛ گرم‌تر و مناسب روایت مقصد/پادویرا، اما برای داشبورد سازمانی سنگین‌تر است.
3. **تکنولوژی سفر**: آبی کبالت، آسمانی و خاکستری سرد؛ دیجیتال و کارا، اما تمایز فرهنگی و حس premium کمتری دارد.

Concept «مسیرهای آرام» برای Prototype انتخاب شده است: `#08253D`، `#0E7490`، `#F4B942`، سطح روشن `#F7FAFC`. رنگ‌های بنفش و سبز تاژبان در هویت کارن‌سیر به‌کار نرفته‌اند.

## لوگو

لوگوی نهایی نیازمند تأیید مالک پروژه است. تا آن زمان فقط wordmark موقت «کارن‌سیر» و نشان انتزاعی مسیر/افق در UI استفاده می‌شود؛ این یک لوگوی نهایی یا ثبت‌شده نیست.

## تایپوگرافی

پیشنهاد اصلی: Vazirmatn برای متن و عنوان فارسی؛ fallback: Tahoma, Arial. اعداد فارسی/انگلیسی باید با داده واقعی و دسترس‌پذیر نمایش یابند.

## سیاست برندهای هم‌زیست

هر Tenant و White Label tokenهای خودش را دارد. In-house، تاژبان و پادویرا به‌صورت محتوایی/عملیاتی برچسب‌گذاری می‌شوند، نه با جعل یک هویت بصری مشترک.

---

## فایل: ECOSYSTEM_MASTER_SPEC.md

# Ecosystem Master Spec

## مرز برندها

| نام | نقش | مرز |
|---|---|---|
| کارن‌سیر / KarenSeir | هویت و محصول اجرایی این سرور | تجربه و هسته عملیاتی این پروژه |
| In-house | پلتفرم دیجیتال سفر و رفاه | برند/کانال مستقل با قابلیت اتصال آینده |
| تاژبان گشت پارس | اپراتور خدمات گردشگری و رفاه سازمانی | تأمین و عملیات؛ رنگ بنفش/سبز آن به کارن‌سیر منتقل نمی‌شود |
| پادویرا | فرهنگ، هنر، رویداد و صنایع‌دستی | دامنه عرضه فرهنگی و تجربه مقصد |
| 60Online/70Online | فروشگاه مستقل | فقط API/Event آینده؛ بدون کد، DB یا UI مشترک |

## بازارها و درآمد

کانال‌ها: B2G، B2B، B2B2C، B2C، سازمان/کارکنان، آژانس، تأمین‌کننده، API، Widget، White Label و اپ اختصاصی شریک. درآمد: فروش مستقیم، کمیسیون، اشتراک، راه‌اندازی White Label، کارمزد تراکنش، API metered usage، affiliate، managed service، پشتیبانی/آموزش، اعتبار/اقساط قانونی، promotion، تحلیل مجاز و افزونه‌ها.

## دامنه‌های دائمی

حمل‌ونقل (هوا، قطار، اتوبوس، کشتی، ترانسفر، اجاره خودرو، ترکیبی، کارگو آینده)، اقامت (هتل تا بوم‌گردی و channel manager)، تور (داخلی، خارجی، زیارتی، سلامت، علمی، رویدادی، فرهنگی، سازمانی)، خدمات سفر (ویزا، بیمه، CIP، راهنما، itinerary، disruption support)، رفاه/تجربه (رستوران، QR menu، مراسم، ورزش، جاذبه، پادویرا و صنایع‌دستی) و خدمات خودرو (امداد، inspection، شست‌وشو و سفر جاده‌ای).

## اصول اجرایی

Pilot فقط یک برش آزمون‌پذیر از این نقشه است. هر سرویس بیرونی adapter مستقل و fail-closed دارد؛ نام یک Provider به معنی قرارداد یا دسترسی نیست.

---

## فایل: PRODUCT_ECOSYSTEM_AUDIT.md

# KarenSeir Product Ecosystem Audit

## Search UX gate — 2026-08-21

| Capability | Evidence | Gate |
|---|---|---|
| Homepage Search interaction | autocomplete, origin/destination, dates/flexibility, passengers/rooms/cabin and trip type | PASS |
| Structured navigation | recoverable URL parameters → authenticated `/search/results` | PASS |
| Results decision UI | vertical cards, final price, provider, freshness, availability, refundability, filter/sort/edit | PASS |
| Compare and saved search | 2–4 Offer selection dock and persisted tenant-scoped saved query | PASS |
| Operational states | skeleton, zero result recovery, provider error/retry, stale, unauthorized and mobile | PASS |
| Visual evidence | six reviewed screenshots; Chromium full regression `16/16` | PASS |
| Homepage identity | Hero/Header/sections/images/palette/type/spacing retained; no page redesign | PASS |
| Real price hints | intentionally absent until contracted dated-fare Provider data exists | BLOCKED-EXTERNAL |

## Unified Search v2 gate — 2026-08-21

| Capability | Evidence | Gate |
|---|---|---|
| Normalization/entity/autocomplete | Persian/Arabic digits and glyphs, punctuation, safe aliases/IATA, typo ranking, typed payload | PASS |
| Multi-vertical/result contract | 14 verticals on shared Offer source; base/tax/fee/discount/final, source timestamps | PASS |
| Freshness/availability/recheck | LIVE/STALE and CONFIRMED/REQUIRES_RECHECK separate; stale hidden by default; price delta fails closed | PASS |
| Dedup/ranking/comparison | deterministic entity key, multiple provider offers, auditable breakdown/explanation; existing comparison uses Offer IDs | PASS |
| Flexible/filter/nearby/map | flexibility intent and filters/map bounds PASS; real price calendar/map tiles/provider alternatives require external feeds | PARTIAL-EXTERNAL |
| History/saved/budget/NL | tenant/user-scoped recent and saved queries; no alerts sent; deterministic intent only; budget outputs require live inventory | PASS-INTERNAL |
| Aggregation/cache/observability | provider diagnostics, bounded resilience adapter and Search business counters exist | PARTIAL: real multi-provider concurrent P50/P95 and distributed cache-hit evidence require adapters/credentials |
| Security | PostgreSQL 67/67 RLS/FORCE, missing/own/cross tenant, IDOR, price tamper, worker role | PASS |
| Homepage freeze | source diff zero; desktop/mobile Chromium structural screenshots | PASS |

Search completion is `88%`. Missing work is not masked: real provider fan-out, provider-result cache telemetry, price-calendar feed and delivered alerts remain credential/adapter dependent.

Timestamp: 2026-08-20

This audit verifies the current repository at HEAD `2054b84a29a14d18d28786c1220e2c0612496f18`. It does not replace prior security/database evidence.

## Benchmark findings applied without copying UI

- Metasearch patterns: flexible-date intent, transparent provider/source, final-price sorting and explicit freshness.
- Marketplace patterns: destination-led discovery, verified-stay review distinction, amenity/cancellation filters and list/map parity.
- Trip-planning patterns: saved itinerary separated from authoritative inventory; every bookable item re-enters price/availability check.
- Iranian-market requirements: Persian/Arabic character normalization, Jalali/Gregorian boundary clarity, IRR/toman labelling, domestic city/airport/rail recognition and provider-contract constraints.

These are behavior contracts only. KarenSeir keeps its approved Persian RTL/Vazirmatn identity and does not reproduce another product's layout or copy.

## Page and capability inventory

| Area | Verified state | Gap / gate |
|---|---|---|
| Homepage | healthy approved UI; discovery/search presentation partly demo-labelled | unified live ecosystem search results |
| `/hotels` | UI-only legacy prototype and clearly mock-labelled | authenticated Search 2.0 integration, filters/map |
| `/compare` | authenticated real backend plus legacy presentation shell | vertical-specific labels and saved comparison |
| `/assistant` | grounded-context backend exists; UI remains prototype | editable/persisted itinerary and model provider |
| `/trips`, manage booking, timeline | real authenticated API, cancellation/refund/support connected | external notification delivery/provider changes |
| account/payment/invoice | real domain and fail-closed payment adapter | contracted gateway; ZarinPal test credential |
| organization/finance | real RBAC workflows, credit/installment/invoice/reconciliation | target policy/report certification |
| supplier/agency/backoffice/admin | real read/mutation APIs with RBAC | richer analytics; external provider contracts |
| nearby/services | demo-labelled discovery and map fallback | map/places credential and real destination catalog |
| white-label | persistent tenant configuration | DNS verification and target certificate |
| reviews/trust | trust copy only | persisted moderated review domain |
| trip builder/wishlist | domain concepts only | persisted tenant/user-scoped implementation |

## Phase 1 gate

- Repository/status/routes/backend/tests inspected: PASS.
- UI authority preserved: PASS; no visual files changed.
- Security baseline preserved: PASS; no schema or RLS change.
- Mock/provider-dependent areas explicitly identified: PASS.
- Rollback: remove this audit/ADR only; no runtime state changed.

## Phase gates after this increment

| Phase | Gate | Evidence / remaining |
|---|---|---|
| 1 Product audit | PASS | page/domain inventory and explicit authority classification |
| 2 Search Engine 2.0 | PASS (internal contract) | 14 verticals, Persian normalization, autocomplete, filters/map bounds, provider timestamps/TTL, stale fail-closed, recent searches; live inventory remains credential-dependent |
| 3 Discovery | PARTIAL | approved Homepage discovery exists; destination catalog/API and dedicated discovery routes remain internal |
| 4 Trip Assistant | PARTIAL | grounded transactional context PASS; editable persisted itinerary/model integration remains |
| 5 Comparison | PARTIAL | authoritative 2–4 offer comparison PASS for core verticals; vertical-specific awards/schema expansion remains |
| 6 Reviews & Trust | MISSING | persisted verified-review/moderation domain remains |
| 7 Map | PARTIAL | provider interface and fallback exist; real map/list result integration requires internal route work plus external credential |
| 8 Trip Builder | MISSING | persisted trip basket, wishlist/share/collaboration remain |
| 9 Operations/Timeline | PASS | tenant-aware immutable events, deep links, source distinction and notification outbox |
| 10 Organizational Travel | PASS | credit/policy/approval/installment/invoice/reporting and white label |
| 11 ZarinPal test | BLOCKED | generic payment safety foundation exists; ZarinPal-specific certified transport and sandbox merchant credential absent; no fake callback success |
| 12 Checkout | PARTIAL | traveller/price-check/payment/invoice/confirmation domains exist; cohesive dedicated checkout UI remains |
| 13 Supplier/Agency | PASS | inventory/price/status/commission/settlement operations with RBAC/audit |
| 14 Mobile/RTL | PARTIAL | frozen Homepage Desktop/Mobile gate PASS; full calendar/map/date/number visual matrix remains |
| 15 Performance/SEO | PARTIAL | metadata/build/image framework exists; canonical/sitemap/structured destination data and CWV evidence remain |
| 16 Security/Financial | PASS | prior real PostgreSQL 56/56 RLS plus current IDOR/payment/idempotency/RBAC regression |

Passed phases: 6/16. The expanded ecosystem scope is estimated at 76%; the prior 97% remains the completion figure for the narrower production-hardening scope and is not reused to conceal new product gaps.

## Increment checkpoint — 2026-08-20T09:34:20Z

| Current phase | Gate | Evidence / remaining |
|---|---|---|
| 7 Trip Basket + Wishlist | BLOCKED | domain/API/UI/idempotency/audit/cross-tenant API PASS؛ PostgreSQL migration 11 direct RLS gate blocked by absent runtime |
| 8 Verified Reviews | BLOCKED | server-derived verified flag، strict anti-forgery، moderation، supplier response separation و tenant tests PASS؛ direct PostgreSQL RLS gate remains |
| 9 Destination Catalog | PASS | hierarchy/persistence/service counts و routeهای مستقل list/detail؛ Homepage unchanged |
| 10 Editable Trip Assistant | PASS (internal) | persisted create/resume/add/remove/reorder/replace/budget/save/duplicate؛ bookable data references authoritative Offer و otherwise needs-live state |
| 11 Comparison Completion | PASS | 2–4 offers، vertical fields، deterministic awards، audit event و tenant isolation |
| 12 Map/List | PASS (credential-independent) | independent route، list/selection/coordinates/bounds contract؛ map transport explicitly blocked by credential |
| 13 Unified Checkout | PARTIAL | existing traveller/price/availability/payment/invoice/confirmation domains remain separate؛ resumable cohesive UI pending |
| 14 ZarinPal TEST | BLOCKED | merchant credential absent؛ dedicated adapter/request/verify remains internal work and no fake success exists |
| 15 SEO/CWV/RTL | PARTIAL | destination metadata/build PASS؛ canonical/sitemap/structured data/CWV and full viewport/date matrix pending |
| 16 Final Security | BLOCKED | API negative regression PASS؛ migration 11 direct PostgreSQL RLS and full security matrix pending |

Current honest completion: `84%`; passed phases: `10/16`. Homepage visual regression remains zero.
# Search UX correction — 2026-08-21

The prior backend completion is no longer used as a proxy for user-visible completion. Browser QA now proves the Search Box and dedicated results route are interactive. Real SavedTrip mutations, selected-Offer comparison and price/availability recheck replace the previous UI-only links/buttons. Nine reviewed screenshots cover default Search, both autocompletes, date and passenger pickers, Desktop results, filters, comparison and Mobile results. Ecosystem completion is now assessed at `94%`; production remains NO-GO for external dependencies.
## Travel Commerce gate — 2026-08-21

- Vacation Rental: **PASS internal** — dedicated property/unit/reservation domain، date overlap guard، tenant ownership، UI routes و Checkout handoff. Seasonal date-level pricing، host onboarding UI و full cancellation settlement هنوز refinement داخلی‌اند.
- Tour: **PASS internal booking** — tour/departure inventory، room pricing، capacity lock، search/list/detail، booking hold و Checkout handoff. Payment sandbox و voucher issuance نیازمند credential/Provider fulfillment واقعی‌اند و success ادعا نشده است.
- Cruise: **PASS foundation / BLOCKED live** — sailing/cabin-ready catalog contract و honest unavailable UX؛ live inventory/booking وابسته به Provider قراردادی است.
- Visa: **PASS case foundation** — source-timestamped product، applicant/documents، human review separation و timeline. Embassy/VAC submission و decision external-authority blockers هستند.
- Benchmark logic used: date/guest eligibility and blocked calendars (Airbnb)، disclosed tour departure/services/visa state (Iranian public tour patterns)، sailing/cabin/fee separation (Royal Caribbean/NCL)، and document/biometric/human authority workflow (France-Visas/German Consular Portal/Canada). No visual design was copied.
- Homepage identity remains frozen; all new presentation lives on dedicated routes.
# Closure audit update — 2026-08-21

- Search UX is now visibly differentiated and browser-usable: eight verticals, context-aware labels, responsive tab layout and evidence captures. Homepage identity regression remains zero.
- Tour/Visa integration is no longer UI-only: Visa Application may reference a tenant-owned Tour Reservation and emits a linked timeline event; foreign ownership is rejected.
- PostgreSQL-specific Head 15 RLS evidence remains BLOCKED_EXTERNAL_ENVIRONMENT, while SQLite migration drift/rollback evidence is PASS.

---

## فایل: PILOT_SCOPE.md

# Pilot Scope

## In scope

OTP Mock، دو Tenant فرضی مستقل (سازمان «بانک آفتاب» و «صنایع فراز»)، Platform/BackOffice، مدیر سازمان، کارمند، policy/credit Mock، هتل با inventory دستی، search/detail، درخواست رزرو، approval، payment Mock fail-closed، ledger/audit نمایشی، comparison هتل، دستیار سفر UI، White Label یک سازمان، صفحه اصلی و dashboard حرفه‌ای.

## Out of scope

backend واقعی، PostgreSQL/RLS، provider credential، نرخ/ظرفیت زنده، payment/OTP حقیقی، settlement واقعی، صدور، AI production، اپ موبایل native، انتقال داده یا کد 60Online/70Online، و فعال‌سازی contract برندهای دیگر.

هتل/آژانس/provider tenant آزمایشی نیستند؛ فقط supplier domain محسوب می‌شوند. Tenant isolation صرفاً با دو سازمان فرضی آزمون UX می‌شود.

---

## فایل: UX_STRATEGY.md

# UX Strategy

مسیرهای کلیدی پایلوت: (۱) کارمند هتل را جست‌وجو، مقایسه و درخواست می‌کند، (۲) مدیر سازمان approval و مصرف اعتبار را می‌بیند، (۳) اپراتور Integration را بدون ادعای اتصال واقعی بررسی می‌کند.

## اصول

- RTL واقعی، سلسله‌مراتب آرام، فضای سفید و خوانایی بالا.
- کارت برای کشف؛ جدول برای عملیات؛ drawer/sheet برای اقدام موبایل.
- Badgeهای قیمت، کیفیت و policy فقط با source و rule قابل‌نمایش‌اند.
- وضعیت‌های pending، unavailable و mock با متن روشن؛ نه با رنگ تنها.
- دستیار پیشنهاد می‌دهد ولی قیمت/موجودی را نمی‌سازد و مسیر منبع را نشان می‌دهد.

## دسترس‌پذیری

کنتراست AA، focus قابل‌مشاهده، هدف لمسی حداقل 44px، label صریح، semantic HTML و احترام به reduced motion لازم است.

---

## فایل: INFORMATION_ARCHITECTURE.md

# Information Architecture

## سطوح تجربه

- **مسافر/کارمند:** خانه، جست‌وجو، نتایج، مقایسه، دستیار، سفرها، اعتبار، درخواست‌ها، پشتیبانی.
- **سازمان:** overview، کارکنان/خانواده، سیاست، اعتبار و بودجه، approval، گزارش، محتوا و White Label.
- **BackOffice:** عملیات رزرو، Provider/Integration، catalog، settlement، support، tenant، audit و observability.
- **Provider/Partner:** inventory، رزروهای دریافتی، تسویه، API keys، webhooks و quality.

## الگوی ناوبری

موبایل: اقدام اصلی پایین صفحه و ناوبری کوتاه؛ دسکتاپ: sidebar وظیفه‌محور. فیلتر، compare tray و وضعیت Mock همیشه آشکار هستند. هر نقش فقط ابزارهای موردنیاز کارش را می‌بیند.

## نقشه دامنه مقیاس‌پذیر

Homepage فقط درگاه «جست‌وجو → کشف → مقایسه → تصمیم → تجربه» است. عمق محصول در Landing Pageهای دامنه‌ای قرار می‌گیرد و Header فقط ورودی‌های پرتکرار را نشان می‌دهد.

- **سفر:** پرواز، هتل و اقامت، قطار، تور، بوم‌گردی، اجاره خودرو، ترانسفر و خدمات پیش از سفر.
- **مقصد و تجربه:** مقصدها، رستوران و کافه، تفریح و ورزش، رویداد، راهنمای محلی و خدمات مقصد.
- **فروشگاه سفر:** صنایع‌دستی، سوغات، محصولات فرهنگی و ملزومات مرتبط با سفر؛ مستقل از هر Marketplace دیگر.
- **هوشمند:** دستیار سفر، برنامه سفر و موتور مقایسه چندگزینه‌ای با توضیح‌پذیری و کنترل کاربر.
- **سازمانی:** سفر سازمانی، رفاه کارکنان، اعتبار و گردش تأیید، وایت‌لیبل tenant-aware.
- **حساب من:** سفرهای من، رزروها، مدارک، مقایسه‌های ذخیره‌شده، اعتبار/کیف پول، اعلان و پشتیبانی.
- **تأمین‌کننده و عملیات:** موجودی، قیمت، رزرو، تسویه، کیفیت و audit؛ جدا از تجربه مصرف‌کننده و با مجوز نقش.

## مدل سفر کاربر

نیاز → کشف → درک → مقایسه → تصمیم → خرید/رزرو → آماده‌سازی → تجربه → پشتیبانی → یادآوری رضایت‌محور → بهبود. موتور جست‌وجو ورودی اصلی این چرخه است؛ قیمت، موجودی، policy، اعتبار و ledger همواره در backend authoritative باقی می‌مانند.

## ناوبری تدریجی

- Header عمومی: مقصدها، سفرهای منتخب، همراه هوشمند و سازمانی.
- جست‌وجوی سرویس‌محور: هشت ورودی سفر بدون نمایش هم‌زمان همه فیلدها.
- نوار خدمات نزدیک Footer: ورودی‌های کم‌تکرار مانند تجربه محلی، صنایع‌دستی و خدمات پیش از سفر.
- پنل‌های نقش‌محور: امکانات حساب، سازمان و تأمین‌کننده فقط پس از ورود و احراز مجوز نمایش داده می‌شوند.

## لایه سفر پس از رزرو

- `/booking/confirmation`: تأیید Mock، دسترسی به واچر و انتخاب آگاهانه برای ورود به سفر.
- `/trips`: فهرست contextهای سفر کاربر.
- `/trips/[id]`: timeline قبل، حین و بعد سفر؛ deep linkهای `?stage=before|during|after`.
- `/nearby?trip=[id]`: همراه محلی با context مقصد/اقامت و تفکیک شریک، اعتبارپذیر و مکان عمومی.
- `/services?destination=shiraz`: خدمات actionable قبل و حین سفر، جدا از Destination discovery.
- `/manage-booking/[bookingId]`: policy preview، تغییر/کنسلی/استرداد، escalation و tracking درخواست.

در موبایل اولویت دسترسی به‌ترتیب سفر، واچر، اطراف من، پشتیبانی و دستیار است. Notificationها تنها با context سفر و deep link مفید نمایش داده می‌شوند.

## خدمات یکپارچه و after-sales

Homepage یک Services Hub فشرده میان Search و مقصدها دارد؛ صفحه `/services` عمق گروه‌های قبل سفر، جابه‌جایی، اقامت، غذا، تجربه و تجارت مرتبط با سفر را فراهم می‌کند. مقصدها همچنان discovery هستند و service cardها CTA عملیاتی دارند.

رزرو و واچر به `Manage Booking` متصل‌اند. policy زمان خرید، policy جاری، quote، request، refund transaction و support escalation شناسه مستقل دارند و به Booking/Trip متصل می‌شوند؛ frontend authority مالی یا حقوقی نیست.

---

## فایل: DESIGN_SYSTEM.md

# Design System

## Tokens

`ink #08253D`، `ocean #0E7490`، `sun #F4B942`، `mist #F7FAFC`، `surface #FFFFFF`، `muted #617184`، `danger #B42318`. spacing: 4/8/12/16/24/32/48. radius: 12/20/28. shadow: نرم و کم‌کنتراست.

## Components

Button، Input، Search field، Select/filter chip، Card، Data table، Badge، Metric، Progress، Alert، Drawer، Bottom navigation، Empty state، Skeleton و Comparison row باید API مستقل، حالت disabled/loading/error و RTL داشته باشند.

## Themeability

tokenهای semantic با CSS variables تعریف می‌شوند؛ White Label فقط token، asset، content و feature flag را تغییر می‌دهد، نه کد fork شده. Componentهای مالی باید منشأ داده و وضعیت policy را نمایش دهند.
# افزوده فاز Homepage

- رنگ اصلی: سرمه‌ای `#071f35`؛ رنگ کنش و تأکید: فیروزه‌ای `#0b8f8b`؛ سطح گرم: `#f7f5f0`؛ accent محدود: `#f3a446`.
- تایپوگرافی فارسی بر پایه fallbackهای محلی امن (Vazirmatn/Tahoma) و سلسله‌مراتب fluid با `clamp` است.
- شعاع کارت‌های اصلی ۲۰ تا ۲۸ پیکسل، خطوط کم‌رنگ و سایه‌های کنترل‌شده است.
- وضعیت focus با outline فیروزه‌ای، motion با احترام به `prefers-reduced-motion` و RTL به‌صورت document-level اعمال می‌شود.

## بازطراحی مرجع تصویری — فاز Plum / Coral

- Homepage از سایر صفحات مستقل است و از زمینه کرم `#f5eee4`، بنفش بسیار تیره `#2a1530` و کورال `#ef5b3d` استفاده می‌کند. بخش AI Homepage نیز فقط از همین خانواده رنگ استفاده می‌کند و آبی/سرمه‌ای/فیروزه‌ای ندارد.
- ترتیب صفحه بدون جابه‌جایی بخش‌های موجود، دستیار AI را بلافاصله پس از سفرهای منتخب و پیش از مقایسه نگه می‌دارد.
- تراکم عمودی صفحه کنترل‌شده و فاصله‌های بخش‌ها ۶۴ تا ۸۸ پیکسل در Desktop و ۴۸ تا ۶۴ پیکسل در Mobile است.
- صفحات عملیاتی موجود می‌توانند tokenهای قبلی را حفظ کنند؛ ممنوعیت پالت سرمه‌ای/فیروزه‌ای فقط برای Homepage اعمال می‌شود.
