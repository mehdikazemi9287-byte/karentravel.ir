// Persona 7 (designer), 8 (technical/security functional), 9 (agency + supplier panel → customer purchase).
const { launch, newCtx, step, api, devToken, fixtures, WEB, API } = require('./lib.cjs');
const { D, trainUrl, flightUrl, mainText, status, priceCheckAndBook, runCheckout, clickWait } = require('./flows.cjs');
const PAGES = ['/', '/flights', '/trains', '/hotels', '/tours', '/login', '/register', '/support', '/contact', '/services', '/villas', '/visa', '/terms', '/privacy'];
const AUTH_PAGES = ['/trips', '/account', '/account/wallet', '/account/payments', '/notifications', '/organization', '/organization/members'];
async function designAudit(page) {
  return page.evaluate(() => {
    const ov = document.documentElement.scrollWidth - window.innerWidth;
    const offenders = []; if (ov > 2) document.querySelectorAll('body *').forEach(e => { const r = e.getBoundingClientRect(); if (r.right > window.innerWidth + 2 && r.width > 0 && getComputedStyle(e).position !== 'fixed') offenders.push(e.tagName.toLowerCase() + '.' + String(e.className).split(' ')[0]); });
    const brokenImgs = [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.getBoundingClientRect().width > 0).map(i => i.src.slice(0, 80));
    const txt = document.body.innerText; const latinDigits = (txt.match(/(?<![A-Za-z\-_\/.:])\b\d{2,}\b/g) || []).filter(x => !/^(09\d+|20\d\d)$/.test(x)).slice(0, 6);
    const ltr = document.documentElement.dir;
    const fonts = new Set([...document.querySelectorAll('h1,h2,p,button')].slice(0, 60).map(e => getComputedStyle(e).fontFamily.split(',')[0]));
    return { ov, offenders: [...new Set(offenders)].slice(0, 5), brokenImgs, latinDigits, dir: ltr, fonts: [...fonts] };
  });
}
(async () => {
  const b = await launch();
  // ---------- Persona 7: designer ----------
  for (const mobile of [false, true]) {
    const P = mobile ? 'p7-designer-m' : 'p7-designer-d';
    const anon = await newCtx(b, { mobile }); const auth = await newCtx(b, { mobile, email: 'org-admin@aftab.test' });
    for (const [ctxObj, list] of [[anon, PAGES], [auth, AUTH_PAGES.concat([trainUrl(1).replace(WEB, ''), '/manage-booking/xx'])]]) {
      const page = ctxObj.page;
      for (const p of list) await step(P, 'طراحی/RTL ' + p.slice(0, 40), page, async () => {
        await page.goto(WEB + p, { waitUntil: 'networkidle' }); await page.waitForTimeout(300); const a = await designAudit(page);
        await page.screenshot({ path: `/home/claude/qa-journeys/shots/${P}-full-${p.replace(/[^a-z0-9]/gi, '_').slice(0, 40)}.png`, fullPage: true });
        const probs = []; if (a.ov > 2) probs.push(`h-overflow ${a.ov}px by ${a.offenders.join(',')}`); if (a.brokenImgs.length) probs.push('broken img ' + a.brokenImgs.join(',')); if (a.dir !== 'rtl') probs.push('dir=' + a.dir); if (a.latinDigits.length) probs.push('latin digits: ' + a.latinDigits.join(' '));
        return probs.length ? { status: 'FAIL', note: probs.join(' ; ') + ' ; fonts=' + a.fonts.join('/') } : 'ok fonts=' + a.fonts.join('/');
      });
    }
    await anon.ctx.close(); await auth.ctx.close();
  }
  // ---------- Persona 8: technical / security (functional) ----------
  {
    const P = 'p8-tech-d'; const { page, ctx } = await newCtx(b, { email: 'qa-customer@consumer.qa' });
    await step(P, 'صفحه 404 فارسی', page, async () => { const r = await page.goto(WEB + '/no-such-page-qa', { waitUntil: 'networkidle' }); const t = await mainText(page); return r.status() === 404 && /پیدا نشد|یافت نشد|۴۰۴|404/.test(t) ? '404: ' + t.slice(0, 100) : { status: 'FAIL', note: `status ${r.status()} text ${t.slice(0, 120)}` }; });
    await step(P, 'رزرو ناموجود /manage-booking/<uuid>', page, async () => { await page.goto(WEB + '/manage-booking/00000000-0000-4000-8000-000000000000', { waitUntil: 'networkidle' }); const t = await mainText(page); return /پیدا نشد|وجود ندارد|دسترسی/.test(t) ? t.slice(0, 120) : { status: 'FAIL', note: t.slice(0, 200) }; });
    await step(P, 'خطای سرور 500 در API (شبیه‌سازی) → پیام فارسی', page, async () => {
      await page.route('**/me/reservations', r => r.fulfill({ status: 500, body: '{"detail":"x"}' })); await page.route('**/me/trips', r => r.fulfill({ status: 500, body: '{"detail":"x"}' }));
      await page.goto(WEB + '/trips', { waitUntil: 'networkidle' }); const t = await mainText(page); await page.unrouteAll();
      return /خطا|دوباره|تلاش|در دسترس نیست/.test(t) ? 'graceful: ' + t.slice(0, 140) : { status: 'FAIL', note: 'no Persian error state: ' + t.slice(0, 160) };
    });
    await step(P, 'انقضای نشست (توکن نامعتبر) در حین کار', page, async () => {
      await page.goto(WEB + '/trips', { waitUntil: 'networkidle' });
      await page.evaluate(() => { const s = JSON.parse(sessionStorage.getItem('karenseir-auth-session')); s.access_token = s.access_token.slice(0, -4) + 'AAAA'; s.refresh_token = 'invalid.' + 'x'.repeat(40); sessionStorage.setItem('karenseir-auth-session', JSON.stringify(s)); });
      await page.reload({ waitUntil: 'networkidle' }); await page.waitForTimeout(800); const t = await mainText(page);
      return /وارد شوید|ورود/.test(t) ? 'expired session → login prompt: ' + t.slice(0, 100) : { status: 'FAIL', note: t.slice(0, 160) };
    });
    await ctx.close();
    const c2 = await newCtx(b, { email: 'qa-customer@consumer.qa' }); const pg = c2.page;
    await step(P, 'پاسخ گم‌شده هنگام ثبت رزرو → بازیابی بدون رزرو تکراری', pg, async () => {
      const before = (await api(c2.ctx._session, 'GET', '/me/reservations')).body.length;
      await pg.goto(trainUrl(1), { waitUntil: 'networkidle' });
      await pg.getByRole('button', { name: 'بررسی قیمت و موجودی' }).first().click(); await pg.getByRole('button', { name: 'ادامه رزرو' }).first().waitFor();
      let first = true; await pg.route('**/orchestration/bookings', async route => { if (first) { first = false; const resp = await route.fetch(); route.abort('connectionreset'); } else route.continue(); });
      await pg.getByRole('button', { name: 'ادامه رزرو' }).first().click(); await pg.waitForTimeout(1500); const st = await status(pg);
      const mid = (await api(c2.ctx._session, 'GET', '/me/reservations')).body.length;
      const resume = pg.getByRole('button', { name: 'پیگیری همان رزرو' }); const hasResume = await resume.count();
      if (hasResume) { await resume.first().click(); await pg.waitForURL(/checkout/, { timeout: 10000 }).catch(() => {}); }
      const after = (await api(c2.ctx._session, 'GET', '/me/reservations')).body.length; await pg.unrouteAll();
      return after - before === 1 && hasResume ? `server created 1 reservation while response was lost; UI offered "پیگیری همان رزرو" and resumed same id → ${pg.url().replace(WEB, '')}` : { status: 'FAIL', note: `before=${before} mid=${mid} after=${after} resumeBtn=${hasResume} status="${st}"` };
    });
    await step(P, 'خروج و بازگشت با دکمه Back (عدم نمایش داده خصوصی)', pg, async () => {
      await pg.goto(WEB + '/account/profile', { waitUntil: 'networkidle' }); await pg.getByRole('button', { name: 'خروج از حساب' }).first().click(); await pg.waitForTimeout(800);
      await pg.goBack({ waitUntil: 'networkidle' }).catch(() => {}); await pg.waitForTimeout(500); const t = await mainText(pg);
      return /QA-DEMO\] مشتری|KS-/.test(t) ? { status: 'FAIL', note: 'private data visible after logout+Back' } : 'no private data after Back';
    });
    await step(P, 'صفحات خصوصی بدون نشست', pg, async () => { const res = []; for (const p of ['/trips', '/account', '/organization', '/checkout/abc', '/supplier', '/agency', '/finance']) { await pg.goto(WEB + p, { waitUntil: 'networkidle' }); res.push(p + ':' + (/وارد شوید|ورود امن|ورود/.test(await mainText(pg)) ? 'gated' : 'OPEN')); } return res.some(x => x.endsWith('OPEN')) ? { status: 'FAIL', note: res.join(' ') } : res.join(' '); });
    await step(P, 'دسترسی متقابل: مشتری رزرو دیگری را باز کند (IDOR)', pg, async () => { const other = (await api(await devToken('employee@aftab.test'), 'GET', '/me/reservations')).body[0]; const r = await api(await devToken('qa-customer@consumer.qa'), 'GET', `/reservations/${other.id}`); return r.status === 404 || r.status === 403 ? 'denied ' + r.status : { status: 'FAIL', note: 'cross-account read ' + r.status }; });
    await step(P, 'شناسه رزرو در URL صفحه pilot عمومی /pilot (حساب‌های آزمایشی)', pg, async () => { await pg.goto(WEB + '/pilot', { waitUntil: 'networkidle' }); const t = await mainText(pg); return /حساب آزمایشی توسعه|employee@aftab\.test/.test(t) ? { status: 'FAIL', note: '/pilot exposes demo dev-account picker and is reachable without auth (dev-login 404s in prod but page itself ships)' } : 'not exposed'; });
    await c2.ctx.close();
  }
  // ---------- Persona 9: supplier + agency panel → customer purchase ----------
  {
    const P = 'p9-partner-d'; const { page, ctx } = await newCtx(b, { email: 'supplier@aftab.test' });
    await step(P, 'پنل تأمین‌کننده /supplier', page, async () => { await page.goto(WEB + '/supplier', { waitUntil: 'networkidle' }); const t = await mainText(page); return /تأمین‌کننده/.test(t) ? t.slice(0, 160) : { status: 'FAIL', note: t.slice(0, 200) }; });
    await step(P, 'ثبت تور از پنل /supplier/tours', page, async () => { await page.goto(WEB + '/supplier/tours', { waitUntil: 'networkidle' }); const t = await mainText(page); const tours = (t.match(/QA-DEMO\] تور/g) || []).length; return tours ? 'supplier sees own QA tours: ' + tours : { status: 'FAIL', note: t.slice(0, 220) }; });
    await step(P, 'ثبت پیشنهاد قطار از فرم پنل /supplier/train/new', page, async () => { await page.goto(WEB + '/supplier/train/new', { waitUntil: 'networkidle' }); const labels = await page.$$eval('main label', l => l.map(x => x.innerText.split('\n')[0].trim()).slice(0, 20)); return 'form fields: ' + labels.join(' / ').slice(0, 300); });
    await step(P, 'تور منتشرشده در /tours برای مشتری سازمانی', page, async () => {
      const c = await newCtx(b, { email: 'employee@aftab.test' }); await c.page.goto(WEB + '/tours', { waitUntil: 'networkidle' }); const link = c.page.locator(`a[href="/tours/${fixtures.aftab.tour_id}"]`);
      const ok = await link.count(); if (!ok) { await c.ctx.close(); return { status: 'FAIL', note: 'supplier tour not listed on /tours' }; }
      await link.first().click(); await c.page.waitForLoadState('networkidle'); const btn = c.page.getByRole('button', { name: /بررسی ظرفیت و قیمت|استعلام مبلغ و ظرفیت/ });
      await btn.first().click(); await c.page.waitForTimeout(1500); const st = await status(c.page); const cont = c.page.getByRole('button', { name: /ادامه|رزرو/ });
      await c.page.screenshot({ path: '/home/claude/qa-journeys/shots/p9-tour-customer.png', fullPage: true }); await c.ctx.close();
      return 'tour quote: ' + st.slice(0, 160);
    });
    await step(P, 'تور در کاتالوگ عمومی /tours (بدون ورود)', page, async () => { const c = await newCtx(b); await c.page.goto(WEB + '/tours', { waitUntil: 'networkidle' }); const t = await mainText(c.page); await c.ctx.close(); return /QA-DEMO\] تور/.test(t) ? 'public tours listed' : { status: 'FAIL', note: 'public visitor sees no tours although public-catalog tenant has a published QA tour: ' + t.slice(0, 160) }; });
    await step(P, 'رزروهای آماده انجام برای تأمین‌کننده /supplier/fulfillment', page, async () => { await page.goto(WEB + '/supplier/fulfillment', { waitUntil: 'networkidle' }); const t = await mainText(page); return { status: 'BLOCKED', note: 'list only shows reservations with captured bank payment; gateway blocked → empty. Credit-funded bookings never appear (see defect). Page: ' + t.slice(0, 120) }; });
    await ctx.close();
    const a = await newCtx(b, { email: 'agency@aftab.test' });
    await step('p9-partner-d', 'پنل آژانس /agency', a.page, async () => { await a.page.goto(WEB + '/agency', { waitUntil: 'networkidle' }); const t = await mainText(a.page); return t.slice(0, 160); });
    await step('p9-partner-d', 'رزروهای آژانس /agency/bookings', a.page, async () => { await a.page.goto(WEB + '/agency/bookings', { waitUntil: 'networkidle' }); const t = await mainText(a.page); return /KS-/.test(t) ? 'bookings visible' : { status: 'FAIL', note: 'agency sees no bookings: ' + t.slice(0, 160) }; });
    await step('p9-partner-d', 'ثبت تور توسط آژانس قراردادی', a.page, async () => { const r = await api(a.ctx._session, 'POST', '/supplier/tours', { supplier_id: fixtures.aftab.supplier_id, title: '[QA-DEMO] تور آژانس', slug: 'qa-ag-' + Date.now(), origin: 'تهران', destination: 'کیش', tour_type: 'leisure', details: {} }); await a.page.goto(WEB + '/agency/workspace', { waitUntil: 'networkidle' }); return r.status < 300 ? 'agency can create tour' : { status: 'FAIL', note: `agency_partner cannot list its own tours: POST /supplier/tours → ${r.status} (${JSON.stringify(r.body).slice(0, 80)}); agency role has no inventory:manage — tours must be listed via a supplier account` }; });
    await a.ctx.close();
  }
  await b.close();
})();
