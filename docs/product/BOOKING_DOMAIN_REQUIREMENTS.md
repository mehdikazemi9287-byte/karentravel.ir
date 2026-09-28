MAJOR PRODUCT CORRECTION — KARENSEIR IS A BOOKING PLATFORM

Stop treating KarenSeir as a travel-content website with search forms.

KarenSeir is a transactional travel ecosystem.
BOOKING / RESERVATION LIFECYCLE is a CORE DOMAIN of the product.

The current implementation has substantially under-modeled reservation,
inventory, traveler, fulfillment, after-sales and trip-operation workflows.

Do a BOOKING-DOMAIN GAP CLOSURE immediately.

Do not stop after the audit.
Implement all internally implementable gaps.

==================================================
1. UNIVERSAL RESERVATION ENGINE
==================================================

Define a normalized lifecycle:

DISCOVER
→ SEARCH
→ AVAILABILITY
→ SELECT
→ RECHECK
→ TRAVELER/GUEST DATA
→ RULES ACCEPTANCE
→ PRICE CONFIRMATION
→ HOLD
→ BOOK
→ PAYMENT
→ CONFIRM
→ ISSUE
→ VOUCHER/TICKET
→ NOTIFY
→ TRIP
→ MODIFY
→ CANCEL
→ REFUND
→ SETTLE
→ CLOSE

Not every vertical needs every state.
Model vertical-specific state machines explicitly.

Persist state transitions and audit events.

Never infer successful booking from successful payment alone.

==================================================
2. BOOKING STATES
==================================================

Model explicit states such as:

DRAFT
SEARCHED
SELECTED
RECHECK_REQUIRED
PRICE_CHANGED
AVAILABILITY_CHANGED
HOLD_PENDING
HELD
HOLD_EXPIRED
BOOKING_PENDING
BOOKED
PAYMENT_PENDING
PAID
ISSUANCE_PENDING
ISSUED
CONFIRMED
PARTIALLY_CONFIRMED
FAILED
CANCELLATION_REQUESTED
CANCELLED
REFUND_PENDING
PARTIALLY_REFUNDED
REFUNDED
COMPLETED

Map supplier-specific statuses into normalized KarenSeir statuses.

==================================================
3. FLIGHT BOOKING
==================================================

Support where supplier data permits:

domestic/international
one-way/round-trip/multi-city
city/airport search
passenger composition
adult/child/infant
cabin
fare family/class
airline
flight number
aircraft
departure/arrival
duration
stop
baggage
refundability
fare rules
supplier
price breakdown
tax/fee
availability
recheck
price change
traveler data
Iranian national ID
passport for applicable travel
birth date
gender where required by supplier
passport expiry/nationality where required
contact data
hold
booking
PNR
payment
issuance
ticket number
voucher
cancellation
refund
after-sales

==================================================
4. HOTEL / ACCOMMODATION BOOKING
==================================================

Support:

destination/property
dates
room count
adult/child
child ages where required
property detail
gallery
amenities
location/map data
room types
board basis
occupancy
bed information where supplied
availability
nightly/total price
tax/fees
cancellation policy
non-refundable conditions
guest data
special requests
recheck
reservation
confirmation number
voucher
modify/cancel
refund

Accommodation/villa flows additionally need where applicable:

capacity
extra guest
check-in rules
host/property rules
deposit
cleaning/service fees
instant/request booking
arrival coordination

==================================================
5. TRAIN
==================================================

Implement a proper train booking domain:

origin/destination
date
passengers
adult/child/infant rules
gender/coupe constraints where applicable
exclusive coupe
train/company
class
departure/arrival
duration
availability
price
passenger identity
recheck
booking
payment
ticket issuance
cancellation/refund rules

==================================================
6. TOUR / PACKAGE
==================================================

Tours are NOT generic content cards.

Model:

departure
destination
dates
duration
capacity
tour type
transport
hotel
room
meal plan
itinerary
services included
services excluded
guide
visa requirements where applicable
documents
traveler composition
price components
supplements
single-room surcharge
child/infant rules
capacity
request/instant confirmation
deposit/payment schedule
booking
documents
voucher
cancellation policy

==================================================
7. CAR RENTAL
==================================================

Model:

pickup/dropoff
date/time
location
vehicle
category
capacity
transmission
mileage policy
fuel policy
insurance
deposit
driver requirements
driver age
license requirements
extra driver
add-ons
availability
price
recheck
reservation
handover/return
damage/deposit lifecycle

==================================================
8. RESTAURANT
==================================================

Restaurant is a reservation vertical, not just a directory.

Model:

venue
branch
date
session
time slot
party size
table/zone where supported
capacity
menu
deposit/prepayment where applicable
special request
reservation
QR confirmation
arrival/check-in
no-show
cancel

Keep restaurant QR capabilities in the domain.

==================================================
9. POOL / SPORT / ATTRACTION
==================================================

Model:

venue
activity
date
session
time slot
gender restrictions where legitimately required
capacity
age rules
ticket type
quantity
price
availability
booking
QR ticket
validation/check-in
cancellation

==================================================
10. EVENTS / EVENT HALLS
==================================================

Event:

event
venue
date/session
seat/zone
ticket category
capacity
quantity
booking
QR ticket
check-in

Event hall:

venue
date
time/session
capacity
package
services
catering
deposit
request/quote
contract
payment schedule
reservation

Do not force these two into the same booking model.

==================================================
11. TRAVEL GUIDES / TOURIST TRANSPORT
==================================================

Guide:

city/language/specialty
date/time
duration
availability
meeting point
price
booking

Transport:

vehicle
route
pickup/dropoff
date/time
passengers
luggage
capacity
driver/vehicle assignment
price
booking
trip status

==================================================
12. CART / MULTI-SERVICE TRIP
==================================================

KarenSeir must not treat every service as an isolated purchase.

Design a Trip Basket / Trip Plan capable of holding:

flight
train
hotel
tour
car
experience
restaurant
event
guide
transport

Handle independently expiring inventory.

Before final booking:
RECHECK every price and availability.

Clearly show:
changed price
unavailable item
expired item
alternative item

Never silently substitute.

==================================================
13. TRAVELER PROFILES
==================================================

Create reusable traveler profiles with appropriate access control.

Support applicable fields:

Persian/Latin names
national ID
birth date
contact details
passport
nationality
passport expiry

Sensitive data must receive appropriate protection.

Do not ask repeatedly for traveler data already available and authorized.

==================================================
14. CHECKOUT
==================================================

Checkout must be a real transactional flow:

reservation summary
travelers/guests
contact
rules
cancellation conditions
price breakdown
fees
discount
wallet
organization credit
installments where eligible
payment method
invoice information
final confirmation

Then:
PAY / RESERVE / REQUEST

depending on vertical.

==================================================
15. PAYMENT IS NOT BOOKING
==================================================

Separate:

Reservation
Order
Payment
Issuance
Refund
Settlement

Use idempotency.

A retry must never create duplicate:

booking
payment
ticket
refund

Handle:
timeout
unknown provider response
callback replay
double click
browser refresh
supplier timeout
payment success + booking failure
booking success + payment uncertainty

==================================================
16. BOOKING DETAIL
==================================================

Every booking needs a useful detail page containing applicable:

status
supplier confirmation
travelers
service details
price
payment
documents
ticket/voucher
rules
timeline
support
cancel/refund
required action

==================================================
17. MY TRIPS
==================================================

My Trips must aggregate reservations into trips.

UPCOMING
ACTIVE
COMPLETED
CANCELLED

Trip detail:

itinerary
reservations
travelers
documents
tickets
vouchers
payments
support cases
notifications
timeline
changes
required actions

==================================================
18. TRIP OPERATIONS CENTER
==================================================

Operational events must be first-class data.

Examples:

flight schedule changed
flight cancelled
hotel confirmation changed
supplier failed
voucher issued
payment status changed
refund changed
document required
pickup changed
event/session changed

Persist:

what changed
old value
new value
source
timestamp
affected reservation
required user action
notification status

==================================================
19. WHAT CHANGED IN MY TRIP?
==================================================

Build this as a real customer feature.

Do not merely display generic notifications.

Show:

WHAT CHANGED
WHEN
WHY if known
WHAT IT AFFECTS
WHAT USER MUST DO
AVAILABLE OPTIONS

==================================================
20. AFTER-SALES
==================================================

Build after-sales workflows:

cancel
partial cancel
change request
refund
partial refund
document request
supplier follow-up
complaint/support case
manual intervention

Human operations must have a case queue.

==================================================
21. ORGANIZATIONAL BOOKING
==================================================

Organization travel must integrate into the SAME booking engine.

Employee
→ Search/Request
→ Travel policy
→ Budget
→ Approval
→ Reservation
→ Organization credit/payment
→ Booking
→ Ticket/Voucher
→ Trip
→ Changes
→ Settlement/reporting

Support:
cost center
department/project
traveler
approver
policy violation
approval trail
credit consumption
organization invoice/statement

==================================================
22. SUPPLIER OPERATIONS
==================================================

Supplier panel needs applicable:

incoming reservations
accept/reject where required
confirmation
capacity
fulfillment
voucher
cancellation
receivable
settlement
dispute/support

==================================================
23. ADMIN / HUMAN OPERATIONS
==================================================

Operations staff need:

global booking search
reservation detail
payment state
supplier state
traveler support
case queue
failed booking queue
issuance queue
refund queue
manual intervention
audit log

Never allow silent destructive overrides.

==================================================
24. NOTIFICATIONS
==================================================

Create event-driven notification orchestration.

Channels:
Web
App
Push
SMS
Email where configured

Use deep links to the exact booking/trip/action.

AI-generated messages and human-support messages must be distinguishable.

==================================================
25. AI ASSISTANT
==================================================

The assistant must operate on the booking domain.

It should be able to:

search
refine
compare
build trip
calculate budget
explain rules
collect missing booking information
handoff to checkout
explain existing booking
retrieve trip status
explain changes
assist cancellation/change requests
escalate to human operations

It must NEVER invent:
price
availability
confirmation
ticket
refund status

==================================================
26. CHECKLINE CAPABILITY AUDIT
==================================================

CheckLine already demonstrates real flight/hotel inventory.

Audit its approved integration possibilities before claiming supplier
functionality is unavailable.

Do not couple KarenSeir directly to CheckLine UI.

Use supplier adapters and a normalized KarenSeir domain.

==================================================
27. UX / FIGMA
==================================================

Now map this booking domain into the approved KarenSeir Figma.

Do not design only happy paths.

Figma/frontend must include:

loading
searching
empty
partial result
price changed
sold out
recheck
hold countdown
payment pending
payment failed
booking pending
booking failed
issuance pending
confirmed
cancel requested
refund pending
refunded
action required

Desktop AND mobile.

==================================================
28. DEFINITION OF DONE
==================================================

A page returning HTTP 200 is NOT DONE.

A button rendering is NOT DONE.

An API unit test is NOT DONE.

A vertical is DONE only when its applicable journey works:

Browser
→ Search
→ Real/Test Adapter
→ Availability
→ Selection
→ Recheck
→ Traveler/Guest
→ Reservation
→ Payment/Test Payment
→ Confirmation
→ Ticket/Voucher
→ My Trips
→ After-sales

with DB persistence, permissions, error handling and browser E2E.

No real financial transaction or real SMS without explicit authorization.

==================================================
EXECUTION
==================================================

1. Build the domain gap matrix.
2. Inspect existing code before creating duplicates.
3. Reuse sound existing components.
4. Implement backend/domain gaps first where required.
5. Implement frontend UX.
6. Update Figma-aligned screens.
7. Run targeted browser E2E.
8. Deploy only tested increments.
9. Preserve rollback.
10. Continue automatically through implementable gaps.

Do NOT stop merely because Supplier/DNS/Payment/SMS is blocked.

Report only:

DOMAIN | BEFORE | IMPLEMENTED | E2E | REMAINING BLOCKER

Keep token consumption low.
Do not repeatedly narrate work.
Do not repeat previously verified tests without a dependency reason.