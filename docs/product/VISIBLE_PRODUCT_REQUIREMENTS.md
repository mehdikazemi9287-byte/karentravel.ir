FORENSICS PASSED. RESUME DEVELOPMENT FROM THE PROVEN LIVE SOURCE:

/home/ubuntu/karenseir-current

The deployment path is now proven.
Do NOT investigate repositories, containers, metadata or deployment identity again.

NEW PRIORITY:
THE CUSTOMER-FACING PRODUCT MUST NOW VISIBLY CHANGE.

The previous work added important backend/domain capabilities, but the
public KarenSeir experience still does not represent the travel marketplace
and booking ecosystem we specified.

For this phase, STOP prioritizing invisible backend expansion.

Do not run migration 20260928_34 yet.
Do not start another finance-engine expansion yet.
Do not produce another architecture-only checkpoint.

==================================================
MISSION
==================================================

Turn the ACTUAL LIVE CUSTOMER PRODUCT into a credible travel marketplace
and booking platform.

Work directly from:

/home/ubuntu/karenseir-current

and use the proven production deployment path.

The following public surfaces are now P0:

/
search/results
flight
hotel/accommodation
train
tour
experiences/services
trips

plus their actual booking/discovery flows.

==================================================
RULE #1 — VISIBLE PRODUCT DELTA
==================================================

Every implementation batch in this phase must produce a meaningful,
browser-visible improvement on the public/customer product.

Backend work is allowed only when required to make that visible journey work.

Do not count:
- database models
- hidden APIs
- documentation
- internal admin routes
- test fixtures

as completion of this phase by themselves.

==================================================
P0 — HOMEPAGE
==================================================

The current homepage is far too sparse.

Rebuild it as the primary travel marketplace/discovery surface while
preserving the approved KarenSeir design identity.

The homepage must visibly expose:

PRIMARY SEARCH
AI TRAVEL ASSISTANT
FLIGHT
HOTEL
TRAIN
TOUR
ACCOMMODATION / VILLA
CAR RENTAL
RESTAURANT
EXPERIENCES
POOL / SPORT
EVENT
EVENT HALL
TRAVEL GUIDE
TOURIST TRANSPORT

Then add real discovery modules such as:

popular destinations
accommodation discovery
travel ideas
weekend trips
seasonal travel
tours
experiences
organizational travel
travel credit/installment proposition
trip-management proposition
support/trust

Use real catalog/content data where available.

Do NOT fabricate:
price
availability
rating
discount
inventory.

==================================================
P0 — SEARCH COMPONENT
==================================================

The main search must feel like a real travel booking product.

Do not use one generic form for every vertical.

Each tab needs appropriate fields.

FLIGHT:
origin
destination
one-way / round-trip / multi-city
departure
return
passengers
cabin

HOTEL:
destination/property
check-in
check-out
rooms
adults
children

TRAIN:
origin
destination
date
passengers
applicable train preferences

TOUR:
origin
destination
date/range
travelers

ACCOMMODATION:
destination
dates
guests
property type

CAR:
pickup
dropoff
dates/times

EXPERIENCE:
destination
date
participants

Do the same appropriately for other verticals.

==================================================
P0 — RESULTS
==================================================

The current generic zero-result page is unacceptable as the primary product.

Build vertical-specific result experiences.

FLIGHT result cards must be ready for:

airline
flight number
departure
arrival
duration
stops
class
baggage
supplier
price
rules
recheck
purchase

and real filters.

HOTEL/ACCOMMODATION:

image
property
location
type
rating only if real
room/rate information
board
capacity
cancellation
price
availability
supplier
detail CTA

and real filters.

TRAIN/TOUR/etc. need their own relevant result representation.

If inventory is unavailable, keep the result page structurally complete
and show an honest empty state with:

modify search
flexible dates
alternative destination
other transport/accommodation options
AI assistance
human assistance

Do not invent fake result cards.

==================================================
P0 — ACCOMMODATION MARKETPLACE
==================================================

Implement the discovery depth discussed using Jabama only as a benchmark,
NOT as a visual template.

Expose categories such as supported:

hotel
villa
apartment
suite
ecolodge
cabin
traditional property
pool property
nature/forest
beach

Build:

destination discovery
property-type discovery
popular cities
seasonal ideas
property results
property detail architecture
availability calendar architecture

==================================================
P0 — TRAVEL ASSISTANT
==================================================

The assistant must become visually prominent.

Give it a real entry point on the homepage.

Example prompts:

«برای آخر هفته شمال کجا بریم؟»

«برای ۴ نفر ویلا با استخر پیدا کن»

«پرواز صبح تهران مشهد و هتل نزدیک حرم می‌خواهم»

The assistant UI should clearly support:

Plan trip
Find
Compare
Build itinerary
Manage existing trip

It must use real data when making transactional claims.

==================================================
P0 — MY TRIPS
==================================================

Replace the nearly empty visual experience.

For authenticated state build the actual travel dashboard:

Upcoming
Active
Completed
Cancelled

and booking/trip cards with:

status
destination
dates
services
travelers
payment state
voucher/ticket
required action

Trip detail must visibly accommodate:

Timeline
What changed?
Documents
Bookings
Payments
Support
Cancellation/refund
Assistant

For unauthenticated users retain the secure login gate, but improve the
page so it communicates what the travel control center actually provides.

==================================================
P0 — ORGANIZATIONAL ENTRY
==================================================

Do NOT hide all the organizational work inside internal routes.

Create a strong customer-facing organization entry page that explains and
routes into:

Business travel
Employee welfare
Team building
Project accommodation
Guest travel
Travel credit
Group travel
RFQ
Reporting
Travel Desk

Use the capabilities we have already specified.

==================================================
DESIGN
==================================================

Return to the approved KarenSeir identity.

Premium Iranian travel product.
RTL.
Vazirmatn.
Dark navy + turquoise.
Consistent components.

Do not allow the current beige/orange/purple drift to become the design
system.

Do not copy Alibaba, Jabama or CheckLine visually.

Use them only to understand product depth.

==================================================
IMPLEMENTATION METHOD
==================================================

Work in visible vertical slices.

Suggested order:

SLICE 1
Homepage + navigation + search shell + AI entry

SLICE 2
Flight results/detail/booking entry

SLICE 3
Hotel + accommodation discovery/results/detail

SLICE 4
Train + tour

SLICE 5
Experiences/leisure/restaurant/etc.

SLICE 6
My Trips + Trip Timeline

SLICE 7
Organization public entry + customer-facing B2B flows

For each slice:

IMPLEMENT
→ BUILD
→ DESKTOP BROWSER CHECK
→ MOBILE BROWSER CHECK
→ TARGETED E2E
→ DEPLOY
→ VERIFY ON 95.38.184.209

Do not wait until all seven slices are finished before showing visible progress.

==================================================
IMPORTANT
==================================================

Do not claim a slice is complete merely because the page exists.

I must be able to open 95.38.184.209 and SEE the difference.

After each deployed slice provide:

SLICE:
COMMIT:
PUBLIC_ROUTES_CHANGED:
VISIBLE_CHANGES:
DESKTOP:
MOBILE:
E2E:
PUBLIC_DEPLOY_VERIFIED:
SCREENSHOT_PATHS:
NEXT_SLICE:

Keep the report short.

Do not repeatedly explain architecture.

Do not spend tokens narrating routine implementation.

START WITH SLICE 1 NOW.

Do not stop after auditing it.
Implement it, test it, deploy it and visually verify it on the PUBLIC IP.