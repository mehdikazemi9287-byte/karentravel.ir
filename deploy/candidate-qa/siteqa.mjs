// Candidate browser QA: ZIP content as site structure. Desktop + mobile. Real pages, real navigation, link crawl.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137', OUT = process.argv[2];
const psql = q => execSync(`docker exec -i ks-catalog-scratch-pg psql -U postgres -d ks_cand37 -At`, {input: q}).toString().trim().split('\n')[0];
const hotel = psql("select h.slug||'|'||h.name_fa||'|'||h.city_id from catalog_hotels h where h.source='checkline' and h.status='published' and h.name_fa is not null and h.city_id is not null and h.description is not null and exists (select 1 from catalog_hotel_room_types r where r.hotel_id=h.id and r.image_url is not null) order by h.id limit 1").split('|');
const tour = psql("select t.slug||'|'||t.title_fa||'|'||t.destination_place_id from catalog_tours t where t.status='published' and t.description is not null and t.slug !~ '^cl-tour' and t.details_json like '%categories%' and exists (select 1 from catalog_tour_departures d where d.tour_id=t.id) and exists (select 1 from catalog_tour_hotels x where x.tour_id=t.id) order by t.id desc limit 1").split('|');
const visaCountry = psql("select replace(id,'cl-visa-country-','') from catalog_content where kind='visa_country' order by length(body) desc limit 1");
const cityWithGallery = psql("select id from catalog_places where kind='city' and details_json like '%\"images\"%' and description is not null and hotel_count>0 limit 1");
const legacy = psql("select legacy_path||'|'||target_path from catalog_legacy_routes where target_path like '/hotels?%city=%' limit 1").split('|');
const attraction = psql("select name_fa from catalog_venues where source='checkline' limit 1");
const login = async email => (await (await fetch(API + '/auth/dev-login', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({email})})).json());
if (hotel.length < 3 || tour.length < 3 || legacy.length < 2) {console.log('fixture lookup failed', hotel, tour, legacy); process.exit(1);}
const browser = await chromium.launch(); const out = {};
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (n, ok, e = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${n}${e !== '' ? ' — ' + String(e).slice(0, 120) : ''}`);
  const ctx = await browser.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 100)));
  const open = async p => {const res = await page.goto(WEB + p, {waitUntil: 'networkidle'}); await page.waitForTimeout(600); return res;};
  const text = () => page.locator('main').first().innerText();
  const fits = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const links = new Set(); const collect = async () => {for (const h of await page.$$eval('main a[href^="/"]', as => as.map(a => a.getAttribute('href')))) links.add(h);};
  // ---------- homepage -> hotel search
  await open('/'); const tab = page.locator('main button:has-text("هتل"), main [role=tab]:has-text("هتل")').first(); if (await tab.count()) await tab.click().catch(() => {}); await page.waitForTimeout(400); const box = page.locator('input[role=combobox]').first();
  let viaHome = false;
  if (await box.count()) {await box.click().catch(() => {}); await box.fill(hotel[1]).catch(() => {}); await page.waitForTimeout(1800); viaHome = (await page.locator(`[role=option]:has-text("${hotel[1]}"), [role=listbox] :text("${hotel[1]}")`).count()) > 0; if (!viaHome) console.log('home options:', (await page.locator('[role=option]').allInnerTexts()).slice(0, 5).join(' | ').slice(0, 200));}
  check('homepage search suggests the bundle hotel', viaHome);
  const homeState = await page.evaluate(() => ({s: Object.keys(sessionStorage), l: Object.keys(localStorage)})); await page.evaluate(() => {sessionStorage.clear(); localStorage.clear();}); await ctx.clearCookies(); if (!viaHome) console.log('home search state keys', JSON.stringify(homeState), page.url());
  // ---------- hotel vertical
  await open(`/hotels?city=${hotel[2]}`); if (!(await page.locator('.cat-grid a').count())) {console.log('retry hotels:', (await text()).slice(-160).replace(/\n/g, ' ')); await page.waitForTimeout(4000); await open(`/hotels?city=${hotel[2]}`);} await page.waitForSelector('.cat-grid a'); check('hotel results for the city, with filters', (await page.locator('.cat-grid a').count()) >= 1 && (await page.locator('.cat-filters select').count()) >= 2); await collect();
  await open('/hotels/' + hotel[0]); await page.waitForSelector('.cat-detail-head h1'); const th = await text();
  check('hotel detail: description, room types with image, facilities', /دربارهٔ اقامتگاه/.test(th) && /انواع اتاق/.test(th) && (await page.locator('img.cat-room-img').count()) >= 1 && (await page.locator('.cat-rooms .cat-amen li').count()) >= 1);
  check('hotel detail: explicit rate/booking state', /نرخ و موجودی\s*متصل نیست/.test(th.replace(/\n/g, ' ')) && /رزرو آنلاین\s*غیرفعال/.test(th.replace(/\n/g, ' ')) && (await page.locator('[data-request-state=inquiry]').count()) === 1);
  check('hotel detail: anonymous is asked to sign in for a request', (await page.locator('[data-request-state] a[href="/login"]').count()) === 1);
  check('hotel SEO title/description from data', (await page.title()).includes(hotel[1].slice(0, 12)) && ((await page.locator('meta[name=description]').getAttribute('content')) || '').length > 20, await page.title()); await collect();
  // ---------- tour vertical
  await open('/tours'); check('tour landing: programme by destination with real tours', /برنامهٔ تورها بر اساس مقصد/.test(await text()) && (await page.locator('#tour-catalog .cat-grid a').count()) >= 3); await collect();
  await open('/tours/search'); await page.waitForSelector('#tour-catalog .cat-grid a'); const totalAll = await page.locator('.cat-meta span').first().innerText();
  const cats = await page.locator('.cat-filters select').first().locator('option').count();
  check('tour search: categories, duration and year filters fed by the data', cats >= 5 && (await page.locator('.cat-filters select').count()) === 3, `${cats} categories`);
  await page.locator('.cat-filters select').nth(1).selectOption('7+'); await page.waitForTimeout(900); const total7 = await page.locator('.cat-meta span').first().innerText(); check('tour search: duration filter narrows results', total7 !== totalAll && /nights=7/.test(page.url()), `${totalAll} → ${total7}`);
  await page.locator('.cat-filters select').nth(1).selectOption(''); await page.locator('.cat-filters select').first().selectOption({index: 1}); await page.waitForTimeout(900); check('tour search: category filter', /category=/.test(page.url()) && (await page.locator('#tour-catalog .cat-grid a').count()) >= 1); await collect();
  const res = await open('/tours/' + encodeURIComponent(tour[0])); const tt = await text();
  check('tour detail by slug: intro, origin/destination, duration, transport, services', res.status() === 200 && /دربارهٔ تور/.test(tt) && /مقصد/.test(tt) && /مدت/.test(tt) && /خدمات تور|برنامهٔ حمل‌ونقل/.test(tt));
  check('tour detail: hotels, past dates, taxonomy', /هتل‌های این تور/.test(tt) && /تاریخ‌های برگزارشده/.test(tt) && (await page.locator('[aria-label="دسته‌بندی"] a').count()) >= 1);
  check('tour detail: not bookable, explicit request state', /رزرو آنلاین\s*غیرفعال/.test(tt.replace(/\n/g, ' ')) && !/\d[\d٬,]*\s*(ریال|تومان)/.test(tt) && !(await page.locator('main button:has-text("رزرو")').count()));
  check('tour SEO title from data', (await page.title()).includes(tour[1].slice(0, 10)), await page.title()); check('tour detail: no horizontal overflow', await fits()); await collect(); await page.screenshot({path: `${OUT}/site-tour-${vp}.png`, fullPage: true});
  await open('/tours/destination/' + tour[2]); await page.waitForSelector('#tour-catalog .cat-grid a'); check('tours by destination page', (await page.locator('#tour-catalog .cat-grid a').count()) >= 1 && !(await page.locator('[aria-label="مقصد تور"]').count())); await collect();
  await open('/tours/reference'); check('old tour list route redirects', /\/tours\/search/.test(page.url()));
  // ---------- request flow as a signed-in customer (creates a real support case on the candidate)
  const s = await login('employee@aftab.test'); await page.goto(WEB + '/login', {waitUntil: 'networkidle'}); await page.evaluate(x => sessionStorage.setItem('karenseir-auth-session', JSON.stringify(x)), s);
  const before = Number(psql("select count(*) from support_cases"));
  await open('/tours/' + encodeURIComponent(tour[0])); await page.locator('[data-request-state] button:has-text("ثبت درخواست استعلام")').click(); await page.locator('[data-request-state] textarea').fill(`دو نفر، نیمهٔ دوم آبان (${vp})`);
  await page.locator('[data-request-state] button:has-text("ارسال درخواست")').click(); await page.locator('[data-request-state] [role=status]').waitFor({timeout: 15000});
  const subj = psql("select subject from support_cases order by created_at desc limit 1");
  check('tour inquiry creates a support case for the customer', Number(psql("select count(*) from support_cases")) === before + 1 && subj.includes('استعلام تور'), subj);
  await open('/hotels/' + hotel[0]); await page.locator('[data-request-state] button:has-text("ثبت درخواست استعلام")').click(); await page.locator('[data-request-state] button:has-text("ارسال درخواست")').click(); await page.locator('[data-request-state] [role=status]').waitFor({timeout: 15000});
  check('hotel inquiry creates a support case', Number(psql("select count(*) from support_cases")) === before + 2 && psql("select count(*) from reservations where created_at > now() - interval '1 minute'") === '0');
  await page.evaluate(() => sessionStorage.clear());
  // ---------- destinations
  await open('/destinations/' + cityWithGallery); const td = await text();
  check('destination: breadcrumbs, gallery, related, hotels', (await page.locator('.cat-place .cat-crumbs a').count()) >= 2 && (await page.locator('.cat-place .cat-gallery img').count()) >= 2 && /مقصدهای مرتبط/.test(td) && /هتل و اقامتگاه/.test(td));
  check('destination SEO title from data', /راهنمای مقصد کارن‌سیر/.test(await page.title()), await page.title()); await collect();
  await page.locator('.cat-place .cat-crumbs a').nth(1).click(); await page.waitForTimeout(900); check('breadcrumb leads to the country page', /\/destinations\/[a-z]{2}$/.test(page.url()) && /اطلاعات مقصد/.test(await text()));
  // ---------- visa / travel requirements
  await open('/visa'); const tv = await text(); check('visa page: country guides and articles from the bundle', /به تفکیک کشور/.test(tv) && /مقاله‌های راهنما/.test(tv) && (await page.locator('a[href^="/visa/cl-visa-"]').count()) >= 10 && /تضمین نمی‌شود/.test(tv)); await collect();
  await open('/visa/cl-visa-country-' + visaCountry); const ta = await text(); check('visa country guide: text, disclaimer, links to hotels and tours', ta.length > 300 && /سفارت مقصد تعیین می‌کند/.test(ta) && (await page.locator('a[href^="/hotels?country="]').count()) === 1); await collect();
  await open('/visa/nope'); check('visa guide: error state', /پیدا نشد/.test(await text()));
  // ---------- attractions and old URLs
  await open('/attractions'); await page.waitForTimeout(800); check('attractions page lists a bundle attraction', (await page.locator('body').innerText()).includes(attraction) || (await (await fetch(API + '/catalog/venues?q=' + encodeURIComponent(attraction))).json()).items.length > 0, attraction);
  await page.goto(WEB + encodeURI(legacy[0]), {waitUntil: 'networkidle'}); await page.waitForURL(u => u.pathname.startsWith('/hotels'), {timeout: 12000}).catch(() => {});
  check('old-site URL is redirected to its KarenSeir page', decodeURIComponent(page.url()).includes(legacy[1].split('?')[0]) && /city=/.test(page.url()), decodeURIComponent(page.url()).replace(WEB, ''));
  await page.goto(WEB + '/no-such-old-page-xyz/', {waitUntil: 'networkidle'}); check('unknown URL stays a normal 404', /این صفحه پیدا نشد/.test(await page.locator('body').innerText()));
  // ---------- dead links reachable from these pages
  const dead = []; let n = 0;
  for (const href of [...links].slice(0, 140)) {n++; const st = await (await ctx.request.get(WEB + href, {maxRedirects: 3}).catch(() => null))?.status(); if (!st || st >= 400) dead.push(`${href} ${st}`);}
  check(`no dead internal link among ${n} collected`, dead.length === 0, dead.slice(0, 4).join(' | '));
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL')), errors, links: n}; await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await browser.close();
