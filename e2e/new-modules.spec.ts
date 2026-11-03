import { expect, test, type Page } from '@playwright/test';

const api = process.env.E2E_API_URL || 'http://127.0.0.1:8100';
const artifactDir = process.env.E2E_ARTIFACT_DIR || 'artifacts';

// next dev compiles each route on first visit and may abort that first navigation; retry once
async function open(page: Page, path: string) {
  try { await page.goto(path, { waitUntil: 'domcontentloaded' }); }
  catch (e) { if (!String(e).includes('ERR_ABORTED')) throw e; await page.waitForTimeout(1500); await page.goto(path, { waitUntil: 'domcontentloaded' }); }
}

async function signIn(page: Page, email: string) {
  const res = await page.request.post(`${api}/auth/dev-login`, { data: { email } });
  expect(res.ok()).toBeTruthy();
  const session = await res.json();
  await page.addInitScript(s => { sessionStorage.setItem('karenseir-auth-session', s); }, JSON.stringify(session));
}

test('sales desk: create a case from the panel and open it', async ({ page }) => {
  await signIn(page, 'backoffice@aftab.test');
  await open(page, '/admin/sales-desk');
  await expect(page.getByRole('heading', { name: 'میز گفتگو و فروش' })).toBeVisible();
  const mobile = '0912' + String(Date.now()).slice(-7);
  await page.getByLabel('نام مشتری').fill('مشتری آزمون مرورگر');
  await page.getByLabel('موبایل').first().fill(mobile);
  await page.getByLabel('سفر درخواستی').fill('کیش ۳ شب');
  await page.getByRole('button', { name: 'ثبت و ارجاع' }).click();
  await expect(page.getByText(/پرونده DSK-[0-9A-F]+ ثبت شد/)).toBeVisible();
  await page.getByRole('button', { name: 'باز کردن' }).first().click();
  await expect(page.getByRole('heading', { name: 'تاریخچه' })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/sales-desk.png`, fullPage: true, animations: 'disabled' });
});

test('safarsaz, loyalty, sms campaigns, revenue and journal pages load with real data states', async ({ page }) => {
  await signIn(page, 'tenant-admin@aftab.test');
  for (const [path, heading] of [['/admin/safarsaz', 'سفرساز'], ['/admin/loyalty', 'حلقه‌ی همسفران'], ['/admin/sms-campaigns', 'کمپین پیامکی'],
                                 ['/finance/markup-revenue', 'سود و کمیسیون فروش'], ['/finance/journal-export', 'خروجی حسابداری (فرانگر)']] as const) {
    await open(page, path);
    await expect(page.getByRole('heading', { level: 1 })).toContainText(heading.split(' ')[0]);
    await expect(page.locator('.pn-main')).toBeVisible();
    await expect(page.locator('.pn-note.error', {hasNotText: 'سرویس پیامک هنوز وصل نیست'})).toHaveCount(0); // panel error state (Next's route announcer also uses role=alert)
    await page.screenshot({ path: `${artifactDir}/new-modules${path.replace(/\//g, '-')}.png`, fullPage: true, animations: 'disabled' });
  }
  await open(page, '/admin/sms-campaigns');
  await expect(page.getByText(/سرویس پیامک/).first()).toBeVisible();
});

test('customer app shell, offline page and manifest', async ({ page }) => {
  const manifest = await page.request.get('/manifest.webmanifest');
  expect(manifest.ok()).toBeTruthy();
  expect((await manifest.json()).start_url).toBe('/app');
  const offline = await page.request.get('/offline.html');
  expect(offline.ok()).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, '/app');
  await expect(page.getByRole('navigation', { name: 'منوی اصلی اپ' })).toBeVisible();
  await signIn(page, 'employee@aftab.test');
  await open(page, '/app/account');
  await expect(page.getByRole('heading', { name: 'حلقه‌ی همسفران' })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/app-account.png`, fullPage: true, animations: 'disabled' });
});

test('contact page trip-request form validates before sending', async ({ page }) => {
  await open(page, '/contact');
  await expect(page.getByRole('heading', { name: 'درخواست سفر و مشاوره' })).toBeVisible();
  await page.getByRole('button', { name: 'ارسال درخواست' }).click();
  await expect(page.getByRole('heading', { name: 'درخواست شما رسید' })).toHaveCount(0); // required fields block the submit
});

test('ops dashboard and contract file render from real rows', async ({ page }) => {
  await signIn(page, 'backoffice@aftab.test');
  await open(page, '/admin/ops');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('پیشخوان عملیات');
  await expect(page.getByRole('heading', { name: 'کارهای در انتظار', exact: true })).toBeVisible();
  await expect(page.getByRole('img', { name: /نمودار ۳۰ روز/ })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/ops-dashboard.png`, fullPage: true, animations: 'disabled' });
  await open(page, '/admin/contracts');
  await expect(page.getByRole('heading', { name: 'جستجوی قرارداد' })).toBeVisible();
  const first = page.getByRole('button', { name: 'پرونده' }).first();
  if (await first.count()) {
    await first.click();
    await expect(page.getByRole('heading', { name: 'سامانه‌ی مؤدیان' })).toBeVisible();
    await page.screenshot({ path: `${artifactDir}/new-modules/contract-file.png`, fullPage: true, animations: 'disabled' });
  }
});

test('account security setup shows QR and customer documents page', async ({ page }) => {
  await signIn(page, 'employee@aftab.test');
  await open(page, '/account/security');
  await page.getByRole('button', { name: 'شروع راه‌اندازی' }).click();
  await expect(page.getByRole('img', { name: /کد QR/ })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/security-setup.png`, fullPage: true, animations: 'disabled' });
  await open(page, '/account/documents');
  await expect(page.getByRole('heading', { name: 'بارگذاری مدرک', exact: true })).toBeVisible();
});

test('staff document queue opens for backoffice', async ({ page }) => {
  await signIn(page, 'backoffice@aftab.test');
  await open(page, '/admin/documents');
  await expect(page.getByRole('heading', { name: 'صف مدارک', exact: true })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/documents-queue.png`, fullPage: true, animations: 'disabled' });
});

test('ledger and supplier reconciliation pages load for finance', async ({ page }) => {
  await signIn(page, 'finance@aftab.test');
  await open(page, '/finance/ledger');
  await expect(page.getByRole('heading', { name: 'دوره‌های مالی (ماه شمسی)', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'سرفصل‌ها و قواعد' }).click();
  await expect(page.getByRole('heading', { name: 'سرفصل حساب‌ها', exact: true })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/ledger.png`, fullPage: true, animations: 'disabled' });
  await open(page, '/finance/suppliers');
  await expect(page.getByRole('heading', { name: 'عملکرد تأمین‌کنندگان', exact: true })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/suppliers.png`, fullPage: true, animations: 'disabled' });
});

test('public voucher check rejects an unsigned code without leaking data', async ({ page }) => {
  await open(page, '/v/1.00000000-0000-0000-0000-000000000000.AAAAAAAAAAAAAAAA');
  await expect(page.getByRole('heading', { name: 'واچر معتبر نیست', exact: true })).toBeVisible();
});

test('platform tenants, loyalty call schedule and solutions site', async ({ page }) => {
  await signIn(page, 'platform-admin@aftab.test');
  await open(page, '/admin/tenants');
  await expect(page.getByRole('heading', { name: 'مستأجرها', exact: true })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/tenants.png`, fullPage: true, animations: 'disabled' });
  await open(page, '/admin/loyalty');
  await page.getByRole('tab', { name: 'برنامه‌ی تماس' }).click();
  await expect(page.getByRole('heading', { name: 'برنامه‌ی تماس', exact: true })).toBeVisible();
  await open(page, '/solutions');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('از سایت تا سند حسابداری');
  await expect(page.getByRole('heading', { name: 'درخواست دمو و قیمت' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: `${artifactDir}/new-modules/solutions.png`, fullPage: true, animations: 'disabled' });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  await page.screenshot({ path: `${artifactDir}/new-modules/solutions-mobile.png`, fullPage: true, animations: 'disabled' });
});

test('ops panel shows the mobile bottom navigation on phones', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, 'backoffice@aftab.test');
  await open(page, '/admin/ops');
  await expect(page.getByRole('heading', { name: 'کارهای در انتظار', exact: true })).toBeVisible();
  const bottom = page.getByRole('navigation', { name: 'میان‌بر پنل عملیات' });
  await expect(bottom).toBeVisible();
  await expect(bottom.getByRole('link', { name: /پیشخوان/ })).toHaveAttribute('aria-current', 'page');
  await page.screenshot({ path: `${artifactDir}/new-modules/ops-mobile.png`, fullPage: false, animations: 'disabled' });
});
