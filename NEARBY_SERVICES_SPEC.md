# Nearby & Services Specification

## Nearby context

`/nearby` یک همراه محلی است، نه صرفاً نقشه. سه context را می‌پذیرد:

1. موقعیت فعلی کاربر، فقط پس از رضایت و مجوز location؛
2. اطراف محل اقامت از Trip Context؛
3. اطراف مقصد سفر از Trip Context.

نسخه فعلی از مختصات نمونه شیراز و `MockPlaceProvider` استفاده می‌کند و هیچ Google/Maps API یا location واقعی فعال نیست.

## تمایز منبع و رابطه تجاری

- `contracted`: شریک نمونه کارن‌سیر؛ فقط با نشان «شریک نمونه».
- `credit-enabled`: پذیرنده نمونه اعتبار؛ با نشان کوتاه «اعتبارپذیر».
- `external`: مکان عمومی منبع Mock؛ بدون نشان شراکت یا مزیت.

نام‌ها، فاصله‌ها، ساعات و مزیت‌ها همگی نمونه‌اند و قرارداد واقعی را القا نمی‌کنند.

## Provider ports

- `PlaceProvider.searchNearby({ latitude, longitude, radius, category, sort })`
- `MapProvider.getViewport(...)`
- `BookingProvider.createBooking(...)`
- `NotificationProvider.listForTrip(...)`
- `PaymentProvider.authorize(...)`

UI فقط به interfaceهای دامنه وابسته است؛ adapter آینده Google Places یا هر Provider دیگر منطق تجاری اختصاصی را وارد component نمی‌کند.

## پذیرش و Rollback

- `/nearby` context selector، category control، map surface و results sheet responsive دارد.
- `/services` خدمات actionable را از مقصدهای الهام‌بخش جدا می‌کند.
- نبود اتصال واقعی صریح، fail-closed و بدون CTA پرداخت/رزرو قطعی است.
- Rollback با حذف routeهای `nearby/services` و module provider Mock انجام می‌شود و داده پایداری را تغییر نمی‌دهد.
