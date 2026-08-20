# Implementation Roadmap

## Next exact internal increment

اتصال routeهای `/trips`، Trip Timeline، `/manage-booking`، `/compare` و پنل‌های سازمان/تأمین‌کننده/آژانس/BackOffice به `KarenSeirApi` تکمیل و E2E شده است. increment بعدی اتصال profile/travelers/wallet/payment/notification preferences و سپس mutationهای نقش‌محور است. اتصال providerهای بیرونی فقط پس از credential قراردادی انجام می‌شود.

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

Booking orchestration، approval/panel read models و routeهای عملیاتی اصلی اکنون متصل‌اند. کار داخلی باقیمانده اصلی customer account، mutationهای پنل‌ها، support case management و reconciliation حسابداری target است؛ اتصال نهایی providerها و deliveryها credential-dependent است.
