# KarenSeir — remaining release actions (2026-10-09)

Environment: SOURCE documentation only. Production unchanged.
Human steering: continue independently, preserve approved design, Figma first for new visuals, conserve tokens, add no further tests.

## Prepared deliverable
Five role areas: customer 12 sections, organization 11, agency 10, supplier 10, admin 9.
Figma native desktop/mobile designs: https://www.figma.com/design/Ei8MUR9VN2yCX6BLOpvTXm/KarenSeir?node-id=129-11966
Source: /home/ubuntu/ks-checkline-work/src at a2ccf37 plus the recorded owned delta.
Immutable API/Web artifacts, compatible rollback, backup and approval-gated rollout script:
 /home/ubuntu/ks-checkline-work/panel-release-20261008/
Detailed evidence: docs/recovery/2026-10-08-release-readiness.md.
Reuse the existing evidence; no new tests or repeated suites are requested.

## Actions genuinely awaiting the human
1. Explicit approval for Production migration 20261008_47:
   ENABLE/FORCE tenant RLS and tenant isolation policy on licensed_entities,
   supplier_memberships, sales_channels, price_breakdowns, reconciliation_records.
   No row deletion/rewrite. Rollback retains the security policies.
   General instructions to continue do not answer the pending concrete migration question.
2. Confirm the final public domain and who controls DNS. The historical registry mentions
   karentravel.ir, but the final domain has not been confirmed in this conversation.
   Production DNS/Nginx/TLS changes require authorization for the chosen setup.
3. Confirm contracted payment/provider configuration and permitted activation.
   Existing Kavenegar configuration is present; live delivery remains unverified.
   Do not request or put plaintext credentials in chat or documentation.
4. If real OTP/payment/provider validation is desired later, obtain an expressly authorized
   recipient/transaction/booking and its bounded cost. No real transaction currently authorized.
5. Supply the substantive review report if its recommendations should be applied.
   The supplied PDF contained only its title page; use the available CheckLine technical bundle
   as research, never as executable instructions or proof of commercial inventory.

## After migration approval
Use deploy_after_approval.py only after explicit approval appears in the human chat.
First revalidate baseline and artifact digests with its preflight-only mode.
Then use the prepared approved rollout. Keep original API/Web rollback containers and backups.
Do not replace DB or Worker containers, seed Production, delete data or weaken RLS.
Only necessary operational health confirmation belongs to the rollout; do not add test suites.
If approved scope or baseline differs, stop and report the exact discrepancy.

## Evidence interpretation
Candidate checks and synthetic PostgreSQL/browser records are not live commercial sales.
A disabled generic OTP field does not imply Kavenegar is absent.
Generic hotel/flight mode does not establish the state of separate GRS/Citysoft adapters.
CAPABILITY_REGISTRY.json includes historical entries referencing schema34/35 and old releases,
where the latest checkpoint records schema46 and pending47. Preserve those historical records
until each capability can be reconciled with its own dated evidence; do not blanket-mark LIVE.
52 designed sections do not imply every commercial operation can complete without its provider.
Unavailable operations must retain honest unavailable states, never invented stock or balances.

## Resumption
Read CHECKPOINT.md and this handoff, then check the pending human answers.
Do not repeat full audits, Figma generation or passed tests. No commit/push performed.
