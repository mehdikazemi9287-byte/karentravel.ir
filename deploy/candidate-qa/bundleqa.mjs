// Candidate browser QA for the CheckLine bundle content: search -> results -> detail for hotels, destinations and tours. Desktop + mobile.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = 'http://127.0.0.1:3396', API = 'http://127.0.0.1:18137', OUT = process.argv[2];
const psql = q => execSync(`docker exec -i ks-catalog-scratch-pg psql -U postgres -d ks_cand37 -At`, {input: q}).toString().trim().split('\n')[0];
const get = async p => (await fetch(API + p)).json();
const hotel = psql("select h.slug||'|'||h.name_fa from catalog_hotels h where h.source='checkline' and h.status='published' and h.description is not null and h.details_json like '%nearby%' and exists (select 1 from catalog_hotel_room_types r where r.hotel_id=h.id) and (select count(*) from catalog_hotel_images i where i.hotel_id=h.id) >= 3 order by h.id limit 1").split('|');
const draft = psql("select slug from catalog_hotels where source='checkline' and status='draft' limit 1");
const tour = psql("select t.id||'|'||t.title_fa from catalog_tours t where t.status='published' and t.description is not null and exists (select 1 from catalog_tour_hotels x join catalog_hotels h on h.id=x.hotel_id where x.tour_id=t.id and h.status='published') and exists (select 1 from catalog_tour_departures d where d.tour_id=t.id) order by t.id desc limit 1").split('|');
const city = psql("select p.id from catalog_places p where p.kind='city' and p.source='checkline' and p.description is not null and p.hotel_count>0 order by p.hotel_count desc limit 1");
const country = psql("select id from catalog_places where kind='country' and details_json like '%visa_note%' and details_json like '%capital%' limit 1");
const tourPlace = psql("select destination_place_id from catalog_tours where status='published' and destination_place_id is not null group by 1 order by count(*) desc limit 1");
const browser = await chromium.launch(); const out = {};
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const check = (n, ok, e = '') => r.push(`${ok ? 'PASS' : 'FAIL'} ${n}${e !== '' ? ' — ' + String(e).slice(0, 110) : ''}`);
  const ctx = await browser.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e).slice(0, 100)));
  const open = async p => {await page.goto(WEB + p, {waitUntil: 'networkidle'}); await page.waitForTimeout(600);};
  const text = () => page.locator('main').first().innerText();
  const fits = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  // ---- search (autocomplete API) -> results -> detail : hotel
  const word = hotel[1].replace(/^هتل\s*/, '').split(' ')[0];
  const sug = await get('/catalog/suggest?q=' + encodeURIComponent(hotel[1]));
  check('autocomplete returns the bundle hotel', sug.items.some(i => i.type === 'hotel' && i.href === '/hotels/' + hotel[0]));
  await page.route(API + '/catalog/hotels?**', async route => {await new Promise(res => setTimeout(res, 800)); await route.continue();});
  await page.goto(`${WEB}/hotels?q=${encodeURIComponent(hotel[1])}`, {waitUntil: 'domcontentloaded'});
  check('hotel results: loading state', await page.locator('[role=status]').first().waitFor({timeout: 6000}).then(() => true).catch(() => false)); await page.unroute(API + '/catalog/hotels?**');
  await page.waitForSelector(`a[href="/hotels/${hotel[0]}"]`); const card = page.locator(`a[href="/hotels/${hotel[0]}"]`).first();
  check('hotel results: card with image, no price number', (await card.locator('img').count()) === 1 && /استعلام/.test(await card.innerText()) && !/ریال|تومان/.test(await card.innerText()));
  await card.click(); await page.waitForSelector('.cat-gallery img'); await page.waitForTimeout(500);
  const imgs = await page.evaluate(async () => {const a = [...document.querySelectorAll('.cat-gallery img')]; a.forEach(i => {i.loading = 'eager';}); await Promise.all(a.map(i => i.complete ? 0 : new Promise(res => {i.onload = i.onerror = res; setTimeout(res, 20000);}))); return [a.length, a.filter(i => i.naturalWidth > 0).length];});
  const t1 = await text();
  check('hotel detail: gallery images load from the source site', imgs[0] >= 3 && imgs[1] === imgs[0], imgs.join('/'));
  check('hotel detail: description, facts, distances, room types', /دربارهٔ اقامتگاه/.test(t1) && /مشخصات اقامتگاه/.test(t1) && /فاصله تا مکان‌های مهم/.test(t1) && /انواع اتاق/.test(t1));
  check('hotel detail: inquiry only, no price, image rights noted', /قیمت پس از انتخاب تاریخ و استعلام/.test(t1) && !/\d[\d٬,]*\s*(ریال|تومان)/.test(t1) && /rights unverified/.test(await page.locator('.cat-gallery').innerText()));
  check('hotel detail: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/bundle-hotel-${vp}.png`, fullPage: true});
  await open('/hotels/' + draft); check('draft hotel is not public', /پیدا نشد/.test(await text()));
  await open('/hotels?q=zzzzqqqq'); check('hotel results: empty state', /اقامتگاهی با این شرایط ثبت نشده است/.test(await text()));
  // ---- destinations
  await open('/destinations/' + city); const t2 = await text();
  check('city page: description and hotels from the bundle', t2.length > 400 && /هتل و اقامتگاه/.test(t2) && /اطلاعات مقصد|سفر به/.test(t2));
  await page.locator('.cat-place-stats a').first().click(); await page.waitForSelector('.cat-grid a'); check('city page -> hotel results for that city', (await page.locator('.cat-grid a').count()) >= 1 && new RegExp('city=' + city).test(page.url()));
  await open('/destinations/' + country); const t3 = await text(); check('country page: capital, currency, visa note', /پایتخت/.test(t3) && /واحد پول/.test(t3) && /ویزا/.test(t3));
  await open('/destinations/' + tourPlace); await page.waitForTimeout(500); check('destination page lists past tours to it', /تورهای برگزارشده به این مقصد/.test(await text()) && (await page.locator('a[href^="/tours/reference/"]').count()) >= 1);
  check('destination pages: no horizontal overflow', await fits());
  // ---- tours
  await open('/tours'); check('tours page shows the reference programme section', /برنامهٔ تورهای برگزارشده/.test(await text()) && (await page.locator('#tour-catalog a[href^="/tours/reference/"]').count()) >= 1);
  await open('/tours/reference'); await page.waitForSelector('#tour-catalog .cat-grid a'); const total = await page.locator('.cat-meta span').first().innerText();
  check('tour list: total and destination chips', /تور/.test(total) && (await page.locator('[aria-label="مقصد تور"] button').count()) >= 3, total);
  await page.locator('[aria-label="مقصد تور"] button').nth(1).click(); await page.waitForTimeout(900); check('tour list: destination filter', /destination=/.test(page.url()) && (await page.locator('#tour-catalog .cat-grid a').count()) >= 1);
  await open('/tours/reference?tq=zzzzqqqq'); check('tour list: empty state', /توری با این شرایط ثبت نشده است/.test(await text()));
  const tsug = await get('/catalog/suggest?q=' + encodeURIComponent(tour[1].split(' ').slice(0, 3).join(' '))); check('autocomplete returns reference tours', tsug.items.some(i => i.type === 'tour'));
  await open('/tours/reference/' + tour[0]); const t4 = await text();
  check('tour detail: programme, facts, hotels, past dates', /دربارهٔ تور/.test(t4) && /مشخصات/.test(t4) && /هتل‌های این تور/.test(t4) && /تاریخ‌های برگزارشده/.test(t4) && /قابل رزرو نیست/.test(t4));
  check('tour detail: inquiry only, no price, no booking button', /استعلام تاریخ و قیمت جدید/.test(t4) && !/\d[\d٬,]*\s*(ریال|تومان)/.test(t4) && !(await page.locator('main button:has-text("رزرو")').count()));
  check('tour detail: no horizontal overflow', await fits()); await page.screenshot({path: `${OUT}/bundle-tour-${vp}.png`, fullPage: true});
  const hlink = page.locator('main a[href^="/hotels/checkline-"]').first(); if (await hlink.count()) {await hlink.click(); await page.waitForURL(/\/hotels\/checkline-/, {timeout: 15000}).catch(() => {}); await page.waitForSelector('.cat-detail-head h1'); check('tour detail -> hotel detail', /\/hotels\/checkline-/.test(page.url()) && /دربارهٔ اقامتگاه|موقعیت و تماس/.test(await page.locator('main').first().innerText()));} else check('tour detail -> hotel detail', false, 'no published hotel link');
  await open('/tours/reference/cl-tour-0'); check('tour detail: error state for unknown tour', /پیدا نشد/.test(await text()));
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL')), errors}; await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await browser.close();
