const { test, expect } = require('./fixtures');
const fs = require('fs');
const path = require('path');

const NES = path.resolve(__dirname, '..', 'test-data', 'mock-recalbox', 'roms', 'nes');
const GL = path.join(NES, 'gamelist.xml');
const BAK = GL + '.bak';

test.afterAll(() => { for (const f of [GL, BAK, GL + '.tmp']) fs.rmSync(f, { force: true }); });

const update = (request, filename, name) =>
  request.post('/api/gamelist/update', { data: { system: 'nes', filename, name } });

test.describe('gamelist.xml writer', () => {
  test('repairs trailing junk on the fly, keeps one session .bak, matches dotted names by prefix', async ({ request }) => {
    const original = '<?xml version="1.0"?>\n<gameList>\n<game><path>./.hackGU.nes</path><name>Old</name></game>\n</gameList>\nGARBAGE-AFTER-END';
    fs.writeFileSync(GL, original);

    // 1) a corrupted-but-recoverable file no longer blocks writes
    let res = await update(request, '.hackGU.nes', 'First');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.created).toBe(false);          // matched the existing "./.hackGU.nes" entry
    let xml = fs.readFileSync(GL, 'utf8');
    expect(xml).not.toContain('GARBAGE');
    expect(xml.match(/<game>/g).length).toBe(1);
    expect(xml).toContain('<name>First</name>');

    // 2) .bak is the pre-session original ...
    expect(fs.readFileSync(BAK, 'utf8')).toBe(original);

    // 3) ... and later writes don't overwrite it with "one write ago"
    res = await update(request, '.hackGU.nes', 'Second');
    expect((await res.json()).ok).toBe(true);
    expect(fs.readFileSync(BAK, 'utf8')).toBe(original);
    expect(fs.readFileSync(GL, 'utf8')).toContain('<name>Second</name>');
  });
});
