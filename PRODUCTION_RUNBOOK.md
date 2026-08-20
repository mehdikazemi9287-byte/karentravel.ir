# Production Runbook

## Gate ورود

DNS عمومی، CA certificate معتبر، secret manager و rotation test، PostgreSQL/Redis managed، collector و alert receiver، image digest و commit provenance، backup/restore و rollback drill باید evidence داشته باشند. `DEMO_MODE` باید false و همه providerهای فعال باید قرارداد و credential معتبر داشته باشند.

## ترتیب استقرار

1. backup رمزگذاری‌شده و restore verification ایزوله؛ ثبت checksum و recovery time.
2. اجرای `deploy/preflight.sh` و migration روی یک job مستقل با همان image release.
3. start API/worker با secretهای mount‌شده، سپس `/health` و `/ready`.
4. smoke test tenant isolation، login، payment fail-closed و metrics.
5. فعال‌سازی release pointer و rollout محدود؛ monitor نرخ 5xx، latency، Redis، outbox و payment/OTP failure.

در outage ابتدا writerها drain، evidence و correlation IDها حفظ و سپس طبق `INCIDENT_RESPONSE.md` عمل شود. هیچ callback یا outbox event دستی بدون idempotency key replay نمی‌شود.
