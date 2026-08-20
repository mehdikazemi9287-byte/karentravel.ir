# ADR-010: Tenant Configuration و Grounded Read Models

White Label به‌صورت یک config tenant-scoped و بدون fork ذخیره می‌شود. domain تا پیش از verification فعال نمی‌شود؛ logo فقط reference امن است. Agency hierarchy و نرخ‌ها basis-point هستند. Notification receipt با provider event id یکتا و callback امضاشده ثبت می‌شود.

Comparison فقط Offerهای معتبر tenant را امتیازدهی می‌کند و breakdown عددی/قابل‌توضیح می‌دهد. AI Context endpoint فقط رزرو، سفر، policy snapshot و provider health موجود را برمی‌گرداند و `authoritative` هر بخش را مشخص می‌کند؛ تولید price/inventory/refund/booking در آن وجود ندارد.

Migration افزایشی و rollback غیرمخرب است.
