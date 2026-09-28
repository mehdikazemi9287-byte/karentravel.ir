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
    await page.getByRole('button', { name: 'شروع و ذخیره Checkout' }).click();
    await page.getByRole('button', { name: 'اتصال به درگاه معتبر' }).click();
    if (redirect?.startsWith('https:')) {
      await expect(page).toHaveURL(redirect);
      await expect(page.getByRole('heading', { name: 'Mock payment destination' })).toBeVisible();
    } else {
      await expect(page.getByRole('status')).not.toHaveText('Checkout ذخیره شد و قابل resume است.');
      await expect(page).toHaveURL(/\/checkout\/mock-reservation$/);
    }
  });
}
