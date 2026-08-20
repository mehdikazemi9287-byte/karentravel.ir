# Implementation Roadmap

## Next exact internal increment

Invoice، support case/thread انسانی، installment execution، settlement posting و مدیریت role تکمیل و E2E شده‌اند. increment دقیق بعدی اجرای migration `20260820_10` و تست RLS/FORCE RLS هر ۵۶ جدول روی PostgreSQL staging ایزوله، سپس backup→restore و rollback rehearsal همان artifact است. پس از آن فقط اتصال providerهای قراردادی و certification target انجام می‌شود.

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

Booking orchestration، customer account، panel mutationها، invoice، support case lifecycle، installment execution، settlement posting و admin user/role lifecycle اکنون متصل‌اند. کار داخلی باقیمانده محدود به staging rehearsal migration/RLS/restore و تنظیم مالیاتی/شماره‌گذاری قانونی صورتحساب پس از دریافت policy تجاری است؛ اتصال نهایی providerها و deliveryها credential-dependent است.
