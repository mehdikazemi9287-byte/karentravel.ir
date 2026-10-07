// Read-only audit of the live site: images, search flows, navigation crawl, data wiring, layout. Nothing is written.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = 'http://95.38.184.209', API = 'http://95.38.184.209:8000', OUT = process.argv[2];
const sql = q => execSync(`docker exec -i karenseir-db-1 psql -U karenseir -d karenseir -At`, {input: q, maxBuffer: 1 << 26}).toString().trim().split('\n').filter(Boolean);
const R = []; const note = (k, v) => {R.push(`${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`);};
const get = async u => {try {const r = await fetch(u, {redirect: 'follow'}); return [r.status, r.headers.get('content-type') || '', r];} catch (e) {return [0, String(e).slice(0, 40)];}};
// ---- 1. hot-linked images really exist
const imgs = [...sql("select url from catalog_hotel_images i join catalog_hotels h on h.id=i.hotel_id where h.status='published' order by md5(url) limit 220"), ...sql("select image_url from catalog_places where image_url like 'https://checkline.travel/%'"), ...sql("select image_url from catalog_hotel_room_types where image_url is not null order by md5(image_url) limit 40"), ...sql("select image_url from catalog_hotels where source='openstreetmap' and image_url is not null order by md5(image_url) limit 40")];
let bad = []; for (let i = 0; i < imgs.length; i += 12) await Promise.all(imgs.slice(i, i + 12).map(async u => {const [s, t] = await get(u); if (s !== 200 || !t.startsWith('image/')) bad.push(`${s} ${u.slice(0, 110)}`);}));
note('images checked / not loading', `${imgs.length} / ${bad.length}`); bad.slice(0, 8).forEach(b => note('  bad image', b));
// ---- 2. data wiring: API answers = database
const j = async p => (await (await fetch(API + p)).json());
const db = n => Number(sql(n)[0]);
note('hotels api/db', [(await j('/catalog/hotels?limit=1')).total, db("select count(*) from catalog_hotels where status='published' and duplicate_of is null")]);
note('tours api/db', [(await j('/catalog/tours?limit=1')).total, db("select count(*) from catalog_tours where status='published'")]);
const visa = await j('/catalog/visa'); note('visa countries+articles api/db', [visa.countries.length + visa.articles.length, db("select count(*) from catalog_content where status='published' and kind in ('visa','visa_country')")]);
note('sitemap paths', (await j('/catalog/sitemap')).paths.length);
for (const q of ['استانبول', 'شیراز', 'دبی', 'Hilton', 'پوکت', 'کیش']) {const s = await j('/catalog/suggest?q=' + encodeURIComponent(q)); const items = Array.isArray(s) ? s : (s.items || s.results || []); note(`suggest ${q}`, [...new Set(items.map(i => i.entity_type))].join(',') + ` (${items.length})`);}
for (const p of ['/admin/catalog/hotels', '/admin/catalog/reference/places', '/admin/catalog/completeness', '/admin/catalog/tours']) note(`anon ${p}`, (await get(API + p))[0]);
// ---- 3. browser: layout on key pages, search flows, crawl
const hotel = sql("select slug from catalog_hotels where source='checkline' and status='published' and image_url is not null order by md5(id) limit 3"); const tour = sql("select slug from catalog_tours where status='published' order by md5(id) limit 2"); const place = sql("select id from catalog_places where kind='city' and hotel_count>0 and details_json like '%checkline%' order by md5(id) limit 2");
const b = await chromium.launch();
for (const [vp, size] of [['desktop', {width: 1440, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const ctx = await b.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errs = []; page.on('pageerror', e => errs.push(String(e).slice(0, 80))); const api5 = []; page.on('response', r => {if (r.url().startsWith(API) && r.status() >= 500) api5.push(r.url().slice(API.length, API.length + 50));});
  const issues = []; const seen = new Set(), queue = [];
  const pages = ['/', '/hotels', ...hotel.map(h => '/hotels/' + h), '/tours', '/tours/search', ...tour.map(t => '/tours/' + encodeURIComponent(t)), '/visa', '/destinations', ...place.map(p => '/destinations/' + p), '/attractions', '/flights', '/trains', '/villas', '/services', '/travel-guides', '/contact', '/support', '/login', '/terms', '/privacy', '/compare', '/assistant', '/organization', '/search/results?vertical=hotel&destination=' + encodeURIComponent('استانبول'), '/admin/catalog', '/admin/catalog/reference', '/admin/tours'];
  for (const p of pages) {
    const res = await page.goto(WEB + p, {waitUntil: 'networkidle'}).catch(() => null); await page.waitForTimeout(700); if (!res) {issues.push(`${p} no response`); continue;}
    const s = await page.evaluate(() => {const w = document.documentElement.clientWidth; return {fits: document.documentElement.scrollWidth <= w, broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.currentSrc).map(i => i.currentSrc.slice(0, 80)), text: document.body.innerText.length, foot: document.querySelectorAll('.kh-foot').length, head: document.querySelectorAll('[data-name="Header / Nav"], .approved-shared-header').length, navH: (document.querySelector('[data-name="Header / Nav"]') || document.querySelector('.approved-shared-header'))?.getBoundingClientRect().height, links: [...new Set([...document.querySelectorAll('a[href^="/"]')].map(a => a.getAttribute('href')))], price: /\d[\d٬,]*\s*(ریال|تومان)/.test(document.querySelector('.cat, .cat-detail, .kh')?.innerText || '')};});
    for (const l of s.links) if (!seen.has(l)) {seen.add(l); queue.push(l);}
    const probs = [res.status() !== 200 && `status ${res.status()}`, !s.fits && 'horizontal overflow', s.broken.length && `broken img ${s.broken[0]}`, s.text < 150 && 'almost empty', s.foot !== 1 && `footer×${s.foot}`, s.head < 1 && 'no header', s.price && 'price text'].filter(Boolean);
    if (probs.length) issues.push(`${decodeURIComponent(p).slice(0, 44)} → ${probs.join('; ')}`); if (p === '/') note(`${vp} header height`, s.navH);
  }
  // search flows from the homepage, one per tab
  for (const tab of ['پرواز', 'هتل', 'قطار', 'تور']) {
    await page.goto(WEB + '/', {waitUntil: 'networkidle'}); await page.locator(`.fs-tabs button:has-text("${tab}")`).first().click(); await page.waitForTimeout(400);
    await page.locator('.approved-search-card button[type=submit], .approved-search-card .fs-submit').first().click().catch(() => {}); await page.waitForTimeout(3500);
    const st = await page.evaluate(() => ({url: location.pathname + location.search.slice(0, 60), err: /خطا|پیدا نشد|404/.test(document.querySelector('h1')?.innerText || ''), text: document.body.innerText.length, alert: [...document.querySelectorAll('[role=alert]')].map(e => e.innerText.slice(0, 60)).join('|')}));
    note(`${vp} search «${tab}»`, `${decodeURIComponent(st.url)}${st.err ? ' ERROR-HEADING' : ''}${st.alert ? ' alert=' + st.alert : ''}`);
  }
  // crawl everything linked from the pages above
  const dead = []; let n = 0; for (const l of queue.slice(0, 450)) {n++; const st = (await ctx.request.get(WEB + l, {maxRedirects: 3}).catch(() => null))?.status(); if (!st || st >= 400) dead.push(`${st} ${decodeURIComponent(l).slice(0, 70)}`);}
  note(`${vp} pages with a problem`, issues.length ? issues : 'none'); note(`${vp} links crawled / dead`, `${n} / ${dead.length}`); dead.slice(0, 10).forEach(d => note('  dead', d)); note(`${vp} script errors / API 5xx`, `${errs.length} / ${api5.length} ${[...errs, ...api5].slice(0, 3).join(' | ')}`);
  await ctx.close();
}
console.log(R.join('\n')); await b.close();
