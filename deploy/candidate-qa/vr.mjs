// Visual regression: baseline (682f5eb, :3397) vs candidate (:3396), same API, desktop + mobile.
import {chromium} from 'playwright';
import fs from 'fs';
const OUT = process.argv[2]; fs.mkdirSync(OUT, {recursive: true});
const PAGES = ['/', '/hotels', '/hotels?country=IR', '/hotels/pars-hotel', '/tours', '/flights', '/trains', '/destinations', '/login', '/villas', '/contact'];
const browser = await chromium.launch(); const res = [];
// pick a real, unedited OSM hotel slug for the detail page
const api = await (await fetch('http://127.0.0.1:18137/catalog/hotels?country=IR&has_image=true&limit=1')).json(); PAGES[3] = '/hotels/' + api.items[0].slug;
for (const [name, vp] of [['desktop', {width: 1440, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  for (const path of PAGES) {
    const shots = [];
    for (const port of [3397, 3396]) {
      const ctx = await browser.newContext({viewport: vp, locale: 'fa-IR', reducedMotion: 'reduce'}); const page = await ctx.newPage();
      await page.goto(`http://127.0.0.1:${port}${path}`, {waitUntil: 'networkidle'}); await page.waitForTimeout(1200);
      await page.addStyleTag({content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
      shots.push(await page.screenshot({fullPage: true, animations: 'disabled'})); await ctx.close();
    }
    const same = shots[0].equals(shots[1]); let diff = 0, dims = '';
    if (!same) {
      const ctx = await browser.newContext(); const page = await ctx.newPage();
      const r = await page.evaluate(async ([a, b]) => {
        const load = s => new Promise(r => {const i = new Image(); i.onload = () => r(i); i.src = 'data:image/png;base64,' + s;});
        const [ia, ib] = [await load(a), await load(b)]; const w = Math.max(ia.width, ib.width), h = Math.max(ia.height, ib.height);
        const px = i => {const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); x.drawImage(i, 0, 0); return x.getImageData(0, 0, w, h).data;};
        const [da, db] = [px(ia), px(ib)]; let n = 0, top = -1, bottom = -1;
        for (let i = 0; i < da.length; i += 4) if (Math.abs(da[i] - db[i]) + Math.abs(da[i + 1] - db[i + 1]) + Math.abs(da[i + 2] - db[i + 2]) > 30) {n++; const y = Math.floor(i / 4 / w); if (top < 0) top = y; bottom = y;}
        return {pct: +(100 * n / (w * h)).toFixed(3), dims: `${ia.width}x${ia.height} vs ${ib.width}x${ib.height}`, rows: `${top}-${bottom}`};
      }, shots.map(s => s.toString('base64')));
      diff = r.pct; dims = r.dims + ' rows ' + r.rows; await ctx.close();
      const tag = `${name}${path.replace(/[^a-z0-9]+/gi, '_')}`; fs.writeFileSync(`${OUT}/${tag}_base.png`, shots[0]); fs.writeFileSync(`${OUT}/${tag}_cand.png`, shots[1]);
    }
    res.push(`${name} ${path} ${same ? 'IDENTICAL' : `DIFF ${diff}% ${dims}`}`);
  }
}
console.log(res.join('\n')); await browser.close();
