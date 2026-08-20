import { expect, test, type APIRequestContext } from '@playwright/test';

const api = 'http://127.0.0.1:8100';

async function login(request: APIRequestContext, email: string) {
  const response = await request.post(`${api}/auth/dev-login`, { data: { email } });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function uiLogin(page: import('@playwright/test').Page, email: string) {
  await page.goto('/pilot');
  await page.getByLabel('حساب آزمایشی توسعه').selectOption({ label: email });
  await page.getByRole('button', { name: 'ورود و دریافت هتل‌ها' }).click();
  await expect(page.getByText(/خوش آمدید/)).toBeVisible();
}

async function createOperationalFixture(request: APIRequestContext, suffix = 'manage') {
  const supplier = await login(request, 'supplier@aftab.test');
  const onboarded = await request.post(`${api}/supplier/onboarding`, { headers: { Authorization: `Bearer ${supplier.access_token}`, 'Idempotency-Key': `e2e-supplier-${suffix}` }, data: { supplier_type: 'hotel', display_name: `تأمین‌کننده E2E ${suffix}` } });
  expect(onboarded.status()).toBe(201);
  const supplierId = (await onboarded.json()).id;
  const policy = { verified: true, source: 'e2e-contract', verified_at: new Date().toISOString(), cancellation: { refundable: true, penalty_amount: 100000 } };
  const offerIds: string[] = [];
  for (const [index, amount] of [[0, 2_000_000], [1, 2_400_000]]) {
    const response = await request.post(`${api}/supplier/offers`, { headers: { Authorization: `Bearer ${supplier.access_token}` }, data: { supplier_id: supplierId, service_type: 'hotel', title: `هتل عملیاتی ${index + 1}`, amount, available_units: 5, valid_minutes: 60, policy, attributes: { rating: 4.5 - index * .2, location_score: 8 - index, amenities: ['wifi'], organization_policy_compliant: true }, fulfillment_mode: 'manual_supplier', provider_key: 'manual_supplier' } });
    expect(response.status()).toBe(201); offerIds.push((await response.json()).id);
  }
  const employee = await login(request, 'employee@aftab.test');
  const check = await request.post(`${api}/offers/${offerIds[0]}/price-check`, { headers: { Authorization: `Bearer ${employee.access_token}` }, data: { units: 1, command_id: `e2e-price-${suffix}` } });
  const booking = await request.post(`${api}/orchestration/bookings`, { headers: { Authorization: `Bearer ${employee.access_token}` }, data: { price_check_id: (await check.json()).id, command_id: `e2e-booking-${suffix}` } });
  expect(booking.status()).toBe(201);
  return (await booking.json()).id as string;
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

test('connected trips and manage-booking use the authenticated tenant API', async ({ page, request }) => {
  const reservationId = await createOperationalFixture(request);
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'سفرهای من' }).click();
  await expect(page.getByText('رزروهای من')).toBeVisible();
  const manage = page.locator(`a[href="/manage-booking/${reservationId}"]`);
  await expect(manage).toBeVisible();
  await manage.click();
  await expect(page.getByRole('heading', { name: /مدیریت KS-/ })).toBeVisible();
  await page.getByRole('button', { name: 'درخواست کنسلی' }).click();
  await expect(page.getByRole('status')).toContainText('ثبت شد');
});

test('connected comparison is explainable and backend-authoritative', async ({ page, request }) => {
  await createOperationalFixture(request, 'compare');
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'مقایسه', exact: true }).click();
  await expect(page.getByText('هتل عملیاتی 1').first()).toBeVisible();
  await expect(page.getByText(/امتیاز/).first()).toBeVisible();
});

test('connected private pages fail closed without a browser session', async ({ page }) => {
  await page.goto('/trips');
  await expect(page.getByText('برای مشاهده این بخش وارد شوید.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'ورود امن' })).toBeVisible();
});

test('organization and role panels enforce frontend RBAC states', async ({ page }) => {
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'سازمان', exact: true }).click();
  await expect(page.getByText('نقش شما به این بخش دسترسی ندارد.')).toBeVisible();
  await page.goBack();
  await page.getByLabel('حساب آزمایشی توسعه').selectOption({ label: 'org-admin@aftab.test' });
  await page.getByRole('button', { name: 'ورود و دریافت هتل‌ها' }).click();
  await page.getByRole('link', { name: 'سازمان', exact: true }).click();
  await expect(page.getByText('ساختار سازمانی')).toBeVisible();
});

test('supplier, agency and backoffice panels read only authorized APIs', async ({ page }) => {
  for (const [email, link, heading] of [['supplier@aftab.test','تأمین‌کننده','پنل تأمین‌کننده'],['agency@aftab.test','آژانس','پنل آژانس'],['backoffice@aftab.test','عملیات','BackOffice / Admin']] as const) {
    await uiLogin(page, email);
    await page.getByRole('link', { name: link, exact: true }).click();
    await expect(page.getByRole('heading', { name: heading })).toBeVisible();
  }
});

test('customer account connects profile, travellers, wallet, payment and notification preferences', async ({ page, request }) => {
  await createOperationalFixture(request, 'account');
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'سفرهای من' }).click();
  await page.getByRole('link', { name: 'حساب من' }).click();
  await expect(page.getByRole('heading', { name: 'پروفایل، مسافران و امور مالی' })).toBeVisible();
  await page.getByLabel('نام مسافر').fill('مسافر E2E');
  await page.getByRole('button', { name: 'افزودن' }).click();
  await expect(page.getByRole('status')).toContainText('مسافر افزوده شد');
  if (await page.getByRole('button', { name: 'ایجاد کیف پول ریالی' }).isVisible()) {
    await page.getByRole('button', { name: 'ایجاد کیف پول ریالی' }).click();
    await expect(page.getByRole('status')).toContainText('کیف پول ایجاد شد');
  }
  const paymentButton = page.getByRole('button', { name: /ساخت پرداخت برای/ }).first();
  if (await paymentButton.isVisible()) {
    await paymentButton.click();
    await expect(page.getByRole('status')).toContainText('Payment Intent ایجاد شد');
  }
  const gateway = page.getByRole('button', { name: 'اتصال به درگاه' }).first();
  await expect(gateway).toBeVisible();
  await gateway.click();
  await expect(page.getByRole('status')).toContainText('درگاه پرداخت معتبر در دسترس نیست');
  const smsPreference = page.getByRole('switch', { name: /تغییرات سفر · sms/ });
  await smsPreference.focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('status')).toContainText('ترجیحات اعلان ذخیره شد');
});

test('supplier, agency and backoffice mutations remain role-scoped', async ({ page, request }) => {
  await createOperationalFixture(request, 'panel-mutations');
  await uiLogin(page, 'supplier@aftab.test');
  await page.getByRole('link', { name: 'تأمین‌کننده', exact: true }).click();
  await page.getByLabel('نام تأمین‌کننده').fill('تأمین‌کننده UI');
  await page.getByRole('button', { name: 'ثبت' }).click();
  await expect(page.getByRole('status')).toContainText('تأمین‌کننده ثبت شد');
  await uiLogin(page, 'agency@aftab.test');
  await page.getByRole('link', { name: 'آژانس', exact: true }).click();
  await page.getByLabel('نام زیرآژانس').fill('زیرآژانس UI');
  await page.getByRole('button', { name: 'ثبت' }).click();
  await expect(page.getByRole('status')).toContainText('زیرآژانس ثبت شد');
  await uiLogin(page, 'backoffice@aftab.test');
  await page.getByRole('link', { name: 'عملیات', exact: true }).click();
  const statusMutation = page.getByRole('button', { name: /تعلیق|فعال‌سازی/ }).first();
  await expect(statusMutation).toBeVisible();
  await statusMutation.click();
  await expect(page.getByText('وضعیت تأمین‌کننده ثبت شد.', { exact: true })).toBeVisible();
});

test('support case thread keeps customer and human-agent messages distinct', async ({ page, request }) => {
  const reservationId = await createOperationalFixture(request, 'support-thread');
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'سفرهای من' }).click();
  await page.locator(`a[href="/manage-booking/${reservationId}"]`).click();
  await page.getByRole('link', { name: 'گفت‌وگو با پشتیبانی انسانی' }).click();
  await page.getByLabel('شرح درخواست').fill('واچر این رزرو نیاز به بررسی انسانی دارد');
  await page.getByRole('button', { name: 'ایجاد پرونده انسانی' }).click();
  await expect(page.getByRole('status')).toContainText('پرونده پشتیبانی انسانی ثبت شد');
  await expect(page.getByText('مشتری', { exact: true })).toBeVisible();

  await uiLogin(page, 'backoffice@aftab.test');
  await page.getByRole('link', { name: 'عملیات', exact: true }).click();
  await page.getByLabel('پرونده پشتیبانی').selectOption({ index: 1 });
  await page.getByLabel('پیام کارشناس انسانی').fill('کارشناس انسانی واچر را بررسی کرد');
  await page.getByRole('button', { name: 'ارسال با برچسب کارشناس انسانی' }).click();
  await expect(page.getByRole('status')).toContainText('پاسخ کارشناس انسانی ثبت شد');
});

test('finance workspace fails closed for customers and opens for finance role', async ({ page }) => {
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'سفرهای من' }).click();
  await page.getByRole('link', { name: 'مالی', exact: true }).click();
  await expect(page.getByText('نقش شما به این بخش دسترسی ندارد.')).toBeVisible();

  await uiLogin(page, 'finance@aftab.test');
  await page.getByRole('link', { name: 'عملیات', exact: true }).click();
  await page.getByRole('link', { name: 'مالی', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'پرداخت، کیف پول، اقساط و تسویه' })).toBeVisible();
});
