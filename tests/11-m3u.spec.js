const { test, expect } = require('./fixtures');
const fs = require('fs');
const path = require('path');

const PSX = path.resolve(__dirname, '..', 'test-data', 'mock-recalbox', 'roms', 'psx');

test('M3U Auto-Fix button creates a playlist with one entry per disc (no .bin)', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Scan ROMs/i }).click();
  await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
  await page.locator('button[data-tab="diagnostics"]').click();

  const card = page.locator('.issue-row, .diag-card, [class*=diag]').filter({ hasText: 'TwoDisc' }).first();
  await expect(card).toBeVisible({ timeout: 5_000 });
  await card.getByRole('button', { name: /Auto-Fix/ }).click();

  const m3u = path.join(PSX, 'TwoDisc.m3u');
  await expect.poll(() => fs.existsSync(m3u), { timeout: 5_000 }).toBeTruthy();
  expect(fs.readFileSync(m3u, 'utf8').trim().split('\n')).toEqual(['TwoDisc (Disc 1).cue', 'TwoDisc (Disc 2).cue']);
});
