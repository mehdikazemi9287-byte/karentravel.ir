#!/usr/bin/env node
// SEO smoke check for KarenSeir public pages — no browser, no JS: it reads the HTML a crawler gets.
// Usage: node tests/seo/seo-check.mjs [base-url] [expected-origin] [--snapshot dir] [--json file]
//   base-url         where the app answers (default http://127.0.0.1:3000)
//   expected-origin  the origin robots/sitemap/canonical must use (default https://karentravel.ir)
// Exit code 1 when a hard rule fails (robots, sitemap, canonical, noindex on a public page, H1 count, status).
import {writeFileSync, mkdirSync} from 'node:fs';
import {PUBLIC_ROUTES} from './public-routes.mjs';

const args = process.argv.slice(2);
const flag = name => { const i = args.indexOf(name); if (i < 0) return null; const v = args[i + 1]; args.splice(i, 2); return v; };
const snapshotDir = flag('--snapshot');
const jsonOut = flag('--json');
const base = (args[0] || 'http://127.0.0.1:3000').replace(/\/$/, '');
const origin = (args[1] || 'https://karentravel.ir').replace(/\/$/, '');
const UA = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)';
const fails = []; const warns = [];
const fail = m => fails.push(m); const warn = m => warns.push(m);
const get = async path => { const r = await fetch(base + path, {headers: {'user-agent': UA}, redirect: 'manual'}); return {status: r.status, location: r.headers.get('location'), text: await r.text()}; };
const decode = s => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const attr = (tag, name) => { const m = tag.match(new RegExp(`\\s${name}="([^"]*)"`)); return m ? decode(m[1]) : null; };
const metaContent = (html, name) => { const t = [...html.matchAll(/<meta\s[^>]*>/g)].map(m => m[0]).find(t => attr(t, 'name') === name); return t ? attr(t, 'content') : null; };

// --- robots.txt
const robots = await get('/robots.txt');
if (robots.status !== 200) fail(`robots.txt status ${robots.status}`);
const robotLines = robots.text.split(/\r?\n/).map(l => l.trim());
if (robotLines.some(l => /^disallow:\s*\/\s*$/i.test(l))) fail('robots.txt blocks the whole site (Disallow: /)');
const sitemapLine = robotLines.find(l => /^sitemap:/i.test(l));
if (!sitemapLine) fail('robots.txt has no Sitemap line');
else if (sitemapLine.replace(/^sitemap:\s*/i, '') !== `${origin}/sitemap.xml`) fail(`robots.txt Sitemap is "${sitemapLine}", want ${origin}/sitemap.xml`);
const disallowed = robotLines.filter(l => /^disallow:/i.test(l)).map(l => l.replace(/^disallow:\s*/i, '')).filter(Boolean);

// --- sitemap.xml
const sm = await get('/sitemap.xml');
if (sm.status !== 200) fail(`sitemap.xml status ${sm.status}`);
const smUrls = [...sm.text.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => decode(m[1]));
if (!smUrls.length) fail('sitemap.xml has no <loc>');
for (const u of smUrls) if (!u.startsWith(origin + '/') && u !== origin) fail(`sitemap URL on wrong origin: ${u}`);
const smPaths = smUrls.map(u => { const p = u.slice(origin.length) || '/'; return p; });
for (const p of smPaths) if (disallowed.some(d => p.startsWith(d))) fail(`sitemap lists a robots-disallowed path: ${p}`);
for (const r of PUBLIC_ROUTES.filter(r => r.sitemap !== false)) if (!smPaths.includes(r.path)) fail(`sitemap misses public page ${r.path}`);

// --- every public page (+ every fixed sitemap entry)
const paths = [...new Set([...PUBLIC_ROUTES.map(r => r.path), ...smPaths.filter(p => !p.includes('/blog/') || PUBLIC_ROUTES.some(r => r.path === p))])];
const rows = []; const titles = new Map();
if (snapshotDir) mkdirSync(snapshotDir, {recursive: true});
for (const path of paths) {
  const res = await get(path);
  const html = res.text;
  const title = decode((html.match(/<title>([^<]*)<\/title>/) || [])[1] || '');
  const description = metaContent(html, 'description');
  const robotsMeta = metaContent(html, 'robots');
  const canonTag = (html.match(/<link\s[^>]*rel="canonical"[^>]*>/) || [])[0];
  const canonical = canonTag ? attr(canonTag, 'href') : null;
  const body = html.replace(/<head>[\s\S]*?<\/head>/, '').replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '');
  const h1 = (body.match(/<h1[\s>]/g) || []).length;
  const imgs = [...body.matchAll(/<img\s[^>]*>/g)].map(m => m[0]);
  const noAlt = imgs.filter(t => { const a = attr(t, 'alt'); return a === null || (a === '' && !/aria-hidden="true"/.test(t)); }).length;
  const text = body.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  const ld = [...html.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)].map(m => { try { const j = JSON.parse(m[1]); return [].concat(j).map(x => x['@type']).join('+'); } catch { return 'INVALID'; } });
  const noindex = /noindex/i.test(robotsMeta || '');
  const row = {path, status: res.status, title, description, descLen: description ? [...description].length : 0, canonical, h1, imgs: imgs.length, noAlt, textChars: text.length, jsonLd: ld, noindex};
  rows.push(row);
  if (snapshotDir) writeFileSync(`${snapshotDir}/${path === '/' ? 'home' : path.slice(1).replace(/\//g, '__')}.html`, body.replace(/nonce="[^"]*"/g, ''));
  if (res.status !== 200) { fail(`${path}: status ${res.status}${res.location ? ' → ' + res.location : ''}`); continue; }
  if (noindex) fail(`${path}: public page is noindex`);
  const want = origin + (path === '/' ? '' : path);
  if (!canonical) fail(`${path}: no canonical`);
  else if (canonical !== want && canonical !== want + '/') fail(`${path}: canonical ${canonical}, want ${want}`);
  if (h1 !== 1) fail(`${path}: ${h1} <h1> (want exactly 1)`);
  if (!title.includes('کارن تراول')) warn(`${path}: title without brand: ${title}`);
  if (titles.has(title)) fail(`${path}: same title as ${titles.get(title)}: ${title}`); else titles.set(title, path);
  if (!description) fail(`${path}: no meta description`);
  else if (row.descLen < 120 || row.descLen > 160) warn(`${path}: description ${row.descLen} chars (want 120–160)`);
  if (noAlt) fail(`${path}: ${noAlt} <img> without alt`);
  if (text.length < 400) warn(`${path}: only ${text.length} chars of text without JS`);
}

// --- a missing page must be a real 404 (and noindex is fine there)
const missing = await get('/this-page-does-not-exist-seo-check');
if (missing.status !== 404) fail(`missing page answers ${missing.status}, want 404`);

if (jsonOut) writeFileSync(jsonOut, JSON.stringify({base, origin, rows, fails, warns, sitemap: smPaths}, null, 2));
for (const r of rows) console.log(`${r.status} ${r.path}  h1=${r.h1} canon=${r.canonical ? 'yes' : 'NO'} desc=${r.descLen} noAlt=${r.noAlt} text=${r.textChars} ld=[${r.jsonLd}]${r.noindex ? ' NOINDEX' : ''}  ${r.title}`);
console.log(`\nsitemap: ${smPaths.length} URLs`);
for (const w of warns) console.log('WARN', w);
for (const f of fails) console.log('FAIL', f);
console.log(fails.length ? `\n${fails.length} failure(s)` : '\nSEO check passed');
process.exit(fails.length ? 1 : 0);
