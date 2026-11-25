# کارن تراول — تصمیم‌های معماری (ADR)

> منبع: مخزن karentravel.ir — تجمیع خودکار برای Gemini Notebook (2026-11-24)


---

## فایل: docs/adr/0001-search-service-monorepo.md

# ADR-0001: karenseir-search stays in the monorepo (for now)

Status: Accepted
Date: 2026-09-11

## Context

`search-service/` was extracted from the monolith (`backend/app/main.py`) as an
independently deployable service (own Docker image `karenseir-search`, own
process, own port 8080/8090, own Postgres database `karenseir_search`, own
Python dependency set) using the strangler fig pattern. The monolith now
gateways to it via `/search/v3`, `/search/v3/public`, and
`/search/autocomplete/v3/public`, resolving tenant identity from the JWT and
passing only a minimal internal `SearchContext` (tenant slug + public flag) —
never raw claims or user records.

The service is already deployment-independent: it has its own Dockerfile,
requirements.txt, test suite, and can be built/deployed/rolled back without
touching the monolith image. The only thing not yet done is moving
`search-service/` into its own Git repository.

The current Phase 2 master prompt explicitly instructs: **do not split
`search-service/` into a separate Git repository in this phase** — document
the decision and the future trigger conditions instead.

## Decision

Keep `search-service/` inside the `karenseir-current` monorepo, as a sibling
directory to `backend/` and the Next.js `web` app, for now. Do not create a
separate `karenseir-search` Git repository yet.

Reasons:
- The service is young (Phase 1/2 of extraction, days old in production). Its
  contract with the monolith (`/internal/search/offer-pool`, `SearchContext`
  shape, failure taxonomy) is still being hardened and is easiest to change
  atomically when both sides are in one commit/one PR.
- A single engineer/small team currently owns both the monolith and the
  service; a repo split adds process overhead (cross-repo versioning, a
  package registry or git-submodule story, coordinated releases) with no
  present benefit — nobody outside this team consumes `search-service/`
  independently yet.
- Shadow-parity and rollback verification during this extraction relied on
  being able to `git diff`/`git log` both sides together; splitting now would
  lose that continuity for the remaining strangler work (frontend cutover,
  eventual retirement of the old monolith search code path).
- Deployment independence (the property that actually matters operationally)
  is already achieved via separate Docker images/containers/DB — a Git
  repository boundary is a separate, weaker-priority concern than a runtime
  boundary, and the runtime boundary is what was required first.

## Future triggers to re-evaluate (split when ANY of these becomes true)

1. **A second consumer appears.** Any other service, team, or repository
   needs to depend on `search-service/` independently of the monolith's
   release cadence (e.g. a mobile-only search proxy, a partner integration).
2. **Independent release cadence is needed.** The team wants to deploy
   `search-service/` changes more often than monolith changes (or vice
   versa) and the shared repo's CI/branch protection rules start actively
   blocking that (e.g. monolith CI failures blocking a search hotfix merge).
3. **Ownership diverges.** A different team or on-call rotation takes
   ownership of Search from the monolith team, making a shared repo's
   permission model (single set of reviewers/branch rules) a liability.
4. **Repo size/CI time becomes a measurable bottleneck** attributable to
   `search-service/`'s own history/tests/build inflating monorepo CI time
   past an agreed threshold.
5. **The internal contract stabilizes and hardens** to the point that changes
   to `/internal/search/offer-pool` or the `SearchContext` schema become rare
   and versioned (e.g. an explicit `v2` internal contract), reducing the need
   for atomic cross-boundary commits.
6. **Elasticsearch/OpenSearch (or another indexing backend) is adopted.** A
   genuinely separate scaling/ops profile (dedicated infra, dedicated
   on-call, heavier resource footprint) is a natural forcing function for a
   repo split, since it would already require independent infra tooling.

None of these conditions currently hold. Re-visit this ADR when one does.

## Consequences

- `search-service/` continues to be versioned, reviewed, and CI'd inside
  `karenseir-current`; its own `tests/` run as a scoped/targeted pytest job,
  not folded into the monolith's pytest run.
- Docker image builds, tags, and container lifecycles remain fully
  independent (already true today) — this ADR only concerns source control,
  not runtime architecture.
- No code changes result from this ADR; it is a documentation-only decision
  record satisfying the Phase 2 requirement to record the rationale rather
  than act on it.

---

## فایل: docs/adr/ADR-001-modular-monolith.md

# ADR-001: Modular Monolith for Pilot Foundation

**Status:** Accepted for target architecture (implementation deferred)

## Context

کارن‌سیر دامنه‌های متعدد، multi-tenancy، providerهای ناهمگون و نیاز عملیاتی حساس دارد؛ در عین حال پایلوت باید کنترل‌شده بماند.

## Decision

شروع backend بعد از تأیید UI با FastAPI/Python، PostgreSQL، SQLAlchemy 2.x، Alembic، Pydantic v2، Redis و Docker Compose در Modular Monolith انجام می‌شود. مرز bounded context، outbox، saga، idempotency، JWT access/refresh، OTP adapter، RBAC/policy، audit، health/readiness، observability و RLS از ابتدا طراحی می‌شوند.

## Consequences

توسعه و تراکنش ساده‌تر است و مرزهای کد برای جداسازی آینده باقی می‌ماند. استقلال deploy فوری به‌دست نمی‌آید و باید با module ownership و contract test از monolith نامنظم جلوگیری شود.

---

## فایل: docs/adr/ADR-002-idempotent-manual-booking.md

# ADR-002: Idempotent Manual Booking Command

**Status:** Accepted

## Context

مسیر پایلوت `POST /bookings` موجودی دستی هتل را کم می‌کند و ledger/audit می‌سازد. تکرار درخواست در اثر retry شبکه یا دوبار کلیک می‌توانست رزرو و کاهش موجودی تکراری ایجاد کند. قیمت و موجودی باید فقط در backend authoritative بمانند.

## Decision

- درخواست ایجاد رزرو باید header صریح `Idempotency-Key` با طول ۸ تا ۱۲۰ نویسه داشته باشد.
- کلید در scope مستأجر و فرمان `legacy-booking.create` ذخیره می‌شود؛ تکرار همان payload همان پاسخ نخست را بدون mutation تازه برمی‌گرداند.
- استفاده دوباره از همان کلید با payload متفاوت با `409` fail-closed می‌شود.
- ردیف هتل هنگام بررسی و کاهش موجودی با `SELECT ... FOR UPDATE` قفل می‌شود (در PostgreSQL؛ SQLite توسعه‌ای این clause را نادیده می‌گیرد).
- این تغییر فقط مسیر دستی پایلوت را سخت‌تر می‌کند و جایگزین مدل provider-neutral `Reservation` یا اتصال Provider نیست.

## Acceptance

- دو درخواست همسان با یک کلید فقط یک Booking، یک ledger، یک audit و یک کاهش موجودی ایجاد کنند.
- همان کلید با تعداد شب متفاوت رد شود.
- tenant scope و سقف اعتبار موجود حفظ شوند.
- lint، typecheck، build و تست backend سبز بمانند.

## Rollback

کد endpoint و ارسال header در صفحه پایلوت قابل بازگشت است. جدول یا migration تازه‌ای ایجاد نمی‌شود و رکوردهای idempotency موجود حذف نمی‌شوند.

---

## فایل: docs/adr/ADR-003-postgresql-rls.md

# ADR-003: PostgreSQL Row-Level Tenant Isolation

**Status:** Accepted

## Decision

تمام جدول‌های دارای `tenant_id` در PostgreSQL با RLS و `FORCE ROW LEVEL SECURITY` محافظت می‌شوند. policy مشترک، `tenant_id` را با `current_setting('app.tenant_id', true)` مقایسه می‌کند و نبود context هیچ ردیفی را قابل خواندن/نوشتن نمی‌کند. API tenant را فقط از access token امضاشده می‌گیرد و با `set_config(..., true)` در transaction جاری قرار می‌دهد.

Migration فقط policy اضافه می‌کند، داده را بازنویسی یا حذف نمی‌کند. seed توسعه در Production اجرا نمی‌شود. تست مستقیم PostgreSQL باید خواندن، درج و تغییر cross-tenant را رد کند.

## Rollback

پیش از migration از PostgreSQL backup گرفته می‌شود. downgrade فقط policy/RLS این migration را غیرفعال می‌کند و هیچ داده‌ای را حذف نمی‌کند. image قبلی همراه migration downgrade یا restore آزموده‌شده مسیر rollback است.


---

## فایل: docs/adr/ADR-004-distributed-rate-limiting.md

# ADR-004: Distributed Production Rate Limiting

**Status:** Accepted

## Decision

Production از Redis و فرمان Lua اتمیک برای fixed-window rate limiting استفاده می‌کند. کلید شامل route class و fingerprint هش‌شدهٔ client/auth است؛ token خام ذخیره نمی‌شود. login محدودیت سخت‌تر دارد و پاسخ `429` شامل `Retry-After` است.

در Production نبود `REDIS_URL`، خطای اتصال Redis یا backend غیرتوزیع‌شده باعث fail-closed شدن readiness/startup می‌شود. Development و تست می‌توانند limiter حافظه‌ای صریح داشته باشند.

## Rollback

rate limiter با بازگرداندن image قبلی rollback می‌شود. حذف Redis keyها لازم نیست چون TTL دارند. غیرفعال‌کردن limiter در Production مجاز نیست.


---

## فایل: docs/adr/ADR-005-production-secret-and-observability-contract.md

# ADR-005: قرارداد Secret و Observability در Production

## وضعیت

پذیرفته‌شده — ۱۴۰۵/۰۵/۲۸

## تصمیم

- سرویس‌ها secret را یا مستقیماً از متغیر محیطی و یا از فایل mount‌شده با پسوند `_FILE` می‌خوانند؛ تعریف هم‌زمان هر دو fail-closed است.
- فایل secret باید regular file، غیر symlink و بدون دسترسی group/other باشد. مقدار secret هرگز log نمی‌شود.
- در `ENVIRONMENT=production` حالت provider برابر `mock` فقط با `DEMO_MODE=true` مجاز است. حالت پیش‌فرض `disabled` می‌ماند و هیچ موفقیت خارجی جعل نمی‌شود.
- قواعد Prometheus برای down بودن API، نرخ 5xx/429 و latency در repository version می‌شوند. اتصال collector و Alertmanager یک gate بیرونی و قابل‌اثبات است.
- validation عمومی DNS/TLS/readiness/metrics با script فقط read-only انجام می‌شود و بدون hostname واقعی PASS اعلام نمی‌شود.

## پذیرش

1. unit test خواندن secret-file، conflict، symlink و permission ناامن را پوشش دهد.
2. Production با provider mock و بدون Demo Mode در startup رد شود.
3. فایل‌های Prometheus با `promtool check rules` در محیط دارای promtool معتبر باشند؛ حداقل syntax YAML در QA محلی بررسی شود.
4. validation عمومی certificate معتبر، hostname، readiness و metrics را بررسی کند و self-signed را نپذیرد.

## Rollback

تغییر schema یا data ندارد. rollback با بازگرداندن image قبلی انجام می‌شود. secretهای mount‌شده تا تأیید سلامت نسخه قبلی حفظ می‌شوند و rotation/revocation فقط پس از rollback موفق انجام می‌شود.

---

## فایل: docs/adr/ADR-006-production-otp-and-session-security.md

# ADR-006: OTP و Session امن و Tenant-aware

## وضعیت

پذیرفته‌شده — ۱۴۰۵/۰۵/۲۸

## تصمیم

- ورود Production از دو فرمان `request` و `verify` با challenge تصادفی و یک‌بارمصرف انجام می‌شود.
- tenant با slug صریح انتخاب و سپس context پایگاه داده bind می‌شود؛ identifier به‌صورت plaintext در challenge ذخیره نمی‌شود.
- OTP شش‌رقمی فقط با CSPRNG ساخته، با HMAC-SHA256 و secret سرور hash و حداکثر پنج دقیقه معتبر است.
- پاسخ request برای کاربر موجود/ناموجود یکسان است. بدون delivery موفق adapter، challenge فعال و session ساخته نمی‌شود.
- verify حداکثر پنج تلاش دارد. failureهای متوالی حساب را ۱۵ دقیقه lock می‌کنند و verify موفق counter را reset می‌کند.
- replay با `consumed_at`، row lock و transaction رد می‌شود. session شامل hash توکن، device hash، IP hash، زمان استفاده و revoke reason است.
- logout نشست جاری را revoke می‌کند؛ reuse توکن refresh قبلی بعد از rotation، کل خانواده نشست را revoke می‌کند.

## پذیرش

تست‌ها باید success، expiration، wrong-code lockout، replay، refresh reuse، logout، tenant isolation، user enumeration و provider fail-closed را پوشش دهند.

## Rollback

Migration فقط جدول/ستون اضافه می‌کند. downgrade داده را حذف نمی‌کند. rollback با image قبلی انجام می‌شود و جدول‌های جدید تا پایان دوره retention دست‌نخورده باقی می‌مانند.

---

## فایل: docs/adr/ADR-007-payment-intent-callback-and-refund.md

# ADR-007: Payment Intent، Callback و Refund

## وضعیت

پذیرفته‌شده — ۱۴۰۵/۰۵/۲۸

## تصمیم

- مبلغ Payment Intent فقط از pricing snapshot رزرو و در transaction backend ساخته می‌شود.
- create/initiate/refund با idempotency tenant-scoped و row lock اجرا می‌شوند.
- callback شامل tenant و event id است، ولی فقط بعد از HMAC-SHA256 روی raw body پذیرفته می‌شود؛ بدون secret معتبر fail-closed است.
- event callback immutable و provider event id یکتا است. state machine transition نامعتبر را رد می‌کند.
- refund یک رکورد مستقل و outbox event می‌سازد؛ موفقیت فقط بعد از callback معتبر ثبت می‌شود و جمع refund از captured amount بیشتر نمی‌شود.

## پذیرش و rollback

تست create، duplicate، callback جعلی/تکراری، transition و over-refund اجباری است. Migration فقط جدول اضافه می‌کند و downgrade مخرب نیست؛ rollback با image قبلی انجام می‌شود.

---

## فایل: docs/adr/ADR-008-offer-booking-orchestration.md

# ADR-008: Orchestration از Offer تا Voucher

## وضعیت

پذیرفته‌شده — ۱۴۰۵/۰۵/۲۸

## تصمیم

- Offer فقط توسط supplier مجاز و برای tenant همان supplier ثبت می‌شود؛ قیمت، موجودی و policy در frontend authoritative نیست.
- Price Check یک snapshot immutable با expiry و hash می‌سازد. Booking فقط از Price Check معتبر و مصرف‌نشده ساخته می‌شود.
- Flight، Hotel، Tour و Package از state machine مشترک استفاده می‌کنند؛ itemهای package snapshot مستقل دارند.
- confirmation خارجی فقط پس از payment captured و response موفق provider انجام می‌شود. inventory داخلی supplier با fulfillment دستی و audit قابل تأیید است.
- Voucher فقط توسط supplier/backoffice پس از confirmation و با document reference غیرحساس صادر می‌شود.
- هر transition history، outbox، actor و idempotency tenant-scoped دارد.
- cancellation/refund estimate فقط از policy snapshot دارای `verified=true` محاسبه می‌شود؛ در غیر این صورت پاسخ `409` است.

## پذیرش و rollback

تست service typeها، expiry، replay، cross-tenant، payment gate، provider failure، manual fulfillment، voucher و policy quote اجباری است. Migration فقط table/column/index اضافه می‌کند و downgrade مخرب نیست.

---

## فایل: docs/adr/ADR-009-configurable-approval-engine.md

# ADR-009: Approval Engine قابل‌تنظیم

## تصمیم

هر tenant می‌تواند template نسخه‌دار شامل stepهای مرتب Expert، Manager، Finance و CEO بسازد. workflow از template snapshot می‌گیرد؛ تغییر template روی گردش جاری اثر ندارد. هر step status و SLA مستقل دارد. تصمیم فقط برای role همان step یا Platform Admin مجاز است، rejection reason اجباری است و escalation history حذف نمی‌شود.

Department، Cost Center و Employee Assignment tenant-scoped هستند. تمام تصمیم‌ها، escalationها و پایان workflow outbox/audit event دارند.

Migration فقط افزایشی است. rollback با application image قبلی و حفظ تاریخچه انجام می‌شود.

---

## فایل: docs/adr/ADR-010-tenant-configuration-and-grounded-views.md

# ADR-010: Tenant Configuration و Grounded Read Models

White Label به‌صورت یک config tenant-scoped و بدون fork ذخیره می‌شود. domain تا پیش از verification فعال نمی‌شود؛ logo فقط reference امن است. Agency hierarchy و نرخ‌ها basis-point هستند. Notification receipt با provider event id یکتا و callback امضاشده ثبت می‌شود.

Comparison فقط Offerهای معتبر tenant را امتیازدهی می‌کند و breakdown عددی/قابل‌توضیح می‌دهد. AI Context endpoint فقط رزرو، سفر، policy snapshot و provider health موجود را برمی‌گرداند و `authoritative` هر بخش را مشخص می‌کند؛ تولید price/inventory/refund/booking در آن وجود ندارد.

Migration افزایشی و rollback غیرمخرب است.

---

## فایل: docs/adr/ADR-011-provider-resilience.md

# ADR-011: Provider Resilience توزیع‌شده

هر adapter با wrapper مشترک اجرا می‌شود. throttling و circuit state در Redis و با کلید tenant/provider نگهداری می‌شوند. Redis configured ولی unavailable باعث fail-closed می‌شود. فقط خطای retryable با backoff محدود retry می‌شود؛ نتیجه business/non-retryable تکرار نمی‌شود. transport باید timeout شبکه خود را enforce کند و wrapper نیز سقف انتظار call دارد.

Circuit پس از پنج failure در ۶۰ ثانیه برای ۳۰ ثانیه باز می‌شود. raw credential، destination، payload یا token وارد key/metric نمی‌شود. rollback با حذف wrapper image است؛ keyها TTL دارند.

---

## فایل: docs/adr/ADR-012-performance-indexes.md

# ADR-012: Performance Baseline و Index Budget

Index فقط برای queryهای واقعی tenant-first اضافه می‌شود. migration افزایشی است و قبل از Production باید زمان build/size روی clone داده واقعی اندازه‌گیری شود. rollback indexها را خودکار حذف نمی‌کند؛ image rollback امن است.

---

## فایل: docs/adr/ADR-013-financial-reconciliation-read-model.md

# ADR-013: Financial Reconciliation Read Model

## Decision

Finance users receive a tenant-scoped, read-only reconciliation view derived from immutable payment, refund, settlement and wallet-ledger records. The view never repairs balances automatically and never accepts an amount from the frontend. It reports per-payment captured/refunded totals, pending refund exposure, provider-reference gaps, settlement totals and ledger balances, plus explicit discrepancies.

Only `ledger:read` may access this view. Every query includes tenant scope and remains protected by PostgreSQL RLS. Cross-tenant identifiers are not accepted as input.

## Acceptance and rollback

Tests cover balanced and mismatched refunds, pending exposure, tenant isolation and role denial. This change has no migration or data mutation; rollback is the prior application image.

---

## فایل: docs/adr/ADR-014-authenticated-frontend-read-models.md

# ADR-014: Authenticated Frontend Read Models

## Decision

Approved pages consume only authenticated, tenant-scoped API read models. A root client provider keeps access and rotating refresh tokens in memory across client navigation; tokens are never written to local/session storage. Only a non-sensitive random device identifier is session-scoped. Full reload intentionally requires login again until an HttpOnly BFF session is introduced.

Trips, notifications and organization overview receive dedicated read-only endpoints. Supplier, Agency, BackOffice and finance pages reuse their existing permission-guarded endpoints. UI states distinguish loading, empty, unauthorized, forbidden, provider unavailable and generic error. Demo fixtures remain only on explicitly identified sample identifiers and are never presented as live data.

## Acceptance and rollback

API tests cover tenant isolation and role denial. Playwright covers authenticated navigation, empty/success views and panel RBAC. No schema or production data changes are made. Rollback is the previous frontend/backend image.

---

## فایل: docs/adr/ADR-015-customer-account-and-panel-mutations.md

# ADR-015: Customer account and role-panel mutations

## Decision

The approved UI will use the existing in-memory authenticated client for customer profile, owned travellers, personal wallets, payments, notification preferences, support messages, supplier inventory, agency configuration and backoffice supplier status. Every query and mutation includes both tenant and ownership/permission predicates. Financial balances remain derived from the immutable ledger; payment initiation remains fail-closed through the configured adapter.

No schema or migration is introduced. Existing operational tables are sufficient. Supplier, agency and backoffice mutations emit audit/outbox records where they change operational state. Customer support messages are visible only when linked to a trip or reservation owned by the authenticated user.

## Acceptance

- Cross-tenant and IDOR reads/mutations return 404; missing role permissions return 403.
- Duplicate personal-wallet creation is idempotent and does not duplicate ledger state.
- Payment UI can create an intent from an authoritative reservation snapshot but cannot claim provider success when the adapter is unavailable.
- Loading, empty, unauthorized, forbidden, validation/error and success states are rendered without changing the approved RTL/Vazirmatn identity.
- Backend regression, lint, strict TypeScript, production build and browser E2E pass.

## Rollback

Revert the route/components and endpoint commit. No database rollback or data migration is required. Existing rows remain compatible and no production credential or provider mode is changed.

---

## فایل: docs/adr/ADR-016-invoice-support-installment-admin.md

# ADR-016: Invoice, support cases, installments and controlled administration

## Decision

Add four tenant-scoped tables: immutable invoice snapshots, support cases, source-labelled support thread messages and installment agreements. PostgreSQL enables and forces the existing fail-closed tenant policy on every new table. Existing settlement records remain the settlement source; posting creates only an auditable pending record and never claims an external transfer.

Invoice issuance is derived from an authoritative reservation price snapshot. Customer reads are owner-scoped. Human support replies require `support:manage`; AI messages cannot be submitted through the human endpoint. Installment agreements are calculated from an active tenant/organization plan and remain `requested` until a finance role activates them. User role changes require `member:manage`, cannot target platform admins, cannot self-escalate and write legacy audit plus outbox evidence.

## Acceptance

- New tables have `tenant_id`, PostgreSQL RLS and FORCE RLS with no-context fail-closed behavior.
- Every mutation is tenant-filtered, RBAC guarded and idempotent where it creates a financial/domain record.
- Invoice totals, installment schedules and settlements are backend-derived; UI cannot submit authoritative totals.
- Human, customer, AI and system thread sources remain distinct.
- Existing and new backend, browser, lint, type and build suites pass.

## Rollback

Revert UI/API code, then downgrade revision `20260820_10`, which drops only the four new unused tables in dependency order. Existing reservations, payments, wallets, settlements, users and security policies are unchanged.

The migration owner provisions `karenseir_api` after initial schema creation. That contract grants current objects and installs default table/sequence privileges so an additive rollback→upgrade cannot silently deny the least-privilege API role access to recreated objects.

---

## فایل: docs/adr/ADR-017-ecosystem-search-layer.md

# ADR-017 — Ecosystem Search Layer

Status: accepted for incremental implementation — 2026-08-20

## Decision

KarenSeir keeps one tenant-aware search contract over the existing `Offer`, `SearchRequest`, provider-adapter and price-check domains. The contract supports flight, hotel, train, tour, accommodation, car rental, restaurant, event/hall, pool/sport, attraction, travel guide, handicraft, tourist transportation and package verticals without duplicating booking logic.

Search responses expose source, observed/availability/price timestamps, expiry, freshness state, inventory state, total price components, verified cancellation policy and vertical attributes. An expired offer is never returned as live. A provider-backed offer without a fresh observation is labelled `provider_required`; it is not promoted to confirmed availability.

Persian query normalization converts Arabic ی/ک, removes diacritics, normalizes whitespace and zero-width characters, and preserves the normalized query in the tenant-scoped search audit record. Filters and ranking operate only on backend offer snapshots. Frontend values are advisory inputs, never authoritative price, availability or policy.

The approved Homepage and its search-box presentation are frozen. Search 2.0 is integrated behind the API and in dedicated result routes only; this ADR does not authorize any Homepage DOM, section order, spacing, typography, color, image or responsive change.

## Acceptance

- All declared verticals use the same endpoint and output envelope.
- Tenant isolation remains enforced in the SQL query and PostgreSQL RLS.
- Expired/stale offers are excluded or explicitly labelled; timestamps are mandatory in every result.
- Price, taxes and fees are backend-derived from the stored offer snapshot.
- Persian normalization, filters, sort, cross-tenant denial and freshness have tests.

## Rollback

The change is API-additive and uses existing tables. Roll back the application commit; no schema downgrade or data deletion is required. Existing minimal `{service_type}` requests remain compatible.

---

## فایل: docs/adr/ADR-018-saved-travel-reviews-destinations-itineraries.md

# ADR-018 — Saved travel, verified trust, destinations and editable itineraries

Status: accepted for incremental implementation — 2026-08-20

## Decision

Add tenant-scoped persisted domains for saved trips and their wishlist/basket items, customer reviews and immutable supplier responses, destination hierarchy, and editable itineraries. Every table has `tenant_id`, PostgreSQL RLS and `FORCE RLS`. User-owned resources are additionally owner-filtered at API level. Mutations use command IDs and audit/outbox records; moving an item changes state under a row lock rather than copying it.

`verified_booking` is always derived by the backend from an owned, issued/completed reservation matching the review service type. It is never accepted from clients. Supplier responses are separate rows and cannot overwrite customer text. AI analysis remains `not_requested` until a real model and moderation policy exist.

Destination records are tenant-configurable and hierarchical (`country/province/city/district/poi`). Search result counts and inventory are queried from the Search Layer; destination pages never persist invented availability.

Itinerary items may reference a current Offer. The server snapshots only source/timestamp metadata and labels every non-fresh or unlinked item `needs_live_availability_check`. Reorder, move-day, replace and duplicate operations are owner-scoped and idempotent.

The approved Homepage is frozen. New UI is allowed only in dedicated routes; this ADR authorizes no Homepage/CSS/asset changes.

## Acceptance

- Own-user create/read/move/remove/duplicate operations pass; cross-tenant and IDOR access return not found/forbidden.
- Duplicate command IDs replay the same response and conflicting payloads fail.
- Missing PostgreSQL tenant context sees/writes no rows; all new tables have RLS/FORCE RLS.
- Review verification cannot be forged; moderation and supplier response actions are audited.
- Destination hierarchy/slugs/geo and itinerary ordering have constraints.
- Existing security, booking, frontend, E2E and frozen Homepage gates remain green.

## Rollback

Revert application routes, then downgrade only revision `20260820_11`. The migration drops the new empty/additive tables in dependency order and does not alter existing bookings, payments, trips, search offers or Homepage assets. Take and verify a database backup before downgrade on any shared environment.

---

## فایل: docs/adr/ADR-019-review-checkout-zarinpal-public-seo.md

# ADR-019 — Review UI, resumable checkout, ZarinPal contract and public destination SEO

Status: Accepted for credential-independent implementation

## Decision

- Homepage, its CSS, assets and approved layout remain frozen. New capability is isolated to dedicated routes and backend contracts.
- Reviews are paginated by the backend. `verified_booking` is read-only and derived from an owned issued/completed reservation. Reports are tenant-aware, idempotent and audited.
- Checkout state is persisted server-side and owned by tenant/user. The backend alone performs price/availability recheck, policy validation, funding validation and PaymentIntent creation. Client amounts are never authoritative.
- ZarinPal is a dedicated payment adapter with disabled/sandbox/production modes. Missing merchant/callback configuration fails closed. Callback parameters never capture funds; only server-side verify may record RefID and capture once.
- Public destination reads use an explicit tenant slug, set PostgreSQL tenant context before querying and expose only published catalog data. Dynamic search URLs remain non-indexable.
- Unified Search v2 extends the existing Offer/SearchRequest foundation rather than creating vertical-specific engines. Entity catalog and saved searches are tenant-scoped; normalized provider offers remain the transactional source.

## Acceptance

- Review list/create/report pagination and supplier response display pass UI/API tests; verified forgery and cross-tenant access fail.
- Checkout create/resume and ordered steps reject stale price, missing policy acknowledgement, foreign travellers, amount tampering and cross-tenant IDs.
- ZarinPal adapter contract tests cover request, verify, amount/authority mismatch, duplicate verification and missing credentials without claiming a sandbox purchase.
- Destination metadata, canonical, OpenGraph, sitemap, robots and JSON-LD are emitted without modifying Homepage.
- PostgreSQL migration is additive, has RLS/FORCE RLS and rollback removes only newly introduced state after backup.

## Rollback

- Revert dedicated routes/API wiring and downgrade only the additive migration after a verified backup.
- Keep external payment modes disabled during rollback; never reinterpret callback data as a successful payment.

---

## فایل: docs/adr/ADR-020-travel-commerce-domains.md

# ADR-020 — Travel commerce domains: rentals, tours, cruises and visas

Status: Accepted for credential-independent implementation

## Context and benchmark findings

KarenSeir keeps one commerce lifecycle while preserving vertical-specific inventory rules. Product patterns were reviewed from public material for Jajiga and Iranian tour operators, Airbnb booking/filter guidance, Royal Caribbean and Norwegian Cruise Line fare/availability terms, and the official France-Visas, German Consular Services Portal and Canada immigration processes. The reusable findings are domain rules, not visual designs:

- Vacation rentals require date-and-guest eligibility, property/unit separation, explicit fees/rules and inventory locking; confirmed or pending reservations must block overlapping inventory.
- Tours require dated departures, capacity, transport/hotel/service disclosure, room/passenger pricing and explicit visa assistance state.
- Cruise fares are sailing/cabin-specific and port fees/taxes are separate; live availability cannot be inferred without a contracted provider.
- Visa applications are document- and human-review workflows. Biometrics, processing and the final decision remain external-authority actions; KarenSeir must never promise approval or an unverified processing time.

## Decision

- Add tenant-scoped `vacation_*`, `tour_*`, `cruise_*` and `visa_*` tables through one additive migration. Every table receives PostgreSQL RLS and FORCE RLS.
- Inventory mutations lock the authoritative unit/departure row, validate the complete date/capacity request and use a tenant-scoped command id for idempotency.
- Customer-facing prices are server-calculated from stored component snapshots. Clients cannot set availability, verification, visa decisions, voucher issuance or payment capture.
- Cruise search/detail may expose configured catalog records, but live booking fails closed until a contracted provider adapter is enabled.
- Visa timelines distinguish `system`, `human_agent` and `external_authority`; applicant uploads cannot mark a document accepted.
- Existing Search v2 remains the shared discovery contract. New verticals extend its service-type vocabulary; they do not create a parallel search engine.
- Homepage identity and section layout remain frozen. Dedicated routes host the new workflows.

## Acceptance

- Own-tenant reads/writes pass; cross-tenant and missing PostgreSQL tenant context fail.
- Rental overlap and tour oversell attempts fail under locked transactions; duplicate commands return the original reservation.
- Visa eligibility is explicitly advisory and source-timestamped; decision and document review require BackOffice/Support roles.
- Cruise live booking returns a fail-closed provider-unavailable response when no contracted adapter exists.
- Browser tests cover Search interaction plus rental, tour, cruise and visa routes without using fake live inventory.

## Rollback

- Take and checksum a PostgreSQL backup before upgrade.
- Disable the new routes, then downgrade only revision `20260820_14`; no existing commerce table is altered or dropped.
- External providers and payment modes remain disabled throughout rollback.

---

## فایل: docs/adr/ADR-021-home-search-interaction-repair.md

# Homepage Search interaction repair

Server evidence 2026-09-08: IP port80 and frontend port3000 return identical HTML. Live standalone image is 9f082e7-leisure, build H201mo0cEFS4jGxRiDVT7; source current is ac379c1 with no bind mount. Editing source or building the unrelated port3210 instance does not update the IP.

Chrome on the actual IP at1440/768/430/390: fs-scrim intercepts the first origin-to-destination click; at768 the date panel overflows the viewport; at430/390 the fixed bottom navigation obscures confirmation. Search submits to the homepage although the current owner requires the existing /search/results route.

Decision: remove blocking scrim and use pointer-outside dismissal; show small-screen pickers in the form flow with scroll clearance. Preserve existing colors, typography, imagery, tabs and backend architecture. Validate criteria, carry selected dates and the full passenger count to the existing Search API, use the existing results page. No seeds, providers, auth or payments.

Acceptance: real browser interaction at all four widths, autocomplete selection, editable dates and passengers, one valid public Search request, correct URL and rendered response, no console/network errors, before/after screenshots. An honest zero-result response is distinguished from confirmed live inventory. Build and candidate checks precede swapping production; retain the prior container for rollback.

Rollback checkpoint: /home/ubuntu/karen-audit-20260908-search/source-before.tar.gz and before.json.

Candidate verification exposed mobile flex-basis:0 collapsing expanded autocomplete to54px; allow natural heights. The existing missing /favicon.ico generated a browser Console404; serve a transparent SVG without introducing a new logo.

---

## فایل: docs/adr/ADR-021-vandapay-payment-provider.md

# ADR-021 — VandaPay («پرداخت با ونداپی») as an additional fail-closed payment provider

وضعیت: پذیرفته‌شده برای پیاده‌سازی مستقل از credential — ۱۴۰۵/۰۸/۲۱ (۲۰۲۶-۱۱-۱۲)

> **یادداشت 2026-11-19:** روی `main` با [ADR-029](ADR-029-federated-org-credit-and-vandapay-hardening.md) ادغام شد: پرچم `VANDAPAY_MODE` (به‌جای `VANDAPAY_ENABLED`)، `VANDAPAY_BASE_URL` (به‌جای `VANDAPAY_API_BASE`)، شروع پرداخت فقط از `POST /payments/{id}/initiate`، aud state `karenseir-vandapay-callback`، و ونداپی درگاه اصلی (ADR-024) است نه روش اضافه کنار ZarinPal.

## زمینه
تصمیم‌های مالک در مخزن ونداپی (`docs/DECISIONS.md`): D13 — ونداپی یکی از درگاه‌های همهٔ سایت‌های گروه؛ D14 — ونداپی سرور و دامنهٔ خودش را دارد (آدرس API فقط پیکربندی است)؛ D15 — اتصال‌ها اکنون ساخته و آزمون می‌شوند ولی تا قرارداد PSP و نظر حقوقی **خاموش** می‌مانند.
ونداپی شرکت ثالث از دید KarenSeir است (پذیرنده = KarenSeir)؛ هیچ کد، DB یا UI از 60Online یا مخزن ونداپی import نمی‌شود — فقط قرارداد HTTP عمومی آن.

## تصمیم
- ماژول مستقل `backend/app/vandapay.py` (فقط کتابخانهٔ استاندارد) + چهار endpoint در `main.py`؛ مسیر ZarinPal و `ADAPTERS["payment"]` دست نخورده‌اند.
- پرچم `VANDAPAY_ENABLED` پیش‌فرض خاموش؛ روشن شدن فقط با `VANDAPAY_API_BASE` (https) + `VANDAPAY_SECRET_KEY` + `VANDAPAY_WEBHOOK_SECRET` + `VANDAPAY_RETURN_URL` (https). در غیر این صورت `/payments/methods` آن را فهرست نمی‌کند و همهٔ endpointهای آن 404 می‌دهند.
- `sk_live_` فقط در `ENVIRONMENT=production`؛ `sk_test_` در production فقط با `DEMO_MODE` و همیشه با برچسب «حالت آزمایشی».
- مبلغ فقط از Payment Intent موجود (pricing snapshot رزرو، ریال) — کلاینت مبلغ نمی‌فرستد. `Idempotency-Key` قطعی `karenseir-{tenant}-{intent}-attempt-{n}`.
- بازگشت مرورگر فقط state امضاشده (JWT، aud `karenseir-vandapay-return`) را می‌پذیرد؛ پارامترهای دیگر مثل `status` نادیده گرفته می‌شوند.
- وب‌هوک: HMAC-SHA256 روی بدنهٔ خام، تحمل ۳۰۰ ثانیه، چند `v1`؛ سپس intent از API ونداپی بازخوانی و tenant/intent از metadata **پاسخ API** (نه رویداد) خوانده می‌شود؛ حذف تکراری با `payment_events(provider_key='vandapay', provider_event_id='evt:…')`.
- Capture فقط وقتی: status=`succeeded` + مبلغ دقیق ریالی + `IRR` + mode کلید + metadata ما + بدون استرداد. `unknown`/`processing`/هر وضعیت ناشناخته = «در حال بررسی»، هیچ تغییری. رویداد `succeeded` که API هنوز تأیید نکرده ⇒ 503 تا ونداپی دوباره بفرستد.
- ~~رویدادهای استرداد فقط ثبت و برای بررسی دستی لاگ می‌شوند~~ — **اصلاح‌شده با ADR-022 (روی main: ADR-029)** (استرداد، لغو intent، تأیید سازمان، اعتبار فدرال).
- بدون migration: از ستون‌های موجود `provider_key`، `provider_authority`، `provider_capture_reference` استفاده می‌شود.

## پذیرش
`backend/tests/test_vandapay.py` (MOCK برچسب‌خورده): پرچم خاموش، پیکربندی ناقص/ناامن، بردارهای مشترک امضا، idempotency، cross-tenant، خطای موقت، unknown/pending، capture یک‌باره، عدم تطابق مبلغ/ارز/mode/metadata/استرداد، state جعلی، امضای غلط/کهنه، تکرار رویداد.

## Rollback
`VANDAPAY_ENABLED=0` (فوری، بدون deploy کد) یا revert کامیت؛ هیچ migration/داده‌ای برای برگرداندن نیست.

---

## فایل: docs/adr/ADR-022-booking-marketplace-closure.md

# ADR-022 — Booking domain and accommodation marketplace closure

Accepted scope: user-supplied booking and accommodation requirements in docs/product.
Source baseline 09950ec; API main/operations hashes match running image fb8d03695ea0.

Reuse Reservation, BookingStatusHistory, PaymentIntent, Voucher, Trip, VacationProperty,
VacationUnit and VacationReservation. Payment capture alone must not issue a booking.
Do not add a parallel booking engine or imply that internal tests prove live selling.

First increment: validated accommodation rates/calendar in existing pricing_json;
per-night capacity from overlapping holds; transparent extra-guest and fixed fees;
calendar read API and assigned-supplier update with audit; customer calendar and quote.
All pricing and inventory are rechecked under the existing unit lock at booking.
A supplier rate update cannot overwrite an existing reservation's price snapshot.
No schema migration. Existing catalog stays private to its tenant until an explicit
publication workflow is implemented. No fake reviews, discounts or availability.

Acceptance: isolated DB-backed tests for calendar/rates, overlapping capacity,
minimum stay, replay/conflict and supplier permissions; desktop/mobile browser
calendar→quote→hold→checkout; affected prior accommodation regression only.
Rollback: retained API/worker/web images; additive JSON keys are compatible, but
older code does not enforce new calendar/rate keys. If used in live inventory,
disable affected units before reverting to an older implementation.

## Domain gap matrix (evidence-based; not a completion claim)
| Domain | Existing | Gap / closure order |
|---|---|---|
| Lifecycle | transitions, history, outbox, separate payment/voucher | replay payload binding; explicit vertical states still need mapping |
| Accommodation | property/unit, dated hold, seasonal quote, checkout | calendar, per-night capacity, fee breakdown first; request/approval and marketplace publication remain |
| Flight/train | normalized offers, travellers, checkout and manual fulfillment | supplier-specific fare/passenger and issuance contracts need verified adapters |
| Tour/car/leisure/guide/transport | existing isolated vertical baselines | compare each applicable field and after-sales action; no blanket DONE |
| Basket/trips | trip records, timeline, linked reservations | independent item expiry and atomic recheck review required |
| Travellers/checkout | owner-scoped profiles and checkout stages | field completeness and sensitive-data review required |
| After-sales/operations | service requests, support, event timeline, roles | partial cancellation/refund and changed-value detail review required |
| Organization | policy/approval/credit baseline | compare full settlement journey against requirements |
| Assistant | deterministic search/hold/checkout | structured accommodation constraints, multi-service planning remain |
| In-house | no approved adapter evidence inspected this increment | read-only integration capability discovery; no UI/DB coupling |
| Design | existing approved component system | preserve homepage; extend states in dedicated screens; Figma source not supplied |

Only tested increments are deployed; remaining internal gaps are not external blockers.

Second increment: explicit REQUEST_TO_BOOK stored on property details and frozen in
reservation snapshot. Requested rows do not promise/hold inventory. Host acceptance
locks and rechecks inventory/price before converting to a timed hold; no payment
intent or checkout until accepted. Rejection/withdrawal is non-financial. Commands
are bound to reservation/action/reason and audited through the existing transition,
trip event and outbox models. Supplier UI uses assigned-property scope only.

Fulfillment consistency: explicit supplier issuance also changes VacationReservation
from held to confirmed in the same DB transaction. Payment alone never does so.

Third increment: reuse EditableItinerary/Item as the trip basket. Replace the
placeholder add action with customer-authored items and real offer linkage. Recheck
each linked offer through the existing PriceCheck boundary; persist each item's
expired/unavailable/changed/ready/provider-required result, never substitute items.
A rechecked plan does not hold inventory or imply a combined purchase. Final per-item
booking retains the existing recheck/hold guards. Provider-only inventory stays
fail-closed. No bulk charge or all-or-nothing booking is introduced implicitly.

Booking recovery delta: known 409/422 invalidates the quote and asks for explicit
recheck; PRICE_CHANGED displays both totals. Unknown response keeps the command;
session-scoped pending command survives refresh, scoped by authenticated subject and
stay selection. The local claim is only a storage namespace, never authorization.
Server ownership checks remain authoritative. A received result clears retry state.
Desktop/mobile QA changed a real stored rate, dropped an already persisted response,
refreshed and recovered the same request ID; no duplicate booking or real charge.

Enterprise, finance, gift and benefit extension: see [ADR-023](ADR-023-enterprise-travel-welfare.md), including explicit internal gaps and Source-only implementation status.

---

## فایل: docs/adr/ADR-023-enterprise-travel-welfare.md

# ADR-023 — Enterprise travel and welfare

User requirements: docs/product/ENTERPRISE_TRAVEL_WELFARE_REQUIREMENTS.md.
Baseline aeac353, source/runtime main/operations content verified. Source and isolated
QA authorized. Production migration requires specific approval under AGENTS.md.

Use existing Organization, EmployeeAssignment, Department, CostCenter, Supplier,
Reservation, credit/ledger and outbox. New pre-booking EnterpriseRequest is not a
fake Reservation. Nine enterprise use cases share typed requirements but group/RFQ
requests are distinct from instant individual checkout. No financial method is
activated by a policy form or quote selection.

Add organization-scoped policy, explicit capability grants, request, immutable audit,
RFQ invitation and versioned supplier quote tables. Every table gets FORCE RLS and
explicit tenant predicates. Membership is necessary; generic tenant membership or a
finance role does not expose all employee requests. Requesters see only their own;
travel desk access and booking-on-behalf capability require an explicit grant.
Organization admins must themselves belong to the organization. Approvers are frozen
in the request policy snapshot, sequential, assigned members, and cannot self-approve.

A policy result is IN_POLICY / OUT_OF_POLICY / APPROVAL_REQUIRED / NOT_ALLOWED.
Store evaluated reasons and policy version. Unknown/no configured policy fails closed.
Budget in a request is an estimate, never reserved/spent credit. Supplier quotes are
real user-entered, versioned amounts; invited suppliers see redacted requirements,
not employee identity or the organization's internal budget. Selection validates
expiry and policy again. It is not a purchase/contract/charge or fulfillment claim.

Acceptance: isolated API/DB tests for owner/org/tenant boundaries, policy outcomes,
approval order/replay/self-approval, invited supplier quotes/revisions and selection;
real desktop/mobile UI→API→DB request and desk workflow; additive migration and RLS
checks against isolated PostgreSQL. No real SMS/payment or production fixtures.

Rollback: no existing table alteration. Keep old app images and the new tables on
application rollback. Destructive downgrade only for isolated QA; production must
not drop request/audit records. Prepare backup and exact migration/deploy commands
before asking for production approval.

## Master gap matrix extension
| Domain | Existing | This increment / remaining |
|---|---|---|
| Nine enterprise use cases | no pre-booking request aggregate | typed request + group RFQ |
| Hierarchy | organization/department/cost center/assignment | reuse; subsidiary/branch/project hierarchy remains |
| RBAC | coarse tenant roles | scoped configurable enterprise capabilities |
| Policy | booking/credit policy fragments | typed request policy + frozen outcomes; full fare/grade rules remain |
| Approvals | reservation-linked workflow | pre-booking sequential approvals with audit |
| Travel Desk | role overview | real open request/approval/RFQ queue |
| RFQ | absent | invitations, versioned quotes, selection; negotiation/contract/order/settlement remain |
| Budgets/benefits | credit ledger/cost-center budget | period/campaign allocations and family eligibility remain |
| Finance | existing checkout/credit/invoices | retain authorization; new methods not activated |
| Dashboard/reports | existing transaction views | no decorative metrics; enterprise scoped reporting remains |
| Enterprise assistant | consumer orchestration | structured group request handoff remains |
| Shared booking | common Reservation/Trip | request-to-reservation binding and delegated booking remain |

## Finance / gift requirements delta
Sources: ENTERPRISE_FINANCE_REQUIREMENTS.md and GIFT_BENEFIT_REQUIREMENTS.md.
The repeated gift attachment is one requirement, not two engines. Existing Wallet,
CreditAccount, FinancialLedgerEntry, InstallmentAgreement and ReconciliationRecord
are integration anchors. A campaign DRAFT records intent only: its proposed total
is not allocated, issued, funded or available credit. Bulk recipients are resolved
and validated server-side against organization membership. No delivery/token or
liability activation endpoint exists until funding and approved policy are wired.

| Added domain | Current implementation boundary | Internal work still required |
|---|---|---|
| Gift / benefit / campaign | persisted scoped campaign draft, bulk recipient validation, server total | funding linkage, approved issuance, claim/redeem, expiry, reports, consumer gifting |
| Enterprise finance | existing ledger/credit/installments/reconciliation retained | facility terms, atomic split funding, immutable balanced movements, source-aware refund integration |
| Settlement | existing settlement records retained | receivables/payables, statements, aging, reconciliation cases |
| Gift security/delivery | no redeemable token created for drafts | hashed single-purpose token, claim authorization, revocation, approved delivery |

All unfinished internal items remain development gaps, not external blockers.
Jabama supplied URL could not be retrieved by the browsing tool; no comparative
capability claim is based on that failed retrieval.

---

## فایل: docs/adr/ADR-023-inner-pages-refinement-on-production-2026-11.md

# ADR-023 — بازطراحی صفحات داخلی روی پایه `production` (جایگزین بخش کد ADR-022)

- تاریخ: ۱۴۰۵/۰۸/۲۶ (2026-11-16) · وضعیت: پذیرفته‌شده (تأیید مالک: «بله انجام بده»)
- زمینه: patch ADR-022 روی `main` قدیمی ساخته شده بود؛ سایت زنده روی `production` است که صفحات داخلی را با `ApprovedShell` (هدر/فوتر مصوب Figma، پالت plum/coral/cream) نمایش می‌دهد. اعمال ADR-022 هدر/فوتر مصوب و شماره پشتیبانی واقعی (`lib/site-contact.ts`) را بازنویسی می‌کرد.

## تصمیم
- هدر، فوتر، صفحه اول و صفحات JourneyShell **دست‌نخورده** می‌مانند (Protected).
- فقط محتوای صفحاتی که با `Shell` → `ApprovedShell` رندر می‌شوند (۱۷ صفحه، مثل /services، /contact، /terms، /register، /booking/confirmation) طبق طراحی Stitch اصلاح می‌شود: دکمه‌های pill و کورال، کارت‌های کرم با گوشه ۲۴px، برچسب‌های Mock طلایی، چت دستیار، جدول مقایسه، focus ring در دسترس.
- پیاده‌سازی: `components/marketplace/approved-inner-2026-11.css` با scope `.approved-site.ks-inner>main` و افزودن کلاس `ks-inner` به `ApprovedShell`.
- نوار ناوبری پایین موبایل اضافه **نشد**: ۴۷ صفحه JourneyShell آن را نداشتند و SupportDock دارند؛ افزودن فقط به ۱۷ صفحه ناوبری را ناهمگون می‌کرد.

## شواهد
- `tsc --noEmit` پاک، `next build --webpack` موفق.
- مقایسه پیکسلی صفحه اول قبل/بعد: بدون تفاوت (`getbbox()==None`).
- `/services` قبل/بعد: `docs/design/stitch-redesign-2026-11/qa/impl/services-before-after.png`.

## Rollback
- `git revert` این commit یا بازگرداندن image پشتیبان `karenseir-web:pre-redesign-*` روی سرور (`deploy/redesign-2026-11-rollback.sh`).

## افزوده ۱۴۰۵/۰۸/۲۶ — صفحات JourneyShell (۴۷ صفحه، تأیید مالک)
- لایه سبک یکدستی: دکمه‌های pill، primary کورال، secondary کرم، focus ring، برچسب Mock طلایی؛ هدر/فوتر/کارت جست‌وجو/SupportDock مستثنا.
- شواهد پیکسلی قبل/بعد: صفحه اول، /hotels، /flights، /account، /manage-booking، /restaurants بدون تفاوت؛ /trips، /tours، /support فقط دکمه‌ها (۱۱۹–۱۶۷ پیکسل). تصویر: `qa/impl/journey-trips-before-after.png`.

---

## فایل: docs/adr/ADR-024-vandapay-payment-gateway.md

# ADR-024 — VandaPay as KarenSeir payment gateway (2026-11-19)

**Status:** Merged and **superseded in implementation** by [ADR-029](ADR-029-federated-org-credit-and-vandapay-hardening.md) (2026-11-19): the PR #87 code (`providers.VandaPayAdapter` HTTP client, `_verify_vandapay`, `providers.vandapay_webhook_event`, `tests/test_vandapay_payment.py`) was replaced by the hardened #88 implementation (`app/vandapay.py`); main has exactly one VandaPay implementation. The product decisions below (VandaPay is the KarenSeir gateway, `VANDAPAY_MODE`, one `/payments/{id}/initiate`, success only server-side, issue only after capture) still hold. Still **disabled** until credentials (owner: VandaPay merchant onboarding).

## Context
Owner decision (1405-08-27): KarenSeir payments go through VandaPay (the group gateway). VandaPay plan:
`vandapay/docs/integration-plans/karenseir.md` (server-side API, hosted checkout, signed webhook, issue only after `succeeded`).
KarenSeir already had a provider-neutral Payment Intent flow (intent → initiate → return/verify → capture → ledger/outbox) wired to ZarinPal.

## Decision
- New `VandaPayAdapter` (backend/app/providers.py) behind the same `ADAPTERS["payment"]` slot. Selected when `VANDAPAY_MODE` ∈ {test, live}; takes precedence over ZarinPal.
- Fail-closed: mode/key prefix must match (`sk_test_`/`sk_live_`), base/return URLs must be HTTPS, otherwise health = `configuration_error` and `/payments/{id}/initiate` returns 503 before any attempt is recorded.
- Initiate: `POST /payment_intents` with `order_ref` = KarenSeir payment intent id, `Idempotency-Key` = intent command id, `return_url` carrying a signed short-lived state (aud `karenseir-vandapay-callback`).
- **Success is decided only server-side:** `GET /payment_intents/{id}` must return `succeeded` with the same amount and `order_ref`. Browser return (`GET /payments/vandapay/return`) and webhook (`POST /payments/vandapay/webhook`, HMAC `VandaPay-Signature`, 300 s tolerance) are only triggers.
- Pending (`processing`, `card_pending`, `unknown`…) → nothing captured, customer can re-check via `/payments/{id}/verify`. Failed/cancelled → intent `failed`.
- Capture reuses the existing ledger path (`commerce.record_payment`, PaymentEvent dedupe, Outbox, trip timeline). **Ticket issuance is unchanged: only after capture.**
- No price/amount is computed in the frontend; the amount is the reservation's bank-payable allocation.

## Not yet (owner decisions / VandaPay side)
- Merchant legal entity + SHEBA (Tazheban?), keys, webhook registration.
- ~~Cancel VandaPay intent when a supplier hold expires~~ — done in ADR-029 (`cancel_pending` + worker sweep).
- ~~Refunds via VandaPay~~ — done in ADR-029 (`POST /refunds/{id}/execute`, deterministic Idempotency-Key, `manual_review` for partial-card refunds).
- Hosted page vs embedded checkout (owner: customers should not leave the site → embedded option exists in VandaPay).

## Test evidence
`backend/tests/test_vandapay_payment.py` (7 tests): fail-closed config, idempotent initiate, amount tampering rejected, pending/failed not captured, signed webhook required and outcome re-read from API, cross-user isolation, single PaymentEvent. Full suite: 593 passed, 2 pre-existing failures unrelated (also fail on base).

## Rollback
`VANDAPAY_MODE=disabled` + `docker compose up -d --no-deps api` (ZarinPal/disabled path unchanged).

---

## فایل: docs/adr/ADR-024-visible-marketplace.md

# ADR-024 — Visible marketplace slices

Explicit user priority supersedes Homepage design freeze: preserve KarenSeir identity,
Vazirmatn and RTL, replace beige/orange/purple homepage treatment with navy/turquoise.
Use the proven current repository and deployment path; do not repeat forensic audit.
Migration 20260928_34 already applied under prior approval; no migration in Slice 1.

Slice 1: visible homepage marketplace, complete service navigation, editorial destination
and accommodation category discovery, prominent assistant prompt handoff, existing
vertical search widget reused. Editorial guides do not claim popularity/rating/price,
and no product cards or availability are fabricated. Assistant drafts require explicit
send; no automatic conversational/transactional operation. Search preserves existing
backend contracts; richer result/booking work remains in subsequent slices.

QA: production build, desktop/mobile browser, tab-specific controls, real route handoffs,
assistant prefill, navigation, public image/asset proof and screenshots. No SMS or money.
Rollback: preserve currently served frontend container/image; frontend-only replacement.
Master gap matrix remains cumulative; unreviewed baseline capabilities are not marked complete.

Slice 2 scope: use existing Offer/recheck/checkout contracts. Show flight number,
carrier, route, duration, stops, cabin, baggage and supplier only from supplied data;
missing stops must never silently mean nonstop. Replace generic empty result dead end
with date changes, editable criteria, transport alternatives and assistant handoff.
Flight landing uses actual search controls. No invented supplier result or hold.

Master autonomous directive is cumulative. Slice 2 also adopts the explicitly requested slogan «تمام سفر، در یک مسیر». Flight facts remain provider supplied; missing stops are unknown. QA uses isolated offers only. No schema change or live financial operation.

### Slice 3 — stay discovery and continuity
Public browser baseline: /hotels only ServiceIntro, /villas category context leads to authentication without usable filter form. Replace /hotels entry with hotel-default search and genuine category/editorial discovery. Accommodation filters/dates/guest count persist through login, property detail, refresh and return. Keep tenant-scoped catalog authorization; no public cross-tenant inventory exposure. Reuse quote/reservation/calendar APIs, no schema change. Render only supplied property amenities/media/rules. Desktop/mobile QA with isolated property + public empty/login handoff, then deploy frontend retaining current rollback.

### Slice 4 — tours and rail
Live browser /tours from homepage at desktop/mobile exposes a generic intro and login gate, without date/party filtering. Complete tour entry, preserve destination/date/party through account and PDP, reuse existing departures/quote/reservation, show supplied itinerary/inclusions only. Rail uses existing homepage search and contracted-offer API; improve rail-specific facts rather than make a parallel inventory model. Keep tenant scope and all external-provider gates. No schema or financial activation.
Slice 4 requires an API delta (not a schema change): optional tour date/party filters use a scoped departure EXISTS with capacity and booking deadline. The date is interpreted as a Tehran calendar day (+03:30), matching displayed departure dates. API test covers midnight boundary, capacity, deadline, invalid party and tenant exclusion. Tour retry command persists across refresh after a lost response. Preview visual review also exposed an auth-hydration race resetting edited catalog criteria; URL initialization is now independent of session loading and controls wait until initialization. No real transactions.

### Slice 5a — restaurant/experience continuity
Live browser verified restaurant editor selects flight because restaurant is absent from options. Search engine filters dated sessions for other leisure verticals but omits restaurant; 27 search application files match live source exactly. Correct category/date filtering, carry actual selected session and guest criteria to PDP/login, display real place amenities/rules and cancellation policy, and retain ticket selection across refresh. Restaurant copy describes scheduled service/admission, not a table assignment unsupported by the current model. No new table-inventory fiction, financial behavior, or migration. Search/API changes are additive/targeted; preserve both old containers when publishing.

Leisure quote/reservation retains only price-check ID and command ID in an account-scoped pending record before sending the booking command. After a lost response, refresh exposes a resume action with the exact original command; it does not silently create a new quote/booking. Backend replay now enforces original PriceCheck.user_id, closing a same-tenant cross-user replay gap. Tests: backend 2 PASS (owner isolation + Tehran date boundary); search 1 PASS across all four leisure verticals. No database migration.

Production search uses Redis (observed). Bump cache-key namespace with the changed date-filter semantics; retain old keys for natural TTL/rollback, never flush Redis. This is a search-only follow-up to the Slice 5a bundle, with frontend/API still built from 9cc109b.

### Slice 5b — pool/sport entry
Replace the legacy pool entry with destination/date/party discovery, embedded results and honest session-condition guidance. Reuse existing leisure detail, recheck and booking APIs; no new inventory model or schema. Validate URL party counts to safe form defaults. Isolated QA pool sessions and public anonymous desktop/mobile verification; retain frontend rollback.

Slice 5b visual gate found a shared search CSS defect: `.result-price .button.primary` consumes --coral, but JourneyShell does not define that legacy token. Browser computed background was transparent with white text (clickability tests alone missed it). Define navy/teal search tokens locally, preserving approved layout. Regression asserts computed opaque teal CTA plus desktop/mobile screenshot review; also covers restaurant and flight result contexts without new booking transactions.

### Slice 5c — attraction entry and ticket conditions
Observed public desktop/mobile attraction route has duplicate h1 and no dedicated search form. Reuse pool discovery form with an explicit service configuration; keep pool route and labels unchanged. Display only API-supplied ticket minimum/maximum ages and entry_rules beside each ticket. These are conditions, not a new age-verification promise. No new API/schema/provider behavior. Verify isolated attraction session-to-booking and pool form regression, then public anonymous journey.

### Slice 5d — event discovery and human inquiry
Public event route has duplicate headings and no inquiry handoff. Add event discovery on shared form and an explicit human inquiry path using existing support/cases API, not a new RFQ/booking model. Product-specific inquiry loads scoped product facts first. Customer receives a support case ID and real messages; no price, capacity, hold or response-time promise. Persist exact pending payload/command per account/service/product for ambiguous response retry. BackOffice already consumes the same cases. All submissions/replies in verification use isolated QA; no production SMS/payment.

QA contract correction: support fields are nullable, but _owned_support_scope requires exactly one trip/reservation. Permit only SERVICE_INQUIRY with both absent; all supplied references still undergo unchanged ownership checks, all ordinary cases still require one anchor. Existing authenticated user ownership, replay payload matching and scoped case listing remain enforced. No schema change. Targeted contract test required before API/worker release.

### Slice 6 — customer case navigation and reply
Public frontend with isolated authenticated API shows support cards with zero links and raw in_progress status. Add scoped case detail and owned customer reply using existing SupportThreadMessage, IdempotencyKey and OutboxEvent tables. Lock case for serialization; replay original response before checking closed state, reject altered payload. Closed/resolved cases remain read-only. No financial decision, schema change or real notification test. Customer→case→reply→Ops and refresh/replay/ownership targeted verification required.

### Slice 7 — generic booking continuity
Public frontend + scoped QA confirms generic result links omit criteria and detail back link drops search. Generic detail command exists only in memory; inline results generate a fresh command each attempt. Share one account-scoped pending booking record across result/detail surfaces, retaining exact price-check/command through ambiguous response and refresh. Disable new recheck/booking until resolved; backend consumed-price-check/ownership gates unchanged. Carry search context in generic detail links and back link; persist explicitly chosen unit count, without inferring infant fares or group pricing. Normalize scoped leisure/support desktop heading size found during visual review. Frontend-only; no real transaction.

Slice 7 follow-up: preserve explicit offer query through ErrorState login redirect (other callers keep existing default). Invalidated price checks remove previous confirmation/continue action and require recheck. If sessionStorage cannot retain the pending command, do not send a booking mutation; display recovery guidance.

### Slice 8 — in-app support response notification
QA baseline has six cases with human replies and zero linked inbox notifications. Reuse notification fanout with optional channel restriction (default unchanged), explicitly web/app only for support response. Add semantic support_reply_received template and case deep link. Add owned, idempotent mark-read endpoint using existing status field; worker must preserve read instead of overwriting it with transport status. UI delivery does not imply reading, shows Persian topics and explicit read action. No external delivery attempt for support response; no migration or production test messages.

### Slice 9 — supplied transport times and contextual recovery
Format valid ISO transport dates with the supplied wall clock and offset; never browser-local conversion or guessed airport timezone. Bare times retain no-zone disclosure, invalid/missing dates remain unavailable. Preserve original ISO in datetime. Share flight/rail renderer; anonymous offer wrapper retains navy/teal and back-to-search context. Notification count describes only the loaded latest50, not all historical unread records. No booking mutation/API/schema change.

### Slice 10 — durable human support reply
Reuse case lock and existing idempotency table for supplied human-reply keys, hashing actor/body and replaying before closed-state guard. Optional header preserves older clients during API-first release; new UI always supplies durable key. Atomic audit/message/in-app notice/outbox; no external channels. New account-scoped Ops composer retains exact case/body/key through ambiguous response/refresh. Storage failure blocks any new reply POST, including existing customer composer. No schema change. Verify response-loss replay produces one message/notice/audit.

### Slice 11 — rental date-range continuity
Public1440/390 accepts reverse rental dates. Validate actual calendar dates and end>=start at entry and shared search before API requests; same-day remains allowed because no new rental policy is inferred. Preserve return for non-flight verticals regardless of inherited one-way flight flag. Clear stale results on invalid rental range, expose truthful corrective error. No inventory/price/booking/backend change.

### Product Slice 12 — flight party integrity through post-booking
Priority supersedes standalone saved-search bug. Close one-way adult flight journey using existing authoritative per-seat contract: search party→detail/recheck units→exact distinct passengers→checkout→isolated payment→manual supplier confirmation/voucher→trips/timeline→cancellation request. Never infer child/infant fares or a return leg from one offer; these requests require explicit separate quote and retain search context. Save/replay criteria in the same slice. Existing supplier/payment/OTP boundaries remain externally blocked in production. No schema or financial policy change. Acceptance requires full isolated browser journey at desktop/mobile, adverse-count/replay/permission tests, public build proof, screenshot comparison. A passing partial checkout is not full-slice completion.

Slice12 self-review: complete isolated flight happy path exposed stale post-request status and no persistent customer request list. Add owner-scoped request history on existing table, enforce owner/hash before replay and prevent multiple submitted requests. Refresh authoritative state after request; retain exact pending request across ambiguous failure/refresh, fail closed if browser cannot persist it. Pending cancellation/refund means review, never completed refund or newly unissued documents. No change to cancellation policy or voucher validity rules.

Operations boundary: an owned customer request must be visible to authorized support staff. Add paginated tenant-scoped review queue and idempotent begin-review action, audited through existing outbox and visible in customer timeline. This only acknowledges review; no cancellation decision, financial approval, refund execution, supplier confirmation or SMS is performed. Unknown statuses remain explicitly unknown.

### Major accommodation journey follow-up (2026-09-29)
Live hotel discovery leads to an authentication wall before any catalog. Add anonymous read-only accommodation discovery/detail using only the existing dedicated karenseir-public catalog identity; never fall back to corporate/consumer inventory or copy offers across tenants. Public output is a strict presentation allowlist without rates, capacity counts or private supplier fields. Authenticated quote/booking remains scoped to the customer's own tenant; absent account entitlement has an explicit recovery path, not a fabricated booking bridge. Gallery/host presentation uses only explicitly supplied presentation fields, with no invented images/ratings. Close durable stay booking response-loss/refresh recovery, storage failure and stale quote handling within the same journey. No schema migration or production seed. Acceptance: tenant-isolation API tests, actual desktop/mobile catalog/detail/recheck/host decision/checkout/trip QA, empty/unavailable public recovery, existing rollback preserved.

### Major Tour journey follow-up (2026-09-29)
Close public program discovery, actual selectable departure/room pricing, durable reservation recovery and full owned checkout/voucher/trip flow. Base tour price retains its existing default double-room contract; other room types require an explicitly supplied integer surcharge (including explicit zero), never an inferred free upgrade. Expired departures are not selectable. Anonymous projection uses only the existing public catalog identity and program/date presentation, not private rates or supplier payloads. No cross-tenant purchase entitlement is inferred. Price expiry, changing quote inputs and storage failures fail closed. Acceptance: room/deadline/tenant/replay API checks plus desktop/mobile isolated customer journey through distinct travellers, payment test destination, voucher and after-sales tracking. No migration or real financial/SMS operation.

### Major Train group journey follow-up (2026-09-29)
Public frontend + isolated QA proved two searched adults produce a one-seat inline quote and one-seat detail at both widths. Propagate the adult party through inline and detail quote→reserved units→distinct checkout travellers and server-calculated total. Add optional train_party to the existing price-check contract with the same count validation as flight; no child/infant/roundtrip fare or seat-number allocation is inferred. Preserve generic durable booking and after-sales paths. Acceptance includes full isolated two-person rail checkout/payment/voucher/trip/Operations journey and unsupported-party recovery; flight validator regression only, not unrelated suites. No migrations or real financial/SMS operations.

### Major scheduled restaurant admission journey (2026-09-29)
Public frontend + isolated QA reproduced validating ticket A, editing the input while validation was pending, then sending ticket B for redemption. Both widths reproduced; redemption was intercepted and never executed. Close the whole restaurant scheduled-ticket journey: durable booking, group QR context, supplier validation bound to the checked ticket, single-use admission and customer timeline. Add a body-based no-store validation route so the active UI no longer sends the bearer QR in a URL. Retain the legacy GET contract and existing time/permission rules; do not invent table inventory or early-admission policy. Show server-backed product/place/session and immutable booked item quantities; one generated QR covers the reservation, not one separately allocated seat/person. Add optional expected_ticket_id to redeem for fail-closed mismatches. Customer QR loading failures remain recoverable without hiding other ticket information. All tests use isolated fixtures and non-financial adapters; no Production redemption, payment, SMS or migration.

### Host content to customer booking journey (2026-09-29)
Existing assigned hosts can manage availability but cannot maintain customer-facing facts. Add a scoped content editor for existing properties, strict non-financial presentation fields, original details preservation, optimistic revision and idempotent durable commands. No ownership/status/booking-mode/cancellation-price/publication change. Public catalog remains isolated. Audit old/new presentation changes through existing outbox/audit; no migration. Acceptance: assigned host update/replay/conflict/denial, customer presentation→quote→request→host acceptance→existing isolated checkout/voucher/trip. Rollback preserves previous API/web; existing details schema is compatible.

### Saved selection to reservation journey (2026-09-29)
Saved offers are currently a text-only dead end. Preserve bounded selection criteria with saved offer, provide owned detail/recheck handoff, bind a resulting reservation and Trip back to the same saved item transactionally. Existing snapshot JSON stores linkage; no migration, automatic purchase, merged itinerary or cross-tenant selection. Lock owned saved item and reject repeat new booking; exact orchestration replay retains original linkage. Personal notes remain non-bookable notes. Prices remain server-authoritative, saved prices never availability promises. Acceptance: search/save/refresh/detail/party/recheck/booking replay/isolated payment/voucher/saved tracking/My Trips at1440/390, ownership/mismatched-offer denial and duplicate guard. Preserve previous images for rollback.

### Enterprise approved request to reservation tracking (SOURCE/PREVIEW)
Close ADR-023 request-to-reservation tracking gap using explicit tenant-scoped EnterpriseBookingLink (incremental schema35). An approved request can be linked only by its requester to their own existing nonterminal reservation of a requested service. Organization request viewers can see booking reference/status through authorized request endpoint, not impersonate customer or access their payment/voucher APIs. This is traceability only: it creates no booking, funding, entitlement, organizational payment authorization or financial commitment. Existing customer checkout remains authoritative. Unique tenant/reservation linkage and idempotency, audit/outbox, requester Trip event. No group-delegated booking or selected-RFQ commercial fulfilment inferred. Production migration and release withheld pending explicit schema35 approval; preserve schema34 runtime/rollback. Test tenant/role/owner/approved state/replay and real browser request→approval→customer booking linkage→organization tracking.

---

## فایل: docs/adr/ADR-025-hotel-stay-integrity.md

# ADR025 — fixed-stay hotel quote integrity (SOURCE/PREVIEW)

An Offer is not a date-independent hotel room. The reproduced two-room search currently
quotes one unit without dates. Reuse Offer/PriceCheck/BookingItem snapshots; no new DB
or provider engine is introduced. Manual hotel allotments must explicitly declare
`hotel_rate`: check_in, check_out, room_type, rate_plan, price_basis=room_stay,
occupancy={adults, children_ages}. Amount is the supplier's complete price per room
for that exact stay and occupancy. Each requested room must match that supplied rate;
no inferred child price, extra bed, daily stock or alternative rate. Missing/mismatched
terms fail closed. Mixed room/rate booking remains a separately scoped capability.

Customer selection carries dates and per-room allocation into the immutable quote,
reservation and checkout. Existing rows/documents remain readable. New hotel quotes
without the contract are rejected; callers/tests must supply explicit terms. A change
in terms between quote and reservation requires a fresh quote. Provider-mode offers
remain blocked by the existing real-provider gate.

Acceptance: two rooms/four adults preserve dates, amount, allocation and traveller
count; mismatched stay, occupancy, omitted contract, command reuse and changed terms
cannot book. Search shortcuts must go through the allocation page. Tests use isolated
labeled fixtures, never Production stock/payment/SMS. No production publication here;
current unpublished schema35 still needs approval. Rollback: revert candidate code;
no schema/data reversal required for this change. Whole-hotel closure remains open.


---

## فایل: docs/adr/ADR-026-worker-reaper-permission-boundary.md

# ADR026 — worker/reaper privilege boundary

## Related operational blocker discovered during verification
The unchanged live worker uses karenseir_worker (BYPASSRLS, non-superuser).
Its provision script explicitly REVOKEs reservations/financial table privileges.
The unconditional reservation reaper crashes every twelfth loop with PostgreSQL
42501. Do not grant this cross-tenant notification role booking/financial access.
Gate the reaper with an explicit opt-in, default off; report disabled status in
worker health. An authorized separately scoped reaper deployment remains required
for automatic hold expiry. This correction does not expire/release any real hold.
Production worker rollout needs explicit approval; no migration35 is necessary
for a worker-only artifact based on the current live backend plus this exact file.

---

## فایل: docs/adr/ADR-027-historical-homepage-recovery.md

# ADR027 — historical presentation recovery, Preview only

User authorizes76bea5c (=2255a05 parent) as historical recovery reference; Figma validation remains pending. Never roll back repository/runtime. Reuse historical Hero, mosaic, editorial trips, comparison, full footer and scroll-aware assistant implementation with original tracked assets. Keep current Search, service routes, AI prompt handoff, accommodation discovery and organization/customer workflows. Navy/turquoise/Vazirmatn/RTL and current slogan supersede historical plum/coral styling. Historical layout preserved; no invented inventory or prices.

Scope: frontend components and scoped CSS only. No backend/DB/Worker/runtime changes. Independent historical builds and Candidate run loopback-only. QA: seven requested viewport screenshots; historical/current/candidate comparison, original assets audit, current route inventory, Search controls, isolated hotel booking/test payment/voucher desktop/mobile, customer/support/account gates. Preserve Production rollbacks. Candidate release readiness is separate from Figma matching and real external integrations. Rollback Source by reverting only this scoped presentation commit; do not revert booking71801f8.

---

## فایل: docs/adr/ADR-028-master-catalog-data.md

# ADR028 — Master catalog data, separate from commercial data

## Decision
Real, relatively static reference records (places, hotels, airlines, airports, rail operators and stations, venues) live in
global `catalog_*` tables (`backend/app/catalog.py`, migration `20261003_36`). They have no `tenant_id` and no price, offer,
availability, inventory, room, seat, rating or review column. The API role gets `SELECT` only; rows are written by
`backend/scripts/catalog/import_catalog.py` under the owner role. Supplier offers, rates and bookings stay in the existing
tenant-scoped tables and will reference catalog ids when a real provider is mapped — the catalog is never rebuilt for pricing.

## Sources and provenance
OpenStreetMap via Overpass (ODbL, attribution shown in the UI), Wikidata (CC0), OurAirports (public domain), Wikimedia
Commons images (per-file author and licence stored in `image_credit`), operators' own websites for rail companies. Every row
stores `source`, `source_ref`, `source_license`, `retrieved_on`. `backend/catalog_data/MANIFEST.json` records counts.

## Pipeline
`fetch_osm.py` / `fetch_reference.py` (raw cache, not committed) → `build_catalog.py` (normalize, validate, deduplicate,
attach images only when the source ties the file to that exact record) → `catalog_data/*.json.gz` → `import_catalog.py`
(idempotent upsert, stale rows removed).

## Rules
- No fabricated commercial data. Every catalog response carries `price: null`, `price_status: "inquiry"`.
- An image shared by more than one record is dropped; records without a verified image render a neutral non-photo header.
- Turkey is limited to the tourism provinces relevant to the Iranian market; other countries are covered country-wide.

## Rollback
Frontend: redeploy the previous image. Backend: `alembic downgrade 20260929_35` drops only the `catalog_*` tables; no
existing table is altered.

---

## فایل: docs/adr/ADR-029-federated-org-credit-and-vandapay-hardening.md

# ADR-029 (در شاخهٔ قدیمی: ADR-022) — اعتبار سازمانی فدرال (یک دفتر مالک برای هر برنامهٔ اعتبار) و سخت‌سازی اتصال ونداپی

وضعیت: پذیرفته‌شده — ۱۴۰۵/۰۸/۲۷ (۲۰۲۶-۱۱-۱۸). تکمیل‌کنندهٔ ADR-021 (جایگزین آن نیست).


## Port to main — 2026-11-19 (one VandaPay implementation)
Status: **ported onto `main`** (PR "VandaPay: one implementation"). Supersedes the simpler PR #87 code path described in
[ADR-024](ADR-024-vandapay-payment-gateway.md); main keeps exactly **one** VandaPay implementation:

- Code: `backend/app/vandapay.py` (client, `Idempotency-Key`, HMAC webhook verification with the shared vectors in
  `backend/tests/fixtures/vandapay_webhook_vectors.json`, intent evaluation) + the VandaPay block in `backend/app/main.py`
  (initiate, settle, refunds, late capture, org approval, hold-release cancel sweep) + `operations.request_external_payment_void`
  + the outbox-worker sweep. `providers.VandaPayAdapter` is only a health shell for the `ADAPTERS["payment"]` slot so a
  misconfigured VandaPay fails closed (503) instead of falling back to ZarinPal; it never moves money.
- Routes: initiation is the single generic `POST /payments/{id}/initiate` (the old `/payments/{id}/vandapay/initiate` is
  **not** ported); exactly one `GET /payments/vandapay/return` and one `POST /payments/vandapay/webhook`; `GET /payments/methods`
  (label / test-mode label); `POST /payments/{id}/verify` re-reads VandaPay server-side.
- Configuration adapted to main (ADR-024 names): `VANDAPAY_MODE=disabled|test|live` (default **disabled**; replaces
  `VANDAPAY_ENABLED`), `VANDAPAY_BASE_URL` (replaces `VANDAPAY_API_BASE`; required, no hard-coded default),
  `VANDAPAY_SECRET_KEY` / `VANDAPAY_WEBHOOK_SECRET` via `read_secret` (`*_FILE` supported), `VANDAPAY_RETURN_URL` (https).
  Key prefix must match the mode; `sk_live_` only in production; `sk_test_` in production only with `DEMO_MODE`.
  `PAYMENT_PROVIDER=sandbox` (QA/staging gateway) takes precedence. `VANDAPAY_CATEGORY` is gone (explicit category map).
- Return state: main's per-purpose key (`_signing_key("payment_state")` / `_decode_payment_state`), aud
  `karenseir-vandapay-callback`, claims include `amount` (must equal the intent). Browsers are redirected to `/payments/{id}`.
- Capture also posts to the commerce treasury (`commerce.record_payment`) like every other gateway capture on main.
- Item 1 (exclusive funding source) and item 2 (credit-only issuance) are enforced on main by the newer funding plan
  (`funding_references.bank_payable` in `/payments/{id}/initiate`, `fully_funded_without_bank` in
  `_reservation_settlement_ready`); the old `_internal_ledger_funding` guard and the `reservation.funded_by_internal_ledger`
  event were not ported. `metadata.internal_funding_amount` is still sent (information only).
- Item 3 (refunds) uses main's refund review: a customer request is `requested` only with a verified policy quote on a
  cancellation-state reservation, else `pending_review`. The VandaPay refund runs automatically only when the reservation is
  `cancelled`; otherwise finance approves with `POST /refunds/{id}/review` and executes with **`POST /refunds/{id}/execute`**
  (`refund:manage`). (`/finance/refunds/{id}/execute` on main belongs to the after-sales maker-checker, whose `gateway`
  method stays refused — wiring VandaPay into that flow is open work.) `processing` and `manual_review` count against the
  refundable remainder (`REFUND_SETTLED_STATUSES`).
- No migration (status columns are free-text; `organization_credit_ledger` already exists as `20260823_19`).
- Rollback: `VANDAPAY_MODE=disabled` (all VandaPay routes 404, sweep no-op) or revert the commit.

## زمینه
ممیزی گروهی درگاه (`gw-audit/10-tourism.md` ردیف‌های K1–K8 و `VERIFICATION.md` §ب ردیف‌های 35–40، روی `f6af234`) این کمبودها را در کد تأیید کرد:
استرداد ونداپی وصل نبود و `refund.*` فقط لاگ می‌شد (K1)؛ intent باز ونداپی پس از آزاد شدن hold لغو نمی‌شد (K2)؛ `requires_org_approval` رسیدگی صریح نداشت (K3)؛ `customer_phone`، دستهٔ هر محصول و اقلام فرستاده نمی‌شد (K4/K5)؛ خطر خرج یک اعتبار در دو دفتر (K6)؛ رزرو کاملاً اعتباری صادر نمی‌شد و `fulfill` خطای 409 می‌داد (K7).

## تصمیم مالک (۲۰۲۶-۱۱-۱۸) — مدل فدرال اعتبار
- کارن‌سیر می‌تواند **اعتبار سازمانی خودش** را مستقل صادر کند (قرارداد و دفتر خودش: `CreditAccount` + `financial_ledger_entries`) و **اختیاری** آن را به ونداپی وصل کند.
- برای هر **برنامهٔ اعتبار** دقیقاً **یک دفتر مالک** وجود دارد: یا دفتر کارن‌سیر یا دفتر ونداپی. یک اعتبار هرگز در دو دفتر خرج نمی‌شود.
- پیاده‌سازی موقت بدون migration: `VANDAPAY_FEDERATED_CREDIT_ORGANIZATION_IDS` (شناسهٔ سازمان‌هایی که دفتر مالکشان ونداپی است). برای این سازمان‌ها مرحلهٔ `funding` رزرو اعتبار داخلی را با 409 رد می‌کند؛ اعتبارشان فقط در صفحهٔ پرداخت ونداپی خرج می‌شود. پیش‌فرض خالی = همهٔ اعتبارهای داخلی مالِ دفتر کارن‌سیرند. وقتی اتصال واقعی شد، این به ستون `credit_accounts.owning_ledger` (migration جدا با gate) منتقل می‌شود.

## تصمیم‌های فنی (همه پشت `VANDAPAY_MODE`، پیش‌فرض `disabled`)
1. **انتخاب انحصاری منبع پرداخت:** `initiate` ونداپی فقط وقتی مجاز است که `مبلغ intent + مانده‌ٔ متعهد کیف/اعتبار داخلی برای همین رزرو == مبلغ کل رزرو`؛ وگرنه 409 و هیچ فراخوانی به ونداپی. یعنی ونداپی فقط بخشی را می‌گیرد که در دفتر کارن‌سیر نیست. `metadata.internal_funding_amount` برای تطبیق فرستاده می‌شود. رزرو آزادشده (cancelled/failed/expired) قابل پرداخت نیست.
2. **رزرو کاملاً اعتباری (K7):** `fulfill` بدون capture کارت فقط وقتی مجاز است که (الف) checkout سرور `payable_amount=0` ثبت کرده و در `awaiting_fulfillment` است، (ب) خالص رزرو دفتر داخلی برای رزرو دقیقاً برابر مبلغ کل است، (ج) هیچ PaymentIntent غیرناموفقی (ونداپی یا دیگر) برای آن رزرو نیست. رویداد `reservation.funded_by_internal_ledger` با تفکیک کیف/اعتبار ثبت می‌شود (ممیزی). capture اعتبار همان مسیر موجود `settle_reservation_funding` است.
3. **استرداد (K1):** کلاینت `refund()` با `Idempotency-Key = karenseir-{tenant}-refund-{refund_id}` (ثابت در هر تلاش ⇒ تکرار پس از timeout دو بار پول برنمی‌گرداند).
   - **اصلاح دستور بالادستی (supervisor):** `POST /payments/{id}/refunds` را مشتری صدا می‌زند؛ اجرای مستقیم استرداد از آن یعنی مشتری می‌تواند بدون لغو تأمین‌کننده پولش را پس بگیرد. پس اجرای خودکار **فقط** وقتی است که رزرو `cancelled` (لغو نهایی تأمین‌کننده) باشد و مجموع استرداد ≤ `refundable_amount` سیاست امضاشدهٔ لحظهٔ رزرو. در غیر این صورت رکورد `requested` می‌ماند و مالی با `POST /refunds/{id}/review` و سپس `POST /refunds/{id}/execute` (مجوز `refund:manage`؛ نسخهٔ main) اجرا می‌کند.
   - وضعیت‌ها: `requested` (ثبت، بدون مجوز) ← `processing` (مجاز؛ پیش از هر حرکت پول commit می‌شود) ← `succeeded` | `failed` | `manual_review`. `requested/processing/manual_review` همه از ماندهٔ قابل استرداد کم می‌شوند.
   - `201 succeeded` ⇒ ثبت فوری. `202 pending` ⇒ `provider_reference` ذخیره و منتظر وب‌هوک. `422 partial_refund_unsupported`/`split_refund_manual_review` ⇒ `manual_review` + رویداد outbox برای انتقال بانکی دستی. خطای موقت ⇒ `processing` می‌ماند و sweep یا تکرار همان `command_id` با همان کلید دوباره می‌فرستد.
   - وب‌هوک `refund.*`: intent از API بازخوانی و وضعیت استرداد از فهرست `refunds` **پاسخ API** خوانده می‌شود (نه رویداد). `refund.succeeded` که API هنوز تأیید نکرده ⇒ 503. استردادی که بیرون از کارن‌سیر (پنل ونداپی) انجام شده و API تأییدش می‌کند ثبت می‌شود (پول واقعاً برگشته). سقف: `refunded ≤ captured` وگرنه `manual_review`.
4. **لغو intent هنگام آزاد شدن hold (K2):** گذار رزرو به `cancelled/failed/expired` (تنها نقطهٔ مشترک `transition_reservation`) intentهای ونداپی `initiated` را `cancel_pending` + outbox می‌کند (بدون شبکه در `operations.py`). `vandapay_sweep` در حلقهٔ outbox worker، tenant به tenant با `set_tenant_context`، `POST …/cancel` را با کلید ثابت می‌فرستد و وضعیت را از API بازخوانی می‌کند. اگر ونداپی دیگر قابل لغو نبود و پول گرفته شده بود ⇒ **late capture**: capture ثبت می‌شود (پول واقعاً جابه‌جا شده)، رزرو **صادر نمی‌شود** و استرداد کامل خودکار ساخته و اجرا می‌شود.
5. **`requires_org_approval` (K3) — سیاست صریح:** همیشه «در انتظار» است، هرگز پرداخت‌شده؛ PaymentIntent در `initiated` می‌ماند؛ یک رویداد Timeline «در انتظار تأیید سازمان (حداکثر ۴۸ ساعت)» (idempotent) ثبت و بازگشت مرورگر `payment_status=pending_org_approval` نشان می‌دهد. کارن‌سیر hold تأمین‌کننده را نه تمدید می‌کند نه به‌خاطر این وضعیت آزاد می‌کند؛ تا تأیید، `fulfill` 409 است. اگر hold تأمین‌کننده زودتر تمام شود (رزرو expired/cancelled) ⇒ intent لغو می‌شود (ونداپی درخواست سازمان را پس می‌گیرد و holdهایش را آزاد می‌کند)؛ captureای که از این مسابقه رد شود late capture ⇒ استرداد کامل. **Fail-safe: صادر نکن، «در انتظار» نشان بده.**
6. **دسته، موبایل، اقلام (K4/K5):** `category` با نگاشت صریح `flight→travel.flight`، `hotel|accommodation|vacation_rental→travel.hotel`، `tour|package→travel.tour`، `train→travel.train`، `bus|tourist_transportation→travel.bus`؛ هر چیز دیگر `travel` (مقدار قبلی). `customer_phone` فقط اگر شناسهٔ ورود (OTP) کاربر یک موبایل معتبر ایرانی باشد؛ امروز شناسه‌ها ایمیل‌اند پس فرستاده نمی‌شود (هرگز حدس زده نمی‌شود). `items` فقط برای رزرو تک‌قلمی (یک خط = کل مبلغ intent)؛ رزرو چندقلمی تفکیک معتبر ندارد ⇒ بدون اقلام.
7. **انقضای intent:** `VANDAPAY_INTENT_EXPIRES_IN_SECONDS` (اختیاری، ۳۰۰ تا ۲۵۹۲۰۰) ⇒ فیلد `expires_in_seconds` (پیشنهاد VP-01 در مخزن ونداپی؛ هنوز ادغام نشده). خالی/نامعتبر ⇒ فیلد فرستاده نمی‌شود = رفتار فعلی (TTL پیش‌فرض ۳۰ دقیقهٔ ونداپی).

## خارج از دامنه (ثبت‌شده)
- K8: `reverse_capture` سهم اعتبار داخلی هنگام استرداد پس از صدور.
- منبع موبایل تأییدشده (ستون/OTP پیامکی) — SMS هنوز READY_BLOCKED_EXTERNAL است.
- ستون `owning_ledger` (migration).

## پذیرش
`backend/tests/test_vandapay_hardening.py` + `backend/tests/test_vandapay.py` (MOCK برچسب‌خورده؛ پس از port روی main: ۳۱ آزمون) + آزمون‌های مالی موجود.

## Rollback
`VANDAPAY_MODE=disabled` (sweep و همهٔ مسیرهای ونداپی بی‌اثر می‌شوند) یا revert کامیت. بدون migration. تنها تغییر رفتاری بدون پرچم: مسیر fulfill کاملاً اعتباری و رد رزرو اعتبار سازمان‌های فدرال (فقط اگر env تنظیم شود).

---

## فایل: docs/adr/ADR-030-injast-second-payment-gateway.md

# ADR-030 — اینجاست (Injast) به‌عنوان درگاه دوم، کنار ونداپی

وضعیت: پیشنهادشده — ۱۴۰۵/۰۹/۰۲ (2026-11-23). شاخهٔ `feat/injast-gateway`. تکمیل‌کنندهٔ ADR-024/029 است و جایگزین آن‌ها نیست.

## زمینه
مالک خواست درگاه اینجاست (مستند IPM نسخهٔ 1.05.14) روی کارن تراول و چک‌لاین نصب شود. برای کارن تراول دو تصمیم گرفت (۱۴۰۵/۰۹/۰۲): اینجاست **کنار** ونداپی باشد و مشتری درگاه را انتخاب کند. merchant کارن تراول هم از چک‌لاین **جدا** باشد.

## تصمیم
1. یک آداپتور مستقل `backend/app/injast.py` ساخته می‌شود و با `INJAST_MODE=disabled|live` به‌صورت پیش‌فرض خاموش است (fail-closed).
2. مسیر initiate همان `POST /payments/{id}/initiate` است. بدنهٔ اختیاری `{"gateway":"injast","national_id":…}` اینجاست را انتخاب می‌کند. اگر بدنه نباشد، رفتار ونداپی یا رفتار قبلی **بدون تغییر** اجرا می‌شود. `GET /payments/methods` هر دو درگاه را برمی‌گرداند و برای اینجاست `requires:["national_id"]` را هم اعلام می‌کند.
3. چون callback اینجاست امضا ندارد، فقط «خبر» حساب می‌شود. پول فقط وقتی ثبت می‌شود که confirm-pay سمت سرور موفق باشد، آن هم برای فاکتوری که خود ما ساخته‌ایم (در idempotency_keys با scope `payment.injast.invoice`) و با مبلغ ثبت‌شدهٔ خودمان.
4. هیچ تماس شبکه‌ای در زمان نگه‌داشتن قفل ردیف انجام نمی‌شود. این کار سه مرحله دارد: نشانهٔ پایدار و commit، تماس شبکه، سپس قفل دوباره و اعمال نتیجه.
5. اگر پاسخ confirm گم شود، sweep در worker آن را دوباره اجرا می‌کند. پاسخ `INVOICE_ALREADY_VERIFIED` فقط وقتی پذیرفته می‌شود که قبلاً confirm از طرف ما ارسال شده باشد. در غیر این صورت بررسی انسانی لازم است.
6. اینجاست API استرداد ندارد. پرداخت دیرهنگام یا تکراری ثبت می‌شود و `RefundRecord` با وضعیت `manual_review` می‌سازد. صدور رزرو انجام نمی‌شود.
7. کد ملی خام ذخیره نمی‌شود و فقط hash آن نگه داشته می‌شود. کد ملی فقط برای ساخت فاکتور و لینک پرداخت استفاده می‌شود.
8. migration لازم نیست.

## پیامدها
- با گرفتن merchant_id و ثبت IP سرور، می‌شود اینجاست را با تغییر env روشن کرد، بدون تغییر کد.
- ریسک باقی‌مانده: یک Failed یا Expired جعلی می‌تواند صفحهٔ وضعیت را «ناموفق» نشان دهد. پرداخت واقعیِ بعدی همان فاکتور باز هم ثبت می‌شود. رفع کامل این ریسک به امضای callback یا endpoint استعلام از طرف اینجاست بستگی دارد (سؤال‌های ۱ و ۲ در `docs/payments/INJAST_INTEGRATION.md`).

## Rollback
`INJAST_MODE=disabled` (پیش‌فرض)، یا revert همین PR. داده‌ای مهاجرت داده نمی‌شود.
