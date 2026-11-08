# Karen Travel (کارن تراول) — Panel Research: User & Staff Dashboards

Date: 2026-11-08 · Scope: customer panel, supplier/agency (B2B) panel, corporate panel, back-office/ops & finance, UX patterns.
Priority legend for an Iranian OTA at **pilot stage**: **MUST** = launch blocker · **SHOULD** = within first releases · **NICE** = later.

> **Source caveat.** Most Iranian OTA pages (alibaba.ir, flytoday.ir, snapptrip.com, zoomit, kojaro, digiato, cafebazaar) **block automated fetching (robots)**. For those, the links below are pages found by search whose titles/URLs show the feature exists (e.g. a refund guide or club page). The detailed flows described for them come from common Iranian OTA practice, **not** from text I verified, and are marked *(practice)*. Read those pages by hand before you lock the spec. International sources (Booking.com, Airbnb, Navan, Perk/TravelPerk, Concur, AltexSoft, GetYourGuide) were fetched and paraphrased.

---

## 1. Customer panel (پنل کاربری مسافر)

### Evidence from Iranian OTAs
- Alibaba runs a dedicated online-refund guide hub, with a separate guide for villas/accommodation, so refunds are self-service per product type: [راهنمای استرداد – علی‌بابا](https://www.alibaba.ir/refund-guide), [استرداد ویلا و اقامتگاه](https://www.alibaba.ir/help-center/categories/refund-guide/accommodation).
- Installment travel (خرید اقساطی) is a productized feature at Alibaba, with published terms: [مقررات خرید اقساطی](https://www.alibaba.ir/help-center/installment-terms), [سفر اقساطی](https://www.alibaba.ir/installment-travel). Market models vary. AzkiVam/Blu Bank loans need one Sayadi cheque. Safarmarket uses Tara/Digipay credit with a cap. Lastsecond tours are sold in installments through the agency, usually guaranteed by cheque (30% upfront for domestic tours, 50% for foreign): [مهر – از کدام سایت تور اقساطی بخرم](https://www.mehrnews.com/news/6559394/از-کدام-سایت-تور-اقساطی-بخرم).
- Gift/travel cards (سفرکارت) appear at Alibaba and Flytoday. They are redeemed as stored credit in the account: [سفرکارت علی‌بابا](https://www.alibaba.ir/safarcard), [سفرکارت فلای‌تودی](https://www.flytoday.ir/newsroom/newsroom-article-16).
- Flytoday offers a deposit ID (شناسه واریز) for wallet top-up by bank transfer with no gateway limit: [شناسه واریز فلای‌تودی](https://www.flytoday.ir/newsroom/newsroom-article-15). Its tiered customer club gives platinum members credit: [باشگاه فلای‌تودی](https://www.flytoday.ir/club), [Kojaro PR](https://www.kojaro.com/pr/306510-flytoday-customer-club-pr/).
- Snapptrip publishes a step-by-step guide to cancelling domestic hotels from the account: [راهنمای کنسلی هتل داخلی](https://www.snapptrip.com/blog/%d8%b1%d8%a7%d9%87%d9%86%d9%85%d8%a7%db%8c-%da%a9%d9%86%d8%b3%d9%84%db%8c-%d9%87%d8%aa%d9%84-%d8%af%d8%a7%d8%ae%d9%84%db%8c/).
- Flightio cashback is credited to the account: [Zoomit PR](https://www.zoomit.ir/pr/431066-flightio-cash-back-hotel-plane-ticket/).
- **Trust lesson (Flightio):** a customer was charged twice for "failed" purchases, about 38M toman in total. Support kept moving the refund date and never gave a definite one. The reporter compares this with the roughly 72-hour reversal that is normal elsewhere: [تابناک](https://www.tabnak.ir/fa/news/1336721/پرواز-فلایتیو-روی-پول-مسافران-بلیت-نداریم-پول‌تان-را-هم-نمی‌دهیم). → A visible refund/failed-payment tracker with SLA dates is a trust feature, not a nice-to-have.

### Checklist
| Feature | Priority | Notes |
|---|---|---|
| OTP login by mobile (no password), session list & logout-all | **MUST** | Iranian norm *(practice)*. Rate-limit OTP. Optional password/TOTP later |
| Dashboard home: next trip card, open requests, wallet balance | **MUST** | Same idea as Airbnb's "Today" tab ([Airbnb](https://www.airbnb.ie/resources/hosting-homes/a/exploring-your-hosting-tools-738)) |
| My trips / orders (سفرهای من), tabs: upcoming / past / cancelled, filter by product (flight, train, hotel, tour, villa, visa) | **MUST** | One order view across products |
| Order detail: status timeline, passengers, PNR/ticket no., payment breakdown, policy text | **MUST** | |
| Download ticket / voucher PDF, resend via SMS/email | **MUST** | |
| Failed-payment tracker ("money deducted, no ticket"): auto reversal state + date | **MUST** | Flightio lesson above |
| Online refund request (استرداد آنلاین): pick passengers/segments → penalty preview per fare rules → destination (wallet or IBAN/شبا) → confirm | **MUST** | [Alibaba refund hub](https://www.alibaba.ir/refund-guide) *(flow from practice)* |
| Refund tracking: submitted → under review → supplier approved → paid, with ETA and amount | **MUST** | |
| Saved passengers (مسافران): name fa/en, کد ملی with checksum validation, birth date (Jalali), passport no./expiry, gender, nationality (foreign nationals) | **MUST** | National code required for domestic flight/train *(practice)* |
| Wallet (کیف پول): balance, top-up via Zarinpal, transactions ledger, refund-to-wallet, withdraw to شبا | **MUST** | Matches [Flytoday deposit-ID](https://www.flytoday.ir/newsroom/newsroom-article-15) model |
| Profile: name, national code, email, verified شبا/card for refunds | **MUST** | Store the IBAN owner's name and match it to the user |
| Support tickets linked to an order; call-back request | **MUST** | |
| Notifications centre (SMS + in-app): flight changes, delays, refund status | **MUST** | |
| Invoices / receipts per order (رسید، فاکتور رسمی with economic code for companies) | **SHOULD** | Ties to Moadian (see §4) |
| Installments (اقساط) status: plan, due dates, cheque/loan provider | **SHOULD** | [Alibaba installment terms](https://www.alibaba.ir/help-center/installment-terms) |
| Gift card / voucher redemption (سفرکارت), discount codes | **SHOULD** | [Alibaba safarcard](https://www.alibaba.ir/safarcard) |
| Customer club (باشگاه مشتریان): tier, points, cashback history | **SHOULD** | [Flytoday club](https://www.flytoday.ir/club) |
| Referral / invite link | **NICE** | [Alibaba invitation](https://www.alibaba.ir/invitation) |
| Price alerts, saved searches, favourites (hotels/tours) | **NICE** | |
| Travel request (اعلام نیاز سفر): free-form request for a custom tour or group, answered by staff | **NICE** (SHOULD for tour business) | Lead capture for the tour operator side |
| Reviews of completed trips | **NICE** | |

---

## 2. Supplier / agency panel (B2B: contracted agencies, villa owners, hotels, charterers)

### Evidence
- **Booking.com extranet** sections: Property, Rates & Availability (room types, pricing, discounts), Calendar (open/close dates, sync), Reservations, Inbox, Guest Reviews, Analytics/Reports, Payments/invoices, plus listing snooze or termination ([Hostaway guide](https://hostaway.com/blog/how-to-use-the-booking-com-extranet)). Disputes are raised from the reservation statements page ([Booking partner community](https://partner.booking.com/en-gb/payments-commission-and-invoices/extranet)).
- **Booking.com roles:** one Primary account (full access including finance, cannot be edited), Admins (manage users), and Users with granular permissions. Permission areas: Reservations, Rates & Availability, Property details, Performance, Finance, Promotions, Notifications, Programmes, Manage users, Connectivity. A restricted page names the permission it needs ([Booking partner help](https://partnerhelp.booking.com/hc/en-gb/articles/213301525-How-do-I-log-on-to-my-Extranet-?)).
- **Airbnb host:** Today (current/upcoming reservations, private notes), Calendar (pricing, min stay, discounts, block dates), Listings (details, photos, arrival guide), Messages (templates, scheduled messages), Earnings with custom reports, and Insights on ratings ([Airbnb](https://www.airbnb.ie/resources/hosting-homes/a/exploring-your-hosting-tools-738)).
- **GetYourGuide supplier portal:** commission shown per ticket type on the bookings page, a pickup planner that flags issues, bulk cancellation with automatic traveller notice and rebook/refund options, review insights and QR review collection, multi-account switching, and 24/7 chat ([GYG Fall 2025](https://www.getyourguide.supply/fall2025)).
- **Viator:** booking calendar, availability tools, product listings that go through a paid quality review, and a minimum review rating to stay listed ([Bókun on Viator](https://www.bokun.io/?p=544)).
- Iranian tour/charter panels: few public docs. Iranian tour-management SaaS vendors advertise tour CRUD, capacity, and collaborator-agency (آژانس همکار) sales with markups ([Virgool – نرم‌افزار مدیریت تور](https://virgool.io/brocker/%D9%86%D8%B1%D9%85-%D8%A7%D9%81%D8%B2%D8%A7%D8%B1-%D8%A2%D9%86%D9%84%D8%A7%DB%8C%D9%86-%D9%85%D8%AF%DB%8C%D8%B1%DB%8C%D8%AA-%D8%AA%D9%88%D8%B1-%D8%A8%D8%B1%D8%A7%DB%8C-%D8%A2%DA%98%D8%A7%D9%86%D8%B3-%D9%85%D8%B3%D8%A7%D9%81%D8%B1%D8%AA%DB%8C-%D9%84%D9%88%DA%A9%D8%B3%DB%8C%D9%86-%D8%AA%D8%B1%DB%8C%D9%BE-j1sdgjbgq88c), [Kojaro – وب‌سرویس آژانس](https://www.kojaro.com/pr/165373-وب-سرویس-اژانس/)). Lastsecond once banned agencies from advertising on its listings, which shows the OTA controls brand exposure ([عصر ایران](https://www.asriran.com/fa/news/400656/تبلیغ-آژانس-ها-در-last-second-ممنوع-شد)).

### Checklist
| Feature | Priority | Notes |
|---|---|---|
| Supplier onboarding: contract, licence (مجوز بند ب/الف), economic code, شبا, documents; staff approval before going live | **MUST** | Same as Viator's quality gate |
| Tour CRUD: itinerary by day, inclusions/exclusions, hotels per city, transport, photos, cancellation policy, documents required | **MUST** | |
| Departures (تاریخ حرکت) & capacity per departure; room-type pricing (single/double/child with/without bed/infant) | **MUST** | |
| Stop-sale / close departure; capacity auto-decrements on booking | **MUST** | |
| Price & markup: supplier net price vs public price; commission % shown per booking | **MUST** | [GYG commission view](https://www.getyourguide.supply/fall2025) |
| Villa/hotel availability calendar: open/close dates, nightly price, min stay | **MUST** (villa) | [Airbnb calendar](https://www.airbnb.ie/resources/hosting-homes/a/exploring-your-hosting-tools-738) |
| Bookings received: list + detail, confirm/reject for on-request items, SLA timer | **MUST** | |
| Passenger manifest (لیست مسافران) export Excel/PDF per departure, with national code/passport | **MUST** | Needed for hotels, insurance and charter ops |
| Settlements / payouts: per-booking net, balance, settlement cycle, statements, dispute a line | **MUST** | [Booking statements/dispute](https://partner.booking.com/en-gb/payments-commission-and-invoices/extranet) |
| Staff users with permission areas (bookings, pricing, finance, users) | **SHOULD** | [Booking roles](https://partnerhelp.booking.com/hc/en-gb/articles/213301525-How-do-I-log-on-to-my-Extranet-?) |
| Messages with Karen ops (per booking thread) | **SHOULD** | |
| Bulk cancel a departure → auto notify + refund/rebook | **SHOULD** | [GYG bulk cancel](https://www.getyourguide.supply/fall2025) |
| Reviews and replies | **SHOULD** | |
| Reports: sales by tour/departure, occupancy, cancellations | **SHOULD** | |
| Charterer seat blocks for flights (block, release deadline, sold vs remaining) | **SHOULD** (if charter at launch) | *(practice)* |
| Sub-agency (آژانس همکار) B2B booking with credit limit & agency markup | **SHOULD** (B2B distribution) | |
| API/channel-manager connectivity | **NICE** | |
| Promotions (early bird, last-minute) | **NICE** | |

---

## 3. Corporate travel panel (organizational credit)

### Evidence
- **Navan:** policies by role, trip type or cost centre that block overspend; approvals routed by team, travel type or spend threshold; live spend reports and benchmarks; duty of care (live traveller location, location-based restrictions, emergency management); HRIS sync of employees ([Navan for travel managers](https://navan.com/solutions/travel-managers)). With Trip Proposals the traveller submits purpose and needs, the manager approves or denies with one click and must give a reason for a denial, the system shows an AI cost estimate, and notifications go out at each step ([Navan Trip Proposals](https://navan.com/blog/introducing-trip-proposals-for-seamless-approval-flow)).
- **Perk (TravelPerk):** separate policies for air, rail, car, stays and in-trip spend; approvals by hierarchy or cost centre; notification of auto-approved trips; express approval for changes; invoices per booking or consolidated weekly, fortnightly or monthly; finance overview and custom exports; cost centres and labels ([Perk admin guide](https://www.perk.com/guidebook/admin/manage/)).
- **SAP Concur:** pre-trip request approval; Send Back with a mandatory comment; Approve & Forward when the amount exceeds the approver's limit or touches another cost centre; history of past approvals ([Clemson approver guide](https://www.clemson.edu/procurement/concur/benefits-of-concur/approver-guide.html)).

### Checklist
| Feature | Priority | Notes |
|---|---|---|
| Organization profile: legal name, economic code/شناسه ملی, contract, admins | **MUST** | |
| Employees: add/import (Excel), roles (traveller, approver, org admin, finance), deactivate | **MUST** | HRIS sync is NICE |
| Organizational credit (اعتبار سازمانی): limit, used, available, per-cost-centre budget | **MUST** | |
| Travel policy: allowed classes/products, max hotel stars/price, advance-booking rules, out-of-policy flag | **MUST** (simple) | [Perk policies](https://www.perk.com/guidebook/admin/manage/) |
| Approval workflow: request → approver(s) → booked; reject with reason; send back; threshold escalation | **MUST** | [Concur](https://www.clemson.edu/procurement/concur/benefits-of-concur/approver-guide.html), [Navan](https://navan.com/blog/introducing-trip-proposals-for-seamless-approval-flow) |
| Book on behalf (travel arranger/EA) | **MUST** | Common in Iranian orgs *(practice)* |
| Consolidated invoice (monthly), per-booking invoice, statement of account | **MUST** | [Perk invoicing](https://www.perk.com/guidebook/admin/manage/) |
| Reports: spend by employee/cost centre/product, Excel export | **SHOULD** | |
| Cost centres / project labels on bookings | **SHOULD** | |
| Duty of care: who is travelling where today, emergency contact list | **SHOULD** | [Navan](https://navan.com/solutions/travel-managers) |
| Delegation / out-of-office approver | **NICE** | |
| Benchmarks, carbon reporting, Slack/Bale approvals | **NICE** | |

---

## 4. Back-office: operations, CRM, finance (staff panel)

### Evidence
- An OTA back office covers a central booking desk that gathers web, phone and chat bookings in one place; CRM with customer history; supplier connectivity; a ledger with AR/AP; supplier commission and due-date rules; KPI and agent-productivity reports; and role-based permissions over bookings, refunds and supplier communication, with login-activity monitoring ([AltexSoft – OTA back office](https://www.altexsoft.com/blog/travel/managing-an-online-travel-agency-how-back-office-system-of-an-ota-works/)).
- The mid-office handles PNR quality control, triggering ticketing after payment, and documents. The back-office handles invoices (fare, tax, fee, markup, discount), month-end reconciliation, supplier reconciliation that flags mismatches, and expected-vs-received commission tracking ([AltexSoft – mid/back office](https://www.altexsoft.com/blog/mid-office-back-office-systems-in-travel/)). Others add a single queue for manual or automated handling, post-booking changes and refunds, and an audit trail across the booking lifecycle ([Coax](https://coaxsoft.com/blog/mid-and-back-office-software-for-travel-agencies)). Typical automated workflows: intake validation, rule-based markup, supplier confirmation, document generation, change management, ticketing, reconciliation, BI ([TravelBooster](https://www.travelbooster.com/blog_post/mid-office-workflows-travel-agents/)).
- **Iranian e-invoice (سامانه مودیان):** the API needs a username, private key and certificate from intamedia.ir. An invoice has a header (type, number, seller/buyer tax IDs, totals, VAT, settlement method) and lines (service ID, qty, fee, discount, VAT rate). Sending returns a uid and reference number for later status inquiry, and cancellation, corrective and return invoice types exist ([Jooyeshgar/moadian](https://www.github.com/Jooyeshgar/moadian)). Press coverage argues that travel/airline agencies must send e-invoices ([تعادل](https://www.taadolnewspaper.ir/fa/news/343553/چرا-آژانس‌های-هواپیمایی-باید-صورتحساب-الکترونیکی-ارسال-کنند)). *Whether VAT applies to the full price or only the commission/service fee for each product must be confirmed with the group's accountant.*

### Checklist — Operations
| Feature | Priority | Notes |
|---|---|---|
| Unified order search (order no., PNR, mobile, national code, ticket no.) | **MUST** | |
| Customer 360: profile, orders, wallet ledger, tickets, notes, OTP/login history | **MUST** | |
| Ops queues: **failed issuance** (paid, not ticketed), pending supplier confirmation, refund requests, schedule changes, on-request hotel/villa | **MUST** | Each with owner, SLA timer, status |
| Manual actions: re-issue, manual issue with ticket no., cancel, partial refund, wallet credit/debit with reason | **MUST** | Two-person approval above a threshold amount |
| Refund processing: penalty calc, supplier refund received?, pay-out to wallet/شبا, batch payouts | **MUST** | |
| Case/ticket management linked to order, internal notes, templates, SMS send | **MUST** | |
| Supplier management: contracts, commissions, credit/deposit balance with airline/consolidator, contact | **MUST** | |
| Tour/listing moderation (approve supplier content before publish) | **MUST** | |
| Roles & permissions (RBAC) + staff accounts with 2FA | **MUST** | [AltexSoft](https://www.altexsoft.com/blog/travel/managing-an-online-travel-agency-how-back-office-system-of-an-ota-works/) |
| Audit log (who changed what, before/after, IP) — immutable | **MUST** | [Coax](https://coaxsoft.com/blog/mid-and-back-office-software-for-travel-agencies) |
| Markup/pricing rules engine (by route, airline, channel, B2B agency) | **SHOULD** | [TravelBooster](https://www.travelbooster.com/blog_post/mid-office-workflows-travel-agents/) |
| Corporate accounts admin (credit limits, policies) | **SHOULD** | |
| CMS/promotions/discount codes, club rules | **SHOULD** | |
| KPI dashboard: sales, conversion, failed-issue rate, refund backlog, SLA breaches | **SHOULD** | |

### Checklist — Finance
| Feature | Priority | Notes |
|---|---|---|
| Double-entry ledger: customer wallets, org credit, supplier payables, revenue/commission | **MUST** | Never edit balances directly; use adjustment entries only |
| Gateway reconciliation (Zarinpal): match each payment to an order, flag paid-but-unfulfilled and unmatched settlements | **MUST** | Supplier/BSP-style reconciliation per [AltexSoft](https://www.altexsoft.com/blog/mid-office-back-office-systems-in-travel/) |
| Supplier settlements: statements, payable cycles, payouts, disputes | **MUST** | |
| Invoices (customer/corporate) with Jalali dates, economic code | **MUST** | |
| Moadian e-invoice submission + status inquiry + corrective/cancel | **SHOULD** (MUST before scale) | [moadian package](https://www.github.com/Jooyeshgar/moadian) |
| Commission expected-vs-received reconciliation | **SHOULD** | |
| Installment receivables (cheques/loan provider) tracking | **SHOULD** | |
| Export to accounting software (Sepidar/Hamkaran etc.) | **NICE** | |

---

## 5. UX patterns for the panels

- **Navigation.** Desktop staff/supplier panels: a collapsible sidebar grouped by domain, which sits on the **right** in RTL, plus a top bar with global search (order/PNR/mobile). Customer panel: account sidebar on desktop and a **bottom nav with 3–5 destinations** on mobile, e.g. Home, My trips, Wallet, Support, Profile ([Smashing – bottom navigation](https://smashingmagazine.com/2016/11/the-golden-rules-of-mobile-navigation-design), [UX Planet](https://uxplanet.org/perfect-bottom-navigation-for-mobile-app-effabbb98c0f)). Show a supplier's or employee's permitted modules only, and name the missing permission on a blocked page ([Booking.com pattern](https://partnerhelp.booking.com/hc/en-gb/articles/213301525-How-do-I-log-on-to-my-Extranet-?)).
- **"Today" home.** Open on what needs action: next trip, pending approvals, overdue queue items ([Airbnb Today](https://www.airbnb.ie/resources/hosting-homes/a/exploring-your-hosting-tools-738)).
- **Status chips.** Use one shared status vocabulary per entity (order, refund, payment, approval). Give every chip a text label as well as a colour, and keep colours consistent: green confirmed/paid, amber pending/under review, red failed/rejected, grey cancelled/expired.
- **Timelines.** Put a vertical event timeline on order, refund and approval detail pages, with an actor and a Jalali timestamp on each step and the **expected next step plus ETA** at the end. This directly addresses the Flightio-type trust failure ([تابناک](https://www.tabnak.ir/fa/news/1336721/پرواز-فلایتیو-روی-پول-مسافران-بلیت-نداریم-پول‌تان-را-هم-نمی‌دهیم)).
- **Empty/loading/error states.** Use skeletons that match the layout instead of spinners. Empty states should explain why the screen is empty and offer one primary action, e.g. "No trips yet → Search flights" ([SaaS UI – skeletons](https://www.saasui.design/blog/saas-loading-skeleton-ux-patterns), [SAP Fiori empty state](https://www.sap.com/design-system/hcm/mobile-patterns/empty-state/no-item-empty-state/usage)). Error states should keep the user's input and offer retry or support.
- **RTL specifics.** Mirror layout, directional arrows (back/next), progress steppers and breadcrumbs. Do **not** mirror logos, media-playback icons, checkmarks or the order of digits. Flight-route arrows follow reading direction, so origin sits on the right ([Material bidirectionality](https://m1.material.io/usability/bidirectionality.html), [Firefox RTL guidelines](https://firefox-source-docs.mozilla.org/code-quality/coding-style/rtl_guidelines.html), [Adobe Spectrum](https://spectrum.adobe.com/page/bi-directionality)). Isolate LTR fragments (PNR, ticket no., IBAN, passport, emails) with `dir="ltr"`/`<bdi>`. Use Persian digits in UI text and accept both Persian and Latin digits in inputs. Use a Jalali date picker with Gregorian shown for international trips. Prices in toman with thousands separators, saying clearly whether the amount is toman or rial.
- **Tables (staff).** Sticky header, saved filters, column chooser, Excel export, bulk actions; on mobile, collapse rows into cards.
- **Accessibility.** WCAG AA contrast, visible focus, keyboard-operable menus and tables, labels on icon-only buttons, OTP fields with `autocomplete="one-time-code"`, and no status shown by colour alone.
- **Safety UX for money actions.** Show a confirmation summary with amount and destination شبا owner name before refunds, wallet adjustments and payouts. Require a second approver above a threshold. Write every such action to the audit log.

---

### Gaps / next steps
1. Log in to Alibaba, MrBilit, Flytoday, Snapptrip and Lastsecond by hand, screenshot their account menus and refund flows, and confirm the items marked *(practice)*.
2. Confirm with the accountant the VAT base per product for Moadian.
3. Decide whether charter seat blocks and B2B sub-agencies are in pilot scope; this moves several SHOULD items to MUST.
