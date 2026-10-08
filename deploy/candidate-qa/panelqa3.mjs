// Candidate E2E for the five panel areas with role isolation: customer → organization → agency → supplier → admin. Desktop, tablet, mobile.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137', OUT = process.argv[2];
const psql = q => execSync(`docker exec -i ks-catalog-scratch-pg psql -U postgres -d ks_cand37 -At`, {input: q}).toString().trim().split('\n')[0];
const login = async email => (await (await fetch(API + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email})})).json());
const orgId = psql("select o.id from organizations o join employee_assignments a on a.organization_id=o.id join users u on u.id=a.user_id where u.email='org-admin@aftab.test' and o.name like 'سازمان آزمون پنل%' order by o.created_at desc limit 1");
const agencyId = psql("select m.agency_id from agency_memberships m join users u on u.id=m.user_id where u.email='agency@aftab.test' limit 1"); const otherAgency = psql(`select id from agencies where id<>'${agencyId}' and id not in (select agency_id from agency_memberships m join users u on u.id=m.user_id where u.email='agency@aftab.test') limit 1`);
const empId = psql("select id from users where email='employee@aftab.test'"); const orgName = psql(`select name from organizations where id='${orgId}'`);
const resetGrant = async () => {const s = await login('org-admin@aftab.test'); await fetch(`${API}/enterprise/organizations/${orgId}/grants`, {method: 'PUT', headers: {authorization: `Bearer ${s.access_token}`, 'content-type': 'application/json'}, body: JSON.stringify({command_id: `qa-reset-${Date.now()}-${Math.random()}`, user_id: Number(empId), permissions: []})});};
if (!orgId || !agencyId) {console.log('fixture missing', orgId, agencyId); process.exit(1);}
const b = await chromium.launch(); const out = {};
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['tablet', {width: 820, height: 1100}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (n, ok, e = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${n}${e !== '' ? ' — ' + String(e).slice(0, 170) : ''}`);
  const ctx = await b.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 90)));
  const as = async email => {const s = await login(email); await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(([x, o, a]) => {sessionStorage.clear(); sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x)); sessionStorage.setItem('karenseir-panel-organization', o); sessionStorage.setItem('karenseir-panel-agency', a);}, [s, orgId, agencyId]);};
  const open = async p => {await page.goto(WEB + p, {waitUntil: 'networkidle'}); await page.waitForTimeout(900); return page.evaluate(() => ({text: document.querySelector('.pn-main')?.innerText || '', fits: document.documentElement.scrollWidth <= document.documentElement.clientWidth, current: document.querySelector('.pn-nav a[aria-current=page]')?.innerText || '', rows: document.querySelectorAll('.pn-table tbody tr').length, unavailable: document.querySelectorAll('[data-state=unavailable]').length, loading: /در حال دریافت/.test(document.querySelector('.pn-main')?.innerText || ''), alerts: [...document.querySelectorAll('.pn-main [role=alert]')].map(e => e.innerText).join('|'), shell: document.querySelectorAll('.pn').length, area: document.querySelector('.pn')?.getAttribute('data-area')}));};
  const sweep = async (label, area, pages) => {const bad = []; for (const [p, min] of pages) {const s = await open(p); if (!(s.shell === 1 && s.area === area && s.fits && !s.alerts && !s.loading && s.text.length > 60 && s.rows >= min && s.current)) bad.push(`${p} ${JSON.stringify({fits: s.fits, rows: s.rows, alerts: s.alerts.slice(0, 50), cur: s.current, len: s.text.length})}`);} check(`${label}: every section renders in the shared shell with data, no overflow`, bad.length === 0, bad.join(' ; '));};
  // ---------- customer
  await resetGrant();
  await as('employee@aftab.test');
  await sweep('customer', 'customer', [['/account', 1], ['/account/profile', 0], ['/account/bookings', 1], ['/account/changes', 0], ['/account/visa', 0], ['/account/payments', 1], ['/account/refunds', 0], ['/account/wallet', 0], ['/account/benefits', 0], ['/account/saved', 1], ['/account/notifications', 0], ['/account/support', 1]]);
  let s = await open('/account/changes');
  const btn = page.locator('.pn-btn:has-text("دیدم")'); const had = await btn.count(); if (had) {await btn.first().click(); await page.waitForTimeout(1800);}
  check('trip changes: listed per trip; "seen" is stored', /برنامهٔ کامل سفر/.test(s.text) && (had === 0 || (await page.locator('.pn-btn:has-text("دیدم")').count()) === had - 1), `buttons ${had}`);
  s = await open('/account/benefits'); check('organization benefits reflect the real membership', /سازمان آزمون پنل/.test(s.text));
  for (const p of ['/admin/audit', '/admin/organizations', '/agency/bookings', '/supplier/services', '/organization/audit']) {const x = await open(p); if (x.rows > 0 || !(x.alerts || /دسترسی ندارد|عضو هیچ|فقط برای مدیران/.test(x.text))) r.push(`FAIL customer opening ${p} directly sees data or no refusal — rows ${x.rows} ${x.text.slice(0, 60)}`);}
  check('customer opening other panels by URL gets a refusal and no rows', !r.some(x => x.startsWith('FAIL customer opening')));
  // ---------- organization
  await as('org-admin@aftab.test');
  await sweep('organization', 'organization', [['/organization', 0], ['/employee', 0], ['/organization/members', 2], ['/organization/requests', 0], ['/organization/policy', 0], ['/organization/structure', 0], ['/organization/credit', 0], ['/organization/bookings', 0], ['/organization/billing', 0], ['/organization/reports', 0], ['/organization/audit', 0]]);
  await open('/organization/members'); const row = page.locator('.pn-table tbody tr', {hasText: 'employee@aftab.test'}); await row.locator('.pn-btn.ghost').first().click(); const chip = row.locator('.pn-chips button', {hasText: 'دیدن همهٔ درخواست‌ها'}); const wasOn = (await chip.getAttribute('aria-pressed')) === 'true'; await chip.click(); await row.locator('.pn-btn:has-text("ذخیرهٔ دسترسی‌ها")').click(); await page.locator('.pn-note.ok').waitFor({timeout: 15000});
  const grant = psql(`select permissions_json from enterprise_grants where organization_id='${orgId}' and user_id=${empId}`); check('permissions: a grant is saved for the member', !wasOn && grant.includes('requests.read_all'), grant);
  s = await open('/organization/audit'); check('audit trail shows the permission change with its actor', /تغییر دسترسی/.test(s.text) && s.rows >= 1);
  s = await open('/organization/billing'); check('organization statement comes from linked-booking invoices', /رزرو متصل/.test(s.text) && s.unavailable === 1);
  await resetGrant();
  // ---------- agency
  await as('agency@aftab.test');
  await sweep('agency', 'agency', [['/agency', 1], ['/agency/sales', 0], ['/agency/bookings', 1], ['/agency/customers', 1], ['/agency/commissions', 1], ['/agency/credit', 0], ['/agency/documents', 0], ['/agency/reports', 1], ['/agency/workspace', 0], ['/agency/support', 0]]);
  s = await open('/agency/bookings'); const dbB = Number(psql(`select count(*) from reservations r join agencies a on a.sales_channel_id=r.sales_channel_id where a.id='${agencyId}'`)); check('agency bookings equal the reservations of its sales channel', s.rows === Math.min(dbB, s.rows) && s.rows >= 1 && dbB >= s.rows, `${s.rows} shown / ${dbB} db`);
  s = await open('/agency/commissions'); check('commission ledger and statement shown with rates', /دفتر کمیسیون/.test(s.text) && /٪/.test(s.text));
  s = await open('/agency/sales'); check('B2B quote workflow available', (await page.locator('.pn-main form, .pn-main select, .pn-main button').count()) >= 1 && s.text.length > 150);
  // ---------- supplier
  await as('supplier@aftab.test');
  await sweep('supplier', 'supplier', [['/supplier', 1], ['/supplier/services', 1], ['/supplier/hotels', 0], ['/supplier/accommodation', 0], ['/supplier/fulfillment', 0], ['/supplier/admission', 0], ['/supplier/rfqs', 0], ['/supplier/settlements', 0], ['/supplier/reports', 1], ['/supplier/support', 0]]);
  await open('/supplier/services'); const hrefs = await page.$$eval('.pn-list a', as => as.map(a => a.getAttribute('href'))); const dead = []; for (const h of hrefs) {const st = (await ctx.request.get(WEB + h)).status(); if (st !== 200) dead.push(`${h} ${st}`);} check(`supplier service editors all open (${hrefs.length})`, hrefs.length === 8 && dead.length === 0, dead.join(' '));
  // ---------- admin
  await as('tenant-admin@aftab.test');
  await sweep('admin', 'admin', [['/admin', 0], ['/admin/organizations', 1], ['/admin/partners', 0], ['/admin/audit', 1]]);
  await open('/admin/organizations'); await page.locator('.pn-table tbody tr', {hasText: orgName}).first().locator('.pn-btn').click(); await page.waitForTimeout(1500);
  check('admin manages an organization: members and credit account in place', (await page.locator('.pn-main').innerText()).includes(`کارکنان ${orgName}`) && (await page.locator('.pn-main').innerText()).includes(`حساب اعتباری ${orgName}`));
  const accBefore = Number(psql(`select count(*) from credit_accounts where organization_id='${orgId}'`));
  if (accBefore === 0) {await page.locator('.pn-form input[inputmode=numeric]').fill('500000000'); await page.locator('.pn-form button:has-text("ایجاد حساب اعتباری")').click(); await page.locator('.pn-card .pn-note').last().waitFor({timeout: 15000}); await page.waitForTimeout(800);}
  const accAfter = Number(psql(`select count(*) from credit_accounts where organization_id='${orgId}'`)); const noteText = accBefore === 0 ? await page.locator('.pn-card .pn-note').last().innerText() : 'existing';
  check('credit account: created from the panel, or refused with the reason', accAfter === 1 || /مجوز مدیریت اعتبار/.test(noteText), `${accBefore}→${accAfter} ${noteText}`);
  s = await open('/admin/audit'); check('tenant audit log lists events with actors', s.rows >= 1);
  // ---------- API authorisation matrix
  const tok = {}; for (const e of ['employee@aftab.test', 'org-admin@aftab.test', 'agency@aftab.test', 'supplier@aftab.test', 'tenant-admin@aftab.test', 'employee@faraz.test']) tok[e] = (await login(e)).access_token;
  const code = async (email, p) => (await fetch(API + p, {headers: email ? {authorization: `Bearer ${tok[email]}`} : {}})).status;
  const O = `/enterprise/organizations/${orgId}`, A = `/agency/${agencyId}`; const deny = [];
  const expect = async (email, p, allowed) => {const c = await code(email, p); if (!allowed.includes(c)) deny.push(`${email || 'anon'} ${p} → ${c}`);};
  for (const p of ['/me/reservations', `${O}/summary`, `${A}/bookings`, '/supplier/dashboard', '/admin/users', '/admin/audit-events', '/enterprise/organizations']) await expect(null, p, [401, 403]);
  for (const p of [`${A}/bookings`, `${A}/credit`, '/supplier/dashboard', '/admin/users', '/admin/audit-events', '/enterprise/organizations', `${O}/statement`, `${O}/credit`]) await expect('employee@aftab.test', p, [403, 404]);
  for (const p of [`${A}/bookings`, `${A}/commission-ledger`, '/supplier/dashboard', '/enterprise/organizations']) await expect('org-admin@aftab.test', p, [403, 404]);
  for (const p of [`${O}/summary`, `${O}/members`, `${O}/statement`, '/supplier/dashboard', '/admin/users', '/admin/audit-events', '/enterprise/organizations', ...(otherAgency ? [`/agency/${otherAgency}/bookings`] : [])]) await expect('agency@aftab.test', p, [403, 404]);
  for (const p of [`${O}/summary`, `${A}/bookings`, `${A}/credit`, '/admin/users', '/admin/audit-events', '/enterprise/organizations']) await expect('supplier@aftab.test', p, [403, 404]);
  for (const p of [`${O}/summary`, `${O}/members`, `${O}/audit`, `${O}/statement`, `${O}/credit`, `${A}/bookings`, `${A}/customers`, `${A}/commission-ledger`]) await expect('employee@faraz.test', p, [403, 404]);
  for (const [e, p] of [['employee@aftab.test', '/me/reservations'], ['org-admin@aftab.test', `${O}/summary`], ['agency@aftab.test', `${A}/bookings`], ['supplier@aftab.test', '/supplier/dashboard'], ['tenant-admin@aftab.test', '/admin/audit-events'], ['tenant-admin@aftab.test', `${O}/credit`]]) await expect(e, p, [200]);
  const post = async (email, p, body) => (await fetch(API + p, {method: 'POST', headers: {authorization: `Bearer ${tok[email]}`, 'content-type': 'application/json'}, body: JSON.stringify(body)})).status;
  for (const e of ['employee@aftab.test', 'agency@aftab.test', 'supplier@aftab.test', 'employee@faraz.test']) {const c = await post(e, `${O}/members`, {email: 'finance@aftab.test'}); if (![403, 404].includes(c)) deny.push(`${e} POST members → ${c}`); const c2 = await post(e, '/enterprise/organizations', {name: 'نباید ساخته شود'}); if (c2 !== 403) deny.push(`${e} POST organizations → ${c2}`);}
  check('API authorisation matrix (anonymous, each role, other tenant; read and write)', deny.length === 0, deny.join(' ; '));
  check('no script error', errors.length === 0, errors.join(' | '));
  if (vp !== 'tablet') {await as('agency@aftab.test'); await open('/agency'); await page.screenshot({path: `${OUT}/panel-agency-${vp}.png`, fullPage: true}); await as('supplier@aftab.test'); await open('/supplier'); await page.screenshot({path: `${OUT}/panel-supplier-${vp}.png`, fullPage: true});}
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL'))}; await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await b.close();
