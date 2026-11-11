import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

/* E2E-C (spec §2.12, Phase 1 acceptance 3/4/6): a real booking paid through the local sandbox gateway
   (PAYMENT_PROVIDER=sandbox, ENVIRONMENT=development — never a real bank), then
   customer cancel wizard → ops approve → finance maker → a different finance checker → customer sees the paid refund.
   Seed accounts are the development seed (dev-login); the second finance user is promoted through the real admin API. */
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
  const ctx = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 }, locale: 'fa-IR' });
  await ctx.addInitScript(value => sessionStorage.setItem('karenseir-auth-session', value), JSON.stringify(session));
  return ctx.newPage();
}
async function shot(page: Page, name: string) { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); }

test('cancel → ops approve → two-person finance refund → customer sees paid refund', async ({ browser, request }) => {
  test.setTimeout(120_000);
  const suffix = `${Date.now()}`;
  // --- a real booking with a verified cancellation policy (penalty 400,000 IRR of 2,000,000)
  const supplier = await login(request, 'supplier@aftab.test');
  const sup = await ok<{ id: string }>(request.post(`${API}/supplier/onboarding`, { headers: { ...auth(supplier), 'Idempotency-Key': `e2e-sup-${suffix}` }, data: { supplier_type: 'hotel', display_name: `E2E refund supplier ${suffix}` } }));
  const day = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
  const rate = { check_in: day(30), check_out: day(32), room_type: 'Mock QA room', rate_plan: 'Mock QA fixed stay', price_basis: 'room_stay', occupancy: { adults: 1, children_ages: [] } };
  const policy = { verified: true, source: 'contract:e2e', verified_at: new Date().toISOString(), cancellation: { refundable: true, penalty_amount: 400_000 } };
  const offer = await ok<{ id: string }>(request.post(`${API}/supplier/offers`, { headers: auth(supplier), data: { supplier_id: sup.id, service_type: 'hotel', title: 'هتل آزمون استرداد', amount: 2_000_000, available_units: 3, valid_minutes: 60, policy, attributes: { hotel_rate: rate }, fulfillment_mode: 'manual_supplier', provider_key: 'manual_supplier' } }));
  const customer = await login(request, 'employee@aftab.test');
  const check = await ok<{ id: string }>(request.post(`${API}/offers/${offer.id}/price-check`, { headers: auth(customer), data: { units: 1, hotel_stay: { check_in: rate.check_in, check_out: rate.check_out, rooms: [rate.occupancy] }, command_id: `e2e-price-${suffix}` } }));
  const res = await ok<{ id: string }>(request.post(`${API}/orchestration/bookings`, { headers: auth(customer), data: { price_check_id: check.id, command_id: `e2e-book-${suffix}` } }));
  const traveller = await ok<{ id: string }>(request.post(`${API}/me/travellers`, { headers: auth(customer), data: { full_name: 'مسافر آزمون استرداد', profile_reference: 'masked:e2e' } }));
  const checkout = await ok<{ id: string }>(request.post(`${API}/reservations/${res.id}/checkout-sessions`, { headers: auth(customer), data: { command_id: `e2e-co-${suffix}` } }));
  let last: { payment_intent_id?: string } = {};
  for (const [step, body] of [['traveller', { traveller_ids: [traveller.id] }], ['recheck', {}], ['policy', { acknowledged: true }], ['funding', { wallet_amount: 0 }], ['invoice', {}], ['payment', {}]] as const) {
    last = await ok(request.put(`${API}/checkout-sessions/${checkout.id}/steps/${step}`, { headers: auth(customer), data: { command_id: `e2e-${step}-${suffix}`, ...body } }));
  }
  // --- pay through the sandbox gateway (test mode: no money moves)
  const init = await request.post(`${API}/payments/${last.payment_intent_id}/initiate`, { headers: auth(customer) });
  const redirect = init.ok() ? ((await init.json()) as { redirect_url: string }).redirect_url : '';
  test.skip(!redirect.includes('/payments/sandbox/'), 'backend is not running with PAYMENT_PROVIDER=sandbox');
  const url = new URL(redirect); const authority = url.pathname.split('/').pop()!; const state = url.searchParams.get('state')!;
  const decided = await ok<{ callback_url: string }>(request.post(`${API}/payments/sandbox/${authority}/decision`, { form: { state, decision: 'success' } }));
  const callback = await ok<{ payment_status: string }>(request.get(`${API}${decided.callback_url}`));
  expect(callback.payment_status).toBe('captured');
  // --- a second finance user, promoted through the real admin API
  const admin = await login(request, 'tenant-admin@aftab.test');
  const users = await ok<{ id: number; email: string; role: string }[]>(request.get(`${API}/admin/users`, { headers: auth(admin) }));
  const second = users.find(u => u.email === 'welfare@aftab.test')!;
  if (second.role !== 'finance_operator') await ok(request.put(`${API}/admin/users/${second.id}/role`, { headers: auth(admin), data: { role: 'finance_operator', reason: 'E2E two-person refund' } }));

  // --- customer: 3-step cancel wizard with the server's penalty preview
  const cust = await pageAs(browser, customer);
  await cust.goto(`/account/bookings/${res.id}/cancel`);
  await expect(cust.getByRole('heading', { name: /درخواست برای رزرو/ })).toBeVisible();
  await shot(cust, 'C-03a-step1_1440');
  await cust.getByRole('button', { name: 'ادامه' }).click();
  await expect(cust.getByLabel('پیش‌نمایش جریمه')).toContainText('۱۶۰٬۰۰۰ تومان');
  await shot(cust, 'C-03a-step2_1440');
  await cust.getByRole('button', { name: 'ادامه' }).click();
  await cust.getByLabel(/کیف پول کارن تراول/).check();
  await cust.getByLabel(/قوانین لغو و مبلغ بالا را خواندم/).check();
  await shot(cust, 'C-03a-step3_1440');
  await cust.getByRole('button', { name: 'ثبت درخواست استرداد' }).click();
  await expect(cust).toHaveURL(/\/account\/refunds\/[0-9a-f-]{36}$/, { timeout: 60_000 });
  const requestId = cust.url().split('/').pop()!;
  await expect(cust.locator('[data-status="submitted"]').first()).toBeVisible();
  await expect(cust.getByLabel('گام بعدی')).toContainText('شروع بررسی توسط کارشناس');

  // --- ops: queue → handling → start review → approve with the verified policy
  const ops = await pageAs(browser, await login(request, 'backoffice@aftab.test'));
  await ops.goto('/backoffice/queues/service_requests');
  await expect(ops.getByRole('table', { name: 'صف درخواست‌های لغو، تغییر و استرداد' })).toBeVisible();
  await shot(ops, 'OPS-02-queue_1440');
  await ops.goto(`/backoffice/requests/${requestId}`);
  await ops.getByRole('button', { name: 'شروع بررسی' }).click();
  await expect(ops.getByRole('status').filter({ hasText: 'ثبت شد' })).toBeVisible();
  await ops.getByRole('button', { name: 'تأیید و ارسال به مالی' }).click();
  await shot(ops, 'OPS-03-approve-dialog_1440');
  await ops.getByRole('dialog').getByRole('button', { name: 'تأیید و ارسال به صف مالی' }).click();
  await expect(ops.locator('[data-status="refund_queued"]').first()).toBeVisible();
  await shot(ops, 'OPS-03-handled_1440');

  // --- finance maker
  const fin1 = await pageAs(browser, await login(request, 'finance@aftab.test'));
  await fin1.goto('/finance/refunds');
  await shot(fin1, 'FIN-02-queue_1440');
  const mine = await ok<{ refund: { id: string; amount: number } }>(request.get(`${API}/me/service-requests/${requestId}`, { headers: auth(customer) }));
  expect(mine.refund.amount).toBe(1_600_000);
  await expect(fin1.getByRole('table', { name: 'صف استرداد' })).toContainText('۱٬۶۰۰٬۰۰۰ ریال');
  await fin1.waitForLoadState('networkidle'); // the list must be hydrated before the client-side link click
  await fin1.locator(`a[href="/finance/refunds/${mine.refund.id}"]`).click();
  await expect(fin1).toHaveURL(new RegExp(`/finance/refunds/${mine.refund.id}$`), { timeout: 60_000 });
  const refundUrl = fin1.url();
  await fin1.getByRole('button', { name: 'ثبت و ارسال برای تأیید نفر دوم' }).click();
  const dialog = fin1.getByRole('dialog');
  await expect(dialog).toContainText('۱٬۶۰۰٬۰۰۰ ریال');
  await expect(dialog).toContainText('یک میلیون و ششصد هزار');
  await shot(fin1, 'FIN-02a-confirm_1440');
  await dialog.getByLabel(/مبلغ، مقصد و نام صاحب حساب را بررسی کردم/).check();
  await dialog.getByRole('button', { name: 'ثبت و ارسال برای تأیید نفر دوم' }).click();
  await expect(fin1.getByText('شما این پرداخت را آماده کرده‌اید')).toBeVisible();   // maker cannot approve

  // --- finance checker (a different user)
  const fin2 = await pageAs(browser, await login(request, 'welfare@aftab.test'));
  await fin2.goto(refundUrl);
  await fin2.getByRole('button', { name: 'تأیید و پرداخت' }).click();
  await fin2.getByRole('dialog').getByLabel(/بررسی کردم/).check();
  await fin2.getByRole('dialog').getByRole('button', { name: 'تأیید و پرداخت' }).click();
  await expect(fin2.getByRole('heading', { name: 'پرداخت انجام شد' })).toBeVisible();
  await expect(fin2.getByRole('table', { name: 'سطرهای سند' })).toBeVisible();
  await shot(fin2, 'FIN-02a-paid_1440');

  // --- customer sees each step, the paid refund and the wallet credit
  await cust.goto(`/account/refunds/${requestId}`);
  await expect(cust.locator('[data-status="refund_paid"]').first()).toBeVisible();
  for (const step of ['ثبت درخواست', 'شروع بررسی', 'تأیید درخواست', 'ورود به صف پرداخت', 'پرداخت استرداد']) await expect(cust.getByRole('list', { name: 'روند' })).toContainText(step);
  await shot(cust, 'C-04a-refund-timeline_1440');
  await cust.goto('/account/wallet');
  await expect(cust.getByRole('table', { name: 'تاریخچهٔ کیف پول' })).toContainText('۱۶۰٬۰۰۰ تومان');
  await shot(cust, 'C-06-wallet_1440');
  const mobile = await pageAs(browser, customer, 390);
  for (const [path, name] of [['/account/refunds', 'C-04-refunds_390'], [`/account/refunds/${requestId}`, 'C-04a-refund-timeline_390'], ['/account', 'C-01-today_390'], [`/account/bookings/${res.id}`, 'C-03-booking-detail_390']] as const) {
    await mobile.goto(path); await mobile.waitForLoadState('networkidle');
    expect(await mobile.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${path} has no horizontal scroll at 390`).toBeTruthy();
    await shot(mobile, name);
  }
});
