/* Personal panel vs organization panel (Launch V1 item 8).
 *
 * A person has one global role (users.role) but may also be a member of one or more organizations
 * (employee_assignments + enterprise_grants, listed by GET /enterprise/context). The backend already
 * authorizes every /enterprise/* call by that membership; this file lets the panel shell do the same,
 * so a regular customer who is also an employee or org manager can open the organization panel and
 * switch back to the personal panel without changing account.
 *
 * Usability layer only, like lib/panel-access.ts: the API stays the authority on every call.
 * Each rule below mirrors the guard of the endpoint the page reads (backend/app/enterprise.py).
 */

export type OrgMembership = {id: string; name: string; permissions: string[]};

/** Any of these enterprise permissions opens organization-wide records (enterprise.py: summary / org_reader). */
const RECORDS = ['requests.read_all', 'policy.manage', 'roles.manage'];
/** enterprise.py: GET /organizations/{org}/members. */
const MEMBERS = ['roles.manage', 'policy.manage', 'requests.on_behalf', 'benefits.manage'];
/** backend/app/org_access.py::PASSENGERS — saved passengers of the organization. */
const PASSENGERS = ['roles.manage', 'requests.read_all', 'requests.on_behalf'];

/** Organization pages a member may open by membership; null = any active membership is enough.
 *  Since Launch V1 8.3 (owner decision 2026-11-24) every organization page is opened by membership + grant;
 *  the global role only still counts for legacy organization roles and for the company's own staff. */
export const ORG_PAGE_PERMISSIONS: Record<string, string[] | null> = {
  '/employee': null,                    // /enterprise/context + /enterprise/requests (own requests)
  '/organization/requests': null,       // /enterprise/requests filters to own / approver / read_all
  '/organization/policy': null,         // GET /organizations/{org}/policy: membership
  '/organization': RECORDS,             // /summary
  '/organization/reports': RECORDS,     // /summary
  '/organization/bookings': RECORDS,
  '/organization/credit': RECORDS,      // org_reader
  '/organization/billing': RECORDS,     // org_reader (/statement)
  '/organization/audit': RECORDS,       // org_reader
  '/organization/members': MEMBERS,
  '/organization/structure': RECORDS,   // GET /organization/overview (scoped to these orgs); editing needs roles.manage
  '/organization/passengers': PASSENGERS, // panel_ops._scope_access (org_access.PASSENGERS)
  '/organization/financial-context': ['requests.read_all'], // ecosystem_finance.organization_links
};

function clean(path: string): string {return (path || '/').replace(/\/+$/, '') || '/';}

/** The page rule governing a path: exact page, else the longest page prefix (detail pages). */
function ruleFor(path: string): string[] | null | undefined {
  const p = clean(path);
  if (p in ORG_PAGE_PERMISSIONS) return ORG_PAGE_PERMISSIONS[p];
  const prefix = Object.keys(ORG_PAGE_PERMISSIONS).filter(h => h !== '/organization' && p.startsWith(h + '/')).sort((a, b) => b.length - a.length)[0];
  return prefix ? ORG_PAGE_PERMISSIONS[prefix] : undefined;
}

/** True when at least one of the user's organizations lets them open this organization-area path. */
export function orgAllows(path: string, orgs: OrgMembership[]): boolean {
  if (!orgs.length) return false;
  const rule = ruleFor(path);
  if (rule === undefined) return false;
  if (rule === null) return true;
  return orgs.some(o => o.permissions.some(p => rule.includes(p)));
}

/** Organization pages opened by membership, in registry order (used to extend the role-based nav). */
export function orgPagesFor(orgs: OrgMembership[]): string[] {
  return Object.keys(ORG_PAGE_PERMISSIONS).filter(h => orgAllows(h, orgs));
}

/** Where the organization panel starts for this person: the overview for managers, else the employee desk. */
export function orgHomeFor(orgs: OrgMembership[]): string | null {
  if (!orgs.length) return null;
  return orgAllows('/organization', orgs) ? '/organization' : '/employee';
}

export type PanelContext = {kind: 'personal' | 'organization'; label: string; href: string};

/** The two panels a person can switch between. The organization entry appears only with a membership
 *  or an organization role, so a plain customer sees no switcher at all. */
export function panelContextsFor(roleOrgHome: string | null, orgs: OrgMembership[]): PanelContext[] {
  const orgHome = orgHomeFor(orgs) ?? roleOrgHome;
  if (!orgHome) return [];
  const name = orgs.length === 1 ? `پنل سازمان: ${orgs[0].name}` : 'پنل سازمان';
  return [{kind: 'personal', label: 'حساب شخصی', href: '/account'}, {kind: 'organization', label: name, href: orgHome}];
}
