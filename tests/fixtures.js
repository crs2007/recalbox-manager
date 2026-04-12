const { test: base, expect } = require('@playwright/test');
const { spawn, execSync } = require('child_process');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const MOCK_DATA    = path.join(PROJECT_ROOT, 'test-data', 'mock-recalbox');
const SERVER_PORT  = 15123;  // dedicated test port — avoids conflict with a live server on 5123
const SERVER_URL   = `http://localhost:${SERVER_PORT}`;

async function waitForServer(url, timeoutMs = 15_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch (_) {}
    await new Promise(r => setTimeout(r, 300));
  }
  throw new Error(`Server at ${url} did not start within ${timeoutMs}ms`);
}

function killPort(port) {
  // Kill any process using the given port (Windows-compatible).
  // With FLASK_RELOADER=false there is only one Python process, so this is a simple cleanup.
  try {
    const output = execSync(
      process.platform === 'win32'
        ? `netstat -ano 2>nul | findstr ":${port} "`
        : `lsof -ti :${port}`,
      { encoding: 'utf8', stdio: 'pipe', timeout: 4000 }
    ).trim();
    if (!output) return;
    const pids = [...new Set(
      process.platform === 'win32'
        ? output.split('\n').map(l => l.trim().split(/\s+/).pop()).filter(Boolean)
        : output.split('\n').filter(Boolean)
    )];
    for (const pid of pids) {
      try {
        if (process.platform === 'win32') {
          execSync(`taskkill /F /T /PID ${pid} 2>nul`, { stdio: 'pipe', timeout: 3000 });
        } else {
          process.kill(parseInt(pid), 'SIGKILL');
        }
      } catch (_) {}
    }
  } catch (_) {}
}

// Fixture that starts/stops the Flask server once per worker (auto-applied to all tests).
const test = base.extend({
  server: [async ({}, use) => {
    // Clean up any stale server on our test port before starting
    killPort(SERVER_PORT);
    await new Promise(r => setTimeout(r, 500));

    const proc = spawn('python', ['server.py'], {
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        RECALBOX_SHARE: MOCK_DATA,
        PORT: String(SERVER_PORT),
        // Disable Werkzeug reloader — prevents orphan child processes that hold the port
        // open after we kill the parent process during fixture teardown
        FLASK_RELOADER: 'false',
        // Disable ScreenScraper so no real API calls happen during tests
        SS_USER: '',
        SS_PASS: '',
        SS_DEVID: '',
        SS_DEVPASS: '',
      },
      stdio: 'pipe',
    });

    proc.stderr.on('data', data => {
      // Uncomment for debugging:
      // process.stderr.write('[SERVER] ' + data);
    });

    proc.on('error', err => {
      console.error('Failed to start server:', err);
    });

    await waitForServer(SERVER_URL + '/api/config');

    await use(proc);

    // Teardown: kill the server process tree (covers Werkzeug reloader child)
    proc.kill();
    killPort(SERVER_PORT);
    await new Promise(r => setTimeout(r, 500));
  }, { scope: 'worker', auto: true }],
});

module.exports = { test, expect };
