# نیرا (NRS) — خلاصهٔ کاری وب‌سرویس فروش بلیت برای کارن‌تراول

- **منبع:** «NRS API Refrence 1405-03-18»، پایگاه دانش نیرا (https://helpdesk.nirasoft.ir/Dana/Kb/89-NRS-API-Refrence-1405-03-18).
- **ماهیت:** این فایل خلاصهٔ کاری خودمان است، نه کپی سند.
- **پیش از هر تغییر:** نسخهٔ سند را با آخرین نسخهٔ پایگاه دانش مقایسه کنید.
- **تصمیم مالک (۷ آذر ۱۴۰۵):** حساب‌های نیرای ایرلاین‌ها **به نام تاژبان** است. کارن‌تراول زیر مجوز تاژبان از همین حساب‌ها استفاده می‌کند.
- **ایران ایرتور:** روی نیرا نیست؛ سیستمش هنوز مشخص نشده و اتصالش جداست.

## اصول
- **یک API برای همهٔ ایرلاین‌ها:** فقط آدرس پایه و حساب هر ایرلاین فرق می‌کند. هر ایرلاین نام کاربری و رمز جدا می‌دهد (بر اساس قرارداد با واحد بازرگانی همان ایرلاین).
- **دو نسل آدرس:**
  - **WS1** (`{host}/ws1/...`): `AvailabilityJS.jsp`، `AvailabilityFareJS.jsp`، `FareJS.jsp`، `NRSRT.jsp`، `NRSETR.jsp`، `NRSCommand.jsp`، `NRSPenalty.jsp`، `NRSPenaltyNow.jsp`.
  - **WS2** (`{host}/ws2/cgi-bin/NRSWeb.cgi/...`؛ نام cgi در بعضی ایرلاین‌ها `NRSWEB.cgi` یا `NRSWebWS.cgi` است): `ReservJS`، `ReservJS2`، `ReservJS-TwoLeg`، `ETIssueJS`، `CancelPNRJS`، `CancelSeatJS`، `ETRefundJS`.
- **فراخوانی:** همه GET با پارامتر query است و پاسخ JSON. **رمز (`OfficePass`) در query می‌رود**، پس هیچ URL کاملی نباید لاگ شود؛ `OfficeUser` و `OfficePass` در لاگ همیشه پنهان شوند.
- **محیط آزمایشی نیرا:** کد `A1`، `http://a1.nirasoft.ir/ws1` و `http://a1.nirasoft.ir/ws2/cgi-bin/NRSWeb.cgi`.
- **کانال فروش:** کاربر وب‌سرویس باید همان «یوزر با پسوند WS» باشد که ایرلاین تعریف کرده؛ وگرنه خطای `Sales Channel not Allowed`.
- **IP:** ایرلاین‌ها معمولاً IP سرور را whitelist می‌کنند.
- **صدور اعتباری:** ضمانت‌نامه باید تأیید مالی شده باشد و مجوز صدور بلیت الکترونیک برای کد کاربر صادر شده باشد.

## مسیر خرید
1. **AvailabilityFare** (یا Availability) برای فهرست پرواز با ظرفیت (و قیمت).
   - فقط در مسیرهایی که آن ایرلاین پرواز دارد فراخوانی شود؛ درخواست بی‌جا بار ایجاد می‌کند.
   - رفت و برگشت را بعضی ایرلاین‌ها پشتیبانی نمی‌کنند؛ دو درخواست جدا.
2. **Fare:** نرخ دقیق کلاس انتخاب‌شده به تفکیک بزرگسال، کودک و نوزاد، همراه عوارض و قوانین استرداد.
3. **ReservJS:** ساخت PNR با TimeLimit. پیش از رزرو، ساعت پرواز دوباره با Availability مقایسه شود؛ ایرلاین‌ها زیاد ساعت عوض می‌کنند.
4. **ETIssueJS:** صدور. PNR قطعی می‌شود و برای هر مسافر یک TicketNo برمی‌گردد. فراخوانی دوباره همان شماره‌ها را برمی‌گرداند، پس idempotent است.

## مسیر استرداد
1. آزادکردن جا:
   - همهٔ مسافران PNR: `CancelPNRJS`.
   - بعضی مسافران: `CancelSeatJS`، یک‌بار برای هر مسافر.
   - **زمان کنسل جا مبنای جریمه است.** بعد از StopBookTime ممکن نیست. اگر پرواز تغییر ساعت داشته (سگمنت TK/UN)، باید CancelSeat زده شود، نه CancelPNR.
2. **NRSPenalty / NRSPenaltyNow:** محاسبهٔ جریمه.
   - پیش از کنسل جا، Penalty بیشترین درصد را می‌دهد و PenaltyNow با فرض ابطال حساب می‌کند. **خروجی PenaltyNow پیش از ابطال جا در ETRefund پذیرفته نمی‌شود.**
   - پس از ابطال، هر دو برابرند. پس اول کنسل جا، بعد جریمه.
3. **ETRefundJS:** ثبت مالی استرداد، برای هر بلیت جدا.
   - `Fare` همان نرخ پایه است.
   - `LP` عوارض فرودگاهی است (TaxCode=LP از ETR).
   - `KU` جمع بقیهٔ عوارض از ETR است.
   - `Penalty` از خروجی Penalty می‌آید.

## بازیابی
- **NRSRT:** اطلاعات PNR (وضعیت، سگمنت‌ها، مسافران، DOCS، بلیت‌ها، مبالغ).
- **NRSETR:** اطلاعات بلیت (Fare، TotalPrice، TAXES، **Comission**، COUPONS، History).
- **NRSCommand:** فرمان ترمینال؛ مثلاً `CRD` برای اعتبار باقی‌مانده و مبلغ بلوکه‌شده.

## پارامترها (نام‌ها)
- **مشترک:** `Airline` (کد ایرلاین)، `OfficeUser`، `OfficePass`.
- **AvailabilityFare / Availability:**
  - `cbSource` و `cbTarget` (کد شهر)؛ `cbAdultQty`، `cbChildQty` و `cbInfantQty`.
  - تاریخ: `cbDay1` و `cbMonth1` (شمسی) یا `DepartureDate` (میلادی، YYYY-MM-DD). اگر هر دو باشند، `DepartureDate` اولویت دارد. پس همیشه `DepartureDate` درست فرستاده شود.
  - خروجی `AvailableFlights[]`: `Origin`، `Destination`، `DepartureDateTime`، `ArrivalDateTime`، `FlightNo`، `Airline`، `Transit`، `ClassesStatus` (در AvailabilityFare آرایهٔ `{FlightClass, Cap, Price, CurrencyCode}`)، `ClassRefundStatus`، `AircraftTypeCode`.
  - کد ظرفیت: `A` یعنی بیش از ۹ صندلی؛ `0` تا `9` تعداد دقیق؛ `C` پر؛ `X` کنسل.
  - **تاریخ خروجی حتماً با تاریخ درخواستی مقایسه شود.**
- **Fare:**
  - ورودی: `Route` (مثلاً `THR-MHD`)، `RBD` (کلاس)، `FlightNo`، `DepartureDate`.
  - خروجی: `AdultFare`/`ChildFare`/`InfantFare` (پایه)، `AdultTotalPrice`/`ChildTotalPrice`/`InfantTotalPrice`، `AdultTaxes`/`ChildTaxes`/`InfantTaxes`، `CRCNRules` (قوانین استرداد)، `BaggageAllowanceWeight`، `BaggageAllowancePieces`.
  - رشتهٔ عوارض با `$` جدا شده و هر بخش `CODE:amount,EN_Desc:...,FA_Desc:...` است.
- **ReservJS:**
  - `cbSource`، `cbTarget`، `FlightClass`، `FlightNo`، `Day`/`Month` یا `DepartureDate`، `No` (تعداد)، `edtContact`.
  - برای هر مسافر ۱ تا ۹: `edtName{i}`، `edtLast{i}`، `edtAge{i}` و `edtID{i}`.
  - `edtContact` می‌تواند چند مقدار جدا با `|` داشته باشد.
  - **جنسیت به نام چسبانده می‌شود:** `MR` برای مرد؛ `MS`، `MRS` یا `MISS` برای زن.
  - اولین مسافر بزرگسال باشد. هر بزرگسال حداکثر ۴ کودک یا نوزاد.
  - `edtID` برای ایرانی پرواز داخلی: `I_{IssuedBy}_{NationalId}_{BirthCountry}_{BirthDate}_{Gender}_{Expire}_{Last}_{First}`؛ کد ملی و تاریخ تولد الزامی‌اند و بقیه می‌توانند خالی بمانند.
  - `edtID` برای پاسپورت: `P_...` با همان ترتیب.
  - تاریخ‌ها به شکل `28DEY73` (شمسی) یا `28JAN95` (میلادی).
  - خروجی `AirReserve[0]`: `{Error, PNR}`. موفق یعنی `Error` برابر `No Err` یا `Success`.
- **ETIssueJS:**
  - ورودی: `PNR`، `Email`.
  - خروجی: `AirNRSTICKETS` با `NAME=TicketNo` برای هر مسافر. بلیت الکترونیکی به ایمیل هم فرستاده می‌شود.
- **CancelPNRJS:** خروجی موفق `No Error COMMAND PNR CANCELLED`، و برای ابطال دوباره `Already Cancelled`.
- **CancelSeatJS:** ورودی `PNR`، `PassengerName`، `PassengerLastName`، `DepartureDate`، `FlightNo`. خروجی `{Done:"true", NewSplittedPNR}`.
- **NRSPenalty / NRSPenaltyNow:**
  - ورودی: `TicketNo`.
  - خروجی: `RefundedTaxes[]`، `Legs[]` با `{RefundedFare, Amount, Mode (P درصدی و F ثابت), AM, Cancellation}`، `PENALTY`، `RefundedAmount`.
- **ETRefundJS:**
  - ورودی: `TicketNo`، `Fare`، `KU`، `LP`، `Penalty`.
  - خروجی: `AirNRSRefund[0]` با `{Done, Desc}`. موفق یعنی `Done=0`؛ خطای مبلغ `Done=-5000` با `INCORRECT RETURN FARE`.

## خطاهای مهم (برای نگاشت به پیام فارسی)
- **پرواز و کلاس:** `FLIGHT CLOSED`، `CLASS CLOSED`، `INVALID FLIGHT`، `POINT OF SALES RESTRICTED`.
- **اعتبار:** `NOT ENOUGH CREDIT`.
- **مدارک و کد ملی:** `SSR DOCS IS MANDATORY…`، `INVALID DOCS NUMBER(S)`، `DUPLICATE NATIONAL CODES`، `INVALID PASSPORT INFORMATION`، `PASSPORT DOCS SSR IS MANDATORY FOR INTERNATIONAL FLIGHTS`.
- **حساب کاربری:** `Access Denied`، `User Account has been expired`، `Invalid User Name`، `Incorrect Password`، `Sales Channel not Allowed`، `REMOTE USER NOT REGISTERED`، `SIGN!`.
- **مسافر و تماس:** `Invalid Passenger Name`، `Invalid Passengers Contact`، `InCorrect Contact`.
- **بلیت و PNR:** `Invalid Ticket Number`، `Ticket Number not Found`، `PNR is already Ticketed`، `PNR Is Cancelled`، `Already Cancelled`، `NO ELECTRONIC TICKET LOADED YET`.
- **رزرو و مسیر:** `Reservation Failur`، `Child or Infant without parents…`، `INVALIDDESTINATION`.

## جدول آدرس پایهٔ ایرلاین‌ها (hostها)
EP آسمان `restapi.iaa.ir` · FP فلای‌پرشیا `api.flypersiaairlines.ir` · HH تابان `api.taban.aero` (cgi: NRSWebWS) · IV کاسپین `api.caspianairlines.com` · I3 آتا `api.ataair.ir` · IRZ ساها `api.sahaair.com` · J1 معراج `apps.merajairlines.ir` · NV کارون `api.karunair.ir` (cgi: NRSWEB) · PA پارس‌ایر `api.parsair.ir` · PY پویا `api.pouyaair.com` (cgi: NRSWEB) · QB قشم‌ایر `api.qeshm-air.com` · VR وارش `api.vareshair.ir` (cgi: NRSWebWS) · Y9 کیش‌ایر `api.kishairlines.ir` (cgi: NRSWEB) · ZV زاگرس `api.zagrosairlines.com` · DZD یزد `api.yazdairways.com` · IRU چابهار `api.chabaharairlines.ir` · A7 آسا جت `api.asajet.ir` · RAI ریمون `api.raimonairways.com` · ATS اطلس `api.atlasairplus.com` · TKN کیش ایران `api.flykishiran.com` · NSN نسیم `api.nasimairlines.ir` · ISP جی‌اسکای `nrs.jskyair.com` · MEH مهر `api.mehrairways.com` · LMB/MBL لاد `nrs.ladairways.ir` · SHR سروش `nrs.soroushair.com` · A1 تست نیرا `a1.nirasoft.ir` (http)

(همه https هستند جز A1. نام فایل cgi در WS2 پیش‌فرض `NRSWeb.cgi` است، مگر جایی که بالا نوشته شده. **آدرس دقیق هر ایرلاین پیش از فعال‌سازی با جدول آخرین نسخهٔ سند چک شود.**)
