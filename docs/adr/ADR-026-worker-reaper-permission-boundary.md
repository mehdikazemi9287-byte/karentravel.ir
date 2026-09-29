# ADR026 — worker/reaper privilege boundary

## Related operational blocker discovered during verification
The unchanged live worker uses karenseir_worker (BYPASSRLS, non-superuser).
Its provision script explicitly REVOKEs reservations/financial table privileges.
The unconditional reservation reaper crashes every twelfth loop with PostgreSQL
42501. Do not grant this cross-tenant notification role booking/financial access.
Gate the reaper with an explicit opt-in, default off; report disabled status in
worker health. An authorized separately scoped reaper deployment remains required
for automatic hold expiry. This correction does not expire/release any real hold.
Production worker rollout needs explicit approval; no migration35 is necessary
for a worker-only artifact based on the current live backend plus this exact file.
