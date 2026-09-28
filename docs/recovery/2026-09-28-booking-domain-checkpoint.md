# Booking-domain implementation checkpoint

Source root /home/ubuntu/karenseir-current; reference Production 95.38.184.209.
Baseline 09950ec. Deployed increments c138249 (accommodation marketplace),
9166800 (trip basket), 5a714cb (booking response recovery). Web fingerprint
916680044d173390d5e3a6a0a59328a038f00b69-worktree-bb9fb10134d0 maps by content
hash to final source. API/worker image e4bace796f3f; web 6809c6a51d6e.

Implemented: per-night inventory, validated rate/calendar rules, explicit fee
breakdown, expanded property types, tenant-scoped category/guest discovery,
assigned-host calendar/rate UI, request-to-book acceptance/rejection/withdrawal,
no payment before host approval, shared checkout/issuance/trip, durable transition
replay binding, persisted trip-plan offer linkage/recheck and customer notes,
explicit price-change UI and refresh-safe recovery of uncertain booking commands.

QA: domain suite 7 passed, subsequent two affected tests passed (basket and
maximum-length approval/issuance). Desktop/mobile isolated E2E: accommodation
through intercepted payment, supplier issuance, voucher and Trip; host response
loss/retry; discovery/empty state; basket persistence/recheck/duplicate-add/detail
handoff; actual QA price change and committed-response-loss followed by refresh
returned the same reservation. Public changed-route checks: 8 + 4 + 2. Five services
healthy, API/assistant readiness and source/image content correspondence verified.
Actual screenshots retained in /tmp; automated browser bounds/interaction checks
are the evidence, not a claim of a complete perceptual design review.

No real financial transaction, real SMS, production test fixtures, migration,
production permission weakening or external integration activation. Original
rollback containers remain; every increment also retains its predecessor. No
rollback rehearsal or data deletion. Latest rollback is web-only to the prior
basket release. For a deep rollback to pre-marketplace code, stop admission to
units using new rate/calendar rules and resolve pending host requests first;
older code does not implement those semantics. Existing user debug_voucher.py
remains untracked and untouched.

This is NOT full booking-domain completion. All requirements are copied verbatim
under docs/product; ADR-022 contains the gap matrix. Remaining internal work is
explicit in the adjacent JSON, including public catalog moderation/publication,
property content, structured protected traveller data, basket-to-single-Trip
linkage and the remaining vertical/after-sales requirements. Do not classify
these as external credential blockers or claim all internal capabilities PASS.

CheckLine integration capability is unverified: no approved source/API reference
was supplied or found in the checked project locations. Do not infer its supplier
functionality is unavailable. No CheckLine UI/database/code was copied. No Figma
source URL was found in the checked design/docs references; existing approved
frontend visual structure was preserved, but no Figma document was edited.

NEXT EXACT ACTION: close accommodation supplier property/unit creation and
publication/moderation through existing models, then public discovery with
explicit tenant visibility. Preserve the completed calendar/host/payment boundary
and run only affected QA; do not restart the full audit.
