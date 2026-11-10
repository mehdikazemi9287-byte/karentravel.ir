# راهنمای انتشار کارن تراول، ۱۹ آبان ۱۴۰۵

این راهنما همه‌ی کارهای merge‌شده تا commit `0a80a25` را روی سرور `188.121.123.218` می‌برد.
سایت الان روی نسخه‌ی قدیمی `25d43ea` است و migration آن `20261104_69` است.

همه‌ی دستورها را **روی مک خودتان** در Terminal اجرا کنید. هر اسکریپت را مستقیم از GitHub می‌گیریم
تا دیگر فایل قدیمیِ Downloads اجرا نشود.

## چه چیزی منتشر می‌شود

| بخش | PR | توضیح کوتاه |
|---|---|---|
| هویت مسافر و خرید از طرف سازمان | #55 | کد ملی، تاریخ تولد، پاسپورت، رزرو برای همکار |
| صفحه‌ی اصلی | #58 | تلفن پشتیبانی در هدر، گزینه‌ی یک‌طرفه (تأییدشده) |
| پنل‌ها، فاز ۱ | #67 | چرخه‌ی کنسلی و استرداد، صف عملیات، استرداد دونفره‌ی مالی، تطبیق حساب |
| امنیت | #68 | تأیید دونفره برای شارژ کیف پول و اعتبار، جداسازی کلیدهای امضا، غیرفعال‌سازی داده‌ی دمو |
| تست‌ها | #66، #69 | CI و e2e سبز، رفع منوی حساب و صفحه‌ی ویزا |

**migrationهای جدید** (به ترتیب): `20261109_70` هویت مسافر، `20261109_71` پس از فروش،
`20261109_72` تأیید دونفره، `20261109_73` ستون `disabled_at`. همه افزودنی‌اند: جدول جدید یا ستون nullable.
روی دیتابیس آزمایشی Postgres 16 از `20261104_69` تا `20261109_73` اجرا شد و بدون خطا تمام شد.
دسترسی‌های `karenseir_api` و RLS هم درست ساخته شد.

**نیاز به تغییر `.env` ندارد.** کلیدهای امضای جدید اگر تنظیم نشوند از همان `JWT_SECRET` ساخته می‌شوند
و هیچ کاربری از حساب بیرون نمی‌افتد.

## مرحله ۱: بررسی بدون تغییر

```bash
curl -fsSL https://raw.githubusercontent.com/mehdikazemi9287-byte/karentravel.ir/production/deploy/karenseir-deploy-server.sh \
  | ssh karen@188.121.123.218 'bash -s -- --check --discard-server-edits'
```

باید `DEPLOY-CHECK-OK` ببینید. اگر فهرست ۵ فایل تغییرکرده‌ی سرور را نشان داد، طبیعی است.
در مرحله‌ی بعد این تغییرها در `backups/server-edits-*.patch` ذخیره و کنار گذاشته می‌شوند.

## مرحله ۲: انتشار

```bash
curl -fsSL https://raw.githubusercontent.com/mehdikazemi9287-byte/karentravel.ir/production/deploy/karenseir-deploy-server.sh \
  | ssh karen@188.121.123.218 'bash -s -- --discard-server-edits' 2>&1 | tee ~/Downloads/deploy-1405-08-19.txt
```

اسکریپت این کارها را به ترتیب انجام می‌دهد:
۱. از دیتابیس backup می‌گیرد.
۲. ایمیج‌های فعلی را با برچسب `pre-<زمان>` نگه می‌دارد.
۳. کد را می‌سازد و migrationها را اجرا می‌کند.
۴. سلامت سایت را چک می‌کند.

اگر build یا migration شکست بخورد، کد و ایمیج‌ها خودکار به نسخه‌ی قبل برمی‌گردند.
اگر health check شکست بخورد هم همین‌طور. پایان موفق: خط `DEPLOY-OK` و `migration head after: 20261109_73`.

**برگشت دستی:** دستور کامل آن در آخرِ خروجی چاپ می‌شود. برای برگشتِ کد لازم نیست دیتابیس downgrade شود،
چون نسخه‌ی قبل با جدول‌ها و ستون‌های اضافه مشکلی ندارد. migration تأیید دونفره عمداً downgrade نمی‌شود،
چون سابقه‌ی حسابرسی است. اگر واقعاً لازم شد، از backup مرحله‌ی ۲ بازیابی کنید.

## مرحله ۳: خاموش کردن داده‌های دمو (بدون حذف)

```bash
U=https://raw.githubusercontent.com/mehdikazemi9287-byte/karentravel.ir/production/deploy
curl -fsSL $U/karenseir-demo-data-disable.sh | ssh karen@188.121.123.218 'bash -s -- --check'
curl -fsSL $U/karenseir-demo-data-disable.sh | ssh karen@188.121.123.218 'bash -s'
```

حساب‌های `*.test` و دو سازمان دمو (`aftab-bank`، `faraz-industries`) غیرفعال می‌شوند.
دو tenant واقعی هیچ‌وقت لمس نمی‌شوند. دستور undo در خروجی چاپ می‌شود.

## مرحله ۴: نقش دیتابیس API

```bash
curl -fsSL $U/karenseir-db-role-check.sh | ssh karen@188.121.123.218 'bash -s -- --check'
```

اگر نوشت API با `karenseir` (superuser) وصل است، RLS عملاً دور زده می‌شود. در آن صورت:

```bash
curl -fsSL $U/karenseir-db-role-check.sh | ssh karen@188.121.123.218 'bash -s -- --apply'
```

این دستور نقش `karenseir_api` را با رمز تصادفی می‌سازد و خط جدید `DATABASE_URL` را **فقط چاپ می‌کند**.
`.env` را خودتان عوض کنید. خط `MIGRATION_DATABASE_URL` را هم که اسکریپت چاپ می‌کند به `.env` اضافه کنید.
این خط به کاربر قبلی (`karenseir`) اشاره می‌کند تا اسکریپت انتشار migrationها را با آن اجرا کند. بعد `docker compose up -d api worker` را اجرا کنید و دوباره `--check` بگیرید.

## مرحله ۵: HTTPS

```bash
curl -fsSL $U/karenseir-https-container.sh | ssh karen@188.121.123.218 'bash -s -- --check'
```

وقتی check سبز شد، همان دستور را بدون `--check` اجرا کنید. اسکریپت برگشت آن
`karenseir-https-container-rollback.sh` است. HSTS اول با ۳۰۰ ثانیه شروع می‌شود.

## مرحله ۶: بعد از HTTPS

در `.env` این دو خط را بگذارید و api را restart کنید:

```
AUTH_COOKIE_MODE=1
AUTH_COOKIE_SECURE=1
```

با این کار نشست کاربر در کوکی httpOnly نگه داشته می‌شود.

## کارهایی که فقط از دست خودتان برمی‌آید

- **احراز هویت حساب کاوه‌نگار.** تا انجام نشود، پیامک با خطای ۴۳۰ رد می‌شود. تنظیم سرور آماده است.
- **ارسال ایمیل ماهان** همراه فایل `docs/integrations/mahan/cert-scenarios-6-8-1405-08-17.csv`.
- **نماد اعتماد و مجوز** برای تأیید قالب‌های اصلی پیامک.
- **پرسش‌های وکیل و حسابدار:** مسئولیت در فروش همکار و نرخ مالیات بر کمیسیون.
