// Local QA only: full-page screenshots of the redesigned organization pages against the local dev backend (test data from fixture.py),
// plus side-by-side sheets «Stitch PNG | implementation». Usage: node shots.cjs <api> <web> <pending-request-id>
const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../../../../node_modules/playwright'));
const fs = require('fs');
const [API, WEB, pending] = process.argv.slice(2);
const OUT = path.resolve(__dirname, '..'); const STITCH = path.resolve(__dirname, '../../../../design/stitch/screens');
const pages = [
  ['dashboard', '/organization', ['b2b_1', 'b2b_2']],
  ['credit', '/organization/credit', ['_23']],
  ['billing', '/organization/billing', ['_23']],
  ['approval', `/organization/requests?request=${pending}`, ['_26']],
];
(async () => {
  const browser = await chromium.launch({ channel: 'chrome' });
  const session = await (await fetch(`${API}/auth/dev-login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'dual-qa@aftab.test' }) })).json();
  const errors = [];
  for (const width of [1440, 390]) for (const [name, url] of pages) {
    const ctx = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 }, locale: 'fa-IR', deviceScaleFactor: 1 });
    await ctx.addInitScript(v => sessionStorage.setItem('karenseir-auth-session', v), JSON.stringify(session));
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push(`${name}@${width}: ${e}`));
    page.on('console', m => { if (m.type() === 'error') errors.push(`${name}@${width} console: ${m.text().slice(0, 200)}`); });
    page.on('response', r => { if (r.url().startsWith(API) && r.status() >= 400) errors.push(`${name}@${width} ${r.status()} ${new URL(r.url()).pathname}`); });
    await page.goto(WEB + url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${OUT}/${name}_${width}.png`, fullPage: true, animations: 'disabled' });
    await ctx.close();
  }
  // comparison sheets: Stitch design on the right (RTL reading order), implementation (desktop + mobile) on the left
  for (const [name, , designs] of pages) {
    const img = f => 'data:image/png;base64,' + fs.readFileSync(f).toString('base64');
    const html = `<html dir="rtl"><body style="margin:0;font-family:Vazirmatn,Tahoma;background:#f4ede3"><div style="display:flex;gap:24px;padding:24px;align-items:flex-start">
      ${designs.map(d => `<figure style="margin:0;width:720px"><figcaption style="font:700 20px Tahoma;margin-bottom:8px">طرح Stitch: ${d}</figcaption><img style="width:720px;border:1px solid #ccc" src="${img(`${STITCH}/${d}/screen.png`)}"></figure>`).join('')}
      <figure style="margin:0;width:720px"><figcaption style="font:700 20px Tahoma;margin-bottom:8px">پیاده‌سازی (دسکتاپ ۱۴۴۰)</figcaption><img style="width:720px;border:1px solid #ccc" src="${img(`${OUT}/${name}_1440.png`)}"></figure>
      <figure style="margin:0;width:300px"><figcaption style="font:700 20px Tahoma;margin-bottom:8px">موبایل ۳۹۰</figcaption><img style="width:300px;border:1px solid #ccc" src="${img(`${OUT}/${name}_390.png`)}"></figure></div></body></html>`;
    const ctx = await browser.newContext({ viewport: { width: 400 + 744 * (designs.length + 1), height: 900 } }); const page = await ctx.newPage();
    await page.setContent(html, { waitUntil: 'load' }); await page.screenshot({ path: `${OUT}/compare_${name}.png`, fullPage: true }); await ctx.close();
  }
  console.log(errors.length ? errors.join('\n') : 'no page errors, no API error responses');
  await browser.close();
})();
