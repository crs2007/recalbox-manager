const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const share = path.join(root, 'test-data', 'mock-recalbox');
const NES = path.join(share, 'roms', 'nes');

test.afterAll(() => { for (const f of ['gamelist.xml', 'gamelist.xml.bak', 'gamelist.xml.tmp']) fs.rmSync(path.join(NES, f), { force: true }); });

test('deferred gamelist writes are batched, visible in the cache, and flushed on demand', () => {
  const code = String.raw`
import sys, os, json
sys.path.insert(0, ${JSON.stringify(root)})
os.environ["RECALBOX_SHARE"] = ${JSON.stringify(share)}
import server as s
xml = os.path.join(s._roms_root(), "nes", "gamelist.xml")
saves = {"n": 0}
real = s._save_gamelist_tree
def counting(system, tree):
    saves["n"] += 1
    return real(system, tree)
s._save_gamelist_tree = counting

for i in range(10):
    r = s.write_gamelist_entry("nes", "Game%d.nes" % i, {"name": "Game %d" % i, "desc": "d%d" % i}, defer=True)
    assert r["ok"] and r.get("deferred"), r
in_cache = s.scan_cache["gamelists"]["nes"]["game3"]["name"]
on_disk_before = os.path.exists(xml)
saves_before = saves["n"]
flush = s.flush_gamelists()
saves_after_flush = saves["n"]
on_disk_after = open(xml, encoding="utf-8").read()
# an immediate (non-deferred) write goes straight to disk
s.write_gamelist_entry("nes", "Now.nes", {"name": "Immediate"})
print(json.dumps({"in_cache": in_cache, "on_disk_before": on_disk_before, "saves_before": saves_before,
  "flushed": flush["flushed"], "saves_after_flush": saves_after_flush, "games_on_disk": on_disk_after.count("<game>"),
  "immediate_on_disk": "Immediate" in open(xml, encoding="utf-8").read(), "total_saves": saves["n"]}))
`;
  const out = JSON.parse(execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop());
  expect(out.in_cache).toBe('Game 3');          // visible immediately
  expect(out.on_disk_before).toBe(false);       // nothing written yet
  expect(out.saves_before).toBe(0);
  expect(out.flushed).toEqual(['nes']);
  expect(out.saves_after_flush).toBe(1);        // 10 updates -> 1 write
  expect(out.games_on_disk).toBe(10);
  expect(out.immediate_on_disk).toBe(true);
  expect(out.total_saves).toBe(2);
});
