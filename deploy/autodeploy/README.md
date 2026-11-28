# انتشار خودکار از گیت‌هاب (main) به سرور

تصمیم مالک (۱۴۰۵/۰۹/۰۷): «دسترسی کامل به سرور» و «بدون تأیید جداگانه منتشر شود». یعنی **هر ادغام در `main` روی گیت‌هاب = انتشار روی سایت**. تأیید مالک همان ادغام در گیت‌هاب است.

- هر ۱۰ دقیقه سرور `origin/main` را می‌خواند. اگر جدیدتر از نسخهٔ در حال اجرا بود، اول `/root/deploy.sh --check` و بعد `/root/deploy.sh` اجرا می‌شود (پشتیبان دیتابیس، migration، سلامت، بازگشت خودکار).
- فقط یک‌طرفه است: گیت‌هاب ← سرور. **کانال اجرای دستور نیست.**
- هیچ چیزی پاک نمی‌کند. نسخه‌ای که شکست بخورد ثبت می‌شود و دوباره امتحان نمی‌شود. اگر فضای دیسک کمتر از ۸ گیگ باشد یا تاریخچه جدا شده باشد، متوقف می‌شود.
- وضعیت: `/opt/karenseir/autodeploy/status.log` روی سرور و `https://karentravel.ir/build_info.json`.
- توقف موقت: ساختن فایل `/opt/karenseir/autodeploy/PAUSE` (برای ادامه، تغییر نامش).

## نصب روی سرور (فقط از main)
```
cd /opt/karenseir/app && git fetch -q origin main
install -d /opt/karenseir/autodeploy
git show origin/main:deploy/autodeploy/karenseir-autodeploy.sh > /opt/karenseir/autodeploy/karenseir-autodeploy.sh
git show origin/main:deploy/autodeploy/karenseir-autodeploy.service > /etc/systemd/system/karenseir-autodeploy.service
git show origin/main:deploy/autodeploy/karenseir-autodeploy.timer > /etc/systemd/system/karenseir-autodeploy.timer
systemctl daemon-reload && systemctl enable --now karenseir-autodeploy.timer
```
