// Re-verification of screens that existed before these rounds (no change made to them): render, API health, layout.
import {chromium} from 'playwright';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137';
const PAGES = {'employee@aftab.test': ['/employee', '/account', '/trips', '/notifications', '/saved-trips', '/organization/requests'], 'org-admin@aftab.test': ['/organization', '/organization/requests', '/organization/structure', '/admin'],
  'welfare@aftab.test': ['/organization', '/organization/requests'], 'supplier@aftab.test': ['/supplier', '/supplier/accommodation', '/supplier/offers/new', '/supplier/fulfillment', '/supplier/train', '/supplier/transport', '/supplier/guides'],
  'tenant-admin@aftab.test': ['/admin', '/white-label', '/backoffice'], 'backoffice@aftab.test': ['/backoffice', '/backoffice/booking-requests', '/backoffice/trips', '/backoffice/records'], 'finance@aftab.test': ['/finance']};
const browser = await chromium.launch(); const rows = [];
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  for (const [email, paths] of Object.entries(PAGES)) {
    const ctx = await browser.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); let js = 0, api5 = [], api4 = [];
    page.on('pageerror', () => js++); page.on('response', res => {if (res.url().startsWith(API)) {if (res.status() >= 500) api5.push(new URL(res.url()).pathname + ' ' + res.status()); else if (res.status() === 403 || res.status() === 404) api4.push(new URL(res.url()).pathname + ' ' + res.status());}});
    const s = await (await fetch(API + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email})})).json();
    await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(x => sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x)), s);
    for (const p of paths) {
      js = 0; api5 = []; api4 = [];
      const res = await page.goto(WEB + p, {waitUntil: 'networkidle'}); await page.waitForTimeout(700);
      const info = await page.evaluate(() => ({len: (document.querySelector('main')?.innerText ?? document.body.innerText).length, fits: document.documentElement.scrollWidth <= document.documentElement.clientWidth, denied: /نقش شما به این بخش دسترسی ندارد|دریافت اطلاعات انجام نشد|فعلاً در دسترس نیست/.test(document.body.innerText)}));
      rows.push({vp, role: email.split('@')[0], p, http: res.status(), js, api5, api4: api4.slice(0, 2), ...info});
    }
    await ctx.close();
  }
}
const bad = rows.filter(r => r.http !== 200 || r.js || r.api5.length || !r.fits || r.len < 80 || r.denied);
console.log('checked', rows.length, 'clean', rows.length - bad.length); bad.forEach(b => console.log('  ', JSON.stringify(b)));
await browser.close();
