// Cut photo regions out of the approved reference render (the only source of these photos) and upscale 2x.
import {chromium} from 'playwright'; import fs from 'fs';
const [src, out] = process.argv.slice(2); const R = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
const b = await chromium.launch(); const p = await b.newPage(); const data = fs.readFileSync(src).toString('base64');
for (const [name, [x, y, w, h, scale = 2]] of Object.entries(R)) {
  const res = await p.evaluate(async ([d, x, y, w, h, s]) => {const i = new Image(); await new Promise(r => {i.onload = r; i.src = 'data:image/jpeg;base64,' + d;}); const c = document.createElement('canvas'); c.width = Math.round(w * s); c.height = Math.round(h * s); const g = c.getContext('2d'); g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high'; g.drawImage(i, x, y, w, h, 0, 0, c.width, c.height);
    const px = g.getImageData(c.width - 3, 3, 1, 1).data; return {url: c.toDataURL('image/jpeg', 0.9), corner: [...px].slice(0, 3)};}, [data, x, y, w, h, scale]);
  fs.writeFileSync(`${out}/${name}.jpg`, Buffer.from(res.url.split(',')[1], 'base64')); console.log(name, res.corner.join(','));
}
await b.close();
