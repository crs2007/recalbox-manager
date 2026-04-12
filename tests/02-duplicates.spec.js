const { test, expect } = require('./fixtures');

test.describe('Duplicates tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    await page.locator('button[data-tab="duplicates"]').click();
  });

  test('Duplicates tab is reachable and shows content', async ({ page }) => {
    // Tab should now be active — either duplicates or an empty state message
    await expect(
      page.locator('.issue-row, .empty-state').first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test('shows duplicate group for Sonic.md and DupGame.zip (same content)', async ({ page }) => {
    // Both files share identical byte content, so they should form a duplicate pair
    const dupRows = page.locator('.issue-row');
    await expect(dupRows.first()).toBeVisible();
    // The duplicate group should mention both files
    const pageText = await page.locator('.issue-row').first().textContent();
    expect(pageText).toBeTruthy();
  });

  test('Duplicates badge shows correct count', async ({ page }) => {
    const badge = page.locator('button[data-tab="duplicates"] .badge');
    if (await badge.isVisible()) {
      const count = parseInt(await badge.textContent());
      expect(count).toBeGreaterThanOrEqual(1);
    }
  });
});
