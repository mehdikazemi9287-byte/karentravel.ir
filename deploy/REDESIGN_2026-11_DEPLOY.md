# Deploy — بازطراحی صفحات داخلی (ADR-022)

> از محیط Claude دسترسی SSH به سرور 188.121.123.218 وجود ندارد (پورت ۲۲ و دامنه از این محیط بسته است)، بنابراین deploy باید روی خود سرور با دستورات زیر انجام شود. تغییر فقط frontend است؛ API، DB و migration ندارد.

## پیش‌نیاز
- فایل patch: `deploy/patches/0001-feat-ui-inner-pages-redesign-Plum-Coral-Cream-Shell-.patch` (از گیت‌هاب، شاخه `design/stitch-redesign-2026-11`)
- طبق قانون سرور: کد در `/opt/karenseir/app` یک checkout بدون remote است؛ پس patch اعمال می‌شود، نه pull.

## مراحل
```bash
# ۱) پشتیبان و ثبت وضعیت فعلی
cd /opt/karenseir/app
git rev-parse HEAD | tee /opt/karenseir/pre-redesign-HEAD.txt
docker ps --format '{{.Names}} {{.Image}}' | tee /opt/karenseir/pre-redesign-images.txt

# ۲) اعمال patch (ابتدا بررسی خشک)
git apply --check /tmp/0001-feat-ui-inner-pages-redesign-Plum-Coral-Cream-Shell-.patch
git am /tmp/0001-feat-ui-inner-pages-redesign-Plum-Coral-Cream-Shell-.patch

# ۳) ساخت و جایگزینی فقط frontend (نام سرویس را با docker-compose.yml سرور تطبیق دهید)
cd /opt/karenseir
docker compose build frontend
docker compose up -d frontend

# ۴) بررسی
curl -sI https://karentravel.ir/ | head -1
curl -s https://karentravel.ir/hotels | grep -c 'ks-inner'      # باید ≥1 باشد
curl -s https://karentravel.ir/ | grep -c 'ks-inner'            # باید 0 باشد (Homepage دست‌نخورده)
```

## QA پس از deploy
- `/hotels`، `/compare`، `/assistant`، `/organization`، `/white-label`، `/search/results` در دسکتاپ و موبایل: هدر با تلفن، فوتر بنفش، ناوبری پایین موبایل.
- صفحه اول باید دقیقاً مثل قبل باشد.

## Rollback
```bash
cd /opt/karenseir/app
git reset --hard "$(cat /opt/karenseir/pre-redesign-HEAD.txt)"
cd /opt/karenseir && docker compose build frontend && docker compose up -d frontend
```
