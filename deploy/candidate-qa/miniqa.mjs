// Round-3 follow-up browser checks: notification requeue button, agency credit link, quote -> booking link. Desktop + mobile.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137';
const psql = q => execSync(`docker exec -i ks-catalog-scratch-pg psql -U postgres -d ks_cand37 -At`, {input: q}).toString().trim();
const login = async email => (await (await fetch(API + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email})})).json());
const call = async (method, path, token, body) => {const r = await fetch(API + path, {method, headers: {'content-type': 'application/json', Authorization: 'Bearer ' + token}, body: body ? JSON.stringify(body) : undefined}); return {status: r.status, body: await r.json().catch(() => null)};};
const browser = await chromium.launch(); const out = {};
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (n, ok, e = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${n}${e ? ' — ' + String(e).slice(0, 100) : ''}`);
  const ctx = await browser.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 100)));
  const as = async email => {const s = await login(email); await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(x => {sessionStorage.clear(); sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x));}, s); return s;};
  const settle = async () => {await page.waitForSelector('p[role=status]', {timeout: 15000}); await page.waitForLoadState('networkidle'); await page.waitForTimeout(700);};
  const text = () => page.locator('main, body').first().innerText();
  // --- requeue a dead-lettered SMS delivery (state set in the candidate DB; nothing is sent: no provider is configured)
  const attempt = psql("update notification_delivery_attempts set status='dead_letter', error_code='provider_not_configured' where id = (select a.id from notification_delivery_attempts a join notifications n on n.id=a.notification_id join trip_events e on e.id=n.trip_event_id where a.channel='sms' and a.status='not_sent' and e.event_key like 'ops-event:%' limit 1) returning id;").split('\n')[0];
  await as('backoffice@aftab.test'); await page.goto(WEB + '/backoffice/notifications', {waitUntil: 'networkidle'}); await page.selectOption('select[aria-label="وضعیت تحویل"]', 'dead_letter'); await page.waitForSelector('button:has-text("ارسال دوباره")');
  await page.locator('button:has-text("ارسال دوباره")').first().click(); await settle();
  check('notifications: requeue button moves a dead-lettered delivery to retry', psql(`select status from notification_delivery_attempts where id='${attempt}'`) === 'retry' && /دوباره در صف ارسال/.test(await text()));
  check('notifications: nothing was actually sent', psql("select count(*) from notification_delivery_attempts where channel in ('sms','push') and status='delivered'") === '0');
  // --- agency credit link through the administration screen
  await as('tenant-admin@aftab.test'); await page.goto(WEB + '/admin/partners', {waitUntil: 'networkidle'}); const card = page.locator('[data-agency="آژانس آزمون QA"]'); await card.waitFor();
  await card.locator('select[name=credit_account_id]').selectOption({index: 1}); await card.locator('form[aria-label="اعتبار آژانس آزمون QA"] button').click(); await settle();
  await as('agency@aftab.test'); await page.goto(WEB + '/agency', {waitUntil: 'networkidle'}); await page.selectOption('select[aria-label="انتخاب آژانس"]', {label: 'آژانس آزمون QA'}); await page.click('[role=tab]:has-text("اعتبار")'); await page.waitForSelector('[data-credit]');
  check('agency credit: limit and ledger balances shown after linking', /سقف اعتبار/.test(await text()) && /۵۰۰٬۰۰۰٬۰۰۰/.test(await text()));
  // --- quote -> accepted -> booking on the agency channel -> linked in the agency panel
  const agent = await login('agency@aftab.test'), cust = await login('employee@aftab.test');
  const agency = (await call('GET', '/agency/workspace', agent.access_token)).body.agencies.find(a => a.name === 'آژانس آزمون QA').id;
  const offer = (await call('GET', `/agency/${agency}/offers`, agent.access_token)).body.items[0].id; const custId = Number(psql("select id from users where email='employee@aftab.test'"));
  const quote = (await call('POST', `/agency/${agency}/quotes`, agent.access_token, {offer_id: offer, customer_user_id: custId})).body;
  check('quote flow: accept through API', (await call('POST', `/me/agency-quotes/${quote.id}/decision`, cust.access_token, {decision: 'accept'})).body.status === 'accepted');
  const rid = psql(`insert into reservations (id, tenant_id, user_id, service_type, status, sales_channel_id, booking_reference, price_snapshot_json, policy_at_booking_json, current_policy_json, version, created_at, updated_at) select gen_random_uuid()::text, a.tenant_id, ${custId}, 'hotel', 'reserved', a.sales_channel_id, 'QA-' || substr(md5(random()::text),1,8), '{"total_amount": 18000000, "currency": "IRR"}', '{}', '{}', 1, now(), now() from agencies a where a.id='${agency}' returning id;`).split('\n')[0];
  await page.goto(WEB + '/agency', {waitUntil: 'networkidle'}); await page.selectOption('select[aria-label="انتخاب آژانس"]', {label: 'آژانس آزمون QA'}); await page.click('[role=tab]:has-text("پیشنهاد قیمت")'); await page.waitForSelector('[data-quotes] tbody tr');
  const row = page.locator('[data-quotes] tbody tr').first();
  await row.locator('input[name=reservation_id]').fill('00000000-0000-4000-8000-000000000000'); await row.locator('button:has-text("وصل به رزرو")').click(); await page.waitForSelector('p[role=alert]'); check('quote flow: unrelated reservation rejected', /هم‌خوان نیست/.test(await page.locator('p[role=alert]').first().innerText()));
  await row.locator('input[name=reservation_id]').fill(rid); await row.locator('button:has-text("وصل به رزرو")').click(); await settle();
  check('quote flow: linked to the customer booking, status booked', /رزروشده/.test(await page.locator('[data-quotes] tbody tr').first().innerText()) && psql(`select status from agency_quotes where id='${quote.id}'`) === 'booked');
  check('quote flow: no horizontal overflow', await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth));
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL')), errors}; await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await browser.close();
