const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const path = require('path');

// Unit-level check of _run_fallback_chain: a source that raises must not 500 the chain,
// and a timeout must fall through to the next source.
test('fallback chain contains source exceptions and falls through on timeout', () => {
  const root = path.resolve(__dirname, '..');
  const code = `
import sys, json
sys.path.insert(0, ${JSON.stringify(root)})
import server
def boom(*a): raise TimeoutError("read timed out")
def crash(*a): raise ValueError("oversize")
def ok(*a): return {"ok": True, "source": "last"}
server.SCRAPE_SOURCES[:] = [
  {"name": "a", "types": {"cover"}, "cover_fn": boom},
  {"name": "b", "types": {"cover"}, "cover_fn": crash},
  {"name": "c", "types": {"cover"}, "cover_fn": ok},
]
print(json.dumps(server._run_fallback_chain("cover", "snes", "x.sfc", "x")))
`;
  const out = execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop();
  expect(JSON.parse(out)).toEqual({ ok: true, source: 'last' });
});
