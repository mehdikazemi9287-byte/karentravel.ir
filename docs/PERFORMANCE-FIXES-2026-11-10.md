# اصلاح عملکرد (PR #75) — انتقال به main، ۲۰۲۶-۱۱-۲۳

PR #75 روی main قدیمی (`ac379c1`) ساخته شده بود. پس از یکی‌شدن شاخه‌ها (۲۰۲۶-۱۱-۱۹) هر مورد جداگانه روی `origin/main` (`62db0d3`) دوباره بررسی شد. محیط: فقط Source؛ migration ندارد؛ بازگشت = revert همین commit.

## منتقل‌شده
- **پشتیبانی (`GET /support/cases`)**: پیام‌های همهٔ پرونده‌ها با یک کوئری، با همان شرط مجوز پرونده‌ها (tenant و مشتری)؛ به‌جای یک کوئری برای هر پرونده.
- **مقصدها (`GET /destinations` و `/public/tenants/{slug}/destinations`)**: شمارش پیشنهادهای فعال با یک خواندن دوستونی در دسته‌های ۵۰۰تایی، به‌جای بارگذاری همهٔ Offerها برای هر مقصد.
- **autocomplete**: `cache_policy` پاسخ tenant-دار از `private_tenant_30s` به `private_no_store`؛ مسیر عمومی قدیمی طول `q` را ۲ تا ۲۰۰ نویسه محدود می‌کند.
- **صفحهٔ اصلی**: نمای نتایج جست‌وجو با `next/dynamic` جدا بارگذاری می‌شود (همان markup اسکلت خود نما)؛ بدون تغییر ظاهر.
- **تصاویر**: `images.formats` = AVIF/WebP برای تصاویر `next/image`.
- آزمون‌ها: `backend/tests/test_performance_fixes.py` (بودجهٔ تعداد SELECT برای ۱ و ۲۵ مقصد/پرونده، جداسازی tenant و مشتری، محدودیت طول).

## کنار گذاشته‌شده
- **تمدید نشست single-flight**: main خودش دارد (`refreshPending` در `lib/api/karenseir-client.ts`).
- **رد پاسخ کهنهٔ جست‌وجو**: main با `searchGeneration` در `UnifiedSearchView` دارد.
- **لغو و رد پاسخ کهنهٔ پیشنهادها**: main با مسیر تازهٔ `/search/autocomplete/v3/public` و پرچم `cancelled` دارد.
- **کش پیشنهاد جغرافیایی (`public_autocomplete_cache.py`)**: فقط روی مسیر قدیمی `/search/autocomplete/public` بود که دیگر frontend از آن استفاده نمی‌کند؛ hash کل کاتالوگ در هر درخواست هم از خود محاسبه گران‌تر بود.
- **جداسازی DB آزمون outbox**: main مشکل را با پاک‌کردن جدول‌ها در fixture حل کرده است.
- لاگ‌های QA قدیمی (`docs/qa/performance-fixes-20261110/`) که مربوط به مبنای قدیمی بودند.

## مانده (کار جدا برای frontend)
- مهلت زمانی درخواست (شامل خواندن بدنه)، اشتراک GETهای هم‌زمان و لغو با `AbortSignal` در `karenseir-client.ts` هنوز در main نیست. client در main بسیار تغییر کرده است (حالت cookie، CSRF، logout با keepalive، آپلود صوت)؛ انتقال مکانیکی امن نبود و مهلت ۳۰ ثانیه برای آپلود صوت و دستیار باید جداگانه تعیین شود.
- debounce ۳۰۰ میلی‌ثانیه برای جست‌وجوی نتایج (main فعلاً بلافاصله اجرا می‌کند و پاسخ کهنه را رد می‌کند).
- صفحه‌بندی SQL جست‌وجوی تجمیعی، Redis عملیاتی، CDN و اندازه‌گیری واقعی سرعت.

## QA
- کل backend (SQLite): 879 passed، 7 skipped.
- `npx tsc --noEmit`: بدون خطا؛ eslint روی `app/page.tsx` و `next.config.mjs`: بدون خطا؛ `npm run build`: موفق.
- آزمون مرورگر و PostgreSQL برای این تغییر اجرا نشد.
