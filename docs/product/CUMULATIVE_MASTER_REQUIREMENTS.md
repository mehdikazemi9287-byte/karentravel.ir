IMPORTANT — ALL PREVIOUS REQUIREMENTS REMAIN ACTIVE

The new visible-product priority DOES NOT cancel, replace or postpone the
previous KarenSeir requirements.

Treat ALL previously specified work as one cumulative MASTER BACKLOG.

Continue from the proven live source:

/home/ubuntu/karenseir-current

Do not throw away completed work.
Do not rebuild working capabilities unnecessarily.
Do not forget partially implemented domains.

==================================================
MASTER SCOPE — ALL OF IT MUST BE COMPLETED
==================================================

The final KarenSeir product must include ALL previously discussed domains:

1. PUBLIC TRAVEL MARKETPLACE
- Homepage
- Discovery
- Destinations
- Search
- Comparison
- Recommendations
- Cross-sell
- Content/discovery modules

2. COMPLETE BOOKING ENGINE
- Search
- Availability
- Recheck
- Selection
- Traveler/guest data
- Rules
- Hold
- Reservation
- Payment
- Confirmation
- Issuance
- Ticket/Voucher
- Modification
- Cancellation
- Refund
- Settlement
- After-sales

3. FLIGHT
- Domestic/international
- One-way/round-trip/multi-city
- Passenger types
- Cabin/fare
- Baggage
- Rules
- Filters
- Recheck
- Booking
- PNR/ticket
- Cancellation/refund

4. HOTEL

5. VILLA / ACCOMMODATION MARKETPLACE
- Hotel
- Villa
- Apartment
- Suite
- Ecolodge
- Cabin
- Traditional stays
- Nature/forest/beach/pool properties
- Marketplace discovery
- Property detail
- Availability calendar
- Instant booking
- Request-to-book
- Supplier/host operations

6. TRAIN

7. TOUR / PACKAGE

8. CAR RENTAL

9. RESTAURANT + QR RESERVATION

10. POOL / SPORT

11. ATTRACTIONS / EXPERIENCES

12. EVENTS / TICKETS

13. EVENT HALLS / CEREMONIES

14. TRAVEL GUIDES

15. HANDICRAFTS

16. TOURIST TRANSPORT

17. MULTI-SERVICE TRIP
A trip may contain multiple independent reservations:
flight + hotel + car + restaurant + activity + event + transport etc.

18. TRIP BASKET / TRIP BUILDER
- Multi-service planning
- Independent inventory expiry
- Recheck
- Alternatives
- Price/availability changes

19. TRAVELER PROFILES
- Reusable traveler data
- National ID/passport where applicable
- Secure handling

20. CHECKOUT
- Booking summary
- Travelers
- Rules
- Price breakdown
- Funding
- Payment
- Confirmation

21. MY TRIPS

22. TRIP DETAIL

23. TRIP TIMELINE

24. TRIP OPERATIONS CENTER

25. «چه چیزی در سفر من تغییر کرده؟»

26. AFTER-SALES
- Change
- Cancel
- Partial cancel
- Refund
- Partial refund
- Supplier follow-up
- Case management
- Human intervention

27. AI TRAVEL ASSISTANT

The assistant must support:
- discovery
- search
- comparison
- itinerary
- budgeting
- booking assistance
- existing bookings
- trip changes
- disruptions
- cancellation guidance
- organizational travel
- human escalation

Never fabricate inventory, price or booking status.

28. HUMAN SUPPORT

AI messages and human-support messages must remain distinguishable.

29. NOTIFICATION ENGINE
- Web
- App
- Push
- SMS
- Email where configured
- Deep links
- Event-driven notifications

30. CUSTOMER PANEL

31. ORGANIZATION PANEL

32. SUPPLIER PANEL

33. AGENCY PANEL

34. ADMIN / OPERATIONS PANEL

35. ENTERPRISE TRAVEL

Including:
- Business travel
- Missions
- Employee travel
- Project accommodation
- Workforce accommodation
- New employee relocation
- Team building
- Incentive travel
- Organizational guests
- Employee welfare
- Organizational events
- Group travel
- Travel Desk

36. ORGANIZATION STRUCTURE
Organization
→ subsidiary
→ branch
→ department
→ cost center
→ project
→ employee/traveler

37. ENTERPRISE RBAC

38. TRAVEL POLICY ENGINE

39. APPROVAL ENGINE
- Single
- Multi-level
- Conditional

40. CORPORATE TRAVEL REQUEST

REQUEST
→ POLICY
→ APPROVAL
→ SEARCH/RFQ
→ RESERVATION
→ FUNDING
→ BOOKING
→ TRIP
→ SETTLEMENT

41. RFQ / QUOTATION ENGINE

RFQ
→ Suppliers
→ Quotes
→ Comparison
→ Revision/Negotiation
→ Selection
→ Approval
→ Proforma
→ Order/Contract
→ Fulfillment
→ Settlement

42. GROUP BOOKING
- Traveler roster
- Rooming
- Transport
- Meals
- Activities
- Venue
- Quote
- Deposit
- Remaining payment
- Documents
- Coordinator

43. ORGANIZATIONAL CREDIT

44. EMPLOYEE BENEFIT / CREDIT

45. WALLET

46. INSTALLMENTS

47. CASH / ONLINE PAYMENT

48. CHEQUE

49. BANK TRANSFER

50. DEFERRED SETTLEMENT

51. SALARY-DEDUCTION MODELS WHERE CONFIGURED

52. SPLIT FUNDING

Examples:
Organization + Employee
Benefit + Employee
Wallet + Online
Credit + Online

53. FINANCIAL LEDGER

54. BUDGET ENGINE

55. INVOICE / PROFORMA / STATEMENT

Correctly distinguish:
Quote
Proforma
Order
Receipt
Invoice
Credit Note
Statement

56. REFUND FUNDING

Refund money/credit to the correct original funding sources.

57. RECONCILIATION

Detect:
PAID_NOT_BOOKED
BOOKED_PAYMENT_UNKNOWN
CREDIT_RESERVED_BOOKING_EXPIRED
REFUND_MISMATCH
SUPPLIER_SETTLEMENT_MISMATCH

58. SUPPLIER PAYABLE

59. ORGANIZATION RECEIVABLE

60. SETTLEMENT

61. GIFT CARD

62. TRAVEL CREDIT

63. EMPLOYEE BENEFIT

64. CORPORATE GIFT / BENEFIT CAMPAIGNS

Support:
- single recipient
- bulk employees
- groups/departments
- campaigns
- configurable amount
- validity
- eligible services
- partial consumption where permitted
- wallet/ledger connection
- secure redemption
- reporting

65. CORPORATE DASHBOARD

66. FINANCE DASHBOARD

67. OPERATIONAL REPORTING

68. FINANCIAL REPORTING

69. SUPPLIER OPERATIONS

70. ADMIN OPERATIONS
Including queues for:
- failed booking
- issuance
- refunds
- payment mismatch
- supplier failure
- action required
- support cases

71. MULTI-TENANCY

72. RBAC

73. AUDIT LOG

74. IDEMPOTENCY

75. CONCURRENCY PROTECTION

76. SECURITY / PRIVACY

77. DESKTOP

78. MOBILE

79. COMPLETE RTL

80. KARENSEIR DESIGN SYSTEM

Use the approved KarenSeir visual direction:
dark navy
turquoise
premium
modern
Iranian
Vazirmatn
RTL

Do not replace it with generic beige/orange/purple styling.

==================================================
EXISTING SYSTEMS / BENCHMARKS
==================================================

Also preserve the previous instruction to investigate existing CheckLine
capabilities.

CheckLine:
transactional capability benchmark and possible approved integration source.

Jabama:
accommodation marketplace and organizational/gift capability benchmark.

Alibaba and other major platforms:
travel discovery, marketplace completeness and UX benchmark.

KarenSeir Figma:
visual/product design source of truth.

DO NOT visually clone any competitor.

==================================================
EXTERNAL INTEGRATIONS ALSO REMAIN REQUIRED
==================================================

Do not forget:

DNS/TLS
real Supplier integration
ZarinPal
Kavenegar

But external blockers must NOT stop internal implementation.

==================================================
EXECUTION STRATEGY
==================================================

Do NOT attempt this as one giant rewrite.

Maintain one MASTER GAP MATRIX:

DOMAIN
CURRENT_STATE
FRONTEND
BACKEND
DATA
FIGMA
E2E
EXTERNAL_DEPENDENCY
NEXT_ACTION

Then execute continuously in vertical slices.

CRITICAL CHANGE:

Visible customer-facing work and underlying domain work must now progress
TOGETHER.

Do not spend multiple iterations implementing invisible backend capabilities
while the public site remains unchanged.

For every major domain:

DOMAIN MODEL
→ API
→ CUSTOMER UI
→ OPERATIONS UI if applicable
→ DESKTOP/MOBILE
→ E2E
→ PUBLIC DEPLOY
→ PUBLIC VISUAL VERIFICATION

==================================================
MIGRATION 20260928_34
==================================================

The previous package `01adfcb` is NOT abandoned.

Keep:
- organizational request
- policy/approval
- supplier RFQ
- group travel benefit draft

as part of the cumulative implementation.

Do not discard or rewrite working code.

However, coordinate migration `20260928_34` with the next safe production
release rather than using the migration as evidence that the visible product
is complete.

If AGENTS.md requires explicit user approval for that production migration,
request approval at the actual deployment point.

==================================================
NO MORE FALSE COMPLETION
==================================================

Do NOT report KarenSeir complete because:

- routes return 200
- containers are healthy
- APIs exist
- migrations pass
- unit tests pass
- placeholders render
- contact-support fallback exists
- isolated E2E passes

Those are technical checks, not product completion.

A capability is COMPLETE only when the applicable user journey is actually
usable end-to-end.

==================================================
CURRENT IMMEDIATE PRIORITY
==================================================

Start with the previously defined visible SLICE 1:

Homepage
+ Navigation
+ Multi-vertical Search
+ AI Assistant entry
+ Discovery modules

Deploy it to the proven public production path and verify visually.

THEN continue automatically through the entire MASTER BACKLOG above.

Do not stop after Slice 1.
Do not ask what to do next after each slice.

Proceed sequentially through implementable work.

Only stop/request input for:
- explicit production migration approval when required
- real financial authorization
- real SMS authorization
- unavailable credentials
- commercial/legal supplier decisions
- destructive/high-risk production actions

Otherwise continue autonomously.

Keep token consumption low:
implement first,
test targeted changes,
report only deltas,
do not repeatedly restate the backlog.