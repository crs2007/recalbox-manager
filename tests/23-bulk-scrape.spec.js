const { test, expect } = require('./fixtures');
const { execFileSync } = require('child_process');
const path = require('path');

const root = path.resolve(__dirname, '..');

test('bulk cover scrape stops on rate_limited and can be resumed', async ({ page }) => {
  let calls = 0;
  await page.route('**/api/covers/scrape', route => {
    calls += 1;
    route.fulfill({ json: { ok: false, error: 'rate_limited' } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: /Scan ROMs/i }).click();
  await expect(page.locator('.spinner')).not.toBeAttached({ timeout: 30_000 });
  await page.locator('button[data-tab="covers"]').click();

  await page.getByRole('button', { name: /Scrape All Missing/ }).click();
  await expect(page.getByRole('button', { name: /Resume/ })).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(2500);          // would be ~2 more calls if the queue kept going
  expect(calls).toBe(1);
});

test('cover + description for one ROM share a single ScreenScraper request', () => {
  const code = String.raw`
import sys, json
sys.path.insert(0, ${JSON.stringify(root)})
import server as s, io
s.ss_config.update({"screenscraper_user": "u", "screenscraper_pass": "p", "screenscraper_devid": "d", "screenscraper_devpass": "dp"})
calls = {"n": 0}
body = json.dumps({"response": {"ssuser": {"requeststoday": "5", "maxrequestsperday": "20000"},
  "jeu": {"medias": [], "synopsis": [{"langue": "en", "text": "A game."}]}}}).encode()
class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass
def fake(req, timeout=None, host_ok=None):
    calls["n"] += 1
    return R(body)
s._public_urlopen = fake
d = s.fetch_screenscraper_description("snes", "Some Game.sfc", "")
c = s.fetch_screenscraper_cover("snes", "Some Game.sfc", "")
print(json.dumps({"calls": calls["n"], "desc": d.get("desc"), "cover_err": c.get("error"), "quota": s._ss_quota_snapshot()}))
`;
  const out = JSON.parse(execFileSync('python', ['-c', code], { encoding: 'utf8' }).trim().split('\n').pop());
  expect(out.calls).toBe(1);
  expect(out.desc).toBe('A game.');
  expect(out.cover_err).toBe('not_found');
  expect(out.quota.remaining).toBe(19995);
});
