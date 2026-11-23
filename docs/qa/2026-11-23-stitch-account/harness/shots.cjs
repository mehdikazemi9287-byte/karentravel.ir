// Local QA: full-page screenshots of the redesigned pages against the local dev backend (test data only).
const { chromium } = require('/home/claude/wt-stitch/node_modules/playwright');
const API = 'http://127.0.0.1:8130', WEB = 'http://127.0.0.1:3130';
const OUT = '/home/claude/wt-stitch/docs/qa/2026-11-23-stitch-account';
const [flightRes, paymentId] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch({ channel: 'chrome' });
  const session = await (await fetch(`${API}/auth/dev-login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'employee@aftab.test' }) })).json();
  const pages = [
    ['trips', '/trips', true], ['trips-loggedout', '/trips', false],
    ['profile', '/account/profile', true], ['wallet', '/account/wallet', true],
    ['checkout-funding', `/checkout/${flightRes}`, true, 'شروع یا ادامهٔ رزرو'],
    ['payment-result', `/payments/${paymentId}`, true], ['booking-confirmation', '/booking/confirmation', false],
  ];
  const errors = [];
  for (const width of [1440, 390]) {
    for (const [name, path, auth, click] of pages) {
      const ctx = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 }, locale: 'fa-IR', deviceScaleFactor: 1 });
      if (auth) await ctx.addInitScript(v => sessionStorage.setItem('karenseir-auth-session', v), JSON.stringify(session));
      const page = await ctx.newPage();
      page.on('pageerror', e => errors.push(`${name}@${width}: ${e}`));
      page.on('console', m => { if (m.type() === 'error') errors.push(`${name}@${width} console: ${m.text().slice(0, 200)}`); });
      await page.goto(WEB + path, { waitUntil: 'networkidle' });
      if (click) { await page.getByRole('button', { name: click }).click(); await page.waitForLoadState('networkidle'); await page.waitForTimeout(800); }
      await page.waitForTimeout(700);
      await page.screenshot({ path: `${OUT}/${name}_${width}.png`, fullPage: true, animations: 'disabled' });
      await ctx.close();
    }
  }
  console.log(errors.length ? errors.join('\n') : 'no page errors');
  await browser.close();
})();
