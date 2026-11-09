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
const stats = async request => (await (await request.get('/api/status')).json()).stats;
const roms = async (request, sys) => (await (await request.get(`/api/systems/${sys}`)).json()).roms.map(r => r.name);

test.describe('scan_cache stays in sync after mutations', () => {
  test('delete removes the ROM from the cache and drops total_files by 1', async ({ request }) => {
    fs.writeFileSync(path.join(ROMS, 'snes', 'Gone.sfc'), 'GONE');
    await scanAndWait(request);
    const before = await stats(request);
    expect(await roms(request, 'snes')).toContain('Gone.sfc');

    const res = await request.post('/api/delete', { data: { system: 'snes', filename: 'Gone.sfc' } });
    expect(res.ok()).toBeTruthy();

    expect(await roms(request, 'snes')).not.toContain('Gone.sfc');
    const after = await stats(request);
    expect(after.total_files).toBe(before.total_files - 1);
    const sys = await (await request.get('/api/systems/snes')).json();
    expect(sys.total_roms).toBe(sys.roms.length);
  });

  test('move shows the ROM in the destination system and updates counters', async ({ request }) => {
    fs.writeFileSync(path.join(ROMS, 'snes', 'Mover.md'), 'MOVER');
    await scanAndWait(request);
    const before = await stats(request);
    const snesBefore = await (await request.get('/api/systems/snes')).json();
    expect(snesBefore.misplaced_count).toBeGreaterThan(0);

    const res = await request.post('/api/move', { data: { from_system: 'snes', to_system: 'megadrive', filename: 'Mover.md' } });
    expect(res.ok()).toBeTruthy();

    expect(await roms(request, 'snes')).not.toContain('Mover.md');
    expect(await roms(request, 'megadrive')).toContain('Mover.md');
    const snesAfter = await (await request.get('/api/systems/snes')).json();
    expect(snesAfter.misplaced_count).toBe(snesBefore.misplaced_count - 1);
    const after = await stats(request);
    expect(after.total_files).toBe(before.total_files);
    expect(after.total_misplaced).toBe(before.total_misplaced - 1);
    expect(after.total_issues).toBe(before.total_issues - 1);
  });
});
