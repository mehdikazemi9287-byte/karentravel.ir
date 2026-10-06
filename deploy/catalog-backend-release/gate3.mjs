// Compatibility gate, part 3: the CURRENT production frontend image, driven once against the old API and once
// against the new API (same data). Browser calls to the baked production API URL are rewritten to the gate APIs.
import {chromium} from 'playwright';
import fs from 'fs';
const WEB = 'http://127.0.0.1:3398', PROD_API = 'http://95.38.184.209:8000', OUT = process.argv[2]; fs.mkdirSync(OUT, {recursive: true});
const APIS = {old: 'http://127.0.0.1:18134', new: 'http://127.0.0.1:18138'};
const PUBLIC = ['/', '/hotels', '/search', '/search/results?vertical=hotel&destination=%D8%AA%D9%87%D8%B1%D8%A7%D9%86', '/tours', '/flights', '/login', '/register', '/villas', '/contact', '/support'];
const AUTHED = ['/account', '/trips', '/notifications', '/employee', '/saved-trips', '/booking'];
const browser = await chromium.launch(); const result = {}; const shots = {};
for (const [vpName, vp] of [['desktop', {width: 1440, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  for (const [apiName, api] of Object.entries(APIS)) {
    const ctx = await browser.newContext({viewport: vp, locale: 'fa-IR', reducedMotion: 'reduce'}); const page = await ctx.newPage();
    const log = {calls: {}, bad: [], errors: [], leaked: 0};
    await ctx.route(u => u.href.startsWith(PROD_API), async route => {
      const req = route.request(); const target = api + req.url().slice(PROD_API.length);
      try {
        const res = await route.fetch({url: target}); const key = `${req.method()} ${new URL(req.url()).pathname}`;
        log.calls[key] = res.status(); if (res.status() >= 500) log.bad.push(`${key} ${res.status()}`);
        const headers = {...res.headers(), 'access-control-allow-origin': WEB, 'access-control-allow-credentials': 'true'};
        await route.fulfill({response: res, headers});
      } catch (e) {log.bad.push(`${req.method()} ${req.url()} ${String(e).slice(0, 60)}`); await route.abort();}
    });
    page.on('pageerror', e => log.errors.push(String(e).slice(0, 140)));
    page.on('console', m => {if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) log.errors.push(m.text().slice(0, 140));});
    const visit = async (path, tag) => {
      await page.goto(WEB + path, {waitUntil: 'networkidle'}); await page.waitForTimeout(900);
      await page.addStyleTag({content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
      shots[`${vpName} ${tag} ${path}`] = {...(shots[`${vpName} ${tag} ${path}`] || {}), [apiName]: await page.screenshot({fullPage: true, animations: 'disabled'}), [`text_${apiName}`]: (await page.innerText('body')).replace(/\d{1,2}:\d{2}(:\d{2})?/g, '')};
    };
    for (const p of PUBLIC) await visit(p, 'public');
    // first hotel detail reachable from the current listing
    await page.goto(WEB + '/hotels', {waitUntil: 'networkidle'});
    const detail = await page.evaluate(() => [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).find(h => /^\/(hotels|booking|search\/results)\/?[^?]*\?.*hotel|^\/hotels\/[^/?]+/.test(h)) || null);
    if (detail) await visit(detail, 'public');
    // authenticated customer routes: session created by the API itself, stored exactly like the app stores it
    const session = await (await fetch(api + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email: process.env.GATE_EMAIL})})).json();
    await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(s => sessionStorage.setItem('karenseir-auth-session', JSON.stringify(s)), session);
    for (const p of AUTHED) await visit(p, 'authed');
    result[`${vpName}/${apiName}`] = {apiCalls: Object.keys(log.calls).length, statuses: Object.fromEntries(Object.entries(log.calls).filter(([, s]) => s >= 400)), serverErrors: log.bad, jsErrors: [...new Set(log.errors)], detail};
    await ctx.close();
  }
}
const diffs = [];
for (const [k, v] of Object.entries(shots)) {
  if (!v.old || !v.new) {diffs.push(`${k}: missing side`); continue;}
  if (!v.old.equals(v.new)) {const textSame = v.text_old === v.text_new; diffs.push(`${k}: pixels differ, text ${textSame ? 'identical' : 'DIFFERS'}`); const t = k.replace(/[^a-z0-9]+/gi, '_').slice(0, 80); fs.writeFileSync(`${OUT}/${t}_old.png`, v.old); fs.writeFileSync(`${OUT}/${t}_new.png`, v.new); if (!textSame) fs.writeFileSync(`${OUT}/${t}.txt`, `--- old\n${v.text_old}\n--- new\n${v.text_new}`);}
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
for (const vp of ['desktop', 'mobile']) {const o = result[`${vp}/old`], n = result[`${vp}/new`];
  console.log(vp, 'api calls old/new', o.apiCalls, n.apiCalls, '| 4xx same:', same(o.statuses, n.statuses), '| 5xx old:', o.serverErrors.length, 'new:', n.serverErrors.length, '| js errors old:', o.jsErrors.length, 'new:', n.jsErrors.length, '| detail:', n.detail);
  if (!same(o.statuses, n.statuses)) console.log('  old', JSON.stringify(o.statuses), '\n  new', JSON.stringify(n.statuses));
  if (n.serverErrors.length) console.log('  5xx new', n.serverErrors.slice(0, 6), ' old', o.serverErrors.slice(0, 6));
  const onlyNew = n.jsErrors.filter(e => !o.jsErrors.includes(e)); if (onlyNew.length) console.log('  js errors only with new API:', onlyNew.slice(0, 5));}
console.log('pages compared', Object.keys(shots).length, 'identical', Object.keys(shots).length - diffs.length); diffs.forEach(d => console.log('  ', d));
await browser.close();
