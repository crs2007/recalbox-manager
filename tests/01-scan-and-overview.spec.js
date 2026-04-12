const { test, expect } = require('./fixtures');

test.describe('Scan and overview', () => {
  test('loads app and shows welcome state before scan', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.header')).toBeVisible();
    await expect(page.getByRole('button', { name: /Scan ROMs/i })).toBeVisible();
  });

  test('scan completes and stat cards appear', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    // Spinner appears while scanning
    await expect(page.locator('.spinner')).toBeVisible({ timeout: 5_000 });
    // Wait for scan to finish (spinner disappears)
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    // Stats grid should now be present with at least one stat card
    await expect(page.locator('.stat-card').first()).toBeVisible();
  });

  test('all 4 mock systems appear in the Systems tab', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    const systemCards = page.locator('.system-card');
    await expect(systemCards.first()).toBeVisible();
    const count = await systemCards.count();
    expect(count).toBeGreaterThanOrEqual(4);
  });

  test('Issues tab badge shows non-zero count for misplaced ROM', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    const issuesBadge = page.locator('button[data-tab="issues"] .badge');
    await expect(issuesBadge).toBeVisible();
    const badgeText = await issuesBadge.textContent();
    expect(parseInt(badgeText)).toBeGreaterThan(0);
  });
});
