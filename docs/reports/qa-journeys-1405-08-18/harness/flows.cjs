// Shared UI flows for persona journeys (local QA stack only).
const { WEB } = require('./lib.cjs');
const D = n => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
const trainUrl = (adults = 1, sort = 'recommended') => `${WEB}/search/results?vertical=train&origin=تهران&destination=مشهد&depart=${D(12)}&adults=${adults}&sort=${sort}`;
const flightUrl = (adults = 1, sort = 'recommended') => `${WEB}/search/results?vertical=flight&origin=تهران&destination=شیراز&depart=${D(15)}&adults=${adults}&trip_type=one_way&sort=${sort}`;
async function mainText(page) { return (await page.locator('main').first().innerText().catch(() => page.locator('body').innerText())).replace(/\s*\n+\s*/g, ' | '); }
async function status(page) { const s = page.getByRole('status'); const n = await s.count(); const out = []; for (let i = 0; i < n; i++) out.push((await s.nth(i).innerText().catch(() => '')).trim()); return out.filter(Boolean).join(' / '); }
// From a results page: price-check the first (or nth) card and continue to checkout. Returns reservation id.
async function priceCheckAndBook(page, nth = 0) {
  await page.getByRole('button', { name: 'بررسی قیمت و موجودی' }).nth(nth).click();
  await page.getByRole('button', { name: 'ادامه رزرو' }).first().waitFor({ timeout: 10000 });
  await page.getByRole('button', { name: 'ادامه رزرو' }).first().click();
  await page.waitForURL(/\/checkout\//, { timeout: 15000 });
  return page.url().split('/checkout/')[1].split('?')[0];
}
async function clickWait(page, name, ms = 900) { await page.getByRole('button', { name, exact: true }).first().click(); await page.waitForTimeout(ms); }
// Drive the checkout stages. travellers: names to add; funding {wallet, credit}. Stops at awaiting_payment / awaiting_fulfillment or on error.
async function runCheckout(page, travellers, funding = {}) {
  const log = [];
  await clickWait(page, 'شروع یا ادامهٔ رزرو');
  for (const name of travellers) {
    await page.getByLabel(/نام و نام خانوادگی مسافر/).fill(name);
    await clickWait(page, 'افزودن مسافر', 700);
  }
  log.push('travellers:' + await status(page));
  await clickWait(page, 'تأیید مسافران'); log.push('confirm:' + await status(page));
  await clickWait(page, 'بررسی قیمت و موجودی'); log.push('recheck:' + await status(page));
  await clickWait(page, 'شرایط را خواندم و می‌پذیرم'); log.push('policy:' + await status(page));
  if (funding.wallet) await page.getByLabel(/مبلغ از کیف پول/).fill(String(funding.wallet));
  if (funding.credit) await page.getByLabel(/مبلغ از اعتبار سازمانی/).fill(String(funding.credit));
  const fundBtn = page.getByRole('button', { name: 'تأیید روش پرداخت' });
  if (await fundBtn.isDisabled()) { log.push('funding-button-disabled'); return log; }
  await clickWait(page, 'تأیید روش پرداخت'); log.push('funding:' + await status(page));
  if (!(await page.getByRole('button', { name: 'دریافت پیش‌فاکتور' }).count())) return log;
  await clickWait(page, 'دریافت پیش‌فاکتور'); log.push('invoice:' + await status(page));
  await clickWait(page, 'ادامه به پرداخت'); log.push('payment:' + await status(page));
  return log;
}
module.exports = { D, trainUrl, flightUrl, mainText, status, priceCheckAndBook, runCheckout, clickWait };
