# Release and Rollback

هر release با version غیرقابل‌تغییر، image digest، source commit، SBOM، migration head و QA evidence ثبت می‌شود. deploy مستقیم source directory ممنوع است.

در workspace فاقد Git، `RELEASE_MANIFEST.json` checksum مستقل source، dependency locks، migration head و timestamp را ثبت می‌کند. تا وقتی commit و image digest واقعی null هستند، manifest صریحاً `provenance_complete=false` است و Production GO نمی‌دهد.

ساختار target:

```text
/opt/karenseir/releases/<version>
/opt/karenseir/current -> /opt/karenseir/releases/<version>
```

`deploy/switch-release.sh` فقط directory موجود زیر release root را با symlink pointer فعال می‌کند. rollback همان command با version قبلی است. migrationهای این repository downgrade مخرب ندارند؛ در ناسازگاری داده، writerها متوقف و backup verify‌شده restore می‌شود.
