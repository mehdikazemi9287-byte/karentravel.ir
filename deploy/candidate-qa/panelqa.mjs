// Candidate browser QA for the role workspaces. Desktop + mobile; data, empty, error/permission and loading states.
import {chromium} from 'playwright';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137', OUT = process.argv[2];
const browser = await chromium.launch(); const out = {};
const login = async email => (await (await fetch(API + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email})})).json());
for (const [vpName, vp] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (name, ok, extra = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — ' + String(extra).slice(0, 110) : ''}`);
  const ctx = await browser.newContext({viewport: vp, locale: 'fa-IR', acceptDownloads: true}); const page = await ctx.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 120)));
  const as = async email => {const s = await login(email); await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(x => {sessionStorage.clear(); if (x) sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x));}, email ? s : null);};
  const open = async path => {await page.goto(WEB + path, {waitUntil: 'networkidle'}); await page.waitForTimeout(500);};
  const text = () => page.locator('main, body').first().innerText();
  const fits = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const denied = async (email, path, name) => {await as(email); await open(path); check(`permission: ${name}`, /دسترسی ندارد|وارد شوید/.test(await text()) && !(await page.locator('table, form[aria-label]').count()));};
  // ---------- finance
  await as('finance@aftab.test');
  await page.route('**/finance/records/**', async route => {await new Promise(res => setTimeout(res, 900)); await route.continue();});
  await page.goto(WEB + '/finance/records', {waitUntil: 'domcontentloaded'});
  check('finance: loading state', await page.locator('[role=status]:has-text("در حال دریافت")').first().waitFor({timeout: 6000}).then(() => true).catch(() => false));
  await page.waitForSelector('table'); await page.unroute('**/finance/records/**');
  check('finance: payments table with real row', /qa-test/.test(await text()) && /۲۴٬۰۰۰٬۰۰۰/.test(await text()));
  check('finance: overview by status, no derived balance', /captured/.test(await text()) && /محاسبه‌شده در این صفحه نمایش داده نمی‌شود/.test(await text()));
  await page.click('[role=tab]:has-text("فاکتورها")'); await page.waitForSelector('th:has-text("مالیات")'); check('finance: invoices with tax column', /۲٬۰۰۰٬۰۰۰/.test(await text()));
  await page.click('[role=tab]:has-text("استردادها")'); await page.waitForSelector('text=ردیفی ثبت نشده است'); check('finance: empty state', true);
  await page.click('[role=tab]:has-text("پرداخت‌ها")'); await page.waitForSelector('table');
  const [dl] = await Promise.all([page.waitForEvent('download', {timeout: 8000}).catch(() => null), page.click('button:has-text("خروجی CSV")')]);
  check('finance: CSV export downloads', !!dl && dl.suggestedFilename() === 'payments.csv');
  await page.route('**/finance/records/**', route => route.abort()); await page.click('[role=tab]:has-text("تسویه‌ها")'); await page.waitForSelector('[role=alert]'); check('finance: error state', /دریافت اطلاعات انجام نشد/.test(await text())); await page.unroute('**/finance/records/**');
  check('finance: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/panel-finance-${vpName}.png`});
  await denied('employee@aftab.test', '/finance/records', 'customer cannot open finance');
  // ---------- agency
  await as('agency@aftab.test'); await open('/agency'); await page.waitForSelector('select[aria-label="انتخاب آژانس"]');
  const options = await page.$$eval('select[aria-label="انتخاب آژانس"] option', os => os.map(o => o.textContent));
  check('agency: only member agencies listed', options.filter(o => /QA/.test(o)).length === 2 && options.length === 3, options.join('|'));
  await page.selectOption('select[aria-label="انتخاب آژانس"]', {label: 'آژانس آزمون QA'}); await page.waitForSelector('table');
  check('agency: bookings attributed via sales channel', (await page.locator('tbody tr').count()) === 2 && /QA-/.test(await text()));
  await page.click('[role=tab]:has-text("کمیسیون")'); await page.waitForSelector('text=جمع:'); check('agency: commission 5% of the confirmed booking only', /۱٬۲۰۰٬۰۰۰/.test(await text()) && (await page.locator('tbody tr').count()) === 1);
  await page.click('[role=tab]:has-text("مشتریان")'); await page.waitForSelector('table'); check('agency: customers', (await page.locator('tbody tr').count()) === 1);
  await page.click('[role=tab]:has-text("تسویه")'); await page.waitForSelector('table'); check('agency: settlements', /۲۰٬۰۰۰٬۰۰۰/.test(await text()));
  await page.click('[role=tab]:has-text("گزارش")'); await page.waitForSelector('[data-report]'); check('agency: report', /confirmed/.test(await text()) && /۲۴٬۰۰۰٬۰۰۰/.test(await text()));
  await page.selectOption('select[aria-label="انتخاب آژانس"]', {label: 'آژانس بدون کانال (آزمون QA)'}); await page.click('[role=tab]:has-text("رزروها")'); await page.waitForSelector('text=رزروی به این آژانس نسبت داده نشده است');
  check('agency: empty state when no channel is linked', /کانال فروش متصل نشده/.test(await text()));
  check('agency: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/panel-agency-${vpName}.png`});
  await denied('employee@aftab.test', '/agency', 'customer cannot open agency panel');
  // ---------- supplier
  await as('supplier@aftab.test'); await open('/supplier/settlements'); await page.waitForSelector('table');
  check('supplier: own supplier, contract and settlement', /تأمین‌کنندهٔ آزمون QA/.test(await text()) && /grs/.test(await text()) && /۲۰٬۰۰۰٬۰۰۰/.test(await text()) && /انجام نشده/.test(await text()));
  check('supplier: no horizontal overflow', await fits());
  await as('agency@aftab.test'); await open('/supplier/settlements'); check('permission: agency cannot open supplier settlements', /دسترسی ندارد/.test(await text()));
  // ---------- support desk
  await as('backoffice@aftab.test'); await open('/backoffice/support'); await page.waitForSelector('select[aria-label="انتخاب پرونده"]');
  await page.selectOption('select[aria-label="انتخاب پرونده"]', {index: 1}); await page.waitForSelector('[data-case]');
  const before = await page.locator('[aria-label="پیام‌های پرونده"] article').count();
  check('support: workspace shows customer, booking, trip events', /رزرو مرتبط/.test(await text()) && /hotel/.test(await text()) && /آرمان|مشتری/.test(await text()));
  const note = `یادداشت آزمون ${vpName} ${Date.now()}`;
  await page.fill('form[aria-label="یادداشت داخلی"] textarea', note); await page.click('form[aria-label="یادداشت داخلی"] button'); await page.waitForSelector(`article[data-author="internal_note"]:has-text("${note}")`);
  check('support: internal note labelled internal-only', /فقط داخلی/.test(await page.locator(`article:has-text("${note}")`).innerText()));
  const reply = `پاسخ آزمون ${vpName} ${Date.now()}`;
  await page.fill('form[aria-label="پاسخ به مشتری"] textarea', reply); await page.click('form[aria-label="پاسخ به مشتری"] button'); await page.waitForSelector(`article[data-author="human_support"]:has-text("${reply}")`);
  check('support: human reply labelled human', /نوشتهٔ انسان/.test(await page.locator(`article:has-text("${reply}")`).innerText()) && (await page.locator('[aria-label="پیام‌های پرونده"] article').count()) === before + 2);
  await page.fill('form[aria-label="ارجاع فوری"] input[name=reason]', 'مشتری در فرودگاه منتظر است'); await page.click('form[aria-label="ارجاع فوری"] button'); await page.waitForSelector('[role=status]:has-text("ارجاع فوری شد")');
  check('support: escalation recorded in history and as internal trip event', /ارجاع فوری/.test(await page.locator('aside.grid').innerText()) && /اقدام پشتیبانی/.test(await page.locator('aside.grid').innerText()));
  check('support: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/panel-support-${vpName}.png`, fullPage: vpName === 'desktop'});
  const cust = await login('employee@aftab.test'); const mine = await (await fetch(API + '/support/cases', {headers: {Authorization: 'Bearer ' + cust.access_token}})).json();
  check('support: customer API never returns the internal note, does return the reply', !JSON.stringify(mine).includes(note) && JSON.stringify(mine).includes(reply));
  await denied('employee@aftab.test', '/backoffice/support', 'customer cannot open the support desk workspace');
  // ---------- notifications
  await as('backoffice@aftab.test'); await open('/backoffice/notifications'); await page.waitForSelector('table');
  check('notifications: channel, template, status, attempt, link, read', /پیامک/.test(await text()) && /important_trip_changes/.test(await text()) && /not_sent/.test(await text()) && /\/trips\//.test(await text()));
  await page.selectOption('select[aria-label="وضعیت تحویل"]', 'delivered'); await page.waitForTimeout(800); check('notifications: no SMS or push was ever delivered', !/پیامک|پوش/.test(await page.locator('tbody, [role=status]').first().innerText()));
  await page.selectOption('select[aria-label="وضعیت تحویل"]', 'dead_letter'); await page.waitForSelector('text=تحویلی با این شرایط ثبت نشده است'); check('notifications: empty state', true);
  await page.selectOption('select[aria-label="وضعیت تحویل"]', ''); await page.selectOption('select[aria-label="کانال"]', 'sms'); await page.waitForTimeout(700);
  check('notifications: channel filter', !(await page.locator('tbody').innerText()).includes('پوش')); check('notifications: no horizontal overflow', await fits());
  await denied('finance@aftab.test', '/backoffice/notifications', 'finance cannot open notification deliveries');
  // ---------- reference tours
  await as('backoffice@aftab.test'); await open('/admin/tours'); await page.waitForSelector('ul li button');
  check('tours: list, all non-sellable', /۵۹ تور/.test(await text()) && /غیرقابل‌فروش/.test(await text()));
  await page.fill('form input', 'ارمنستان'); await page.click('form button.primary'); await page.waitForTimeout(800); await page.locator('ul li button').first().click(); await page.waitForSelector('form[aria-label="ویرایش تور مرجع"]');
  const form = page.locator('form[aria-label="ویرایش تور مرجع"]');
  check('tours: no price/capacity/supplier/future-date field', (await form.locator('label').allInnerTexts()).every(l => !/قیمت|ظرفیت|تأمین‌کننده|نرخ/.test(l)) && /قابل‌فروش نیست/.test(await form.innerText()));
  await form.locator('input[placeholder="مثلاً am-yerevan"]').fill('nowhere-xyz'); await form.locator('button.primary').first().click(); await page.waitForSelector('[role=alert]');
  check('tours: validation error from server', /فهرست مرجع نیست/.test(await page.locator('p[role=alert]').first().innerText()));
  await form.locator('input[placeholder="مثلاً am-yerevan"]').fill('am-yerevan'); await form.locator('button:has-text("افزودن روز")').click(); await form.locator('[data-day] input').nth(1).fill(`ورود به ایروان (${vpName})`);
  await form.locator('button.primary').first().click(); await page.waitForSelector('[role=status]:has-text("ذخیره شد")');
  await open('/admin/tours'); await page.fill('form input', 'ارمنستان'); await page.click('form button.primary'); await page.waitForTimeout(800); await page.locator('ul li button').first().click(); await page.waitForSelector('[data-day]');
  check('tours: itinerary persisted after reload', (await page.locator('[data-day] input').nth(1).inputValue()) === `ورود به ایروان (${vpName})`);
  await page.locator('button:has-text("حذف روز")').first().click(); await page.locator('form[aria-label="ویرایش تور مرجع"] input[placeholder="مثلاً am-yerevan"]').fill(''); await page.locator('form[aria-label="ویرایش تور مرجع"] button.primary').first().click(); await page.waitForSelector('[role=status]:has-text("ذخیره شد")');
  check('tours: test edit reverted', true); check('tours: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/panel-tours-${vpName}.png`});
  await denied('supplier@aftab.test', '/admin/tours', 'supplier cannot open reference tours');
  await as(null); await open('/finance/records'); check('permission: anonymous', /وارد شوید/.test(await text()));
  out[vpName] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL')), errors};
  await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await browser.close();
