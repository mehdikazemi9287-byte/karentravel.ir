# سیتی‌نت (Citynet Gateway) — مسیر پروازهای نیرا برای کارن‌تراول

تاریخ: ۷ آذر ۱۴۰۵ (۲۷ نوامبر ۲۰۲۶) · محیط: **Research**. کد و Production تغییر نکرده‌اند.

## یافته
- مالک گفت پروازهای چک‌لاین «از روی نیرا» فروخته می‌شوند. در checkline.ir یک جست‌وجوی نمونه (تهران به تبریز، ۱۰ آذر) زده شد. نتیجه‌ها (قشم‌ایر، معراج، آتا و دیگران) از نیرا مستقیم نمی‌آیند؛ افزونهٔ وردپرس `citynet` آن‌ها را از **درگاه سیتی‌نت** می‌گیرد:
  - `POST https://gateway.citysoft.ir/api/v1.0/flights/search`
  - و `parsetoken`، `refreshtoken`، `inventory/tempFlight` و `currencyconvert`.
- یعنی سیتی‌نت به نیرا (و سیستم‌های دیگر) وصل است و آژانس فقط به یک API وصل می‌شود. در اسناد پروژه هم سیتی‌نت «تأمین‌کنندهٔ فناوری/API کارن‌تراول» است (`karentravel-master-spec-v3.1-FROZEN.md`، Aggregator).
- **مستندات عمومی:** https://doc.citysoft.ir (Swagger، «Citynet API 1.0.0»، OAS 3.1). سرور `https://gateway.citysoft.ir/api/v1.0/`. ۳۲ مسیر و ۴۶ schema.

## فهرست مسیرها (خلاصه)
| بخش | مسیر |
|---|---|
| ورود | `POST /authenticate` (username, password → token) |
| پرواز | `POST /flights/search` (OriginDestinationInformations, TravelerInfoSummary, TravelPreference, SpecificFlightInfo) · `POST /flights/rules` · `POST /flights/baggage` (AirItinerary, PassengerType) · `POST /flights/captcha` · `GET /airlines?name=` · `GET /airportlist?q=` |
| هتل | `GET /hotels/smartsearch?q=` · `POST /hotels/search` (CheckIn/OutDate, RoomGuests, GuestNationality) · `POST /hotels/rooms` (CitynetCode) |
| CIP | `GET /cip/airports` · `POST /cip/search` · `GET /cip/flightlist` · `POST /cip/rules` · `POST /cip/precancel` · `POST /cip/cancel` · `POST /ticketing/ticket` (کنسلی آفلاین) |
| رزرو/صدور | `POST /bookingengine/book` (Transport، Stay، CIP، FlightAndHotel، Insurance؛ شامل Owner، Ticketing، Discount، TravelerInfo، currencyToPay) · `GET /bookingengine/ticket` (ContractNo, Credit, Wallet, Currency) |
| گزارش و مالی | `GET /contractlist` (بازهٔ تاریخ / شمارهٔ قرارداد) · `GET /report/ticket/pdf` · `GET /ledgers` · `GET /ledgers/budget` · `GET /currencyconvert` |
| بیمه | `POST /insurance/search` · `POST /insurance/markup/insuranceinfo` |

## پیشنهاد (نیازمند تأیید مالک)
1. **حساب API سیتی‌نت جدا برای کارن‌تراول** (به نام تاژبان یا کارن‌تراول؛ جدا از حساب وب‌سایت چک‌لاین). اصل هلدینگ: شخصیت‌های حقوقی جدا، و داده و تسویهٔ جدا. اطلاعات ورود فقط در `.env` سرور، نه در مخزن.
2. تأمین‌کننده در رجیستری: `citynet` با وضعیت `UNDER_EVALUATION`، و پس از قرارداد `CONTRACTED`. تا قرارداد نباشد، کد آداپتر نوشته نمی‌شود (قاعدهٔ Master Spec).
3. آداپتر یکسان با ماهان: search ← rules/baggage ← book ← ticket ← contractlist برای تطبیق، پشت `CITYNET_MODE=off|sandbox|live`، fail-closed و بدون قیمت ساختگی.
4. یک اتصال، چند ایرلاین: ایرلاین‌های نیرا (آسمان، معراج، کاسپین، زاگرس، وارش، آتا، قشم‌ایر، تابان، کارون، کیش‌ایر، فلای‌پرشیا، پارس‌ایر و دیگران) و هتل و CIP و بیمه همه از همین درگاه می‌آیند.
5. صفحهٔ `/flights`: ردیف ایرلاین‌ها فقط برای ایرلاین‌هایی که از سیتی‌نت واقعاً قابل فروش‌اند.

## پرسش‌های باز برای سیتی‌نت
- حساب sandbox یا تست دارند؟
- صدور با اعتبار (Credit) یا کیف پول (Wallet) آژانس است؟
- کمیسیون و markup در API چگونه برمی‌گردد؟
- قاعدهٔ تسویهٔ نیرا از طریق سیتی‌نت همان RTRD نیمه‌ماهه است؟
