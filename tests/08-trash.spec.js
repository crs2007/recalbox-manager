const { test, expect } = require('./fixtures');
const fs = require('fs');
const path = require('path');

const ROMS = path.resolve(__dirname, '..', 'test-data', 'mock-recalbox', 'roms');

test.describe('Safe delete never overwrites an earlier trashed file', () => {
  test('two files with the same name are both kept byte for byte', async ({ request }) => {
    const dir = path.join(ROMS, 'snes');
    const src = path.join(dir, 'Collide.sfc');

    fs.writeFileSync(src, 'FIRST TRASHED COPY');
    let res = await request.post('/api/delete', { data: { system: 'snes', filename: 'Collide.sfc' } });
    expect(res.ok()).toBeTruthy();
    const first = (await res.json()).trash_path;

    fs.writeFileSync(src, 'SECOND FILE');
    res = await request.post('/api/delete', { data: { system: 'snes', filename: 'Collide.sfc' } });
    expect(res.ok()).toBeTruthy();
    const second = (await res.json()).trash_path;

    expect(second).not.toBe(first);
    expect(fs.readFileSync(first, 'utf8')).toBe('FIRST TRASHED COPY');
    expect(fs.readFileSync(second, 'utf8')).toBe('SECOND FILE');
    expect(fs.existsSync(src)).toBeFalsy();
  });
});
