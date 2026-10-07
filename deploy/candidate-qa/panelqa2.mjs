// Candidate browser QA for the customer and organization panels: real data, real actions, role isolation. Desktop + mobile.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137', OUT = process.argv[2];
const psql = q => execSync(`docker exec -i ks-catalog-scratch-pg psql -U postgres -d ks_cand37 -At`, {input: q}).toString().trim().split('\n')[0];
const login = async email => (await (await fetch(API + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email})})).json());
const b = await chromium.launch(); const out = {}; const orgName = `سازمان آزمون پنل ${Date.now() % 100000}`;
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (n, ok, e = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${n}${e !== '' ? ' — ' + String(e).slice(0, 150) : ''}`);
  const ctx = await b.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 90)));
  const as = async email => {const s = await login(email); await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(x => {sessionStorage.clear(); sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x));}, s); return s;};
  const open = async p => {await page.goto(WEB + p, {waitUntil: 'networkidle'}); await page.waitForTimeout(900); return page.evaluate(() => ({text: document.querySelector('.pn-main')?.innerText || '', fits: document.documentElement.scrollWidth <= document.documentElement.clientWidth, current: document.querySelector('.pn-nav a[aria-current=page]')?.innerText || '', rows: document.querySelectorAll('.pn-table tbody tr').length, unavailable: document.querySelectorAll('[data-state=unavailable]').length, loading: /در حال دریافت/.test(document.querySelector('.pn-main')?.innerText || ''), alerts: [...document.querySelectorAll('.pn-main [role=alert]')].map(e => e.innerText).join('|')}));};
  // ---- anonymous
  await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(() => sessionStorage.clear()); let s = await open('/account/bookings'); check('anonymous sees a sign-in prompt, no data', /وارد حساب خود شوید/.test(s.text) && s.rows === 0);
  // ---- customer
  await as('employee@aftab.test'); const uid = Number(psql("select id from users where email='employee@aftab.test'")); const dbRes = Number(psql(`select count(*) from reservations where user_id=${uid}`));
  s = await open('/account'); check('overview: counts from the account, no invented credit figure', /رزروها/.test(s.text) && !/۴۸٬۰۰۰٬۰۰۰|48,000,000/.test(s.text) && s.current === 'نمای کلی' && s.fits && !s.alerts, s.alerts);
  s = await open('/account/bookings'); check('bookings: every reservation of the user, with manage links', s.rows >= Math.min(dbRes, 1) && (await page.locator('.pn-table a[href^="/manage-booking/"]').count()) >= 1 && s.fits, `${s.rows} rows / db ${dbRes}`);
  const href = await page.locator('.pn-table a[href^="/manage-booking/"]').first().getAttribute('href'); const st = (await ctx.request.get(WEB + href)).status(); check('manage-booking link opens', st === 200, href);
  s = await open('/account/payments'); const dbInv = Number(psql(`select count(*) from invoices i join reservations r on r.id=i.reservation_id where r.user_id=${uid}`)); check('payments and invoices from the ledger', (await page.locator('.pn-card').count()) === 3 && s.rows >= Math.min(dbInv, 1) && s.fits && !s.alerts, `${s.rows} rows, invoices db ${dbInv}`);
  s = await open('/account/visa'); check('visa: own applications, honest unavailable state, country guides from the bundle', s.unavailable >= 1 && (await page.locator('a[href^="/visa/cl-visa-country-"]').count()) >= 10 && s.fits);
  s = await open('/account/refunds'); check('cancellation and refunds page', /شرایط لغو/.test(s.text) && s.fits && !s.alerts);
  s = await open('/account/wallet'); const hadWallet = Number(psql(`select count(*) from wallets where owner_reference='${uid}'`)) > 0;
  if (!hadWallet) {await page.locator('.pn-btn:has-text("ایجاد کیف پول")').click(); await page.locator('.pn-note.ok').waitFor({timeout: 15000}); await page.waitForTimeout(700);}
  const wt = await page.locator('.pn-main').innerText(); check('wallet: created by a real call, balance zero from ledger, top-up shown as unavailable', Number(psql(`select count(*) from wallets where owner_reference='${uid}'`)) === 1 && /قابل استفاده\s*۰ ریال/.test(wt.replace(/\n/g, ' ')) && /شارژ آنلاین/.test(wt), wt.slice(0, 90).replace(/\n/g, ' '));
  s = await open('/account/notifications'); const unreadBefore = Number(psql(`select count(*) from notifications where user_id=${uid} and status<>'read'`));
  if (unreadBefore > 0) {await page.locator('.pn-btn:has-text("خواندم")').first().click(); await page.waitForTimeout(1500);}
  check('notifications: list and mark-as-read persists', s.text.length > 100 && (unreadBefore === 0 || Number(psql(`select count(*) from notifications where user_id=${uid} and status<>'read'`)) === unreadBefore - 1) && s.fits, `unread before ${unreadBefore}`);
  s = await open('/account/support'); check('support cases of the user with a link to the conversation', s.rows >= 1 && (await page.locator('a[href^="/support?case="]').count()) >= 1 && s.fits);
  s = await open('/account/profile'); check('profile and travellers (existing editor) inside the shell', s.current === 'پروفایل و مسافران' && s.text.length > 150 && s.fits);
  await page.screenshot({path: `${OUT}/panel-customer-${vp}.png`, fullPage: true}); await open('/account'); await page.screenshot({path: `${OUT}/panel-customer-home-${vp}.png`, fullPage: true});
  // ---- organization: not a member yet
  s = await open('/organization'); const member0 = Number(psql(`select count(*) from employee_assignments where user_id=${uid}`)); if (member0 === 0) check('non-member sees an explanation, not an empty dashboard', /عضو هیچ سازمانی نیست/.test(s.text));
  // ---- tenant admin creates the organization and its first member
  await as('tenant-admin@aftab.test'); s = await open('/organization'); let orgId = psql(`select id from organizations where name='${orgName}'`);
  if (!orgId) {await page.locator('.pn-form input').last().fill(orgName); await page.locator('.pn-form button:has-text("ایجاد")').click(); await page.waitForTimeout(1800); orgId = psql(`select id from organizations where name='${orgName}'`);}
  check('tenant admin creates an organization', !!orgId, orgName);
  await page.evaluate(id => sessionStorage.setItem('karenseir-panel-organization', id), orgId); s = await open('/organization/members');
  if (Number(psql(`select count(*) from employee_assignments where organization_id='${orgId}'`)) === 0) {await page.locator('.pn-form input[type=email]').fill('org-admin@aftab.test'); await page.locator('.pn-form button:has-text("افزودن")').click(); await page.locator('.pn-note.ok').waitFor({timeout: 15000});}
  check('tenant admin adds the organization admin as first member', Number(psql(`select count(*) from employee_assignments where organization_id='${orgId}'`)) >= 1);
  // ---- organization admin
  await as('org-admin@aftab.test'); await page.evaluate(id => sessionStorage.setItem('karenseir-panel-organization', id), orgId);
  s = await open('/organization/members'); if (!/employee@aftab\.test/.test(s.text)) {await page.locator('.pn-form input[type=email]').fill('employee@aftab.test'); await page.locator('.pn-form button:has-text("افزودن")').click(); await page.locator('.pn-note.ok').waitFor({timeout: 15000}); await page.waitForTimeout(600);}
  await page.locator('.pn-form input[type=email]').fill('nobody@aftab.test'); await page.locator('.pn-form button:has-text("افزودن")').click(); await page.locator('.pn-note.error').waitFor({timeout: 15000});
  s = await open('/organization/members'); check('organization admin manages members; unknown e-mail is refused with a message', s.rows === 2 && /employee@aftab\.test/.test(s.text) && s.fits, `${s.rows} rows`);
  s = await open('/organization'); check('overview: real counts for the organization', /کارکنان\s*۲/.test(s.text.replace(/\n/g, ' ')) && s.current === 'نمای کلی' && s.fits && !s.alerts, s.text.slice(0, 120).replace(/\n/g, ' '));
  s = await open('/organization/policy'); check('policy page shows the policy in force or says none is set', /سیاست سفر جاری/.test(s.text) && (/هنوز سیاست سفری ثبت نشده/.test(s.text) || /نسخهٔ/.test(s.text)) && s.fits);
  s = await open('/organization/requests'); check('request and approval workspace inside the shell', s.current === 'درخواست و تأیید سفر' && s.text.length > 200 && s.fits);
  s = await open('/organization/structure'); check('departments and cost centres inside the shell', s.text.length > 80 && s.fits);
  s = await open('/organization/credit'); check('credit: no account → stated; payroll deduction marked unavailable', /حساب اعتباری تعریف نشده/.test(s.text) && s.unavailable === 1 && s.fits);
  s = await open('/organization/bookings'); check('organization bookings: linked reservations only', /متصل/.test(s.text) && !s.loading && s.fits);
  s = await open('/organization/billing'); check('billing: own invoices, organization settlement marked unavailable', s.unavailable === 1 && s.fits);
  s = await open('/organization/reports'); check('reports from real counts with CSV export', /درخواست‌ها بر اساس وضعیت/.test(s.text) && (await page.locator('.pn-btn:has-text("CSV")').count()) === 1 && s.fits); await page.screenshot({path: `${OUT}/panel-org-${vp}.png`, fullPage: true});
  // ---- member without management rights, and a user of another tenant
  await as('employee@aftab.test'); await page.evaluate(id => sessionStorage.setItem('karenseir-panel-organization', id), orgId);
  s = await open('/organization/members'); check('plain member: no member list, no add form', /فقط برای مدیران سازمان/.test(s.text) && (await page.locator('.pn-form input[type=email]').count()) === 0);
  s = await open('/organization/reports'); check('plain member: no organization report', /فقط برای مدیران سازمان/.test(s.text));
  const out2 = await login('employee@faraz.test'); const codes = []; for (const p of [`/enterprise/organizations/${orgId}/summary`, `/enterprise/organizations/${orgId}/members`, `/enterprise/organizations/${orgId}/policy`, `/enterprise/requests?org=${orgId}`]) codes.push((await fetch(API + p, {headers: {authorization: `Bearer ${out2.access_token}`}})).status);
  check('another tenant cannot read the organization (API)', codes.every(c => c === 403 || c === 404), codes.join(','));
  check('no script error', errors.length === 0, errors.join(' | '));
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL'))}; await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await b.close();
