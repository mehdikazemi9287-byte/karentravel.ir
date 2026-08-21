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

async function createOperationalFixture(request: APIRequestContext, suffix = 'manage', serviceType = 'hotel') {
  const supplier = await login(request, 'supplier@aftab.test');
  const onboarded = await request.post(`${api}/supplier/onboarding`, { headers: { Authorization: `Bearer ${supplier.access_token}`, 'Idempotency-Key': `e2e-supplier-${suffix}` }, data: { supplier_type: 'hotel', display_name: `تأمین‌کننده E2E ${suffix}` } });
  expect(onboarded.status()).toBe(201);
  const supplierId = (await onboarded.json()).id;
  const policy = { verified: true, source: 'e2e-contract', verified_at: new Date().toISOString(), cancellation: { refundable: true, penalty_amount: 100000 } };
  const offerIds: string[] = [];
  for (const [index, amount] of [[0, 2_000_000], [1, 2_400_000]]) {
    const response = await request.post(`${api}/supplier/offers`, { headers: { Authorization: `Bearer ${supplier.access_token}` }, data: { supplier_id: supplierId, service_type: serviceType, title: serviceType === 'flight' ? `پرواز تهران شیراز ${index + 1}` : `هتل عملیاتی ${index + 1}`, amount, available_units: 5, valid_minutes: 60, policy, attributes: serviceType === 'flight' ? { rating: 4.5 - index * .2, origin: 'تهران', destination: 'شیراز', airline: 'هواپیمایی تست قراردادی', departure_time: '08:30', arrival_time: index ? '10:15' : '10:00', duration: index ? '۱ ساعت و ۴۵ دقیقه' : '۱ ساعت و ۳۰ دقیقه', duration_minutes: index ? 105 : 90, stops: 0, baggage: '۲۰ کیلوگرم', organization_policy_compliant: true } : { rating: 4.5 - index * .2, stars: 4, location_score: 8 - index, city: 'شیراز', room_type: 'دوتخته', breakfast: true, amenities: ['wifi'], organization_policy_compliant: true }, fulfillment_mode: 'manual_supplier', provider_key: 'manual_supplier' } });
    expect(response.status()).toBe(201); offerIds.push((await response.json()).id);
  }
  const employee = await login(request, 'employee@aftab.test');
  const check = await request.post(`${api}/offers/${offerIds[0]}/price-check`, { headers: { Authorization: `Bearer ${employee.access_token}` }, data: { units: 1, command_id: `e2e-price-${suffix}` } });
  const booking = await request.post(`${api}/orchestration/bookings`, { headers: { Authorization: `Bearer ${employee.access_token}` }, data: { price_check_id: (await check.json()).id, command_id: `e2e-booking-${suffix}` } });
  expect(booking.status()).toBe(201);
  return (await booking.json()).id as string;
}

test('frozen Homepage keeps approved structure on desktop and mobile', async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    await expect(page.getByRole('banner')).toBeVisible();
    await expect(page.getByRole('heading', { level: 1 })).toContainText('سفر را');
    await expect(page.getByRole('tab', { name: 'پرواز', exact: true })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'هتل', exact: true })).toBeVisible();
    await expect(page.getByText('دستیار هوشمند سفر کارن‌سیر')).toBeVisible();
    await expect(page.getByText('قبل از انتخاب، کنار هم ببین.')).toBeVisible();
    await expect(page.locator('.ref-footer')).toHaveCount(1);
    const screenshot = await page.screenshot({ fullPage: true, animations: 'disabled' });
    expect(screenshot.byteLength).toBeGreaterThan(100_000);
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  }
});

test('login and booking flow through the pilot UI', async ({ page }) => {
  const response = await page.goto('/pilot');
  expect(response?.headers()['content-security-policy']).toContain("frame-ancestors 'none'");
  await expect(page.getByRole('heading', { name: 'رزرو هتل با جریان سازمانی' })).toBeVisible();
  await page.getByRole('button', { name: 'ورود و دریافت هتل‌ها' }).click();
  await expect(page.getByText(/خوش آمدید/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'هتل پارسیان آزادی' })).toBeVisible();
  await page.getByRole('button', { name: 'درخواست ۲ شب' }).first().click();
  await expect(page.getByText(/در انتظار تأیید است/)).toBeVisible();

});

test('professional Homepage search interactions reach usable results', async ({ page, request }) => {
  test.setTimeout(60_000);
  await createOperationalFixture(request, 'search-ux', 'flight');
  await uiLogin(page, 'employee@aftab.test');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.getByRole('region', { name: 'جست‌وجوی یکپارچه سفر' })).not.toContainText(/Mock|نتایج Mock|نمایش آزمایشی/);
  await page.screenshot({ path: 'artifacts/search-ux/homepage-search-desktop.png', fullPage: true, animations: 'disabled' });

  const origin = page.getByRole('combobox', { name: 'مبدأ' });
  await origin.fill('تهرون');
  await expect(page.getByRole('option', { name: /^تهران/ })).toBeVisible();
  await origin.fill('تهر');
  await expect(page.getByRole('listbox', { name: 'پیشنهادهای مبدأ' })).toBeVisible();
  await expect(page.getByRole('option', { name: /فرودگاه مهرآباد/ })).toBeVisible();
  await page.screenshot({ path: 'artifacts/search-ux/homepage-autocomplete.png', animations: 'disabled' });
  await page.getByRole('option', { name: /^تهران/ }).click();
  const destination = page.getByRole('combobox', { name: 'مقصد' });
  await destination.fill('شیرا');
  await expect(page.getByRole('listbox', { name: 'پیشنهادهای مقصد' })).toBeVisible();
  await expect(page.getByRole('option', { name: /^شیراز/ })).toBeVisible();
  await page.screenshot({ path: 'artifacts/search-ux/destination-autocomplete.png', animations: 'disabled' });
  await page.getByRole('option', { name: /^شیراز/ }).click();

  await page.getByRole('button', { name: /تاریخ سفر/ }).click();
  await page.getByLabel('تاریخ رفت').fill('2026-09-21');
  await page.getByLabel('تاریخ برگشت').fill('2026-09-24');
  await page.getByRole('button', { name: '±۱ روز' }).click();
  await page.screenshot({ path: 'artifacts/search-ux/date-picker.png', animations: 'disabled' });
  await page.getByRole('button', { name: 'تأیید تاریخ' }).click();

  await page.getByRole('button', { name: /مسافران/ }).click();
  await page.getByRole('button', { name: 'افزایش بزرگسال' }).click();
  await expect(page.getByText('۳', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'artifacts/search-ux/passenger-picker.png', animations: 'disabled' });
  await page.getByRole('button', { name: 'تأیید مسافران' }).click();
  await page.getByRole('button', { name: 'یک‌طرفه' }).click();
  await expect(page.getByRole('button', { name: 'یک‌طرفه' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'رفت‌وبرگشت' }).click();
  await page.getByRole('button', { name: 'جست‌وجو', exact: true }).click();
  await expect(page).toHaveURL(/\/search\/results\?.*vertical=flight/);
  await expect(page.getByRole('heading', { name: /پرواز تهران شیراز/ }).first()).toBeVisible();
  const resultsUrl = page.url();
  await page.screenshot({ path: 'artifacts/search-ux/search-results-desktop.png', fullPage: true, animations: 'disabled' });

  await page.getByLabel('مرتب‌سازی نتایج').selectOption('lowest_price');
  await page.getByRole('checkbox', { name: 'فقط قابل استرداد' }).check();
  await page.getByRole('button', { name: 'اعمال فیلتر' }).click();
  await page.screenshot({ path: 'artifacts/search-ux/filter-panel.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: '♡ علاقه‌مندی' }).first().click();
  await expect(page.getByRole('status')).toContainText('در علاقه‌مندی ذخیره شد');
  await page.getByRole('button', { name: '+ افزودن به سفر' }).first().click();
  await expect(page.getByRole('status')).toContainText('به سبد سفر افزوده شد');
  await page.getByRole('button', { name: 'بررسی قیمت و موجودی' }).first().click();
  await expect(page.getByText('قیمت و موجودی همین لحظه تأیید شد.')).toBeVisible();
  const compare = page.getByRole('checkbox', { name: /برای مقایسه/ });
  await compare.nth(0).check(); await compare.nth(1).check();
  await page.getByRole('link', { name: 'مقایسه گزینه‌ها' }).click();
  await expect(page).toHaveURL(/\/compare\?type=flight&offers=/);
  await expect(page.getByRole('heading', { name: 'تفاوت‌ها را یک‌جا ببینید.' })).toBeVisible();
  await expect(page.locator('.compare-wrap article')).toHaveCount(2);
  await page.screenshot({ path: 'artifacts/search-ux/comparison.png', fullPage: true, animations: 'disabled' });
  await page.goto(resultsUrl);
  await expect(page.getByRole('heading', { name: /پرواز تهران شیراز/ }).first()).toBeVisible();
  await page.getByRole('button', { name: 'ویرایش جست‌وجو' }).click();
  await expect(page.getByLabel('ویرایش مقصد')).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: 'artifacts/search-ux/search-results-mobile.png', fullPage: true, animations: 'disabled' });
});

test('travel commerce rental, tour, visa and cruise states are usable and honest', async ({ page, request }) => {
  test.setTimeout(60_000);
  const suffix = Date.now().toString();
  const supplierUser = await login(request, 'supplier@aftab.test');
  const supplierResponse = await request.post(`${api}/supplier/onboarding`, { headers: { Authorization: `Bearer ${supplierUser.access_token}`, 'Idempotency-Key': `commerce-supplier-${suffix}` }, data: { supplier_type: 'multi_service', display_name: 'تأمین‌کننده Travel Commerce E2E' } });
  const supplierId = (await supplierResponse.json()).id;
  const propertyResponse = await request.post(`${api}/supplier/vacation-properties`, { headers: { Authorization: `Bearer ${supplierUser.access_token}` }, data: { supplier_id: supplierId, title: 'ویلای ساحلی تست مرورگر', slug: `e2e-villa-${suffix}`, city: 'رامسر', property_type: 'villa', capacity: 6, bedrooms: 2, details: { amenities: ['استخر', 'پارکینگ'], cancellation: 'نیازمند recheck' } } });
  expect(propertyResponse.status()).toBe(201); const propertyId = (await propertyResponse.json()).id;
  const unitResponse = await request.post(`${api}/supplier/vacation-properties/${propertyId}/units`, { headers: { Authorization: `Bearer ${supplierUser.access_token}` }, data: { title: 'واحد دربست', capacity: 6, available_units: 1, nightly_price: 9000000 } });
  expect(unitResponse.status()).toBe(201);
  const tourResponse = await request.post(`${api}/supplier/tours`, { headers: { Authorization: `Bearer ${supplierUser.access_token}` }, data: { supplier_id: supplierId, title: 'تور فرهنگی شیراز E2E', slug: `e2e-tour-${suffix}`, origin: 'تهران', destination: 'شیراز', tour_type: 'cultural', details: { visa_status: 'not_required', services: ['هتل', 'راهنما', 'بیمه'], itinerary: [{ day: 1, title: 'حافظیه' }] } } });
  expect(tourResponse.status()).toBe(201); const tourId = (await tourResponse.json()).id;
  const departureResponse = await request.post(`${api}/supplier/tours/${tourId}/departures`, { headers: { Authorization: `Bearer ${supplierUser.access_token}` }, data: { starts_at: '2030-06-10T06:00:00Z', ends_at: '2030-06-13T18:00:00Z', booking_deadline: '2030-06-08T18:00:00Z', capacity: 12, base_price: 15000000, pricing: { single_surcharge: 3000000 } } });
  expect(departureResponse.status()).toBe(201);
  const backoffice = await login(request, 'backoffice@aftab.test');
  const visaResponse = await request.post(`${api}/backoffice/visa-products`, { headers: { Authorization: `Bearer ${backoffice.access_token}` }, data: { destination_country: 'فرانسه', visa_type: 'tourist', title: 'ویزای توریستی فرانسه E2E', source_url: 'https://france-visas.gouv.fr/en/web/france-visas/visa-application-guidelines', source_verified_at: new Date().toISOString(), details: { documents: ['گذرنامه', 'عکس', 'بیمه'], processing_time: 'تضمین‌نشده' } } });
  expect(visaResponse.status()).toBe(201); const visaId = (await visaResponse.json()).id;
  const employee = await login(request, 'employee@aftab.test');
  const visaApplicationResponse = await request.post(`${api}/visa-products/${visaId}/applications`, { headers: { Authorization: `Bearer ${employee.access_token}` }, data: { purpose: 'tourism', travel_at: '2030-09-01T00:00:00Z', command_id: `visa-case-${suffix}` } });
  expect(visaApplicationResponse.status()).toBe(201); const visaApplicationId = (await visaApplicationResponse.json()).id;

  await uiLogin(page, 'employee@aftab.test');
  await page.goto('/villas'); await expect(page.getByText('ویلای ساحلی تست مرورگر')).toBeVisible(); await page.screenshot({ path: 'artifacts/travel-commerce/villa-results.png', fullPage: true, animations: 'disabled' });
  await page.getByText('ویلای ساحلی تست مرورگر').click(); await expect(page.getByText('واحد دربست')).toBeVisible(); await page.screenshot({ path: 'artifacts/travel-commerce/villa-detail.png', fullPage: true, animations: 'disabled' });
  await page.goto('/tours'); await expect(page.getByText('تور فرهنگی شیراز E2E')).toBeVisible(); await page.screenshot({ path: 'artifacts/travel-commerce/tour-results.png', fullPage: true, animations: 'disabled' });
  await page.getByText('تور فرهنگی شیراز E2E').click(); await expect(page.getByRole('button', { name: 'بررسی ظرفیت و قیمت' })).toBeVisible(); await page.screenshot({ path: 'artifacts/travel-commerce/tour-detail.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'بررسی ظرفیت و قیمت' }).click(); await expect(page.getByRole('status')).toContainText('واچر فقط پس از پرداخت'); await page.screenshot({ path: 'artifacts/travel-commerce/tour-booking.png', fullPage: true, animations: 'disabled' });
  await page.goto(`/visa/${visaId}`); await expect(page.getByText('صدور، eligibility یا زمان پردازش را تضمین نمی‌کند')).toBeVisible(); await page.screenshot({ path: 'artifacts/travel-commerce/visa-detail.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'شروع درخواست و بررسی انسانی' }).click(); await expect(page.getByRole('status')).toContainText('صدور تضمین نمی‌شود'); await page.screenshot({ path: 'artifacts/travel-commerce/visa-application.png', fullPage: true, animations: 'disabled' });
  await page.goto(`/visa/applications/${visaApplicationId}`); await expect(page.getByRole('heading', { name: 'پرونده ویزا' })).toBeVisible(); await page.getByLabel('نام متقاضی ویزا').fill('مسافر مرورگر'); await page.getByLabel('شماره گذرنامه').fill('P123456789'); await page.getByRole('button', { name: 'افزودن متقاضی' }).click(); await page.getByRole('button', { name: 'ثبت بارگذاری گذرنامه' }).click(); await expect(page.getByText(/passport ·/)).toContainText('uploaded'); await page.screenshot({ path: 'artifacts/travel-commerce/visa-timeline.png', fullPage: true, animations: 'disabled' });
  await page.goto('/cruises'); await expect(page.getByText('رزرو زنده کروز: مسدود تا اتصال Provider قراردادی')).toBeVisible(); await page.screenshot({ path: 'artifacts/travel-commerce/cruise-state.png', fullPage: true, animations: 'disabled' });
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

test('unified search results expose freshness and persist saved search', async ({ page, request }) => {
  await createOperationalFixture(request, 'unified-search');
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'جست‌وجوی یکپارچه' }).click();
  await page.getByLabel('عبارت جست‌وجو').fill('هتل عملیاتی');
  await page.getByRole('button', { name: 'جست‌وجو', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'هتل عملیاتی 1' }).first()).toBeVisible();
  await expect(page.getByText('زنده و تازه', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('موجودی تأییدشده', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'ذخیره جست‌وجو' }).click();
  await expect(page.getByText('جست‌وجو در حساب شما ذخیره شد.')).toBeVisible();
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

test('saved travel, itinerary, destination and map fallback use tenant APIs', async ({ page, request }) => {
  const suffix = Date.now().toString();
  const backoffice = await login(request, 'backoffice@aftab.test');
  const destination = await request.post(`${api}/destinations`, { headers: { Authorization: `Bearer ${backoffice.access_token}` }, data: { kind: 'city', name_fa: 'شیراز E2E', name_en: 'Shiraz', slug: `shiraz-e2e-${suffix}`, latitude: 29.59, longitude: 52.58, description: 'مقصد تست عملیاتی', seasonality: ['spring'], categories: ['historical'], highlights: ['حافظیه'], nearby_slugs: [] } });
  expect(destination.status()).toBe(201);
  await uiLogin(page, 'employee@aftab.test');
  await page.goto('/saved-trips');
  await page.getByLabel('عنوان سفر').fill(`سفر E2E ${suffix}`);
  await page.getByRole('button', { name: 'ساخت سفر ذخیره‌شده' }).click();
  await expect(page.getByText('سفر ذخیره شد.', { exact: true })).toBeVisible();
  const savedTripCard = page.locator('section').filter({ hasText: `سفر E2E ${suffix}` }).last();
  await page.getByLabel(`مرجع آیتم سفر E2E ${suffix}`).fill('attraction:hafezieh');
  await savedTripCard.getByRole('button', { name: 'ذخیره در علاقه‌مندی' }).click();
  await expect(page.getByText(/علاقه‌مندی/, { exact: false }).first()).toBeVisible();
  await savedTripCard.getByRole('button', { name: 'انتقال' }).click();
  await expect(page.getByText(/سبد سفر/, { exact: false }).first()).toBeVisible();
  await page.goto('/itineraries');
  await page.getByLabel('عنوان برنامه سفر').fill(`برنامه E2E ${suffix}`);
  await page.getByRole('button', { name: 'ساخت برنامه' }).click();
  await expect(page.getByRole('status')).toContainText('قابل‌ویرایش ساخته شد');
  await page.getByRole('button', { name: 'افزودن آیتم' }).click();
  await expect(page.getByText('نیازمند بررسی زنده موجودی')).toBeVisible();
  await page.goto('/destinations');
  await page.getByRole('link', { name: /شیراز E2E/ }).click();
  await expect(page.getByText('Offer تازه‌ای برای این مقصد موجود نیست')).toBeVisible();
  await page.goto('/map');
  await expect(page.getByText('در نبود credential نقشه')).toBeVisible();
});
