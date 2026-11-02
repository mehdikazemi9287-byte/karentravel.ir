import { expect, test, type Page } from '@playwright/test';

const api = process.env.E2E_API_URL || 'http://127.0.0.1:8100';
const artifactDir = process.env.E2E_ARTIFACT_DIR || 'artifacts';

async function signIn(page: Page, email: string) {
  const res = await page.request.post(`${api}/auth/dev-login`, { data: { email } });
  expect(res.ok()).toBeTruthy();
  const session = await res.json();
  await page.addInitScript(s => { sessionStorage.setItem('karenseir-auth-session', s); }, JSON.stringify(session));
}

test('sales desk: create a case from the panel and open it', async ({ page }) => {
  await signIn(page, 'backoffice@aftab.test');
  await page.goto('/admin/sales-desk');
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
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1 })).toContainText(heading.split(' ')[0]);
    await expect(page.locator('.pn-main')).toBeVisible();
    await expect(page.locator('.pn-note.error', {hasNotText: 'سرویس پیامک هنوز وصل نیست'})).toHaveCount(0); // panel error state (Next's route announcer also uses role=alert)
    await page.screenshot({ path: `${artifactDir}/new-modules${path.replace(/\//g, '-')}.png`, fullPage: true, animations: 'disabled' });
  }
  await page.goto('/admin/sms-campaigns');
  await expect(page.getByText(/سرویس پیامک/).first()).toBeVisible();
});

test('customer app shell, offline page and manifest', async ({ page }) => {
  const manifest = await page.request.get('/manifest.webmanifest');
  expect(manifest.ok()).toBeTruthy();
  expect((await manifest.json()).start_url).toBe('/app');
  const offline = await page.request.get('/offline.html');
  expect(offline.ok()).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/app');
  await expect(page.getByRole('navigation', { name: 'منوی اصلی اپ' })).toBeVisible();
  await signIn(page, 'employee@aftab.test');
  await page.goto('/app/account');
  await expect(page.getByRole('heading', { name: 'حلقه‌ی همسفران' })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/new-modules/app-account.png`, fullPage: true, animations: 'disabled' });
});

test('contact page trip-request form validates before sending', async ({ page }) => {
  await page.goto('/contact');
  await expect(page.getByRole('heading', { name: 'درخواست سفر و مشاوره' })).toBeVisible();
  await page.getByRole('button', { name: 'ارسال درخواست' }).click();
  await expect(page.getByRole('heading', { name: 'درخواست شما رسید' })).toHaveCount(0); // required fields block the submit
});
