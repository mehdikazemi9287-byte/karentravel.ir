# Working Agreement

## مرز پروژه

این مخزن فقط KarenSeir است. 60Online/70Online هرگز import، copy یا shared database/UI نمی‌شود. CheckLine، تاژبان گشت پارس و پادویرا هویت مستقل دارند.

## قواعد تغییر

- ابتدا اسناد و ADR را به‌روز کنید؛ سپس code محدود به scope مصوب.
- API/provider/payment بدون credential معتبر و آزمون fail-closed فعال نمی‌شود.
- قیمت، inventory، policy، credit و ledger در frontend authoritative نیستند.
- هر داده demo با Mock برچسب می‌خورد.
- White Label با configuration tenant-aware، نه fork، انجام می‌شود.
- هر فاز باید acceptance، test و rollback داشته باشد.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
