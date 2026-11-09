# گزارش پیشرفت کارن تراول — ۱۸ آبان ۱۴۰۵ (۹ نوامبر ۲۰۲۶)

ادامه‌ی گزارش `1405-08-17-progress-report.md`. هدف: هر کسی با این فایل و مخزن بتواند کار را ادامه دهد.

## ۱. خلاصه

| موضوع | وضعیت |
|---|---|
| سایت زنده `http://karentravel.ir` | ✅ سالم (بررسی هر ۳۰ دقیقه؛ همه‌ی صفحه‌ها 200، زیر ۱۳۰ms) |
| کد روی سرور | production `25d43ea` (۱۷ آبان). اصلاحات امروز merge شده ولی **هنوز deploy نشده** |
| شاخه‌ی production | `4324f84` به بعد — تست: ۶۳۰ موفق، ۲ ناموفق قدیمی؛ build موفق |
| HTTPS | ⏳ اسکریپت مخصوص nginx کانتینری آماده (PR #49)؛ منتظر اجرای `--check` |
| پنل‌ها | ✅ بررسی، تحقیق، طرح کامل، فیگمای فاز ۱ (۳۴ frame)؛ ⏳ منتظر تأیید مالک |
| مالیات و B2B | ✅ تحقیق؛ ⏳ پرسش‌های حسابدار و وکیل |

## ۲. PRهای merge شده

| PR | موضوع |
|---|---|
| #46 | گزارش پیشرفت ۱۷ آبان |
| #47 | بررسی پنل‌های موجود + تحقیق رقبا |
| #48 | تحقیق مالیات (ارزش افزوده روی کارمزد، مودیان) و B2B/چارتر |
| #49 | اسکریپت HTTPS برای nginx کانتینری (`deploy/karenseir-https-container.sh`) |
| #50 | منوی نقش‌محور، صفحه‌ی «دسترسی ندارید»، تورهای آژانس در پنل آژانس، `/search` |
| #51 | طرح کامل پنل‌ها (`docs/product/panels/04-panel-spec.md`) |
| #52 | اصلاحات امنیتی C-1، H-1، H-2، M-1، M-2، M-4، M-6؛ پنهان کردن `/pilot` |
| #53 | گزارش QA سفر مشتری از نگاه ۹ نقش (۱۶۶ گام، ۲۱ نقص) |
| #54 | D1: صدور رزرو با اعتبار سازمانی و آزادسازی اعتبار رهاشده؛ D6: درگاه آزمایشی فقط در dev/staging |
| #55 | D2–D4، D7–D10، D12، D20، D21: کد ملی/گذرنامه، رزرو برای همکار، پیام کمبود اعتبار، وضعیت‌های فارسی، ساعت تهران، دسترس‌پذیری (migration `20261109_70`) |
| #56 | اسکریپت deploy: توقف و برگشت خودکار در شکست migration |
| #57 | نقشه و پیش‌نمایش فیگمای پنل‌ها |
| #58 | صفحه‌ی اصلی (تأیید مالک): تلفن پشتیبانی در header، یک‌طرفه بیرون از تقویم |
| #59 | بدون تغییر (نام شاخه با گزارش قبلی تکراری بود؛ commit خالی) |

## ۳. شواهد QA
- سفر مشتری: `docs/reports/qa-journeys-1405-08-18/REPORT.md` (+ `matrix.md`، `axe.json`، هارنس، اجرای دوباره در `rerun-d1-d6/`).
- امنیت: `docs/reports/1405-08-17-security-review.md` و `docs/reports/evidence/1405-08-18-security-fix/`.
- فیگما: `docs/product/panels/FIGMA_MAP.md` و `figma-previews/`.
- تأیید تغییر صفحه‌ی اصلی: `docs/product/approvals.md`.

## ۴. باقی‌مانده

### منتظر مالک
1. اجرای deploy (دستور در بخش ۶).
2. اجرای `--check` اسکریپت HTTPS و ارسال خروجی؛ باز بودن TCP 443 در گروه امنیتی ابرک.
3. تأیید طرح‌های فیگمای پنل‌ها و رنگ دکمه‌ی اصلی (`#c9462a` به‌جای مرجانی برای کنتراست AA).
4. خروجی دستور بررسی سرور: کاربر دیتابیس (H-4)، `ENVIRONMENT`، فایروال.
5. پاسخ پرسش‌های حسابدار (۱۳) و وکیل (۱۰) در `04-panel-spec.md` §۷.

### کار فنی
- امنیت: H-3 (HTTPS)، H-4 (نقش دیتابیس بدون superuser)، تأیید دونفره برای شارژ، توکن در sessionStorage/CSP nonce، کلیدهای جدا، محدود کردن `/fulfill` به آژانس.
- QA: OTP، شارژ کیف پول مشتری، اقساط (BLOCKED)؛ کنتراست `/login` و `/contact`؛ D15–D19.
- پنل‌ها: پیاده‌سازی فاز ۱ بعد از تأیید فیگما (چرخه‌ی کنسلی/استرداد، صف استرداد مالی، تطبیق حساب، تأیید دونفره)، سپس B2B/چارتر، سازمان، عملیات، مالی/مودیان، مدیر.
- ماهان: ارسال CSV سناریوهای ۶ تا ۸ به ماهان؛ اتصال به جست‌وجو و خرید.
- lint (۴۵ خطای قدیمی) و ۲ تست ناموفق قدیمی.

## ۵. برنامه‌ی بعد
1. deploy ← بررسی کامل سایت زنده (سفر مشتری، هدرها، صفحه‌ی اصلی جدید).
2. HTTPS ← بررسی هدرها، CSP، redirectها.
3. تأیید فیگما ← پیاده‌سازی پنل‌های فاز ۱ ← QA ← deploy.
4. فاز B2B/چارتر (فیگما ← کد ← QA ← deploy).

## ۶. دستورها (از ترمینال Mac)

```
# deploy
curl -fsSL https://raw.githubusercontent.com/mehdikazemi9287-byte/karentravel.ir/production/deploy/karenseir-deploy-server.sh -o ~/Downloads/karenseir-deploy.sh
ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-deploy.sh
ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-deploy.sh 2>&1 | tee ~/Downloads/deploy-out2.txt

# HTTPS (فقط بررسی)
curl -fsSL https://raw.githubusercontent.com/mehdikazemi9287-byte/karentravel.ir/production/deploy/karenseir-https-container.sh -o ~/Downloads/karenseir-https-container.sh
ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-https-container.sh 2>&1 | tee ~/Downloads/https-check2.txt
```

برگشت از deploy: اسکریپت دستور برگشت دقیق را در خروجی چاپ می‌کند (شاخه‌ی قبلی + ایمیج‌های `pre-<زمان>`).
