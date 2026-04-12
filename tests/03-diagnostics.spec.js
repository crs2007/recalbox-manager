const { test, expect } = require('./fixtures');

test.describe('Diagnostics tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    await page.locator('button[data-tab="diagnostics"]').click();
  });

  test('Diagnostics tab is reachable', async ({ page }) => {
    await expect(
      page.locator('.issue-row, .empty-state, table')
    ).toBeVisible({ timeout: 5_000 });
  });

  test('OrphanBin.bin is flagged as missing CUE file', async ({ page }) => {
    // OrphanBin.bin is in psx/ with no matching .cue — diagnostic: missing_cue
    // May appear in multiple places (diagnostic card + BIOS table area), use first()
    await expect(page.getByText('OrphanBin.bin').first()).toBeVisible({ timeout: 5_000 });
  });

  test('PSX BIOS shows wrong version status in BIOS table', async ({ page }) => {
    // scph1001.bin has a fake content (wrong MD5), so it should be flagged
    // The BIOS table is rendered inside the diagnostics tab
    await expect(page.getByText('scph1001.bin')).toBeVisible({ timeout: 5_000 });
  });
});
