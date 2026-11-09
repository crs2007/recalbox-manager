const { test, expect } = require('./fixtures');
const fs = require('fs');
const path = require('path');

const PSX = path.resolve(__dirname, '..', 'test-data', 'mock-recalbox', 'roms', 'psx');
const SYNC = Buffer.from([0x00, ...Array(10).fill(0xff), 0x00]);

async function scanAndWait(request) {
  await request.post('/api/scan');
  for (let i = 0; i < 100; i++) {
    const p = await (await request.get('/api/scan/progress')).json();
    if (!p.progress.running && ['done', 'error'].includes(p.progress.phase)) break;
    await new Promise(r => setTimeout(r, 300));
  }
}

test.describe('CUE detection and generation', () => {
  test('multi-track set with a valid cue is not flagged; the true orphan still is', async ({ request }) => {
    await scanAndWait(request);
    const diags = await (await request.get('/api/diagnostics')).json();
    const list = Array.isArray(diags) ? diags : diags.diagnostics;
    const missing = list.filter(d => d.key === 'missing_cue').map(d => d.file);
    expect(missing).toContain('OrphanBin.bin');
    expect(missing.filter(f => f.startsWith('MultiTrack'))).toEqual([]);
  });

  test('generate-cue uses MODE1 for a MODE1 bin and refuses headerless / multi-track files', async ({ request }) => {
    fs.writeFileSync(path.join(PSX, 'Mode1.bin'), Buffer.concat([SYNC, Buffer.from([0x00, 0x00, 0x00, 0x01]), Buffer.alloc(64)]));
    let res = await request.post('/api/fix/generate-cue', { data: { system: 'psx', filename: 'Mode1.bin' } });
    expect(res.ok()).toBeTruthy();
    expect(fs.readFileSync(path.join(PSX, 'Mode1.cue'), 'utf8')).toContain('MODE1/2352');

    res = await request.post('/api/fix/generate-cue', { data: { system: 'psx', filename: 'OrphanBin.bin' } });
    expect(res.status()).toBe(422);
    res = await request.post('/api/fix/generate-cue', { data: { system: 'psx', filename: 'MultiTrack (Track 2).bin' } });
    expect([409, 422]).toContain(res.status());
    fs.rmSync(path.join(PSX, 'Mode1.bin'), { force: true });
    fs.rmSync(path.join(PSX, 'Mode1.cue'), { force: true });
  });
});
