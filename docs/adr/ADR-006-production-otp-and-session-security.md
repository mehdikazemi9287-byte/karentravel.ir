# ADR-006: OTP و Session امن و Tenant-aware

## وضعیت

پذیرفته‌شده — ۱۴۰۵/۰۵/۲۸

## تصمیم

- ورود Production از دو فرمان `request` و `verify` با challenge تصادفی و یک‌بارمصرف انجام می‌شود.
- tenant با slug صریح انتخاب و سپس context پایگاه داده bind می‌شود؛ identifier به‌صورت plaintext در challenge ذخیره نمی‌شود.
- OTP شش‌رقمی فقط با CSPRNG ساخته، با HMAC-SHA256 و secret سرور hash و حداکثر پنج دقیقه معتبر است.
- پاسخ request برای کاربر موجود/ناموجود یکسان است. بدون delivery موفق adapter، challenge فعال و session ساخته نمی‌شود.
- verify حداکثر پنج تلاش دارد. failureهای متوالی حساب را ۱۵ دقیقه lock می‌کنند و verify موفق counter را reset می‌کند.
- replay با `consumed_at`، row lock و transaction رد می‌شود. session شامل hash توکن، device hash، IP hash، زمان استفاده و revoke reason است.
- logout نشست جاری را revoke می‌کند؛ reuse توکن refresh قبلی بعد از rotation، کل خانواده نشست را revoke می‌کند.

## پذیرش

تست‌ها باید success، expiration، wrong-code lockout، replay، refresh reuse، logout، tenant isolation، user enumeration و provider fail-closed را پوشش دهند.

## Rollback

Migration فقط جدول/ستون اضافه می‌کند. downgrade داده را حذف نمی‌کند. rollback با image قبلی انجام می‌شود و جدول‌های جدید تا پایان دوره retention دست‌نخورده باقی می‌مانند.
