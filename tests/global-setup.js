const { execFileSync } = require('child_process');
const path = require('path');

/**
 * Runs before the entire test suite (once per `npm test` invocation).
 * Restores mock data to a known clean state so mutations from previous runs
 * (e.g. moved/deleted ROMs) don't break subsequent runs.
 */
module.exports = async function globalSetup() {
  const script = path.join(__dirname, '..', 'test-data', 'setup-mock-data.js');
  execFileSync(process.execPath, [script], { stdio: 'inherit' });
};
