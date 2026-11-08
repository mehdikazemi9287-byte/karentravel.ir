# گزارش پیشرفت کارن تراول (کارن‌سیر) — ۱۷ آبان ۱۴۰۵ (۸ نوامبر ۲۰۲۶)

این فایل گزارش کامل کار امروز، وضعیت فعلی سرور، شواهد QA، کارهای باقی‌مانده و برنامه‌ی مراحل بعد است.
هدف: اگر هر ابزار یا دسترسی‌ای قطع شد، هر کسی با همین فایل و مخزن بتواند کار را ادامه دهد.

---

## ۱. خلاصه در یک نگاه

| موضوع | وضعیت |
|---|---|
| سایت `http://karentravel.ir` | ✅ بالا، نسخه‌ی جدید با برند «کارن تراول» |
| کد روی سرور | ✅ production `25d43ea` (+ commit مخصوص سرور) روی شاخه‌ی `release-20261108-1832` |
| گواهی ماهان (سناریوهای ۶ تا ۸) | ✅ هر سه رزرو شد: `TL2C2`، `TL2C3`، `TL2C4` (بلیت صادر نشد) |
| HTTPS | ⏳ در حال آماده‌سازی؛ اسکریپت مخصوص nginx کانتینری در حال نوشتن و آزمایش |
| هدرهای امنیتی تکراری | ⏳ با مرحله‌ی HTTPS رفع می‌شود |
| خطاهای lint (۴۵ خطا) | ❌ از قبل وجود داشته؛ CI را قرمز می‌کند؛ PR جدا لازم است |
| ۲ تست backend ناموفق | ❌ از قبل وجود داشته؛ به کار امروز ربطی ندارد؛ باید بررسی شود |

---

## ۲. کارهای انجام‌شده امروز

### PR #43 — ماهان، سناریوهای ۶ تا ۸ (merge شد، commit `5f59880`)
- بررسی کامل: تست کل backend و build فرانت.
- مشکل پیدا و رفع شد: تست‌ها تاریخ ثابت داشتند و از ۱ دسامبر ۲۰۲۶ خودبه‌خود شکست می‌خوردند؛ حالا تاریخ نسبت به امروز ساخته می‌شود.
- اگر رزرو به timeout بخورد، دیگر با نام تازه تکرار نمی‌شود (جلوگیری از PNR تکراری)؛ سناریو با کد `BOOK_UNKNOWN` متوقف می‌شود.
- کش «نرخ ندارد» برای هر مسیر و ترکیب مسافر جدا شد؛ پاسخ نامعتبر ماهان خطای قابل‌گزارش می‌دهد؛ رمز OfficePass در متن خطا پوشانده می‌شود.
- **نتیجه‌ی اجرای واقعی روی QAA:** سناریو ۶ → `TL2C2`، سناریو ۷ → `TL2C3`، سناریو ۸ → `TL2C4`. هیچ بلیتی صادر نشد.

### PR #44 — اسکریپت HTTPS و یک منبع برای هدرهای امنیتی (merge شد، commit `25d43ea`)
- مانع اصلی پیدا و رفع شد: اسکریپت با `ssh … 'bash -s'` بعد از خط ۸۸ بی‌صدا تمام می‌شد.
- اجرای دوباره دیگر بلوک 443 را برنمی‌دارد؛ rollback ایمیج قبلی را برمی‌گرداند؛ شکست وسط کار nginx و `.env` را خودکار برمی‌گرداند.
- هدرهای امنیتی روی پاسخ‌های خطا و redirect هم فرستاده می‌شوند.
- **توجه:** این اسکریپت برای nginx نصب‌شده روی خود سرور است. سرور فعلی nginx را در کانتینر اجرا می‌کند، پس نسخه‌ی مخصوص کانتینر لازم است (بخش ۵).

### PR #45 — اسکریپت deploy مخصوص چیدمان فعلی سرور (merge شد، commit `57317b5`)
- فایل: `deploy/karenseir-deploy-server.sh`
- پشتیبان دیتابیس، tag ایمیج‌ها برای برگشت، build فقط web/api/worker، بررسی سلامت، برگشت خودکار در صورت خرابی.

### Deploy روی سرور
- سرور از `release-20261104-1735` (`8ca27bd`) به production `25d43ea` رفت.
- خروجی: `DEPLOY-OK: production 25d43ea on branch release-20261108-1832`.
- بررسی بعد از deploy در مرورگر: عنوان «کارن تراول \| بلیط هواپیما، قطار، هتل و تور»؛ صفحه‌ی اصلی، `/flights`، `/hotels`، `/tours`، `/trains`، `/api/health`، `/sitemap.xml`، `/robots.txt` همه 200؛ IP سرور در HTML نیست.

---

## ۳. شواهد QA

| بررسی | production قبل از merge (`d440feb`) | بعد از merge (`25d43ea`) |
|---|---|---|
| تست‌های backend (کامل، sqlite) | ۵۷۷ موفق، ۲ ناموفق، ۷ رد شده | ۵۸۷ موفق، ۲ ناموفق، ۷ رد شده |
| تست‌های ماهان | — | ۱۲ از ۱۲ |
| تست‌های امنیتی | — | ۲۰ از ۲۰ |
| build فرانت (`npm run build`) | موفق | موفق |
| `tsc --noEmit` | — | بدون خطا |
| lint | ۴۵ خطا (از قبل) | ۴۵ خطا (بدون خطای تازه) |
| `bash -n` و shellcheck اسکریپت‌ها | — | بدون هشدار تازه |
| `nginx -t` پیکربندی‌های مخزن | — | موفق |

دو تست ناموفق (هر دو از قبل، روی production هم):
- `test_booking_financial_journey.py::test_organization_credit_and_wallet_funding_reserve_capture_release_and_isolation` — پاسخ funding شش فیلد بیشتر از انتظار تست دارد.
- `test_final_internal_domains.py::test_installment_execution_and_settlement_posting_are_tenant_safe` — ثبت settlement به جای 201 پاسخ 409 می‌دهد.

---

## ۴. وضعیت فعلی سرور (۱۸۸.۱۲۱.۱۲۳.۲۱۸)

- پوشه‌ی پروژه‌ی compose: `/opt/karenseir` (فایل‌های `docker-compose.yml` و `docker-compose.override.yml` مخصوص سرور، `.env`، `backup.sh`).
- کد: `/opt/karenseir/app` (مخزن git **بدون remote**). production مستقیم از GitHub عمومی گرفته می‌شود.
- commit مخصوص سرور که باید در هر deploy حفظ شود: `8ca27bd` (mirror پیپ و فایل جای‌خالی `catalog_data`). اسکریپت deploy خودکار حفظش می‌کند.
- nginx: **کانتینر** `karenseir-nginx-1` (`nginx:1.27-alpine`)، پیکربندی `/opt/karenseir/nginx/default.conf`، پورت 80 و 443 باز.
- گواهی: پوشه‌ی `/opt/karenseir/certs` خالی است. سرویس `certbot` در compose با profile `ssl` تعریف شده.
- سرویس‌ها: web، api، worker، search، assistant، db (postgres 16)، redis، nginx.
- پشتیبان شبانه: `backup.sh` ساعت ۳:۳۰ (cron کاربر karen)، پوشه‌ی `backups/`.

### برگشت از deploy امروز (فقط در صورت نیاز)
```
ssh karen@188.121.123.218 'cd /opt/karenseir/app && git checkout release-20261104-1735 && for s in web api worker; do docker tag karenseir-$s:pre-20261108-1832 karenseir-$s:latest; done && cd /opt/karenseir && docker compose up -d --no-build web api worker'
```

---

## ۵. کارهای باقی‌مانده

### در جریان
1. **HTTPS برای karentravel.ir** — اسکریپت مخصوص nginx کانتینری (`deploy/karenseir-https-container.sh`) در حال نوشتن و آزمایش روی سرور شبیه‌سازی‌شده.

### باز (به ترتیب اولویت)
2. **هدرهای امنیتی تکراری** (`nosniff, nosniff`، `DENY, DENY`): با مرحله‌ی HTTPS رفع می‌شود (nginx تنها منبع).
3. **آدرس‌ها در `.env` سرور:** `PUBLIC_ORIGIN` و `CORS_ORIGINS` هنوز روی IP؛ `ZARINPAL_CALLBACK_URL` روی دامنه‌ی قدیمی `karenseir.ir`. با مرحله‌ی HTTPS به `https://karentravel.ir` می‌روند. بعد از فعال شدن پرداخت، آدرس بازگشت جدید باید در پنل زرین‌پال هم ثبت شود.
4. **ماهان:** پر کردن شیت ماهان با جدول CSV سناریوها و ارسال به پشتیبانی ماهان؛ پرسیدن مسیر داخلی قابل‌قیمت روی QAA؛ بعد اتصال ماهان به جست‌وجو و خرید پرواز سایت.
5. **۴۵ خطای lint** که CI را قرمز نگه می‌دارد (در فایل‌های رزرو/checkout و hookهای React).
6. **۲ تست backend ناموفق** (بخش ۳).
7. **workflow دستی deploy روی GitHub** کار نمی‌کند چون فایلش در شاخه‌ی پیش‌فرض `main` نیست؛ فعلاً deploy از Mac با `deploy/karenseir-deploy-server.sh` انجام می‌شود.
8. **HSTS:** بعد از یک هفته HTTPS پایدار، از ۳۰۰ ثانیه به یک سال افزایش یابد.
9. شاخه‌ی پیش‌فرض `main` (`ac379c1`) با `production` هم‌راستا نیست؛ تصمیم لازم است کدام شاخه مرجع باشد.

---

## ۶. برنامه‌ی مراحل بعد

| مرحله | کار | چه کسی | خروجی مورد انتظار |
|---|---|---|---|
| ۱ | آماده شدن و آزمایش اسکریپت HTTPS کانتینری، PR و merge | Claude | PR جدید + فایل قابل دانلود |
| ۲ | اجرای `--check` اسکریپت HTTPS روی سرور از Mac | شما | `PREFLIGHT-OK` |
| ۳ | اجرای اصلی HTTPS | شما (با دستور آماده) | `HTTPS-OK` |
| ۴ | بررسی سایت روی https، هدرها، CSP، redirectها | Claude | گزارش QA |
| ۵ | ارسال نتایج گواهی ماهان | شما / Claude (پیش‌نویس) | پاسخ ماهان |
| ۶ | رفع lint و ۲ تست ناموفق | Claude | CI سبز |
| ۷ | اتصال ماهان به جست‌وجو و خرید پرواز | Claude | PR + تست |
| ۸ | افزایش HSTS بعد از یک هفته | شما (یک دستور) | — |

---

## ۷. راهنمای دستورها (از ترمینال Mac)

### deploy آخرین نسخه‌ی production
```
curl -fsSL https://raw.githubusercontent.com/mehdikazemi9287-byte/karentravel.ir/production/deploy/karenseir-deploy-server.sh -o ~/Downloads/karenseir-deploy.sh
ssh karen@188.121.123.218 'bash -s -- --check' < ~/Downloads/karenseir-deploy.sh      # فقط بررسی
ssh karen@188.121.123.218 'bash -s' < ~/Downloads/karenseir-deploy.sh 2>&1 | tee ~/Downloads/deploy-out.txt
```

### اجرای گواهی ماهان روی QAA
```
ssh karen@188.121.123.218 'cd /opt/karenseir && docker compose run --rm -T -e MAHAN_ENV=qaa api python -m app.mahan_cert --only 6,7,8'
```

### بررسی سلامت سایت
```
curl -sI http://karentravel.ir/ && curl -s http://karentravel.ir/api/health
```

---

## ۸. پیوندها

- مخزن: https://github.com/mehdikazemi9287-byte/karentravel.ir
- PR #43: https://github.com/mehdikazemi9287-byte/karentravel.ir/pull/43
- PR #44: https://github.com/mehdikazemi9287-byte/karentravel.ir/pull/44
- PR #45: https://github.com/mehdikazemi9287-byte/karentravel.ir/pull/45
