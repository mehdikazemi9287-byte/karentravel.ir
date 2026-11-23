import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

/* Panels Phase 2b — OPS-CH-05 / AG-CH-06 / FIN-02c / AG-15b (Figma P3 243:2): a published charter block with seats allocated to a
   partner agency that booked on its credit → operations records a +3 h schedule change with the impact preview and sends it
   for a second approver → the tenant admin approves (the change is applied) → the partner agency sees the notice and asks for a
   refund → finance confirms the refund to agency credit (ConfirmMoney) → the agency ledger shows the credit-back.
   Setup goes through the real APIs; development seed accounts only. No SMS is sent (outbox only). */
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
async function go(page: Page, path: string) {
  for (let i = 0; i < 3; i++) { try { await page.goto(path, { timeout: 60_000 }); return; } catch (e) { if (i === 2) throw e; } }
}
async function shot(page: Page, name: string) { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); }
/** Tehran wall-clock (UTC+3:30) value for a datetime-local input. */
const tehranLocal = (d: Date) => new Date(d.getTime() + 210 * 60_000).toISOString().slice(0, 16);

async function activeAgency(request: APIRequestContext, ta: Session, ops: Session, email: string, name: string, licence: string) {
  const agency = await ok<{ id: string }>(request.post(`${API}/admin/partners/agencies`, { headers: auth(ta), data: { display_name: name, commission_bps: 100 } }));
  const users = await ok<{ id: number; email: string; role: string }[]>(request.get(`${API}/admin/users`, { headers: auth(ta) }));
  const u = users.find(x => x.email === email)!;
  if (u.role !== 'agency_partner') await ok(request.put(`${API}/admin/users/${u.id}/role`, { headers: auth(ta), data: { role: 'agency_partner', reason: 'E2E partner agency' } }));
  await ok(request.post(`${API}/agency/${agency.id}/members`, { headers: auth(ta), data: { user_id: u.id } }));
  const owner = await login(request, email);
  await ok(request.put(`${API}/agency/${agency.id}/profile`, { headers: auth(owner), data: { legal_name: `${name} (حقوقی)`, national_id: '14000000000', economic_code: '411400000000', postal_code: '1969000000', ceo_name: 'مدیر نمونه', iban: 'IR000000000000000000000000' } }));
  const lic = await ok<{ id: string; registries: { registry: string }[] }>(request.post(`${API}/agency/${agency.id}/licences`, { headers: auth(owner), data: { licence_type: licence, number: `${licence}-${Date.now() % 1_000_000}`, expires_on: new Date(Date.now() + 400 * 86_400_000).toISOString().slice(0, 10), attest: true } }));
  await ok(request.post(`${API}/agency/${agency.id}/profile/submit`, { headers: auth(owner) }));
  for (const r of lic.registries) await ok(request.post(`${API}/staff/agencies/${agency.id}/licences/${lic.id}/checks`, { headers: auth(ops), data: { registry: r.registry, result: 'confirmed', reference: `INQ-${r.registry}` } }));
  await ok(request.post(`${API}/staff/agencies/${agency.id}/kyc`, { headers: auth(ops), data: { decision: 'approve' } }));
  return { id: agency.id, owner };
}

test('charter schedule change → second approver → agency notice → refund to agency credit', async ({ browser, request }) => {
  test.setTimeout(240_000);
  const suffix = `${Date.now()}`;
  const ta = await login(request, 'tenant-admin@aftab.test'); const opsS = await login(request, 'backoffice@aftab.test');
  const charterer = await activeAgency(request, ta, opsS, 'agency@aftab.test', `چارترکنندهٔ تغییر ${suffix}`, 'BAND_ALEF');
  const buyerName = `آژانس خریدار تغییر ${suffix}`;
  const buyer = await activeAgency(request, ta, opsS, 'org-admin@aftab.test', buyerName, 'BAND_BE');
  // second finance person for the credit limit
  const users = await ok<{ id: number; email: string; role: string }[]>(request.get(`${API}/admin/users`, { headers: auth(ta) }));
  const second = users.find(u => u.email === 'welfare@aftab.test')!;
  if (second.role !== 'finance_operator') await ok(request.put(`${API}/admin/users/${second.id}/role`, { headers: auth(ta), data: { role: 'finance_operator', reason: 'E2E two-person credit' } }));
  const fin1S = await login(request, 'finance@aftab.test'); const fin2S = await login(request, 'welfare@aftab.test');
  const lim = await ok<{ request_id: string }>(request.post(`${API}/finance/agency-accounts/${buyer.id}/credit-limit`, { headers: { ...auth(fin1S), 'Idempotency-Key': `e2e-cc-lim-${suffix}` }, data: { new_limit_irr: 200_000_000, reason: 'قرارداد اعتبار آزمون' } }));
  await ok(request.post(`${API}/maker-checker/requests/${lim.request_id}/approve`, { headers: auth(fin2S), data: {} }));
  // a published block, 3 seats allocated to the buyer, which books 1 seat on its credit
  const dep = new Date(Date.now() + 15 * 86_400_000); dep.setUTCMinutes(0, 0, 0);
  const blk = await ok<{ id: string }>(request.post(`${API}/agency/${charterer.id}/charter/blocks`, { headers: auth(charterer.owner), data: {
    airline_code: 'QB', airline_name: 'قشم ایر', flight_number: suffix.slice(-4), origin: 'IKA', destination: 'IST', origin_city: 'تهران', destination_city: 'استانبول', route_scope: 'international',
    departure_at: dep.toISOString(), arrival_at: new Date(dep.getTime() + 210 * 60_000).toISOString(), seats_total: 10, net_adult_irr: 30_000_000, release_at: new Date(dep.getTime() - 2 * 86_400_000).toISOString(),
    refund_tiers: [{ hours_before: 72, penalty_bps: 2000 }], submit: true } }));
  await ok(request.post(`${API}/staff/charter/blocks/${blk.id}/decision`, { headers: auth(opsS), data: { decision: 'approve', platform_fee_bps: 300 } }));
  await ok(request.post(`${API}/agency/${charterer.id}/charter/blocks/${blk.id}/allocations`, { headers: auth(charterer.owner), data: { agency_id: buyer.id, seats: 3 } }));
  const recv = await ok<{ items: { offer_id: string }[] }>(request.get(`${API}/agency/${buyer.id}/charter/allocations-received`, { headers: auth(buyer.owner) }));
  const pc = await ok<{ id: string }>(request.post(`${API}/offers/${recv.items[0].offer_id}/price-check`, { headers: auth(buyer.owner), data: { units: 1, command_id: `pc-cc-${suffix}` } }));
  await ok(request.post(`${API}/agency/${buyer.id}/credit-bookings`, { headers: auth(buyer.owner), data: { price_check_id: pc.id, command_id: `cb-cc-${suffix}` } }));

  // --- OPS-CH-05: operations previews a +3 h change and sends it for a second approver
  const ops = await pageAs(browser, opsS);
  await go(ops, `/backoffice/charter-blocks/${blk.id}`);
  await expect(ops.getByRole('heading', { name: 'تغییر برنامهٔ پرواز چارتر' })).toBeVisible({ timeout: 60_000 });
  const newDep = new Date(dep.getTime() + 3 * 3_600_000);
  await ops.getByLabel('حرکت جدید (وقت تهران)').fill(tehranLocal(newDep));
  await ops.getByLabel('رسیدن جدید (وقت تهران)').fill(tehranLocal(new Date(newDep.getTime() + 210 * 60_000)));
  await ops.getByLabel('دلیل تغییر و شرح برای آژانس‌ها').fill('تغییر برنامهٔ ایرلاین؛ سایر مشخصات پرواز بدون تغییر است.');
  await ops.getByRole('button', { name: 'پیش‌نمایش اثر' }).click();
  const impact = ops.locator('section.pn-card', { hasText: 'پیش‌نمایش اثر روی سهمیه‌ها و رزروها' });
  await expect(impact.getByRole('row', { name: new RegExp(buyerName) })).toBeVisible();
  await expect(ops.getByText(/۱۸۰ دقیقه · استرداد کامل مجاز/)).toBeVisible();
  await shot(ops, 'OPS-CH-05-charter-schedule-change_1440');
  await ops.getByRole('button', { name: 'ارسال برای تأیید نفر دوم' }).click();
  await expect(ops.getByText('ثبت شما؛ نفر دوم تأیید می‌کند')).toBeVisible();
  // the same staff user cannot approve; the tenant admin (second approver) applies it
  const adm = await pageAs(browser, ta);
  await go(adm, `/backoffice/charter-blocks/${blk.id}`);
  await adm.getByRole('button', { name: 'تأیید و اعمال (نفر دوم)' }).click();
  await expect(adm.getByText('تأیید و اعمال شد.')).toBeVisible();
  await go(adm, `/backoffice/charter-blocks/${blk.id}`);
  await expect(adm.locator('section.pn-card', { hasText: 'سوابق تغییر و لغو این پرواز' }).getByText('تغییر زمان')).toBeVisible();

  // --- AG-CH-06: the buyer agency sees the notice and asks for a refund for its booking
  const ag = await pageAs(browser, buyer.owner);
  await ag.addInitScript(id => sessionStorage.setItem('karenseir-panel-agency', id), buyer.id);
  await go(ag, '/agency/inventory/notices');
  await expect(ag.getByText('نیازمند پاسخ شما')).toBeVisible();
  await shot(ag, 'AG-CH-06-schedule-change-notice_1440');
  await ag.getByRole('button', { name: 'درخواست استرداد' }).click();
  await expect(ag.getByText('بازگشت به اعتبار در انتظار تأیید مالی')).toBeVisible();

  // --- FIN-02c: finance confirms the refund to agency credit (the agency owner was the maker)
  const fin = await pageAs(browser, fin1S);
  await go(fin, '/finance/refunds');
  await fin.locator('section.pn-card', { hasText: 'بازگشت به اعتبار آژانس' }).getByRole('row', { name: new RegExp(buyerName) }).getByRole('link', { name: 'بررسی و تأیید' }).click();
  await expect(fin.getByRole('heading', { name: 'تفکیک استرداد به اعتبار' })).toBeVisible({ timeout: 60_000 });
  await shot(fin, 'FIN-02c-refund-to-agency-credit_1440');
  await fin.getByRole('button', { name: 'تأیید و ثبت در اعتبار' }).click();
  await fin.getByLabel(/مبلغ، مقصد و نام صاحب حساب را بررسی کردم/).check();
  await fin.locator('dialog').getByRole('button', { name: 'تأیید و ثبت در اعتبار' }).click();
  await expect(fin.getByText('در اعتبار آژانس ثبت شد.')).toBeVisible();

  // --- AG-15b: the agency ledger shows the credit-back
  await go(ag, '/agency/credit');
  await expect(ag.locator('td', { hasText: 'استرداد به اعتبار · REFUND' })).toBeVisible();
  await shot(ag, 'AG-15b-credit-ledger-refund_1440');
  await go(ag, '/agency/inventory/notices');
  await expect(ag.getByText('به اعتبار آژانس برگشت')).toBeVisible();

  // --- mobile 390: notice page without horizontal scroll
  const mob = await pageAs(browser, buyer.owner, 390);
  await mob.addInitScript(id => sessionStorage.setItem('karenseir-panel-agency', id), buyer.id);
  await go(mob, '/agency/inventory/notices');
  await expect(mob.getByText('به اعتبار آژانس برگشت')).toBeVisible();
  expect(await mob.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await shot(mob, 'AG-CH-06-schedule-change-notice_390');
});
