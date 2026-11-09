const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const os = require('os');
const path = require('path');

const root = path.resolve(__dirname, '..');
const share = path.join(root, 'test-data', 'mock-recalbox');

test('probes run in parallel, are cached by (size, mtime) and persisted across restarts', () => {
  const cacheFile = path.join(os.tmpdir(), `probe-cache-${process.pid}.json`);
  const code = String.raw`
import sys, os, json, time, zipfile
sys.path.insert(0, ${JSON.stringify(root)})
os.environ["RECALBOX_SHARE"] = ${JSON.stringify(share)}
os.environ["RECALBOX_PROBE_CACHE"] = ${JSON.stringify(cacheFile)}
import server as s

d = os.path.join(s._roms_root(), "nes")
os.makedirs(d, exist_ok=True)
paths = {}
bad = os.path.join(d, "BadMagic.nes"); open(bad, "wb").write(b"XXXX" + b"\0" * 100); paths["bad"] = bad
tail = os.path.join(d, "FFTail.nes"); open(tail, "wb").write(b"NES\x1a" + b"\x01" * 70000 + b"\xff" * 600); paths["tail"] = tail
z = os.path.join(d, "Inside.zip")
with zipfile.ZipFile(z, "w") as zf: zf.writestr("game.nes", "x")
paths["zip"] = z
bz = os.path.join(d, "Broken.zip"); open(bz, "wb").write(b"not a zip at all"); paths["broken"] = bz

def mk(p):
    st = os.stat(p)
    return {"name": os.path.basename(p), "ext": os.path.splitext(p)[1].lower(), "size": st.st_size,
            "mtime_ns": st.st_mtime_ns, "path": p, "system": "nes", "diagnostics": []}
roms = [mk(p) for p in paths.values()]

calls = {"n": 0}
real = s._probe_rom
def counting(*a, **k):
    calls["n"] += 1
    return real(*a, **k)
s._probe_rom = counting

p1 = s._probe_roms("nes", roms, need_contents=True)
first_calls = calls["n"]
p2 = s._probe_roms("nes", roms, need_contents=True)           # all cached
second_calls = calls["n"] - first_calls
s._save_probe_cache()

# "restart": fresh in-memory cache, load from disk
s._probe_cache.clear(); s._load_probe_cache()
p3 = s._probe_roms("nes", roms, need_contents=True)
third_calls = calls["n"] - first_calls - second_calls

# a changed file is re-probed
open(bad, "wb").write(b"NES\x1a" + b"\0" * 100)
os.utime(bad, ns=(1, 2))
roms[0] = mk(bad)
p4 = s._probe_roms("nes", roms, need_contents=True)

for p in paths.values(): os.remove(p)
print(json.dumps({
  "first": first_calls, "second": second_calls, "third": third_calls, "fourth": calls["n"] - first_calls - second_calls - third_calls,
  "bad_magic": p1["BadMagic.nes"].get("nes_magic"), "tail": p1["FFTail.nes"].get("tail_uniform"),
  "zip_ok": p1["Inside.zip"].get("zip_valid"), "zip_names": p1["Inside.zip"].get("inner_names"),
  "broken": p1["Broken.zip"].get("zip_valid"), "same": p1 == p2 == p3,
  "changed_magic": p4["BadMagic.nes"].get("nes_magic"),
}))
`;
  const out = JSON.parse(execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop());
  expect(out.first).toBe(4);
  expect(out.second).toBe(0);          // served from memory
  expect(out.third).toBe(0);           // served from the persisted file after a "restart"
  expect(out.fourth).toBe(1);          // only the modified file is re-read
  expect(out.bad_magic).toBe(false);
  expect(out.tail).toBe(true);
  expect(out.zip_ok).toBe(true);
  expect(out.zip_names).toEqual(['game.nes']);
  expect(out.broken).toBe(false);
  expect(out.same).toBe(true);
  expect(out.changed_magic).toBe(true);
});
