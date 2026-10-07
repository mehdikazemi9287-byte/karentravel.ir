// Side-by-side sheet: approved reference (left) and the running site (right), same height scale.
import {chromium} from 'playwright'; import fs from 'fs';
const [url, ref, out, w] = [process.argv[2], process.argv[3], process.argv[4], Number(process.argv[5] || 1440)];
const b = await chromium.launch(); const p = await (await b.newContext({viewport: {width: w, height: 900}, locale: 'fa-IR'})).newPage();
await p.goto(url, {waitUntil: 'networkidle'}); await p.waitForTimeout(1500); const shot = (await p.screenshot({fullPage: true})).toString('base64'); fs.writeFileSync(out.replace('.png', '-site.png'), Buffer.from(shot, 'base64'));
const q = await (await b.newContext({viewport: {width: 1300, height: 1400}})).newPage();
await q.setContent(`<body style="margin:0;display:flex;gap:10px;background:#777;align-items:flex-start"><img style="width:640px" src="data:image/jpeg;base64,${fs.readFileSync(ref).toString('base64')}"><img style="width:640px" src="data:image/png;base64,${shot}"></body>`); await q.waitForTimeout(500);
await q.screenshot({path: out, fullPage: true}); await b.close();
