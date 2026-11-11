import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { writeFileSync } from 'fs';

/* Panels Phase 1 rest (P2-10 + §1.7): one visit per main panel page for each role, signed in with the development seed
   (dev-login). Each page must render its own title (not «دسترسی ندارید»), run without CSP violations (nonce CSP from
   proxy.ts) and without page errors, and pass axe: no critical issue anywhere, and no serious issue on the Phase 1-rest pages.
   All findings are written to E2E_A11Y_REPORT when set (QA evidence). */
const API = process.env.E2E_API_URL || 'http://127.0.0.1:8100';
const REPORT = process.env.E2E_A11Y_REPORT || '';
const SHOTS = process.env.E2E_SCREENSHOT_DIR || '';
type Session = { access_token: string; refresh_token: string; token_type: string; user: { name: string; role: string; tenant: string } };

const ROLES: Record<string, { email: string; role?: string; pages: string[] }> = {
  customer: { email: 'employee@aftab.test', pages: ['/account', '/account/bookings', '/account/refunds', '/account/price-changes', '/panel/today'] },
  // welfare@ (an organization manager) because charter-block.spec turns org-admin@ into an agency partner on a shared e2e DB.
  // refund-loop and agency-credit promote welfare@ to finance_operator, so this test puts the role back first (`role`).
  organization: { email: 'welfare@aftab.test', role: 'welfare_manager', pages: ['/organization', '/organization/requests', '/organization/passengers'] },
  agency: { email: 'agency@aftab.test', pages: ['/agency', '/agency/credit', '/agency/passengers'] },
  supplier: { email: 'supplier@aftab.test', pages: ['/supplier', '/supplier/fulfillment'] },
  ops: { email: 'backoffice@aftab.test', pages: ['/panel/today', '/backoffice/queues/service_requests', '/backoffice/price-changes', '/backoffice/agencies'] },
  finance: { email: 'finance@aftab.test', pages: ['/panel/today', '/finance/refunds', '/finance/approvals', '/finance/failed-payments', '/finance/settlement-import', '/finance/bank-batches', '/finance/tax-rates', '/finance/reconciliation'] },
  admin: { email: 'tenant-admin@aftab.test', pages: ['/panel/today', '/admin', '/admin/sla', '/finance/tax-rates'] },
};
const NEW_PAGES = new Set(['/panel/today', '/account/price-changes', '/organization/passengers', '/agency/passengers', '/backoffice/price-changes', '/finance/approvals',
  '/finance/failed-payments', '/finance/settlement-import', '/finance/bank-batches', '/finance/tax-rates', '/admin/sla']);
const findings: Record<string, unknown> = {};

async function login(request: APIRequestContext, email: string): Promise<Session> {
  const r = await request.post(`${API}/auth/dev-login`, { data: { email } });
  expect(r.ok(), await r.text()).toBeTruthy();
  return r.json();
}
async function ensureRole(request: APIRequestContext, email: string, role: string) {
  const admin = await login(request, 'tenant-admin@aftab.test');
  const headers = { Authorization: `Bearer ${admin.access_token}` };
  const users = await request.get(`${API}/admin/users`, { headers });
  expect(users.ok(), await users.text()).toBeTruthy();
  const target = ((await users.json()) as { id: number; email: string; role: string }[]).find(u => u.email === email)!;
  if (target.role === role) return;
  const r = await request.put(`${API}/admin/users/${target.id}/role`, { headers, data: { role, reason: 'E2E role smoke' } });
  expect(r.ok(), await r.text()).toBeTruthy();
}
async function pageAs(browser: Browser, session: Session, width = 1440): Promise<Page> {
  const ctx = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 }, locale: 'fa-IR' });
  await ctx.addInitScript(value => sessionStorage.setItem('karenseir-auth-session', value), JSON.stringify(session));
  return ctx.newPage();
}
async function go(page: Page, url: string) {
  try { await page.goto(url); } catch (e) { if (!String(e).includes('ERR_ABORTED')) throw e; await page.goto(url); }
}

test.beforeAll(async ({ request }) => {
  test.setTimeout(600_000);
  // next dev compiles a route on first visit; compile every page once so the visits below measure the page, not the compiler.
  for (const p of Array.from(new Set(Object.values(ROLES).flatMap(r => r.pages)))) await request.get(p, { timeout: 120_000 });
});
test.afterAll(() => { if (REPORT) writeFileSync(REPORT, JSON.stringify(findings, null, 2)); });

for (const [role, { email, role: userRole, pages }] of Object.entries(ROLES)) {
  test(`${role}: main panel pages render with nonce CSP and pass axe`, async ({ browser, request }) => {
    test.setTimeout(240_000);
    if (userRole) await ensureRole(request, email, userRole);
    const page = await pageAs(browser, await login(request, email));
    const csp: string[] = []; const errors: string[] = [];
    page.on('console', m => { if (/Content Security Policy|Refused to (execute|load)/i.test(m.text())) csp.push(m.text()); });
    page.on('pageerror', e => errors.push(String(e)));
    for (const path of pages) {
      const response = await page.goto(path).catch(async e => { if (!String(e).includes('ERR_ABORTED')) throw e; return page.goto(path); });
      const header = response?.headers()['content-security-policy'] ?? '';
      expect(header, `${path} CSP`).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
      expect(header).not.toContain("script-src 'self' 'unsafe-inline'");
      await expect(page.locator('main .pn-head h1')).toBeVisible();
      await expect(page.locator('main .pn-head h1')).not.toHaveText('دسترسی ندارید');
      await expect(page.locator('main [data-state="no-access"]')).toHaveCount(0);
      await page.waitForLoadState('networkidle').catch(() => undefined);
      const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      const serious = axe.violations.filter(v => v.impact === 'serious' || v.impact === 'critical');
      findings[`${role} ${path}`] = axe.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }));
      expect(axe.violations.filter(v => v.impact === 'critical').map(v => v.id), `${path} critical a11y`).toEqual([]);
      if (NEW_PAGES.has(path)) expect(serious.map(v => `${v.id}: ${v.nodes.map(n => `${n.target.join(' ')} — ${n.failureSummary ?? ''}`).join(' | ')}`), `${path} serious a11y`).toEqual([]);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/${role}${path.replace(/\//g, '_')}.png`, fullPage: true });
    }
    expect(csp, 'CSP violations').toEqual([]);
    expect(errors, 'page errors').toEqual([]);
  });
}

test('mobile: every role gets the bottom navigation with «بیشتر»', async ({ browser, request }) => {
  test.setTimeout(120_000);
  for (const [role, path] of [['finance', '/finance/refunds'], ['ops', '/backoffice/queues/service_requests'], ['customer', '/account']] as const) {
    const page = await pageAs(browser, await login(request, ROLES[role].email), 390);
    await go(page, path);
    const nav = page.locator('nav.pn-bottom');
    await expect(nav).toBeVisible();
    await expect(nav.getByRole('link')).toHaveCount(5);
    await expect(nav.getByRole('link', { name: 'بیشتر' })).toBeVisible();
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/mobile-${role}.png`, fullPage: false });
    await page.context().close();
  }
});
