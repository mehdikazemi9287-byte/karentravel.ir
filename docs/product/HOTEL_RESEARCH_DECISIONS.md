# Hotel decisions — 2026-09-29 / SOURCE

Research source observation is not a supplier contract or implementation claim. No research appendix was provided with the latest directive. Existing GRS code is not proof of a credential or live integration. Booking.com below is a reference only.

| ID | User issue | Primary source / observed | Actually observed | Karen Travel decision | Acceptance |
|---|---|---|---|---|---|
| H04 | Guest and room selection lost | Public d2ba674 frontend + isolated API, 2026-09-29; browser-baseline.json | rooms2/adults4 became units1 and no dates, at1440/390 | Preserve an explicit typed stay and room allocation; fail closed on unsupported supplier terms | Quote, snapshot, traveller flow and voucher agree; changed dates require new quote |
| H04-REF | Child/room occupancy affects suitability | [Booking.com child policies](https://developers.booking.com/demand/docs/accommodations/child-policies), observed2026-09-29 | Official guide distinguishes child ages and per-room allocation | Never infer child price or room allocation from one total count | Adult/child allocations validated against supplied contract |
| H05-REF | Matching availability vs generic property price | [Booking.com accommodation search](https://developers.booking.com/demand/docs/accommodations/search-for-available-properties), observed2026-09-29 | Search includes guest details and room allocation | Keep date/party-specific quote separate from property discovery | No unscoped catalog price represented as final selected stay total |
| H01 | Contract and source ownership | User directive2026-09-29 §2.1; frozen V3.1 supplier and booking contracts | Manual contracted stock allowed, with source/owner/validity | Do not invent nightly terms or enable GRS without contractual access | Supplier source and validity attached to published manual inventory |
| H22 | Publication authority | AGENTS.md + latest directive §3 | Prior unapproved schema35 is still pending | Preserve live d2ba674 and candidate1e6ee5e; hotel work SOURCE/PREVIEW only | Fresh authorized release gate before production writes |

Implementation: room/date loss is OPEN. Live sales: UNVERIFIED. No new provider is selected by these references.
