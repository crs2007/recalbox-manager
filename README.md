# Recalbox ROM Manager

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

A web-based tool to organize, diagnose, and manage your [Recalbox](https://www.recalbox.com/) ROM collection. Runs on a Windows PC and connects to the Recalbox device via its SMB network share — no SSH, no scripts on the Pi.

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Cover Art (ScreenScraper)](#cover-art-screenscraper)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Supported Systems](#supported-systems)
- [Safety](#safety)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Full ROM Inventory** — Scans all system folders and lists every file
- **Misplaced ROM Detection** — Identifies files whose extension doesn't match their system folder (e.g., a `.smc` SNES file sitting in the Genesis folder)
- **Duplicate Detection** — Finds identical ROMs stored in multiple locations (content hash comparison)
- **ROM Diagnostics** — Detects why a game might fail to load: missing `.cue` files, no `.m3u` playlist for multi-disc games, broken `.m3u` references, empty/corrupt files, likely overdumps, and **ZIP content mismatch** (archive accepted by the system but contains files for a different system)
- **BIOS Status Check** — Verifies required BIOS files are present for every system that needs them, with optional MD5 hash validation
- **Cover Art** — Reads existing `gamelist.xml` covers and fetches missing ones from [ScreenScraper.fr](https://www.screenscraper.fr/). Covers are saved to the Recalbox share and instantly visible on your TV.
- **Move ROMs** — Relocate files to the correct system folder via the UI
- **Bulk Auto-Fix** — One-click fix for misplaced ROMs with an unambiguous target, and bulk-move all wrong-ZIP-contents ROMs to their correct systems
- **Safe Delete** — Moves deleted files to a `_trash` folder instead of permanently deleting
- **Search** — Find any ROM across all systems instantly
- **System Health Dashboard** — At-a-glance status for every emulator folder

## Screenshots

**Scanning in progress**

![Scanning](images/scaning.png)

**Dashboard after scan — systems overview with health stats**

![After scan](images/after_scan.png)

## Prerequisites

- **Python 3.10+** — [Download from python.org](https://www.python.org/downloads/)
- **Recalbox on the local network** — Confirm you can browse `\\RECALBOX\share` in Windows File Explorer before starting

## Quick Start

### Option A — start.bat (recommended)

```bat
:: 1. Clone or download this repository
git clone https://github.com/crs2007/recalbox-manager.git
cd recalbox-manager

:: 2. Double-click start.bat — it installs dependencies and starts the server
start.bat
```

### Option B — manual

```bat
git clone https://github.com/crs2007/recalbox-manager.git
cd recalbox-manager
pip install flask flask-cors py7zr
python server.py
```

Then open **http://localhost:5123** in your browser.

### First-time workflow

1. **Check connection** — The top bar shows the current share path. If it says **Connected**, your Recalbox is reachable. If not, update the path (see [Configuration](#configuration)).
2. **Scan ROMs** — Click the **Scan ROMs** button. The first scan over SMB can take 1–3 minutes for large collections.
3. **Review Systems** — The Systems tab shows every emulator folder with counts of OK, misplaced, cover art, and total files.
4. **Fix Issues** — Switch to the Issues tab to see misplaced ROMs. Use **Auto-Fix** for unambiguous moves, or move files individually.
5. **Check Duplicates** — The Duplicates tab groups identical files (by content hash) so you can decide which copy to keep.
6. **Run Diagnostics** — The Diagnostics tab flags ROMs that are present but likely broken: missing `.cue` files, corrupt archives, empty files, etc.
7. **Check BIOS** — The Diagnostics tab also shows which required BIOS files are present, missing, or the wrong version.
8. **Cover Art** — The Missing Covers tab shows all ROMs without artwork. Click **🖼 Scrape Cover** per ROM or **Scrape All Missing** to bulk-fetch from ScreenScraper.
9. **Search** — Use the Search tab to find any ROM across all systems instantly.

## Configuration

### Default share path

The tool assumes `\\RECALBOX\share`. If your Recalbox uses a different name or IP, change it in one of two ways:

**Option A — Web UI:** Use the path field in the top bar and click Update.

**Option B — Environment variable:**

```bat
set RECALBOX_SHARE=\\192.168.1.50\share
python server.py
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `RECALBOX_SHARE` | `\\RECALBOX\share` | UNC path to the Recalbox network share |
| `PORT` | `5123` | Local server port |
| `SS_USER` | *(none)* | ScreenScraper username (alternative to `screenscraper.cfg`) |
| `SS_PASS` | *(none)* | ScreenScraper password (alternative to `screenscraper.cfg`) |

### Port

```bat
set PORT=8080
python server.py
```

## Cover Art (ScreenScraper)

The tool integrates with [ScreenScraper.fr](https://www.screenscraper.fr/) — the same service Recalbox uses internally — to fetch box art for ROMs that don't have it yet.

### How it works

1. On every scan, the tool reads each system's `gamelist.xml` to detect which ROMs already have cover images (and verifies the image file actually exists on the share).
2. ROMs without covers are listed in the **Missing Covers** tab.
3. You can scrape one ROM at a time or use **Scrape All Missing** to process the whole list automatically (with a 1.2-second delay between requests to respect rate limits).
4. Each fetched image is saved to `\\RECALBOX\share\roms\<system>\media\images\` and the `gamelist.xml` is updated automatically. Recalbox will display the cover art immediately the next time you browse that system.

### Setting up ScreenScraper credentials

#### Option A — credentials file (recommended)

Create (or edit) the file `screenscraper.cfg` in the project folder:

```ini
[screenscraper]
user = your_username
pass = your_password
devid = your_developer_id
devpass = your_developer_password
```

This file is listed in `.gitignore` and will never be committed. The server loads it automatically on startup.

#### Option B — Web UI

Click the **🖼 ScreenScraper** button in the top config bar, enter your username and password, then click **Save**. The credentials are written to `screenscraper.cfg` automatically.

#### Option C — environment variables

```bat
set SS_USER=your_username
set SS_PASS=your_password
python server.py
```

### Getting credentials

Two separate registrations are needed at [screenscraper.fr](https://www.screenscraper.fr/):

1. **User account** — Register at the main site. This gives you `user` and `pass`.
2. **Developer API credentials** — Post a request in the [ScreenScraper developer forum](https://www.screenscraper.fr/forumsujets.php?frub=12&numpage=0). A moderator will reply with your `devid` and `devpass`.

Both are required. Without the developer credentials, the API returns HTTP 403.

### Supported systems for scraping

ScreenScraper supports most major systems: NES, SNES, N64, Game Boy family, GameCube, Wii, Mega Drive, Dreamcast, PlayStation, PSP, Atari, PC Engine, Neo Geo, MAME, Amiga, DOS, ScummVM, and many more.

Systems not listed in the ScreenScraper database will show a "system not supported" message rather than failing silently.

## Architecture

```
recalbox-manager/
├── server.py              # Python/Flask backend — API routes, ROM scanning, file ops
├── static/
│   └── index.html         # Single-page UI — vanilla JS, no build step, no framework
├── requirements.txt       # flask, flask-cors
├── start.bat              # Windows launcher (installs deps, starts server)
├── screenscraper.cfg      # Your ScreenScraper credentials (gitignored — do not commit)
└── README.md
```

**Design decisions:**

- **Single HTML file UI** — All styles, markup, and JS in one file. Zero build tooling needed.
- **In-memory scan cache** — Full ROM inventory is held in memory after a scan; no database required.
- **Extension-based detection** — `SYSTEM_EXTENSIONS` in `server.py` maps every Recalbox system folder to its valid file extensions. `EXTENSION_TO_SYSTEMS` is the reverse lookup used for suggesting corrections.
- **Diagnostic layer** — `run_rom_diagnostics()` runs 7 checks per system folder after extension detection, flagging issues that extension matching alone can't catch — including ZIP content inspection (Check 7) which opens each `.zip`/`.7z` and validates that the inner files match the current system's expected formats.
- **gamelist.xml integration** — `parse_gamelist()` reads each system's XML for cover paths; `write_gamelist_entry()` writes new entries atomically (temp file → rename, with `.bak` backup).
- **Safe deletes** — Trash goes to a `_trash/` subfolder under `roms/`, never permanent deletion.
- **Pagination** — ROM lists page at 100 items (client-side, from cached data).

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Current configuration and connection status |
| POST | `/api/config` | Update share path and/or ScreenScraper credentials |
| POST | `/api/scan` | Trigger a full ROM scan |
| GET | `/api/status` | Last scan time and summary stats |
| GET | `/api/systems` | All systems (summary only, no ROM lists) |
| GET | `/api/systems/<name>` | System detail with full ROM list and per-ROM diagnostics |
| GET | `/api/issues` | All issues, optional `?type=` filter |
| GET | `/api/duplicates` | Duplicate ROM groups by content hash |
| GET | `/api/diagnostics` | All diagnostic findings, optional `?system=` filter |
| GET | `/api/bios` | BIOS file presence and MD5 status for all systems |
| POST | `/api/move` | Move a single ROM `{ filename, from_system, to_system }` |
| POST | `/api/bulk-move` | Move multiple ROMs `{ moves: [{ filename, from_system, to_system }] }` |
| POST | `/api/delete` | Trash a ROM `{ filename, system }` |
| GET | `/api/search?q=` | Search ROMs by name across all systems |
| GET | `/api/covers/image/<system>/<file>` | Proxy a cover image from the SMB share to the browser |
| GET | `/api/covers/missing` | All properly-placed ROMs that have no cover art |
| POST | `/api/covers/scrape` | Fetch cover from ScreenScraper and update `gamelist.xml` |
| GET | `/api/gamelist/<system>` | Parsed `gamelist.xml` data for a system |
| POST | `/api/gamelist/update` | Merge or insert a `<game>` entry in `gamelist.xml` |

## Diagnostics

The **Diagnostics** tab identifies reasons a game might fail to load, beyond simple extension mismatches.

### ROM Checks (run per system folder after scan)

| Issue | Description |
|-------|-------------|
| `missing_cue` | A `.bin` file on a CD system has no matching `.cue` file. The emulator cannot read the disc without it. |
| `missing_m3u` | Multiple disc files (e.g., `(Disc 1)`, `(Disc 2)`) found but no `.m3u` playlist. Emulator won't know the disc order. |
| `broken_m3u` | An `.m3u` playlist references one or more disc files that don't exist in the folder. |
| `empty_file` | ROM is 0 bytes or under 512 bytes — almost certainly a corrupt or failed download. |
| `likely_overdump` | The last 512 bytes of the file are all `0xFF` or `0x00` — the hallmark of a padded bad dump. |
| `corrupt_archive` | A `.zip` file fails Python's `zipfile.is_zipfile()` check — the archive is unreadable. |
| `wrong_zip_contents` | The archive container (`.zip`/`.7z`) is accepted by the system, but the files **inside** belong to a different system. The emulator opens the archive and finds nothing it can use. Common cause: a MAME arcade romset dropped into a console folder (e.g., `outrun.zip` in `atari7800/`). |

Each diagnostic card in the UI shows a step-by-step fix and a **Search online** link pre-filled with a relevant query. Cards for `wrong_zip_contents` also show the inner file extensions found and **Move → system** buttons for each suggested destination. The **⚡ Fix All Wrong ZIPs** button in the filter bar moves all affected ROMs in one action.

### BIOS Status

Systems that require BIOS files are checked automatically. The Diagnostics tab shows:

- **✓ Present** — file found (and MD5 matches if a hash is known)
- **✗ Missing** — required file absent
- **⚠ Wrong version** — file present but MD5 doesn't match the expected hash
- **– Optional** — file absent but not required for basic operation

Systems with BIOS requirements: PlayStation, Dreamcast, GBA, Sega CD, Saturn, Neo Geo, Famicom Disk System, PC Engine CD, Neo Geo CD, Amiga CD32, 3DO, MSX/MSX2.

## Supported Systems

Recognizes 60+ Recalbox system folders with their valid ROM extensions, including:

- **Nintendo** — NES, SNES, N64, Game Boy, GBA, DS
- **Sega** — Master System, Mega Drive/Genesis, Saturn, Dreamcast, Game Gear
- **Sony** — PlayStation, PSP
- **Atari** — 2600, 5200, 7800, Jaguar, Lynx
- **NEC** — PC Engine / TurboGrafx-16
- **SNK** — Neo Geo, Neo Geo Pocket
- **Arcade** — MAME, FBNeo
- **Computers** — Amiga, DOS, MSX, ZX Spectrum, Commodore 64, and more

## Safety

- **No permanent deletes** — The delete function moves files to `_trash/` under the roms folder
- **No system files touched** — Only operates on the `roms/` directory
- **Read-only scan** — Scanning never modifies any files
- **Manual confirmation** — Bulk operations require explicit confirmation before executing
- **Atomic gamelist writes** — `gamelist.xml` updates use a temp-file-then-rename pattern with automatic `.bak` backups, so a crash mid-write cannot corrupt your metadata

## Troubleshooting

**"Not found" on share path**

- Confirm Recalbox is powered on and on the same network
- Test `\\RECALBOX\share` directly in Windows File Explorer
- If the hostname doesn't resolve, switch to the IP: `\\192.168.x.x\share`

**Scan is slow**

- Expected for large collections over SMB — a first scan of thousands of files can take 1–3 minutes
- Subsequent UI operations are fast because results are cached in memory

**ScreenScraper "not found" for a game**

- The ROM filename must be close to the official name. Try renaming it to match the No-Intro or Redump database name.
- Arcade ROMs (MAME short names like `mslug.zip`) work well; homebrew or hacks may not be in the database.

**ScreenScraper rate limit hit**

- The free tier allows ~20,000 requests/day. For very large collections, scrape one system at a time across multiple sessions.

**Cover saved but not showing on Recalbox TV**

- Recalbox caches its game list. Restart EmulationStation or reboot the Recalbox to reload `gamelist.xml`.

**Port already in use**

```bat
set PORT=8080
python server.py
```

## Known Limitations

- **Scan blocks the server** — The scan runs synchronously; the UI shows a spinner but the Flask thread is blocked. A very large collection may time out the request.
- **Arcade ROM matching** — MAME/FBNeo ROMs are all `.zip`, so extension-based detection cannot identify misplaced arcade ROMs within arcade folders. ZIP content inspection (Check 7) handles the reverse case: arcade romsets accidentally placed in console folders are now detected and flagged. DAT file support for full arcade validation is not yet implemented.
- **7z archives** — Corrupt `.7z` detection is not implemented (only `.zip` is checked by `zipfile.is_zipfile()`). ZIP content inspection for `.7z` requires `py7zr` — install it with `pip install py7zr` if not already present.
- **ScreenScraper credentials not encrypted** — `screenscraper.cfg` is plain text. It is gitignored and local-only, but anyone with access to your PC can read it.

## Contributing

Bug reports and feature suggestions are welcome via [GitHub Issues](../../issues).

If you'd like to contribute code:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a pull request

Please keep the zero-dependency frontend philosophy — no npm, no build step for the UI.

## License

MIT © 2026 Rimer Sharon — see [LICENSE](LICENSE) for details.
