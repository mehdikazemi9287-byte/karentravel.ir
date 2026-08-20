import { expect, test, type APIRequestContext } from '@playwright/test';

const api = 'http://127.0.0.1:8100';

async function login(request: APIRequestContext, email: string) {
  const response = await request.post(`${api}/auth/dev-login`, { data: { email } });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test('login, search and booking flow through the pilot UI', async ({ page }) => {
  const response = await page.goto('/pilot');
  expect(response?.headers()['content-security-policy']).toContain("frame-ancestors 'none'");
  await expect(page.getByRole('heading', { name: 'رزرو هتل با جریان سازمانی' })).toBeVisible();
  await page.getByRole('button', { name: 'ورود و دریافت هتل‌ها' }).click();
  await expect(page.getByText(/خوش آمدید/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'هتل پارسیان آزادی' })).toBeVisible();
  await page.getByRole('button', { name: 'درخواست ۲ شب' }).first().click();
  await expect(page.getByText(/در انتظار تأیید است/)).toBeVisible();

  await page.goto('/');
  await page.getByRole('tab', { name: 'هتل', exact: true }).click();
  await page.getByRole('button', { name: 'جست‌وجو', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('گزینه‌های نمایشی');
});

test('approval and tenant dashboard API flow', async ({ request }) => {
  const employee = await login(request, 'employee@aftab.test');
  const booking = await request.post(`${api}/bookings`, {
    headers: { Authorization: `Bearer ${employee.access_token}`, 'Idempotency-Key': `e2e-booking-${Date.now()}` },
    data: { hotel_id: 2, nights: 1 },
  });
  expect(booking.status()).toBe(201);
  const welfare = await login(request, 'welfare@aftab.test');
  const approved = await request.post(`${api}/bookings/${(await booking.json()).id}/approval`, {
    headers: { Authorization: `Bearer ${welfare.access_token}` }, data: { decision: 'approve' },
  });
  expect((await approved.json()).status).toBe('approved');
  const dashboard = await request.get(`${api}/me/dashboard`, { headers: { Authorization: `Bearer ${employee.access_token}` } });
  expect((await dashboard.json()).bookings.some((item: { status: string }) => item.status === 'approved')).toBeTruthy();
});

test('cancellation and refund preview remains non-destructive', async ({ page }) => {
  await page.goto('/manage-booking/book1');
  await page.getByRole('button', { name: /کنسلی و استرداد/ }).click();
  await expect(page.getByText('تا قبل از تأیید نهایی، رزرو شما تغییری نمی‌کند.')).toBeVisible();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'تأیید درخواست' }).click();
  await expect(page.getByText('✓ درخواست ثبت شد و رزرو فعلی بدون تغییر باقی ماند.')).toBeVisible();
});
