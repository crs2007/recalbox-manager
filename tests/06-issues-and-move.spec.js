const { test, expect } = require('./fixtures');

test.describe('Issues tab — misplaced ROM detection and move', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    await page.locator('button[data-tab="issues"]').click();
  });

  test('Issues tab shows SonicWrong.md as misplaced in snes', async ({ page }) => {
    await expect(page.getByText('SonicWrong.md')).toBeVisible({ timeout: 5_000 });
    const issueRow = page.locator('.issue-row', { hasText: 'SonicWrong.md' });
    await expect(issueRow).toBeVisible();
    await expect(issueRow.getByText('snes')).toBeVisible();
  });

  test('misplaced ROM shows a move option (Choose... button — 2 suggested systems)', async ({ page }) => {
    const issueRow = page.locator('.issue-row', { hasText: 'SonicWrong.md' });
    await expect(issueRow).toBeVisible({ timeout: 5_000 });
    // .md maps to megadrive AND genesis (2 systems), so button is "Choose..." not a direct move
    await expect(issueRow.getByRole('button', { name: 'Choose...' })).toBeVisible();
  });

  // Mutating test — runs last in this file. Opens modal and moves SonicWrong.md to megadrive.
  test('modal move: select megadrive and confirm — file no longer misplaced', async ({ page }) => {
    const issueRow = page.locator('.issue-row', { hasText: 'SonicWrong.md' });
    await expect(issueRow).toBeVisible({ timeout: 5_000 });

    // Open move modal
    await issueRow.getByRole('button', { name: 'Choose...' }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 5_000 });

    // Select megadrive (first suggested option in the dropdown)
    await page.locator('#moveTarget').selectOption('megadrive');

    // Click the Move button inside the modal
    await page.locator('.modal-actions').getByRole('button', { name: 'Move' }).click();

    // Modal should close after move
    await expect(page.locator('.modal')).not.toBeAttached({ timeout: 8_000 });

    // Re-scan to verify the file is no longer misplaced in snes
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    await page.locator('button[data-tab="issues"]').click();

    // SonicWrong.md should no longer appear as a misplaced issue
    await expect(page.getByText('SonicWrong.md')).not.toBeVisible({ timeout: 5_000 });
  });
});
