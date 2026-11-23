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
  // Flight results sort by the flight-specific orderings (cheapest/best/fastest).
  await page.getByRole('group', { name: 'مرتب‌سازی نتایج' }).getByRole('button', { name: 'ارزان‌ترین' }).click(); // flight results use Stitch sort pills
  // Zero results: honest empty state in the normal results layout; the callback request is a secondary, collapsible action.
  const zeroResults = page.getByRole('region', { name: 'بدون نتیجهٔ آنلاین' });
  const failure = page.getByRole('alert').filter({ hasText: 'جست‌وجو فعلاً انجام نشد' });
  await expect(zeroResults).toBeVisible();
  await expect(failure).toHaveCount(0);
  await delayed.fulfill({ status: 503, json: { detail: 'Mock stale failure' } });
  // Give the released response time to reach React before checking final state.
  await page.waitForTimeout(300);
  await expect(zeroResults).toBeVisible();
  await expect(failure).toHaveCount(0);
});
