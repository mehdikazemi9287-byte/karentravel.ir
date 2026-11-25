import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { execFileSync } from 'child_process';
import { existsSync } from 'fs';
import { orgAllows } from '../../lib/panel-context';

/* Launch V1 item 8.4 — one person, two panels. A plain `customer` account that is also a member of organization A
   (no management permission) and a manager of organization B. Checks, against the real development API:
   /account shows no organization data; the panel switcher opens the organization panel; pages allowed by the
   membership open without «دسترسی ندارید» and without a 403 from the API; pages that stay role-only show «دسترسی ندارید»;
   switching back to the personal account keeps the same session and browser storage; a plain customer sees no switcher.

   Seeding: the API has no endpoint that creates a `customer` inside the seed tenant (registration puts customers in the
   consumer tenant, which cannot hold organizations), so the accounts are inserted into the e2e SQLite file
   (E2E_DATABASE_FILE, set by playwright.config.ts). Organizations and memberships go through the real API (tenant admin).
   Organization B gets its own manager for this run: a member whose `roles.manage` comes from a grant in B (the
   membership + grant model; no API creates an organization's first manager, so that one grant row is a fixture). That
   manager then grants the dual user through the real, permission-checked API. The shared seed account
   org-admin@aftab.test is not used: other specs (charter-block, charter-change) turn it into an `agency_partner`, after
   which it holds no organization authority (that is what failed in CI, where all specs share one database). */
const API = process.env.E2E_API_URL || 'http://127.0.0.1:8100';
const DB = process.env.E2E_DATABASE_FILE || '';
const PY = process.env.E2E_PYTHON || '.venv/bin/python';
const SFX = String(Date.now()).slice(-7);
const DUAL = `dual-${SFX}@aftab.test`, PLAIN = `plain-${SFX}@aftab.test`, MANAGER_B = `org-b-manager-${SFX}@aftab.test`;
const ORG_A = `سازمان آزمون الف ${SFX}`, ORG_B = `سازمان آزمون ب ${SFX}`;
type Session = { access_token: string; refresh_token: string; token_type: string; user: { name: string; role: string; tenant: string } };

// The dual user's grant in B (A: membership only). Which organization pages that opens is read from the panel's own
// registry (lib/panel-context.ts), so the spec follows the access model instead of a frozen list: before Launch V1 8.3
// structure / passengers / financial-context stay role-only (expected «دسترسی ندارید»); with 8.3 (PR #110, authority
// from membership + grants) they open by this grant too. Either way the API must not answer 403 on an allowed page.
const DUAL_GRANT_B = ['requests.read_all', 'roles.manage', 'policy.manage'];
const ORG_PAGES = ['/organization', '/organization/requests', '/organization/policy', '/organization/members', '/organization/credit', '/organization/billing', '/organization/reports', '/organization/audit', '/organization/bookings', '/organization/structure', '/organization/passengers', '/organization/financial-context'];
const DUAL_ORGS = [{ id: 'A', name: 'A', permissions: [] as string[] }, { id: 'B', name: 'B', permissions: DUAL_GRANT_B }];
const ALLOWED = ORG_PAGES.filter(p => orgAllows(p, DUAL_ORGS));
const DENIED = ORG_PAGES.filter(p => !orgAllows(p, DUAL_ORGS));

function py(script: string, args: string[]) {
  execFileSync(PY, ['-I', '-c', script, DB, ...args], { stdio: 'pipe' });
}
function seedCustomers() {
  py([
    'import sqlite3, sys',
    'db = sqlite3.connect(sys.argv[1])',
    "tenant = db.execute(\"select id from tenants where slug='aftab-bank'\").fetchone()[0]",
    'for email, name in [(sys.argv[2], "مسافر دوزمینه‌ای آزمون"), (sys.argv[3], "مشتری سادهٔ آزمون"), (sys.argv[4], "مدیر سازمان ب آزمون")]:',
    "    db.execute('insert or ignore into users (tenant_id, email, name, role) values (?, ?, ?, ?)', (tenant, email, name, 'customer'))",
    'db.commit()',
  ].join('\n'), [DUAL, PLAIN, MANAGER_B]);
}
/** Bootstrap grant: every organization permission for `email` in organization `org` (the member must already exist). */
function seedManagerGrant(org: string, email: string) {
  py([
    'import json, sqlite3, sys, uuid, datetime',
    'db = sqlite3.connect(sys.argv[1])',
    'org, email = sys.argv[2], sys.argv[3]',
    "tenant, uid = db.execute('select tenant_id, id from users where email=?', (email,)).fetchone()",
    "assert db.execute('select 1 from employee_assignments where tenant_id=? and organization_id=? and user_id=?', (tenant, org, uid)).fetchone(), 'not a member'",
    "now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')",
    "perms = json.dumps(sorted(['requests.read_all', 'requests.on_behalf', 'requests.approve', 'policy.manage', 'roles.manage', 'rfq.manage', 'benefits.manage']))",
    "db.execute('insert into enterprise_grants (id, tenant_id, organization_id, user_id, permissions_json, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?)', (str(uuid.uuid4()), tenant, org, uid, perms, now, now))",
    'db.commit()',
  ].join('\n'), [org, email]);
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
  await call(request, admin, 'post', `/enterprise/organizations/${b.id}/members`, { email: MANAGER_B });
  const members = await call(request, admin, 'post', `/enterprise/organizations/${b.id}/members`, { email: DUAL }) as { id: number; email: string }[];
  const dualId = members.find(m => m.email === DUAL)!.id;
  // B's own manager (membership + grant in B) grants the manager set to the dual user in B only, through the real API.
  seedManagerGrant(b.id, MANAGER_B);
  const managerB = await login(request, MANAGER_B);
  expect(managerB.user.role).toBe('customer');
  await call(request, managerB, 'put', `/enterprise/organizations/${b.id}/grants`, { command_id: `e2e-dual-grant-${SFX}`, user_id: dualId, permissions: DUAL_GRANT_B });
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
