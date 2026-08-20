# Domain Map

| Bounded Context | مسئولیت | رویداد/مرز نمونه |
|---|---|---|
| Identity, Tenant, White Label | هویت، عضویت، دامنه و theme | TenantProvisioned |
| Catalog, Inventory, Search | عرضه نرمال‌شده و کشف | OfferUpdated |
| Comparison, Trip Assistant | تصمیم‌یار و ترکیب سفر | ComparisonSaved |
| Booking, Fulfillment | lifecycle رزرو و صدور | BookingConfirmed |
| Corporate Policy, Credit | eligibility، سهمیه، approval | ApprovalRequested |
| Wallet, Payment, Settlement | ledger، پرداخت، refund، تسویه | PaymentCaptured |
| Promotion, Loyalty, CRM | مشوق و ارتباط | PromotionApplied |
| CMS, Reporting, Support | محتوا، گزارش، رسیدگی | CaseOpened |
| Integration Hub, Provider Mgmt | adapter، routing، health | ProviderDegraded |
| Notification, Audit | اطلاع‌رسانی و رخدادهای غیرقابل‌انکار | AuditRecorded |

مرزها از ابتدا در Modular Monolith برقرار می‌شوند تا جداسازی سرویس در آینده براساس بار/مالکیت امکان‌پذیر باشد.
# دامنه‌های افزوده‌شده

- Identity: `OTPChallenge`، `AuthenticationState`، `AuthenticationAudit`، `RefreshTokenSession`
- Finance: `PaymentIntent`، `PaymentEvent`، `RefundRecord`، `Wallet`، `FinancialLedgerEntry`
- Operations: `Trip`، `TripEventRecord`، `NotificationRecord`، `OutboxEvent`
- Commerce: `Offer`، `PriceCheck`، `BookingItem`، `BookingStatusHistory`، `Voucher`
- Corporate: `Department`، `CostCenter`، `EmployeeAssignment`، `ApprovalTemplate` و stepهای instance
- Tenant configuration: `WhiteLabelConfiguration` و Agency hierarchy
