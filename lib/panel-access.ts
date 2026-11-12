/* Single source of truth for panel navigation and the client route guard.
 *
 * Every panel link carries the rule that its page's main API endpoint enforces (see the guard named next to each rule).
 * Role → permission sets come from `role-permissions.json`, a copy of `backend/app/security.py::ROLE_PERMISSIONS`
 * that a backend test keeps identical (`backend/tests/test_panel_access_registry.py`).
 *
 * This is a usability layer, not a security boundary: the API still checks role, permission, tenant and
 * supplier/agency membership on every call. There is no Next middleware on purpose: the session lives in
 * sessionStorage and is sent only as a Bearer header, so a request for a page carries no cookie or role the
 * server could read. A role cookie written by the browser could be forged and would add nothing over the API
 * checks, so the guard runs in the panel shell, and the API keeps the authority.
 */
import ROLE_PERMISSIONS from './role-permissions.json';

export type Area = 'customer' | 'organization' | 'agency' | 'supplier' | 'ops' | 'finance' | 'admin';
export type Rule = {roles?: string[]; anyPermission?: string[]; notRoles?: string[]};
export type NavItem = {label: string; href: string; area: Area; rule?: Rule; menu?: boolean; inNav?: boolean; moved?: Record<string, string>; group?: string; mobile?: number; glyph?: string};

const PERMS = ROLE_PERMISSIONS as Record<string, string[]>;
export function hasPermission(role: string, permission: string): boolean {
  const p = PERMS[role] ?? [];
  return p.includes(permission) || p.includes('platform:manage');
}
export function allows(rule: Rule | undefined, role: string): boolean {
  if (!rule) return true;
  if (rule.notRoles?.includes(role)) return false;
  if (rule.roles && rule.roles.includes(role)) return true;
  if (rule.anyPermission && rule.anyPermission.some(p => hasPermission(role, p))) return true;
  return !rule.roles && !rule.anyPermission;
}

export const roleHome: Record<string, string> = {customer: '/account', employee: '/employee', manager: '/organization', welfare_manager: '/organization', organization_admin: '/organization', supplier: '/supplier', agency_partner: '/agency', backoffice_expert: '/backoffice', finance_operator: '/finance', tenant_admin: '/admin', platform_admin: '/admin'};
export const ROLE_FA: Record<string, string> = {customer: 'مشتری', employee: 'کارمند سازمان', manager: 'مدیر سازمان', welfare_manager: 'مدیر رفاه', organization_admin: 'مدیر سازمان', supplier: 'تأمین‌کننده', agency_partner: 'آژانس همکار', backoffice_expert: 'کارشناس عملیات', finance_operator: 'کارشناس مالی', tenant_admin: 'مدیر مجموعه', platform_admin: 'مدیر پلتفرم'};

const PARTNERS_AND_PUBLIC = ['customer', 'employee', 'supplier', 'agency_partner'];
const ORG_MANAGERS = ['manager', 'welfare_manager', 'organization_admin', 'tenant_admin', 'platform_admin'];
// Rules mirror the backend guard of each page's endpoint.
const R = {
  any: undefined,
  platform: {roles: ['platform_admin']},                                                              // platform_tenants.platform
  tenantAdmin: {roles: ['tenant_admin', 'platform_admin']},                                           // tenant:manage / TENANT_ADMINS / admin_users
  opsStaff: {anyPermission: ['backoffice:read', 'ledger:read', 'tenant:manage'], notRoles: ['employee', 'customer']},   // ops_console.staff
  desk: {anyPermission: ['support:manage', 'reservation:manage', 'tenant:manage'], notRoles: PARTNERS_AND_PUBLIC},     // train/partner/sales desk agent
  docs: {anyPermission: ['backoffice:read', 'support:manage', 'tenant:manage'], notRoles: ['employee', 'customer']},     // traveller_documents.staff
  editor: {roles: ['platform_admin', 'tenant_admin', 'backoffice_expert']},                           // site_cms.editor
  catalog: {roles: ['platform_admin', 'backoffice_expert']},                                          // catalog_admin guard
  safarsazStaff: {anyPermission: ['reservation:manage', 'tenant:manage'], notRoles: PARTNERS_AND_PUBLIC}, // safarsaz._is_staff
  backoffice: {anyPermission: ['backoffice:read']},
  support: {anyPermission: ['support:manage']},
  tripOps: {anyPermission: ['trip:event:create', 'support:manage', 'backoffice:read']},               // platform_ops.STAFF_READ
  tripChanges: {anyPermission: ['trip:event:create']},
  ledger: {anyPermission: ['ledger:read']},
  financeRead: {anyPermission: ['ledger:read', 'tenant:manage']},                                     // commerce/ledger/receivables finance_read
  supplierFinance: {anyPermission: ['ledger:read', 'reconciliation:manage', 'tenant:manage']},       // supplier_insights.finance
  inventoryStaff: {anyPermission: ['tenant:manage', 'backoffice:read', 'ledger:read']},              // inventory.staff (minus partner inventory:manage)
  inventoryAdmin: {roles: ['tenant_admin', 'platform_admin']},                                        // charter_quotas.admin (staff side)
  orgManager: {roles: ORG_MANAGERS},
  orgMember: {roles: ['employee', ...ORG_MANAGERS]},
  orgRecords: {roles: [...ORG_MANAGERS, 'finance_operator']},                                         // enterprise.org_reader
  agency: {anyPermission: ['agency:manage']},                                                         // platform_ops.agency_user
  supplier: {anyPermission: ['inventory:manage']},                                                    // /supplier/dashboard etc.
  fulfil: {anyPermission: ['reservation:fulfill']},                                                   // /admission-tickets/*
  supplierLinks: {anyPermission: ['inventory:manage', 'ledger:read']},
  quotes: {roles: ['customer', 'employee']},
  serviceDecide: {anyPermission: ['service_request:decide']},                                        // after_sales ops_user
  refunds: {anyPermission: ['refund:manage']},                                                        // after_sales fin_user
  reconcile: {anyPermission: ['reconciliation:manage']},                                              // after_sales recon_user
  agencyReview: {anyPermission: ['license:verify', 'tenant:manage', 'backoffice:read', 'ledger:read'], notRoles: PARTNERS_AND_PUBLIC}, // agency_b2b.staff_reader
  charterReview: {anyPermission: ['inventory:publish', 'tenant:manage', 'backoffice:read'], notRoles: PARTNERS_AND_PUBLIC},     // charter_blocks.staff
  agencyCredit: {anyPermission: ['credit:fund', 'ledger:read'], notRoles: PARTNERS_AND_PUBLIC},                                // agency_b2b.finance_accounts
  staff: {roles: ['backoffice_expert', 'finance_operator', 'tenant_admin', 'platform_admin']},                                // /panel/today for staff areas
  priceChanges: {anyPermission: ['service_request:decide', 'refund:manage', 'tenant:manage'], notRoles: PARTNERS_AND_PUBLIC},     // panel_ops.proposals
  financeOps: {anyPermission: ['ledger:read', 'reconciliation:manage', 'tenant:manage'], notRoles: PARTNERS_AND_PUBLIC},          // panel_ops.finance_read
  approvals: {anyPermission: ['credit:fund', 'refund:manage', 'tenant:manage', 'credit:manage'], notRoles: PARTNERS_AND_PUBLIC},   // /maker-checker/requests (kinds the user may check)
  agencySettlement: {anyPermission: ['settlement:manage', 'ledger:read', 'refund:manage'], notRoles: PARTNERS_AND_PUBLIC},       // agency_settlement.fin_reader
} satisfies Record<string, Rule | undefined>;

/* Mobile bottom navigation (Figma BottomNav 209:393: four destinations + «بیشتر»): order and glyph per page. */
const MOBILE: Record<string, [number, string]> = {
  '/account': [1, '⌂'], '/account/bookings': [2, '✈'], '/account/refunds': [3, '↩'], '/account/wallet': [4, '◫'],
  '/organization': [1, '⌂'], '/organization/requests': [2, '✓'], '/organization/bookings': [3, '✈'], '/organization/passengers': [4, '☺'], '/employee': [1, '⌂'],
  '/agency': [1, '⌂'], '/agency/sell': [2, '✈'], '/agency/bookings': [3, '▤'], '/agency/credit': [4, '◫'],
  '/supplier': [1, '⌂'], '/supplier/fulfillment': [2, '✓'], '/supplier/services': [3, '▤'], '/supplier/settlements': [4, '◫'],
  '/backoffice/queues/service_requests': [2, '▤'], '/admin/ops': [3, '◉'], '/backoffice/price-changes': [4, '±'],
  '/finance/refunds': [2, '↩'], '/finance/approvals': [3, '✓'], '/finance/reconciliation': [4, '⇄'],
  '/admin': [2, '◎'], '/admin/audit': [3, '▤'], '/admin/sla': [4, '⏱'], '/panel/today': [1, '☀'],
};
const I = (area: Area, label: string, href: string, rule?: Rule, extra: Partial<NavItem> = {}): NavItem =>
  ({area, label, href, rule, inNav: true, ...(MOBILE[href] ? {mobile: MOBILE[href][0], glyph: MOBILE[href][1]} : {}), ...extra});
/* Staff pages live in three areas with their own sidebar (spec §1.1): operations, finance and tenant administration. */
const OPS_ADMIN_PAGES = new Set(['/admin/ops', '/admin/train-desk', '/admin/partner-requests', '/admin/sales-desk', '/admin/documents', '/admin/contracts', '/admin/safarsaz',
  '/admin/catalog', '/admin/catalog/reference', '/admin/tours', '/admin/inventory']);
export function staffArea(href: string): Area {
  if (href.startsWith('/finance') || href === '/admin/ecosystem') return 'finance';
  if (href.startsWith('/backoffice') || OPS_ADMIN_PAGES.has(href)) return 'ops';
  return 'admin';
}

export const PANEL_ITEMS: NavItem[] = [
  I('customer', 'نمای کلی', '/account'), I('customer', 'درخواست‌های قطار', '/account/train-requests'), I('customer', 'شهرشاد، پادویرا و سوغات', '/account/partner-requests'),
  I('customer', 'پروفایل و مسافران', '/account/profile'), I('customer', 'رزروها و سفرها', '/account/bookings'), I('customer', 'تغییرات سفر', '/account/changes'),
  I('customer', 'ویزا', '/account/visa'), I('customer', 'مدارک مسافران', '/account/documents'), I('customer', 'پرداخت و فاکتور', '/account/payments'),
  I('customer', 'لغو و استرداد', '/account/refunds'), I('customer', 'تغییر قیمت رزرو', '/account/price-changes'), I('customer', 'کیف پول و اعتبار', '/account/wallet'), I('customer', 'مزایای سازمانی', '/account/benefits'),
  I('customer', 'ذخیره‌شده‌ها و پیشنهادها', '/account/saved'), I('customer', 'اعلان‌ها', '/account/notifications'), I('customer', 'امنیت ورود', '/account/security'), I('customer', 'پشتیبانی', '/account/support'),

  I('organization', 'نمای کلی', '/organization', R.orgManager), I('organization', 'میز کار کارمند', '/employee', R.orgMember),
  I('organization', 'کارکنان و دسترسی‌ها', '/organization/members', R.orgManager, {menu: true}), I('organization', 'درخواست و تأیید سفر', '/organization/requests', R.orgMember),
  I('organization', 'سیاست سفر', '/organization/policy', R.orgManager), I('organization', 'واحدها و مراکز هزینه', '/organization/structure', R.orgManager),
  I('organization', 'اعتبار و اقساط', '/organization/credit', R.orgRecords), I('organization', 'رزروهای سازمان', '/organization/bookings', R.orgManager),
  I('organization', 'صورتحساب و تسویه', '/organization/billing', R.orgRecords), I('organization', 'گزارش', '/organization/reports', R.orgManager),
  I('organization', 'سوابق و گردش تأیید', '/organization/audit', R.orgRecords), I('organization', 'مسافران سازمان', '/organization/passengers', R.orgManager), I('organization', 'تعهد مالی سفر', '/organization/financial-context', R.orgRecords),

  // Agency sidebar (Figma P2 AG-*): grouped like the approved frames — today, my inventory (seller), sell & price, money, the agency itself.
  I('agency', 'امروز', '/agency', R.agency),
  ...([['تورهای من', '/agency/tours'], ['پرواز و بلوک صندلی', '/agency/inventory/flights'], ['اطلاعیه‌های تغییر پرواز', '/agency/inventory/notices']] as [string, string][]).map(([l, h]) => I('agency', l, h, R.agency, {group: 'موجودی من (فروشنده)', menu: h === '/agency/tours'})),
  ...([['فروش با اعتبار آژانس', '/agency/sell'], ['فروش و پیشنهاد قیمت', '/agency/sales'], ['رزروها', '/agency/bookings'], ['مشتریان', '/agency/customers'], ['قواعد markup و کمیسیون', '/agency/pricing']] as [string, string][])
    .map(([l, h]) => I('agency', l, h, R.agency, {group: 'فروش و قیمت'})),
  ...([['حساب و اعتبار', '/agency/credit'], ['صورت تسویهٔ دوره‌ای', '/agency/settlements'], ['کمیسیون', '/agency/commissions'], ['صورتحساب‌ها', '/agency/invoices'], ['تسویه و اسناد', '/agency/documents'], ['گزارش', '/agency/reports']] as [string, string][])
    .map(([l, h]) => I('agency', l, h, R.agency, {group: 'مالی و حساب'})),
  ...([['پروفایل و مجوزها', '/agency/profile'], ['کاربران آژانس', '/agency/users'], ['مسافران آژانس', '/agency/passengers'], ['میز کار کامل', '/agency/workspace'], ['پشتیبانی', '/agency/support']] as [string, string][])
    .map(([l, h]) => I('agency', l, h, R.agency, {group: 'آژانس'})),

  I('supplier', 'نمای کلی', '/supplier', R.supplier, {menu: true}), I('supplier', 'خدمات، نرخ و ظرفیت', '/supplier/services', R.supplier),
  I('supplier', 'تورهای من', '/supplier/tours', R.supplier, {menu: true, moved: {agency_partner: '/agency/tours'}}), I('supplier', 'هتل‌های من', '/supplier/hotels', R.supplier, {menu: true}),
  I('supplier', 'اقامتگاه و تقویم', '/supplier/accommodation', R.supplier), I('supplier', 'سفارش‌ها و تأیید', '/supplier/fulfillment', R.supplier),
  I('supplier', 'کنترل بلیت', '/supplier/admission', R.fulfil), I('supplier', 'درخواست‌های سازمانی', '/supplier/rfqs', R.supplier),
  I('supplier', 'تسویه و قرارداد', '/supplier/settlements', R.supplier, {menu: true}), I('supplier', 'گزارش', '/supplier/reports', R.supplier),
  I('supplier', 'پشتیبانی', '/supplier/support', R.supplier), I('supplier', 'روابط مالی قرارداد', '/supplier/financial-context', R.supplierLinks),

  ...([
    ['پیشخوان عملیات', '/admin/ops', R.opsStaff], ['محتوای سایت', '/admin/content', R.editor], ['وبلاگ', '/admin/blog', R.editor], ['میز بلیت قطار', '/admin/train-desk', R.desk],
    ['خدمات همکار', '/admin/partner-requests', R.desk], ['پرونده‌ی قرارداد', '/admin/contracts', R.opsStaff], ['صف مدارک مسافران', '/admin/documents', R.docs],
    ['کاربران و نقش‌ها', '/admin', R.tenantAdmin], ['مستأجرها و وایت‌لیبل', '/admin/tenants', R.platform], ['سازمان‌ها', '/admin/organizations', R.tenantAdmin],
    ['تأمین‌کنندگان و آژانس‌ها', '/admin/partners', R.tenantAdmin], ['سوابق ممیزی', '/admin/audit', R.tenantAdmin], ['هتل‌ها', '/admin/catalog', R.catalog],
    ['داده‌های مرجع', '/admin/catalog/reference', R.catalog], ['تورها', '/admin/tours', R.catalog], ['سفرساز', '/admin/safarsaz', R.safarsazStaff],
    ['میز گفتگو و فروش', '/admin/sales-desk', R.desk], ['حلقه‌ی همسفران', '/admin/loyalty', R.tenantAdmin], ['کمپین پیامکی', '/admin/sms-campaigns', R.tenantAdmin],
    ['عملیات و پشتیبانی', '/backoffice', R.backoffice], ['مالی', '/finance', R.ledger], ['صندوق و حساب‌ها', '/finance/treasury', R.financeRead],
    ['قوانین فروش', '/admin/commerce', R.tenantAdmin], ['پرواز و موجودی', '/admin/inventory', R.inventoryStaff], ['سهمیه‌ی همکاران', '/admin/charter-quotas', R.inventoryAdmin],
    ['گزارش فروش', '/finance/reports', R.inventoryStaff], ['سود و کمیسیون فروش', '/finance/markup-revenue', R.financeRead], ['خروجی فرانگر', '/finance/journal-export', R.financeRead],
    ['مطالبات سازمان‌ها', '/finance/receivables', R.financeRead], ['دفتر کل و بستن دوره', '/finance/ledger', R.financeRead],
    ['عملکرد و تطبیق تأمین‌کنندگان', '/finance/suppliers', R.supplierFinance], ['روابط مالی اکوسیستم', '/admin/ecosystem', R.financeRead],
    ['صف لغو، تغییر و استرداد', '/backoffice/queues/service_requests', R.serviceDecide], ['صف استرداد مالی', '/finance/refunds', R.refunds], ['تطبیق درگاه', '/finance/reconciliation', R.reconcile],
    ['آژانس‌ها و مجوزها', '/backoffice/agencies', R.agencyReview], ['بلوک‌های چارتر', '/backoffice/charter-blocks', R.charterReview], ['حساب و اعتبار آژانس‌ها', '/finance/agency-accounts', R.agencyCredit],
    ['امروز', '/panel/today', R.any], ['تأییدهای دونفره', '/finance/approvals', R.approvals], ['پیشنهاد تغییر قیمت', '/backoffice/price-changes', R.priceChanges],
    ['پرداخت‌های ناموفق', '/finance/failed-payments', R.financeOps], ['ورود فایل تسویهٔ درگاه', '/finance/settlement-import', R.reconcile], ['پرداخت گروهی بانکی', '/finance/bank-batches', R.refunds],
    ['نرخ مالیات تاریخ‌دار', '/finance/tax-rates', R.financeOps], ['تسویهٔ دوره‌ای آژانس‌ها', '/finance/settlements/agencies', R.agencySettlement],
    ['اعتراض‌های تسویهٔ آژانس', '/finance/settlements/disputes', R.agencySettlement], ['SLA صف عملیات', '/admin/sla', R.tenantAdmin],
  ] as [string, string, Rule][]).map(([label, href, rule]) => I(staffArea(href), label, href, rule, {menu: true})),
  // Staff pages outside the panel shell (JourneyShell): not in the sidebar, but in the account menu for the roles that can use them.
  ...([
    ['مرکز عملیات سفر', '/backoffice/trip-events', R.tripOps], ['تغییرات سفر', '/backoffice/trips', R.tripChanges], ['درخواست‌های تغییر و استرداد', '/backoffice/booking-requests', R.support],
    ['پرونده‌های عملیات', '/backoffice/records', R.backoffice], ['میز پشتیبانی', '/backoffice/support', R.support], ['وضعیت اعلان‌ها', '/backoffice/notifications', R.tripOps],
    ['رکوردهای مالی', '/finance/records', R.ledger], ['حسابداری و کمیسیون', '/finance/accounting', R.ledger],
    ['رسیدگی به درخواست مشتری', '/backoffice/requests', R.serviceDecide], ['صف‌های عملیات', '/backoffice/queues', R.serviceDecide],
    ['تسویهٔ آژانس‌ها', '/finance/settlements', R.agencySettlement],  // guards /finance/settlements/[id] (Phase 2b)
  ] as [string, string, Rule][]).map(([label, href, rule]) => I(staffArea(href), label, href, rule, {menu: true, inNav: false})),
];

/** Access for a page path that has no item of its own (detail pages, editors). */
const STAFF_ROLES: Rule = {roles: ['backoffice_expert', 'finance_operator', 'tenant_admin', 'platform_admin']};
const AREA_FALLBACK: Record<Area, Rule | undefined> = {customer: undefined, organization: R.orgMember, agency: R.agency, supplier: {anyPermission: ['inventory:manage', 'reservation:fulfill']},
  ops: STAFF_ROLES, finance: STAFF_ROLES, admin: STAFF_ROLES};

/** The item that governs a path: the exact item, else the longest item prefix in the same area, else the area rule. */
export function itemFor(area: Area, path: string): NavItem | null {
  const clean = (path || '/').replace(/\/+$/, '') || '/';
  const exact = PANEL_ITEMS.find(i => i.href === clean);
  if (exact) return exact;
  const roots = new Set(['/account', '/organization', '/agency', '/supplier', '/admin', '/backoffice', '/finance', '/employee']);
  const staff = ['ops', 'finance', 'admin'];
  const same = (i: NavItem) => i.area === area || (staff.includes(area) && staff.includes(i.area));
  const prefix = PANEL_ITEMS.filter(i => same(i) && !roots.has(i.href) && clean.startsWith(i.href + '/')).sort((a, b) => b.href.length - a.href.length)[0];
  return prefix ?? null;
}
export function canOpen(area: Area, path: string, role: string): boolean {
  const item = itemFor(area, path);
  return allows(item ? item.rule : AREA_FALLBACK[area], role);
}
export function navFor(area: Area, role: string): NavItem[] {
  const own = PANEL_ITEMS.filter(i => i.area === area && i.inNav && i.href !== '/panel/today' && allows(i.rule, role));
  const today = PANEL_ITEMS.find(i => i.href === '/panel/today');
  return ['ops', 'finance', 'admin'].includes(area) && today && allows(today.rule, role) && own.length ? [today, ...own] : own;
}
export function homeFor(role: string): string {return roleHome[role] ?? '/account';}

/** The area a page belongs to: staff pages declared as 'admin' are placed in ops / finance / admin by their path. */
export function areaFor(area: Area, path: string): Area {
  if (area !== 'admin') return area;
  const item = itemFor('admin', path) ?? PANEL_ITEMS.find(i => i.href !== '/' && path.startsWith(i.href + '/') && ['ops', 'finance', 'admin'].includes(i.area));
  return item && ['ops', 'finance', 'admin'].includes(item.area) ? item.area : staffArea(path);
}
export const AREA_FA: Record<Area, string> = {customer: 'حساب من', organization: 'پنل سازمان', agency: 'پنل همکار', supplier: 'پنل تأمین‌کننده', ops: 'عملیات', finance: 'مالی', admin: 'مدیریت مجموعه'};
const AREA_HOME: Partial<Record<Area, string>> = {ops: '/backoffice/queues/service_requests', finance: '/finance', admin: '/admin'};
/** The other staff areas this role can open (area switcher at the top of the staff sidebar). */
export function staffAreasFor(role: string): Array<{area: Area; label: string; href: string}> {
  return (['ops', 'finance', 'admin'] as Area[]).map(area => {
    const first = navFor(area, role).find(i => i.href !== '/panel/today');
    const home = AREA_HOME[area]; const href = home && canOpen(area, home, role) ? home : first?.href;
    return href ? {area, label: AREA_FA[area], href} : null;
  }).filter((x): x is {area: Area; label: string; href: string} => x !== null);
}
/** Mobile bottom tabs: «امروز» (staff) or the area home, then the area's mobile destinations the role may open; «بیشتر» opens the full menu. */
export function mobileTabsFor(area: Area, role: string): Array<{label: string; href: string; glyph: string}> {
  const nav = navFor(area, role);
  const picked = nav.filter(i => i.mobile).sort((a, b) => (a.mobile ?? 9) - (b.mobile ?? 9)).slice(0, 4);
  const fill = nav.filter(i => !picked.includes(i)).slice(0, Math.max(0, 4 - picked.length));
  return [...picked, ...fill].map(i => ({label: i.label, href: i.href, glyph: i.glyph ?? '•'}));
}

/** Account-menu links: the customer basics, the role's own panel, then every staff/partner tool the role may open. */
export function roleLinks(role: string): Array<[string, string]> {
  const links: Array<[string, string]> = [['حساب من', '/account'], ['رزروها و سفرها', '/account/bookings'], ['درخواست‌های قطار', '/account/train-requests'], ['شهرشاد، پادویرا و سوغات', '/account/partner-requests'], ['اعلان‌ها', '/account/notifications'], ['امنیت ورود', '/account/security'], ['پشتیبانی', '/account/support']];
  const home = roleHome[role]; if (home && home !== '/account') links.push(['پنل کاری من', home]);
  for (const i of PANEL_ITEMS) if (i.menu && allows(i.rule, role)) links.push([i.label, i.href]);
  if (allows(R.quotes, role)) links.push(['پیشنهادهای قیمت', '/quotes']);
  return links.filter((item, index, all) => all.findIndex(x => x[1] === item[1]) === index);
}
