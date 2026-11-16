# ADR-022 — بازطراحی صفحات داخلی با design system صفحه اول (Stitch، آبان ۱۴۰۵)

- وضعیت: پذیرفته‌شده (درخواست صریح مالک ۱۴۰۵/۰۸/۲۴ و ۱۴۰۵/۰۸/۲۵)
- شاخه: `design/stitch-redesign-2026-11`

## زمینه

صفحه اول (Protected) با پالت Plum/Coral/Cream بازطراحی شده بود ولی صفحات داخلی‌ای که از `Shell` استفاده می‌کنند (`/hotels`، `/compare`، `/assistant`، `/organization`، `/employee`، `/white-label`، `/integrations`) و صفحه مستقل `/search/results` هنوز توکن‌های قدیمی سرمه‌ای/فیروزه‌ای داشتند. مالک بازطراحی همه بخش‌ها جز صفحه اول را در Google Stitch تأیید و پیاده‌سازی و deploy آن را درخواست کرد.

## تصمیم

1. لایه CSS جدید `app/redesign-2026-11.css` که فقط زیر `.ks-inner` (Wrapper جدید `Shell`) و `.search-results-page:not(.embedded)` اعمال می‌شود؛ متغیرهای `--ink/--ocean/--sun/--mist/--muted/--line` در همین scope به پالت برند بازنویسی می‌شوند.
2. `Shell` در `app/page.tsx`: هدر با تلفن پشتیبانی و دکمه ورود، فوتر بنفش با گوشه گرد، و ناوبری پایین موبایل (خانه، جست‌وجو، سفرهای من، دستیار، حساب).
3. هیچ تغییری در Homepage، جست‌وجوی جاسازی‌شده در Homepage، JourneyShell (که از قبل پالت Plum دارد)، داده، API، قیمت یا provider انجام نشده است.

## پیامدها

- کنتراست: رنگ متن تأکیدی `#C93F24` (کورال تیره‌تر) برای خوانایی روی کرم؛ دکمه‌ها `#EF5B3D`.
- Rollback: حذف `import './redesign-2026-11.css'` از `app/layout.tsx` و بازگرداندن تابع‌های `Header/Footer/MobileNav/Shell` از commit قبلی.
- Acceptance: `tsc --noEmit` تمیز، eslint تمیز روی فایل‌های تغییرکرده، `next build --webpack` موفق؛ اسکرین‌شات دسکتاپ و موبایل در `docs/design/stitch-redesign-2026-11/qa/impl/`.
