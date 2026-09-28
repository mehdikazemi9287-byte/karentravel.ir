ADD — KARENSEIR GIFT, BENEFIT & TRAVEL CREDIT ENGINE

Do not implement "Gift Card" as a static voucher page.

Create a reusable Gift / Benefit / Travel Credit domain serving both B2C
and B2B/B2B2C.

==================================================
1. GIFT PRODUCTS
==================================================

Support:

PERSONAL_GIFT_CARD
ORGANIZATION_GIFT_CARD
TRAVEL_CREDIT
EMPLOYEE_BENEFIT
CAMPAIGN_CREDIT
SERVICE_SPECIFIC_CREDIT
DESTINATION_SPECIFIC_CREDIT

Gift value may be:

fixed amount
custom amount
organization-defined amount

==================================================
2. PERSONALIZATION
==================================================

Support:

recipient name
sender/person/organization
message
occasion
approved visual theme
live preview
optional validity period

Possible occasions:

birthday
marriage
Nowruz
Yalda
employee appreciation
performance reward
retirement
organizational occasion
travel incentive

Do not copy another company's card designs.

Use KarenSeir visual identity.

==================================================
3. DELIVERY
==================================================

Support controlled delivery:

private link
account assignment
SMS when integration is approved
email when configured
app/push where available
QR where appropriate

Never expose redeemable tokens publicly.

==================================================
4. ORGANIZATION BULK DISTRIBUTION
==================================================

This is critical.

Organization must be able to issue benefits to:

one employee
employee list
department
branch
employee group
campaign population

Support bulk import/API where appropriate.

Example:

"برای ۱۲۰۰ پرسنل، نفری ۵ میلیون تومان اعتبار سفر نوروزی"

must NOT require creating 1200 cards manually.

==================================================
5. RULES
==================================================

Credit can optionally be constrained by:

service category
travel/leisure
hotel
villa
tour
flight
train
restaurant
pool/sport
event
attraction

and:

validity dates
employee
family
organization
campaign
minimum spend
maximum contribution

Rules must be server-authoritative.

==================================================
6. REDEMPTION
==================================================

Lifecycle:

CREATED
→ FUNDED
→ ISSUED
→ DELIVERED
→ CLAIMED
→ PARTIALLY_USED
→ USED
→ EXPIRED

Also handle:

CANCELLED
REVOKED

where contractual policy permits.

Support partial consumption when policy allows.

==================================================
7. WALLET CONNECTION
==================================================

Do not create an isolated gift-card balance system.

Gift/benefit credit should integrate with KarenSeir Wallet/Ledger.

Example:

Trip price: 8,000,000
Gift credit: 5,000,000
Remaining customer payment: 3,000,000

Checkout must calculate this correctly.

==================================================
8. COMBINATION RULES
==================================================

Policy engine must determine whether Gift Credit can combine with:

organization credit
personal wallet
discount
installment
online payment
other benefit credits

Never assume stacking is allowed.

==================================================
9. CORPORATE CAMPAIGNS
==================================================

Create Campaign:

name
organization
population
budget
allocation/person
validity
eligible services
funding source
delivery method
usage rules

Examples:

Nowruz Travel Benefit
Summer Leisure Credit
Employee Birthday
Top Performer Reward
Family Travel Program

==================================================
10. ORGANIZATION DASHBOARD
==================================================

Show real metrics:

allocated
issued
claimed
consumed
remaining
expired
campaign utilization
employee utilization

Respect employee privacy.

==================================================
11. REFUND
==================================================

If a booking paid partly by gift/benefit credit is cancelled:

apply cancellation penalty
calculate refundable amount
restore eligible credit according to policy
refund other payment components separately

Do not convert organization-funded benefit into unrestricted cash.

==================================================
12. SECURITY
==================================================

Gift tokens must be:

unguessable
single-purpose
revocable where permitted
expiry-aware
protected against replay

Store redemption/audit history.

==================================================
13. AI ASSISTANT
==================================================

Assistant should understand:

"برای ۵۰۰ نفر پرسنل کارت سفر ۳ میلیونی برای نوروز می‌خواهم."

and create a structured organizational campaign draft:

500 recipients
× 3,000,000
= 1,500,000,000 total allocation

Then apply:
eligibility
validity
service restrictions
funding
approval
distribution

without activating financial liability until authorized.

==================================================
TARGET
==================================================

Gift Card is only one presentation layer.

The underlying KarenSeir capability must be:

GIFT
+ BENEFIT
+ TRAVEL CREDIT
+ CORPORATE CAMPAIGN
+ WALLET
+ POLICY
+ BULK DISTRIBUTION
+ REDEMPTION
+ REPORTING