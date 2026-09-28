ADD THIS TO THE KARENSEIR PRODUCT REQUIREMENTS.

ACCOMMODATION IS A MARKETPLACE DOMAIN — NOT JUST HOTEL SEARCH.

Use products such as Jabama only as a benchmark for marketplace depth,
discovery patterns and category completeness.
Do NOT copy their visual design.

KarenSeir must support a much broader accommodation domain:

HOTEL
VILLA
APARTMENT
SUITE
ECOLODGE
CABIN
RURAL HOUSE
BEACH PROPERTY
FOREST PROPERTY
POOL PROPERTY
TRADITIONAL HOUSE
RESORT
HOSTEL
CAMP / SPECIAL STAY
and other supported inventory types.

==================================================
ACCOMMODATION DISCOVERY
==================================================

Users must be able to discover accommodation BEFORE knowing an exact property.

Build:

- search by destination
- date
- guest/room composition
- property type
- city
- province/region
- map/area
- popular destinations
- nearby stays where supported
- seasonal destinations
- weekend ideas
- family stays
- couple stays
- group stays
- pool properties
- beachfront
- forest/nature
- traditional/ecolodge
- budget
- premium
- instant booking
- special offers where real

Discovery and Search are separate but connected experiences.

==================================================
ACCOMMODATION RESULT PAGE
==================================================

Build a serious marketplace result experience:

list
map where supported
filters
sorting
price
availability
property type
capacity
rooms
beds
amenities
rating/reviews where real
instant/request booking
cancellation conditions
location/area
distance metadata where available
discount only when real
remaining capacity only when real

Support pagination/infinite loading appropriately.

==================================================
PROPERTY DETAIL
==================================================

A property needs a real PDP:

photo gallery
title
property type
location
map
host/operator where applicable
description
capacity
base capacity
maximum capacity
bedrooms
beds
bathrooms
amenities
rules
check-in/out
availability calendar
pricing
weekend/holiday pricing when applicable
extra-person pricing
fees
deposit
cancellation policy
reviews where authentic
nearby places where supported
support/contact path
booking CTA

==================================================
AVAILABILITY CALENDAR
==================================================

Do not use a decorative date picker.

Calendar must understand:

AVAILABLE
UNAVAILABLE
REQUEST
MINIMUM_STAY
SPECIAL_PRICE
SOLD_OUT

and recheck before reservation.

==================================================
HOST / PROPERTY SUPPLIER
==================================================

Because KarenSeir is multi-tenant, accommodation needs supplier operations.

Property supplier should be able to manage applicable:

properties
units
photos
amenities
rules
calendar
inventory
rates
special dates
minimum stay
reservations
accept/reject for request bookings
guest communication through controlled channels
check-in
check-out
cancellation
receivables
settlement

Admin needs moderation and audit controls.

==================================================
BOOKING MODES
==================================================

Support both when required:

INSTANT_BOOKING

and

REQUEST_TO_BOOK

Do not fake instant confirmation for inventory that requires host/supplier
approval.

==================================================
PRICING ENGINE
==================================================

Accommodation pricing may require:

base nightly rate
weekday/weekend
holiday
seasonal
extra guest
cleaning/service fee
discount
organization rate
commission
tax where applicable

Always display a transparent final price breakdown.

==================================================
REVIEWS
==================================================

If reviews are implemented:

only verified/legitimate review sources may be represented as such.

Support:
rating
review
stay verification
moderation
supplier response

Never generate fake reviews or ratings.

==================================================
DISCOVERY CONTENT
==================================================

KarenSeir homepage and accommodation landing pages need real merchandising:

Popular destinations
Weekend escapes
Nature stays
Beach stays
Pool stays
Traditional stays
Family travel
Group travel
Seasonal ideas
Nearby experiences

These modules must use real catalog/content data rather than fabricated
availability.

==================================================
CROSS-SELL
==================================================

This is where KarenSeir should exceed a standalone accommodation marketplace.

After destination/dates are known, connect accommodation with:

Flight
Train
Car rental
Restaurant
Attraction
Pool/Sport
Event
Tour
Guide
Tourist transport

Example:

User chooses a villa in Ramsar
→ suggest transport
→ local experiences
→ restaurant reservation
→ attraction tickets
→ guide
→ return travel

All within ONE Trip.

==================================================
AI DISCOVERY
==================================================

The AI assistant should understand requests such as:

"برای آخر هفته شمال، ۸ نفر هستیم،
ویلای استخردار تمیز تا ۲۰ میلیون می‌خوام،
خیلی از تهران دور نباشه."

It should translate that into structured constraints:

destination flexibility
dates
8 guests
villa
pool
budget
distance preference

Then query REAL inventory.

It may relax constraints only after informing the user.

Never fabricate a property.

==================================================
IMPORTANT PRODUCT PRINCIPLE
==================================================

KarenSeir is not:

a homepage
+ flight tab
+ hotel tab
+ contact-support buttons.

It is:

TRAVEL MARKETPLACE
+ BOOKING ENGINE
+ DISCOVERY ENGINE
+ TRIP MANAGEMENT
+ ORGANIZATIONAL TRAVEL
+ FINANCIAL/CREDIT LAYER
+ AI ORCHESTRATION
+ HUMAN OPERATIONS.

Audit the existing implementation against this definition and continue
closing the gaps rather than merely documenting them.