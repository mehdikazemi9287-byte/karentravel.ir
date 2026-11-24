import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { execFileSync } from 'child_process';
import { existsSync } from 'fs';

/* Launch V1 item 8.4 — one person, two panels. A plain `customer` account that is also a member of organization A
   (no management permission) and a manager of organization B. Checks, against the real development API:
   /account shows no organization data; the panel switcher opens the organization panel; pages allowed by the
   membership open without «دسترسی ندارید» and without a 403 from the API; pages that stay role-only show «دسترسی ندارید»;
   switching back to the personal account keeps the same session and browser storage; a plain customer sees no switcher.

   Seeding: the API has no endpoint that creates a `customer` inside the seed tenant (registration puts customers in the
   consumer tenant, which cannot hold organizations), so the two accounts are inserted into the e2e SQLite file
   (E2E_DATABASE_FILE, set by playwright.config.ts). Organizations, memberships and grants go through the real API. */
const API = process.env.E2E_API_URL || 'http://127.0.0.1:8100';
const DB = process.env.E2E_DATABASE_FILE || '';
const PY = process.env.E2E_PYTHON || '.venv/bin/python';
const SFX = String(Date.now()).slice(-7);
const DUAL = `dual-${SFX}@aftab.test`, PLAIN = `plain-${SFX}@aftab.test`;
const ORG_A = `سازمان آزمون الف ${SFX}`, ORG_B = `سازمان آزمون ب ${SFX}`;
type Session = { access_token: string; refresh_token: string; token_type: string; user: { name: string; role: string; tenant: string } };

const ALLOWED = ['/organization', '/organization/requests', '/organization/policy', '/organization/members', '/organization/credit', '/organization/billing', '/organization/reports', '/organization/audit', '/organization/bookings'];
// Role-only pages (lib/panel-context.ts): their endpoints are guarded by the global role, so membership does not open them.
const DENIED = ['/organization/structure', '/organization/passengers', '/organization/financial-context'];

function seedCustomers() {
  const script = [
    'import sqlite3, sys',
    'db = sqlite3.connect(sys.argv[1])',
    "tenant = db.execute(\"select id from tenants where slug='aftab-bank'\").fetchone()[0]",
    'for email, name in [(sys.argv[2], "مسافر دوزمینه‌ای آزمون"), (sys.argv[3], "مشتری سادهٔ آزمون")]:',
    "    db.execute('insert or ignore into users (tenant_id, email, name, role) values (?, ?, ?, ?)', (tenant, email, name, 'customer'))",
    'db.commit()',
  ].join('\n');
  execFileSync(PY, ['-I', '-c', script, DB, DUAL, PLAIN], { stdio: 'pipe' });
}
async function login(request: APIRequestContext, email: string): Promise<Session> {
  const r = await request.post(`${API}/auth/dev-login`, { data: { email } });
  expect(r.ok(), await r.text()).toBeTruthy();
  return r.json();
}
async function call(request: APIRequestContext, session: Session, method: 'post' | 'put', path: string, data: unknown) {
  const r = await request[method](`${API}${path}`, { headers: { Authorization: `Bearer ${session.access_token}` }, data });
  expect(r.ok(), `${method} ${path}: ${await r.text()}`).toBeTruthy();
  return r.json();
}
async function pageAs(browser: Browser, session: Session, width = 1440): Promise<Page> {
  const ctx = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 }, locale: 'fa-IR' });
  await ctx.addInitScript(value => { if (!sessionStorage.getItem('karenseir-auth-session')) sessionStorage.setItem('karenseir-auth-session', value); }, JSON.stringify(session));
  return ctx.newPage();
}
async function go(page: Page, url: string) {
  try { await page.goto(url); } catch (e) { if (!String(e).includes('ERR_ABORTED')) throw e; await page.goto(url); }
}
/** Panel heading once the guard has decided (the shell says «در حال دریافت…» while /enterprise/context is in flight). */
async function settledTitle(page: Page) {
  const h1 = page.locator('main .pn-head h1');
  await expect(h1).toBeVisible();
  await page.waitForLoadState('networkidle').catch(() => undefined);
  await expect(page.locator('main [role="status"]', { hasText: 'در حال دریافت' })).toHaveCount(0, { timeout: 20_000 });
  return (await h1.textContent())?.trim() ?? '';
}

test.describe.configure({ mode: 'serial' });
let dual: Session, plain: Session;

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000);
  test.skip(!DB || !existsSync(DB), 'E2E_DATABASE_FILE is not a local SQLite file (run through playwright.config.ts)');
  seedCustomers();
  const admin = await login(request, 'tenant-admin@aftab.test');
  const a = await call(request, admin, 'post', '/enterprise/organizations', { name: ORG_A });
  const b = await call(request, admin, 'post', '/enterprise/organizations', { name: ORG_B });
  await call(request, admin, 'post', `/enterprise/organizations/${a.id}/members`, { email: DUAL });
  await call(request, admin, 'post', `/enterprise/organizations/${b.id}/members`, { email: 'org-admin@aftab.test' });
  const members = await call(request, admin, 'post', `/enterprise/organizations/${b.id}/members`, { email: DUAL }) as { id: number; email: string }[];
  const dualId = members.find(m => m.email === DUAL)!.id;
  // organization_admin holds every enterprise permission in an organization it belongs to; it grants the manager set to the dual user in B only.
  const orgAdmin = await login(request, 'org-admin@aftab.test');
  await call(request, orgAdmin, 'put', `/enterprise/organizations/${b.id}/grants`, { command_id: `e2e-dual-grant-${SFX}`, user_id: dualId, permissions: ['requests.read_all', 'roles.manage', 'policy.manage'] });
  dual = await login(request, DUAL); plain = await login(request, PLAIN);
  expect(dual.user.role).toBe('customer'); expect(plain.user.role).toBe('customer');
  // next dev compiles a route on first visit; compile the pages once so the checks below measure the page, not the compiler.
  for (const p of ['/account', ...ALLOWED, ...DENIED, '/employee']) await request.get(p, { timeout: 120_000 });
});

test('dual-context: /account shows only personal data and offers the switcher', async ({ browser }) => {
  const page = await pageAs(browser, dual);
  await go(page, '/account');
  expect(await settledTitle(page)).not.toBe('دسترسی ندارید');
  const switcher = page.locator('[data-panel-switcher]');
  await expect(switcher).toBeVisible();
  await expect(switcher.getByRole('link', { name: 'حساب شخصی' })).toHaveAttribute('aria-current', 'true');
  await expect(switcher.getByRole('link', { name: /پنل سازمان/ })).toBeVisible();
  const body = page.locator('body');
  for (const text of [ORG_A, ORG_B, 'اعتبار سازمانی']) await expect(body).not.toContainText(text);
  await expect(page.locator('#pn-nav').getByRole('link', { name: 'مزایای سازمانی' })).toHaveCount(0);
});

test('dual-context: switcher opens the organization panel; allowed pages load, role-only pages say «دسترسی ندارید»', async ({ browser }) => {
  test.setTimeout(240_000);
  const page = await pageAs(browser, dual);
  const forbidden: string[] = []; const errors: string[] = [];
  page.on('response', r => { if (r.url().startsWith(API) && r.status() === 403) forbidden.push(`${new URL(page.url()).pathname} -> ${r.request().method()} ${new URL(r.url()).pathname}`); });
  page.on('pageerror', e => errors.push(String(e)));
  await go(page, '/account');
  await settledTitle(page);
  await page.locator('[data-panel-switcher]').getByRole('link', { name: /پنل سازمان/ }).click();
  await page.waitForURL('**/organization');
  expect(await settledTitle(page)).toBe('نمای کلی');
  // The dashboard opens the organization where this person manages (B), not the first membership (A).
  await expect(page.locator('.so-hero h2')).toHaveText(ORG_B);
  await expect(page.locator('[data-panel-switcher]').getByRole('link', { name: /پنل سازمان/ })).toHaveAttribute('aria-current', 'true');
  for (const path of ALLOWED) {
    await go(page, path);
    const title = await settledTitle(page);
    expect(title, path).not.toBe('دسترسی ندارید');
    await expect(page.locator('main [data-state="no-access"]'), path).toHaveCount(0);
  }
  expect(forbidden, 'no 403 from the API on pages the membership allows').toEqual([]);
  for (const path of DENIED) {
    await go(page, path);
    expect(await settledTitle(page), path).toBe('دسترسی ندارید');
    await expect(page.getByText('دسترسی ندارید').first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test('dual-context: switching back to the personal account keeps the session and browser storage', async ({ browser }) => {
  const page = await pageAs(browser, dual);
  await go(page, '/organization');
  await settledTitle(page);
  await page.evaluate(() => localStorage.setItem('e2e-dual-marker', 'kept'));
  const before = await page.evaluate(() => ({ auth: sessionStorage.getItem('karenseir-auth-session'), local: JSON.stringify(Object.entries(localStorage).sort()) }));
  await page.locator('[data-panel-switcher]').getByRole('link', { name: 'حساب شخصی' }).click();
  await page.waitForURL('**/account');
  expect(await settledTitle(page)).not.toBe('دسترسی ندارید');
  await expect(page.getByText('برای دیدن این بخش وارد حساب خود شوید.')).toHaveCount(0);
  await expect(page.locator('[data-panel-switcher]').getByRole('link', { name: 'حساب شخصی' })).toHaveAttribute('aria-current', 'true');
  const after = await page.evaluate(() => ({ auth: sessionStorage.getItem('karenseir-auth-session'), local: JSON.stringify(Object.entries(localStorage).sort()) }));
  expect(after.auth).toBe(before.auth);
  expect(after.local).toBe(before.local);
  // ...and back again: the organization panel still opens with the same session.
  await page.locator('[data-panel-switcher]').getByRole('link', { name: /پنل سازمان/ }).click();
  await page.waitForURL('**/organization');
  expect(await settledTitle(page)).toBe('نمای کلی');
});

test('plain customer: no switcher, and the organization panel is closed', async ({ browser }) => {
  for (const width of [1440, 390]) {
    const page = await pageAs(browser, plain, width);
    await go(page, '/account');
    expect(await settledTitle(page)).not.toBe('دسترسی ندارید');
    await expect(page.locator('[data-panel-switcher]')).toHaveCount(0);
    await go(page, '/organization');
    expect(await settledTitle(page)).toBe('دسترسی ندارید');
    await page.context().close();
  }
});
