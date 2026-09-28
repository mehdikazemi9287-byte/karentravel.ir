# ADR-022 — Booking domain and accommodation marketplace closure

Accepted scope: user-supplied booking and accommodation requirements in docs/product.
Source baseline 09950ec; API main/operations hashes match running image fb8d03695ea0.

Reuse Reservation, BookingStatusHistory, PaymentIntent, Voucher, Trip, VacationProperty,
VacationUnit and VacationReservation. Payment capture alone must not issue a booking.
Do not add a parallel booking engine or imply that internal tests prove live selling.

First increment: validated accommodation rates/calendar in existing pricing_json;
per-night capacity from overlapping holds; transparent extra-guest and fixed fees;
calendar read API and assigned-supplier update with audit; customer calendar and quote.
All pricing and inventory are rechecked under the existing unit lock at booking.
A supplier rate update cannot overwrite an existing reservation's price snapshot.
No schema migration. Existing catalog stays private to its tenant until an explicit
publication workflow is implemented. No fake reviews, discounts or availability.

Acceptance: isolated DB-backed tests for calendar/rates, overlapping capacity,
minimum stay, replay/conflict and supplier permissions; desktop/mobile browser
calendar→quote→hold→checkout; affected prior accommodation regression only.
Rollback: retained API/worker/web images; additive JSON keys are compatible, but
older code does not enforce new calendar/rate keys. If used in live inventory,
disable affected units before reverting to an older implementation.

## Domain gap matrix (evidence-based; not a completion claim)
| Domain | Existing | Gap / closure order |
|---|---|---|
| Lifecycle | transitions, history, outbox, separate payment/voucher | replay payload binding; explicit vertical states still need mapping |
| Accommodation | property/unit, dated hold, seasonal quote, checkout | calendar, per-night capacity, fee breakdown first; request/approval and marketplace publication remain |
| Flight/train | normalized offers, travellers, checkout and manual fulfillment | supplier-specific fare/passenger and issuance contracts need verified adapters |
| Tour/car/leisure/guide/transport | existing isolated vertical baselines | compare each applicable field and after-sales action; no blanket DONE |
| Basket/trips | trip records, timeline, linked reservations | independent item expiry and atomic recheck review required |
| Travellers/checkout | owner-scoped profiles and checkout stages | field completeness and sensitive-data review required |
| After-sales/operations | service requests, support, event timeline, roles | partial cancellation/refund and changed-value detail review required |
| Organization | policy/approval/credit baseline | compare full settlement journey against requirements |
| Assistant | deterministic search/hold/checkout | structured accommodation constraints, multi-service planning remain |
| CheckLine | no approved adapter evidence inspected this increment | read-only integration capability discovery; no UI/DB coupling |
| Design | existing approved component system | preserve homepage; extend states in dedicated screens; Figma source not supplied |

Only tested increments are deployed; remaining internal gaps are not external blockers.

Second increment: explicit REQUEST_TO_BOOK stored on property details and frozen in
reservation snapshot. Requested rows do not promise/hold inventory. Host acceptance
locks and rechecks inventory/price before converting to a timed hold; no payment
intent or checkout until accepted. Rejection/withdrawal is non-financial. Commands
are bound to reservation/action/reason and audited through the existing transition,
trip event and outbox models. Supplier UI uses assigned-property scope only.

Fulfillment consistency: explicit supplier issuance also changes VacationReservation
from held to confirmed in the same DB transaction. Payment alone never does so.

Third increment: reuse EditableItinerary/Item as the trip basket. Replace the
placeholder add action with customer-authored items and real offer linkage. Recheck
each linked offer through the existing PriceCheck boundary; persist each item's
expired/unavailable/changed/ready/provider-required result, never substitute items.
A rechecked plan does not hold inventory or imply a combined purchase. Final per-item
booking retains the existing recheck/hold guards. Provider-only inventory stays
fail-closed. No bulk charge or all-or-nothing booking is introduced implicitly.

Booking recovery delta: known 409/422 invalidates the quote and asks for explicit
recheck; PRICE_CHANGED displays both totals. Unknown response keeps the command;
session-scoped pending command survives refresh, scoped by authenticated subject and
stay selection. The local claim is only a storage namespace, never authorization.
Server ownership checks remain authoritative. A received result clears retry state.
Desktop/mobile QA changed a real stored rate, dropped an already persisted response,
refreshed and recovered the same request ID; no duplicate booking or real charge.

Enterprise, finance, gift and benefit extension: see [ADR-023](ADR-023-enterprise-travel-welfare.md), including explicit internal gaps and Source-only implementation status.
