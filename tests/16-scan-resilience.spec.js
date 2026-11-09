const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const path = require('path');

const root = path.resolve(__dirname, '..');
const share = path.join(root, 'test-data', 'mock-recalbox');

function runPy(body) {
  const code = String.raw`
import sys, json, os
sys.path.insert(0, ${JSON.stringify(root)})
os.environ["RECALBOX_SHARE"] = ${JSON.stringify(share)}
import server as s
${body}
`;
  return JSON.parse(execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop());
}

test.describe('Scan resilience', () => {
  test('an OSError in one folder becomes a scan_error issue and the scan continues', () => {
    const out = runPy(`
real = os.scandir
def flaky(p):
    if os.path.basename(str(p)) == "snes":
        raise OSError(64, "The specified network name is no longer available")
    return real(p)
os.scandir = flaky
res = s._scan_inventory()
print(json.dumps({"ok": res.get("ok"), "systems": sorted(s.scan_cache["systems"]),
                  "types": [i["type"] for i in s.scan_cache["issues"]]}))
`);
    expect(out.ok).toBe(true);
    expect(out.types).toContain('scan_error');
    expect(out.systems).toContain('megadrive');
    expect(out.systems).not.toContain('snes');
  });

  test('a crash mid-scan keeps the previous good inventory and reports stale', () => {
    const out = runPy(`
s._scan_inventory()                       # a good scan first
before = sorted(s.scan_cache["systems"])
real = s.parse_gamelist
n = {"c": 0}
def boom(*a, **k):
    n["c"] += 1
    if n["c"] == 3:
        raise RuntimeError("SMB dropped")
    return real(*a, **k)
s.parse_gamelist = boom
s._run_scan_bg()
print(json.dumps({"before": before, "after": sorted(s.scan_cache["systems"]),
                  "phase": s.scan_progress["phase"], "stale": s.scan_progress.get("stale")}))
`);
    expect(out.phase).toBe('error');
    expect(out.stale).toBe(true);
    expect(out.after).toEqual(out.before);
    expect(out.after.length).toBeGreaterThan(0);
  });
});
