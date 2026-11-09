const { test, expect } = require('./fixtures');

const BAD_SYSTEMS = ['..\\..', 'C:\\Windows', '../x', '/etc', 'snes/../..', 'nosuchsystem'];

const endpoints = [
  ['/api/gamelist/update', s => ({ system: s, filename: 'a.sfc', name: 'x' })],
  ['/api/gamelist/repair', s => ({ system: s })],
  ['/api/covers/scrape', s => ({ system: s, filename: 'a.sfc' })],
  ['/api/descriptions/scrape', s => ({ system: s, filename: 'a.sfc' })],
  ['/api/covers/download-url', s => ({ system: s, filename: 'a.sfc', image_url: 'https://example.com/a.png' })],
];

test.describe('Client-supplied paths are validated', () => {
  for (const [url, body] of endpoints) {
    test(`${url} rejects traversal / unknown systems`, async ({ request }) => {
      for (const sys of BAD_SYSTEMS) {
        const res = await request.post(url, { data: body(sys) });
        expect(res.status(), `${url} system=${sys}`).toBe(400);
      }
    });
  }

  test('filenames with separators or drive letters are rejected', async ({ request }) => {
    for (const fn of ['..\\evil.sfc', 'C:\\evil.sfc', '../evil.sfc', 'a/b.sfc']) {
      const res = await request.post('/api/gamelist/update', { data: { system: 'snes', filename: fn, name: 'x' } });
      expect(res.status(), fn).toBe(400);
    }
  });

  test('generate-m3u rejects path-like game_name and non-basename files', async ({ request }) => {
    let res = await request.post('/api/fix/generate-m3u', {
      data: { system: 'psx', files: ['TwoDisc (Disc 1).cue'], game_name: '..\\..\\..\\evil' },
    });
    expect(res.status()).toBe(400);
    res = await request.post('/api/fix/generate-m3u', {
      data: { system: 'psx', files: ['..\\secret.cue'], game_name: 'ok' },
    });
    expect(res.status()).toBe(400);
  });

  test('config rejects non-string credentials', async ({ request }) => {
    const res = await request.post('/api/config', { data: { screenscraper_user: { a: 1 } } });
    expect(res.status()).toBe(400);
  });
});
