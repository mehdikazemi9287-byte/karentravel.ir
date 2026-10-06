// Candidate browser QA: reference admin (search, filter, completeness, edit), destination guides fed by the catalogue, service routes. Desktop + mobile.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137', OUT = process.argv[2];
const psql = q => execSync(`docker exec -i ks-catalog-scratch-pg psql -U postgres -d ks_cand37 -At`, {input: q}).toString().trim().split('\n')[0];
const login = async email => (await (await fetch(API + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email})})).json());
const browser = await chromium.launch(); const out = {};
const airport = psql("select id from catalog_airports where name_fa is null and updated_by is null and source='ourairports' order by id limit 1");
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (n, ok, e = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${n}${e !== '' ? ' — ' + String(e).slice(0, 140) : ''}`);
  const ctx = await browser.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 100)));
  const fits = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const open = async p => {const res = await page.goto(WEB + p, {waitUntil: 'networkidle'}); await page.waitForTimeout(500); return res;};
  // ---------- public: destination guide cards lead to catalogue-fed pages
  await open('/destinations'); check('destinations index keeps its six guide cards', (await page.locator('a.customer-destination').count()) === 6);
  for (const slug of ['shiraz', 'kish', 'yazd']) {
    const res = await open('/destinations/' + slug); await page.waitForSelector('.cat-place h1', {timeout: 15000}).catch(() => {}); const t = await page.locator('main').first().innerText();
    check(`/destinations/${slug} is fed by the catalogue record`, res.status() === 200 && (await page.locator('.cat-place').count()) === 1 && (await page.locator('.cat-place .cat-crumbs a').count()) >= 2 && !/برای برنامه‌ریزی سفر/.test(t) && await fits(), t.slice(0, 60).replace(/\n/g, ' '));
  }
  check('guide page canonical points at the catalogue place', ((await page.locator('link[rel=canonical]').getAttribute('href').catch(() => '')) || '').includes('/destinations/cl-city-'));
  await page.screenshot({path: `${OUT}/ref-destination-${vp}.png`, fullPage: true});
  for (const p of ['/services', '/visa', '/attractions', '/flights', '/hotels', '/tours', '/tours/search', '/travel-guides', '/contact', '/support', '/terms', '/handicrafts', '/villas', '/trains']) {
    const res = await ctx.request.get(WEB + p, {maxRedirects: 3}); if (res.status() !== 200) check(`route ${p}`, false, res.status());
  }
  check('service and vertical routes answer 200', !r.some(x => x.startsWith('FAIL route')));
  // ---------- admin: anonymous is refused, platform admin works
  await open('/admin/catalog/reference'); check('reference admin asks an anonymous visitor to sign in', /وارد شوید/.test(await page.locator('main').first().innerText()));
  const s = await login('platform-admin@aftab.test'); await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(x => sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x)), s);
  await open('/admin/catalog/reference'); await page.waitForSelector('.cadm-list button', {timeout: 15000});
  check('completeness summary for seven kinds', (await page.locator('.cadm-state').first().locator('div').count()) === 7);
  check('places listed with completeness', (await page.locator('.cadm-list button').count()) === 30 && /٪ کامل/.test(await page.locator('.cadm-list button').first().innerText()));
  const total = await page.locator('.cadm-count').innerText();
  await page.locator('.cadm-bar select').selectOption('country'); await page.locator('.cadm-bar button[type=submit]').click(); await page.waitForTimeout(900);
  check('filter by place type', (await page.locator('.cadm-count').innerText()) !== total && /۵۰ رکورد/.test(await page.locator('.cadm-count').innerText()), await page.locator('.cadm-count').innerText());
  await page.locator('.cadm-bar input').first().fill('تایلند'); await page.locator('.cadm-bar button[type=submit]').click(); await page.waitForTimeout(900);
  check('search finds the country', (await page.locator('.cadm-list button').count()) >= 1 && /تایلند/.test(await page.locator('.cadm-list button').first().innerText()));
  await page.locator('.cadm-list button').first().click(); await page.waitForSelector('.cadm-form'); const d = await page.locator('.cadm-form').innerText();
  check('place detail: relations and provenance', /هتل/.test(d) && /تور/.test(d) && /فرودگاه/.test(d) && /منبع/.test(d) && await fits());
  // ---------- edit an airport: completeness rises, record becomes admin-owned
  await page.locator('.cadm-checks label', {hasText: 'فرودگاه‌ها'}).click(); await page.waitForSelector('.cadm-list button');
  await page.locator('.cadm-bar label.cadm-inline input').check(); await page.locator('.cadm-bar input').first().fill(airport); await page.locator('.cadm-bar button[type=submit]').click(); await page.waitForTimeout(900);
  const before = await page.locator('.cadm-list button').first().innerText(); check('incomplete filter shows what is missing', /خالی: .*نام فارسی/.test(before), before.replace(/\n/g, ' '));
  await page.locator('.cadm-list button').first().click(); await page.waitForSelector('.cadm-form');
  const nameFa = `فرودگاه آزمون ${vp}`; await page.locator('.cadm-grid label', {hasText: 'نام فارسی'}).locator('input').fill(nameFa); await page.locator('.cadm-form button.primary').click(); await page.locator('.cadm-note.ok').waitFor({timeout: 15000});
  const row = psql(`select name_fa||'|'||(updated_by is not null) from catalog_airports where id='${airport}'`);
  check('airport edit is saved, audited and admin-owned', row === `${nameFa}|true` && /ویرایش‌شده در پنل/.test(await page.locator('.cadm-form').innerText()) && Number(psql(`select count(*) from audit_events where action='catalog_reference.updated' and created_at > now() - interval '1 minute'`)) >= 1, row);
  await page.locator('.cadm-grid label', {hasText: 'عرض'}).count();
  await page.screenshot({path: `${OUT}/ref-admin-${vp}.png`, fullPage: true});
  // ---------- other kinds load; visa edit rejects an empty body
  for (const label of ['ایرلاین‌ها', 'جاذبه‌ها', 'راهنمای ویزا']) {await page.locator('.cadm-checks label', {hasText: label}).click(); await page.waitForSelector('.cadm-list button', {timeout: 15000}); check(`${label}: listed`, (await page.locator('.cadm-list button').count()) >= 1);}
  await page.locator('.cadm-list button').first().click(); await page.waitForSelector('.cadm-form'); await page.locator('.cadm-form textarea').fill(''); await page.locator('.cadm-form button.primary').click(); await page.locator('.cadm-note.error').waitFor({timeout: 15000});
  check('visa guide: empty text is refused with a message', /نمی‌تواند خالی باشد/.test(await page.locator('.cadm-note.error').innerText()));
  // ---------- hotel and tour lists show what is missing
  await open('/admin/catalog'); await page.waitForSelector('.cadm-list button'); await page.locator('.cadm-bar select').nth(1).selectOption('incomplete'); await page.locator('.cadm-bar button[type=submit]').click(); await page.waitForTimeout(1200);
  check('hotel list names the missing parts', /خالی: /.test(await page.locator('.cadm-list').innerText()));
  await page.locator('.cadm-bar input').first().fill('cl-13033'); await page.locator('.cadm-bar select').nth(1).selectOption(''); await page.locator('.cadm-bar button[type=submit]').click(); await page.waitForTimeout(1200);
  check('a hotel without a country is in the panel as a draft', (await page.locator('.cadm-list button').count()) === 1 && /ZZ/.test(await page.locator('.cadm-list').innerText()));
  await page.locator('.cadm-list button').first().click(); await page.waitForSelector('.cadm-form', {timeout: 15000}).catch(() => {}); check('…and opens for completion', (await page.locator('.cadm-form').count()) >= 1 && errors.length === 0, errors.join(' | '));
  await open('/admin/tours'); await page.waitForSelector('ul button.grid'); check('tour list shows completeness', /محتوای کامل|خالی: /.test(await page.locator('ul:has(button.grid)').first().innerText()));
  // ---------- a role without the right is refused by the API
  const cust = await login('employee@aftab.test'); const res = await fetch(API + '/admin/catalog/reference/places', {headers: {authorization: `Bearer ${cust.access_token}`}}); check('customer role is refused (403)', res.status === 403, res.status);
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL')), errors}; await ctx.close();
  execSync(`docker exec -i ks-catalog-scratch-pg psql -U postgres -d ks_cand37 -At`, {input: `update catalog_airports set name_fa=null, updated_by=null, updated_at=null, search_text=replace(search_text, 'فرودگاه ازمون ${vp}', '') where id='${airport}'`});
}
console.log(JSON.stringify(out, null, 1)); await browser.close();
