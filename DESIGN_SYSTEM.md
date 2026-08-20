# Design System

## Tokens

`ink #08253D`، `ocean #0E7490`، `sun #F4B942`، `mist #F7FAFC`، `surface #FFFFFF`، `muted #617184`، `danger #B42318`. spacing: 4/8/12/16/24/32/48. radius: 12/20/28. shadow: نرم و کم‌کنتراست.

## Components

Button، Input، Search field، Select/filter chip، Card، Data table، Badge، Metric، Progress، Alert، Drawer، Bottom navigation، Empty state، Skeleton و Comparison row باید API مستقل، حالت disabled/loading/error و RTL داشته باشند.

## Themeability

tokenهای semantic با CSS variables تعریف می‌شوند؛ White Label فقط token، asset، content و feature flag را تغییر می‌دهد، نه کد fork شده. Componentهای مالی باید منشأ داده و وضعیت policy را نمایش دهند.
# افزوده فاز Homepage

- رنگ اصلی: سرمه‌ای `#071f35`؛ رنگ کنش و تأکید: فیروزه‌ای `#0b8f8b`؛ سطح گرم: `#f7f5f0`؛ accent محدود: `#f3a446`.
- تایپوگرافی فارسی بر پایه fallbackهای محلی امن (Vazirmatn/Tahoma) و سلسله‌مراتب fluid با `clamp` است.
- شعاع کارت‌های اصلی ۲۰ تا ۲۸ پیکسل، خطوط کم‌رنگ و سایه‌های کنترل‌شده است.
- وضعیت focus با outline فیروزه‌ای، motion با احترام به `prefers-reduced-motion` و RTL به‌صورت document-level اعمال می‌شود.

## بازطراحی مرجع تصویری — فاز Plum / Coral

- Homepage از سایر صفحات مستقل است و از زمینه کرم `#f5eee4`، بنفش بسیار تیره `#2a1530` و کورال `#ef5b3d` استفاده می‌کند. بخش AI Homepage نیز فقط از همین خانواده رنگ استفاده می‌کند و آبی/سرمه‌ای/فیروزه‌ای ندارد.
- ترتیب صفحه بدون جابه‌جایی بخش‌های موجود، دستیار AI را بلافاصله پس از سفرهای منتخب و پیش از مقایسه نگه می‌دارد.
- تراکم عمودی صفحه کنترل‌شده و فاصله‌های بخش‌ها ۶۴ تا ۸۸ پیکسل در Desktop و ۴۸ تا ۶۴ پیکسل در Mobile است.
- صفحات عملیاتی موجود می‌توانند tokenهای قبلی را حفظ کنند؛ ممنوعیت پالت سرمه‌ای/فیروزه‌ای فقط برای Homepage اعمال می‌شود.
