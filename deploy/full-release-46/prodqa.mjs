// Read-only browser smoke of Production after the full release. Desktop + mobile. No sign-in, no form submit, nothing is written.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = process.argv[3] || 'http://95.38.184.209', API = 'http://95.38.184.209:8000', OUT = process.argv[2];
const psql = q => execSync(`docker exec -i karenseir-db-1 psql -U karenseir -d karenseir -At`, {input: q}).toString().trim().split('\n')[0];
const hotel = psql("select h.slug||'|'||h.name_fa||'|'||h.city_id from catalog_hotels h where h.source='checkline' and h.status='published' and h.duplicate_of is null and h.name_fa is not null and h.city_id is not null and h.description is not null and (select count(*) from catalog_hotel_images i where i.hotel_id=h.id) > 12 and exists (select 1 from catalog_hotel_room_types r where r.hotel_id=h.id and r.image_url is not null) order by h.id limit 1").split('|');
const geoHotel = psql("select slug from catalog_hotels where source='checkline' and status='published' and duplicate_of is null and latitude is not null order by id limit 1");
const tour = psql("select t.slug||'|'||t.title_fa||'|'||t.destination_place_id from catalog_tours t where t.status='published' and t.description is not null and t.slug !~ '^cl-tour' and exists (select 1 from catalog_tour_departures d where d.tour_id=t.id) and exists (select 1 from catalog_tour_hotels x where x.tour_id=t.id) order by t.id desc limit 1").split('|');
const cityName = psql(`select name_fa from catalog_places where id='${hotel[2]}'`);
const visaCountry = psql("select replace(id,'cl-visa-country-','') from catalog_content where kind='visa_country' order by length(body) desc limit 1");
const city = psql("select id from catalog_places where kind='city' and details_json like '%\"images\"%' and description is not null and hotel_count>0 limit 1");
const legacy = psql("select legacy_path||'|'||target_path from catalog_legacy_routes where target_path like '/hotels?%city=%' limit 1").split('|');
if (hotel.length < 3 || tour.length < 3 || legacy.length < 2) {console.log('fixture lookup failed', hotel, tour, legacy); process.exit(1);}
const browser = await chromium.launch(); const out = {};
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (n, ok, e = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${n}${e !== '' ? ' — ' + String(e).slice(0, 140) : ''}`);
  const ctx = await browser.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = [], api5xx = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 100))); page.on('response', res => {if (res.url().startsWith(API) && res.status() >= 500) api5xx.push(`${res.status()} ${res.url().slice(API.length, API.length + 60)}`);});
  const open = async p => {const res = await page.goto(WEB + p, {waitUntil: 'networkidle'}); await page.waitForTimeout(600); return res;};
  const text = () => page.locator('main').first().innerText();
  const fits = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const broken = () => page.evaluate(() => [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.currentSrc).map(i => i.currentSrc.slice(0, 90)));
  const links = new Set(); const collect = async () => {for (const h of await page.$$eval('a[href^="/"]', as => as.map(a => a.getAttribute('href')))) links.add(h);};
  const price = t => /\d[\d٬,]*\s*(ریال|تومان)/.test(t);
  // ---------- home, RTL, navigation
  let res = await open('/'); const html = await page.evaluate(() => ({dir: document.documentElement.dir || getComputedStyle(document.body).direction, lang: document.documentElement.lang, font: getComputedStyle(document.body).fontFamily}));
  check('home 200, RTL, Persian, Vazirmatn', res.status() === 200 && html.dir === 'rtl' && html.lang.startsWith('fa') && /vazir/i.test(html.font), JSON.stringify(html).slice(0, 120));
  check('home: header navigation and footer links', (await page.locator('header a[href^="/"], nav a[href^="/"]').count()) >= 4 && (await page.locator('footer a').count()) >= 3);
  check('home: no horizontal overflow, no broken image', await fits() && (await broken()).length === 0, (await broken()).join(' | ')); await collect(); await page.screenshot({path: `${OUT}/prod-home-${vp}.png`, fullPage: true});
  await page.locator('.fs-tabs button:has-text("هتل")').first().click(); await page.waitForTimeout(400);
  const box = page.locator('input[role=combobox][aria-controls="destination-suggestions"]').first(); await box.click(); await box.fill(hotel[1]); await page.waitForTimeout(2000);
  const opt = page.locator('#destination-suggestions [role=option]').filter({hasText: hotel[1]}).first(); const viaHome = (await opt.count()) > 0; check('home search suggests a catalogue hotel', viaHome);
  if (viaHome) {await opt.click(); await page.waitForURL(u => u.pathname.startsWith('/hotels/'), {timeout: 15000}).catch(() => {}); await page.waitForSelector('.cat-detail-head h1', {timeout: 15000}).catch(() => {}); check('home search: choosing the hotel opens its page', decodeURIComponent(page.url()).endsWith('/hotels/' + hotel[0]));}
  await open(`/search/results?vertical=hotel&destination=${encodeURIComponent(cityName)}`); await page.waitForSelector('#catalog-for-search .cat-grid a', {timeout: 20000}).catch(() => {});
  check('hotel search results list registered hotels without a price', (await page.locator('#catalog-for-search .cat-grid a').count()) >= 1 && !price(await page.locator('#catalog-for-search').innerText().catch(() => '')));
  // ---------- hotels
  await open('/hotels'); await page.waitForSelector('.cat-grid a', {timeout: 20000}); check('hotels list with filters', (await page.locator('.cat-grid a').count()) >= 6 && (await page.locator('.cat-filters select, .cat-filters input').count()) >= 2 && await fits()); await collect();
  await open(`/hotels?city=${hotel[2]}`); await page.waitForSelector('.cat-grid a', {timeout: 20000}); check('hotels by city', (await page.locator('.cat-grid a').count()) >= 1); await collect();
  res = await open('/hotels/' + hotel[0]); await page.waitForSelector('.cat-detail-head h1'); await page.waitForTimeout(2500); let t = await text();
  check('hotel detail: description, rooms, gallery', res.status() === 200 && /دربارهٔ اقامتگاه/.test(t) && /انواع اتاق/.test(t) && (await page.locator('.cat-detail .cat-gallery figure').count()) === 12);
  const loaded = await page.evaluate(() => [...document.querySelectorAll('.cat-gallery img')].slice(0, 4).map(i => i.complete && i.naturalWidth > 0)); check('hotel images really load', loaded.length >= 2 && loaded.slice(0, 2).every(Boolean), JSON.stringify(loaded));
  check('hotel: rate not connected, booking off, no price, inquiry asks to sign in', /نرخ و موجودی\s*متصل نیست/.test(t.replace(/\n/g, ' ')) && /رزرو آنلاین\s*غیرفعال/.test(t.replace(/\n/g, ' ')) && !price(t) && (await page.locator('[data-request-state] a[href="/login"]').count()) === 1);
  check('hotel SEO: title, description, canonical', (await page.title()).includes(hotel[1].slice(0, 12)) && ((await page.locator('meta[name=description]').getAttribute('content')) || '').length > 20 && ((await page.locator('link[rel=canonical]').getAttribute('href').catch(() => '')) || '').endsWith('/hotels/' + hotel[0]), await page.title());
  check('hotel detail fits the viewport', await fits()); await collect(); await page.screenshot({path: `${OUT}/prod-hotel-${vp}.png`, fullPage: true});
  res = await open('/hotels/' + geoHotel); check('hotel with a verified position opens', res.status() === 200 && (await page.locator('.cat-detail-head h1').count()) === 1);
  // ---------- tours
  await open('/tours'); check('tour landing with programmes', /برنامهٔ تورها بر اساس مقصد/.test(await text()) && (await page.locator('#tour-catalog .cat-grid a').count()) >= 3 && await fits()); await collect();
  await open('/tours/search'); await page.waitForSelector('#tour-catalog .cat-grid a', {timeout: 20000}); const all = await page.locator('.cat-meta span').first().innerText();
  await page.locator('.cat-filters select').nth(1).selectOption('7+'); await page.waitForTimeout(1200); check('tour search filters work', (await page.locator('.cat-filters select').count()) === 3 && (await page.locator('.cat-meta span').first().innerText()) !== all); await collect();
  res = await open('/tours/' + encodeURIComponent(tour[0])); t = await text();
  check('tour detail by slug: content, hotels, past dates', res.status() === 200 && /دربارهٔ تور/.test(t) && /هتل‌های این تور/.test(t) && /تاریخ‌های برگزارشده/.test(t));
  check('tour: not bookable, no price', /رزرو آنلاین\s*غیرفعال/.test(t.replace(/\n/g, ' ')) && !price(t) && !(await page.locator('main button:has-text("رزرو")').count()) && await fits()); await collect(); await page.screenshot({path: `${OUT}/prod-tour-${vp}.png`, fullPage: true});
  const tourHotel = await page.locator('main a[href^="/hotels/"]').first().getAttribute('href').catch(() => null); if (tourHotel) {const st = (await ctx.request.get(WEB + tourHotel)).status(); check('tour → hotel relation resolves', st === 200, tourHotel);}
  await open('/tours/destination/' + tour[2]); await page.waitForSelector('#tour-catalog .cat-grid a', {timeout: 20000}); check('tours by destination', (await page.locator('#tour-catalog .cat-grid a').count()) >= 1); await collect();
  // ---------- visa, destinations, attractions
  await open('/visa'); t = await text(); check('visa: country guides and articles', /به تفکیک کشور/.test(t) && (await page.locator('a[href^="/visa/cl-visa-"]').count()) >= 10 && /تضمین نمی‌شود/.test(t) && await fits()); await collect();
  await open('/visa/cl-visa-country-' + visaCountry); t = await text(); check('visa country guide', t.length > 300 && /سفارت مقصد تعیین می‌کند/.test(t) && !price(t)); await collect();
  await open('/destinations'); check('destinations index', (await page.locator('a.customer-destination').count()) === 6 && (await broken()).length === 0 && await fits()); await collect();
  await open('/destinations/shiraz'); await page.waitForSelector('.cat-place h1', {timeout: 20000}).catch(() => {}); check('guide page fed by the catalogue', (await page.locator('.cat-place .cat-crumbs a').count()) >= 2 && await fits());
  await open('/destinations/' + city); await page.waitForSelector('.cat-place h1', {timeout: 20000}); t = await text();
  check('destination: breadcrumbs, gallery, related, hotels', (await page.locator('.cat-place .cat-crumbs a').count()) >= 2 && (await page.locator('.cat-place .cat-gallery img').count()) >= 2 && /مقصدهای مرتبط/.test(t) && /هتل و اقامتگاه/.test(t) && await fits()); await collect();
  await page.locator('.cat-place .cat-crumbs a').nth(1).click(); await page.waitForTimeout(1200); check('breadcrumb: city → country', /\/destinations\/[a-z]{2}$/.test(page.url()));
  await open('/attractions'); check('attractions page', (await page.locator('main a, main article, main li').count()) >= 3 && await fits()); await collect();
  // ---------- other verticals and static routes
  const bad = []; for (const p of ['/flights', '/trains', '/villas', '/services', '/login', '/contact', '/support', '/terms', '/travel-guides', '/handicrafts', '/restaurants', '/car-rental', '/cruises', '/experiences', '/robots.txt', '/sitemap.xml']) {const st = (await ctx.request.get(WEB + p, {maxRedirects: 3})).status(); if (st !== 200) bad.push(`${p} ${st}`);}
  check('service and static routes answer 200', bad.length === 0, bad.join(' | '));
  await open('/flights'); check('flights page renders', (await page.locator('main').count()) >= 1 && await fits() && (await broken()).length === 0);
  await open('/admin/catalog/reference'); check('admin area refuses an anonymous visitor', /وارد شوید/.test(await page.locator('body').innerText()));
  // ---------- old URLs, 404, crawl
  await page.goto(WEB + encodeURI(legacy[0]), {waitUntil: 'networkidle'}); await page.waitForURL(u => u.pathname.startsWith('/hotels'), {timeout: 15000}).catch(() => {}); check('old-site URL redirects to its page', /city=/.test(page.url()), decodeURIComponent(page.url()).replace(WEB, ''));
  const targets = execSync(`docker exec -i karenseir-db-1 psql -U karenseir -d karenseir -At`, {input: 'select distinct target_path from catalog_legacy_routes'}).toString().trim().split('\n'); const badT = [];
  for (const tp of targets) {const st = (await ctx.request.get(WEB + encodeURI(tp), {maxRedirects: 3})).status(); if (st !== 200) badT.push(`${tp} ${st}`);} check(`every old-page target is live (${targets.length})`, badT.length === 0, badT.join(' | '));
  check('unknown URL is a real 404', (await ctx.request.get(WEB + '/no-such-page-xyz/')).status() === 404);
  const dead = []; let n = 0; for (const href of [...links].slice(0, 160)) {n++; const st = await (await ctx.request.get(WEB + href, {maxRedirects: 3}).catch(() => null))?.status(); if (!st || st >= 400) dead.push(`${href} ${st}`);}
  check(`no dead internal link among ${n}`, dead.length === 0, dead.slice(0, 4).join(' | '));
  check('no script error and no API 5xx during the run', errors.length === 0 && api5xx.length === 0, [...errors, ...api5xx].slice(0, 3).join(' | '));
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL')), links: n}; await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await browser.close();
