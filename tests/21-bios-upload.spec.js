const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const BIOS = path.join(root, 'test-data', 'mock-recalbox', 'bios');

const upload = (request, buf, extra = {}) => request.post('/api/fix/upload-bios', {
  multipart: { system: 'psx', expected_filename: 'scph1001.bin', ...extra, file: { name: 'scph1001.bin', mimeType: 'application/octet-stream', buffer: buf } },
});

test.describe('BIOS upload', () => {
  test('replaces atomically, keeps a .bak and leaves no temp file', async ({ request }) => {
    const target = path.join(BIOS, 'scph1001.bin');
    const before = fs.readFileSync(target);
    const res = await upload(request, Buffer.from('NEW_BIOS_CONTENT'));
    expect(res.ok()).toBeTruthy();
    expect(fs.readFileSync(target, 'utf8')).toBe('NEW_BIOS_CONTENT');
    expect(fs.readFileSync(target + '.bak')).toEqual(before);
    expect(fs.existsSync(target + '.upload.tmp')).toBeFalsy();
  });

  test('uploads over 64 MB are refused with a JSON 413', async ({ request }) => {
    const res = await upload(request, Buffer.alloc(65 * 1024 * 1024, 1));
    expect(res.status()).toBe(413);
    expect((await res.json()).error).toBe('too_large');
  });

  test('a wrong-hash upload cannot replace a BIOS that already has the right hash (unless forced)', () => {
    const code = String.raw`
import sys, os, io, json, hashlib
sys.path.insert(0, ${JSON.stringify(root)})
os.environ["RECALBOX_SHARE"] = ${JSON.stringify(path.join(root, 'test-data', 'mock-recalbox'))}
import server as s
target = os.path.join(s._bios_root(), "scph1001.bin")
good = open(target, "rb").read()
for e in s.BIOS_REQUIREMENTS["psx"]:
    if e["file"] == "scph1001.bin":
        e["md5"] = hashlib.md5(good).hexdigest()   # pretend the current file is the correct one
c = s.app.test_client()
h = {"X-Requested-With": "recalbox-manager"}
def post(force):
    d = {"system": "psx", "expected_filename": "scph1001.bin", "file": (io.BytesIO(b"WRONG"), "x.bin")}
    if force: d["force"] = "1"
    return c.post("/api/fix/upload-bios", data=d, headers=h, content_type="multipart/form-data")
r1 = post(False)
kept = open(target, "rb").read() == good
r2 = post(True)
print(json.dumps({"s1": r1.status_code, "kept": kept, "s2": r2.status_code, "forced": open(target, "rb").read() == b"WRONG"}))
`;
    const out = JSON.parse(execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop());
    expect(out).toEqual({ s1: 409, kept: true, s2: 200, forced: true });
  });
});
