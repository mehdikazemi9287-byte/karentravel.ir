# KarenSeir / کارن‌سیر

نسخه محلی قابل اجرای اکوسیستم سفر، رفاه سازمانی و تجربه‌های مقصد کارن‌سیر.

## وضعیت فعلی

این مخزن شامل رابط RTL و responsive، Homepage یکپارچه و backend عملیاتی FastAPI برای identity، booking orchestration، payment/refund، approval، Trip Events، notification، White Label، comparison و grounded context است. صفحه‌های نمایشی قدیمی همچنان صریحاً **Mock** هستند؛ providerهای خارجی بدون credential قراردادی fail-closed می‌مانند و هیچ پرداخت یا اتصال خارجی Production فعال نیست.

## اجرا

```bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use --lts
npm ci
npm run dev -- --port 3001
```

سپس `http://localhost:3001` را باز کنید. برای بررسی نهایی از `npm run lint`، `npx tsc --noEmit` و `npm run build` استفاده کنید. build پروژه عمداً از Webpack رسمی Next.js استفاده می‌کند؛ Turbopack در محیط‌های محدود هنگام اجرای PostCSS ممکن است برای bind داخلی panic کند.

حداقل نسخه Node برای Next.js 16، نسخه `20.9.0` است. در محیط‌هایی که SWC native قابل بارگذاری نیست، توسعه را با `npm run dev -- --webpack` اجرا کنید.

برای پایلوت API، dependencyها را فقط در virtualenv پروژه نصب کنید:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/uvicorn app.main:app --reload
```

صفحه `/pilot` از `NEXT_PUBLIC_API_URL` (پیش‌فرض `http://localhost:8000`) استفاده می‌کند.

## نقطه توقف

Provider، پرداخت، OTP و سرویس‌های بیرونی تا زمان وجود credential معتبر و آزمون fail-closed غیرفعال می‌مانند. به هیچ وجه 60Online/70Online در این پروژه ادغام نمی‌شود.

## زیرساخت عملیاتی افزایشی

Backend اکنون علاوه بر پایلوت قبلی، مدل‌های tenant-aware رزرو مستقل از Provider، آیتم رزرو، مسافر، بلیت/واچر، درخواست تغییر/کنسلی/استرداد، کیف پول و اعتبار سازمانی، ledger تغییرناپذیر، approval، Trip، TripEvent، notification delivery، پشتیبانی انسانی، ارجاع گفت‌وگوی AI، refresh session، role permission، idempotency و outbox را دارد. schema پایه در `20260817_01` و افزونه امنیت/مالی/اعلان در `20260818_02` به‌صورت non-destructive ثبت شده‌اند.

Adapterهای `flight`، `hotel`، `tour_hotel`، `train`، payment، OTP، SMS، Push، Email، inventory و issuance فقط mock/fail-closed هستند و موفقیت خارجی جعل نمی‌کنند.

هسته backend اکنون OTP challenge یک‌بارمصرف و tenant-aware، session family/rotation/logout، Payment Intent، callback امضاشده و refund idempotent دارد. تا نصب credential و transport مجاز، OTP و Payment همچنان fail-closed می‌مانند و dev-login در Production مخفی است.

Orchestration افزوده‌شده Offer/Price Check/Booking/Voucher چهار نوع سرویس، Manage Booking policy-safe، approval چندمرحله‌ای، White Label persistence، comparison explainable، AI grounded context، notification receipts و panel APIهای عملیاتی را پوشش می‌دهد. داده‌های Mock قدیمی frontend همچنان صریحاً Mock هستند و به Production واقعی تبدیل نشده‌اند.

اجرای API و worker در توسعه:

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload
python -m app.outbox_worker
```

## اسناد

تمام دامنه اکوسیستم، مرز پایلوت و تصمیم‌های اصلی در فایل‌های ریشه و `docs/adr` ثبت شده‌اند.

## وضعیت QA صفحه اصلی

- Next.js و eslint-config به `16.3.1` و PostCSS به `8.5.23` ارتقا یافته‌اند؛ `npm audit --omit=dev` برای dependencyهای Production صفر آسیب‌پذیری گزارش می‌کند.
- فونت رسمی Vazirmatn به‌صورت dependency محلی بارگذاری می‌شود.
- مسیرهای `/`، `/hotels`، `/compare`، `/assistant`، `/organization`، `/employee`، `/white-label`، `/integrations` و `/pilot` روی dev server پاسخ `200` داده‌اند.
- lint، TypeScript strict و تست‌های API موفق‌اند. Build باید با Node استاندارد سیستم اجرا شود؛ runtime داخلی ChatGPT به‌دلیل code-signing باینری SWC معیار معتبر Build نیست.

Homepage فعلی بر اساس جهت طراحی کرم، بنفش تیره و کورال بازطراحی شده است. تصویر Hero یزد، مقصدهای نامتقارن، سفرهای منتخب، همراه هوشمند، نوار مقایسه، خدمات سازمانی و Footer منحنی در مسیر `/` قرار دارند. تصاویر اجرایی صفحه محلی‌اند و به Unsplash یا لینک موقت Figma وابسته نیستند.

موتور جست‌وجوی Homepage اکنون ورودی اصلی محصول است و چهار ماژول مصوب «پرواز»، «هتل»، «تور + هتل» و «تشریفات فرودگاه» را نمایش می‌دهد؛ توسعه برای قطار/اتوبوس/خودرو در domain adapter باقی مانده و UI فعلی را شلوغ نمی‌کند. رابط جست‌وجوی زبان طبیعی فقط آمادگی معماری را نشان می‌دهد و تا زمان اتصال معتبر، صریحاً Mock و fail-closed است.

معماری اطلاعات آینده در `INFORMATION_ARCHITECTURE.md` ثبت شده است؛ Homepage درگاه اکوسیستم می‌ماند و مقصد/تجربه، فروشگاه سفر، حساب، سازمان و تأمین‌کننده در دامنه‌های مستقل توسعه می‌یابند. لایه تجارت سفر کارن‌سیر مستقل است و با 60Online/70Online ادغام نمی‌شود.

## چرخه سفر پس از رزرو

Prototype اکنون مسیر `SEARCH → BOOKING → CONFIRMATION/VOUCHER → MY TRIP → BEFORE/DURING/AFTER → NEARBY → SERVICES → SUPPORT` را نمایش می‌دهد:

- `/booking/confirmation`: تأیید صریح Mock و انتخاب مشاهده واچر یا ورود به سفر؛
- `/trips`: مرکز سفرهای کاربر و اعلان‌های context-aware؛
- `/trips/mock-shiraz-1405`: سفر نمونه تهران–شیراز با timeline، واچر، رزروها، مسافران و اقدامات باقی‌مانده؛
- `/nearby?trip=mock-shiraz-1405`: همراه محلی مبتنی بر MockPlaceProvider؛
- `/services?destination=shiraz`: خدمات actionable و مستقل از Destination discovery.
- `/manage-booking/book1`: مدیریت Mock تغییر، کنسلی و استرداد با policy preview و escalation.

مدل‌های دامنه در `lib/domain` و portهای Provider در `lib/providers` قرار دارند. همه داده‌ها، نام شرکا، واچر، مزیت، فاصله، اعلان و وضعیت تجاری نمونه‌اند. `PlaceProvider`، `MapProvider`، `BookingProvider`، `NotificationProvider` و `PaymentProvider` تا زمان credential/contract معتبر fail-closed باقی می‌مانند.

مدیریت رزرو از سفر من، کارت رزرو، واچر، تأیید رزرو، دستیار و پشتیبانی قابل دسترسی است. قواعد زمان خرید جدا از قواعد جاری نگه داشته می‌شوند و در نبود اطلاعات معتبر، جریمه و مبلغ قابل بازگشت حدس زده نمی‌شود. کلیک اولیه هیچ تغییر واقعی در رزرو ایجاد نمی‌کند.

مسیر `/support` ورودی مستقل کمک انسانی است. SupportDock سراسری پنج اقدام «دستیار هوشمند»، «صحبت با کارشناس»، «پیگیری رزرو»، «تغییر و استرداد» و «مشکل در سفر» دارد و متناسب با سفر شیراز نمایش داده می‌شود. در موبایل Dock به محرک جمع‌شونده تبدیل می‌شود و هیچ زمان پاسخ یا دسترسی تأییدنشده‌ای ادعا نمی‌شود.

Services Hub Homepage فقط میان Search و مقصدها اضافه شده و Destination Bento، سفرهای منتخب، Hero و Search جابه‌جا یا بازطراحی نشده‌اند. صفحه کامل `/services` گروه‌بندی، زبان اقدام و فیلتر «اعتبارپذیر نمونه» دارد؛ تجارت سفر کارن‌سیر مستقل از 60Online/70Online است.

## زیرساخت رویداد سفر

`TripEvent` پایهٔ کوچک «مرکز زنده سفر» است. رویدادهای نمونه در `/trips/mock-shiraz-1405` نمایش داده می‌شوند و deep linkهایی مانند `/trips/mock-shiraz-1405?event=event-flight-time` مستقیماً رویداد را هدف می‌گیرند. `NotificationProvider` کانال‌های درون‌برنامه، Push و SMS را مدل می‌کند، اما provider نمونه همیشه `not-sent` است؛ اتصال realtime، ارسال، رسید تحویل و تنظیمات کامل اعلان پیاده‌سازی نشده‌اند.
