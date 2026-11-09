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

export type Area = 'customer' | 'organization' | 'agency' | 'supplier' | 'admin';
export type Rule = {roles?: string[]; anyPermission?: string[]; notRoles?: string[]};
export type NavItem = {label: string; href: string; area: Area; rule?: Rule; menu?: boolean; inNav?: boolean; moved?: Record<string, string>};

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
} satisfies Record<string, Rule | undefined>;

const I = (area: Area, label: string, href: string, rule?: Rule, extra: Partial<NavItem> = {}): NavItem => ({area, label, href, rule, inNav: true, ...extra});
export const PANEL_ITEMS: NavItem[] = [
  I('customer', 'نمای کلی', '/account'), I('customer', 'درخواست‌های قطار', '/account/train-requests'), I('customer', 'شهرشاد، پادویرا و سوغات', '/account/partner-requests'),
  I('customer', 'پروفایل و مسافران', '/account/profile'), I('customer', 'رزروها و سفرها', '/account/bookings'), I('customer', 'تغییرات سفر', '/account/changes'),
  I('customer', 'ویزا', '/account/visa'), I('customer', 'مدارک مسافران', '/account/documents'), I('customer', 'پرداخت و فاکتور', '/account/payments'),
  I('customer', 'لغو و استرداد', '/account/refunds'), I('customer', 'کیف پول و اعتبار', '/account/wallet'), I('customer', 'مزایای سازمانی', '/account/benefits'),
  I('customer', 'ذخیره‌شده‌ها و پیشنهادها', '/account/saved'), I('customer', 'اعلان‌ها', '/account/notifications'), I('customer', 'امنیت ورود', '/account/security'), I('customer', 'پشتیبانی', '/account/support'),

  I('organization', 'نمای کلی', '/organization', R.orgManager), I('organization', 'میز کار کارمند', '/employee', R.orgMember),
  I('organization', 'کارکنان و دسترسی‌ها', '/organization/members', R.orgManager, {menu: true}), I('organization', 'درخواست و تأیید سفر', '/organization/requests', R.orgMember),
  I('organization', 'سیاست سفر', '/organization/policy', R.orgManager), I('organization', 'واحدها و مراکز هزینه', '/organization/structure', R.orgManager),
  I('organization', 'اعتبار و اقساط', '/organization/credit', R.orgRecords), I('organization', 'رزروهای سازمان', '/organization/bookings', R.orgManager),
  I('organization', 'صورتحساب و تسویه', '/organization/billing', R.orgRecords), I('organization', 'گزارش', '/organization/reports', R.orgManager),
  I('organization', 'سوابق و گردش تأیید', '/organization/audit', R.orgRecords), I('organization', 'تعهد مالی سفر', '/organization/financial-context', R.orgRecords),

  I('agency', 'نمای کلی', '/agency', R.agency), I('agency', 'تورهای من', '/agency/tours', R.agency, {menu: true}), I('agency', 'فروش و پیشنهاد قیمت', '/agency/sales', R.agency),
  I('agency', 'رزروها', '/agency/bookings', R.agency), I('agency', 'مشتریان', '/agency/customers', R.agency), I('agency', 'کمیسیون', '/agency/commissions', R.agency),
  I('agency', 'اعتبار و حساب', '/agency/credit', R.agency), I('agency', 'تسویه و اسناد', '/agency/documents', R.agency), I('agency', 'گزارش', '/agency/reports', R.agency),
  I('agency', 'میز کار کامل', '/agency/workspace', R.agency), I('agency', 'پشتیبانی', '/agency/support', R.agency),

  I('supplier', 'نمای کلی', '/supplier', R.supplier, {menu: true}), I('supplier', 'خدمات، نرخ و ظرفیت', '/supplier/services', R.supplier),
  I('supplier', 'تورهای من', '/supplier/tours', R.supplier, {menu: true, moved: {agency_partner: '/agency/tours'}}), I('supplier', 'هتل‌های من', '/supplier/hotels', R.supplier, {menu: true}),
  I('supplier', 'اقامتگاه و تقویم', '/supplier/accommodation', R.supplier), I('supplier', 'سفارش‌ها و تأیید', '/supplier/fulfillment', R.supplier),
  I('supplier', 'کنترل بلیت', '/supplier/admission', R.fulfil), I('supplier', 'درخواست‌های سازمانی', '/supplier/rfqs', R.supplier),
  I('supplier', 'تسویه و قرارداد', '/supplier/settlements', R.supplier, {menu: true}), I('supplier', 'گزارش', '/supplier/reports', R.supplier),
  I('supplier', 'پشتیبانی', '/supplier/support', R.supplier), I('supplier', 'روابط مالی قرارداد', '/supplier/financial-context', R.supplierLinks),

  ...([
    ['پیشخوان عملیات', '/admin/ops', R.opsStaff], ['محتوای سایت', '/admin/content', R.editor], ['میز بلیت قطار', '/admin/train-desk', R.desk],
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
  ] as [string, string, Rule][]).map(([label, href, rule]) => I('admin', label, href, rule, {menu: true})),
  // Staff pages outside the panel shell (JourneyShell): not in the sidebar, but in the account menu for the roles that can use them.
  ...([
    ['مرکز عملیات سفر', '/backoffice/trip-events', R.tripOps], ['تغییرات سفر', '/backoffice/trips', R.tripChanges], ['درخواست‌های تغییر و استرداد', '/backoffice/booking-requests', R.support],
    ['پرونده‌های عملیات', '/backoffice/records', R.backoffice], ['میز پشتیبانی', '/backoffice/support', R.support], ['وضعیت اعلان‌ها', '/backoffice/notifications', R.tripOps],
    ['رکوردهای مالی', '/finance/records', R.ledger], ['حسابداری و کمیسیون', '/finance/accounting', R.ledger],
    ['رسیدگی به درخواست مشتری', '/backoffice/requests', R.serviceDecide], ['صف‌های عملیات', '/backoffice/queues', R.serviceDecide],
  ] as [string, string, Rule][]).map(([label, href, rule]) => I('admin', label, href, rule, {menu: true, inNav: false})),
];

/** Access for a page path that has no item of its own (detail pages, editors). */
const AREA_FALLBACK: Record<Area, Rule | undefined> = {customer: undefined, organization: R.orgMember, agency: R.agency, supplier: {anyPermission: ['inventory:manage', 'reservation:fulfill']},
  admin: {roles: ['backoffice_expert', 'finance_operator', 'tenant_admin', 'platform_admin']}};

/** The item that governs a path: the exact item, else the longest item prefix in the same area, else the area rule. */
export function itemFor(area: Area, path: string): NavItem | null {
  const clean = (path || '/').replace(/\/+$/, '') || '/';
  const exact = PANEL_ITEMS.find(i => i.href === clean);
  if (exact) return exact;
  const roots = new Set(['/account', '/organization', '/agency', '/supplier', '/admin', '/backoffice', '/finance', '/employee']);
  const prefix = PANEL_ITEMS.filter(i => i.area === area && !roots.has(i.href) && clean.startsWith(i.href + '/')).sort((a, b) => b.href.length - a.href.length)[0];
  return prefix ?? null;
}
export function canOpen(area: Area, path: string, role: string): boolean {
  const item = itemFor(area, path);
  return allows(item ? item.rule : AREA_FALLBACK[area], role);
}
export function navFor(area: Area, role: string): NavItem[] {
  return PANEL_ITEMS.filter(i => i.area === area && i.inNav && allows(i.rule, role));
}
export function homeFor(role: string): string {return roleHome[role] ?? '/account';}

/** Account-menu links: the customer basics, the role's own panel, then every staff/partner tool the role may open. */
export function roleLinks(role: string): Array<[string, string]> {
  const links: Array<[string, string]> = [['حساب من', '/account'], ['رزروها و سفرها', '/account/bookings'], ['درخواست‌های قطار', '/account/train-requests'], ['شهرشاد، پادویرا و سوغات', '/account/partner-requests'], ['اعلان‌ها', '/account/notifications'], ['امنیت ورود', '/account/security'], ['پشتیبانی', '/account/support']];
  const home = roleHome[role]; if (home && home !== '/account') links.push(['پنل کاری من', home]);
  for (const i of PANEL_ITEMS) if (i.menu && allows(i.rule, role)) links.push([i.label, i.href]);
  if (allows(R.quotes, role)) links.push(['پیشنهادهای قیمت', '/quotes']);
  return links.filter((item, index, all) => all.findIndex(x => x[1] === item[1]) === index);
}
