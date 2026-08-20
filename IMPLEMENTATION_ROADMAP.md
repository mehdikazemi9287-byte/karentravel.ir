# Implementation Roadmap

## Next exact internal increment

اتصال profile/travellers/wallet/payment/notification preferences و mutationهای اصلی Supplier/Agency/BackOffice تکمیل و E2E شده است. increment بعدی طراحی افزایشی domain برای invoice، support case/thread، installment execution و settlement posting است؛ سپس user/role administration کامل می‌شود. اتصال providerهای بیرونی فقط پس از credential قراردادی انجام می‌شود.

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

Booking orchestration، customer account، panel read/mutationهای اصلی، support message و reconciliation UI اکنون متصل‌اند. کار داخلی باقیمانده invoice، support case lifecycle، installment execution، settlement posting و admin user/role lifecycle است؛ اتصال نهایی providerها و deliveryها credential-dependent است.
