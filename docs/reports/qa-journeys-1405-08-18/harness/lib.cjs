// QA harness helpers (local stack only). Records PASS/FAIL/BLOCKED per persona step.
const { chromium } = require('playwright');
const fs = require('fs');
const WEB = 'http://127.0.0.1:3000', API = 'http://127.0.0.1:8000';
const SHOTS = '/home/claude/qa-journeys/shots';
const RESULTS = '/home/claude/qa-journeys/results.jsonl';
const fixtures = JSON.parse(fs.readFileSync('/home/claude/qa-journeys/fixtures.json', 'utf8'));
async function launch() { return chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome', args: ['--no-sandbox'] }); }
async function devToken(email) { const r = await fetch(API + '/auth/dev-login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email }) }); if (!r.ok) throw new Error('dev-login ' + r.status); return r.json(); }
async function api(token, method, path, body, extra = {}) { const r = await fetch(API + path, { method, headers: { 'content-type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token.access_token } : {}), ...extra }, body: body ? JSON.stringify(body) : undefined }); let j = null; try { j = await r.json(); } catch {} return { status: r.status, body: j }; }
async function newCtx(browser, { mobile = false, email = null, zoom = null } = {}) {
  const ctx = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: 'fa-IR' } : { viewport: { width: 1440, height: 1000 }, locale: 'fa-IR' });
  if (email) { const s = await devToken(email); await ctx.addInitScript(v => { try { if (!sessionStorage.getItem('qa-injected')) { sessionStorage.setItem('karenseir-auth-session', v); sessionStorage.setItem('qa-injected', '1'); } } catch {} }, JSON.stringify(s)); ctx._session = s; }
  const page = await ctx.newPage();
  page._console = []; page._failed = [];
  page.on('console', m => { if (m.type() === 'error') page._console.push(m.text().slice(0, 300)); });
  page.on('pageerror', e => page._console.push('pageerror: ' + String(e).slice(0, 300)));
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('/_next/')) page._failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(API, 'API').replace(WEB, 'WEB')}`); });
  return { ctx, page };
}
let n = 0;
async function step(persona, name, page, fn, { blocked = null } = {}) {
  const id = String(++n).padStart(3, '0'); const shot = `${SHOTS}/${persona}-${id}.png`;
  page._console.length = 0; page._failed.length = 0;
  let status = 'PASS', note = '';
  if (blocked) { status = 'BLOCKED'; note = blocked; }
  else { try { const r = await fn(); if (typeof r === 'string') note = r; else if (r && r.status) { status = r.status; note = r.note || ''; } } catch (e) { status = 'FAIL'; note = String(e.message || e).split('\n')[0].slice(0, 400); } }
  try { await page.screenshot({ path: shot, fullPage: false }); } catch {}
  const rec = { persona, id, name, status, note, url: page.url().replace(WEB, ''), shot, console: [...page._console].slice(0, 5), failed: [...page._failed].slice(0, 6) };
  fs.appendFileSync(RESULTS, JSON.stringify(rec) + '\n'); console.log(`[${status}] ${persona} ${id} ${name} ${note}`);
  return rec;
}
module.exports = { launch, devToken, api, newCtx, step, fixtures, WEB, API, SHOTS };
