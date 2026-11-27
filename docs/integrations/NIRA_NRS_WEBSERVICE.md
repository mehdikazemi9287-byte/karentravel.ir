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

## Implementation (Source — branch `feat/nira-nrs-adapter`)

**Files**
- `backend/app/nira_nrs.py` — the NRS client: config from env, host table, parsers, typed errors with Persian messages, edtID builder, redaction.
- `backend/app/nira_flight.py` — supplier behind `flight_port` (same pattern as `mahan_flight.py`) and API `/flights/suppliers/nira/{status,search,console/availability}`.
- `app/admin/suppliers/nira` + `components/panel/NiraConsolePanel.tsx` — staff-only test console (`backoffice:read`).
- Tests: `backend/tests/test_nira_nrs.py` and `backend/tests/test_nira_flight.py`. HTTP is mocked with `httpx.MockTransport`; no network.

**Environment** (server env only; placeholders in `.env.example` and `deploy/karentravel.production.env.example`)

| Name | Meaning |
| --- | --- |
| `NIRA_MODE` | `off` (default) · `sandbox` · `live`. An unknown value counts as `off` and reports `invalid_mode`. |
| `NIRA_AIRLINES` | Comma list of enabled codes. The aliases `VAR`→VR, `JI`→J1 and `TBN`→HH are accepted. |
| `NIRA_<CODE>_USER` / `NIRA_<CODE>_PASS` | The airline's web-service (WS) office user and password. |
| `NIRA_<CODE>_HOST` | Optional override of the built-in host table (`https://host` or `host`, no path). **Required for `W5`.** |
| `NIRA_<CODE>_CGI` | Optional override of the WS2 cgi name (for example `NRSWebWS.cgi`). |
| `NIRA_<CODE>_ROUTES` | Optional route table (`THR-MHD,MHD-THR`). If set, only those routes are queried for that airline; if unset, every search asks that airline. |

**Modes**
- **off:** nothing is built and no HTTP call is made. Search answers `unavailable/off` with no offers, and the rest of the site works as before.
- **sandbox:**
  - Only `A1` on `a1.nirasoft.ir`. Every other host is refused before sending.
  - The search is available only to staff, and the results are marked `test_inventory`.
- **live:**
  - Every airline in `NIRA_AIRLINES` that has credentials, over https only.
  - `A1` and the test host are refused.
  - Airlines are asked in parallel (6 at a time, 25 s overall).
  - An airline that fails is left out with its reason. If they all fail, the answer is `unavailable/provider_error`; we never return an empty "success" or an invented result.

**Security**
- `OfficeUser`/`OfficePass` travel in the query string. This is how NRS works.
- No URL or query string is written anywhere:
  - httpx's own request log line is rewritten as `?[redacted]`.
  - Errors are raised outside the `except` block, so the httpx exception, which holds the URL, is not attached as `__cause__`/`__context__`.
  - Any text the airline echoes back is redacted.
- Timeouts: connect 5 s, read 20 s.
- Only reads are retried (twice, on network error, timeout or 503). ReservJS, ETIssueJS, CancelPNR, CancelSeat and ETRefund are sent exactly once; a lost answer is `ambiguous` and must be checked with NRSRT/NRSETR.
- The ETR `Comission` exists only inside `TicketRecord`; `public()` does not include it.

**What is exposed and what is not**
- Search, status and the single-airline console are exposed.
- The client implements and tests reserve (with a flight-time re-check), issue, RT, ETR, cancel PNR/seat, penalty and PenaltyNow, refund (Fare/KU/LP/Penalty from ETR + Penalty) and CRD. These have **no HTTP endpoint yet**: as with Mahan, ticket issue is disabled until the owner approves it in writing and payment, idempotency and reconciliation are wired.

**How to test one airline (on the server, by the owner or DevOps)**
1. Set `NIRA_MODE=sandbox`, `NIRA_AIRLINES=A1`, `NIRA_A1_USER`, `NIRA_A1_PASS` in the server env. Make sure the api container actually receives these names (env_file / compose), then deploy with the normal script.
2. Log in as staff → «آزمون اتصال نیرا» (`/admin/suppliers/nira`) → pick the airline, route (city codes such as THR/MHD), date → «جست‌وجو». Each click sends exactly one request.
3. For a real airline: `NIRA_MODE=live`, `NIRA_AIRLINES=VR` (for example), `NIRA_VR_USER/PASS`, and preferably `NIRA_VR_ROUTES`.

**Caveats**
- `Sales Channel not Allowed` means the user is not the airline's web-service user (the one ending in WS). Ask the airline's commercial department for the WS user.
- `Access Denied`/`SIGN!` with correct credentials usually means IP whitelisting. The server's outbound IP `188.121.123.218` must be whitelisted by each airline.
- **Not verified against a real NRS host** (there were no credentials in this environment); the first sandbox call decides:
  - the spelling of the query parameters `Airline` and `Email` (the spec writes them this way; Mahan's NRS was used with `AirLine`/`EMail`) — they are constants `P_AIRLINE`/`P_EMAIL`;
  - the `edtAge` format (sent as age in whole years on the flight day);
  - the space between the first name and the title (`ALI MR`);
  - the `Command` parameter name in NRSCommand;
  - the exact shape of `AirNRSTICKETS`, of the ETR `TAXES` and of the error envelope (the parsers accept several case-insensitive shapes and fail closed on anything else).

## گزارش پیشرفت (۷ آذر ۱۴۰۵)

**انجام شد (فقط کد در شاخه، هنوز روی سایت نیست):**
- اتصال نیرا با کلید `NIRA_MODE` ساخته شد و پیش‌فرض آن خاموش است. در حالت خاموش هیچ درخواستی به هیچ ایرلاینی نمی‌رود و جست‌وجوی سایت مثل قبل کار می‌کند.
- همهٔ متدهای سند در کد پیاده شده‌اند: جست‌وجو، نرخ، رزرو، صدور، بازیابی، ابطال، جریمه، استرداد و اعتبار.
- جست‌وجو و صفحهٔ آزمون کارشناس (`/admin/suppliers/nira`) باز شده‌اند. رزرو و صدور بلیت از سایت هنوز ممکن نیست.
- رمز و نام کاربری ایرلاین در هیچ لاگ، پیام خطا یا پاسخی دیده نمی‌شود و این با آزمون خودکار بررسی شده است.
- ۵۵ آزمون خودکار نوشته شد؛ همه با پاسخ‌های ساختگی و بدون تماس واقعی با ایرلاین اجرا می‌شوند.

**مانده:**
- هیچ تماس واقعی با نیرا یا ایرلاین‌ها انجام نشده، چون رمزی در این محیط نیست. چند نام پارامتر هنوز با سرور واقعی تأیید نشده‌اند (فهرستشان در بخش Caveats بالاست).
- ادغام PR، تنظیم env روی سرور و دیپلوی انجام نشده است.
- رزرو، صدور بلیت و استرداد از سایت به تأیید کتبی مالک و اتصال پرداخت نیاز دارد.

**قدم بعد:**
1. یوزر و رمز وب‌سرویس (WS) تست نیرا (A1) گرفته شود و روی سرور در حالت `sandbox` یک جست‌وجو از صفحهٔ آزمون زده شود.
2. از هر ایرلاین یوزر WS گرفته شود و درخواست whitelist شدن IP سرور (`188.121.123.218`) داده شود.
3. اولین ایرلاین (مثلاً وارش) با `NIRA_<CODE>_ROUTES` در حالت `live` آزمایش شود.
