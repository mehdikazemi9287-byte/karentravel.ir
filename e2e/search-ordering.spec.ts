import { expect, test, type Route } from '@playwright/test';

test('an older search failure cannot overwrite the latest successful search', async ({ page }) => {
  let releaseFirst!: (route: Route) => void;
  const first = new Promise<Route>(resolve => { releaseFirst = resolve; });
  let count = 0;
  await page.route('**/search/v3/public', async route => {
    count += 1;
    if (count === 1) { releaseFirst(route); return; }
    await route.fulfill({ json: { entities: [], pagination: { total: 0 }, provider_diagnostics: [], zero_result_recovery: [] } });
  });
  await page.goto('/search/results?vertical=flight&destination=Mock');
  const delayed = await first;
  await page.getByLabel('مرتب‌سازی نتایج').selectOption('lowest_price');
  await expect(page.getByRole('heading', { name: 'نتیجه‌ای پیدا نشد' })).toBeVisible();
  await delayed.fulfill({ status: 503, json: { detail: 'Mock stale failure' } });
  // Give the released response time to reach React before checking final state.
  await page.waitForTimeout(300);
  await expect(page.getByRole('heading', { name: 'نتیجه‌ای پیدا نشد' })).toBeVisible();
  await expect(page.locator('.results-notice[role=alert]')).toHaveCount(0);
});
