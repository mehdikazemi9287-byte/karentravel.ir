# Implementation Roadmap

## Search UX gate — PASS — 2026-08-21

The existing Homepage Search Box now exposes the completed backend capabilities through accessible autocomplete, date flexibility, passenger/room/cabin controls, trip type and URL-restorable submission. The dedicated results route provides real authenticated Offer cards, filters, sorting, comparison and complete operational states on Desktop and Mobile. Six visual evidence files and `16/16` Chromium scenarios are green.

Next exact gate: provide one authorized sandbox travel-provider credential and certify bounded fan-out, partial failure, provider P50/P95 and dated fare availability. Do not add price hints/calendar values until a real feed supplies them.

## Unified Search next gate — 2026-08-21

Credential-independent Search v2 is complete through normalization, entity/autocomplete, shared multi-vertical contracts, freshness/availability/price states, deduplication, explainable ranking, filters/flexible intent, saved history, natural-language structuring, budget candidates and zero-result recovery. Migration head is `20260820_13`; PostgreSQL `67/67` RLS/FORCE and backend `87/87` are green.

Next exact gate: provide one authorized sandbox travel-provider credential, then certify bounded concurrent fan-out, timeout/partial-failure isolation, provider/vertical TTL cache keys, hit rate and Search/provider P50/P95 without changing Homepage. Price calendar and alerts remain inactive until real feeds/transports exist.

## Next exact release gate

اقدام دقیق بعدی: فراهم‌کردن PostgreSQL ایزوله روی میزبان validation، backup گرفتن از همان staging، اجرای migration `20260820_11` و اثبات fail-closed/cross-tenant/FORCE RLS برای هر ۷ جدول تازه؛ سپس اجرای backend بدون skip. بعد از آن، ZarinPal adapter request/verify با credential sandbox معتبر و unified checkout تکمیل می‌شود. تا پیش از این gate هیچ موفقیت پرداخت یا RLS واقعی جدید ادعا نمی‌شود.

در scope جدید Product Ecosystem، Phase 1 و Search 2.0 داخلی بسته شده‌اند. اقدام داخلی دقیق بعدی: migration افزایشی tenant-RLS برای persisted Trip Basket/Wishlist و Verified Review، سپس APIهای idempotent و تست cross-tenant آن‌ها؛ Homepage frozen می‌ماند و UI فقط در routeهای اختصاصی افزوده می‌شود.

تمام کارهای credential-independent این مرحله، شامل اجرای واقعی migration `20260820_10`، RLS/FORCE RLS هر ۵۶ جدول، backup→restore، rollback→upgrade، integrity و regression کامل شده‌اند. اقدام بعدی به‌صورت دقیق: دریافت target مجاز و Secret Manager references، build imageهای immutable و ثبت digest، سپس اجرای public readiness، restore و rollback smoke gate پیش از هر ترافیک. اتصال Providerها فقط پس از قرارداد و credential معتبر انجام می‌شود.

| فاز | خروجی آزمون‌پذیر | معیار پذیرش |
|---|---|---|
| 0: Discovery/UI | اسناد + Prototype فعلی | build/lint سبز، مرور Desktop/Mobile و تأیید UI |
| 1: Foundation | FastAPI modular monolith، identity، tenant، RLS، audit | migration و isolation test واقعی |
| 2: Corporate pilot | catalog/manual hotel، policy، credit، approval، ledger | lifecycle رزرو end-to-end و reconciliation test |
| 3: Integrations | adapters و hub | fail-closed، idempotency، routing و observability test |
| 4: Scale | payment/settlement، API/widget، white label | security، DR و load acceptance |
| 5: Intelligence | tool-backed assistant و comparison | no-hallucination evaluation و explanation audit |

هر فاز ADR، acceptance criteria، security review، rollout و rollback plan دارد.
# وضعیت تکمیل Production

Identity core و financial command core به‌صورت افزایشی پیاده شده‌اند. اتصال SMS/Payment/Travel Provider، target deployment و certification بیرونی همچنان gate تجاری/زیرساختی هستند. ترتیب بعدی: target hardening و immutable release → contract provider validation → controlled pilot → certification.

Booking orchestration، customer account، panel mutationها، invoice، support case lifecycle، installment execution، settlement posting و admin user/role lifecycle اکنون متصل‌اند. staging rehearsal migration/RLS/restore نیز PASS است. مقدار مالیات و مرجع قانونی صورتحساب configurable و در Production بدون policy مصوب fail-closed است؛ اتصال نهایی providerها و deliveryها credential-dependent است.
