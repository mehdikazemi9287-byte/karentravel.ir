# Figma map — Panels / P3 Settlement + Charter ops + P1 rest (کارن تراول)

- File: https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir
- Page: `Panels / P3 Settlement+Charter ops+P1 rest` (node `243:2`) — https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=243-2
- README note frame on the page: `243:3`.
- Built 2026-11-12 (۲۱ آبان ۱۴۰۵). Desktop 1440 at x=0, mobile 390 at x=1560 on the same row (same convention as P1/P2).
- Everything is sample data («نمونه» MockLabel banner on every frame). Persian RTL, Persian digits, Jalali dates, amounts in rial. Agencies are «آژانس نمونهٔ ۱…۵», flight `KS-9001` / block `CB-1405-0031` are invented sample codes.
- Library instances used: Sidebar, TopBar, BottomNav, StatusChip, Timeline/Step, MockLabel, Button, JalaliDateField, MoneyBreakdown (View=finance), ConfirmMoney (Threshold=below); tokens `Panels / pn tokens`; text styles `Panels v2/*`. No library component was added or changed.
- Preview PNGs: `docs/product/panels/figma-previews/p3/` (desktop ≈900 px wide, mobile ≈250–360 px wide, 128-colour quantised — use Figma for detail).

## Shared rules shown in these frames (for the code agent)

- **Settlement formula** (both agency models): `net = gross_sales − refunds_credited_back − commission − VAT(10%) on commission only`. VAT is never applied to sales or refund amounts. Refund lines reverse commission and its VAT pro-rata (`KR-1DS8N`: 32,000,000 sale, −28,800,000 refund → commission 256,000 + VAT 25,600 on the retained 3,200,000).
- **Direction**: buyer agency (sells our inventory on credit) → «بدهی آژانس / دریافتنی از آژانس»; seller agency (own inventory) → «پرداختنی به آژانس / طلب شما». Finance list shows a «جهت» column; agency side shows it in KPI/summary wording.
- **Settlement status** → StatusChip tone (label overridden): `draft` «پیش‌نویس» neutral(`closed`) · `issued` «منتظر تأیید آژانس / منتظر تأیید شما» warn(`under_review`) · `accepted` «منتظر پرداخت / تأییدشده · منتظر پرداخت» info(`submitted`) · `disputed` «مورد اعتراض» bad(`rejected`) · `settled` «تسویه‌شده» ok(`approved`). Drafts are hidden from agencies.
- **Status stepper** (desktop): pill row `پیش‌نویس ← صادرشده ← تأیید آژانس یا اعتراض ← تسویه‌شده`; done = ok-soft with ✓, current = action fill, disputed = bad-soft, next = dashed outline. Mobile replaces it with a one-line note «گام ۳ از ۴ …».
- **Agency acceptance deadline**: 5 working days after issue, then implicit acceptance — shown as pending owner decision (OQ-O6).
- **Dispute status**: open → waiting_finance («منتظر مالی») → resolved (accept with adjustment / reject with reason) → agency re-accepts corrected statement → payment. SLA 2 working days.
- **Refund for agency bookings** defaults to «بازگشت به اعتبار آژانس»; IBAN to agency only with reason + second approver; customer wallet/card disabled for agency bookings. Commission/VAT reversal affects the period settlement, not the credit amount.
- **Charter change**: >3 h change ⇒ passenger may choose accept or full refund without penalty (sample rule from the block policy); applying a change/cancel needs a second approver; agencies are notified (panel + SMS to agency manager; email after integration). Passenger notification is the agency’s job for B2B bookings.

## Priority 1 frames (22)

| Frame | Node | URL | Preview |
|---|---|---|---|
| PNL/agency/AG-17-settlements-list/1440 | 244:120 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=244-120 | p3/AG-17-settlements-list-1440.png |
| PNL/agency/AG-17-settlements-list/390 | 244:516 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=244-516 | p3/AG-17-settlements-list-390.png |
| PNL/agency/AG-17-settlement-detail-v2/1440 | 245:120 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=245-120 | p3/AG-17-settlement-detail-1440.png |
| PNL/agency/AG-17-settlement-detail-v2/390 | 245:595 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=245-595 | p3/AG-17-settlement-detail-390.png |
| PNL/finance/FIN-05-settlements-list/1440 | 246:304 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=246-304 | p3/FIN-05-settlements-list-1440.png |
| PNL/finance/FIN-05-settlements-list/390 | 246:795 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=246-795 | p3/FIN-05-settlements-list-390.png |
| PNL/finance/FIN-05-settlement-detail/1440 | 246:1144 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=246-1144 | p3/FIN-05-settlement-detail-1440.png |
| PNL/finance/FIN-05-settlement-detail/390 | 246:1637 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=246-1637 | p3/FIN-05-settlement-detail-390.png |
| PNL/agency/AG-18a-dispute-open/1440 | 247:578 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=247-578 | p3/AG-18a-dispute-open-1440.png |
| PNL/agency/AG-18a-dispute-open/390 | 247:945 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=247-945 | p3/AG-18a-dispute-open-390.png |
| PNL/finance/FIN-08-dispute-resolve/1440 | 247:1236 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=247-1236 | p3/FIN-08-dispute-resolve-1440.png |
| PNL/finance/FIN-08-dispute-resolve/390 | 247:1662 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=247-1662 | p3/FIN-08-dispute-resolve-390.png |
| PNL/finance/FIN-02c-refund-to-agency-credit/1440 | 248:913 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=248-913 | p3/FIN-02c-refund-to-agency-credit-1440.png |
| PNL/finance/FIN-02c-refund-to-agency-credit/390 | 248:1345 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=248-1345 | p3/FIN-02c-refund-to-agency-credit-390.png |
| PNL/agency/AG-15b-credit-ledger-refund/1440 | 248:1635 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=248-1635 | p3/AG-15b-credit-ledger-refund-1440.png |
| PNL/agency/AG-15b-credit-ledger-refund/390 | 248:2054 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=248-2054 | p3/AG-15b-credit-ledger-refund-390.png |
| PNL/ops/OPS-CH-05-charter-schedule-change/1440 | 249:1288 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=249-1288 | p3/OPS-CH-05-charter-schedule-change-1440.png |
| PNL/ops/OPS-CH-05-charter-schedule-change/390 | 249:1754 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=249-1754 | p3/OPS-CH-05-charter-schedule-change-390.png |
| PNL/ops/OPS-CH-05b-charter-cancel/1440 | 250:1427 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=250-1427 | p3/OPS-CH-05b-charter-cancel-1440.png |
| PNL/ops/OPS-CH-05b-charter-cancel/390 | 250:1865 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=250-1865 | p3/OPS-CH-05b-charter-cancel-390.png |
| PNL/agency/AG-CH-06-schedule-change-notice/1440 | 250:2222 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=250-2222 | p3/AG-CH-06-schedule-change-notice-1440.png |
| PNL/agency/AG-CH-06-schedule-change-notice/390 | 250:2612 | https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=250-2612 | p3/AG-CH-06-schedule-change-notice-390.png |

## Notes per screen

### a. Settlement — agency side
- **AG-17 list** (`/agency/settlements`): KPI tiles (awaiting your acceptance + deadline, current net debt, open disputes, settled in 90 d); filter pills (همه / منتظر تأیید شما / مورد اعتراض / تأییدشده / تسویه‌شده) + Jalali range; table columns: شمارهٔ صورت, دوره, فروش ناخالص, استرداد به اعتبار, کمیسیون + VAT, بدهی خالص, وضعیت, اقدام. Row states: issued (highlighted, primary «بررسی و تأیید»), disputed (dispute id), accepted (awaiting payment), settled (bank tracking ref). Mobile = card list. Info note with the formula; drafts hidden.
- **AG-17 detail v2** (`/agency/settlements/[id]`, state = issued): header + chip, status stepper, deadline note (implicit acceptance pending OQ-O6), summary card (gross, refunds credited back, net sales, commission 8 %, VAT 10 % on commission only, dispute adjustments, net debt highlighted), two-sided timeline (draft auto-created → issued by finance → agency accept/dispute [current] → payment with bank ref [next, ETA] → settled + commission invoice to Moadian queue), line table with row checkbox + per-row «اعتراض» (columns: کد رزرو, تاریخ, نوع, مبلغ فروش, استرداد, کمیسیون ۸٪, VAT کمیسیون, خالص ردیف), primary «تأیید صورت تسویه», ghost «ثبت اعتراض برای ردیف انتخاب‌شده». Mobile sticky bar: اعتراض / تأیید صورت.
- Sample numbers: ST-1405-AG-0024 gross 1,200,000,000 − refunds 90,000,000 = 1,110,000,000; commission 88,800,000; VAT 8,880,000; net 1,012,320,000.

### a. Settlement — staff (finance) side
- **FIN-05 list** (`/finance/settlements/agencies`): primary «اجرای دورهٔ تسویه»; KPIs per status (draft / awaiting agency / disputed / accepted awaiting payment + sum); pills incl. پیش‌نویس; search; table: شمارهٔ صورت, آژانس, دوره, خالص, جهت (دریافتنی از آژانس / پرداختنی به آژانس), وضعیت, مهلت/مرجع, اقدام (صدور / مشاهده / رسیدگی / ثبت پرداخت). Rules note: issue needs `settlement:manage`; payment above maker-checker threshold (AD-06) needs second approver; disputed statements cannot be paid.
- **FIN-05 detail** (`/finance/settlements/[id]`, state = disputed): stepper with disputed branch (پیش‌نویس ✓ ← صادرشده ✓ ← مورد اعتراض ← حل اختلاف [current] ← تأیید آژانس ← تسویه‌شده); finance summary incl. «تعدیل در انتظار حل» and «خالص در صورت پذیرش کامل»; finance actions card: issued info, open dispute + «رسیدگی به اختلاف», «صدور اصلاحیه», payment/receipt form (bank tracking code, amount) **disabled with reason**; line table (finance view) with the disputed row highlighted; «سوابق (audit)» link.
- Sample numbers: ST-1405-AG-0023 gross 980,000,000 − refunds 40,000,000 = 940,000,000; commission 73,400,000 (line KR-5M2Q8T missing); VAT 7,340,000; issued net 859,260,000; after accepted dispute 857,280,000.

### b. Dispute
- **AG-18a dispute open** (agency, on a settlement line): context card of the line (code, date, type, net sale, commission/VAT recorded, line net; cap = line net); form: category (select), amount claimed (focus state, words + max hint), expected effect, description (min 20 chars), attachment dropzone **placeholder** with a sample file row (real upload after file storage integration), post-submit info, primary «ثبت اعتراض»; «مسیر پرونده» timeline (submit [current] → finance review SLA 2 wd → decision → agency accepts corrected statement).
- **FIN-08 dispute resolve** (staff): header chips «منتظر مالی» + «مهلت پاسخ: ۱ روز»; claim card (category, amount, line figures, quoted description, attachment «مشاهده», system check: contract rate 8 % ⇒ expected 1,800,000 + VAT 180,000 = 1,980,000); timeline incl. finance message and agency reply; decision card: radio «پذیرش با تعدیل» (adjustment amount, current net → adjustment → net after correction) / «رد با دلیل» (reason field), note to agency, maker-checker note, primary «ثبت تصمیم و صدور اصلاحیه», ghost «درخواست اطلاعات بیشتر».

### c. Refund to agency credit
- **FIN-02c** (`/finance/refunds/[id]` variant): destination radios — «بازگشت به اعتبار آژانس» (selected) / «واریز به شبای آژانس» (disabled: reason + second approver) / «کیف پول یا کارت مسافر» (disabled for agency bookings); **MoneyBreakdown (View=finance, overridden)**: paid from credit 32,000,000, cancellation penalty 10 % −3,200,000, refundable 28,800,000, method, free credit before/after (158,400,000 → 187,200,000), section «اثر در تسویهٔ دوره»: commission reversal −2,304,000, VAT reversal −230,400, remaining commission on penalty 256,000 + 25,600; **ConfirmMoney (Threshold=below, overridden)**: amount + words, destination «اعتبار آژانس نمونهٔ ۱», ledger type `REFUND_TO_AGENCY_CREDIT`, reason, checkbox, Idempotency-Key, «تأیید و ثبت در اعتبار».
- **AG-15b credit ledger** (`/agency/credit`): KPIs (limit 500,000,000 / used 312,800,000 / free 187,200,000 / credit-backs this period); success note for the new credit-back; ledger table (تاریخ, نوع chip, شرح, مرجع, برداشت, برگشت, مانده آزاد) with the credit-back row highlighted (+28,800,000, ref SR-1405-00512 · KR-1DS8N); row detail card (booking amount, penalty, credited amount, settlement effect on commission/VAT, ledger doc id).

### d. Charter schedule change / cancel
- **OPS-CH-05 schedule change** (ops, on a charter block): tabs تغییر زمان یا تاریخ / لغو پرواز; old → new time boxes + delay chip; JalaliDateField (focus) + departure/arrival time fields; reason select; text for agencies; agency response deadline (implicit acceptance after deadline = proposal, owner decision). Side: consequence card (passenger choice; max credit-back 992,000,000; max commission+VAT reversal 87,296,000; no penalty) and notification preview (channels chips + sample message). Impact card: KPIs (3 agencies, 45 allocated seats/14 free, 26 bookings, 31 passengers) + per-agency allocation table (quota, affected bookings, passengers, free seats, system action). Actions: «ارسال برای تأیید نفر دوم» / «ذخیرهٔ پیش‌نویس».
- **OPS-CH-05b cancel**: irreversible warning; reason + text; radio no-alternative / offer alternative flight; money impact card (bookings/passengers, penalty 0, commission+VAT reversal −87,296,000, total credit-back 992,000,000, maker-checker note, danger «ارسال لغو برای تأیید نفر دوم»); per-agency table (bookings, passengers, credit-back, commission+VAT reversal, notification chip, total row) + notification preview.
- **AG-CH-06 agency notice** (`/agency/inventory/flights/[id]` or today card target): notice card (old → new, deadline, affected 12 bookings / 14 pax, answered 2/12, consequence note, «پذیرش برای ۱۰ رزرو باقی‌مانده», «دانلود فهرست مسافران»); affected bookings table with masked passenger names, pax count, amount, response chip (پذیرفته / درخواست استرداد / منتظر پاسخ) and per-row «پذیرش» / «درخواست استرداد».
- Sample: 26 Aban 1405 = 2026-11-17 (Gregorian helper on the date field).

## Known limitations (P1 set)
- Ops Sidebar has no charter/inventory item: OPS-CH frames relabel `nav:tours` to «موجودی و چارتر». Finance dispute frames use the «آژانس‌ها» item (no «اختلاف‌ها» item). Recommend adding these items + an `Area=agency` Sidebar variant to the library.
- StatusChip has no settlement/dispute statuses; labels are overridden on tone variants (mapping above). Recommend adding `settle_*` / `dispute_*` variants.
- Mobile ops/finance frames reuse P1/P2 mobile shells; the ops mobile sticky bar was added locally. Loading/empty/error variants are not drawn for P3.
- A few mobile pill rows clip the last pill at 390 px (AG-CH-06) — in code use horizontal scroll for pills.
