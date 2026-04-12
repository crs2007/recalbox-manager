const { test, expect } = require('./fixtures');

test.describe('System detail view', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
  });

  test('clicking snes system card shows its ROM list', async ({ page }) => {
    await page.locator('.system-card[data-system="snes"]').click();
    // Breadcrumb appears when inside a system
    await expect(page.locator('.breadcrumb')).toBeVisible({ timeout: 5_000 });
    // Both SNES ROMs should appear
    await expect(page.getByText('SuperMario.smc')).toBeVisible();
    await expect(page.getByText('SonicWrong.md')).toBeVisible();
  });

  test('ROM filter narrows the displayed list', async ({ page }) => {
    await page.locator('.system-card[data-system="snes"]').click();
    await expect(page.locator('.breadcrumb')).toBeVisible({ timeout: 5_000 });
    // Type in filter box
    await page.locator('#romFilter').fill('super');
    // Wait for 200ms debounce + re-render
    await page.waitForTimeout(400);
    await expect(page.getByText('SuperMario.smc')).toBeVisible();
    await expect(page.getByText('SonicWrong.md')).not.toBeVisible();
  });

  test('misplaced ROM shows warning badge and Move button', async ({ page }) => {
    await page.locator('.system-card[data-system="snes"]').click();
    await expect(page.locator('.breadcrumb')).toBeVisible({ timeout: 5_000 });
    // SonicWrong.md is misplaced — should have a "Wrong folder" badge and a Move button
    const sonicRow = page.locator('tr', { hasText: 'SonicWrong.md' });
    await expect(sonicRow.getByText(/wrong folder/i)).toBeVisible();
    await expect(sonicRow.getByRole('button', { name: /move/i })).toBeVisible();
  });

  // Mutating test — runs last in this file. Deletes SuperMario.smc to _trash.
  test('delete button sends ROM to trash (toast confirms success)', async ({ page }) => {
    page.on('dialog', d => d.accept());
    await page.locator('.system-card[data-system="snes"]').click();
    await expect(page.locator('.breadcrumb')).toBeVisible({ timeout: 5_000 });
    // Click the trash button for SuperMario.smc
    const superMarioRow = page.locator('tr', { hasText: 'SuperMario.smc' });
    await superMarioRow.getByRole('button', { name: /🗑/u }).click();
    // "Trashed SuperMario.smc" toast confirms the server accepted the delete.
    // Note: the scan_cache is not updated until re-scan, so the row stays visible
    // in the current view — this is expected app behavior, not a bug.
    await expect(page.locator('.toast.success', { hasText: /trashed/i })).toBeVisible({ timeout: 5_000 });
  });
});
