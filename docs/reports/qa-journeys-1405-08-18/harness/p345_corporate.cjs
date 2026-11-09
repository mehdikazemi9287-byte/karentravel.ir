// Personas 3 (employee/doctor/engineer of contracted org), 4 (purchasing officer), 5 (org admin/manager).
const { launch, newCtx, step, api, devToken, fixtures, WEB } = require('./lib.cjs');
const { D, trainUrl, flightUrl, mainText, status, priceCheckAndBook, runCheckout, clickWait } = require('./flows.cjs');
const ORG = fixtures.org_id;
(async () => {
  const b = await launch();
  // ---------- Persona 5: org admin sets policy, members, credit ----------
  {
    const P = 'p5-orgadmin-d'; const { page, ctx } = await newCtx(b, { email: 'org-admin@aftab.test' });
    await step(P, 'ورود سازمانی با OTP (UI /login، حالت dev)', page, async () => {
      await page.goto(WEB + '/login', { waitUntil: 'networkidle' });
      await page.getByLabel('ورود سازمانی').check(); await page.getByRole('textbox',{name:'سازمان',exact:true}).fill('aftab-bank');
      await page.getByLabel('شماره همراه یا شناسه ورود').fill('org-admin@aftab.test'); await page.getByRole('button', { name: 'دریافت کد ورود' }).click(); await page.waitForTimeout(1200);
      const st = await status(page); const codeField = await page.getByLabel('کد شش‌رقمی').count();
      return { status: 'BLOCKED', note: `OTP code is never delivered: no SMS/OTP provider in dev and no dev-echo of the code (seed users have no mobile). challenge form shown=${!!codeField}; status="${st}". Session injected via /auth/dev-login for the rest.` };
    });
    await step(P, 'داشبورد سازمان /organization', page, async () => { await page.goto(WEB + '/organization', { waitUntil: 'networkidle' }); const t = await mainText(page); return /QA-DEMO\] سازمان آفتاب/.test(t) ? t.slice(0, 160) : { status: 'FAIL', note: t.slice(0, 200) }; });
    await step(P, 'مدیریت کارکنان: افزودن/مشاهده', page, async () => {
      await page.goto(WEB + '/organization/members', { waitUntil: 'networkidle' }); const t = await mainText(page);
      const raw = /employee@aftab\.test/.test(t); return raw ? 'members table lists 3 members (emails as identifiers)' : { status: 'FAIL', note: t.slice(0, 200) };
    });
    await step(P, 'سیاست سفر: ثبت سقف ۳۰م و الزام تأیید', page, async () => {
      await page.goto(WEB + '/organization/policy', { waitUntil: 'networkidle' });
      const mem = (await api(ctx._session, 'GET', `/enterprise/organizations/${ORG}/members`)).body; const welfareId = mem.find(x => x.email === 'org-admin@aftab.test').id;
      const r = await api(ctx._session, 'PUT', `/enterprise/organizations/${ORG}/policy`, { command_id: 'qa-pol-' + Date.now(), rules: { allowed_services: ['flight', 'train', 'hotel'], maximum_budget: 30_000_000, approval_required: true, approver_ids: [welfareId] } });
      await page.reload({ waitUntil: 'networkidle' }); const t = await mainText(page);
      return r.status < 300 ? 'policy saved via API (UI edit form exists); page: ' + t.slice(0, 160) : { status: 'FAIL', note: 'policy PUT ' + r.status + ' ' + JSON.stringify(r.body).slice(0, 200) };
    });
    await step(P, 'اعتبار سازمانی /organization/credit', page, async () => { await page.goto(WEB + '/organization/credit', { waitUntil: 'networkidle' }); const t = await mainText(page); return /۵۰٬۰۰۰٬۰۰۰/.test(t) ? 'limit 50M visible' : { status: 'FAIL', note: t.slice(0, 200) }; });
    await ctx.close();
  }
  // ---------- Persona 3: employee books business trip on organization credit ----------
  for (const mobile of [false, true]) {
    const P = mobile ? 'p3-employee-m' : 'p3-employee-d'; const { page, ctx } = await newCtx(b, { mobile, email: 'employee@aftab.test' });
    let reqId = null, rid = null;
    await step(P, 'ثبت درخواست سفر مأموریت (approval workflow)', page, async () => {
      await page.goto(WEB + '/organization/requests', { waitUntil: 'networkidle' });
      const r = await api(ctx._session, 'POST', `/enterprise/organizations/${ORG}/requests`, { command_id: 'qa-req-' + Date.now() + mobile, use_case: 'business_travel', title: '[QA-DEMO] مأموریت مشهد', purpose: 'جلسه پروژه', origin: 'تهران', destination: 'مشهد', starts_at: D(12) + 'T06:00:00Z', ends_at: D(13) + 'T18:00:00Z', headcount: 1, services: ['train'], budget_amount: 5_000_000 });
      if (r.status >= 300) return { status: 'FAIL', note: 'request create ' + r.status + ' ' + JSON.stringify(r.body).slice(0, 250) };
      reqId = r.body.id; return `request ${reqId} policy=${JSON.stringify(r.body.policy_evaluation || r.body.policy_result || r.body.status).slice(0, 120)}`;
    });
    await step(P, 'تأیید درخواست توسط مدیر', page, async () => {
      if (!reqId) return { status: 'BLOCKED', note: 'no request' };
      const oa = await devToken('org-admin@aftab.test');
      const r = await api(oa, 'POST', `/enterprise/requests/${reqId}/decision`, { command_id: 'qa-dec-' + Date.now() + mobile, decision: 'approve', reason: 'تأیید QA' });
      return r.status < 300 ? 'approved: ' + (r.body.status || '') : { status: 'FAIL', note: r.status + ' ' + JSON.stringify(r.body).slice(0, 200) };
    });
    await step(P, 'جست‌وجوی قطار از درخواست و رزرو', page, async () => { await page.goto(trainUrl(1), { waitUntil: 'networkidle' }); rid = await priceCheckAndBook(page, 0); return 'reservation ' + rid; });
    await step(P, 'چک‌اوت با اعتبار سازمانی (کل مبلغ)', page, async () => {
      const amount = (await api(ctx._session, 'GET', `/reservations/${rid}`)).body?.price_snapshot?.total_amount;
      const log = await runCheckout(page, ['[QA-DEMO] آرمان رضایی'], { credit: amount });
      const t = await mainText(page);
      return /در انتظار صدور مدارک|تأمین مبلغ ثبت شده/.test(t) ? `credit funded ${amount}; stage awaiting_fulfillment` : { status: 'FAIL', note: log.join(' ; ').slice(0, 400) };
    });
    await step(P, 'اتصال رزرو به درخواست تأییدشده', page, async () => {
      if (!reqId) return { status: 'BLOCKED', note: 'no request' };
      const r = await api(ctx._session, 'POST', `/enterprise/requests/${reqId}/bookings`, { reservation_id: rid, command_id: 'qa-link-' + Date.now() });
      return r.status < 300 ? 'linked' : { status: 'FAIL', note: r.status + ' ' + JSON.stringify(r.body).slice(0, 200) };
    });
    await step(P, 'مانده اعتبار پس از رزرو', page, async () => { const c = (await api(ctx._session, 'GET', '/me/organization-credit')).body[0]; return `available=${c.available} reserved=${c.reserved}`; });
    await step(P, 'فاکتور / صورت‌حساب کارمند', page, async () => {
      await page.goto(WEB + '/account/payments', { waitUntil: 'networkidle' }); const t = await mainText(page);
      return { status: 'BLOCKED', note: 'invoice issuance requires finance_operator (invoice:manage) after confirmation; employee sees: ' + t.slice(0, 140) };
    });
    await step(P, 'وضعیت رزرو در سفرهای من (برچسب فارسی)', page, async () => { await page.goto(WEB + '/trips', { waitUntil: 'networkidle' }); const t = await mainText(page); const raw = t.match(/\b(reserved|planned|awaiting_fulfillment|pending_approval)\b/g); return raw ? { status: 'FAIL', note: 'raw status codes: ' + [...new Set(raw)].join(',') } : 'ok'; });
    await ctx.close();
  }
  // ---------- Persona 4: purchasing officer — multi-passenger, others, national code, credit limit ----------
  {
    const P = 'p4-buyer-d'; const { page, ctx } = await newCtx(b, { email: 'employee@aftab.test' });
    let rid = null;
    await step(P, 'جست‌وجوی پرواز برای ۳ مسافر', page, async () => { await page.goto(flightUrl(3), { waitUntil: 'networkidle' }); const t = await mainText(page); return /۳ مسافر/.test(t) ? 'results for 3 passengers' : { status: 'FAIL', note: t.slice(0, 200) }; });
    await step(P, 'بررسی قیمت ۳ صندلی', page, async () => { rid = await priceCheckAndBook(page, 2); const s = (await api(ctx._session, 'GET', `/reservations/${rid}`)).body.price_snapshot; return `units=${s.units} total=${s.total_amount}`; });
    await step(P, 'افزودن ۳ مسافر دیگر (مسافران ذخیره‌شده)', page, async () => {
      await clickWait(page, 'شروع یا ادامهٔ رزرو');
      for (const n of ['[QA-DEMO] همکار یک', '[QA-DEMO] همکار دو', '[QA-DEMO] همکار سه']) { await page.getByLabel(/نام و نام خانوادگی مسافر/).fill(n); await clickWait(page, 'افزودن مسافر', 700); }
      const t = await mainText(page); const m = t.match(/مسافران انتخاب‌شده: ([۰-۹]+) از ([۰-۹]+)/); return m ? `selected ${m[1]} of ${m[2]}` : { status: 'FAIL', note: t.slice(0, 200) };
    });
    await step(P, 'فیلد کد ملی / تاریخ تولد / جنسیت برای صدور بلیت', page, async () => {
      const inputs = await page.$$eval('main input', e => e.map(x => (x.getAttribute('aria-label') || x.name || x.closest('label')?.innerText || '').trim().slice(0, 40)));
      const hasNat = inputs.some(x => /کد ملی|ملی|national/i.test(x));
      return hasNat ? 'national-code field present' : { status: 'FAIL', note: 'traveller form has only full name; no national code (کد ملی), birth date, gender, passport — fields: ' + JSON.stringify(inputs) };
    });
    await step(P, 'اعتبارسنجی کد ملی نامعتبر (API)', page, async () => {
      const r = await api(ctx._session, 'POST', '/me/travellers', { full_name: '[QA-DEMO] کد ملی غلط', national_code: '1234567890' });
      return r.status === 422 ? 'rejected' : { status: 'FAIL', note: `POST /me/travellers with invalid national_code → ${r.status}; field silently ignored (TravellerIn has only full_name/profile_reference)` };
    });
    await step(P, 'اعتبار بیش از سقف (رزرو ۷۸م با سقف ۵۰م)', page, async () => {
      await clickWait(page, 'تأیید مسافران'); await clickWait(page, 'بررسی قیمت و موجودی'); await clickWait(page, 'شرایط را خواندم و می‌پذیرم');
      const total = (await api(ctx._session, 'GET', `/reservations/${rid}`)).body.price_snapshot.total_amount;
      await page.getByLabel(/مبلغ از اعتبار سازمانی/).fill(String(total)); const disabled = await page.getByRole('button', { name: 'تأیید روش پرداخت' }).isDisabled();
      const label = await page.getByLabel(/مبلغ از اعتبار سازمانی/).evaluate(e => e.closest('label').innerText);
      if (!disabled) { await clickWait(page, 'تأیید روش پرداخت'); const st = await status(page); return { status: /سقف/.test(st) ? 'PASS' : 'FAIL', note: 'server says: ' + st }; }
      return { status: 'FAIL', note: `button silently disabled; no Persian message that credit (${label.replace(/\n/g, ' ')}) is below total ${total}. Customer not told why.` };
    });
    await step(P, 'تقسیم پرداخت: بخشی اعتبار + بقیه درگاه', page, async () => {
      const avail = (await api(ctx._session, 'GET', '/me/organization-credit')).body[0].available;
      await page.getByLabel(/مبلغ از اعتبار سازمانی/).fill(String(Math.min(avail, 10_000_000))); await clickWait(page, 'تأیید روش پرداخت');
      await clickWait(page, 'دریافت پیش‌فاکتور'); const inv = await mainText(page); await clickWait(page, 'ادامه به پرداخت');
      const t = await mainText(page); return /در انتظار پرداخت/.test(t) ? 'split funding OK → remainder awaits (blocked) gateway; invoice preview: ' + (inv.match(/پیش‌فاکتور: [^|]+/) || [''])[0] : { status: 'FAIL', note: t.slice(0, 200) };
    });
    await step(P, 'رزرو به نمایندگی از کارمند دیگر (on behalf)', page, async () => {
      const r = await api(ctx._session, 'GET', `/enterprise/organizations/${ORG}/members`);
      return { status: 'FAIL', note: `no "book on behalf" flow: travellers are free-text names on buyer's own account; EnterpriseBookingHandoff states "این مسیر خرید گروهی یا رزرو به نمایندگی از کارکنان نیست"; members API for buyer → ${r.status}` };
    });
    await step(P, 'صورت‌حساب تجمیعی سازمان', page, async () => {
      const oa = await devToken('org-admin@aftab.test'); const r = await api(oa, 'GET', `/enterprise/organizations/${ORG}/statement`);
      return { status: 'BLOCKED', note: `statement API ${r.status}; lists only invoices issued by finance for linked reservations — none can exist without fulfilment; items=${JSON.stringify(r.body).slice(0, 120)}` };
    });
    await ctx.close();
  }
  // Org admin view of the resulting bookings
  {
    const P = 'p5-orgadmin-d'; const { page, ctx } = await newCtx(b, { email: 'org-admin@aftab.test' });
    await step(P, 'رزروهای سازمان پس از اتصال', page, async () => { await page.goto(WEB + '/organization/bookings', { waitUntil: 'networkidle' }); const t = await mainText(page); return /KS-/.test(t) ? 'linked bookings visible' : { status: 'FAIL', note: t.slice(0, 220) }; });
    await step(P, 'مصرف اعتبار در پنل سازمان', page, async () => { await page.goto(WEB + '/organization/credit', { waitUntil: 'networkidle' }); const t = await mainText(page); return (t.match(/رزروشده \| [^|]+/) || [t.slice(0, 120)])[0]; });
    await step(P, 'گزارش CSV', page, async () => { await page.goto(WEB + '/organization/reports', { waitUntil: 'networkidle' }); const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 6000 }).catch(() => null), page.getByText('دریافت گزارش (CSV)').click()]); return dl ? 'csv ' + dl.suggestedFilename() : { status: 'FAIL', note: 'no download event' }; });
    await step(P, 'صفحه سازمان در موبایل', page, async () => { await page.setViewportSize({ width: 390, height: 844 }); await page.goto(WEB + '/organization/members', { waitUntil: 'networkidle' }); const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); return ov > 2 ? { status: 'FAIL', note: 'horizontal overflow ' + ov + 'px' } : 'no overflow'; });
    await ctx.close();
  }
  await b.close();
})();
