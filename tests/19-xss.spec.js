const { test, expect } = require('./fixtures');
const fs = require('fs');
const path = require('path');

const SNES = path.resolve(__dirname, '..', 'test-data', 'mock-recalbox', 'roms', 'snes');
const GL = path.join(SNES, 'gamelist.xml');

// A game name that would break out of an HTML attribute / inject an element if not escaped.
const EVIL = `x" onmouseover="window.__xss=1" x="<img src=x onerror="window.__xss=2">&quot; onfocus=&quot;window.__xss=3`;

test.afterAll(() => { fs.rmSync(GL, { force: true }); fs.rmSync(path.join(SNES, 'Evil.sfc'), { force: true }); });

test('hostile game names render inertly', async ({ page }) => {
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  fs.writeFileSync(path.join(SNES, 'Evil.sfc'), 'EVIL');
  fs.writeFileSync(GL, `<?xml version="1.0"?><gameList><game><path>./Evil.sfc</path><name>${esc(EVIL)}</name></game></gameList>`);

  const dialogs = [];
  page.on('dialog', d => { dialogs.push(d.message()); d.dismiss(); });

  const pageErrors = []; page.on('pageerror', e => pageErrors.push(e.message));
  await page.goto('/');
  await page.getByRole('button', { name: /Scan ROMs/i }).click();
  await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });

  await page.locator('.system-card[data-system="snes"]').click();
  await expect(page.locator('.breadcrumb')).toBeVisible({ timeout: 5_000 });
  const row = page.locator('tr', { hasText: 'Evil.sfc' });
  await row.hover();
  await row.getByTitle('Edit metadata').click();
  await page.waitForTimeout(300);

  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
  expect(await page.locator('img[src="x"]').count()).toBe(0);
  expect(dialogs).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test('responses carry a CSP and nosniff', async ({ request }) => {
  const res = await request.get('/api/status');
  expect(res.headers()['content-security-policy']).toContain("frame-ancestors 'none'");
  expect(res.headers()['x-content-type-options']).toBe('nosniff');
});
