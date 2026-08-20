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
