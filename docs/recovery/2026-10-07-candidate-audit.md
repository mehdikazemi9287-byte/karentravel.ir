# Candidate audit — 2026-10-07 (evidence from the candidate API/DB; nothing here was run against production data)

## `GET /public/tour-products` = 503
Not a defect. `_public_search_identity()` fails closed with «کاتالوگ عمومی هنوز راه‌اندازی نشده است» when the `public_search_identity` tenant/user does not exist. The candidate database was restored from the catalog scratch dump and seeded with the development users only, so that identity is absent. Production has it (tenant 3) and answers `200 []` — there is no published tour product.

## Tour catalog and departure dates (migration 39, candidate only)
- `catalog_tours` / `catalog_tour_departures`: title + the dates the source recorded. No price, capacity, currency, supplier or tenant column (asserted by test). Every row is `draft`, `sellable=false`, `price=null`; admin read API only (`/admin/catalog/tours`).
- CheckLine: 59 tours, 165 date rows imported; 162 valid Jalali dates converted (2023-10-23 … 2026-10-05), 3 invalid kept as raw text only, **0 on or after 2026-10-06**. 15 were disabled and 7 sold out in the source.
- A sellable tour is still only a supplier-owned `tour_products` + `tour_departures` row (tenant, contract, capacity, price). Nothing is copied there. Open decision: which tenant/supplier owns these tours and what their new departures and rates are.

## Supplier mapping and hotel rate/availability port
- `catalog_hotel_provider_mappings` (provider, provider_hotel_id, unique per provider) — entered and verified in the admin API; audited.
- `app/hotel_rates.py`: `HotelRateSource` protocol, `RateQuery`/`RateOffer`, `validate_offers` (drops zero/negative/non-integer amount, unknown currency, wrong hotel id, missing ref, expired or timezone-less validity), `GET /catalog/hotels/{slug}/rates`.
- `RATE_SOURCES` is empty at runtime (test asserts it). Result today: every hotel `rate_available=false`, `bookable=false`; the rates endpoint answers `no_rate_source`. `bookable` additionally needs `BOOKING_FROM_CATALOG_ENABLED`, which is false.
- To connect GRS: implement `HotelRateSource.quote` on top of `grs_adapter`/`grs_contract.normalize_rate_plan_price`, register it under key `grs`, verify mappings. Blocked on the real GRS endpoint, token, unit and wire contract (`provider_inventory` in CAPABILITY_REGISTRY).

## Flight / airline / airport reference data
- 72 airlines: all with IATA, 69 with ICAO, 8 without a Persian name, 4 IATA codes shared by two rows (needs review), 10 countries.
- 174 airports in the 6 catalog countries only (IR 77, TR 66, AE 12, IQ 12, GE 4, AM 3): all with ICAO, all with timezone, 7 without a Persian name, 51 not linked to a catalog city, `scope` known for 52 (international) and unknown for 122.
- No airport exists for the 14 countries added from CheckLine. No schedule, fare or seat data exists anywhere (by design; needs a flight supplier).

## Panels, operations, timeline, notifications
257 operations in the candidate API. Parameterless GET routes × 10 roles + anonymous (66 routes): no sensitive route open to anonymous; `/admin` catalog routes only platform_admin and backoffice_expert; `/finance` only finance_operator and platform_admin; `/supplier` only supplier and platform_admin; `/agency` only agency_partner and platform_admin; `/backoffice` backoffice_expert, platform_admin (tenant_admin on 1).

| Area | Backend routes | State (CAPABILITY_REGISTRY) | Real blocker |
|---|---|---|---|
| Customer (`/me`, `/trips`, `/saved-trips`, `/wallets`) | 36 | my_trips, wallet, invoice READY_BLOCKED_EXTERNAL | live OTP |
| Supplier | 23 | accommodation_marketplace PARTIAL | real supplier inventory |
| Agency/partner | 3 | — (thin) | product decision on scope |
| Finance | 5 (+payments 6) | payment_gateway READY_BLOCKED_EXTERNAL | merchant, HTTPS callback |
| Support / operations (`/support`, `/backoffice`, `/reservations`) | 36 | human_support LIVE | — |
| Trip timeline / «چه چیزی تغییر کرده» | part of `/me`, `/trips` | trip_timeline, trip_changes READY_BLOCKED_EXTERNAL | live OTP to reach it as a customer; provider change events (GRS webhook) |
| Notifications | in_app/push/sms | READY_BLOCKED_EXTERNAL | push credential, Kavenegar template |
| Admin | 17 | `/admin/catalog` built and QA'd in this work | — |

Not changed in this work: none of the panels above except `/admin/catalog`. Tests selected by `tenant|rbac|isolation|cross`: 47 pass, 3 fail, 3 skipped — the 3 failures are in the 13 that also fail on the baseline commit (8 of those 13 are `test_supplier_assets` PermissionError on the media directory in the test container).
