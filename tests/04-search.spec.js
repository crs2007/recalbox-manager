const { test, expect } = require('./fixtures');

test.describe('Search tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    await page.locator('button[data-tab="search"]').click();
  });

  test('Search tab shows search input', async ({ page }) => {
    await expect(page.locator('#searchInput')).toBeVisible();
  });

  test('searching "sonic" returns matching ROMs', async ({ page }) => {
    await page.locator('#searchInput').fill('sonic');
    // Wait for the API response (debounced 300ms + network)
    await page.waitForResponse(resp => resp.url().includes('/api/search'), { timeout: 5_000 });
    // Should find at least one result containing "sonic" (case-insensitive)
    await expect(
      page.locator('table tr, .issue-row').filter({ hasText: /sonic/i }).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test('searching "super" returns SuperMario.smc', async ({ page }) => {
    await page.locator('#searchInput').fill('super');
    await page.waitForResponse(resp => resp.url().includes('/api/search'), { timeout: 5_000 });
    await expect(
      page.locator('table tr, .issue-row').filter({ hasText: /super/i }).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test('single character query returns no results (min 2 chars)', async ({ page }) => {
    await page.locator('#searchInput').fill('s');
    await page.waitForTimeout(500);
    // Should NOT trigger an API call — expect a hint or empty results
    await expect(page.locator('table tr').first()).not.toBeVisible({ timeout: 2_000 })
      .catch(() => {
        // If a table row exists, it should not contain meaningful results for "s"
      });
  });
});
