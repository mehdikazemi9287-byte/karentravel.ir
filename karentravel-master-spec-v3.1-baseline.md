# Karen Travel — Master Platform Specification
## نسخه ۳.۱ (Baseline) — شهریور ۱۴۰۵

---

# هویت پروژه

| فیلد | مقدار |
|------|-------|
| نام پلتفرم | **Karen Travel** |
| دامنه اصلی | **karentravel.ir** |
| هویت حقوقی پلتفرم | مستقل — کدبیس، دامنه، دیتابیس و Deployment مستقل |
| هسته مجوزی و تجاری | **تاژبان گشت پارس** — Licensed/Commercial Parent |
| مالکیت داده | هلدینگ |

---

# اصل بنیادین: Spec ≠ Implementation

> هیچ Agent، توسعه‌دهنده یا سیستم خودکاری حق ندارد صرفاً به دلیل وجود یک Feature در این Master Spec، گزارش دهد که آن Feature ساخته شده است.

وضعیت هر قابلیت باید با شواهد واقعی سرور یکی از مقادیر زیر باشد:

| وضعیت | معنی |
|--------|------|
| **DONE** | کاملاً پیاده‌سازی، تست و فعال در Production |
| **PARTIAL** | بخشی پیاده شده، بخشی باقی‌مانده |
| **MOCK** | داده آزمایشی/جعلی — واقعی نیست |
| **DISCONNECTED** | کد وجود دارد اما به Supplier/Service واقعی متصل نیست |
| **NOT_STARTED** | هنوز شروع نشده |
| **BLOCKED** | مسدود شده به دلیل وابستگی خارجی |

**این وضعیت‌ها در سند جداگانه «Implementation Status Matrix» نگهداری می‌شوند، نه در این Spec.**

---

# ساختار اکوسیستم — تفکیک ۷ بازیگر

| بازیگر | تعریف | مثال |
|--------|-------|------|
| **Licensed Entity** | شخصیت حقوقی دارنده مجوز فعالیت گردشگری | تاژبان گشت پارس |
| **Platform** | سامانه نرم‌افزاری مستقل (کدبیس + دیتابیس + Deployment) | Karen Travel |
| **Brand** | هویت بصری و تجاری که مشتری نهایی می‌بیند | checkline.ir |
| **Tenant** | نمونه منطقی جداشده روی Platform (داده + تنظیمات) | Checkline Tenant, سازمان X |
| **Authorized Sales Channel** | کانال فروش مجاز که تحت مجوز یک Licensed Entity فعالیت می‌کند | چک‌لاین، آژانس Y |
| **Supplier / Commercial Partner** | تأمین‌کننده خدمت، نرخ، موجودی یا فناوری | ایرلاین، هتل، سیتی‌نت |
| **White Label** | حالت خاصی از Tenant + Brand که برند و ظاهر سفارشی دارد | پورتال سفر بانک Z |

### نمودار رابطه‌ای

```
تاژبان گشت پارس ──── Licensed Entity / Commercial Parent
    │                    (مجوزها، قراردادهای مادر، مسئولیت حقوقی)
    │
    ├── Karen Travel ──── Platform (مستقل فنی)
    │       │
    │       ├── checkline.ir ──── Authorized Sales Channel
    │       │       (Brand + Tenant، تحت مجوز تاژبان)
    │       │
    │       ├── پورتال سفر بانک Z ──── White Label
    │       │       (Brand سفارشی + Tenant، تحت مجوز تاژبان)
    │       │
    │       └── آژانس Y ──── B2B Channel
    │               (فروش تحت مجوز خود یا تاژبان)
    │
    └── [کانال‌های آینده]

Commercial & Supply Partners (طبقه جدا):
    ├── Airlines (ایران‌ایر، ماهان، ...)
    ├── Charterers (چارترکنندگان پرواز)
    ├── Consolidators (Biletbank, PKfare, ...)
    ├── Hotel Suppliers / Bedbanks (اسنپ‌تریپ، اقامت۲۴، ...)
    ├── Aggregators (پرتو، مقیم، ...)
    ├── Rail/Transport (رجا، ...)
    ├── Insurance (بیمه سامان، ...)
    ├── Technology/API Providers (سیتی‌نت، ...)
    └── [سایر تأمین‌کنندگان]
```

### قاعده‌ها
- تاژبان = Licensed/Commercial Parent (نه والد کدبیس)
- Karen Travel = Platform فنی مستقل
- checkline.ir = Authorized Sales Channel (می‌تواند با معماری WL اجرا شود — تصمیم باز)
- سیتی‌نت = Technology/API Provider (در طبقه Suppliers)
- هیچ‌یک از موارد بالا از روی نام برند استنباط نمی‌شود — صریحاً تنظیم می‌شود

---

# فهرست دامنه‌ها (۲۳ دامنه + ضمیمه)

1. **License Governance** (جدید)
2. معماری کلی
3. نقش‌ها و RBAC/ABAC
4. Booking Lifecycle & State Machine
5. **تأمین‌کنندگان — Supplier Registry & Hierarchy** (گسترش)
6. **Contract & Rate Engine** (بازطراحی)
7. موتور قیمت‌گذاری
8. مدیریت قرارداد
9. عملیات تور
10. اینونتوری
11. CRM و فروش
12. **مالی — Financial Source of Truth** (گسترش)
13. اسناد و مدارک
14. **پورتال‌ها + White Label Operational Contract** (گسترش)
15. Approval Workflow
16. امنیت و ممیزی
17. گزارش‌دهی و BI
18. CMS و سئو
19. موبایل و PWA
20. **Trip Operations Center + Case Management** (گسترش)
21. **AI Layer + Human/AI Boundary** (گسترش)
22. یکپارچه‌سازی خارجی
23. نقشه دیپلوی

**ضمیمه الزامی: ۳ End-to-End Contract**

---

(محتوای کامل هر دامنه در بدنه سند — ادامه)

---

# ۱. License Governance

## ۱.۱ Domain Model

```
LicensedEntity {
  id: UUID
  legal_name: string           // "تاژبان گشت پارس"
  registration_number: string
  tax_id: string
  licenses: [License]
  master_contracts: [Contract]
  status: enum [ACTIVE, SUSPENDED, EXPIRED]
}

License {
  id: UUID
  entity_id: FK → LicensedEntity
  type: enum [TOURISM_AGENCY, AIRLINE_TICKET_SALES, INSURANCE_AGENT, ENAMAD, MEDIA_LICENSE, OTHER]
  license_number: string
  issuing_authority: string
  issue_date: date
  expiry_date: date
  scope: string
  status: enum [ACTIVE, EXPIRED, SUSPENDED, REVOKED]
  document_url: string
}

SalesChannel {
  id: UUID
  name: string
  type: enum [DIRECT_B2C, WHITE_LABEL, B2B_AGENT, CORPORATE_PORTAL, B2E_PORTAL]
  licensed_entity_id: FK → LicensedEntity
  platform_id: FK → Platform
  brand_config: JSON

  // White Label Operational Contract (تنظیم‌پذیر)
  merchant_of_record: enum [PLATFORM, CHANNEL, LICENSED_ENTITY]
  invoice_issuer: enum [PLATFORM, CHANNEL, LICENSED_ENTITY]
  payment_receiver: enum [PLATFORM, CHANNEL]
  refund_responsible: enum [PLATFORM, CHANNEL]
  support_l1_responsible: enum [PLATFORM, CHANNEL]
  support_l2_responsible: enum [PLATFORM]  // همیشه Platform
  revenue_share_model: JSON
  commission_model: JSON

  status: enum [ACTIVE, SUSPENDED, TERMINATED]
}
```

## ۱.۲ قاعده‌ها
- هر Booking باید `licensed_entity_id` و `sales_channel_id` داشته باشد
- فاکتور رسمی شامل نام و شماره مجوز Licensed Entity
- مجوز Expire شده → فروش جدید از آن کانال مسدود
- Audit: هر تراکنش Traceable به مجوز + کانال + پلتفرم

---

# ۲. معماری کلی

## معماری ۸ لایه‌ای

```
L8: AI Layer (از روز اول)
L7: Presentation (B2C, B2B, Corporate, Supplier, Admin, PWA, API)
L6: Application (Booking, Tour Builder, Trip Ops, CRM, CMS, BI)
L5: Business Logic (Pricing, Commission, Contract, Inventory, Revenue, Tax, Workflow, Refund)
L4: Integration (API Gateway + Supplier Adapters + Payment + Accounting + Notification)
L3: Supplier Layer (Status: UNSELECTED→UNDER_EVALUATION→CONTRACTED→SANDBOX→PRODUCTION→DEPRECATED)
L2: Financial (Ledger, AP/AR, Bank, Reconciliation, Faranegar, Sepidar, Salamaneh, Multi-Currency)
L1: Infrastructure (PostgreSQL, Redis, Elasticsearch, MQ, Monitoring, Backup/DR)
```

## ADR (Architecture Decision Records)

| # | تصمیم | دلیل |
|---|-------|------|
| ADR-001 | Karen Travel = پلتفرم مستقل | مالکیت کامل کد و داده |
| ADR-002 | Multi-Tenant از روز اول | checkline.ir اولین Channel |
| ADR-003 | AI Layer (L8) از روز اول | AI-ready Schema + Events |
| ADR-004 | Supplier Status System | جلوگیری از ساخت کد برای Supplier تعیین‌نشده |
| ADR-005 | Event-Driven برای عملیات حساس | Booking/Payment/Refund از طریق Event |
| ADR-006 | Idempotency روی تمام Write APIs | جلوگیری از تراکنش تکراری |
| ADR-007 | License Governance = Domain مستقل | هر تراکنش Traceable به مجوز |
| ADR-008 | ۷ بازیگر جداگانه | جلوگیری از اشتباه هویتی |
| ADR-009 | Financial Source of Truth = Internal Ledger | نه Frontend، نه Supplier response |
| ADR-010 | Spec ≠ Implementation | وضعیت واقعی جداگانه ردیابی |

---

# ۳. نقش‌ها و RBAC/ABAC

۲۱ نقش عملیاتی (R01–R21) — جدول کامل از V3 حفظ.
مدل RBAC/ABAC + Maker-Checker — از V3 حفظ.

---

# ۴. Booking Lifecycle & State Machine

۱۶ وضعیت (DRF→CNF→CAN→RFD→...) — از V3 حفظ.
Transition Rules — از V3 حفظ.
Refund Flow (12 مرحله + Error States + Idempotency + Concurrency + 8 Acceptance Tests) — از V3 حفظ.

---

# ۵. تأمین‌کنندگان — Supplier Registry & Hierarchy

## ۵.۱ Supplier Taxonomy (۱۶ نوع)

| نوع | تعریف | مثال |
|-----|-------|------|
| Airline | مالک هواپیما + مجوز پرواز | ایران‌ایر، ماهان |
| Charterer | خریدار عمده صندلی | آژانس‌های چارترکننده |
| Consolidator | واسط فروش عمده | Biletbank, PKfare |
| GDS | سیستم توزیع جهانی | Amadeus, Travelport |
| Aggregator | اگریگیتور چند-منبع | پرتو، نیرا |
| Intermediary Software | نرم‌افزار واسط | سپهر، مقیم، راویس |
| OTA Partner | OTA با وب‌سرویس | booking.ir |
| Hotel Direct | هتل مستقیم | هتل‌های قراردادی |
| Bedbank / Hotel Aggregator | واسط عمده هتل | اسنپ‌تریپ، اقامت۲۴ |
| Channel Manager | مدیر کانال هتل | چنلید |
| Rail Operator | اپراتور ریلی | رجا |
| Insurance Provider | بیمه‌گر | بیمه سامان |
| CIP Operator | تشریفات فرودگاه | شرکت‌های CIP |
| Transport Provider | ترانسفر/اتوبوس/خودرو | (UNSELECTED) |
| Experience Provider | گشت و تجربه | (UNSELECTED) |
| Technology/API Provider | فناوری | سیتی‌نت |

## ۵.۲ Supply Chain

یک محصول ممکن است زنجیره چندتأمین‌کننده‌ای داشته باشد:
```
بلیط چارتری: Customer → Platform → مقیم (Intermediary) → آژانس X (Charterer) → ماهان (Airline)
هتل خارجی: Customer → Platform → پرتو (Aggregator) → Hotelbeds (Bedbank) → هتل (Direct)
```

## ۵.۳ Supplier Status System

| وضعیت | اقدام مجاز | Codex/Dev مجاز؟ |
|--------|-----------|----------------|
| UNSELECTED | فقط تحقیق | فقط Interface تعریف |
| UNDER_EVALUATION | تحقیق + POC | فقط Interface |
| CONTRACTED | توسعه Adapter | ✅ بله |
| SANDBOX | تست | ✅ بله |
| PRODUCTION | فروش | ✅ بله |
| DEPRECATED | Sunset | خیر (فقط نگهداری) |

## ۵.۴ فهرست کامل تأمین‌کنندگان

۲۲ پرواز + ۹ هتل + ۶ اشتراکی + قطار/بیمه/CIP — جداول کامل با تعرفه و وضعیت از V3 حفظ.
۷ مورد UNSELECTED (اتوبوس/ترانسفر/خودرو/گشت/رستوران/تفریحی/Event) — از V3 حفظ.
تمام اطلاعات فنی نیازمند تأیید Provider قبل از توسعه.

---

# ۶. Contract & Rate Engine

## ۶.۱ Price Source Tracking

| Source | کد | شرح |
|-------|-----|------|
| Public Fare | PUB | نرخ عمومی منتشرشده |
| Contracted Rate | CTR | نرخ قراردادی |
| Charter Rate | CHR | نرخ چارتر |
| Allotment Rate | ALT | نرخ سهمیه |
| Negotiated Rate | NEG | نرخ مذاکره‌شده |
| Corporate Rate | CRP | نرخ سازمانی |
| Promotion Rate | PRM | نرخ پروموشنی |

## ۶.۲ Price Decomposition

هر قیمت نهایی تجزیه‌پذیر و Audit‌پذیر:

```
PriceBreakdown {
  booking_id: UUID

  // منبع
  source: enum [PUB, CTR, CHR, ALT, NEG, CRP, PRM]
  source_contract_id: UUID | null

  // نرخ پایه
  supplier_net_rate: decimal
  supplier_currency: string
  exchange_rate: decimal
  supplier_net_rate_irr: decimal

  // Markup و کارمزد
  platform_markup: decimal
  platform_markup_type: enum [FIXED, PERCENTAGE]
  service_fee: decimal

  // کمیسیون
  supplier_commission: decimal
  agent_commission: decimal

  // تخفیف
  discount_amount: decimal
  discount_source: enum [PROMO_CODE, LOYALTY, CORPORATE, EARLY_BIRD, BUNDLE, NONE]
  promo_code: string | null

  // مالیات
  vat: decimal
  airport_tax: decimal
  i6_tax: decimal
  red_crescent: decimal
  other_taxes: decimal

  // سهم White Label
  wl_channel_id: UUID | null
  wl_revenue_share: decimal
  wl_commission_type: enum [FIXED, PERCENTAGE, NONE]

  // جمع
  total_selling_price: decimal
  total_cost: decimal
  gross_margin: decimal
  net_margin: decimal

  // Audit
  calculated_at: datetime
  calculated_by: enum [SYSTEM, MANUAL_OVERRIDE]
  override_reason: string | null
  approved_by: UUID | null
}
```

---

# ۷–۱۱. دامنه‌های عملیاتی

Pricing Engine، Contract Lifecycle، Tour Operations، Inventory، CRM — از V3 حفظ.

---

# ۱۲. مالی — Financial Source of Truth

## اصل (ADR-009)

> هیچ وضعیت PAID/REFUNDED/SETTLED صرفاً با پاسخ Frontend یا Supplier قطعی نمی‌شود.
> **مرجع مالی = Internal Ledger + PSP/Bank Reconciliation**

## Ledger Model

```
InternalLedger {
  entry_id: UUID
  booking_id: UUID
  entry_type: enum [SALE, PURCHASE, PAYMENT_IN, PAYMENT_OUT, REFUND, COMMISSION, TAX, ADJUSTMENT]
  debit_account: string
  credit_account: string
  amount: decimal
  currency: string
  exchange_rate: decimal
  source: enum [PSP_CALLBACK, SUPPLIER_API, MANUAL, SYSTEM]
  source_reference: string
  reconciliation_status: enum [UNMATCHED, MATCHED, DISPUTED, RESOLVED]
  reconciled_with: string | null
  reconciled_at: datetime | null
  created_at: datetime
  is_reversible: boolean
}
```

## Reconciliation Types

| نوع | منبع داخلی | منبع خارجی | فرکانس |
|-----|-----------|-----------|---------|
| PSP/Bank | Ledger (PAYMENT_IN) | صورت‌حساب بانک | روزانه |
| Airline | Ledger (PURCHASE) | BSP/ایرلاین | هفتگی |
| Hotel | Ledger (PURCHASE) | صورت‌حساب هتل | ماهانه |
| Supplier | Ledger (PURCHASE) | گزارش تسویه | ماهانه |
| Commission | Ledger (COMMISSION) | سلمانه | ماهانه |

سرفصل‌های حسابداری، اسناد خودکار، Cost Center — از V3 حفظ.

---

# ۱۳. اسناد و مدارک

از V3 حفظ.
اضافه: هر Invoice/Voucher شامل اطلاعات Licensed Entity (نام حقوقی + شماره مجوز + شناسه مالیاتی).

---

# ۱۴. پورتال‌ها + White Label Operational Contract

## White Label Contract (۱۲ بُعد تنظیم‌پذیر)

| بُعد | گزینه‌ها | قابل تنظیم؟ |
|------|---------|------------|
| صاحب برند | کانال / سازمان | ✓ |
| صاحب مجوز | Licensed Entity | ✓ |
| Merchant of Record | Platform / Channel / Licensed Entity | ✓ |
| Seller of Record (فاکتور) | Platform / Channel / Licensed Entity | ✓ |
| صادرکننده فاکتور | Platform / Channel | ✓ |
| صادرکننده واچر | Platform (همیشه) | ✗ |
| دریافت‌کننده وجه | Platform / Channel | ✓ |
| مسئول استرداد | Platform / Channel | ✓ |
| پشتیبانی سطح ۱ | Platform / Channel | ✓ |
| پشتیبانی سطح ۲ | Platform (همیشه) | ✗ |
| Revenue Share | درصدی / ثابت / ترکیبی | ✓ |
| Commission Model | از Markup / کل فروش / ثابت | ✓ |

**قاعده: هیچ‌کدام از روی نام برند استنباط نمی‌شود.**

پورتال‌های B2C, B2B, Corporate, B2E, B2G, Supplier — از V3 حفظ.

---

# ۱۵–۱۹. دامنه‌های ۱۵ تا ۱۹

Approval, Security/Audit, BI, CMS, PWA — از V3 حفظ.

---

# ۲۰. Trip Operations Center + Case Management

## Trip Object — از V3 حفظ.
## Trip Timeline — از V3 حفظ.

## Case Management (جدید)

```
TripCase {
  id: UUID
  trip_id: FK → Trip
  booking_id: FK → Booking | null

  type: enum [
    SCHEDULE_CHANGE, FLIGHT_CANCELLATION, HOTEL_MODIFICATION,
    HOTEL_OVERBOOKING, SUPPLIER_FAILURE, PRICE_DIFFERENCE,
    REISSUE_REQUIRED, REFUND_REQUEST, NO_SHOW, DISRUPTION,
    VISA_ISSUE, CUSTOMER_COMPLAINT, OTHER
  ]

  severity: enum [LOW, MEDIUM, HIGH, CRITICAL]
  status: enum [OPEN, ASSIGNED, IN_PROGRESS, WAITING_SUPPLIER, WAITING_CUSTOMER, RESOLVED, CLOSED]
  assigned_to: UUID | null
  
  notifications_sent: [{
    channel: enum [SMS, EMAIL, PUSH, IN_APP]
    sent_at: datetime
    deep_link: string
    is_ai_generated: boolean
  }]

  resolution_type: enum [REBOOKED, REFUNDED, COMPENSATED, NO_ACTION_NEEDED, CUSTOMER_ACCEPTED, ESCALATED] | null
  resolution_notes: string | null
  resolved_by: UUID | null

  audit_trail: [CaseAuditEntry]
}
```

## Case SLA

| Severity | اختصاص | اولین پاسخ | Resolution |
|----------|--------|-----------|-----------|
| CRITICAL | ≤15 دقیقه | ≤30 دقیقه | ≤4 ساعت |
| HIGH | ≤1 ساعت | ≤2 ساعت | ≤24 ساعت |
| MEDIUM | ≤4 ساعت | ≤8 ساعت | ≤72 ساعت |
| LOW | ≤24 ساعت | ≤48 ساعت | ≤1 هفته |

---

# ۲۱. AI Layer + Human/AI Boundary

## AI Permissions و Red Lines — از V3 حفظ.

## Human/AI Boundary (تکمیل)

### تفکیک پیام (الزامی)
| نوع | در API | نشان بصری |
|-----|--------|----------|
| AI-Generated | source: "AI" | 🤖 + «پیام خودکار» |
| Human | source: "HUMAN" | 👤 + «پشتیبانی» |
| AI-Drafted + Human-Approved | source: "AI_HUMAN_APPROVED" | 🤖→👤 + «بررسی‌شده» |

### Handoff Protocol
```
AI → Human:
  1. AI تشخیص: نیاز به مداخله انسانی
  2. ثبت HandoffEvent {reason, context, conversation_id}
  3. اختصاص به اپراتور
  4. اپراتور Context کامل + AI conversation را می‌بیند
  5. مشتری اعلان: "شما الان با کارشناس صحبت می‌کنید"
  6. Handoff در Audit ثبت
```

### AI ممنوعیت‌های قطعی (بدون تأیید انسانی)
- Refund اجرا کند
- Issue/صدور بلیط کند
- رزرو تغییر دهد
- تعهد مالی ایجاد کند
- تأیید Supplier جعل کند
- قیمت/موجودی جعل کند
- Audit Log تغییر دهد
- بدون برچسب AI پیام بفرستد

---

# ۲۲. یکپارچه‌سازی خارجی — از V3 حفظ.

---

# ۲۳. نقشه دیپلوی — ۵ فاز از V3 حفظ.

---

# ضمیمه الزامی: ۳ End-to-End Contract

## E2E-1: Booking Lifecycle

```
Search → PriceCheck → Reserve → Pay → Issue → Voucher → Change → Cancel → Refund → Reconcile
```

| # | مرحله | Domain(s) | Error Path |
|---|--------|----------|-----------|
| 1 | Search | Booking + Adapters | Timeout → Retry 3x → Partial |
| 2 | PriceCheck | Rate Engine | Price Changed → تأیید مجدد |
| 3 | Reserve | Booking Engine | Reject → Free Seats Check |
| 4 | Pay | Payment + Ledger | PSP Fail → Retry / Alt Gateway |
| 5 | Issue | Booking + Supplier | Fail → CRITICAL Case + Manual |
| 6 | Voucher | Document Engine | — |
| 7 | Change | Booking + Rate + Approval | Not Changeable → Cancel Option |
| 8 | Cancel | Booking + Rate + Approval | Supplier Fail → Case |
| 9 | Refund | Refund + Ledger + PSP | (Refund Flow V3) |
| 10 | Reconcile | Financial Engine | Dispute → Manual |

Transaction Boundaries:
- Steps 1-2: Read-Only
- Step 3: DB Transaction
- Steps 4-5: Saga
- Steps 7-9: Saga
- Step 10: Batch

Acceptance Tests: E2E1-01→E2E1-08 (Happy Path, Price Change, Payment Fail, Issue Fail, Cancel+Refund, Partial Refund, Recon Match, Recon Dispute)

---

## E2E-2: Corporate Credit Lifecycle

```
Corporate Credit → Approval → Booking → Invoice → Payroll Deduction / Settlement
```

| # | مرحله | Domain(s) |
|---|--------|----------|
| 1 | Credit Setup | Contract + License |
| 2 | Employee Request | Booking (B2E Portal) |
| 3 | Travel Policy Check | Rule Engine |
| 4 | Approval | Approval Workflow |
| 5 | Booking (از اعتبار) | Booking + Ledger |
| 6 | Invoice | Document Engine |
| 7 | Payroll Deduction | Payroll Integration |
| 8 | Settlement | Financial Engine |

Acceptance Tests: E2E2-01→E2E2-05 (In-Policy, Out-of-Policy, Credit Exhausted, Payroll Deduction, Monthly Settlement)

---

## E2E-3: Supplier Lifecycle

```
Supplier Contract → Rate/Inventory → Sale → Commission → Settlement
```

| # | مرحله | Domain(s) |
|---|--------|----------|
| 1 | Onboarding | Supplier Registry + Contract |
| 2 | Rate/Inventory | Supplier Portal + Inventory |
| 3 | Sale | Booking + Rate Engine |
| 4 | Commission | Commission Engine (Salamaneh) |
| 5 | Supplier Invoice | Ledger |
| 6 | Settlement | Financial Engine |
| 7 | Reconciliation | Reconciliation |

Acceptance Tests: E2E3-01→E2E3-05 (Happy Path, Rate Change, Overcharge Dispute, Credit Exceeded, Commission Override)

---

# واژه‌نامه

| اصطلاح | توضیح |
|--------|-------|
| Licensed Entity | شخصیت حقوقی دارنده مجوز گردشگری |
| Merchant of Record | فروشنده رسمی تراکنش |
| Seller of Record | نام روی فاکتور |
| Bedbank | واسط عمده‌فروش هتل |
| Channel Manager | مدیر توزیع موجودی هتل |
| Handoff | انتقال AI → انسان |
| DLQ | Dead Letter Queue |
| Saga | الگوی تراکنش توزیع‌شده |
| ADR | Architecture Decision Record |
| TOC | Trip Operations Center |
| RAG | Retrieval-Augmented Generation |
| CSAT / NPS | Customer Satisfaction / Net Promoter Score |

---

# چک‌لیست V3.1

| # | اصلاح | وضعیت |
|---|-------|-------|
| 1 | License Governance = Domain مستقل | ✅ |
| 2 | تفکیک ۷ بازیگر | ✅ |
| 3 | White Label Operational Contract (۱۲ بُعد) | ✅ |
| 4 | Supplier Hierarchy (۱۶ نوع) | ✅ |
| 5 | Contract & Rate Engine + Price Source (۷ منبع) | ✅ |
| 6 | ۳ End-to-End Contract | ✅ |
| 7 | Financial Source of Truth (ADR-009) | ✅ |
| 8 | TOC Case Management (۱۲ نوع + SLA) | ✅ |
| 9 | Human/AI Boundary + Handoff | ✅ |
| 10 | Spec ≠ Implementation (۶ وضعیت) | ✅ |
| +α | CheckLine = Authorized Sales Channel | ✅ |

---

> **نسخه:** ۳.۱ (Baseline)
> **تاریخ:** شهریور ۱۴۰۵
> **مالک:** هلدینگ — پروژه Karen Travel
> **وضعیت:** ✅ Baseline — آماده Freeze
> **مرحله بعدی:** تطبیق Spec با وضعیت واقعی سرور → Implementation Status Matrix → Gap Matrix اجرایی
> **Spec ≠ Implementation**
