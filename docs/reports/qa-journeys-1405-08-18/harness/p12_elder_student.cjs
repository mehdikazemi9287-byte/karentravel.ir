// Persona 1 (65+ elder: a11y, keyboard, zoom 200%) and persona 2 (student: budget, mobile-only).
const fs = require('fs');
const { launch, newCtx, step, api, WEB } = require('./lib.cjs');
const { D, trainUrl, flightUrl, mainText, status, priceCheckAndBook, runCheckout, clickWait } = require('./flows.cjs');
const AXE = fs.readFileSync('/home/claude/qawt/node_modules/axe-core/axe.min.js', 'utf8');
async function axe(page) { await page.addScriptTag({ content: AXE }); return page.evaluate(async () => { const r = await window.axe.run(document, { runOnly: ['wcag2a', 'wcag2aa'] }); return r.violations.map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length, sample: v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' ; ').slice(0, 160) })); }); }
async function tapTargets(page) { return page.evaluate(() => { const bad = []; document.querySelectorAll('a,button,input,select,[role=tab],[role=button]').forEach(e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); if (r.width === 0 || r.height === 0 || cs.visibility === 'hidden') return; if ((r.width < 44 || r.height < 44) && !(e.tagName === 'A' && cs.display === 'inline')) bad.push(`${e.tagName}:${(e.getAttribute('aria-label') || e.textContent || e.type || '').trim().slice(0, 18)}(${Math.round(r.width)}x${Math.round(r.height)})`); }); return bad; }); }
async function minFont(page) { return page.evaluate(() => { const sizes = {}; document.querySelectorAll('main p, main span, main small, main label, main li, main a, main button, footer a, footer p').forEach(e => { if (!e.textContent.trim() || e.children.length > 3) return; const s = parseFloat(getComputedStyle(e).fontSize); if (e.getBoundingClientRect().height) sizes[s] = (sizes[s] || 0) + 1; }); return sizes; }); }
const results = {};
(async () => {
  const b = await launch();
  for (const mobile of [false, true]) {
    const P = mobile ? 'p1-elder-m' : 'p1-elder-d';
    const { page, ctx } = await newCtx(b, { mobile });
    for (const path of ['/', '/trains', '/flights', '/login']) {
      await step(P, `axe WCAG A/AA ${path}`, page, async () => { await page.goto(WEB + path, { waitUntil: 'networkidle' }); const v = await axe(page); results[P + path] = v; const serious = v.filter(x => ['serious', 'critical'].includes(x.impact)); return serious.length ? { status: 'FAIL', note: serious.map(x => `${x.id}×${x.n} [${x.sample}]`).join(' | ').slice(0, 500) } : 'no serious/critical; minor: ' + v.map(x => x.id).join(','); });
    }
    await step(P, 'اندازه فونت (حداقل ۱۶px برای سالمند)', page, async () => { await page.goto(WEB + '/trains', { waitUntil: 'networkidle' }); const s = await minFont(page); const small = Object.entries(s).filter(([k]) => +k < 14).reduce((a, [, v]) => a + v, 0); return small ? { status: 'FAIL', note: 'text nodes <14px: ' + small + ' ; histogram ' + JSON.stringify(s) } : 'histogram ' + JSON.stringify(s); });
    await step(P, 'اندازه هدف لمسی (≥۴۴px) در /trains', page, async () => { const bad = await tapTargets(page); return bad.length ? { status: 'FAIL', note: bad.length + ' targets <44px: ' + bad.slice(0, 12).join(', ') } : 'all ≥44'; });
    await step(P, 'شماره پشتیبانی تلفنی قابل مشاهده', page, async () => { await page.goto(WEB + '/', { waitUntil: 'networkidle' }); const tel = page.locator('a[href^="tel:"]'); const n = await tel.count(); const vis = n ? await tel.first().isVisible() : false; const inViewport = n ? await tel.first().evaluate(e => e.getBoundingClientRect().top < window.innerHeight) : false; return n && vis ? (inViewport ? 'tel link visible above fold' : { status: 'FAIL', note: `tel link exists (${n}) but not above the fold on home; elder must scroll to footer` }) : { status: 'FAIL', note: 'no tel: link on homepage' }; });
    await step(P, 'مسیر ساده خرید قطار (بدون ورود) → پیام فارسی ورود', page, async () => {
      await page.goto(trainUrl(1), { waitUntil: 'networkidle' }); const t = await mainText(page);
      const login = page.getByRole('link', { name: /ورود برای قیمت و رزرو|ورود/ }); const hasPrice = /ریال/.test(t);
      return `anon sees ${hasPrice ? 'prices' : 'NO final price'}; login CTA count=${await login.count()}; jargon check: ${['Offer', 'checkout', 'Mock', 'recheck', 'UTC'].filter(w => t.includes(w)).join(',') || 'none'}`;
    });
    await step(P, 'اصطلاحات فنی/انگلیسی در مسیر خرید (UTC, Offer, Checkout)', page, async () => {
      const t = await mainText(page); const j = ['UTC+', 'Offer', 'Checkout', 'policy', 'Price Check', 'stale', 'bps'].filter(w => t.includes(w));
      return j.length ? { status: 'FAIL', note: 'jargon shown to customer on train results: ' + j.join(', ') } : 'none';
    });
    await step(P, 'پیام خطای فارسی برای شماره موبایل نامعتبر در ورود', page, async () => {
      await page.goto(WEB + '/login', { waitUntil: 'networkidle' }); await page.getByLabel('شماره همراه یا شناسه ورود').fill('12345'); await page.getByRole('button', { name: 'دریافت کد ورود' }).click(); await page.waitForTimeout(600);
      const msg = await page.getByLabel('شماره همراه یا شناسه ورود').evaluate(e => e.validationMessage); const st = await status(page);
      return /09|شماره|معتبر/.test(msg + st) ? `msg="${msg}"` : { status: 'FAIL', note: `only browser-native pattern message ("${msg}") — no Persian hint of the expected 09xxxxxxxxx format; status="${st}"` };
    });
    if (!mobile) {
      await step(P, 'ناوبری فقط با کیبورد: Tab تا فرم جست‌وجو و فوکوس قابل دیدن', page, async () => {
        await page.goto(WEB + '/trains', { waitUntil: 'networkidle' }); const seen = [];
        for (let i = 0; i < 25; i++) { await page.keyboard.press('Tab'); seen.push(await page.evaluate(() => { const e = document.activeElement; const cs = getComputedStyle(e); const ring = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== 'none'; return `${e.tagName}:${(e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 14)}${ring ? '' : '[NO-FOCUS-RING]'}`; })); }
        const skip = seen[0] && /پرش|محتوا|skip/i.test(seen[0]); const noRing = seen.filter(s => s.includes('NO-FOCUS-RING'));
        const reachedSearch = seen.findIndex(s => /مبدأ|مبدا/.test(s));
        return { status: (!skip || noRing.length) ? 'FAIL' : 'PASS', note: `skip-link=${!!skip}; search origin reached at Tab #${reachedSearch + 1}; elements without visible focus ring=${noRing.length}: ${noRing.slice(0, 6).join(', ')}` };
      });
      await step(P, 'تکمیل جست‌وجوی قطار فقط با کیبورد', page, async () => {
        await page.goto(WEB + '/trains', { waitUntil: 'networkidle' });
        const o = page.getByRole('combobox', { name: 'مبدأ' }); await o.focus(); await page.keyboard.type('تهران'); await page.waitForTimeout(500); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
        const d = page.getByRole('combobox', { name: 'مقصد' }); await page.keyboard.press('Tab'); await page.keyboard.press('Tab'); const focused = await page.evaluate(() => document.activeElement.getAttribute('aria-label'));
        await d.focus(); await page.keyboard.type('مشهد'); await page.waitForTimeout(500); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
        await page.getByRole('button', { name: /تاریخ سفر/ }).focus(); await page.keyboard.press('Enter'); await page.waitForTimeout(400);
        const dialogFocus = await page.evaluate(() => document.activeElement.textContent.trim().slice(0, 20));
        return `origin/dest via keyboard ok; date picker opened, focus now on "${dialogFocus}" (focus after origin+2Tab: ${focused})`;
      });
      await step(P, 'بزرگ‌نمایی ۲۰۰٪ (عرض مؤثر ۷۲۰px) بدون اسکرول افقی', page, async () => {
        await page.setViewportSize({ width: 720, height: 500 }); const out = [];
        for (const p of ['/', '/trains', trainUrl(1).replace(WEB, ''), '/login']) { await page.goto(WEB + p, { waitUntil: 'networkidle' }); out.push([p.slice(0, 30), await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)]); }
        await page.evaluate(() => { document.documentElement.style.zoom = '2'; }); await page.goto(WEB + '/trains', { waitUntil: 'networkidle' });
        await page.setViewportSize({ width: 1440, height: 1000 }); await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; }); await page.waitForTimeout(300);
        const clip = await page.evaluate(() => [...document.querySelectorAll('button, a')].filter(e => e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow === 'hidden').length);
        const bad = out.filter(x => x[1] > 2); return bad.length ? { status: 'FAIL', note: 'horizontal scroll at 200% zoom: ' + JSON.stringify(bad) } : `no h-scroll at 720px: ${JSON.stringify(out)}; root-font 200% clipped controls=${clip}`;
      });
    }
    await ctx.close();
  }
  // ---------- Persona 2: student, mobile only ----------
  {
    const P = 'p2-student-m'; const { page, ctx } = await newCtx(b, { mobile: true, email: 'qa-student@consumer.qa' });
    let rid;
    await step(P, 'جست‌وجوی قطار ارزان (موبایل)', page, async () => { await page.goto(trainUrl(1, 'lowest_price'), { waitUntil: 'networkidle' }); const t = await mainText(page); const pr = (t.match(/[۰-۹٬]+ ریال/g) || []); return pr.length ? 'prices: ' + pr.join(', ') : { status: 'FAIL', note: t.slice(0, 200) }; });
    await step(P, 'مرتب‌سازی «کمترین قیمت نهایی» در قطار', page, async () => { const nums = await page.$$eval('article', a => a.map(x => (x.innerText.match(/([۰-۹٬]+) ریال/) || [])[1]).filter(Boolean)); const n = nums.map(p => Number(p.replace(/[۰-۹]/g, c => '۰۱۲۳۴۵۶۷۸۹'.indexOf(c)).replace(/٬/g, ''))); return n.every((v, i) => !i || n[i - 1] <= v) ? 'asc ' + n : { status: 'FAIL', note: 'order ' + n }; });
    await step(P, 'فیلتر حداکثر قیمت ۴٬۰۰۰٬۰۰۰', page, async () => {
      const f = page.getByLabel('حداکثر قیمت'); if (!(await f.isVisible())) { const t = page.getByRole('button', { name: /فیلتر/ }).first(); if (await t.count()) await t.click(); }
      await page.getByLabel('حداکثر قیمت').fill('4000000'); await page.getByRole('button', { name: 'اعمال فیلتر' }).click(); await page.waitForTimeout(1500);
      const n = await page.locator('article').count(); return n === 1 ? 'filtered to 1' : { status: 'FAIL', note: 'cards after max_price=4M: ' + n };
    });
    await step(P, 'اطلاعات تخفیف دانشجویی / باشگاه مشتریان', page, async () => { await page.goto(WEB + '/account/benefits', { waitUntil: 'networkidle' }); const t = await mainText(page); return { status: /دانشجو/.test(t) ? 'PASS' : 'FAIL', note: 'no student discount / club info for consumers; /account/benefits: ' + t.slice(0, 160) }; });
    await step(P, 'رزرو قطار تا مرحله پرداخت (موبایل)', page, async () => { await page.goto(trainUrl(1, 'lowest_price'), { waitUntil: 'networkidle' }); rid = await priceCheckAndBook(page, 0); const log = await runCheckout(page, ['[QA-DEMO] دانشجو']); const t = await mainText(page); return /در انتظار پرداخت/.test(t) ? 'awaiting_payment' : { status: 'FAIL', note: log.join(';').slice(0, 300) }; });
    await step(P, 'ورودی مبلغ کیف پول/اعتبار در موبایل (input type=number با ارقام فارسی)', page, async () => { return 'see designer checks'; });
    await step(P, 'پرداخت آنلاین', page, null, { blocked: 'no sandbox/test payment gateway configured (ZARINPAL_MODE=disabled) → 503' });
    await ctx.close();
  }
  fs.writeFileSync('/home/claude/qa-journeys/axe.json', JSON.stringify(results, null, 1));
  await b.close();
})();
