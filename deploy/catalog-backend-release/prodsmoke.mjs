// Read-only browser smoke of the live site (public pages only; no form is submitted).
// Usage: node prodsmoke.mjs <outDir> [beforeDir]
import {chromium} from 'playwright'; import fs from 'fs'; import crypto from 'crypto';
const WEB = 'http://95.38.184.209', OUT = process.argv[2], BEFORE = process.argv[3]; fs.mkdirSync(OUT, {recursive: true});
const PAGES = ['/', '/search', '/search/results?vertical=hotel&destination=%D8%AA%D9%87%D8%B1%D8%A7%D9%86', '/hotels', '/tours', '/flights', '/trains', '/villas', '/login', '/register', '/account', '/trips', '/booking', '/contact', '/support', '/admin', '/supplier', '/finance'];
const browser = await chromium.launch(); const summary = {}; let bad = 0;
for (const [vpName, vp] of [['desktop', {width: 1440, height: 900}], ['mobile', {width: 390, height: 844}]]) {
  const ctx = await browser.newContext({viewport: vp, locale: 'fa-IR', reducedMotion: 'reduce'}); const page = await ctx.newPage(); let api5xx = [], jsErrors = [], apiCalls = {};
  page.on('response', r => {if (r.url().includes(':8000/')) {const k = `${r.request().method()} ${new URL(r.url()).pathname}`; apiCalls[k] = r.status(); if (r.status() >= 500) api5xx.push(`${k} ${r.status()}`);}});
  page.on('pageerror', e => jsErrors.push(String(e).slice(0, 120)));
  for (const path of PAGES) {
    const res = await page.goto(WEB + path, {waitUntil: 'networkidle'}); await page.waitForTimeout(1500);
    await page.evaluate(async () => {await Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => {i.onload = i.onerror = r; setTimeout(r, 4000);})));});
    await page.addStyleTag({content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
    const shot = await page.screenshot({fullPage: true, animations: 'disabled'}); const tag = `${vpName}${path.replace(/[^a-z0-9]+/gi, '_').slice(0, 40)}`;
    fs.writeFileSync(`${OUT}/${tag}.png`, shot); const text = (await page.innerText('body')).replace(/\d{1,2}:\d{2}(:\d{2})?/g, ''); fs.writeFileSync(`${OUT}/${tag}.txt`, text);
    summary[tag] = {status: res.status(), sha: crypto.createHash('sha1').update(shot).digest('hex').slice(0, 12), textSha: crypto.createHash('sha1').update(text).digest('hex').slice(0, 12)};
  }
  summary[`_${vpName}`] = {api5xx, jsErrors: [...new Set(jsErrors)], apiCalls};
  await ctx.close();
}
fs.writeFileSync(`${OUT}/summary.json`, JSON.stringify(summary, null, 1));
const pages = Object.entries(summary).filter(([k]) => !k.startsWith('_'));
console.log('pages', pages.length, 'http200', pages.filter(([, v]) => v.status === 200).length, '| api5xx', summary._desktop.api5xx.concat(summary._mobile.api5xx), '| jsErrors', summary._desktop.jsErrors.concat(summary._mobile.jsErrors).length, '| api calls seen', Object.keys({...summary._desktop.apiCalls, ...summary._mobile.apiCalls}).length);
if (BEFORE) {
  const b = JSON.parse(fs.readFileSync(`${BEFORE}/summary.json`)); let px = 0, tx = 0; const notes = [];
  for (const [k, v] of pages) {if (b[k].status !== v.status) {bad++; notes.push(`${k}: http ${b[k].status} -> ${v.status}`);} if (b[k].textSha !== v.textSha) {tx++; bad++; notes.push(`${k}: TEXT differs`);} else if (b[k].sha !== v.sha) {px++; notes.push(`${k}: pixels differ (text identical)`);}}
  for (const vp of ['_desktop', '_mobile']) {const ca = JSON.stringify(b[vp].apiCalls), cb = JSON.stringify(summary[vp].apiCalls); if (ca !== cb) {bad++; notes.push(`${vp}: API call statuses changed\n   before ${ca}\n   after  ${cb}`);} if (summary[vp].api5xx.length > b[vp].api5xx.length || summary[vp].jsErrors.length > b[vp].jsErrors.length) {bad++; notes.push(`${vp}: new errors`);}}
  console.log('COMPARE_WITH_BEFORE: pixel-identical', pages.length - px - tx, 'of', pages.length, '| text changed', tx, '| pixel-only', px); notes.forEach(n => console.log('  ', n));
}
await browser.close(); process.exit(bad ? 1 : 0);
