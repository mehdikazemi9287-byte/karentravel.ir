# Risk, Assumption & Dependency Register

| نوع | مورد | کنترل/وضعیت |
|---|---|---|
| Assumption | دو سازمان فرضی برای نمایش isolation کافی‌اند | فقط UI؛ backend نیازمند RLS test است |
| Assumption | موجودی و ارقام Prototype Mock هستند | در همه صفحه‌ها برچسب Mock دیده می‌شود |
| Risk | نشت داده بین tenant | RLS، tenant context، audit و penetration test پیش از Production |
| Risk | توهم AI درباره قیمت | ابزار authoritative و fail-closed |
| Risk | provider ناپایدار/بدون قرارداد | adapter، circuit breaker، manual disable و عدم نمایش اتصال |
| Risk | قواعد اعتبار/اقساط | review حقوقی/مالی و ledger server-side |
| Dependency | Provider contracts/credentials | هنوز موجود نیست؛ blocker production integration |
| Dependency | payment/OTP/KYC | adapter و قراردادهای معتبر لازم است |
| Dependency | Brand approval | لوگوی نهایی و مسیر بصری نیازمند تأیید مالک است |
