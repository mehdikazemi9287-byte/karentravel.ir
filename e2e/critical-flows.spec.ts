import { expect, test, type APIRequestContext } from '@playwright/test';

const api = process.env.E2E_API_URL || 'http://127.0.0.1:8100';
const artifactDir = process.env.E2E_ARTIFACT_DIR || 'artifacts';

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
  suffix += '-' + Date.now();
  const supplier = await login(request, 'supplier@aftab.test');
  const onboarded = await request.post(`${api}/supplier/onboarding`, { headers: { Authorization: `Bearer ${supplier.access_token}`, 'Idempotency-Key': `e2e-supplier-${suffix}` }, data: { supplier_type: 'hotel', display_name: `تأمین‌کننده E2E ${suffix}` } });
  expect(onboarded.status()).toBe(201);
  const supplierId = (await onboarded.json()).id;
  const policy = { verified: true, source: 'e2e-contract', verified_at: new Date().toISOString(), cancellation: { refundable: true, penalty_amount: 100000 } };
  // Hotel offers must carry a dated, occupancy-specific room rate and the price check must
  // select the matching stay (fixed-stay allotment integrity, backend/app/hotel_stay.py).
  const hotelRate = { check_in: '2030-03-01', check_out: '2030-03-03', room_type: 'دوتخته', rate_plan: 'با صبحانه', price_basis: 'room_stay', occupancy: { adults: 2, children_ages: [] } };
  const hotelStay = { check_in: hotelRate.check_in, check_out: hotelRate.check_out, rooms: [hotelRate.occupancy] };
  const offerIds: string[] = [];
  for (const [index, amount] of [[0, 2_000_000], [1, 2_400_000]]) {
    const response = await request.post(`${api}/supplier/offers`, { headers: { Authorization: `Bearer ${supplier.access_token}` }, data: { supplier_id: supplierId, service_type: serviceType, title: serviceType === 'flight' ? `پرواز تهران شیراز ${index + 1}` : `هتل عملیاتی ${index + 1}`, amount, available_units: 5, valid_minutes: 60, policy, attributes: serviceType === 'flight' ? { rating: 4.5 - index * .2, origin: 'تهران', destination: 'شیراز', airline: 'هواپیمایی تست قراردادی', departure_time: '08:30', arrival_time: index ? '10:15' : '10:00', duration: index ? '۱ ساعت و ۴۵ دقیقه' : '۱ ساعت و ۳۰ دقیقه', duration_minutes: index ? 105 : 90, stops: 0, baggage: '۲۰ کیلوگرم', organization_policy_compliant: true } : { rating: 4.5 - index * .2, stars: 4, location_score: 8 - index, city: 'شیراز', room_type: 'دوتخته', breakfast: true, amenities: ['wifi'], organization_policy_compliant: true, hotel_rate: hotelRate }, fulfillment_mode: 'manual_supplier', provider_key: 'manual_supplier' } });
    expect(response.status()).toBe(201); offerIds.push((await response.json()).id);
  }
  const employee = await login(request, 'employee@aftab.test');
  const check = await request.post(`${api}/offers/${offerIds[0]}/price-check`, { headers: { Authorization: `Bearer ${employee.access_token}` }, data: { units: 1, command_id: `e2e-price-${suffix}`, ...(serviceType === 'hotel' ? { hotel_stay: hotelStay } : {}) } });
  expect(check.status()).toBe(201);
  const booking = await request.post(`${api}/orchestration/bookings`, { headers: { Authorization: `Bearer ${employee.access_token}` }, data: { price_check_id: (await check.json()).id, command_id: `e2e-booking-${suffix}` } });
  expect(booking.status()).toBe(201);
  return (await booking.json()).id as string;
}

test('frozen Homepage keeps approved structure on desktop and mobile', async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    // Approved reference homepage (Figma node 45:3 header + D13 support phone, owner-approved 1405-08-18).
    await expect(page.getByRole('link', { name: 'کارن تراول، صفحه اصلی' }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: /تماس با پشتیبانی/ }).first()).toBeVisible();
    await expect(page.getByRole('heading', { level: 1 })).toContainText('سفر را');
    const search = page.getByRole('region', { name: 'جست‌وجوی یکپارچه سفر' });
    for (const name of ['پرواز', 'هتل', 'قطار', 'تور']) await expect(search.getByRole('tab', { name, exact: true })).toBeVisible();
    await expect(search.getByRole('radiogroup', { name: 'نوع سفر' }).getByRole('radio', { name: 'رفت‌وبرگشت' })).toBeChecked();
    await expect(search.getByRole('button', { name: 'پیدا کن', exact: true })).toBeVisible();
    for (const name of ['کجای ایران صدایت می‌زند؟', 'همه‌ی سفر، در یک جا', 'سفر سازمانی، بدون پیچیدگی']) await expect(page.getByRole('heading', { level: 2, name })).toBeVisible();
    await expect(page.getByRole('contentinfo')).toHaveCount(1);
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
  await page.screenshot({ path: `${artifactDir}/search-ux/homepage-search-desktop.png`, fullPage: true, animations: 'disabled' });
  // The approved homepage shows the four primary services as tabs (flight, hotel, train, tour).
  for (const name of ['هتل', 'قطار', 'تور']) {
    await page.getByRole('tab', { name, exact: true }).click();
    await expect(page.getByRole('tabpanel', { name: `فرم جست‌وجوی ${name}` })).toBeVisible();
  }
  await page.screenshot({ path: `${artifactDir}/search-ux/tour-search-state.png`, animations: 'disabled' });
  await page.getByRole('tab', { name: 'پرواز', exact: true }).click();

  const origin = page.getByRole('combobox', { name: 'مبدأ', exact: true });
  await origin.fill('تهرون');
  await expect(page.getByRole('option', { name: /^تهران/ }).first()).toBeVisible();
  await origin.fill('تهر');
  await expect(page.getByRole('listbox', { name: 'پیشنهادهای مبدأ' })).toBeVisible();
  await expect(page.getByRole('option', { name: /فرودگاه مهرآباد/ })).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/search-ux/homepage-autocomplete.png`, animations: 'disabled' });
  await page.getByRole('option', { name: /^تهران/ }).first().click();
  const destination = page.getByRole('combobox', { name: 'مقصد', exact: true });
  await destination.fill('شیرا');
  await expect(page.getByRole('listbox', { name: 'پیشنهادهای مقصد' })).toBeVisible();
  await expect(page.getByRole('option', { name: /^شیراز/ }).first()).toBeVisible();
  await page.screenshot({ path: `${artifactDir}/search-ux/destination-autocomplete.png`, animations: 'disabled' });
  await page.getByRole('option', { name: /^شیراز/ }).first().click();

  // Trip type lives outside the calendar (owner-approved D11); round trip stays the default.
  const tripType = page.getByRole('radiogroup', { name: 'نوع سفر' });
  await expect(tripType.getByRole('radio', { name: 'رفت‌وبرگشت' })).toBeChecked();
  await page.getByRole('button', { name: 'تاریخ سفر', exact: true }).click();
  await page.getByRole('button', { name: 'ماه بعد', exact: true }).click();
  await page.getByRole('button', { name: /^انتخاب ۱۰ / }).first().click();
  await page.getByRole('button', { name: /^انتخاب ۱۲ / }).first().click();
  await page.getByRole('button', { name: '±۱ روز' }).click();
  await expect(page.getByRole('button', { name: '±۱ روز' })).toHaveAttribute('aria-pressed', 'true');
  await page.screenshot({ path: `${artifactDir}/search-ux/date-picker.png`, animations: 'disabled' });
  await page.getByRole('button', { name: 'تأیید تاریخ' }).click();

  await page.getByRole('button', { name: /^مسافران/ }).click();
  await page.getByRole('button', { name: 'افزایش بزرگسال' }).click();
  await expect(page.getByRole('button', { name: 'کاهش بزرگسال' })).toBeEnabled();
  await page.screenshot({ path: `${artifactDir}/search-ux/passenger-picker.png`, animations: 'disabled' });
  await page.getByRole('button', { name: 'تأیید مسافران' }).click();
  await expect(page.getByRole('button', { name: /^مسافران ۲ مسافر/ })).toBeVisible();
  await tripType.getByRole('radio', { name: 'رفت‌وبرگشت' }).click();
  await expect(tripType.getByRole('radio', { name: 'رفت‌وبرگشت' })).toBeChecked();
  // The fixture offers are one-way flights; a round-trip search may not price-check them.
  await tripType.getByRole('radio', { name: 'یک‌طرفه' }).click();
  await expect(tripType.getByRole('radio', { name: 'یک‌طرفه' })).toBeChecked();
  await page.getByRole('button', { name: 'پیدا کن', exact: true }).click();
  await expect(page).toHaveURL(/\/search\/results\?.*vertical=flight/);
  await expect(page).toHaveURL(/trip_type=one_way/);
  await expect(page.getByRole('heading', { name: /پرواز تهران شیراز/ }).first()).toBeVisible();
  const resultsUrl = page.url();
  await page.screenshot({ path: `${artifactDir}/search-ux/search-results-desktop.png`, fullPage: true, animations: 'disabled' });

  await page.getByLabel('مرتب‌سازی نتایج').selectOption('cheapest');
  await page.getByRole('checkbox', { name: 'فقط قابل استرداد' }).check();
  await page.getByRole('button', { name: 'اعمال فیلتر' }).click();
  await page.screenshot({ path: `${artifactDir}/search-ux/filter-panel.png`, fullPage: true, animations: 'disabled' });
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
  await page.screenshot({ path: `${artifactDir}/search-ux/comparison.png`, fullPage: true, animations: 'disabled' });
  await page.goto(resultsUrl);
  await expect(page.getByRole('heading', { name: /پرواز تهران شیراز/ }).first()).toBeVisible();
  await page.getByRole('button', { name: 'ویرایش جست‌وجو' }).click();
  await expect(page.getByLabel('ویرایش مقصد')).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `${artifactDir}/search-ux/search-results-mobile.png`, fullPage: true, animations: 'disabled' });
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
  await page.goto('/villas'); await expect(page.locator(`a[href^="/villas/${propertyId}"]`)).toBeVisible(); await page.screenshot({ path: `${artifactDir}/travel-commerce/villa-results.png`, fullPage: true, animations: 'disabled' });
  await page.locator(`a[href^="/villas/${propertyId}"]`).click(); await expect(page.getByRole('combobox', { name: 'واحد اقامت' })).toContainText('واحد دربست — ظرفیت ۶ نفر'); await page.screenshot({ path: `${artifactDir}/travel-commerce/villa-detail.png`, fullPage: true, animations: 'disabled' });
  await page.goto('/tours'); await expect(page.locator(`a[href^="/tours/${tourId}"]`)).toBeVisible(); await page.screenshot({ path: `${artifactDir}/travel-commerce/tour-results.png`, fullPage: true, animations: 'disabled' });
  await page.locator(`a[href^="/tours/${tourId}"]`).click(); await expect(page.getByRole('combobox', { name: 'حرکت تور' })).toBeVisible(); await page.screenshot({ path: `${artifactDir}/travel-commerce/tour-detail.png`, fullPage: true, animations: 'disabled' });
  // A tour quote needs a departure and a room type the organiser priced (base 15,000,000 + single surcharge 3,000,000).
  await page.getByRole('combobox', { name: 'حرکت تور' }).selectOption({ index: 1 });
  await page.getByRole('combobox', { name: 'نوع اتاق' }).selectOption({ label: 'یک‌نفره' });
  await page.getByRole('button', { name: 'استعلام مبلغ و ظرفیت' }).click();
  await expect(page.getByText('۱۸٬۰۰۰٬۰۰۰ ریال برای ۱ بزرگسال')).toBeVisible();
  await expect(page.getByRole('status')).toContainText('شرایط و مبلغ را پیش از ثبت ظرفیت بررسی کنید'); await page.screenshot({ path: `${artifactDir}/travel-commerce/tour-booking.png`, fullPage: true, animations: 'disabled' });
  // /visa/[id] renders the public visa guides; a customer reaches a visa service from the account's visa page.
  await page.goto('/account/visa'); await page.locator(`a[href="/visa/products/${visaId}"]`).click();
  await expect(page.getByRole('heading', { level: 1, name: 'ویزای توریستی فرانسه E2E' })).toBeVisible(); await expect(page.getByText('صدور، شرایط احراز یا زمان پردازش را تضمین نمی‌کند')).toBeVisible(); await page.screenshot({ path: `${artifactDir}/travel-commerce/visa-detail.png`, fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'شروع درخواست و بررسی انسانی' }).click(); await expect(page.getByRole('status')).toContainText('صدور تضمین نمی‌شود'); await page.screenshot({ path: `${artifactDir}/travel-commerce/visa-application.png`, fullPage: true, animations: 'disabled' });
  await page.goto(`/visa/applications/${visaApplicationId}`); await expect(page.getByRole('heading', { name: 'پرونده ویزا' })).toBeVisible(); await page.getByLabel('نام متقاضی ویزا').fill('مسافر مرورگر'); await page.getByLabel('شماره گذرنامه').fill('P123456789'); await page.getByRole('button', { name: 'افزودن متقاضی' }).click(); await page.getByRole('button', { name: 'ثبت بارگذاری گذرنامه' }).click(); await expect(page.getByText(/passport ·/)).toContainText('uploaded'); await page.screenshot({ path: `${artifactDir}/travel-commerce/visa-timeline.png`, fullPage: true, animations: 'disabled' });
  // No cruise provider is connected: the page only takes a request for a human callback, never a live booking.
  await page.goto('/cruises'); await expect(page.getByRole('heading', { name: 'ثبت درخواست سفر دریایی' })).toBeVisible(); await expect(page.getByRole('button', { name: /رزرو|پرداخت/ })).toHaveCount(0); await page.screenshot({ path: `${artifactDir}/travel-commerce/cruise-state.png`, fullPage: true, animations: 'disabled' });
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

test('cancellation and refund preview remains non-destructive', async ({ page, request }) => {
  // The demo /manage-booking/book1 page is gone; the preview now comes from the backend cancellation quote.
  const reservationId = await createOperationalFixture(request, 'refund-preview');
  await uiLogin(page, 'employee@aftab.test');
  await page.goto(`/manage-booking/${reservationId}`);
  await expect(page.getByRole('heading', { name: 'قوانین و برآورد استرداد' })).toBeVisible();
  await expect(page.getByText('جریمه طبق شرایط: ۱۰۰٬۰۰۰ ریال')).toBeVisible();
  await expect(page.getByText('برآورد قابل استرداد: ۱٬۹۰۰٬۰۰۰ ریال')).toBeVisible();
  await expect(page.getByText('این برآورد به معنی انجام بازپرداخت نیست؛ درخواست باید بررسی شود.')).toBeVisible();
  const employee = await login(request, 'employee@aftab.test');
  const reservation = await request.get(`${api}/reservations/${reservationId}`, { headers: { Authorization: `Bearer ${employee.access_token}` } });
  expect((await reservation.json()).status).toBe('reserved');
});

test('connected trips and manage-booking use the authenticated tenant API', async ({ page, request }) => {
  const reservationId = await createOperationalFixture(request);
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'سفرهای من' }).click();
  await expect(page.getByText('رزروهای من')).toBeVisible();
  const manage = page.locator(`a[href="/manage-booking/${reservationId}"]`).filter({ hasText: 'مدیریت رزرو' });
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
  await expect(page.getByRole('link', { name: 'ورود به حساب' })).toHaveAttribute('href', '/login?redirect=%2Ftrips');
});

test('organization and role panels enforce frontend RBAC states', async ({ page }) => {
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'سازمان', exact: true }).click();
  await expect(page.getByRole('alert').getByRole('heading', { name: 'دسترسی ندارید' })).toBeVisible();
  await expect(page.getByText('این بخش برای نقش «کارمند سازمان» در دسترس نیست.', { exact: false })).toBeVisible();
  await uiLogin(page, 'org-admin@aftab.test');
  await page.getByRole('link', { name: 'سازمان', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'نمای کلی' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'پنل سازمان' }).getByRole('link', { name: 'کارکنان و دسترسی‌ها' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'دسترسی ندارید' })).toHaveCount(0);
});

test('supplier, agency and backoffice panels read only authorized APIs', async ({ page }) => {
  // Each role lands in its own panel shell; the panel navigation is named after the role's area.
  for (const [email, link, panel] of [['supplier@aftab.test','تأمین‌کننده','پنل تأمین‌کننده'],['agency@aftab.test','آژانس','پنل همکار'],['backoffice@aftab.test','عملیات','مدیریت مجموعه']] as const) {
    await uiLogin(page, email);
    await page.getByRole('link', { name: link, exact: true }).click();
    await expect(page.getByRole('navigation', { name: panel })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'دسترسی ندارید' })).toHaveCount(0);
  }
  await expect(page.getByRole('heading', { level: 1, name: 'BackOffice / Admin' })).toBeVisible();
});

test('customer account connects profile, travellers, wallet, payment and notification preferences', async ({ page, request }) => {
  const reservationId = await createOperationalFixture(request, 'account');
  await uiLogin(page, 'employee@aftab.test');
  await page.getByRole('link', { name: 'سفرهای من' }).click();
  // Signed-in pages reach the account through the header account menu (role-filtered links).
  await page.getByText('حساب کاربری', { exact: true }).click();
  await page.getByRole('link', { name: 'حساب من', exact: true }).click();
  await page.getByRole('navigation', { name: 'حساب من' }).getByRole('link', { name: 'پروفایل و مسافران' }).click();
  await expect(page.getByRole('heading', { name: 'پروفایل، مسافران و امور مالی' })).toBeVisible();
  // Traveller identity is validated (Iranian national code checksum) before it is saved.
  await page.getByText('افزودن مسافر جدید', { exact: true }).click();
  const travellerForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'افزودن مسافر' }) });
  await travellerForm.getByRole('textbox', { name: 'نام و نام خانوادگی مسافر', exact: true }).fill('مسافر E2E');
  const nationalCode = travellerForm.getByRole('textbox', { name: /^کد ملی/ });
  await nationalCode.fill('0012345678');
  await expect(nationalCode).toHaveAttribute('aria-invalid', 'true');
  await travellerForm.getByRole('button', { name: 'افزودن مسافر' }).click();
  await expect(travellerForm.getByRole('alert')).toBeVisible();
  await nationalCode.fill('0012345679');
  await expect(nationalCode).toHaveAttribute('aria-invalid', 'false');
  await travellerForm.getByRole('button', { name: 'افزودن مسافر' }).click();
  await expect(page.getByRole('status')).toContainText('مسافر افزوده شد');
  await expect(page.getByText('مسافر E2E', { exact: true })).toBeVisible();
  if (await page.getByRole('button', { name: 'ایجاد کیف پول ریالی' }).isVisible()) {
    await page.getByRole('button', { name: 'ایجاد کیف پول ریالی' }).click();
    await expect(page.getByRole('status')).toContainText('کیف پول ایجاد شد');
  }
  // Payment is completed through the checkout of the reservation; never initiate a financial transaction here.
  const employee = await login(request, 'employee@aftab.test');
  const reference = (await (await request.get(`${api}/reservations/${reservationId}`, { headers: { Authorization: `Bearer ${employee.access_token}` } })).json()).booking_reference;
  await expect(page.getByRole('link', { name: `تکمیل رزرو ${reference}` })).toHaveAttribute('href', `/checkout/${reservationId}`);
  const smsPreference = page.getByRole('switch', { name: /تغییرات سفر · sms/ });
  const before = await smsPreference.getAttribute('aria-checked');
  await smsPreference.focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('status')).toContainText('ترجیحات اعلان ذخیره شد');
  await expect(page.getByRole('switch', { name: /تغییرات سفر · sms/ })).toHaveAttribute('aria-checked', before === 'true' ? 'false' : 'true');
});

test('supplier, agency and backoffice mutations remain role-scoped', async ({ page, request }) => {
  await createOperationalFixture(request, 'panel-mutations');
  // Supplier records are now registered by staff; a supplier publishes offers for its own suppliers.
  await uiLogin(page, 'supplier@aftab.test');
  await page.getByRole('link', { name: 'تأمین‌کننده', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'پنل تأمین‌کننده' })).toBeVisible();
  await page.goto('/supplier/offers/new');
  await expect(page.getByRole('heading', { level: 1, name: 'ثبت عرضهٔ اقامت' })).toBeVisible();
  await page.getByRole('textbox', { name: 'عنوان اقامت' }).fill('اتاق دوتخته UI');
  await page.getByRole('textbox', { name: 'شهر', exact: true }).fill('شیراز');
  await page.getByRole('textbox', { name: 'نوع اتاق' }).fill('دوتخته');
  await page.getByRole('textbox', { name: 'شرح خدمت' }).fill('اتاق دوتخته با صبحانه');
  await page.getByRole('textbox', { name: 'مرجع قرارداد' }).fill('قرارداد E2E-1405');
  await page.getByRole('textbox', { name: 'شرایط رزرو و استرداد' }).fill('غیرقابل استرداد طبق قرارداد');
  await page.getByLabel('تاریخ ورود').fill('2030-04-01');
  await page.getByLabel('تاریخ خروج').fill('2030-04-03');
  await page.getByRole('textbox', { name: 'نام برنامهٔ نرخ' }).fill('با صبحانه');
  await page.getByRole('spinbutton', { name: 'بزرگسال در هر اتاق' }).fill('2');
  await page.getByRole('spinbutton', { name: 'قیمت نهایی هر واحد (ریال)' }).fill('3000000');
  await page.getByRole('spinbutton', { name: 'ظرفیت قابل رزرو' }).fill('2');
  await page.getByRole('spinbutton', { name: 'اعتبار عرضه (دقیقه)' }).fill('60');
  await page.getByRole('spinbutton', { name: 'جریمه طبق قرارداد (ریال)' }).fill('0');
  await page.getByRole('checkbox', { name: 'صحت ظرفیت، مبلغ و شرایط قرارداد را تأیید می‌کنم.' }).check();
  await page.getByRole('button', { name: 'ثبت عرضهٔ معتبر' }).click();
  await expect(page.getByRole('status')).toContainText('عرضه در حساب تأمین‌کننده ثبت شد');
  await expect(page.getByRole('link', { name: 'مشاهدهٔ جزئیات عرضهٔ ثبت‌شده' })).toBeVisible();
  // Partner roles cannot reach staff mutations.
  await uiLogin(page, 'agency@aftab.test');
  await page.getByRole('link', { name: 'آژانس', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'پنل همکار' })).toBeVisible();
  await page.goto('/backoffice');
  await expect(page.getByRole('alert').getByRole('heading', { name: 'دسترسی ندارید' })).toBeVisible();
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
  await page.locator(`a[href="/manage-booking/${reservationId}"]`).filter({ hasText: 'مدیریت رزرو' }).click();
  await page.getByRole('link', { name: 'گفت‌وگو با پشتیبانی انسانی' }).click();
  await page.getByLabel('شرح درخواست').fill('واچر این رزرو نیاز به بررسی انسانی دارد');
  await page.getByRole('button', { name: 'ایجاد پرونده انسانی' }).click();
  await expect(page.getByRole('status')).toContainText('پرونده پشتیبانی انسانی ثبت شد');
  await expect(page.locator('article').filter({ hasText: 'واچر این رزرو نیاز به بررسی انسانی دارد' }).last().getByText('مشتری', { exact: true })).toBeVisible();

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
  // Navigation is role-filtered, so customers get no finance link; the URL itself still fails closed.
  await expect(page.getByRole('link', { name: 'مالی', exact: true })).toHaveCount(0);
  await page.goto('/finance');
  await expect(page.getByRole('alert').getByRole('heading', { name: 'دسترسی ندارید' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'پرداخت، کیف پول، اقساط و تسویه' })).toHaveCount(0);

  await uiLogin(page, 'finance@aftab.test');
  await page.getByRole('link', { name: 'عملیات', exact: true }).click();
  await page.getByRole('navigation', { name: 'مدیریت مجموعه' }).getByRole('link', { name: 'مالی', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'پرداخت، کیف پول، اقساط و تسویه' })).toBeVisible();
});

test('saved travel, itinerary, destination and map fallback use tenant APIs', async ({ page, request }) => {
  const suffix = Date.now().toString();
  const backoffice = await login(request, 'backoffice@aftab.test');
  const destination = await request.post(`${api}/destinations`, { headers: { Authorization: `Bearer ${backoffice.access_token}` }, data: { kind: 'city', name_fa: 'شیراز E2E', name_en: 'Shiraz', slug: `shiraz-e2e-${suffix}`, latitude: 29.59, longitude: 52.58, description: 'مقصد تست عملیاتی', seasonality: ['spring'], categories: ['historical'], highlights: ['حافظیه'], nearby_slugs: [] } });
  expect(destination.status()).toBe(201);
  await uiLogin(page, 'employee@aftab.test');
  await page.goto('/saved-trips');
  // Saved trips are named lists that collect search selections; free-text item references are gone.
  await page.getByRole('textbox', { name: 'عنوان فهرست سفر' }).fill(`سفر E2E ${suffix}`);
  await page.getByRole('button', { name: 'ساخت فهرست سفر' }).click();
  await expect(page.getByRole('status')).toContainText('فهرست سفر ذخیره شد');
  const savedTrip = page.getByRole('region', { name: `سفر E2E ${suffix}` });
  await expect(savedTrip.getByText('این فهرست هنوز انتخابی ندارد.')).toBeVisible();
  await savedTrip.getByRole('textbox', { name: `یادداشت سفر E2E ${suffix}` }).fill('حافظیه و باغ ارم');
  await savedTrip.getByRole('button', { name: 'ذخیرهٔ یادداشت' }).click();
  await expect(page.getByRole('status')).toContainText('یادداشت ذخیره شد؛ این یادداشت رزرو نیست.');
  await page.goto('/itineraries');
  await page.getByRole('textbox', { name: 'عنوان برنامه سفر' }).fill(`برنامه E2E ${suffix}`);
  await page.getByRole('button', { name: 'ساخت برنامه' }).click();
  const itinerary = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: `برنامه E2E ${suffix}` }) }).last();
  await expect(itinerary.getByRole('heading', { level: 2, name: `برنامه E2E ${suffix}` })).toBeVisible();
  // With no priced service in the plan there is nothing to recheck; a note is not a booking.
  await expect(itinerary.getByRole('button', { name: 'بررسی قیمت و موجودی همهٔ خدمات' })).toBeDisabled();
  await itinerary.getByRole('textbox', { name: 'عنوان یادداشت' }).fill('بازدید حافظیه');
  await itinerary.getByRole('button', { name: 'افزودن یادداشت سفر' }).click();
  await expect(itinerary.getByRole('heading', { level: 3, name: 'روز ۱: بازدید حافظیه' })).toBeVisible();
  // /destinations lists curated guides; a tenant destination is served at its own slug.
  await page.goto(`/destinations/shiraz-e2e-${suffix}`);
  await expect(page.getByRole('heading', { level: 1, name: 'شیراز E2E' })).toBeVisible();
  await expect(page.getByText('Offer تازه‌ای برای این مقصد موجود نیست')).toBeVisible();
  await page.goto('/map');
  await expect(page.getByText('در نبود credential نقشه')).toBeVisible();
});
