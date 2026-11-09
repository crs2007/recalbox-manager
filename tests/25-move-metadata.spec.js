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

test.afterAll(() => {
  for (const sys of ['snes', 'megadrive']) {
    for (const f of ['gamelist.xml', 'gamelist.xml.bak']) fs.rmSync(path.join(ROMS, sys, f), { force: true });
    fs.rmSync(path.join(ROMS, sys, 'media'), { recursive: true, force: true });
  }
  fs.rmSync(path.join(ROMS, 'megadrive', 'Meta.md'), { force: true });
  fs.rmSync(path.join(ROMS, 'snes', 'Meta.md'), { force: true });
});

test('moving a ROM carries its gamelist entry and cover to the destination', async ({ request }) => {
  const snes = path.join(ROMS, 'snes');
  fs.mkdirSync(path.join(snes, 'media', 'images'), { recursive: true });
  fs.writeFileSync(path.join(snes, 'Meta.md'), 'META');
  fs.writeFileSync(path.join(snes, 'media', 'images', 'Meta.png'), Buffer.from('\x89PNG-fake'));
  fs.writeFileSync(path.join(snes, 'gamelist.xml'),
    '<?xml version="1.0"?><gameList>' +
    '<game><path>./Meta.md</path><name>Meta Game</name><desc>Nice game</desc><image>./media/images/Meta.png</image></game>' +
    '<game><path>./Other.sfc</path><name>Other</name></game></gameList>');
  await scanAndWait(request);

  const res = await request.post('/api/move', { data: { from_system: 'snes', to_system: 'megadrive', filename: 'Meta.md' } });
  expect(res.ok()).toBeTruthy();
  expect((await res.json()).metadata.moved_entry).toBe(true);

  // source: entry gone, other entries untouched, cover moved away
  const srcXml = fs.readFileSync(path.join(snes, 'gamelist.xml'), 'utf8');
  expect(srcXml).not.toContain('Meta Game');
  expect(srcXml).toContain('Other');
  expect(fs.existsSync(path.join(snes, 'media', 'images', 'Meta.png'))).toBeFalsy();

  // destination: entry + cover present, image path still valid
  const dst = path.join(ROMS, 'megadrive');
  const dstXml = fs.readFileSync(path.join(dst, 'gamelist.xml'), 'utf8');
  expect(dstXml).toContain('Meta Game');
  expect(dstXml).toContain('Nice game');
  expect(dstXml).toContain('./media/images/Meta.png');
  expect(fs.existsSync(path.join(dst, 'media', 'images', 'Meta.png'))).toBeTruthy();

  // cache: the moved ROM is in the new system with its metadata, not "missing cover"
  const sys = await (await request.get('/api/systems/megadrive')).json();
  const rom = sys.roms.find(r => r.name === 'Meta.md');
  expect(rom.game_name).toBe('Meta Game');
  expect(rom.has_cover).toBe(true);
  expect(rom.has_description).toBe(true);
  const missing = await (await request.get('/api/covers/missing')).json();
  expect(missing.some(m => m.name === 'Meta.md')).toBe(false);
});
