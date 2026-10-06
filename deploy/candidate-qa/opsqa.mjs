// Candidate browser QA: customer «what changed» + Trip Operations Center. Desktop + mobile; loading, empty, error, permission states.
import {chromium} from 'playwright';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137', OUT = process.argv[2], TRIP = process.argv[3], EMPTY = process.argv[4];
const browser = await chromium.launch(); const out = {};
const api = async (method, path, token, body) => {const r = await fetch(API + path, {method, headers: {'content-type': 'application/json', ...(token ? {Authorization: 'Bearer ' + token} : {})}, body: body ? JSON.stringify(body) : undefined}); return {status: r.status, body: await r.json().catch(() => null)};};
const login = async email => (await api('POST', '/auth/dev-login', null, {email})).body;
for (const [vpName, vp] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (name, ok, extra = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — ' + extra : ''}`);
  const ctx = await browser.newContext({viewport: vp, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 120)));
  const as = async email => {const s = await login(email); await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(x => sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x)), s); return s;};
  const noOverflow = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  // fixture through the API: one fresh unacknowledged customer-visible change for this pass
  const ops = await login('backoffice@aftab.test');
  const made = await api('POST', `/operations/trips/${TRIP}/events`, ops.access_token, {command_id: `qa-${vpName}-${Date.now()}`, category: 'room_change', severity: 'warning', source: 'supplier', old_value: {'نوع اتاق': 'دوتخته دبل'}, new_value: {'نوع اتاق': 'دوتخته توئین'}, reason: 'اعلام هتل'});
  check('fixture event recorded', made.status === 201);
  // ---- customer
  await as('employee@aftab.test');
  await page.route('**/trips/*/changes', async route => {await new Promise(res => setTimeout(res, 1200)); await route.continue();});
  await page.goto(`${WEB}/trips/${TRIP}`, {waitUntil: 'domcontentloaded'});
  check('loading state', await page.locator('[role=status]:has-text("در حال دریافت تغییرهای ثبت‌شده")').waitFor({timeout: 5000}).then(() => true).catch(() => false));
  await page.waitForSelector('[data-change-id]'); await page.unroute('**/trips/*/changes');
  const card = page.locator(`[data-change-id="${made.body.id}"]`);
  check('change shows old and new value', /دوتخته دبل/.test(await card.innerText()) && /دوتخته توئین/.test(await card.innerText()) && /قبلی/.test(await card.innerText()) && /تأمین‌کننده/.test(await card.innerText()));
  check('internal event hidden from customer', !(await page.locator('section[aria-labelledby=trip-changes-title]').innerText()).includes('در انتظار پاسخ تأمین‌کننده'));
  const before = await page.locator('[aria-live=polite]').first().innerText();
  await card.locator('button:has-text("دیدم و متوجه شدم")').click(); await card.locator('text=دیده شد').waitFor();
  const after = await page.locator('[aria-live=polite]').first().innerText();
  check('acknowledge updates state', before !== after && !(await card.locator('button').count()), `${before} → ${after}`);
  check('timeline (same source) still renders', (await page.locator('main').innerText()).length > 200);
  check('no horizontal overflow (trip page)', await noOverflow());
  await page.screenshot({path: `${OUT}/ops-customer-${vpName}.png`, fullPage: true});
  await page.goto(`${WEB}/trips/${EMPTY}`, {waitUntil: 'networkidle'});
  check('empty state', await page.locator('text=تا این لحظه تغییری برای این سفر ثبت نشده است').isVisible());
  await page.goto(`${WEB}/trips/00000000-0000-4000-8000-000000000000`, {waitUntil: 'networkidle'});
  check('error state for a trip that is not mine', await page.locator('[role=alert]:has-text("این سفر در حساب شما نیست")').isVisible());
  await page.route('**/trips/*/changes', route => route.abort()); await page.goto(`${WEB}/trips/${TRIP}`, {waitUntil: 'networkidle'});
  check('error state when the service fails', await page.locator('[role=alert]:has-text("دریافت تغییرها انجام نشد")').isVisible()); await page.unroute('**/trips/*/changes');
  await page.goto(`${WEB}/backoffice/trip-events`, {waitUntil: 'networkidle'});
  check('permission state: customer cannot open the operations center', /دسترسی ندارد/.test(await page.locator('main, body').first().innerText()) && !(await page.locator('form[aria-label="ثبت تغییر سفر"]').count()));
  // ---- operations
  await as('backoffice@aftab.test'); await page.goto(`${WEB}/backoffice/trip-events`, {waitUntil: 'networkidle'}); await page.waitForSelector('form[aria-label="ثبت تغییر سفر"]');
  const numbers = await page.$$eval('dl dd', ds => ds.slice(0, 3).map(d => d.textContent));
  check('summary counters', numbers.length === 3, numbers.join('/'));
  const form = page.locator('form[aria-label="ثبت تغییر سفر"]');
  await form.locator('select[name=trip]').selectOption(TRIP); await form.locator('select[name=category]').selectOption('transfer_change'); await form.locator('select[name=severity]').selectOption('critical');
  await form.locator('input[name=field]').fill('ساعت ترانسفر'); await form.locator('input[name=old_value]').fill('۱۰:۰۰'); await form.locator('input[name=new_value]').fill('۱۰:۰۰'); await form.locator('input[name=reason]').fill('اعلام رانندهٔ ترانسفر');
  await form.locator('button.primary').click(); await form.locator('[role=alert]').waitFor();
  check('validation: identical old/new rejected with server message', /متفاوت/.test(await form.locator('[role=alert]').innerText()));
  await form.locator('input[name=new_value]').fill(`۱۲:۳۰ (${vpName})`); await form.locator('button.primary').click(); await form.locator('[role=status]').waitFor();
  const first = page.locator('[data-change-id]').first();
  check('recorded event appears with actor, source and diff', /تغییر ترانسفر/.test(await first.innerText()) && /ثبت‌کننده/.test(await first.innerText()) && new RegExp(`۱۲:۳۰ \\(${vpName}\\)`).test(await first.innerText()) && /مشتری هنوز ندیده است/.test(await first.innerText()));
  await page.locator('[aria-label="فیلتر رویدادها"] select').first().selectOption('hotel_change'); await page.waitForTimeout(800);
  const cats = await page.$$eval('[data-change-id] h3', hs => [...new Set(hs.map(h => h.textContent))]);
  check('filter by category', cats.length === 1 && cats[0] === 'تغییر هتل', cats.join(','));
  await page.locator('[aria-label="فیلتر رویدادها"] select').first().selectOption(''); await page.locator('[aria-label="فیلتر رویدادها"] input[type=checkbox]').check(); await page.waitForTimeout(800);
  check('filter unacknowledged excludes acknowledged and internal', !(await page.locator('[data-change-id]').allInnerTexts()).some(t => /مشتری دیده است|رویداد داخلی/.test(t)));
  await page.locator('[aria-label="فیلتر رویدادها"] select').first().selectOption('tour_change'); await page.waitForTimeout(800);
  check('empty state in the center', await page.locator('text=رویدادی با این شرایط ثبت نشده است').isVisible());
  check('no horizontal overflow (operations center)', await noOverflow());
  await page.locator('[aria-label="فیلتر رویدادها"] select').first().selectOption(''); await page.locator('[aria-label="فیلتر رویدادها"] input[type=checkbox]').uncheck(); await page.waitForTimeout(600);
  await page.screenshot({path: `${OUT}/ops-center-${vpName}.png`, fullPage: vpName === 'desktop'});
  // the customer sees exactly the record operations just created
  const cust = await login('employee@aftab.test'); const seen = await api('GET', `/trips/${TRIP}/changes`, cust.access_token);
  check('customer API returns the same record', seen.body.changes.some(c => c.category === 'transfer_change' && Object.values(c.new_value)[0] === `۱۲:۳۰ (${vpName})`));
  await ctx.clearCookies(); await page.evaluate(() => sessionStorage.clear()); await page.goto(`${WEB}/backoffice/trip-events`, {waitUntil: 'networkidle'});
  check('permission state: anonymous', /وارد شوید/.test(await page.locator('body').innerText()));
  out[vpName] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL')), errors};
  await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await browser.close();
