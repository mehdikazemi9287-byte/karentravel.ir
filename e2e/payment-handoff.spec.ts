import { expect, test } from '@playwright/test';

// Mock contract tests: no real authentication, payment or provider request.
for (const redirect of ['https://payment.example.test/mock', 'http://payment.example.test/mock', 'javascript:alert(1)', 'invalid', undefined]) {
  test(`payment handoff validates backend redirect: ${redirect ?? 'missing'}`, async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem('karenseir-auth-session', JSON.stringify({
      access_token: 'mock-token', refresh_token: 'mock-refresh', token_type: 'bearer',
    })));
    await page.route('**/me/**', route => route.fulfill({ json: [] }));
    await page.route('**/reservations/mock-reservation/checkout-sessions', route => route.fulfill({ json: {
      id: 'mock-checkout', stage: 'awaiting_payment', payment_intent_id: 'mock-payment', state: {},
      reservation: { id: 'mock-reservation', service_type: 'Mock', price_snapshot: { total_amount: 1000 } },
    } }));
    await page.route('**/payments/mock-payment/initiate', route => route.fulfill({ json: { redirect_url: redirect } }));
    await page.route('https://payment.example.test/**', route => route.fulfill({ contentType: 'text/html', body: '<h1>Mock payment destination</h1>' }));
    await page.goto('/checkout/mock-reservation');
    await page.getByRole('button', { name: 'شروع یا ادامهٔ رزرو' }).click();
    await page.getByRole('button', { name: 'ادامه در درگاه پرداخت' }).click();
    if (redirect?.startsWith('https:')) {
      await expect(page).toHaveURL(redirect);
      await expect(page.getByRole('heading', { name: 'Mock payment destination' })).toBeVisible();
    } else {
      // Non-https, script or malformed redirects are refused; a missing one is reported as unavailable.
      await expect(page.getByRole('status')).toHaveText(redirect === undefined ? /درگاه پرداخت در دسترس نیست/ : /اتصال به درگاه انجام نشد/);
      await expect(page).toHaveURL(/\/checkout\/mock-reservation$/);
    }
  });
}
