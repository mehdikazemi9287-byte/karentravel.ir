# ADR025 — fixed-stay hotel quote integrity (SOURCE/PREVIEW)

An Offer is not a date-independent hotel room. The reproduced two-room search currently
quotes one unit without dates. Reuse Offer/PriceCheck/BookingItem snapshots; no new DB
or provider engine is introduced. Manual hotel allotments must explicitly declare
`hotel_rate`: check_in, check_out, room_type, rate_plan, price_basis=room_stay,
occupancy={adults, children_ages}. Amount is the supplier's complete price per room
for that exact stay and occupancy. Each requested room must match that supplied rate;
no inferred child price, extra bed, daily stock or alternative rate. Missing/mismatched
terms fail closed. Mixed room/rate booking remains a separately scoped capability.

Customer selection carries dates and per-room allocation into the immutable quote,
reservation and checkout. Existing rows/documents remain readable. New hotel quotes
without the contract are rejected; callers/tests must supply explicit terms. A change
in terms between quote and reservation requires a fresh quote. Provider-mode offers
remain blocked by the existing real-provider gate.

Acceptance: two rooms/four adults preserve dates, amount, allocation and traveller
count; mismatched stay, occupancy, omitted contract, command reuse and changed terms
cannot book. Search shortcuts must go through the allocation page. Tests use isolated
labeled fixtures, never Production stock/payment/SMS. No production publication here;
current unpublished schema35 still needs approval. Rollback: revert candidate code;
no schema/data reversal required for this change. Whole-hotel closure remains open.

