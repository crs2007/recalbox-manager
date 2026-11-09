const { test, expect } = require('./fixtures');
const fs = require('fs');
const path = require('path');

const SNES = path.resolve(__dirname, '..', 'test-data', 'mock-recalbox', 'roms', 'snes');

test.afterAll(() => {
  for (const f of fs.readdirSync(SNES)) if (f.startsWith('Headered')) fs.rmSync(path.join(SNES, f), { force: true });
});

test('strip-smc-header is atomic, never reuses a stale .bak, and keeps the filename', async ({ request }) => {
  const rom = path.join(SNES, 'Headered.smc');
  const body = Buffer.alloc(1024, 7);
  fs.writeFileSync(rom, Buffer.concat([Buffer.alloc(512, 0), body]));
  fs.writeFileSync(rom + '.bak', 'STALE BACKUP FROM A DIFFERENT FILE');

  const res = await request.post('/api/fix/strip-smc-header', { data: { system: 'snes', filename: 'Headered.smc' } });
  expect(res.ok()).toBeTruthy();
  const out = await res.json();

  expect(fs.readFileSync(rom)).toEqual(body);                          // header gone, same filename
  expect(fs.existsSync(rom + '.tmp')).toBeFalsy();
  expect(fs.readFileSync(rom + '.bak', 'utf8')).toBe('STALE BACKUP FROM A DIFFERENT FILE');  // untouched
  expect(out.backup).not.toBe('Headered.smc.bak');                     // a fresh timestamped backup
  const fresh = fs.readFileSync(path.join(SNES, out.backup));
  expect(fresh.length).toBe(1536);                                     // the original, with header
});
