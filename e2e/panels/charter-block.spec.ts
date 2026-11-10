import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

/* Panels Phase 2 — charter (CH-01/02/03/04, staff review): a charterer with a verified BAND_ALEF licence registers an
   international seat block in the form, operations publishes it into the normal inventory, the charterer allocates seats to
   a partner agency, and the partner sees the allocation. The domestic option is visible but disabled while the
   charter_domestic_sale flag is off. Setup of the two agencies goes through the real APIs (profile, licence, registry checks,
   KYC); the screens under test are driven through the UI. Development seed accounts only. */
const API = process.env.E2E_API_URL || 'http://127.0.0.1:8100';
const SHOTS = process.env.E2E_SCREENSHOT_DIR || '';
type Session = { access_token: string; refresh_token: string; token_type: string; user: { name: string; role: string; tenant: string } };

async function login(request: APIRequestContext, email: string): Promise<Session> {
  const r = await request.post(`${API}/auth/dev-login`, { data: { email } });
  expect(r.ok(), await r.text()).toBeTruthy();
  return r.json();
}
const auth = (s: Session) => ({ Authorization: `Bearer ${s.access_token}` });
async function ok<T>(p: Promise<import('@playwright/test').APIResponse>): Promise<T> {
  const r = await p; expect(r.ok(), `${r.url()} ${r.status()} ${await r.text()}`).toBeTruthy(); return r.json() as Promise<T>;
}
async function pageAs(browser: Browser, session: Session, width = 1440): Promise<Page> {
  const ctx = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 }, locale: 'fa-IR', deviceScaleFactor: 1 });
  await ctx.addInitScript(value => sessionStorage.setItem('karenseir-auth-session', value), JSON.stringify(session));
  return ctx.newPage();
}
async function shot(page: Page, name: string) { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); }

async function activeAgency(request: APIRequestContext, ta: Session, ops: Session, email: string, name: string, licence: string) {
  const agency = await ok<{ id: string }>(request.post(`${API}/admin/partners/agencies`, { headers: auth(ta), data: { display_name: name, commission_bps: 100 } }));
  const users = await ok<{ id: number; email: string; role: string }[]>(request.get(`${API}/admin/users`, { headers: auth(ta) }));
  const u = users.find(x => x.email === email)!;
  if (u.role !== 'agency_partner') await ok(request.put(`${API}/admin/users/${u.id}/role`, { headers: auth(ta), data: { role: 'agency_partner', reason: 'E2E partner agency' } }));
  await ok(request.post(`${API}/agency/${agency.id}/members`, { headers: auth(ta), data: { user_id: u.id } }));
  const owner = await login(request, email);
  await ok(request.put(`${API}/agency/${agency.id}/profile`, { headers: auth(owner), data: { legal_name: `${name} (حقوقی)`, national_id: '14000000000', economic_code: '411400000000', postal_code: '1969000000', ceo_name: 'مدیر نمونه', iban: 'IR000000000000000000000000' } }));
  const lic = await ok<{ id: string; registries: { registry: string }[] }>(request.post(`${API}/agency/${agency.id}/licences`, { headers: auth(owner), data: { licence_type: licence, number: `${licence}-${Date.now() % 100000}`, expires_on: new Date(Date.now() + 400 * 86_400_000).toISOString().slice(0, 10), attest: true } }));
  await ok(request.post(`${API}/agency/${agency.id}/profile/submit`, { headers: auth(owner) }));
  for (const r of lic.registries) await ok(request.post(`${API}/staff/agencies/${agency.id}/licences/${lic.id}/checks`, { headers: auth(ops), data: { registry: r.registry, result: 'confirmed', reference: `INQ-${r.registry}` } }));
  await ok(request.post(`${API}/staff/agencies/${agency.id}/kyc`, { headers: auth(ops), data: { decision: 'approve' } }));
  return { id: agency.id, owner };
}

test('charter block: form → ops publish → allocation to a partner agency', async ({ browser, request }) => {
  test.setTimeout(180_000);
  const suffix = `${Date.now()}`;
  const ta = await login(request, 'tenant-admin@aftab.test'); const opsS = await login(request, 'backoffice@aftab.test');
  const charterer = await activeAgency(request, ta, opsS, 'agency@aftab.test', `چارترکنندهٔ آزمون ${suffix}`, 'BAND_ALEF');
  const partnerName = `آژانس همکار آزمون ${suffix}`;
  const partner = await activeAgency(request, ta, opsS, 'org-admin@aftab.test', partnerName, 'BAND_BE');

  // --- CH-02: the charterer fills the seat-block form; the domestic option is shown but disabled (flag off)
  const ch = await pageAs(browser, charterer.owner);
  await ch.addInitScript(id => sessionStorage.setItem('karenseir-panel-agency', id), charterer.id);
  await ch.goto('/agency/inventory/flights/new');
  await expect(ch.getByRole('radio', { name: /داخلی \(DOMESTIC\)/ })).toBeDisabled();
  await expect(ch.getByText('غیرفعال: فروش چارتر داخلی تا تأیید قانونی فعال نشده است')).toBeVisible();
  await ch.getByLabel('ایرلاین چارتردهنده (کد)').fill('QB');
  await ch.getByLabel('نام ایرلاین').fill('قشم ایر');
  await ch.getByLabel('شمارهٔ پرواز').fill(suffix.slice(-4));
  await ch.getByLabel('ظرفیت قراردادی (صندلی)').fill('10');
  await ch.getByLabel('نرخ خالص بزرگسال (ADT)').fill('39,800,000');
  await ch.getByLabel('کودک (CHD)').fill('29,850,000');
  await ch.getByLabel('نوزاد (INF)').fill('3,980,000');
  await expect(ch.getByText('سقف ثبت نشده')).toBeVisible();
  await shot(ch, 'CH-02-seat-block-form_1440');
  await ch.getByRole('button', { name: 'ارسال برای بازبینی' }).click();
  await expect(ch).toHaveURL(/\/agency\/inventory\/flights\/[0-9a-f-]{36}$/);
  const blockId = ch.url().split('/').pop()!;
  await expect(ch.locator('[data-status="submitted"]')).toBeVisible();

  // --- staff review: operations publishes with the contract fee
  const ops = await pageAs(browser, opsS);
  await ops.goto('/backoffice/charter-blocks');
  await ops.getByRole('row', { name: new RegExp(`QB${suffix.slice(-4)}`) }).getByRole('button', { name: 'بررسی' }).click();
  await ops.getByLabel(/کارمزد پلتفرم طبق قرارداد/).fill('300');
  await shot(ops, 'OPS-charter-review_1440');
  await ops.getByRole('button', { name: 'تأیید و انتشار' }).click();
  await expect(ops.getByText('منتشر شد.')).toBeVisible();

  // --- CH-03/04: the charterer allocates 3 seats to the partner agency
  await ch.reload();
  await expect(ch.locator('[data-status="published"]')).toBeVisible();
  await ch.getByLabel('آژانس گیرنده').selectOption({ label: partnerName });
  await ch.getByLabel('تعداد صندلی').fill('3');
  await ch.getByRole('button', { name: 'ثبت سهمیه' }).click();
  await expect(ch.getByRole('row', { name: new RegExp(partnerName) })).toContainText('۳ از ۳');
  await expect(ch.locator('.pn-stat', { hasText: 'آزاد برای فروش عمومی' })).toContainText('۷');
  await expect(ch.locator('[data-view="agency_seller"]')).toContainText('کارمزد پلتفرم');
  await shot(ch, 'CH-03-04-block-detail-allocation_1440');

  // --- CH-01 list (desktop + mobile) and the partner's view of its allocation
  await ch.goto('/agency/inventory/flights');
  await expect(ch.getByRole('link', { name: /IKA/ }).first()).toBeVisible();
  await shot(ch, 'CH-01-flights-list_1440');
  const mob = await pageAs(browser, charterer.owner, 390);
  await mob.addInitScript(id => sessionStorage.setItem('karenseir-panel-agency', id), charterer.id);
  await mob.goto('/agency/inventory/flights');
  await expect(mob.getByText(/QB/).first()).toBeVisible();
  expect(await mob.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await shot(mob, 'CH-01-flights-list_390');
  const got = await ok<{ items: { seats: number; status: string }[] }>(request.get(`${API}/agency/${partner.id}/charter/allocations-received`, { headers: auth(partner.owner) }));
  expect(got.items.find(x => x.status === 'held')?.seats).toBe(3);
  // the partner cannot open the charterer's block
  expect((await request.get(`${API}/agency/${charterer.id}/charter/blocks/${blockId}`, { headers: auth(partner.owner) })).status()).toBe(404);
});
