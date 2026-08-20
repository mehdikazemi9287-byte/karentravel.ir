# Booking Management & After-Sales Specification

## اصل تجربه

پیش از هر تغییر، کنسلی یا استرداد، نتیجه و هزینه باید به کاربر نمایش داده شود. کلیک اولیه هیچ رزروی را تغییر نمی‌دهد. نسخه فعلی صرفاً Mock و fail-closed است.

## دامنه خدمات

پرواز، هتل، اقامتگاه، قطار، تور، اجاره خودرو، ترانسفر، تجربه و سایر خدمات قابل رزرو از یک مدل مشترک استفاده می‌کنند؛ ruleهای هر نوع خدمت و Provider جدا ارزیابی می‌شوند.

## snapshot و policy جاری

- `policyAtBooking`: snapshot تغییرناپذیر قوانین زمان خرید، همراه نسخه و زمان ثبت.
- `currentPolicy`: آخرین policy دریافت‌شده برای ارزیابی شرایط جاری.
- اختلاف این دو باید برای audit حفظ شود و policy جدید نباید بی‌صدا جای تعهد زمان خرید را بگیرد.

## مسیر درخواست

`ثبت درخواست → در حال بررسی → در انتظار تأمین‌کننده → نیازمند اقدام کاربر → تأیید/رد → در حال بازپرداخت → بازپرداخت شد → بسته شد`

مسیرهای voluntary، provider disruption، exceptional و platform/operational error rule path یکسان ندارند.

## Quote و confirmation

هر `CancellationQuote` یا `ChangeQuote` شامل eligibility، deadline، policy source، جریمه و مبلغ قابل استرداد است. اگر Provider معتبر در دسترس نباشد، مبلغ‌ها `unknown` می‌مانند و پیام «نیاز به بررسی قوانین تأمین‌کننده» نمایش داده می‌شود. تأیید نهایی prototype فقط escalation نمایشی می‌سازد و mutation واقعی ندارد.

## AI و پشتیبانی

AI از Booking Context intentهای کنسلی، مبلغ بازگشت، تغییر تاریخ/اتاق/شب، لغو Provider، واچر جدید و وضعیت استرداد را تشخیص می‌دهد؛ عدد یا eligibility تولید نمی‌کند. نبود policy معتبر به hand-off «ارسال برای بررسی کارشناس» ختم می‌شود.

## Visibility و context

SupportDock در gateway و تمام سطوح سفر حضور دارد. AI، کارشناس انسانی، پیگیری رزرو، after-sales و مشکل فوری actionهای مستقل‌اند. وقتی Trip Context موجود است، مقصد در prompt کمک نمایش داده می‌شود؛ disruption ثبت‌شده نیز پیام مستقل و Mock دارد.

برای اقامت، action catalog شامل refundable/non-refundable، deadline، penalty نزدیک check-in، no-show، تغییر تاریخ/اتاق/مهمان/شب، early checkout، late arrival، لغو Provider، voucher mismatch و revised voucher است. برای حمل‌ونقل، voluntary cancellation، disruption/delay، تغییر تاریخ، rebook/reissue، no-show، penalty و refundable amount جدا مدل می‌شوند؛ availability هر مورد از Provider می‌آید.

## پذیرش و Rollback

- `/manage-booking/book1` summary، action selector، policy preview، confirmation و request timeline دارد.
- CTA مدیریت رزرو در My Trip، confirmation، BookingCard، VoucherCard، AI و Support دیده می‌شود.
- شناسه نامعتبر `404` است؛ هیچ درخواست یا transaction واقعی ساخته نمی‌شود.
- Rollback با حذف route/component مدیریت رزرو و مدل‌های policy این فاز انجام می‌شود؛ migration یا داده پایدار ندارد.

## زبان مشتری

اصطلاحات فنی در model باقی می‌مانند اما UI آن‌ها را به «قوانین رزرو»، «امکان انجام درخواست»، «تغییر و صدور مجدد»، «نیاز به بررسی تأمین‌کننده» و «نسخه نمایشی» ترجمه می‌کند. تنها وضعیت جاری timeline تأکید بصری دارد و پیش از تأیید نهایی جمله «تا قبل از تأیید نهایی، رزرو شما تغییری نمی‌کند» نمایش داده می‌شود.
