// Persona 6: regular B2C customer paying online (consumer tenant, dev-login session injected).
const { launch, newCtx, step, api, devToken, WEB } = require('./lib.cjs');
const { trainUrl, flightUrl, mainText, status, priceCheckAndBook, runCheckout } = require('./flows.cjs');
(async () => {
  const b = await launch();
  for (const mobile of [false, true]) {
    const P = mobile ? 'p6-customer-m' : 'p6-customer-d';
    const { page, ctx } = await newCtx(b, { mobile, email: 'qa-customer@consumer.qa' });
    let rid = null;
    await step(P, 'جست‌وجوی پرواز از صفحه اصلی (فرم)', page, async () => {
      await page.goto(WEB + '/', { waitUntil: 'networkidle' });
      const o = page.getByRole('combobox', { name: 'مبدأ' }); await o.fill('تهر'); await page.getByRole('option', { name: /^تهران/ }).first().click();
      const d = page.getByRole('combobox', { name: 'مقصد' }); await d.fill('شیرا'); await page.getByRole('option', { name: /^شیراز/ }).first().click();
      await page.getByRole('button', { name: /تاریخ رفت|تاریخ سفر/ }).first().click(); await page.waitForTimeout(400);
      if (await page.getByRole('button', { name: 'یک‌طرفه' }).count()) await page.getByRole('button', { name: 'یک‌طرفه' }).first().click();
      await page.locator('.jalali-grid button:enabled').nth(5).click(); if (await page.getByRole('button', { name: 'تأیید تاریخ' }).count()) await page.getByRole('button', { name: 'تأیید تاریخ' }).click();
      await page.getByRole('button', { name: /پیدا کن|جست‌وجو/ }).first().click();
      await page.waitForTimeout(800); if (!/search\/results/.test(page.url()) && await page.getByRole('button', { name: 'تأیید تاریخ' }).count()) { await page.locator('.jalali-grid button:enabled').nth(3).click(); await page.getByRole('button', { name: 'تأیید تاریخ' }).click(); await page.getByRole('button', { name: /پیدا کن|جست‌وجو/ }).first().click(); }
      await page.waitForURL(/search\/results/, { timeout: 10000 }); await page.waitForLoadState('networkidle');
      const t = await mainText(page); if (!/QA-DEMO\] پرواز/.test(t)) return { status: 'FAIL', note: 'no flight results after homepage search: ' + t.slice(0, 200) };
      return 'results visible (QA-DEMO offers)';
    });
    await step(P, 'جست‌وجوی هتل شیراز', page, async () => {
      await page.goto(`${WEB}/search/results?vertical=hotel&destination=شیراز&depart=${new Date(Date.now() + 20 * 864e5).toISOString().slice(0, 10)}&return=${new Date(Date.now() + 22 * 864e5).toISOString().slice(0, 10)}&adults=2&rooms=1`, { waitUntil: 'networkidle' });
      const t = await mainText(page); return /QA-DEMO\] هتل/.test(t) ? 'hotel result shown' : { status: 'FAIL', note: 'no hotel results: ' + t.slice(0, 250) };
    });
    await step(P, 'رزرو هتل: بررسی قیمت → چک‌اوت', page, async () => {
      await page.getByRole('button', { name: 'انتخاب اتاق و مهمانان' }).first().click(); await page.waitForURL(/\/offers\//);
      await page.getByRole('button', { name: 'بررسی قیمت و ظرفیت' }).click(); await page.waitForTimeout(2000);
      const st = await status(page); const cont = page.getByRole('button', { name: /ادامه رزرو|انتخاب و تکمیل اطلاعات مسافران/ });
      if (!(await cont.count())) return { status: 'FAIL', note: 'hotel price-check did not offer continue: ' + st };
      await cont.first().click(); await page.waitForURL(/\/checkout\//, { timeout: 15000 });
      const hasMain = await page.locator('main').count();
      return 'hotel price-check → checkout ' + page.url().replace(WEB, '') + ' (offer page <main> landmarks seen earlier: see a11y)';
    });
    await step(P, 'جست‌وجوی پرواز و مرتب‌سازی ارزان‌ترین', page, async () => {
      await page.goto(flightUrl(1, 'lowest_price'), { waitUntil: 'networkidle' });
      const prices = await page.$$eval('article', a => a.map(x => (x.innerText.match(/([۰-۹٬]+) ریال/) || [])[1]).filter(Boolean));
      const nums = prices.map(p => Number(p.replace(/[۰-۹]/g, c => '۰۱۲۳۴۵۶۷۸۹'.indexOf(c)).replace(/٬/g, '')));
      const sorted = [...nums].sort((a, b) => a - b); if (!nums.length) return { status: 'FAIL', note: 'no prices' };
      return JSON.stringify(nums) === JSON.stringify(sorted) ? 'sorted asc: ' + nums.join(',') : { status: 'FAIL', note: 'not sorted asc: ' + nums.join(',') };
    });
    await step(P, 'بررسی قیمت پرواز و ادامه رزرو', page, async () => { rid = await priceCheckAndBook(page, 0); return 'reservation ' + rid; });
    let log = [];
    await step(P, 'چک‌اوت: مسافر → قیمت → شرایط → تأمین → پیش‌فاکتور → پرداخت', page, async () => {
      log = await runCheckout(page, ['[QA-DEMO] مسافر عادی']);
      const t = await mainText(page);
      if (!/در انتظار پرداخت/.test(t)) return { status: 'FAIL', note: log.join(' ; ').slice(0, 400) };
      return 'reached awaiting_payment; ' + log.slice(-1);
    });
    await step(P, 'رفرش صفحه چک‌اوت و ادامه (بدون رزرو تکراری)', page, async () => {
      const before = (await api(ctx._session, 'GET', '/me/reservations')).body.length;
      await page.reload({ waitUntil: 'networkidle' });
      await page.getByRole('button', { name: 'شروع یا ادامهٔ رزرو' }).click(); await page.waitForTimeout(1000);
      const t = await mainText(page); const after = (await api(ctx._session, 'GET', '/me/reservations')).body.length;
      if (after !== before) return { status: 'FAIL', note: `reservations ${before}->${after}` };
      return /در انتظار پرداخت/.test(t) ? 'resumed same checkout at awaiting_payment, no new reservation' : { status: 'FAIL', note: 'did not resume stage: ' + t.slice(0, 200) };
    });
    await step(P, 'بازگشت (Back) از چک‌اوت به نتایج و دوباره ادامه', page, async () => {
      await page.goBack({ waitUntil: 'networkidle' }); const u = page.url();
      const before = (await api(ctx._session, 'GET', '/me/reservations')).body.length;
      if (await page.getByRole('button', { name: 'ادامه رزرو' }).count()) { await page.getByRole('button', { name: 'ادامه رزرو' }).first().click(); await page.waitForTimeout(2500); }
      const after = (await api(ctx._session, 'GET', '/me/reservations')).body.length;
      return after > before ? { status: 'FAIL', note: `Back then "ادامه رزرو" again created a 2nd reservation (${before}->${after}); url ${page.url().replace(WEB, '')}` } : 'no duplicate (' + u.replace(WEB, '') + ')';
    });
    // D6 re-run: explicit local sandbox gateway (PAYMENT_PROVIDER=sandbox, dev/test/staging only).
    await step(P, 'دوبار کلیک روی پرداخت (بدون پرداخت تکراری)', page, async () => {
      await page.goto(`${WEB}/checkout/${rid}`, { waitUntil: 'networkidle' }); await page.getByRole('button', { name: 'شروع یا ادامهٔ رزرو' }).click(); await page.waitForTimeout(1000);
      const btn = page.getByRole('button', { name: 'ادامه در درگاه پرداخت' });
      const reqs = []; page.on('request', r => { if (r.url().includes('/initiate')) reqs.push(r.url()); });
      await btn.dblclick().catch(() => {}); await page.waitForURL(/\/payments\/sandbox\//, { timeout: 10000 }).catch(() => {});
      return reqs.length <= 1 ? `initiate requests on dblclick=${reqs.length}; landed on ${new URL(page.url()).pathname.slice(0, 30)}…` : { status: 'FAIL', note: 'initiate sent ' + reqs.length + ' times' };
    });
    await step(P, 'درگاه پرداخت آزمایشی (TEST gateway)', page, async () => {
      if (!/\/payments\/sandbox\//.test(page.url())) return { status: 'FAIL', note: 'not redirected to sandbox gateway: ' + page.url() + ' ' + await status(page) };
      const body = await page.locator('body').innerText();
      if (!body.includes('درگاه آزمایشی — پرداخت واقعی نیست')) return { status: 'FAIL', note: 'sandbox page lacks the test label' };
      await page.getByRole('button', { name: 'پرداخت آزمایشی موفق' }).click(); await page.waitForURL(u => u.toString().startsWith(WEB + '/payments/'), { timeout: 15000 });
      const pi = (await api(ctx._session, 'GET', '/me/payments')).body.find(p => p.reservation_id === rid);
      const st = (await api(ctx._session, 'GET', `/payments/${pi.id}`)).body;
      return st.status === 'captured' && /^SANDBOX-TEST-/.test(st.receipt_reference || '') ? `labelled sandbox page → success → real callback/verify → captured ${st.captured_amount} ref ${st.receipt_reference}` : { status: 'FAIL', note: JSON.stringify(st).slice(0, 300) };
    });
    await step(P, 'وضعیت پرداخت /payments/:id', page, async () => {
      const pi = (await api(ctx._session, 'GET', '/me/payments')).body.find(p => p.reservation_id === rid);
      if (!pi) return { status: 'FAIL', note: 'no payment intent listed in /me/payments' };
      await page.goto(`${WEB}/payments/${pi.id}`, { waitUntil: 'networkidle' }); return (await mainText(page)).slice(0, 220);
    });
    await step(P, 'سفرهای من', page, async () => { await page.goto(WEB + '/trips', { waitUntil: 'networkidle' }); const t = await mainText(page); return /KS-/.test(t) ? (/\b(reserved|planned|awaiting_payment)\b/.test(t) ? { status: 'FAIL', note: 'raw English status codes shown to customer: ' + (t.match(/\b(reserved|planned|awaiting_payment)\b/g) || []).join(',') } : 'trips list ok') : { status: 'FAIL', note: 'no booking in trips' }; });
    await step(P, 'دانلود واچر/بلیت', page, async () => {
      // Issuance is a supplier/staff action (customers may only request cancel/change): the consumer-tenant QA supplier fulfils via its panel API.
      const sup = await devToken('qa-supplier@consumer.qa');
      const ready = (await api(sup, 'GET', '/supplier/reservations/ready')).body;
      if (!Array.isArray(ready) || !ready.some(r => r.id === rid)) return { status: 'FAIL', note: 'paid reservation not in supplier ready list: ' + JSON.stringify(ready).slice(0, 200) };
      const f = await api(sup, 'POST', `/reservations/${rid}/fulfill`, { command_id: 'qa-ful-' + Date.now() + mobile, provider_reference: '[QA-DEMO] REF', document_reference: 'document://qa-demo-voucher' });
      if (f.status !== 200) return { status: 'FAIL', note: 'fulfil ' + f.status + ' ' + JSON.stringify(f.body).slice(0, 200) };
      await page.goto(`${WEB}/manage-booking/${rid}`, { waitUntil: 'networkidle' });
      const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 8000 }).catch(() => null), page.getByRole('button', { name: 'دریافت واچر صادرشده' }).click()]);
      return dl ? `issued by supplier → voucher downloaded (${dl.suggestedFilename()})` : { status: 'FAIL', note: 'no voucher download: ' + await status(page) };
    });
    await step(P, 'درخواست کنسلی/استرداد از مدیریت رزرو', page, async () => {
      await page.goto(`${WEB}/manage-booking/${rid}`, { waitUntil: 'networkidle' });
      await page.getByRole('button', { name: 'درخواست استرداد' }).click(); await page.waitForTimeout(1500); const st = await status(page);
      const r = (await api(ctx._session, 'GET', `/reservations/${rid}`)).body;
      return /ثبت/.test(st) && r.status === 'refund_requested' ? 'refund request on issued booking: ' + st + ' (status refund_requested)' : { status: 'FAIL', note: (st || 'no status') + ' reservation=' + r.status };
    });
    await step(P, 'تیکت پشتیبانی انسانی', page, async () => {
      await page.getByRole('link', { name: /گفت‌وگو با پشتیبانی انسانی/ }).click(); await page.waitForLoadState('networkidle');
      await page.getByLabel('شرح درخواست').fill('[QA-DEMO] لطفاً وضعیت پرداخت را بررسی کنید'); await page.getByRole('button', { name: 'ایجاد پرونده انسانی' }).click(); await page.waitForTimeout(1500);
      const st = await status(page); return /ثبت شد/.test(st) ? st : { status: 'FAIL', note: st };
    });
    await step(P, 'اعلان‌ها', page, async () => { await page.goto(WEB + '/notifications', { waitUntil: 'networkidle' }); const t = await mainText(page); return /رزرو ثبت شد/.test(t) ? 'in-app notifications present; SMS/push declared not connected' : { status: 'FAIL', note: t.slice(0, 200) }; });
    await step(P, 'کیف پول: ایجاد و پرداخت با کیف پول', page, async () => {
      await page.goto(WEB + '/account/wallet', { waitUntil: 'networkidle' }); let t = await mainText(page);
      if (await page.getByRole('button', { name: 'ایجاد کیف پول ریالی' }).count()) { await page.getByRole('button', { name: 'ایجاد کیف پول ریالی' }).click(); await page.waitForTimeout(1000); t = await mainText(page); }
      return { status: 'BLOCKED', note: 'wallet can be created but has no top-up path for a customer (top-up needs gateway; wallet commands need credit:manage role) → balance 0, wallet payment cannot be exercised. Page: ' + t.slice(0, 160) };
    });
    await step(P, 'اقساط', page, async () => { await page.goto(WEB + '/account/payments', { waitUntil: 'networkidle' }); const t = await mainText(page); return { status: 'BLOCKED', note: 'installments need finance approval + gateway for down payment; page: ' + t.slice(0, 160) }; });
    await step(P, 'خروج از حساب', page, async () => {
      await page.goto(WEB + '/account/profile', { waitUntil: 'networkidle' });
      const btn = page.getByRole('button', { name: 'خروج از حساب' }); if (!(await btn.count())) { await page.goto(WEB + '/account', { waitUntil: 'networkidle' }); }
      if (!(await page.getByRole('button', { name: 'خروج از حساب' }).count())) return { status: 'FAIL', note: 'no logout button on /account/profile or /account' };
      await page.getByRole('button', { name: 'خروج از حساب' }).first().click(); await page.waitForTimeout(1000);
      await page.goto(WEB + '/trips', { waitUntil: 'networkidle' }); const t = await mainText(page);
      return /وارد شوید/.test(t) ? 'logged out; /trips gated' : { status: 'FAIL', note: 'still signed in after logout: ' + t.slice(0, 120) };
    });
    await ctx.close();
  }
  await b.close();
})();
