const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const share = path.join(root, 'test-data', 'mock-recalbox');
const NES = path.join(share, 'roms', 'nes');

function runPy(body) {
  const code = String.raw`
import sys, os, json
sys.path.insert(0, ${JSON.stringify(root)})
os.environ["RECALBOX_SHARE"] = ${JSON.stringify(share)}
os.environ["RECALBOX_PROBE_CACHE"] = "off"
import server as s
${body}
`;
  return JSON.parse(execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop());
}

test.afterAll(() => { for (const f of fs.readdirSync(NES)) if (/^(Partial|Keys)/.test(f) || f === 'gamelist.xml') fs.rmSync(path.join(NES, f), { force: true }); });

test.describe('Audit leftovers (#23)', () => {
  test('.part files are not reported as misplaced ROMs, and stale ones are cleaned up', async ({ request }) => {
    fs.writeFileSync(path.join(NES, 'Partial.nes.part'), 'half a download');
    await request.post('/api/scan');
    for (let i = 0; i < 100; i++) {
      const p = await (await request.get('/api/scan/progress')).json();
      if (!p.progress.running && ['done', 'error'].includes(p.progress.phase)) break;
      await new Promise(r => setTimeout(r, 300));
    }
    const nes = await (await request.get('/api/systems/nes')).json();
    expect((nes.roms || []).some(r => r.name.endsWith('.part'))).toBe(false);
    const out = runPy(`
s._cleanup_stale_parts()
print(json.dumps({"gone": not os.path.exists(os.path.join(s._roms_root(), "nes", "Partial.nes.part"))}))
`);
    expect(out.gone).toBe(true);
  });

  test('gamelist entries are keyed by basename, so Game.cue and Game.m3u do not collide', () => {
    fs.writeFileSync(path.join(NES, 'gamelist.xml'),
      '<?xml version="1.0"?><gameList>' +
      '<game><path>./Keys.cue</path><name>CUE entry</name></game>' +
      '<game><path>./Keys.m3u</path><name>M3U entry</name></game></gameList>');
    const out = runPy(`
gl = s.parse_gamelist("nes")
print(json.dumps({"cue": s._gl_lookup(gl, "Keys.cue")["name"], "m3u": s._gl_lookup(gl, "Keys.m3u")["name"],
                  "stem_fallback": s._gl_lookup(gl, "Keys.zip")["name"]}))
`);
    expect(out.cue).toBe('CUE entry');
    expect(out.m3u).toBe('M3U entry');
    expect(out.stem_fallback).toBeTruthy();       // unknown extension still falls back to the stem
  });

  test('catalog cache reloads when the file changes; covers revalidate; ss_configured needs all 4 creds', async ({ request }) => {
    const out = runPy(`
import time
s.CATALOG_DIR = os.path.join(os.environ.get("TMPDIR", os.path.expanduser("~")), "cat-test-%d" % os.getpid())
os.makedirs(s.CATALOG_DIR, exist_ok=True)
p = os.path.join(s.CATALOG_DIR, "nes.json")
json.dump({"games": [{"filename": "a.nes"}]}, open(p, "w"))
first = len(s._load_catalog("nes")["games"])
json.dump({"games": [{"filename": "a.nes"}, {"filename": "b.nes"}]}, open(p, "w"))
os.utime(p, ns=(1, 5_000_000_000))
second = len(s._load_catalog("nes")["games"])
os.remove(p); os.rmdir(s.CATALOG_DIR)
s.ss_config.update({"screenscraper_user": "u", "screenscraper_pass": "p", "screenscraper_devid": "", "screenscraper_devpass": ""})
two = s._ss_configured()
s.ss_config.update({"screenscraper_devid": "d", "screenscraper_devpass": "dp"})
print(json.dumps({"first": first, "second": second, "two": two, "four": s._ss_configured()}))
`);
    expect(out).toEqual({ first: 1, second: 2, two: false, four: true });

    fs.mkdirSync(path.join(share, 'roms', 'snes', 'media', 'images'), { recursive: true });
    fs.writeFileSync(path.join(share, 'roms', 'snes', 'media', 'images', 'c.png'), Buffer.from('\x89PNG'));
    const res = await request.get('/api/covers/image/snes/c.png');
    expect(res.headers()['cache-control']).toBe('no-cache');
    fs.rmSync(path.join(share, 'roms', 'snes', 'media'), { recursive: true, force: true });
  });
});
