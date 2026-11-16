# ADR-023 — بازطراحی صفحات داخلی روی پایه `production` (جایگزین بخش کد ADR-022)

- تاریخ: ۱۴۰۵/۰۸/۲۶ (2026-11-16) · وضعیت: پذیرفته‌شده (تأیید مالک: «بله انجام بده»)
- زمینه: patch ADR-022 روی `main` قدیمی ساخته شده بود؛ سایت زنده روی `production` است که صفحات داخلی را با `ApprovedShell` (هدر/فوتر مصوب Figma، پالت plum/coral/cream) نمایش می‌دهد. اعمال ADR-022 هدر/فوتر مصوب و شماره پشتیبانی واقعی (`lib/site-contact.ts`) را بازنویسی می‌کرد.

## تصمیم
- هدر، فوتر، صفحه اول و صفحات JourneyShell **دست‌نخورده** می‌مانند (Protected).
- فقط محتوای صفحاتی که با `Shell` → `ApprovedShell` رندر می‌شوند (۱۷ صفحه، مثل /services، /contact، /terms، /register، /booking/confirmation) طبق طراحی Stitch اصلاح می‌شود: دکمه‌های pill و کورال، کارت‌های کرم با گوشه ۲۴px، برچسب‌های Mock طلایی، چت دستیار، جدول مقایسه، focus ring در دسترس.
- پیاده‌سازی: `components/marketplace/approved-inner-2026-11.css` با scope `.approved-site.ks-inner>main` و افزودن کلاس `ks-inner` به `ApprovedShell`.
- نوار ناوبری پایین موبایل اضافه **نشد**: ۴۷ صفحه JourneyShell آن را نداشتند و SupportDock دارند؛ افزودن فقط به ۱۷ صفحه ناوبری را ناهمگون می‌کرد.

## شواهد
- `tsc --noEmit` پاک، `next build --webpack` موفق.
- مقایسه پیکسلی صفحه اول قبل/بعد: بدون تفاوت (`getbbox()==None`).
- `/services` قبل/بعد: `docs/design/stitch-redesign-2026-11/qa/impl/services-before-after.png`.

## Rollback
- `git revert` این commit یا بازگرداندن image پشتیبان `karenseir-web:pre-redesign-*` روی سرور (`deploy/redesign-2026-11-rollback.sh`).
