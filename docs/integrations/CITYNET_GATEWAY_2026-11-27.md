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

## افزوده (۷ آذر، عصر): مستندات خود نیرا
- **منبع:** پایگاه دانش نیرا (شرکت دانا پرداز)، https://helpdesk.nirasoft.ir/Dana/Kb. سند «NRS API Refrence 1405-03-18» (PDF، ۵۸ صفحه) و «NRS API Refrence Extention 1405-03-18». متن در مرورگر خوانده شد؛ PDF در مخزن گذاشته نشد (مال نیراست).
- **متدها:**
  - رزرو و خرید: Availability، AvailabilityFare، Fare، Reserve (PNR با TimeLimit)، ETIssue (صدور)، RT، ETR.
  - کنسلی و استرداد: Cancel PNR، CancelSeat، Penalty، PenaltyNow، ETRefund.
  - فرمان: Command.
  - دو نسل آدرس: WS1 و WS2، یعنی `/ws2/cgi-bin/NRSWeb.cgi`.
- **مراحل خرید:** Availability ← Fare ← Reserve ← ETIssue. پیش از Reserve، ساعت پرواز دوباره بررسی شود؛ ایرلاین‌ها ساعت را زیاد عوض می‌کنند.
- **مهم‌ترین نکته:** «قبل از فراخوانی… با واحد بازرگانی **شرکت هواپیمایی** تماس بگیرید و **بر اساس قرارداد** نام کاربری و کلمه عبور دریافت نمایید.» هر ایرلاین سرور جدای خودش را دارد. در جدول آدرس‌ها برای آسمان، فلای‌پرشیا، تابان، کاسپین، آتا، ساها، معراج، پویا، قشم‌ایر، وارش، کیش‌ایر، زاگرس، یزد، چابهار و دیگران آدرس جدا آمده است.
- **نتیجه، دو راه:**
  1. **مستقیم با نیرا:** برای هر ایرلاین قرارداد و حساب جدا لازم است (حدود ۱۹ قرارداد). اتصال یک‌بار نوشته می‌شود، ولی تسویه و اعتبار با هر ایرلاین جداست.
  2. **از طریق سیتی‌نت:** یک قرارداد و یک API برای همهٔ ایرلاین‌ها، به‌اضافهٔ هتل، CIP و بیمه. چک‌لاین امروز همین راه را می‌رود.
  - **پیشنهاد:** برای شروع، سیتی‌نت. برای ایرلاین‌هایی که تاژبان یا چک‌لاین با آن‌ها قرارداد مستقیم و نرخ بهتر دارد، بعداً اتصال مستقیم نیرا (یک آداپتر مشترک NRS با آدرس و حساب هر ایرلاین). تصمیم با مالک.
