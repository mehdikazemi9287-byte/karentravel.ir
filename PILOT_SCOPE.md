# Pilot Scope

## In scope

OTP Mock، دو Tenant فرضی مستقل (سازمان «بانک آفتاب» و «صنایع فراز»)، Platform/BackOffice، مدیر سازمان، کارمند، policy/credit Mock، هتل با inventory دستی، search/detail، درخواست رزرو، approval، payment Mock fail-closed، ledger/audit نمایشی، comparison هتل، دستیار سفر UI، White Label یک سازمان، صفحه اصلی و dashboard حرفه‌ای.

## Out of scope

backend واقعی، PostgreSQL/RLS، provider credential، نرخ/ظرفیت زنده، payment/OTP حقیقی، settlement واقعی، صدور، AI production، اپ موبایل native، انتقال داده یا کد 60Online/70Online، و فعال‌سازی contract برندهای دیگر.

هتل/آژانس/provider tenant آزمایشی نیستند؛ فقط supplier domain محسوب می‌شوند. Tenant isolation صرفاً با دو سازمان فرضی آزمون UX می‌شود.
