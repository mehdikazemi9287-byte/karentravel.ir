// Homepage checks after the alignment to the approved reference. Desktop + mobile. Read-only.
import {chromium} from 'playwright';
const WEB = process.argv[2], OUT = process.argv[3]; const b = await chromium.launch(); const out = {};
for (const [vp, size] of [['desktop', {width: 1440, height: 900}], ['mobile', {width: 390, height: 844}], ['tablet', {width: 820, height: 1100}]]) {
  const r = []; const check = (n, ok, e = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${n}${e !== '' ? ' — ' + String(e).slice(0, 160) : ''}`);
  const ctx = await b.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 100)));
  await page.goto(WEB + '/', {waitUntil: 'networkidle'}); await page.waitForTimeout(1200);
  const s = await page.evaluate(() => {const q = x => document.querySelector(x); const cs = x => q(x) ? getComputedStyle(q(x)) : null; const w = document.documentElement.clientWidth;
    return {fits: document.documentElement.scrollWidth <= w, over: [...document.querySelectorAll('.kh *, .approved-search-card')].filter(e => {const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > w + 1 || r.left < -1);}).slice(0, 3).map(e => e.className.toString().slice(0, 30)),
      tabs: [...document.querySelectorAll('.approved-search-card .fs-tabs button')].filter(e => e.offsetParent).sort((a, c) => c.getBoundingClientRect().right - a.getBoundingClientRect().right).map(e => e.innerText.trim()),
      ai: cs('.kh-ai')?.backgroundColor, cmp: cs('.kh-cmp')?.backgroundColor, strip: cs('.kh-strip')?.backgroundColor, foot: cs('.kh-foot')?.backgroundColor, cta: cs('.kh-org-cta')?.backgroundColor, font: cs('.kh')?.fontFamily, dir: cs('.kh')?.direction,
      trips: document.querySelectorAll('.kh-trip').length, chips: document.querySelectorAll('.kh-ai-chips a').length, services: [...document.querySelectorAll('.kh-strip a')].map(a => a.getAttribute('href')), footW: q('.kh-foot')?.getBoundingClientRect().width, w,
      broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.currentSrc).length, price: /\d[\d٬,]*\s*(ریال|تومان)/.test(q('.kh').innerText), links: [...new Set([...document.querySelectorAll('a[href^="/"]')].map(a => a.getAttribute('href')))]};});
  check('no horizontal overflow', s.fits && s.over.length === 0, s.over.join(','));
  check('search tabs: پرواز، هتل، قطار، تور', s.tabs.join('،') === 'پرواز،هتل،قطار،تور', s.tabs.join('،'));
  check('section colours follow the reference', s.ai === 'rgb(207, 230, 242)' && s.cmp === 'rgb(58, 27, 61)' && s.strip === 'rgb(58, 27, 61)' && s.foot === 'rgb(253, 247, 238)' && s.cta === 'rgb(239, 91, 61)', [s.ai, s.cmp, s.foot].join(' '));
  check('RTL and Vazirmatn', s.dir === 'rtl' && /Vazirmatn/.test(s.font));
  check('three trips, three prompts, five services, full-width footer', s.trips === 3 && s.chips === 3 && s.services.join() === '/services,/tours,/trains,/hotels,/flights' && Math.abs(s.footW - s.w) < 2, `${s.footW}/${s.w}`);
  check('no broken image, no price shown', s.broken === 0 && !s.price);
  const dead = []; for (const h of s.links) {const st = (await ctx.request.get(WEB + h, {maxRedirects: 3})).status(); if (st >= 400) dead.push(`${h} ${st}`);} check(`all ${s.links.length} homepage links are live`, dead.length === 0, dead.join(' | '));
  await page.locator('.fs-tabs button:has-text("قطار")').first().click(); await page.waitForTimeout(400); check('train tab is selectable', (await page.locator('.fs-tabs button.is-active').innerText()).includes('قطار'));
  await page.locator('.kh-ai-chips a').first().click(); await page.waitForURL(u => u.pathname.startsWith('/assistant'), {timeout: 15000}).catch(() => {}); check('prompt chip opens the assistant', page.url().includes('/assistant'));
  for (const p of ['/hotels', '/tours', '/contact']) {await page.goto(WEB + p, {waitUntil: 'networkidle'}); const f = await page.evaluate(() => ({n: document.querySelectorAll('.kh-foot').length, fits: document.documentElement.scrollWidth <= document.documentElement.clientWidth})); check(`${p}: shared light footer, fits`, f.n === 1 && f.fits);}
  check('no script error', errors.length === 0, errors.join(' | '));
  await page.goto(WEB + '/', {waitUntil: 'networkidle'}); await page.waitForTimeout(1000); await page.screenshot({path: `${OUT}/home-${vp}.png`, fullPage: true});
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL'))}; await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await b.close();
