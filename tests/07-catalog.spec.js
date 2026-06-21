const { test, expect } = require('./fixtures');

// The download endpoint streams from archive.org, so the UI-flow test intercepts the
// browser's POST with page.route (the server is never asked to fetch). The read endpoints
// hit the real server + the committed catalog/*.json, so they need no network.

test.describe('Download ROMs catalog — API', () => {
  test('GET /api/catalog/systems lists the shipped systems', async ({ request }) => {
    const res = await request.get('/api/catalog/systems');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.systems)).toBeTruthy();
    const keys = body.systems.map(s => s.system);
    // The five committed catalogs.
    for (const k of ['mame', 'nes', 'snes', 'megadrive', 'gba']) {
      expect(keys).toContain(k);
    }
    const nes = body.systems.find(s => s.system === 'nes');
    expect(nes.count).toBeGreaterThan(0);
  });

  test('GET /api/catalog/<system> paginates and filters', async ({ request }) => {
    const res = await request.get('/api/catalog/nes?page=0');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.total).toBeGreaterThan(100);
    expect(body.games.length).toBe(100); // page size
    expect(body.games[0]).toHaveProperty('filename');
    expect(body.games[0]).toHaveProperty('url');
    expect(body.games[0]).toHaveProperty('owned');

    const filtered = await request.get('/api/catalog/nes?q=mario');
    const fb = await filtered.json();
    expect(fb.total).toBeGreaterThan(0);
    expect(fb.total).toBeLessThan(body.total);
    expect(fb.games.every(g => /mario/i.test(g.name) || /mario/i.test(g.filename))).toBeTruthy();
  });

  test('catalog rejects unknown system', async ({ request }) => {
    const res = await request.get('/api/catalog/not-a-system');
    expect(res.status()).toBe(400);
  });

  test('download validates input without touching the network', async ({ request }) => {
    // invalid filename (path traversal)
    const bad = await request.post('/api/catalog/download', {
      data: { system: 'nes', filename: '../evil.zip' },
    });
    expect(bad.status()).toBe(400);

    // file not present in the catalog
    const missing = await request.post('/api/catalog/download', {
      data: { system: 'nes', filename: 'definitely-not-in-catalog-xyz.zip' },
    });
    expect(missing.status()).toBe(404);
  });
});

test.describe('Download ROMs catalog — UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Scan ROMs/i }).click();
    await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
    await page.locator('button[data-tab="catalog"]').click();
  });

  test('tab renders a system bar and a grid of game cards', async ({ page }) => {
    await page.waitForResponse(resp => resp.url().includes('/api/catalog/'), { timeout: 10_000 });
    await expect(page.locator('.catalog-systembar')).toBeVisible();
    await expect(page.locator('.catalog-card').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('#catalogSearch')).toBeVisible();
  });

  test('searching filters the grid', async ({ page }) => {
    await expect(page.locator('.catalog-card').first()).toBeVisible({ timeout: 10_000 });
    await page.locator('#catalogSearch').fill('mario');
    await page.waitForResponse(resp => resp.url().includes('/api/catalog/') && resp.url().includes('q=mario'), { timeout: 5_000 });
    await expect(
      page.locator('.catalog-card .browse-card-name').filter({ hasText: /mario/i }).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test('downloading a game flips the card to Owned (download mocked)', async ({ page }) => {
    // Intercept the browser's download call so no real archive.org fetch happens.
    await page.route('**/api/catalog/download', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, filename: 'x', cover: true, cover_source: 'libretro', description: false }),
      })
    );
    await expect(page.locator('.catalog-card').first()).toBeVisible({ timeout: 10_000 });
    const firstCard = page.locator('.catalog-card').first();
    await firstCard.getByRole('button', { name: /Download/i }).click();
    await expect(firstCard.getByText('✓ Owned')).toBeVisible({ timeout: 5_000 });
  });
});
