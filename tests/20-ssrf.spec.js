const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const path = require('path');

const root = path.resolve(__dirname, '..');

function runPy(body) {
  const code = String.raw`
import sys, json
sys.path.insert(0, ${JSON.stringify(root)})
import server as s, socket, urllib.error, urllib.request
${body}
`;
  return JSON.parse(execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop());
}

test.describe('SSRF hardening', () => {
  test('direct connections to loopback / private / metadata addresses are refused', () => {
    const out = runPy(`
res = {}
for u in ["http://127.0.0.1:1/x.png", "http://192.168.1.1/x.png", "http://169.254.169.254/latest/meta-data"]:
    try:
        s._public_urlopen(u, timeout=3); res[u] = "opened"
    except Exception as e:
        res[u] = type(e).__name__
print(json.dumps(res))
`);
    for (const v of Object.values(out)) expect(v).not.toBe('opened');
  });

  test('a hostname that rebinds to a private address is refused at connect time', () => {
    const out = runPy(`
real = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: [(2, 1, 6, "", ("10.0.0.5", 0))] if h == "rebind.test" else real(h, *a, **k)
try:
    s._public_urlopen("http://rebind.test/x.png", timeout=3); r = "opened"
except Exception as e:
    r = type(e).__name__ + ":" + str(e)
print(json.dumps(r))
`);
    expect(out).toContain('blocked non-public address');
  });

  test('redirects to non-http schemes or disallowed hosts are rejected', () => {
    const out = runPy(`
h = s._CheckedRedirectHandler(host_ok=s._is_archive_org_url)
req = urllib.request.Request("https://archive.org/x")
def hop(url):
    try:
        h.redirect_request(req, None, 302, "Found", {}, url); return "followed"
    except urllib.error.HTTPError:
        return "blocked"
print(json.dumps({"file": hop("file:///etc/passwd"), "evil": hop("https://evil.example/x"),
                  "ia": hop("https://ia800000.us.archive.org/x")}))
`);
    expect(out).toEqual({ file: 'blocked', evil: 'blocked', ia: 'followed' });
  });

  test('download-url still rejects loopback targets', async ({ request }) => {
    const res = await request.post('/api/covers/download-url', {
      data: { system: 'snes', filename: 'a.sfc', image_url: 'http://127.0.0.1:15123/api/status' },
    });
    expect(res.status()).toBe(400);
  });
});
