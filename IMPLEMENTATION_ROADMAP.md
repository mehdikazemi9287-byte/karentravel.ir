# Implementation Roadmap

## Next exact internal increment

اتصال تدریجی routeهای موجود `/trips`، `/manage-booking`، `/compare` و پنل‌های نقش‌محور به `KarenSeirApi` با حفظ کامل layout؛ سپس افزودن E2E برای orchestration جدید و panel mutationها. اتصال providerهای بیرونی فقط پس از credential قراردادی انجام می‌شود.

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

Identity core و financial command core به‌صورت افزایشی پیاده شده‌اند. اتصال SMS/Payment/Travel Provider، target deployment و certification بیرونی همچنان gate تجاری/زیرساختی هستند. ترتیب بعدی: contract provider واقعی → booking orchestration → operations delivery → controlled pilot → certification.

Booking orchestration و approval/panel read models اکنون کامل شده‌اند. کار داخلی باقیمانده اصلی، اتصال تمام صفحه‌های نمایشی frontend به session/API مشترک و reconciliation حسابداری target است؛ اتصال نهایی providerها و deliveryها credential-dependent است.
