# Portal Re-Verification — 2026-09-11

Real-browser + API verification of every portal after the public-media and
notification-foundation deploys. Sessions minted server-side (dev-login is 404 in
prod, OTP provider disabled); temporary role users created and deleted.

## Matrix

| Portal | Route | Connected? | Evidence |
|---|---|---|---|
| Customer / B2C | `/account` | **DONE** | 12 API calls all 200 (`/me/profile,travellers,wallets,payments,reservations,notification-preferences,installment-plans,installments,invoices,trips,notifications`, `/support/cases`); real name/wallet (۵۰۰٬۰۰۰), traveller row, honest "no payment credential" state; empty states; RTL; 0 console errors |
| Customer trips list | `/trips` | **DONE** | `ConnectedTrips`, `/me/trips` 200 |
| Customer trip detail | `/trips/[id]` | **MOCK** | explicit `<MockNotice>` — "رزرو، واچر و مسافران این سفر نمونه" |
| Customer manage-booking | `/manage-booking/[id]` | **PARTIAL** | real UUID → `ConnectedManageBooking` (connected); literal `book1` etc. → mock |
| Customer support | `/support` | **DONE** | `SupportLanding` + `SupportComposer`, `/support/cases` 200 |
| Corporate | `/organization` | **DONE** | `ConnectedOrganization`, `/organization/overview` 200; real org ("سازمان اعتبار عمومی · active"), cost-centre/approval counts, empty states. Minor: page uses the public `<Shell>` header, not the authed header |
| Corporate finance | `/finance` | **CONNECTED (API)** | `ConnectedFinance` → `/finance/reconciliation` 200 for `finance_operator`, 403 for others. Not browser-verified — no finance user seeded in prod |
| B2E / Employee | `/employee` | **MOCK** | `app/page.tsx` `Employee()` → hardcoded `Dashboard` (۴۸٬۰۰۰٬۰۰۰ ریال, every tile labelled "Mock"); **zero API calls**. No employee credit/approval/request component exists |
| Agency / B2B | `/agency` | **PARTIAL** | `/agency/dashboard` 200 + RBAC enforced (agency↔backoffice↔supplier mutually 403); UI is the generic `ConnectedRolePanel` (sub-agency form + JSON dump). No dedicated dashboard / booking / traveller / commission views |
| Supplier | `/supplier` | **DONE** | fully verified in the media workstream — upload/preview/replace/delete, membership scoping, cross-supplier + cross-tenant isolation |
| Admin | `/admin` | **DONE** | `ConnectedAdmin`, `/admin/users` 200; real tenant-1 user list, role change with privilege-escalation guard + audit; cross-tenant → 403 |
| Backoffice / Ops | `/backoffice`, `/integrations` | **DONE** | `ConnectedRolePanel kind=backoffice`, `/backoffice/overview` 200; real reservations (KS-7E01247…, KS-VILLA-…), invoice-issue mutations, supplier-status management, human support reply |
| White-label | `/white-label` | **MOCK** | explicit "Prototype", hardcoded credit figures |

Other mock/demo routes: `/nearby`, `/services`, `/booking/confirmation`, `/assistant`.

## RBAC / tenant isolation — 18/18 API checks pass

- customer token → every admin/ops/agency/backoffice/finance/supplier endpoint = 403
- agency ↔ backoffice ↔ supplier — mutually 403 (no privilege bleed)
- faraz (tenant 2) → aftab admin data = 403
- `_supplier_scope` membership boundary holds (verified separately)

## Prod seeding gap (not a code defect)

Prod tenant `aftab-bank` seeds only `employee, welfare_manager, supplier,
organization_admin`. No `agency_partner / backoffice_expert / finance_operator /
tenant_admin / platform_admin` user exists — those portals can only be exercised
by creating a user. A prod seed/backfill for operator roles is recommended.

## Internally-implementable gaps found

1. **B2E / Employee portal** — replace the mock `Dashboard` with a connected view
   over `/me/*` + org credit + `/approvals` (the APIs already exist).
2. **Agency portal** — dedicated dashboard/bookings/commission UI instead of the
   generic JSON panel.
3. **Trip detail `/trips/[id]`** — wire to `/trips/{id}` + `/trips/{id}/timeline`
   (the "چه چیزی در سفر من تغییر کرده؟" event feed already exists server-side).
4. Corporate `/organization` — use the authenticated shell header.
