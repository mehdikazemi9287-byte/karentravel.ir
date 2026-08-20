# White Label Specification

Tenant-aware: `tenant_id`، domain binding، branding token، content namespace، feature flags، policy namespace، data isolation و audit مستقل. سازمان می‌تواند کاملاً خودگردان یا managed مشترک با کارن‌سیر باشد.

مدیر سازمان کارکنان، واحد، شعبه، خانواده، نقش، تأمین‌کننده، بودجه/اعتبار، approval، محتوا، درخواست، پرداخت/تسویه و گزارش را مدیریت می‌کند. نقش‌ها شامل Organization Admin، Welfare، Finance، Travel Approver و Operator است.

دامنه custom پس از اعتبارسنجی DNS/TLS فعال می‌شود. هیچ tenant با کپی پروژه ساخته نمی‌شود. RLS و تست نفوذ بین‌مستاجری در backend مرحله بعد اجباری است.
