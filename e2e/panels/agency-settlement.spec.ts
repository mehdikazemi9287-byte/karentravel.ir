import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

/* Panels Phase 2b — AG-17 / FIN-05 / AG-18a / FIN-08 (Figma P3 243:2): a sale on agency credit → finance drafts the period
   statement and asks to issue it (maker) → a second finance user approves → the agency owner opens a dispute on the row →
   finance accepts it with an adjustment (maker) → the second finance user approves → the agency accepts the corrected statement
   → finance records the bank payment (maker, ConfirmMoney) → the second finance user approves → settled.
   Setup (agency, licence, credit limit, flight offer, booking) goes through the real APIs; development seed accounts only.
   welfare@ is promoted to finance_operator as the second finance person (same as refund-loop / agency-credit; role-smoke resets it). */
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
/** next dev compiles a route on first visit; retry a navigation that times out while it compiles. */
async function go(page: Page, path: string) {
  for (let i = 0; i < 3; i++) { try { await page.goto(path, { timeout: 60_000 }); return; } catch (e) { if (i === 2) throw e; } }
}
async function shot(page: Page, name: string) { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); }
const letters = () => Array.from({ length: 2 }, () => String.fromCharCode(65 + Math.floor(Math.random() * 26))).join('');

test('agency settlement: issue (two finance users) → dispute → adjustment → accept → settle', async ({ browser, request }) => {
  test.setTimeout(240_000);
  const suffix = `${Date.now()}`;
  const pa = await login(request, 'platform-admin@aftab.test');
  const ta = await login(request, 'tenant-admin@aftab.test');
  const opsS = await login(request, 'backoffice@aftab.test');
  // --- flight offer through the inventory API (unique route per run)
  const origin = `S${letters()}`; const dest = `T${letters()}`;
  const sup = await ok<{ id: string }>(request.post(`${API}/inventory/suppliers`, { headers: auth(pa), data: { name: `E2E airline ${suffix}`, supplier_type: 'airline' } }));
  const route = await ok<{ id: string }>(request.post(`${API}/inventory/routes`, { headers: auth(pa), data: { origin, destination: dest, scope: 'international' } }));
  const start = new Date(Date.now() + 12 * 86_400_000); const iso = start.toISOString().slice(0, 10); const wd = String((start.getUTCDay() + 6) % 7);
  const series = await ok<{ id: string }>(request.post(`${API}/inventory/flight-series`, { headers: auth(pa), data: { route_id: route.id, supplier_id: sup.id, airline_code: 'EP', flight_number: suffix.slice(-4),
    date_from: iso, date_to: iso, schedule: { [wd]: { time: '09:00', duration: 120 } }, capacity: 20, adult_fare: 20_000_000, child_fare: 20_000_000, infant_fare: 2_000_000 } }));
  await ok(request.post(`${API}/inventory/flight-series/${series.id}/generate`, { headers: auth(pa) }));
  // --- an active agency (agency@ owner) with a credit limit approved by two finance users
  const agencyName = `آژانس تسویهٔ آزمون ${suffix}`;
  const agency = await ok<{ id: string }>(request.post(`${API}/admin/partners/agencies`, { headers: auth(ta), data: { display_name: agencyName, commission_bps: 120 } }));
  const users = await ok<{ id: number; email: string; role: string }[]>(request.get(`${API}/admin/users`, { headers: auth(ta) }));
  const agencyUser = users.find(u => u.email === 'agency@aftab.test')!;
  if (agencyUser.role !== 'agency_partner') await ok(request.put(`${API}/admin/users/${agencyUser.id}/role`, { headers: auth(ta), data: { role: 'agency_partner', reason: 'E2E settlement' } }));
  await ok(request.post(`${API}/agency/${agency.id}/members`, { headers: auth(ta), data: { user_id: agencyUser.id } }));
  const second = users.find(u => u.email === 'welfare@aftab.test')!;
  if (second.role !== 'finance_operator') await ok(request.put(`${API}/admin/users/${second.id}/role`, { headers: auth(ta), data: { role: 'finance_operator', reason: 'E2E two-person settlement' } }));
  const owner = await login(request, 'agency@aftab.test');
  await ok(request.put(`${API}/agency/${agency.id}/profile`, { headers: auth(owner), data: { legal_name: `${agencyName} (حقوقی)`, national_id: '14000000000', economic_code: '411400000000', postal_code: '1969000000', ceo_name: 'مدیر نمونه', iban: 'IR000000000000000000000000' } }));
  const lic = await ok<{ id: string; registries: { registry: string }[] }>(request.post(`${API}/agency/${agency.id}/licences`, { headers: auth(owner), data: { licence_type: 'BAND_ALEF', number: `A-${suffix.slice(-6)}`, expires_on: new Date(Date.now() + 400 * 86_400_000).toISOString().slice(0, 10), attest: true } }));
  await ok(request.post(`${API}/agency/${agency.id}/profile/submit`, { headers: auth(owner) }));
  for (const r of lic.registries) await ok(request.post(`${API}/staff/agencies/${agency.id}/licences/${lic.id}/checks`, { headers: auth(opsS), data: { registry: r.registry, result: 'confirmed', reference: `INQ-${r.registry}` } }));
  await ok(request.post(`${API}/staff/agencies/${agency.id}/kyc`, { headers: auth(opsS), data: { decision: 'approve' } }));
  const fin1S = await login(request, 'finance@aftab.test'); const fin2S = await login(request, 'welfare@aftab.test');
  const lim = await ok<{ request_id: string }>(request.post(`${API}/finance/agency-accounts/${agency.id}/credit-limit`, { headers: { ...auth(fin1S), 'Idempotency-Key': `e2e-lim-${suffix}` }, data: { new_limit_irr: 100_000_000, reason: 'قرارداد اعتبار آزمون' } }));
  await ok(request.post(`${API}/maker-checker/requests/${lim.request_id}/approve`, { headers: auth(fin2S), data: {} }));
  // --- a booking on agency credit (net 20,000,000; commission 1.2% = 240,000; VAT on commission 24,000)
  const offers = await ok<{ items: { id: string }[] }>(request.get(`${API}/agency/${agency.id}/offers?q=${origin}`, { headers: auth(owner) }));
  const offer = offers.items[0]; expect(offer, 'flight offer for the new route').toBeTruthy();
  const pc = await ok<{ id: string }>(request.post(`${API}/offers/${offer.id}/price-check`, { headers: auth(owner), data: { units: 1, command_id: `pc-${suffix}` } }));
  await ok(request.post(`${API}/agency/${agency.id}/credit-bookings`, { headers: auth(owner), data: { price_check_id: pc.id, command_id: `cb-${suffix}` } }));

  // --- FIN-05: finance (maker) runs the period and asks to issue the statement
  const fin1 = await pageAs(browser, fin1S);
  await go(fin1, '/finance/settlements/agencies');
  await fin1.getByRole('button', { name: 'اجرای دورهٔ تسویه' }).click();
  await fin1.getByLabel('آژانس').selectOption({ label: agencyName });
  await fin1.getByRole('button', { name: 'ساخت پیش‌نویس' }).click();
  await expect(fin1.getByRole('heading', { name: /صورت تسویه ST-/ })).toBeVisible({ timeout: 60_000 });
  await expect(fin1.locator('.b2b-sum')).toContainText('۲۰٬۰۰۰٬۰۰۰ ریال');
  await expect(fin1.locator('.b2b-sum')).toContainText('۲۴٬۰۰۰ ریال');   // VAT 10% of the commission only
  const statementUrl = new URL(fin1.url()).pathname;
  await fin1.getByRole('button', { name: 'درخواست صدور (maker)' }).click();
  await expect(fin1.getByText('ثبت شما؛ نفر دوم تأیید می‌کند').first()).toBeVisible();
  await shot(fin1, 'FIN-05-settlement-detail-draft_1440');

  // --- the second finance user approves the issue
  const fin2 = await pageAs(browser, fin2S);
  await go(fin2, statementUrl);
  await fin2.getByRole('button', { name: 'تأیید (نفر دوم)' }).click();
  await expect(fin2.locator('[data-status="under_review"]').first()).toBeVisible();

  // --- AG-17 / AG-18a: the agency owner sees the issued statement and disputes the sale row
  const ag = await pageAs(browser, owner);
  await ag.addInitScript(id => sessionStorage.setItem('karenseir-panel-agency', id), agency.id);
  await go(ag, '/agency/settlements');
  await expect(ag.getByText('منتظر تأیید شما').first()).toBeVisible();
  await shot(ag, 'AG-17-settlements-list_1440');
  await ag.getByRole('link', { name: 'بررسی و تأیید' }).first().click();
  await expect(ag.locator('.b2b-steps')).toBeVisible({ timeout: 60_000 });  // first visit compiles the route on the dev server
  await shot(ag, 'AG-17-settlement-detail_1440');
  await ag.getByRole('button', { name: 'اعتراض' }).first().click();
  await ag.getByLabel('مبلغ ادعایی به نفع آژانس (ریال)').fill('40000');
  await ag.getByLabel('شرح (دست‌کم ۲۰ نویسه)').fill('نرخ کمیسیون قرارداد ما ۱.۴ درصد است نه ۱.۲ درصد.');
  await shot(ag, 'AG-18a-dispute-open_1440');
  await ag.getByRole('button', { name: 'ثبت اعتراض' }).click();
  await expect(ag.getByText('اعتراض باز').first()).toBeVisible();
  await expect(ag.getByRole('button', { name: 'تأیید صورت تسویه' })).toBeDisabled();

  // --- FIN-08: finance accepts with an adjustment (maker); the second finance user approves the adjustment
  await go(fin1, '/finance/settlements/disputes');
  await fin1.getByRole('button', { name: 'رسیدگی' }).first().click();
  await fin1.getByLabel('یادداشت برای آژانس').fill('قرارداد بررسی شد؛ اختلاف پذیرفته می‌شود.');
  await shot(fin1, 'FIN-08-dispute-resolve_1440');
  await fin1.getByRole('button', { name: 'ثبت تصمیم و صدور اصلاحیه' }).click();
  await expect(fin1.getByText('منتظر نفر دوم').or(fin1.getByText('ثبت شما؛ نفر دوم تأیید می‌کند')).first()).toBeVisible();
  await go(fin2, '/finance/settlements/disputes');
  await fin2.getByRole('button', { name: 'تأیید (نفر دوم)' }).first().click();
  await expect(fin2.getByText('تأیید و اعمال شد.')).toBeVisible();

  // --- the agency accepts the corrected statement (new adjustment row; old rows unchanged)
  await go(ag, statementUrl.replace('/finance/', '/agency/'));
  await ag.getByText(/ردیف‌های حساب/).click();
  await expect(ag.getByText('اصلاحیه').first()).toBeVisible();
  await ag.getByRole('button', { name: 'تأیید صورت تسویه' }).click();
  await expect(ag.getByText('صورت تسویه تأیید شد.')).toBeVisible();

  // --- finance records the agency's bank payment (maker, ConfirmMoney) → the second finance user approves → settled
  await go(fin1, statementUrl);
  await fin1.getByLabel('کد پیگیری بانکی واریز آژانس').fill(`PAYA-${suffix.slice(-6)}`);
  await fin1.getByRole('button', { name: 'ثبت تسویه (maker)' }).click();
  await fin1.getByLabel(/مبلغ، مقصد و نام صاحب حساب را بررسی کردم/).check();
  await fin1.getByRole('button', { name: 'ثبت درخواست تسویه' }).click();
  await expect(fin1.getByText('درخواست تسویه ثبت شد؛ نفر دوم تأیید می‌کند.')).toBeVisible();
  await go(fin2, statementUrl);
  await fin2.getByRole('button', { name: 'تأیید (نفر دوم)' }).click();
  await expect(fin2.getByText('تأیید و اعمال شد.')).toBeVisible();
  await go(fin2, statementUrl);
  await expect(fin2.locator('.as-card-head [data-status="approved"]')).toBeVisible();
  await shot(fin2, 'FIN-05-settlement-detail-settled_1440');
  await go(fin1, '/finance/settlements/agencies');
  await shot(fin1, 'FIN-05-settlements-list_1440');

  // --- mobile 390: agency list without horizontal scroll
  const mob = await pageAs(browser, owner, 390);
  await mob.addInitScript(id => sessionStorage.setItem('karenseir-panel-agency', id), agency.id);
  await go(mob, '/agency/settlements');
  await expect(mob.getByText('تسویه‌شده').first()).toBeVisible();
  expect(await mob.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await shot(mob, 'AG-17-settlements-list_390');
});
