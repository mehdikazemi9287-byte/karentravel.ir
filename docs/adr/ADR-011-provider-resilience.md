# ADR-011: Provider Resilience توزیع‌شده

هر adapter با wrapper مشترک اجرا می‌شود. throttling و circuit state در Redis و با کلید tenant/provider نگهداری می‌شوند. Redis configured ولی unavailable باعث fail-closed می‌شود. فقط خطای retryable با backoff محدود retry می‌شود؛ نتیجه business/non-retryable تکرار نمی‌شود. transport باید timeout شبکه خود را enforce کند و wrapper نیز سقف انتظار call دارد.

Circuit پس از پنج failure در ۶۰ ثانیه برای ۳۰ ثانیه باز می‌شود. raw credential، destination، payload یا token وارد key/metric نمی‌شود. rollback با حذف wrapper image است؛ keyها TTL دارند.
