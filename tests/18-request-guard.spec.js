const { test, expect } = require('./fixtures');

test.describe('Request guard (DNS rebinding / CSRF)', () => {
  test('mutating request without the custom header is refused', async ({ request }) => {
    const res = await request.post('/api/scan', { headers: { 'X-Requested-With': '' } });
    expect(res.status()).toBe(403);
  });

  test('multipart upload (simple CSRF request) without the header is refused', async ({ request }) => {
    const res = await request.post('/api/fix/upload-bios', {
      headers: { 'X-Requested-With': '' },
      multipart: { system: 'psx', expected_filename: 'scph1001.bin', file: { name: 'x.bin', mimeType: 'application/octet-stream', buffer: Buffer.from('x') } },
    });
    expect(res.status()).toBe(403);
  });

  test('a cross-origin Origin is refused even with the header', async ({ request }) => {
    const res = await request.post('/api/scan', { headers: { Origin: 'http://evil.example' } });
    expect(res.status()).toBe(403);
  });

  test('a rebound hostname in Host is refused for reads too', async ({ request }) => {
    const res = await request.get('/api/status', { headers: { Host: 'evil.example:15123' } });
    expect(res.status()).toBe(403);
  });

  test('normal localhost requests still work', async ({ request }) => {
    const res = await request.get('/api/status');
    expect(res.ok()).toBeTruthy();
  });

  test('switching share_path to another network host needs confirmation', async ({ request }) => {
    const res = await request.post('/api/config', { data: { share_path: '\\\\attacker.example\\share' } });
    expect(res.status()).toBe(409);
    expect((await res.json()).error).toBe('host_change_requires_confirmation');
    // and nothing was changed
    const cfg = await (await request.get('/api/config')).json();
    expect(cfg.share_path).not.toContain('attacker');
  });
});
