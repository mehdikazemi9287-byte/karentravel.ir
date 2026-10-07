// Production after the frontend was put back: the previous frontend against the released API. Read-only.
import {chromium} from 'playwright'; import {execSync} from 'child_process';
const WEB = 'http://95.38.184.209', API = 'http://95.38.184.209:8000', OUT = process.argv[2];
const psql = q => execSync(`docker exec -i karenseir-db-1 psql -U karenseir -d karenseir -At`, {input: q}).toString().trim().split('\n')[0];
const cl = psql("select h.slug||'|'||h.name_fa||'|'||h.city_id from catalog_hotels h where h.source='checkline' and h.status='published' and h.duplicate_of is null and h.name_fa is not null and h.description is not null and h.image_url is not null order by h.id limit 1").split('|');
const osm = psql("select slug from catalog_hotels where source='openstreetmap' and status='published' and image_url is not null order by id limit 1");
const b = await chromium.launch(); const out = {};
for (const [vp, size] of [['desktop', {width: 1366, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const r = []; const ctx = await b.newContext({viewport: size, locale: 'fa-IR'}); const page = await ctx.newPage(); const errors = [], bad = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 100))); page.on('response', res => {if (res.url().startsWith(API) && res.status() >= 500) bad.push(`${res.status()} ${res.url().slice(API.length, API.length + 60)}`);});
  for (const p of ['/', '/hotels', `/hotels?city=${cl[2]}`, '/hotels/' + cl[0], '/hotels/' + osm, '/tours', '/flights', '/trains', '/villas', '/destinations', '/destinations/shiraz', '/visa', '/attractions', '/services', '/login', '/contact', '/search/results?vertical=hotel&destination=' + encodeURIComponent('شیراز')]) {
    const res = await page.goto(WEB + p, {waitUntil: 'networkidle'}); await page.waitForTimeout(900);
    const s = await page.evaluate(() => ({fits: document.documentElement.scrollWidth <= document.documentElement.clientWidth, dir: document.documentElement.dir, broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.currentSrc).length, text: document.body.innerText.length, price: /\d[\d٬,]*\s*(ریال|تومان)/.test(document.querySelector('.cat, .cat-detail')?.innerText || '')}));
    const ok = res.status() === 200 && s.fits && s.dir === 'rtl' && s.broken === 0 && s.text > 200 && !s.price; r.push(`${ok ? 'PASS' : 'FAIL'} ${decodeURIComponent(p).slice(0, 50)} ${ok ? '' : JSON.stringify({st: res.status(), ...s})}`);
    if (p === '/' || p.startsWith('/hotels/checkline')) await page.screenshot({path: `${OUT}/oldfe-${p === '/' ? 'home' : 'clhotel'}-${vp}.png`, fullPage: true});
  }
  r.push(`${errors.length === 0 && bad.length === 0 ? 'PASS' : 'FAIL'} no script error, no API 5xx ${[...errors, ...bad].slice(0, 3).join(' | ')}`);
  out[vp] = {pass: r.filter(x => x.startsWith('PASS')).length, fail: r.filter(x => x.startsWith('FAIL'))}; await ctx.close();
}
console.log(JSON.stringify(out, null, 1)); await b.close();
