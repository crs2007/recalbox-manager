const { test, expect } = require('./fixtures');
const fs = require('fs');
const path = require('path');

const ROMS = path.resolve(__dirname, '..', 'test-data', 'mock-recalbox', 'roms');

async function scanAndWait(request) {
  await request.post('/api/scan');
  for (let i = 0; i < 100; i++) {
    const p = await (await request.get('/api/scan/progress')).json();
    if (!p.progress.running && ['done', 'error'].includes(p.progress.phase)) break;
    await new Promise(r => setTimeout(r, 300));
  }
}

test.describe('Duplicate detection is content-verified', () => {
  const head = Buffer.alloc(65536, 0x41);
  const a = path.join(ROMS, 'snes', 'HackA.sfc');
  const b = path.join(ROMS, 'snes', 'HackB.sfc');
  const c = path.join(ROMS, 'megadrive', 'HackC.bin');
  const d = path.join(ROMS, 'megadrive', 'HackD.bin');

  test.afterAll(() => { for (const f of [a, b, c, d]) fs.rmSync(f, { force: true }); });

  test('same 64KB prefix but different tails are not duplicates; trash refuses them', async ({ request }) => {
    fs.writeFileSync(a, Buffer.concat([head, Buffer.from('AAAA')]));
    fs.writeFileSync(b, Buffer.concat([head, Buffer.from('BBBB')]));
    fs.writeFileSync(c, Buffer.concat([head, Buffer.from('CCCCCCCC')]));
    fs.writeFileSync(d, Buffer.concat([head, Buffer.from('DDDDDDDD')]));
    await scanAndWait(request);

    const dups = await (await request.get('/api/duplicates')).json();
    const names = dups.flatMap(g => g.copies.map(x => x.file));
    for (const n of ['HackA.sfc', 'HackB.sfc', 'HackC.bin', 'HackD.bin']) expect(names).not.toContain(n);
    // The genuine byte-identical pair from the mock data is still reported.
    expect(names).toContain('DupGame.zip');

    const res = await request.post('/api/duplicates/trash', {
      data: { keep: { system: 'snes', file: 'HackA.sfc' }, trash: { system: 'snes', file: 'HackB.sfc' } },
    });
    expect(res.status()).toBe(409);
    expect(fs.existsSync(b)).toBeTruthy();
  });

  test('trash endpoint accepts a genuinely identical pair', async ({ request }) => {
    const res = await request.post('/api/duplicates/trash', {
      data: { keep: { system: 'megadrive', file: 'Sonic.md' }, trash: { system: 'neogeo', file: 'DupGame.zip' } },
    });
    expect(res.ok()).toBeTruthy();
    expect(fs.existsSync((await res.json()).trash_path)).toBeTruthy();
    expect(fs.existsSync(path.join(ROMS, 'neogeo', 'DupGame.zip'))).toBeFalsy();
  });
});
