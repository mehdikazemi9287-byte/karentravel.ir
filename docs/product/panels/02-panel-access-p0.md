# Panel access P0 fixes (audit 01, items P0-3, P0-4, P0-5)

## Done
- **P0-5 `/search` dead link**: customer app tab, home button and "سفر دوباره" links now go to `/search/results`. `app/search/page.tsx` is a server redirect (307) to `/search/results`, keeping the query string.
- **P0-3 role-aware nav and guard**: `lib/panel-access.ts` is the single registry of panel links and the rule each one needs. The rules mirror the backend guard of the page's endpoint. Role permissions come from `lib/role-permissions.json`, an exact copy of `backend/app/security.py::ROLE_PERMISSIONS`; `backend/tests/test_panel_access_registry.py` fails if they drift. `PanelShell` filters the sidebar and the mobile ops tabs by role. On a page the role cannot use, it renders a Persian "دسترسی ندارید" card with a link to the user's own panel (and to the right page when one exists, e.g. agency → `/agency/tours`). `roleLinks()` (the account menu) uses the same registry.
- **P0-4 agency tours**: `/agency/tours` (agency nav "تورهای من") reuses the Safarsaz partner UI. Backend: Safarsaz partner scope = supplier memberships ∪ the tour organiser linked to each agency the user is a member of (`Agency.supplier_id`). The admin sets that link with `PUT /admin/partners/agencies/{id}/tour-organiser` (tenant:manage, one organiser per agency, audited). There is a select for it in "تأمین‌کنندگان و آژانس‌ها". New `GET /safarsaz/tours/{id}/bookings` lists bookings received per departure (capacity, remaining, travellers, amount, status). It returns no customer identity, and another organiser's tour returns 404.

## Why no Next middleware
The session is in `sessionStorage` and goes out only as a Bearer header. Page requests carry no cookie or role the server could read. A browser-written role cookie would be forgeable and add nothing over the API checks. So the guard is client-side (usability), and the API stays the authority. No server check was weakened.

## Tests
- `backend/tests/test_agency_tours_access.py`: link is admin-only and unique; the agency has no access before the link; cross-agency isolation on read, update, departures and bookings; bookings appear after publish and booking; no PII; losing membership removes access.
- `tests/unit/panel-access.cjs`: nav sizes per role, guard decisions, agency pointer, account menu, every registered page exists.

## Remaining / next
- Back office and finance still share the `admin` area (now filtered); separate areas are P2.
- JourneyShell staff pages (`/backoffice/*`, `/finance/records|accounting`) are not guarded by PanelShell. They still show API 403s.
- Departure manifest (traveller names) for organisers is P1-5. It needs a privacy decision.
- P0-1, P0-2 and P0-6 (after-sales loop, refund queue, reconciliation actions) are not part of this change.
- Playwright role smoke tests (P2-10) need the e2e servers.
