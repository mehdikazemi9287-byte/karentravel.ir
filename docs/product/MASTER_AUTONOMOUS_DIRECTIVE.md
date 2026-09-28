KARENSEIR — MASTER AUTONOMOUS PRODUCT COMPLETION DIRECTIVE

این دستور، دستور اجرایی اصلی پروژه از این لحظه است.

SOURCE:
 /home/ubuntu/karenseir-current

LIVE:
 http://95.38.184.209

تمام نیازمندی‌ها، تصمیم‌ها و قابلیت‌های قبلی KarenSeir همچنان معتبرند.
هیچ قابلیت قبلی را به دلیل این دستور حذف، ساده یا فراموش نکن.

اما از این لحظه منتظر نباش من تک‌تک ایرادها و قابلیت‌های بدیهی یک سایت
گردشگری را برایت نام ببرم.

ماموریت تو این است:

KARENSEIR را خودت مانند یک محصول واقعی گردشگری بررسی کن،
کمبودهایش را کشف کن،
اولویت‌بندی کن،
پیاده‌سازی کن،
در مرورگر واقعی تست کن،
روی مسیر واقعی Production منتشر کن،
دوباره بررسی کن،
و این چرخه را تا رسیدن به یک محصول بالغ ادامه بده.

==================================================
1. اول سایت را ببین؛ نه کد را
==================================================

ابتدا LIVE PRODUCT را با مرورگر واقعی بررسی کن.

Desktop و Mobile.

مثل یک مشتری واقعی رفتار کن.

همه لینک‌ها، منوها، Tabها، فرم‌ها، CTAها و مسیرهای قابل دسترس را کشف کن.

فقط HTTP 200 چک نکن.

واقعاً کلیک کن.

جستجو کن.
تاریخ عوض کن.
مسافر اضافه کن.
فیلتر کن.
Sort کن.
نتیجه باز کن.
جزئیات باز کن.
رزرو را شروع کن.
Login/Register را امتحان کن.
My Trips را ببین.
Assistant را استفاده کن.
مسیر سازمانی را بررسی کن.
Empty/Error/Loading Stateها را ببین.

خودت Route Inventory بساز.

==================================================
2. معیار تو «یک سایت گردشگری نرمال و بالغ» است
==================================================

برای هر صفحه از خودت بپرس:

اگر این یک OTA / Travel Marketplace واقعی بود،
کاربر اینجا چه انتظاری داشت؟

اگر چیزی بدیهی کم است، منتظر دستور من نباش.

آن را GAP ثبت کن.

KarenSeir را از منظر این کلاس‌های محصول بررسی کن:

OTA
Travel Marketplace
Accommodation Marketplace
Experience Marketplace
Corporate Travel Platform
Trip Management Platform

==================================================
3. Benchmark واقعی انجام بده
==================================================

در حد دسترسی موجود، محصولات مطرح ایران و جهان را بررسی کن.

از جمله:

Alibaba
Jabama
Flightio
SnappTrip
Safarmarket
CheckLine

و نمونه‌های بین‌المللی مناسب مانند:

Booking.com
Expedia
Airbnb
Trip.com
Skyscanner
Google Travel
GetYourGuide
Viator
Klook

برای B2B نیز Corporate Travel Managementهای بالغ را بررسی کن.

هدف COPY نیست.

ظاهر، متن یا طراحی رقبا را کپی نکن.

بررسی کن:

Information Architecture
Discovery
Search
Results
Filters
Comparison
PDP
Booking
Checkout
Post-booking
Account
Trip Management
Support
Corporate Travel
Marketplace patterns

KarenSeir Figma و تصمیم‌های تأییدشده KarenSeir
مرجع هویت و طراحی محصول هستند.

==================================================
4. KarenSeir فقط Landing Page نیست
==================================================

KarenSeir باید یک اکوسیستم Transactional واقعی باشد.

حداقل دامنه‌ها:

Flight
Train
Hotel
Villa / Accommodation
Tour
Car Rental
Restaurant
Restaurant QR
Pool / Sport
Attraction / Experience
Events
Event Halls
Travel Guides
Handicrafts
Tourist Transport

هرکدام را مستقل بررسی کن.

یک فرم Generic را برای همه Verticalها کافی فرض نکن.

==================================================
5. چرخه کامل رزرو را ممیزی کن
==================================================

برای Verticalهای applicable چرخه واقعی باید بتواند تا حد لازم شامل این باشد:

DISCOVER
→ SEARCH
→ AVAILABILITY
→ FILTER
→ SORT
→ COMPARE
→ DETAIL
→ SELECT
→ RECHECK
→ TRAVELER/GUEST
→ RULES
→ HOLD/REQUEST
→ RESERVE
→ CHECKOUT
→ PAYMENT
→ CONFIRMATION
→ ISSUE
→ TICKET/VOUCHER
→ MY TRIPS
→ MODIFY
→ CANCEL
→ REFUND
→ SUPPORT

هر حلقه گمشده را خودت پیدا کن.

Payment را معادل Booking ندان.

Booking را معادل Issuance ندان.

==================================================
6. Flight باید Flight واقعی باشد
==================================================

بررسی و تکمیل کن:

Domestic/International
One-way
Round-trip
Multi-city
Origin/Destination
Airport/City
Dates
Adult/Child/Infant
Cabin
Fare/Class
Airline
Flight Number
Departure/Arrival
Duration
Stops
Baggage
Rules
Refundability
Price Breakdown
Filters
Sorting
Supplier
Availability
Recheck
Price Change
Traveler Data
PNR
Ticket
Cancellation
Refund

از CheckLine به‌عنوان benchmark عمق Transactional و در صورت مجاز بودن
به‌عنوان potential integration source بررسی کن.

اما KarenSeir را به CheckLine tightly couple نکن.

==================================================
7. Accommodation یک Marketplace واقعی است
==================================================

فقط Hotel Search نساز.

پشتیبانی محصولی مناسب برای:

Hotel
Villa
Apartment
Suite
Ecolodge
Cabin
Traditional Stay
Pool Property
Nature/Forest
Beach
و سایر inventoryهای واقعی

بررسی کن:

Destination Discovery
Property Types
Popular Cities
Seasonal Discovery
Map where applicable
Filters
Sorting
Gallery
Property Detail
Amenities
Capacity
Rooms/Beds
Rules
Check-in/out
Availability Calendar
Pricing
Fees
Cancellation
Instant Booking
Request to Book
Reviews only if real
Supplier/Host Operations

Jabama فقط benchmark عمق Marketplace است، نه قالب طراحی.

==================================================
8. Discovery Engine را جدی بگیر
==================================================

کاربر همیشه نمی‌داند دقیقاً چه می‌خواهد.

Homepage و صفحات Category باید بتوانند سفر را کشف‌پذیر کنند:

Popular Destinations
Weekend Trips
Seasonal Travel
Travel Ideas
Accommodation Discovery
Experiences
Tours
Nearby/Related services where legitimate
Destination Pages
Saved/Recent Search where appropriate
Cross-sell

Homepage نباید فقط Hero + Search + چند کارت باشد.

==================================================
9. Multi-Service Trip
==================================================

KarenSeir باید «سفر» بفروشد، نه فقط Product Tab.

مثال:

Flight
+ Hotel
+ Transfer
+ Restaurant
+ Experience
+ Event
+ Return

باید بتوانند در یک Trip جمع شوند.

بررسی/تکمیل کن:

Trip Builder
Trip Basket
Independent Reservations
Recheck
Inventory Expiry
Price Change
Alternative
Cross-sell
Unified Itinerary
Unified Support

==================================================
10. My Trips هسته محصول است
==================================================

تکمیل کن:

Upcoming
Active
Completed
Cancelled

و در Trip Detail:

Reservations
Travelers
Tickets
Vouchers
Documents
Payments
Timeline
Support
Required Actions
Cancellation/Refund
Assistant

==================================================
11. Trip Operations Center
==================================================

تغییرات سفر باید First-Class Data باشند.

نمونه:

Flight changed
Flight cancelled
Voucher issued
Hotel changed
Payment changed
Refund changed
Pickup changed
Document required
Supplier problem

ثبت کن:

old value
new value
source
time
affected reservation
required action
notification

==================================================
12. «چه چیزی در سفر من تغییر کرده؟»
==================================================

این یک Notification ساده نیست.

کاربر باید بفهمد:

چه چیزی تغییر کرد؟
چه زمانی؟
چه چیزی تحت تأثیر است؟
چه کاری باید انجام دهد؟
چه گزینه‌هایی دارد؟

==================================================
13. AI Travel Assistant
==================================================

Assistant نباید Chat Widget تزئینی باشد.

خودت آن را با Promptهای واقعی تست کن.

مثلاً:

«آخر هفته کجا بریم؟»

«برای ۴ نفر شمال ویلای استخردار می‌خواهم.»

«دو نفر تهران مشهد، پنجشنبه تا شنبه، پرواز صبح و هتل نزدیک حرم.»

«در سفر من چه چیزی تغییر کرده؟»

«این رزرو قابل استرداد است؟»

Assistant باید بتواند در حد داده و اختیار واقعی:

Discover
Search
Filter
Compare
Budget
Build Trip
Explain Rules
Collect Missing Data
Handoff to Booking
Manage Existing Trip
Explain Changes
Support Cancellation
Escalate to Human

هیچ Price، Availability، Booking یا Refund را جعل نکند.

==================================================
14. Human Support
==================================================

AI و Human Support را یکی نکن.

Case Management و Human Escalation واقعی داشته باش.

==================================================
15. Enterprise / B2B / B2B2C
==================================================

این بخش فقط «اعتبار سازمانی» نیست.

بررسی و تکمیل کن:

Business Travel
Mission
Employee Welfare
Project Accommodation
Workforce Accommodation
New Employee Relocation
Team Building
Incentive Travel
Organizational Guests
Group Travel
Organizational Events
Travel Desk

ساختار:

Organization
→ Subsidiary
→ Branch
→ Department
→ Cost Center
→ Project
→ Employee/Traveler

==================================================
16. Policy & Approval
==================================================

Travel Policy Engine و Approval Engine را کامل کن.

Self-Service و Travel Desk Booking هر دو.

Request lifecycle:

REQUEST
→ POLICY
→ APPROVAL
→ SEARCH/RFQ
→ RESERVATION
→ FUNDING
→ BOOKING
→ TRIP
→ SETTLEMENT

==================================================
17. RFQ
==================================================

برای خدمات غیر Instant Bookable:

RFQ
→ Suppliers
→ Quotes
→ Comparison
→ Revision
→ Selection
→ Approval
→ Proforma
→ Order/Contract
→ Payment/Credit
→ Fulfillment
→ Settlement

به‌خصوص:

Group Travel
Events
Halls
Large Accommodation
Transport
Custom Tours
Team Building

==================================================
18. Finance / Credit
==================================================

همه این مفاهیم را یکی نکن:

Wallet
Organization Credit
Employee Benefit
Prepaid
Postpaid
Installment
Cheque
Bank Transfer
Online Payment
Deferred Settlement
Salary Deduction where configured
Split Funding

Financial truth باید Server-Side باشد.

==================================================
19. Ledger / Reconciliation
==================================================

Reservation
Order
Payment
Credit
Ledger
Refund
Invoice/Statement
Supplier Payable
Organization Receivable
Settlement

را از نظر Domain درست تفکیک کن.

Idempotency
Concurrency Protection
Audit Trail
Reconciliation

الزامی‌اند.

مواردی مثل:

PAID_NOT_BOOKED
BOOKED_PAYMENT_UNKNOWN
CREDIT_RESERVED_BOOKING_EXPIRED
REFUND_MISMATCH

باید قابل کشف و عملیات باشند.

==================================================
20. Gift / Benefit / Travel Credit
==================================================

فقط Gift Card Page نساز.

زیرساخت:

Gift
Travel Credit
Employee Benefit
Corporate Campaign
Bulk Distribution
Eligibility
Validity
Service Restrictions
Partial Usage where allowed
Wallet/Ledger
Secure Redemption
Reporting

را بررسی و تکمیل کن.

==================================================
21. Panels
==================================================

به‌صورت واقعی بررسی کن:

Customer
Organization
Supplier
Agency
Admin
Operations
Finance

وجود Route کافی نیست.

با نقش مربوطه Journey واقعی را تست کن.

==================================================
22. Normal Website Fundamentals
==================================================

خودت چیزهای پایه‌ای که من ممکن است فراموش کرده باشم پیدا کن.

بررسی کن:

Header
Navigation
Footer
Brand
About
Contact
Support
FAQ
Terms
Privacy
Cancellation information
Trust
404
Error states
Loading
Skeleton
Empty states
SEO basics
Accessibility basics
Keyboard
Forms
Validation
Responsive
RTL
Typography
Images
Performance
Broken Links
Dead Buttons
Placeholder Text
Technical Leakage

==================================================
23. Fake Completion Hunt
==================================================

عمداً دنبال اینها بگرد:

Dead button
Placeholder
Mock shown as real
Fake price
Fake rating
Fake availability
Contact-support replacing a missing workflow
Empty page
Generic inappropriate form
API disconnected from UI
UI disconnected from API
Orphan backend feature
Orphan frontend feature
Payment without booking
Booking without issuance

==================================================
24. Design
==================================================

هویت تأییدشده KarenSeir را حفظ کن:

Persian RTL
Vazirmatn
Dark Navy
Turquoise
Modern
Premium
Trustworthy
Iranian

شعار:
«تمام سفر، در یک مسیر»

Beige/Orange/Purple فعلی را بدون تأیید به Design System تبدیل نکن.

طراحی رقبا را کپی نکن.

==================================================
25. خودت Backlog بساز
==================================================

منتظر نباش من بگویم چه چیزی کم است.

یک MASTER GAP MATRIX زنده نگه دار:

AREA
JOURNEY
CURRENT
EXPECTED
FRONTEND
BACKEND
DATA
FIGMA
E2E
EXTERNAL
PRIORITY
NEXT ACTION

اولویت:

P0 = Core journey broken/missing
P1 = Normal mature travel capability
P2 = Important enhancement
P3 = Later sophistication

==================================================
26. بعد از Audit متوقف نشو
==================================================

این مهم‌ترین دستور است:

AUDIT فقط شروع کار است.

پس از کشف GAPها:

PRIORITIZE
→ IMPLEMENT
→ TEST
→ BROWSER REVIEW
→ FIX
→ DEPLOY
→ PUBLIC VERIFY
→ RE-AUDIT

و دوباره همین چرخه.

از من نپرس:
«حالا کدام را انجام بدهم؟»

خودت P0 بعدی را انتخاب کن.

==================================================
27. Visible + Backend با هم
==================================================

دیگر چند Iteration پشت سر هم Backend مخفی نساز در حالی که سایت عمومی
تکان نمی‌خورد.

برای هر Vertical Slice:

DOMAIN
→ API
→ CUSTOMER UI
→ OPERATIONS UI where needed
→ DESKTOP
→ MOBILE
→ E2E
→ DEPLOY
→ PUBLIC VISUAL VERIFICATION

باید با هم جلو بروند.

==================================================
28. Browser Review اجباری است
==================================================

بعد از هر تغییر مهم UI:

Build
→ Desktop Browser
→ Mobile Browser
→ Screenshot
→ Self Review
→ Fix
→ Retest

از خودت بپرس:

«اگر هیچ سابقه‌ای از این پروژه نداشتم، آیا این را یک محصول گردشگری بالغ
می‌دانستم؟»

اگر نه، ادامه بده.

==================================================
29. Production Verification
==================================================

مسیر Live قبلاً اثبات شده:

NGINX
→ 127.0.0.1:3000
→ karenseir-frontend-1
→ /home/ubuntu/karenseir-current

این موضوع را دوباره Audit نکن مگر evidence جدیدی از خرابی Deploy وجود داشته باشد.

بعد از هر Release باید تغییر را روی:

http://95.38.184.209

واقعاً ببینی.

Healthy container یا HTTP 200 جای این بررسی را نمی‌گیرد.

==================================================
30. Existing Work را دور نریز
==================================================

تمام کارهای قبلی باقی می‌مانند.

از جمله package/commitهای سازمانی و قابلیت‌های ساخته‌شده.

کد سالم را دوباره از صفر نساز.

قبل از Implementation بررسی کن چه چیزی وجود دارد و آن را تکمیل/متصل کن.

==================================================
31. External Integrations
==================================================

این موارد همچنان لازم‌اند:

DNS/TLS
Real Supplier
ZarinPal
Kavenegar

اما EXTERNAL_BLOCKED بهانه توقف توسعه داخلی نیست.

برای integrationهای unavailable از Adapter/Test path صادقانه استفاده کن.

هیچ داده ساختگی را Production inventory معرفی نکن.

==================================================
32. Safety
==================================================

بدون اجازه صریح:

Real Payment نکن.
Real SMS نفرست.
Financial Liability فعال نکن.
Supplier Transaction واقعی ایجاد نکن.
Production destructive action انجام نده.

AGENTS.md را رعایت کن.

Migration/Production actionهایی که طبق آن نیازمند approval هستند باید همان
موقع approval بگیرند.

==================================================
33. Definition of Done
==================================================

اینها DONE نیستند:

HTTP 200
Container Healthy
API exists
Migration PASS
Unit Test PASS
Route exists
Button renders
Mock E2E alone

DONE یعنی Journey مربوطه واقعاً کار کند.

معیار نهایی:

یک کاربر عادی بدون اطلاع از تاریخچه پروژه KarenSeir را باز کند.

آیا با یک Travel Marketplace / Booking Platform واقعی، کامل، قابل فهم و
قابل اعتماد روبه‌رو می‌شود؟

اگر نه:

کار تمام نشده است.

==================================================
34. EXECUTION ORDER
==================================================

همین الان شروع کن.

اول:

LIVE PRODUCT AUDIT

سپس فوراً P0ها را اجرا کن.

اولویت عملی اولیه:

1. Homepage / Navigation / Discovery / Search / AI
2. Flight
3. Hotel + Accommodation Marketplace
4. Train + Tour
5. Experiences / Restaurant / Leisure / Events
6. Booking / Checkout
7. My Trips / Timeline / Operations
8. Enterprise customer journeys
9. Finance / Gift / Credit
10. Remaining P1/P2 gaps

اما اگر Audit یک P0 جدی‌تر کشف کرد، ترتیب را خودت اصلاح کن.

==================================================
35. REPORTING
==================================================

گزارش‌های طولانی عملیاتی نده.

فقط Delta:

CURRENT_SLICE:
DISCOVERED:
IMPLEMENTED:
PUBLIC_ROUTES_CHANGED:
DESKTOP:
MOBILE:
E2E:
PUBLIC_DEPLOY_VERIFIED:
REMAINING_P0:
EXTERNAL_BLOCKERS:
NEXT_SLICE:

سپس بدون انتظار برای پاسخ من، کار قابل‌اجرا را ادامه بده.

==================================================
FINAL COMMAND
==================================================

DO NOT WAIT FOR THE USER TO DESIGN KARENSEIR FOR YOU.

Inspect the product.
Understand the travel domain.
Benchmark mature products.
Find what is missing.
Implement it.
Use the browser.
Critique your own implementation.
Deploy it.
Verify the public product.
Repeat.

Continue autonomously until only genuinely external, policy-dependent,
approval-required or high-risk actions remain.