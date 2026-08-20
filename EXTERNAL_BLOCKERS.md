# External Blockers

All adapters remain fail-closed until these are supplied and validated outside Git:

- `BLOCKED_EXTERNAL_CREDENTIAL`: contracted SMS/OTP transport credential and approved sender.
- `BLOCKED_EXTERNAL_CREDENTIAL`: payment merchant credential, callback secret and provider certification.
- `BLOCKED_EXTERNAL_CREDENTIAL`: contracted Flight, Hotel and Tour provider endpoints/credentials/webhook secrets.
- Public DNS ownership and valid public-CA TLS certificate.
- External secret manager with rotation/revocation evidence.
- External Prometheus-compatible collector and Alertmanager receiver.
- Authorized target infrastructure and security-testing engagement.
- Approved legal/finance invoice tax rate, policy reference and numbering requirements; Production invoice issuance is fail-closed until configured.
- Immutable container image build/digests and target backup/rollback smoke evidence (no container runtime is available on this validation host).

These blockers do not authorize fallback to mock transports in Production.
