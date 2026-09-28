import { expect, test } from '@playwright/test';

test('public login uses the consumer tenant and preserves registration handoff', async ({ page }) => {
  let sent: Record<string, unknown> | undefined;
  await page.route('**/auth/otp/request', async route => {
    sent = route.request().postDataJSON();
    await route.fulfill({ json: { challenge_id: '00000000-0000-4000-8000-000000000001', expires_in: 300, status: 'accepted' } });
  });
  await page.goto('/login?redirect=%2Ftrips');
  await expect(page.getByLabel('سازمان', { exact: true })).toHaveCount(0);
  await page.getByLabel('شماره همراه یا شناسه ورود').fill('09121230000');
  await page.getByRole('button', { name: 'دریافت کد ورود' }).click();
  await expect(page.getByLabel('کد شش‌رقمی')).toBeVisible();
  expect(sent).toEqual({ tenant_slug: 'karenseir-consumer', identifier: '09121230000' });
  await page.getByRole('link', { name: 'حساب ندارید؟ ثبت‌نام کنید' }).click();
  await expect(page).toHaveURL(/\/register\?redirect=%2Ftrips$/);
});

test('organization login remains explicit and changes discard the old challenge', async ({ page }) => {
  let sent: Record<string, unknown> | undefined;
  await page.route('**/auth/otp/request', async route => {
    sent = route.request().postDataJSON();
    await route.fulfill({ json: { challenge_id: '00000000-0000-4000-8000-000000000002', expires_in: 300, status: 'accepted' } });
  });
  await page.goto('/login');
  await page.getByRole('checkbox', { name: 'ورود سازمانی' }).check();
  await page.getByLabel('سازمان', { exact: true }).fill('aftab-bank');
  await page.getByLabel('شماره همراه یا شناسه ورود').fill('employee@aftab.test');
  await page.getByRole('button', { name: 'دریافت کد ورود' }).click();
  await expect(page.getByLabel('کد شش‌رقمی')).toBeVisible();
  expect(sent).toEqual({ tenant_slug: 'aftab-bank', identifier: 'employee@aftab.test' });
  await page.getByRole('checkbox', { name: 'ورود سازمانی' }).uncheck();
  await expect(page.getByLabel('کد شش‌رقمی')).toHaveCount(0);
});
