// Candidate browser QA, round 3: partner administration, supplier hotels, mapping editor, agency quotes, customer quotes,
// commission ledger and accounting, tour hotels. Desktop + mobile.
import {chromium} from 'playwright';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137', OUT = process.argv[2], HOTEL = '4fb4ffe9-42f6-5d4e-8fcd-fde6c9071e84';
const browser = await chromium.launch(); const out = {};
const login = async email => (await (await fetch(API + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email})})).json());
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (name, ok, extra = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — ' + String(extra).slice(0, 120) : ''}`);
  const ctx = await browser.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 120)));
  page.on('dialog', d => d.accept('اصلاح ثبت آزمون'));
  const as = async email => {const s = email ? await login(email) : null; await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(x => {sessionStorage.clear(); if (x) sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x));}, s);};
  const open = async path => {await page.goto(WEB + path, {waitUntil: 'networkidle'}); await page.waitForTimeout(500);};
  const text = () => page.locator('main, body').first().innerText();
  const fits = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const ok = async () => {await page.waitForSelector('p[role=status]', {timeout: 15000}); await page.waitForLoadState('networkidle'); await page.waitForTimeout(700);};
  const denied = async (email, path, name) => {await as(email); await open(path); check(`permission: ${name}`, /دسترسی ندارد|وارد شوید|فقط برای/.test(await text()) && !(await page.locator('form[aria-label]').count()));};
  const tag = `${vp}-${Date.now().toString().slice(-6)}`, agencyName = `آژانس QA ${tag}`, supplierName = `تأمین‌کنندهٔ QA ${tag}`, ref = `QA-${tag}`;
  // ---- supplier: empty state before assignment
  await as('supplier@aftab.test'); await open('/supplier/hotels'); check('supplier hotels: empty state', /هتلی به تأمین‌کنندهٔ شما واگذار نشده است/.test(await text()));
  // ---- partners administration
  await as('tenant-admin@aftab.test');
  await page.route(API + '/admin/partners', async route => {await new Promise(res => setTimeout(res, 900)); await route.continue();});
  await page.goto(WEB + '/admin/partners', {waitUntil: 'domcontentloaded'}); check('partners: loading state', await page.locator('[role=status]:has-text("در حال دریافت")').first().waitFor({timeout: 6000}).then(() => true).catch(() => false));
  await page.waitForSelector('form[aria-label="آژانس جدید"]'); await page.unroute(API + '/admin/partners');
  await page.fill('form[aria-label="آژانس جدید"] input[name=display_name]', agencyName); await page.fill('form[aria-label="آژانس جدید"] input[name=commission]', '4'); await page.click('form[aria-label="آژانس جدید"] button'); await page.waitForSelector(`[data-agency="${agencyName}"]`);
  const card = page.locator(`[data-agency="${agencyName}"]`);
  check('partners: agency created with commission', /کمیسیون ۴٪/.test(await card.innerText()));
  await page.fill('form[aria-label="آژانس جدید"] input[name=display_name]', agencyName); await page.click('form[aria-label="آژانس جدید"] button'); await page.waitForSelector('p[role=alert]'); check('partners: duplicate name rejected', /وجود دارد/.test(await page.locator('p[role=alert]').first().innerText()));
  await card.locator('input[name=name]').fill(`کانال ${tag}`); await card.locator('button:has-text("ساخت کانال فروش")').click(); await card.locator('text=کانال فروش: کانال').waitFor(); check('partners: sales channel created and linked', true);
  await card.locator('select[name=user_id]').selectOption({index: 1}); await card.locator('button:has-text("افزودن عضو")').click(); await card.locator('button[aria-label^="حذف"]').first().waitFor(); check('partners: agency member added', !/بدون عضو/.test(await card.innerText()));
  await card.locator('button[aria-label^="حذف"]').first().click(); await card.locator('text=بدون عضو').waitFor(); check('partners: agency member removed', true);
  await page.click('[role=tab]:has-text("تأمین‌کنندگان")'); await page.fill('form[aria-label="تأمین‌کنندهٔ جدید"] input[name=display_name]', supplierName); await page.click('form[aria-label="تأمین‌کنندهٔ جدید"] button'); await page.waitForSelector(`[data-supplier="${supplierName}"]`);
  const sup = page.locator(`[data-supplier="${supplierName}"]`);
  await sup.locator('select[name=user_id]').selectOption({index: 1}); await sup.locator('button:has-text("افزودن عضو")').click(); await sup.locator('button[aria-label^="حذف"]').first().waitFor(); check('partners: supplier created with member', true);
  await sup.locator('input[name=hotel_id]').fill('no-such-hotel'); await sup.locator('button:has-text("واگذاری هتل")').click(); await page.waitForSelector('p[role=alert]'); check('partners: unknown hotel rejected', /فهرست مرجع نیست/.test(await page.locator('p[role=alert]').first().innerText()));
  await sup.locator('input[name=hotel_id]').fill(HOTEL); await sup.locator('button:has-text("واگذاری هتل")').click(); await sup.locator('text=ایبیس').waitFor(); check('partners: hotel assigned to supplier', true);
  check('partners: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/r3-partners-${vp}.png`});
  // ---- supplier self-service mapping
  await as('supplier@aftab.test'); await open('/supplier/hotels'); await page.waitForSelector(`[data-hotel="${HOTEL}"]`);
  const sh = page.locator(`[data-hotel="${HOTEL}"]`); await sh.locator('input[name=provider]').fill('grs'); await sh.locator('input[name=provider_hotel_id]').fill(ref); await sh.locator('button').click(); await sh.locator(`text=${ref}`).waitFor();
  check('supplier hotels: proposed id is pending, rate not connected', /در انتظار تأیید کارن‌سیر/.test(await sh.innerText()) && /نرخ: متصل نیست/.test(await sh.innerText()));
  await sh.locator('input[name=provider]').fill('grs'); await sh.locator('input[name=provider_hotel_id]').fill(ref); await sh.locator('button').click(); await page.waitForSelector('p[role=alert]'); check('supplier hotels: duplicate id rejected', /قبلاً ثبت شده/.test(await page.locator('p[role=alert]').first().innerText()));
  check('supplier hotels: no horizontal overflow', await fits());
  // ---- catalog admin: mapping editor (verify, room, rate plan)
  await as('backoffice@aftab.test'); await open('/admin/catalog'); await page.waitForSelector('.cadm-list li'); await page.fill('.cadm-bar input', HOTEL); await page.click('.cadm-bar button[type=submit]'); await page.waitForTimeout(700); await page.click('.cadm-list li button'); await page.waitForSelector(`[data-mapping="${ref}"]`);
  const mp = page.locator(`[data-mapping="${ref}"]`); await mp.locator('button:has-text("تأیید با سند تأمین‌کننده")').click(); await mp.locator('text=تأییدشده').first().waitFor(); check('mapping editor: verify', !(await mp.locator('button:has-text("تأیید با سند")').count()));
  await mp.locator('select[name=room_type_id]').selectOption({index: 1}); await mp.locator('input[name=provider_room_id]').fill(`RM-${tag}`); await mp.locator('button:has-text("افزودن اتاق")').click(); await mp.locator(`text=RM-${tag}`).waitFor(); check('mapping editor: room mapped', /↔/.test(await mp.innerText()));
  await mp.locator('input[name=plan]').fill(`BAR-${tag}`); await mp.locator('select[name=board]').selectOption('BB'); await mp.locator('select[name=refundable]').selectOption('yes'); await mp.locator('button:has-text("افزودن طرح نرخ")').click(); await mp.locator(`text=BAR-${tag}`).waitFor();
  check('mapping editor: rate plan without amount', /صبحانه، قابل استرداد/.test(await mp.innerText()) && !/ریال/.test(await mp.innerText()));
  check('mapping editor: hotel still not rate-available', /RateAvailable\s*خیر/.test(await page.locator('.cadm-state').innerText())); check('mapping editor: no horizontal overflow', await fits());
  await page.locator('[data-mappings]').screenshot({path: `${OUT}/r3-mappings-${vp}.png`});
  // ---- agency quotes
  await as('agency@aftab.test'); await open('/agency'); await page.selectOption('select[aria-label="انتخاب آژانس"]', {label: 'آژانس آزمون QA'}); await page.click('[role=tab]:has-text("پیشنهاد قیمت")'); await page.waitForSelector('form[aria-label="پیشنهاد قیمت جدید"]');
  const before = await page.locator('[data-quotes] tbody tr').count();
  await page.selectOption('select[name=offer_id]', {index: 1}); await page.selectOption('select[name=customer_known]', {index: 1}); await page.fill('input[name=note]', `یادداشت ${tag}`); await page.click('form[aria-label="پیشنهاد قیمت جدید"] button'); await ok();
  check('agency quote: created at the supplier price', (await page.locator('[data-quotes] tbody tr').count()) === before + 1 && /۱۸٬۰۰۰٬۰۰۰/.test(await page.locator('[data-quotes] tbody tr').first().innerText()) && /ارسال‌شده/.test(await page.locator('[data-quotes] tbody tr').first().innerText()));
  await page.click('form[aria-label="پیشنهاد قیمت جدید"] button'); check('agency quote: browser validation blocks empty form', (await page.locator('[data-quotes] tbody tr').count()) === before + 1);
  check('agency quote: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/r3-agency-quotes-${vp}.png`});
  // ---- customer accepts
  await as('employee@aftab.test'); await open('/quotes'); await page.waitForSelector('[data-quote]'); const mine = page.locator('[data-quote]').first();
  check('customer quotes: shows agency, price, validity', /آژانس آزمون QA/.test(await mine.innerText()) && /۱۸٬۰۰۰٬۰۰۰/.test(await mine.innerText()) && /اعتبار تا/.test(await mine.innerText()));
  await mine.locator('button.primary').click(); await ok(); check('customer quotes: accepted, not a booking', /پذیرفته‌شده/.test(await page.locator('[data-quote]').first().innerText()) && /رزرو یا پرداخت نیست/.test(await text()));
  check('customer quotes: no horizontal overflow', await fits());
  await as('agency@aftab.test'); await open('/agency'); await page.selectOption('select[aria-label="انتخاب آژانس"]', {label: 'آژانس آزمون QA'}); await page.click('[role=tab]:has-text("پیشنهاد قیمت")'); await page.waitForSelector('[data-quotes] tbody tr');
  check('agency quote: agency sees the acceptance', /پذیرفته‌شده/.test(await page.locator('[data-quotes] tbody tr').first().innerText()));
  await page.locator('[data-quotes] tbody tr').first().locator('button:has-text("لغو")').click(); await ok(); check('agency quote: cancel', /لغوشده/.test(await page.locator('[data-quotes] tbody tr').first().innerText()));
  await page.click('[role=tab]:has-text("اعتبار")'); await page.waitForTimeout(900); check('agency credit: state shown', /سقف اعتبار|حساب اعتباری به این آژانس متصل نشده است/.test(await text()));
  // ---- finance: commission ledger and accounting
  await as('finance@aftab.test'); await open('/finance/accounting'); await page.waitForSelector('h2:has-text("دفتر کمیسیون")');
  const pending = await page.locator('button:has-text("ثبت در دفتر")').count(); check('accounting: confirmed agency bookings awaiting posting', pending >= 1, pending);
  await page.locator('button:has-text("ثبت در دفتر")').first().click(); await ok(); check('accounting: commission accrued (5% of 30,000,000)', /۱٬۵۰۰٬۰۰۰/.test(await text()) && (await page.locator('button:has-text("ثبت در دفتر")').count()) === pending - 1);
  await page.locator('tr:has-text("ثبت‌شده") button:has-text("تأیید")').first().click(); await ok(); await page.waitForSelector('form[aria-label="تسویهٔ کمیسیون"]'); check('accounting: approved', true);
  await page.locator('form[aria-label="تسویهٔ کمیسیون"] input').first().fill(`TRX-${tag}`); await page.locator('form[aria-label="تسویهٔ کمیسیون"] button').first().click(); await ok(); check('accounting: settled with payment reference', new RegExp(`TRX-${tag}`).test(await text()) && /تسویه‌شده/.test(await text()));
  await page.click('[role=tab]:has-text("مطالبات")'); await page.waitForTimeout(600); check('accounting: receivables with formula', /outstanding = invoice.total_amount/.test(await text()) && /۳۰٬۰۰۰٬۰۰۰/.test(await text()));
  await page.click('[role=tab]:has-text("بدهی به تأمین‌کننده")'); await page.waitForTimeout(600); check('accounting: supplier payables', /تأمین‌کنندهٔ آزمون QA/.test(await text()) && /۲۰٬۰۰۰٬۰۰۰/.test(await text()));
  await page.click('[role=tab]:has-text("خلاصهٔ مالیات")'); await page.waitForTimeout(600); check('accounting: tax summary', /tax_amount/.test(await text()) && /جمع مالیات/.test(await text()));
  await page.click('[role=tab]:has-text("اعتبار سازمانی")'); await page.waitForTimeout(600); check('accounting: organization credit', /۵۰۰٬۰۰۰٬۰۰۰/.test(await text()));
  check('accounting: states it is not the statutory ledger', /جایگزین دفاتر قانونی نیست/.test(await text())); check('accounting: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/r3-accounting-${vp}.png`});
  await page.route(API + '/finance/accounting', route => route.abort()); await open('/finance/accounting'); check('accounting: error state', /در دسترس نیست|انجام نشد|ممکن نیست/.test(await text())); await page.unroute(API + '/finance/accounting');
  await as('agency@aftab.test'); await open('/agency'); await page.selectOption('select[aria-label="انتخاب آژانس"]', {label: 'آژانس آزمون QA'}); await page.click('[role=tab]:has-text("دفتر کمیسیون")'); await page.waitForSelector('table'); check('agency ledger: sees the settled posting', new RegExp(`TRX-${tag}`).test(await text()));
  // ---- reference tour: hotels
  await as('backoffice@aftab.test'); await open('/admin/tours'); await page.fill('form input', 'ارمنستان'); await page.click('form button.primary'); await page.waitForTimeout(800); await page.locator('ul li button').first().click(); await page.waitForSelector('[data-tour-hotels]');
  const th = page.locator('[data-tour-hotels]'); await th.locator('input').last().fill('ibis yerevan'); await th.locator('button:has-text("جست‌وجو")').click(); await th.locator('button:has-text("افزودن به تور")').first().waitFor(); await th.locator('button:has-text("افزودن به تور")').first().click();
  await page.locator('form[aria-label="ویرایش تور مرجع"] button.primary').first().click(); await ok();
  await open('/admin/tours'); await page.fill('form input', 'ارمنستان'); await page.click('form button.primary'); await page.waitForTimeout(800); await page.locator('ul li button').first().click(); await page.waitForSelector('[data-tour-hotels]');
  check('tour hotels: linked hotel persisted', (await page.locator('[data-linked-hotel]').count()) === 1);
  await page.locator('[data-linked-hotel] button:has-text("حذف")').click(); await page.locator('form[aria-label="ویرایش تور مرجع"] button.primary').first().click(); await ok(); check('tour hotels: test link removed', (await page.locator('[data-linked-hotel]').count()) === 0);
  // ---- cleanup of the hotel assignment through the UI, permissions
  await as('tenant-admin@aftab.test'); await open('/admin/partners'); await page.click('[role=tab]:has-text("تأمین‌کنندگان")'); await page.locator(`[data-supplier="${supplierName}"] button[aria-label*="ایبیس"]`).click(); await ok(); check('partners: hotel assignment removed', /هتل‌های واگذارشده: هیچ/.test((await page.locator(`[data-supplier="${supplierName}"]`).innerText()).replace(/\s+/g, ' ')));
  await page.locator(`[data-supplier="${supplierName}"] button[aria-label^="حذف"]`).first().click(); await ok();
  await denied('agency@aftab.test', '/admin/partners', 'agency user cannot open partner administration');
  await denied('employee@aftab.test', '/finance/accounting', 'customer cannot open accounting');
  await denied('employee@aftab.test', '/supplier/hotels', 'customer cannot open supplier hotels');
  await denied('supplier@aftab.test', '/finance/accounting', 'supplier cannot open accounting');
  await denied(null, '/quotes', 'anonymous cannot open quotes');
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL')), errors};
  await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await browser.close();
