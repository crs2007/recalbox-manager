const { test, expect } = require('./fixtures');

test.describe('Frontend does less work', () => {
  test('toasts are painted without re-rendering #app', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#app *');
    // Mark the #app subtree; a full render() would replace every child and lose the mark.
    await page.evaluate(() => { document.getElementById('app').firstElementChild.dataset.mark = 'kept'; });
    await page.evaluate(() => toast('hello toast', 'info'));
    await expect(page.locator('#toasts .toast')).toHaveText('hello toast');
    expect(await page.evaluate(() => document.getElementById('app').firstElementChild.dataset.mark)).toBe('kept');
    await expect(page.locator('#toasts .toast')).toHaveCount(0, { timeout: 6000 });
  });

  test('a successful scrape patches the open system instead of refetching it', async ({ page }) => {
    let systemFetches = 0;
    await page.route('**/api/systems/snes', route => { systemFetches += 1; route.continue(); });
    await page.route('**/api/covers/scrape', route => route.fulfill({
      json: { ok: true, source: 'test', cover_url: '/api/covers/image/snes/x.png', gamelist_updated: true, stats: { total_files: 1 } },
    }));
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    const card = page.locator('.system-card').first();
    await card.click();
    await expect(page.locator('.breadcrumb')).toBeVisible({ timeout: 5_000 });
    const before = systemFetches;
    const folder = await page.evaluate(() => state.selectedSystem.folder);
    const romName = await page.evaluate(() => state.selectedSystem.roms[0].name);
    await page.evaluate(([n, f]) => scrapeCover(n, f, ''), [romName, folder]);
    expect(systemFetches).toBe(before);   // no GET /api/systems/<name> after the scrape
    expect(await page.evaluate(([n]) => state.selectedSystem.roms.find(r => r.name === n).has_cover, [romName])).toBe(true);
  });

  test('system payload no longer ships absolute ROM paths', async ({ request }) => {
    const sys = await (await request.get('/api/systems')).json();
    const name = Object.keys(sys).find(k => sys[k].total_roms > 0);
    const detail = await (await request.get('/api/systems/' + name)).json();
    expect(detail.roms.length).toBeGreaterThan(0);
    expect(detail.roms.every(r => !('path' in r))).toBe(true);
  });

  test('browse cards open the edit modal via delegated index (no inline JSON)', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    await page.locator('button[data-tab="browse"]').click();
    const card = page.locator('.browse-card').first();
    await expect(card).toBeVisible({ timeout: 10_000 });
    expect(await card.getAttribute('onclick')).toMatch(/^showEditFromBrowse\('/);
    await card.click();
    await expect(page.locator('.modal, .modal-overlay, [class*=modal]').first()).toBeVisible({ timeout: 5_000 });
  });
});
