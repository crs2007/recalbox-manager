#!/usr/bin/env node
/**
 * Creates test-data/mock-recalbox/ folder structure for Playwright tests.
 * Idempotent — safe to re-run. Called by tests/global-setup.js before each test run.
 */
const fs   = require('fs');
const path = require('path');

const BASE = path.join(__dirname, 'mock-recalbox');

function mkdirp(p) { fs.mkdirSync(p, { recursive: true }); }
function write(p, content) { fs.writeFileSync(p, content); }
function rmrf(p) { try { fs.rmSync(p, { recursive: true, force: true }); } catch (_) {} }

// Clean up leftover state from previous test runs (moved/deleted files, trash)
rmrf(path.join(BASE, 'roms', '_trash'));
rmrf(path.join(BASE, 'roms', 'snes'));
rmrf(path.join(BASE, 'roms', 'megadrive'));
rmrf(path.join(BASE, 'roms', 'psx'));
rmrf(path.join(BASE, 'roms', 'neogeo'));

// Recreate directories fresh
mkdirp(path.join(BASE, 'roms', 'snes'));
mkdirp(path.join(BASE, 'roms', 'megadrive'));
mkdirp(path.join(BASE, 'roms', 'psx'));
mkdirp(path.join(BASE, 'roms', 'neogeo'));
mkdirp(path.join(BASE, 'bios'));

// Both Sonic.md and DupGame.zip share identical bytes → same MD5 → duplicate group
const SHARED = Buffer.from('\x00SHARED_CONTENT_FOR_DUPLICATE_DETECTION_RECALBOX');

// SNES: 1 valid ROM, 1 misplaced Mega Drive file (.md extension is valid for megadrive, not snes)
write(path.join(BASE, 'roms', 'snes', 'SuperMario.smc'),   Buffer.from('\x00SNES_VALID_HEADER_SUPERMARIO'));
write(path.join(BASE, 'roms', 'snes', 'SonicWrong.md'),    Buffer.from('\x00MD_IN_WRONG_FOLDER_SONIC'));

// Mega Drive: 1 valid ROM (shares content with DupGame.zip → duplicate pair)
write(path.join(BASE, 'roms', 'megadrive', 'Sonic.md'),    SHARED);

// PSX: 1 complete .bin+.cue pair (valid), 1 .bin without .cue (triggers missing_cue diagnostic)
write(path.join(BASE, 'roms', 'psx', 'GameWithCue.bin'),   Buffer.from('\x00PSX_BIN_DISC1_WITH_CUE'));
write(path.join(BASE, 'roms', 'psx', 'GameWithCue.cue'),
  'FILE "GameWithCue.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n');
write(path.join(BASE, 'roms', 'psx', 'OrphanBin.bin'),     Buffer.from('\x00PSX_BIN_NO_CUE_ORPHAN'));

// NeoGeo: same content as Sonic.md → triggers duplicate detection
write(path.join(BASE, 'roms', 'neogeo', 'DupGame.zip'),    SHARED);

// BIOS: fake content → MD5 won't match expected PSX BIOS hash → "wrong_version" status
write(path.join(BASE, 'bios', 'scph1001.bin'),             Buffer.from('\x00FAKE_PSX_BIOS_WRONG_HASH'));

console.log('Mock data ready at:', BASE);
