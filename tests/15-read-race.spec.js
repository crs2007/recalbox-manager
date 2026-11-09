const { test, expect } = require('./fixtures');

// Hammer the read endpoints while a scan is running; none may 500 or return broken JSON.
test('read endpoints stay consistent while a scan is running', async ({ request }) => {
  await request.post('/api/scan');
  const paths = ['/api/systems', '/api/systems/snes', '/api/issues', '/api/duplicates',
    '/api/search?q=so', '/api/diagnostics', '/api/status', '/api/scan/progress',
    '/api/diagnostics/snapshot'];
  let bad = [];
  for (let round = 0; round < 15; round++) {
    const res = await Promise.all(paths.map(p => request.get(p)));
    res.forEach((r, i) => {
      // /api/systems/snes may legitimately 404 before the inventory reaches it
      if (r.status() >= 500 || (r.status() >= 400 && !(i === 1 && r.status() === 404))) bad.push(`${paths[i]} -> ${r.status()}`);
    });
  }
  expect(bad).toEqual([]);
  // let the scan finish so later tests start from a quiet server
  for (let i = 0; i < 100; i++) {
    const p = await (await request.get('/api/scan/progress')).json();
    if (!p.progress.running && ['done', 'error'].includes(p.progress.phase)) break;
    await new Promise(r => setTimeout(r, 300));
  }
});
