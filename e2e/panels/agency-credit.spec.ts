import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

/* Panels Phase 2 — E2E-E (minimal): agency onboarding (AG-02) → staff licence verification per registry + KYC approval (OPS-09)
   → finance maker sets a credit limit, a different finance user approves (maker-checker) → agency markup rule (AG-07)
   → booking on agency credit with the agency-buyer MoneyBreakdown (AG-03) → statement shows HOLD + CAPTURE (AG-15).
   Development seed accounts (dev-login), ENVIRONMENT=development, SQLite e2e DB. The flight is declared through the real
   inventory API by the seed platform admin; nothing is bought from a real supplier. */
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
const card = (page: Page, title: string) => page.locator('section.pn-card', { has: page.getByRole('heading', { name: title }) });
const letters = () => Array.from({ length: 2 }, () => String.fromCharCode(65 + Math.floor(Math.random() * 26))).join('');

test('agency onboarding → licence verification → two-person credit limit → booking on agency credit', async ({ browser, request }) => {
  test.setTimeout(180_000);
  const suffix = `${Date.now()}`;
  // --- a real flight offer through the inventory API (platform admin), route codes unique per run
  const pa = await login(request, 'platform-admin@aftab.test');
  const origin = `Q${letters()}`; const dest = `Z${letters()}`;
  const sup = await ok<{ id: string }>(request.post(`${API}/inventory/suppliers`, { headers: auth(pa), data: { name: `E2E airline ${suffix}`, supplier_type: 'airline' } }));
  const route = await ok<{ id: string }>(request.post(`${API}/inventory/routes`, { headers: auth(pa), data: { origin, destination: dest, scope: 'international' } }));
  const start = new Date(Date.now() + 10 * 86_400_000); const iso = start.toISOString().slice(0, 10); const wd = String((start.getUTCDay() + 6) % 7);
  const series = await ok<{ id: string }>(request.post(`${API}/inventory/flight-series`, { headers: auth(pa), data: { route_id: route.id, supplier_id: sup.id, airline_code: 'EP', flight_number: suffix.slice(-4),
    date_from: iso, date_to: iso, schedule: { [wd]: { time: '09:00', duration: 120 } }, capacity: 20, adult_fare: 20_000_000, child_fare: 20_000_000, infant_fare: 2_000_000 } }));
  await ok(request.post(`${API}/inventory/flight-series/${series.id}/generate`, { headers: auth(pa) }));

  // --- tenant admin registers the agency and its owner user (seed agency account)
  const ta = await login(request, 'tenant-admin@aftab.test');
  const agency = await ok<{ id: string; name: string }>(request.post(`${API}/admin/partners/agencies`, { headers: auth(ta), data: { display_name: `آژانس آزمون E2E ${suffix}`, commission_bps: 120 } }));
  const users = await ok<{ id: number; email: string; role: string }[]>(request.get(`${API}/admin/users`, { headers: auth(ta) }));
  const agencyUser = users.find(u => u.email === 'agency@aftab.test')!;
  await ok(request.post(`${API}/agency/${agency.id}/members`, { headers: auth(ta), data: { user_id: agencyUser.id } }));
  const second = users.find(u => u.email === 'welfare@aftab.test')!;  // a second finance person for maker-checker
  if (second.role !== 'finance_operator') await ok(request.put(`${API}/admin/users/${second.id}/role`, { headers: auth(ta), data: { role: 'finance_operator', reason: 'E2E two-person credit' } }));
  const owner = await login(request, 'agency@aftab.test');
  const ag = await pageAs(browser, owner);
  await ag.addInitScript(id => sessionStorage.setItem('karenseir-panel-agency', id), agency.id);

  // --- AG-02: owner fills the legal profile, adds a BAND_ALEF licence and submits for verification
  await ag.goto('/agency/profile');
  const prof = card(ag, 'پروفایل حقوقی');
  await prof.getByLabel('نام حقوقی').fill('شرکت خدمات مسافرتی آزمون (نمونه)');
  await prof.getByLabel('شناسهٔ ملی').fill('۱۴۰۰۰۰۰۰۰۰۰');
  await prof.getByLabel('شمارهٔ اقتصادی').fill('411400000000');
  await prof.getByLabel('کد پستی').fill('1969000000');
  await prof.getByLabel('مدیرعامل').fill('مدیر نمونه');
  await prof.getByLabel('شبا').fill('IR000000000000000000000000');
  await prof.getByRole('button', { name: 'ذخیرهٔ پروفایل' }).click();
  await expect(prof.getByText('ذخیره شد.')).toBeVisible();
  const licCard = card(ag, 'بارگذاری یا تمدید مجوز');
  await licCard.getByLabel('شمارهٔ مجوز').fill(`A-1405-${suffix.slice(-4)}`);
  await licCard.getByLabel('تاریخ انقضا').fill(new Date(Date.now() + 400 * 86_400_000).toISOString().slice(0, 10));
  await licCard.getByLabel(/اطلاعات بالا با مدرک مطابقت دارد/).check();
  await licCard.getByRole('button', { name: 'ارسال برای احراز' }).click();
  await expect(card(ag, 'مجوزها').getByText(`A-1405-${suffix.slice(-4)}`)).toBeVisible();
  await prof.getByRole('button', { name: 'ارسال برای احراز' }).click();
  await expect(prof.locator('[data-status="submitted"]')).toBeVisible();
  await shot(ag, 'AG-02-profile-licences_1440');

  // --- OPS-09: back office records the check in each required registry, then approves the agency
  const ops = await pageAs(browser, await login(request, 'backoffice@aftab.test'));
  await ops.goto('/backoffice/agencies');
  await ops.getByRole('row', { name: new RegExp(agency.name) }).getByRole('button', { name: 'باز کردن' }).click();
  for (const registry of ['درگاه ملی مجوزها', 'سازمان هواپیمایی کشوری']) {
    const form = ops.locator('form', { has: ops.getByRole('button', { name: 'ثبت نتیجهٔ احراز' }) }).first();
    await form.locator('select').first().selectOption({ label: registry });
    await form.getByLabel('شمارهٔ پیگیری استعلام').fill(`INQ-${suffix.slice(-5)}`);
    await form.getByRole('button', { name: 'ثبت نتیجهٔ احراز' }).click();
    await expect(ops.getByText('نتیجه ثبت شد.')).toBeVisible();
  }
  await expect(ops.locator('[data-status="verified"]').first()).toBeVisible();
  await ops.getByRole('button', { name: 'تأیید و فعال‌سازی آژانس' }).click();
  await expect(ops.getByText('تصمیم ثبت شد.')).toBeVisible();
  await shot(ops, 'OPS-09-agency-verification_1440');

  // --- finance: maker requests the credit limit, nothing moves; a different finance user approves
  const fin1 = await pageAs(browser, await login(request, 'finance@aftab.test'));
  await fin1.goto('/finance/agency-accounts');
  await fin1.getByRole('row', { name: new RegExp(agency.name) }).getByRole('button', { name: 'شارژ / سقف' }).click();
  await fin1.getByLabel('سقف تازه (ریال)').fill('50,000,000');
  await fin1.getByLabel('دلیل').nth(1).fill('قرارداد اعتبار آزمون');
  await fin1.getByRole('button', { name: 'ثبت درخواست سقف (maker)' }).click();
  await expect(fin1.getByText('ثبت شما؛ نفر دوم تأیید می‌کند')).toBeVisible();
  expect((await ok<{ balances: { credit_limit_irr: number } }>(request.get(`${API}/agency/${agency.id}/wallet`, { headers: auth(owner) }))).balances.credit_limit_irr).toBe(0);
  const fin2 = await pageAs(browser, await login(request, 'welfare@aftab.test'));
  await fin2.goto('/finance/agency-accounts');
  await fin2.getByRole('row', { name: /تغییر سقف اعتبار/ }).getByRole('button', { name: 'تأیید' }).click();
  await expect(fin2.getByText('تأیید و اعمال شد.')).toBeVisible();
  await shot(fin2, 'FIN-agency-accounts-checker_1440');

  // --- AG-07: the owner adds a fixed markup rule for flights
  await ag.goto('/agency/pricing');
  await ag.getByRole('button', { name: 'قاعدهٔ جدید' }).click();
  await ag.getByLabel('مقدار (ریال)').fill('1,000,000');
  await ag.getByRole('button', { name: 'ذخیرهٔ قاعده' }).click();
  await expect(card(ag, 'قواعد markup من').getByText(/ثابت ۱٬۰۰۰٬۰۰۰ ریال/)).toBeVisible();
  await shot(ag, 'AG-07-markup-commission_1440');

  // --- AG-03: price check → agency-buyer breakdown (VAT on commission only) → book and pay from the agency account
  await ag.goto('/agency/sell');
  await ag.getByLabel('جست‌وجو در عرضه‌های فعال').fill(origin);
  await ag.getByRole('button', { name: 'جست‌وجو' }).click();
  await ag.getByRole('button', { name: 'استعلام و پیش‌نمایش' }).first().click();
  const quote = ag.getByTestId('agency-quote');
  await expect(quote.locator('[data-view="agency_buyer"]')).toContainText('۲۴۰٬۰۰۰ ریال');  // commission 1.2% of 20,000,000
  await expect(quote).toContainText('۲۴٬۰۰۰ ریال');   // VAT 10% of the commission, not of the fare
  await expect(quote).toContainText('۲۱٬۰۰۰٬۰۰۰ ریال'); // customer price = net + markup
  await shot(ag, 'AG-03-sell-on-credit_1440');
  await quote.getByRole('button', { name: 'رزرو و پرداخت از حساب آژانس' }).click();
  await expect(quote.getByText('کد رزرو')).toBeVisible();

  // --- AG-15: the statement shows the hold and the capture; available credit dropped by the net price only
  await ag.goto('/agency/credit');
  await expect(ag.locator('td', { hasText: 'کسر در صدور · CAPTURE' })).toBeVisible();
  await expect(ag.locator('td', { hasText: 'بلوکه · HOLD' }).first()).toBeVisible();
  await expect(ag.locator('.pn-stat', { hasText: 'ماندهٔ قابل استفاده' })).toContainText('۳۰٬۰۰۰٬۰۰۰ ریال');
  await shot(ag, 'AG-15-credit-wallet_1440');
  const download = ag.waitForEvent('download');
  await ag.getByRole('button', { name: 'خروجی CSV' }).click();
  expect((await download).suggestedFilename()).toMatch(/^statement-.*\.csv$/);
  await ag.goto('/agency/bookings');
  await expect(card(ag, 'رزروهای پرداخت‌شده از حساب آژانس').getByText('تأییدشده').first()).toBeVisible();
  await shot(ag, 'AG-05-bookings_1440');
  await ag.goto('/agency/invoices');
  await expect(ag.getByText('B2B نوع اول')).toBeVisible();
  await shot(ag, 'AG-invoices_1440');
  await ag.goto('/agency');
  await expect(ag.getByRole('heading', { name: 'وضعیت B2B آژانس' })).toBeVisible();
  await shot(ag, 'AG-01-today_1440');

  // --- mobile 390: credit page without horizontal scroll
  const mob = await pageAs(browser, owner, 390);
  await mob.addInitScript(id => sessionStorage.setItem('karenseir-panel-agency', id), agency.id);
  await mob.goto('/agency/credit');
  await expect(mob.locator('td', { hasText: 'کسر در صدور · CAPTURE' })).toBeVisible();
  expect(await mob.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await shot(mob, 'AG-15-credit-wallet_390');
});
