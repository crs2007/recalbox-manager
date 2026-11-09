const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const path = require('path');

test('_sniff_image_ext detects real images and rejects text / php responses', () => {
  const root = path.resolve(__dirname, '..');
  const code = String.raw`
import sys, json
sys.path.insert(0, ${JSON.stringify(root)})
import server as s
print(json.dumps([
  s._sniff_image_ext(b"\x89PNG\r\n\x1a\n"+b"0"*8),
  s._sniff_image_ext(b"\xff\xd8\xff\xe0"+b"0"*8),
  s._sniff_image_ext(b"RIFF\x00\x00\x00\x00WEBPVP8 "),
  s._sniff_image_ext(b"RIFF\x00\x00\x00\x00WAVEfmt "),
  s._sniff_image_ext(b"Erreur: quota depasse"),
]))
`;
  const out = execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop();
  expect(JSON.parse(out)).toEqual(['.png', '.jpg', '.webp', null, null]);
});
