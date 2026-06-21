# Changelog

All notable changes to Recalbox Manager are documented here.

## v2026.06.3 — 2026-06-21
### Added
- **Download ROMs catalog** — New "Download ROMs" tab to acquire new games per system straight onto the share. Ships pre-built per-system catalogs (`catalog/<system>.json`) for the top 5 systems (MAME, NES, SNES, Genesis/Megadrive, GBA), generated offline from the archive.org metadata API by `tools/build_catalog.py`. Each game shows a cover (deterministic Libretro thumbnail URL, no pre-download) and lets you download the ROM into `roms/<system>/`, automatically writing a `gamelist.xml` entry with name, and best-effort cover + description (via the existing scrape fallback chain). New endpoints: `GET /api/catalog/systems`, `GET /api/catalog/<system>`, `POST /api/catalog/download`. Already-owned games are flagged against the current scan. Per-item and "download all on this page" (sequential queue) actions with progress.

## v2026.06.2 — 2026-06-21
### Added / Performance
- **Progressive, non-blocking scan** — `POST /api/scan` now starts the scan in a background thread and returns immediately; the UI polls the new `GET /api/scan/progress` endpoint and renders systems one-by-one with a live progress bar, so you can start working before the scan finishes. The scan runs in two phases: a fast metadata-only **inventory** (names/sizes/placement/gamelist — no per-file content reads), then a background **deep analysis** (duplicate detection + content diagnostics) that fills in counts as it completes.
- **Faster duplicate detection** — Files are now grouped by size first and only candidates that share a size with another file are hashed. Files with a unique size cannot be duplicates, so the large majority of the per-ROM 64 KB hash reads over SMB are skipped.
- **Fewer SMB round-trips** — `parse_gamelist()` now batches cover-image existence checks (one `os.scandir` per media folder instead of one `os.path.exists` per game), and `run_rom_diagnostics()` reuses the file list already gathered during inventory instead of re-enumerating each system folder.

## v2026.06.0 — 2026-06-20
### Fixed
- **Data-loss guard on move** — Moving a ROM into a folder that already contains a same-named file no longer trashes the source based on a 64 KB partial hash. `files_identical()` now requires equal size **and** a full-file byte comparison before the misplaced source is removed (affects `/api/move` and `/api/bulk-move`). Two different ROMs that shared a 64 KB header could previously cause the source to be silently trashed.
- **Path traversal** — `/api/move`, `/api/delete`, and `/api/bulk-move` now reject any `filename` that isn't a bare basename (blocks `..` escapes and absolute paths), matching the guard already used by the auto-fix endpoints.
- **Version check** — "Update available" now compares CalVer numerically (`2026.06.0` parsed to an int tuple) instead of lexicographically, which wrongly ranked `2026.04.6` above `2026.04.23`.
- **m3u false positive** — Comment lines with leading whitespace (`  # ...`) are no longer mistaken for disc references in the `broken_m3u` diagnostic.
### Changed / Security
- **Localhost by default** — The server now binds `127.0.0.1` and runs with `debug=False` unless `RECALBOX_MANAGER_HOST=0.0.0.0` / `FLASK_DEBUG=1` are set. This removes the Werkzeug interactive-debugger RCE surface and stops exposing the unauthenticated API to the whole LAN by default.
- **CORS scoped to localhost** — Replaced the wildcard CORS policy with a localhost-only origin allowlist, closing cross-site (CSRF-style) access to the mutating endpoints.
- **SSRF guard** — `/api/covers/download-url` now rejects URLs whose host resolves to loopback/private/link-local addresses (e.g. cloud metadata, `127.0.0.1`).
- **Download size caps** — All image fetches (ScreenScraper, Libretro, Sega Fandom) now cap the response at 25 MB instead of reading unbounded into memory.
- **Concurrency** — Added a lock around the scan-cache swap and the gamelist.xml read-modify-write so concurrent scans/scrapes can't corrupt state or lose updates.
- **share_path validation** — `/api/config` now rejects empty / non-string / null-byte share paths.
- Narrowed an over-broad `except` in archive inspection; standardized JSON request parsing on `get_json(silent=True)`; hardened the frontend `escJs` helper to escape newlines.

## v2026.04.23 — 2026-04-27
### Changed
- **BIOS Status UX** — Added a summary banner showing counts of required/optional/wrong-version BIOS files with a plain-language explanation of what to do. Rows now sorted by priority (required missing first, ok rows dimmed at bottom). Each missing/wrong-version row gets a "🔍 Search" button that opens a DuckDuckGo search for the filename. Upload button relabelled "⚡ Select & Upload" to clarify it opens a local file picker.

## v2026.04.22 — 2026-04-27
### Added
- **31 new system definitions** — Added `tic80` (.tic), `pico8` (.p8/.png), `3do`, `apple2`, `atari800`, `atarixegs`, `bbcmicro`, `cdimono1`, `c16`, `c128`, `vic20`, `daphne`, `dragon32`, `easyrpg`, `famicom`, `gameandwatch`, `lowresnx` (.nx), `megaduck`, `n64dd`, `openbor` (.pak), `pcfx`, `sgb`, `solarus`, `supervision`, `ti99`, `turbografx`, `turbografxcd`, `uzebox` (.uze), `videopac`, `wasm4` (.wasm), `x1` to `SYSTEM_EXTENSIONS`. ROMs in these folders are no longer flagged as unknown/unrecognised.
### Fixed
- **Extension gaps on existing systems** — Added missing extensions: `.neo` (neogeo), `.chd` (mame), `.dmg` (gb/gbc/gba), `.68k`/`.mdx`/`.sgd` (megadrive/genesis), `.rom`/`.abs`/`.cof` (atarijaguar), `.md`/`.smd` (sega32x), `.toc`/`.cbn`/`.ccd` (psx), `.vboy` (virtualboy), `.pc2` (wonderswan/wonderswancolor), `.chd` (pcengine), `.scummvm` (scummvm), `.gz`/`.udi`/`.mgt`/`.trd`/`.scl`/`.dsk` (zxspectrum), `.m3u` (neogeocd/saturn/dreamcast).

## v2026.04.21 — 2026-04-27
### Fixed
- **Connection indicator after failed scan** — When "Scan ROMs" fails (e.g. Recalbox offline or share unreachable), the "● Connected" indicator now correctly flips to "● Not found" instead of staying green.

## v2026.04.20 — 2026-04-26
### Added
- **BIOS upload fix** — "⚡ Upload BIOS" button in the BIOS Status table for entries with status `missing` or `wrong_version`. Selecting a file uploads it via `POST /api/fix/upload-bios` which saves it to `{share}/bios/`. MD5 is verified if known — mismatch shows a yellow warning toast (regional variants still accepted). On success, BIOS table refreshes automatically.
- **snes BIOS detection** — Added `BS-X.bin` (required, MD5 `fed4d8242cfbed61343d53d48432aced`) to `BIOS_REQUIREMENTS` for the `snes` system so the snes9x mandatory-BIOS error is now visible and actionable in the Diagnostics tab.

## v2026.04.19 — 2026-04-26
### Added
- **Clickable stat cards** — All stat cards in the dashboard header are now clickable buttons that navigate directly to the relevant tab: Systems → Systems tab, Total ROMs → Browse, Misplaced → Issues, Duplicates → Duplicates, Total Issues → Issues, Diagnostics → Diagnostics, With Covers / Missing Covers → Missing Covers, With Descriptions / Missing Descriptions → Missing Descriptions. Total Size remains non-clickable. Cards show a pointer cursor and lift on hover.
### Explained
- **Total Issues vs Misplaced:** "Total Issues" counts all issue types combined — `unknown_system` (ROMs in unrecognized system folders), `misplaced` (wrong extension in a known system), `duplicate` groups, `corrupted_gamelist`, and `permission_error`. "Misplaced" only counts ROMs with a wrong extension inside a *known* system. ROMs in folders not listed in `SYSTEM_EXTENSIONS` (unknown systems) are counted in Total Issues but not in Misplaced.

## v2026.04.18 — 2026-04-25
### Added
- **Report Issue feature** — "⚠ Report Issue" button in the footer, Diagnostics tab header, and Knowledge Base tab lets users report unknown issues directly from the app. Clicking it fetches a full diagnostic snapshot (app version, Python/OS info, scan stats, diagnostic counts, last 50 log lines) and opens a pre-filled GitHub issue in a new tab — no GitHub token required.
- **`GET /api/diagnostics/snapshot`** — New endpoint that collects environment info, scan stats, and diagnostics grouped by type with sample files for bug-report use.
- **`GET /api/version/check`** — Checks GitHub releases for a newer version (cached 1 hour). If an update is available, a subtle "↑ Update: vX.X.X" banner appears in the header linking to the release page.
- **`POST /api/kb/report` + `GET /api/kb/reports`** — Session-local user report store (max 20, never written to disk). Submitted reports appear in a "Recently Reported by You" strip at the bottom of the Knowledge Base tab.
- **In-memory log ring buffer** — A `_RingHandler` attached to the root logger captures the last 50 log lines in memory, included in the diagnostic snapshot for bug reports.
- **"Request Auto-fix" button** — Diagnostic cards for non-auto-fixable issue types now show a "✦ Request Fix" button that opens the Report Issue modal pre-filled with the type and system name.
- **"My problem is different" KB link** — Each expanded Knowledge Base card now has a link that opens the Report Issue modal pre-filled with the issue key.

## v2026.04.17 — 2026-04-25
### Fixed
- **Move is a true move, not a copy** — After a successful `shutil.move`, the server now calls `_remove_rom_from_cache()` to remove the file from the source system in the in-memory scan cache (roms list, diagnostic issues, global issues, and stats). Previously the cache was never updated, so the file kept appearing in the source system panel, making it look as though it had only been copied. The UI now removes the diagnostic card and issues entry immediately on success without requiring a rescan.

## v2026.04.16 — 2026-04-25
### Fixed
- **Move to non-existent system folder now works** — `/api/move` and `/api/bulk-move` previously returned "Destination system folder not found" for systems like `amiga` or `genesis` whose folders don't exist on the share yet (because the user never had ROMs there). Both endpoints now create the missing folder automatically before moving the file.

## v2026.04.15 — 2026-04-25
### Fixed
- **`.7z` archive inspection now actually runs** — `start.bat` was only installing `flask` and `flask-cors`, silently skipping `py7zr`. As a result Check 7 (`wrong_zip_contents`) returned `None` for every `.7z` file and never flagged anything — Sega 32X (and any system with `.7z` ROMs) showed no in-portal indication of the "this 7zipped game does not contain any file supported by the selected emulator" issue. `start.bat` now installs from `requirements.txt` and the import test includes `py7zr`.
- **Visible warning when `py7zr` is missing** — `/api/config` now returns `py7zr_available`. The UI shows an orange banner under the share-path bar telling the user to `pip install py7zr` and restart, so the silent-skip failure mode can never recur unnoticed. Server logs a `WARNING` at startup as well.

## v2026.04.14 — 2026-04-25
### Added
- **Per-file Auto-Fix for wrong archive contents** — `wrong_zip_contents` diagnostic cards now show an **⚡ Move → {system}** button directly in the card header, matching the UX pattern of other fixable diagnostic types (`missing_cue`, `missing_m3u`, `smc_copier_header`). Clicking it moves the misplaced archive to its suggested system in one step without expanding the card.
- **Wrong-archive warning badge on Diagnostics tab** — When archives with wrong inner contents are detected, an amber ⚠ count badge appears on the Diagnostics tab button so the problem is visible without navigating into the tab.

## v2026.04.13 — 2026-04-19
### Added
- **Severity classification** — All 12 diagnostic issue types now carry `severity` (critical / warning / info) and `auto_fix` metadata. Diagnostic cards display a colored severity badge (red/yellow/cyan) in the card header.
- **Auto-Fix: Generate CUE** — `POST /api/fix/generate-cue` creates a minimal single-track `.cue` file for any missing-CUE diagnostic. Cards for `missing_cue` issues now show an **⚡ Auto-Fix** button that runs the fix instantly and removes the card without a rescan.
- **Auto-Fix: Generate M3U** — `POST /api/fix/generate-m3u` generates a multi-disc `.m3u` playlist. Cards for `missing_m3u` issues show an **⚡ Auto-Fix** button.
- **Auto-Fix: Strip SMC Header** — `POST /api/fix/strip-smc-header` strips the 512-byte copier header from SNES `.smc` files, creating a `.smc.bak` backup first. Cards show an **⚡ Strip Header** button with a confirmation dialog.
- **Auto-Fix: Rename BIOS** — `POST /api/fix/rename-bios` renames a wrong-case BIOS file to the expected filename. BIOS table now has an **Actions** column with an **⚡ Fix Case** button for `wrong_case` entries.
- **Knowledge Base tab** — New **Knowledge Base** tab (between Diagnostics and Missing Covers) serves the full `DIAGNOSTIC_SOLUTIONS` dict via `GET /api/kb`. Supports full-text search (title, description, steps), category filtering (ROM Diagnostics / BIOS Issues), collapsible cards with severity + auto-fixable badges, numbered steps, and a "Search online" link per entry. Loaded automatically on init and after each scan.

## v2026.04.12 — 2026-04-19
### Added
- **Corrupted gamelist.xml detection & auto-repair** — `parse_gamelist()` now reports corruption state (error, recoverability, repair kind) back to the scan pipeline, which emits a new `corrupted_gamelist` issue type. The Issues tab surfaces these with a 🧩 icon, parse-error detail, count of recovered entries, and a **Repair** button. New `POST /api/gamelist/repair` endpoint creates a `.bak` backup, strips trailing junk after the last `</gameList>`, verifies the result parses, atomically replaces the file, refreshes the in-memory cache, and drops the issue. Filter chip added for the new issue type.

## v2026.04.11 — 2026-04-18
### Fixed
- **Malformed gamelist.xml recovery** — `parse_gamelist()` now recovers from trailing junk after the `</gameList>` closing tag (e.g. `</gameList>st>`). Previously, any XML parse error caused the entire gamelist to be silently skipped, making all cover images and metadata invisible. Affected sega32x and potentially any system with a corrupted gamelist.xml

## v2026.04.10 — 2026-04-18
### Added
- **Browser favicon** — added an SVG favicon (retro game controller icon) matching the app's dark/cyan theme, so the browser tab shows a proper icon instead of the generic default

## v2026.04.9 — 2026-04-18
### Fixed
- **Browse tab stale covers** — after setting/scraping a cover image on a ROM, the browse tab now correctly shows the updated cover instead of the old "no cover" placeholder. The browse cache is invalidated when system data is reloaded.

## v2026.04.8 — 2026-04-18
### Added
- **Sega Fandom Wiki scraper** — new `fetch_sega_fandom_description()` and `fetch_sega_fandom_cover()` functions that pull game descriptions and cover images from sega.fandom.com via MediaWiki API (opensearch + extracts/pageimages). Automatically used for Sega systems (Mega Drive, Master System, Game Gear, Saturn, Dreamcast, etc.)
- **Generalized fallback scrape chain** — replaced hardcoded if-else fallback logic with a data-driven `SCRAPE_SOURCES` registry and `_run_fallback_chain()` runner. Sources are tried in order, skipping those that don't apply to the current system. Transient errors (rate limit, timeout) stop the chain; "not found" errors cascade to the next source
  - **Covers:** ScreenScraper → Libretro Thumbnails → Sega Fandom Wiki (Sega systems only)
  - **Descriptions:** ScreenScraper → Sega Fandom Wiki (Sega systems only) → Bootleg Games Wiki
- Frontend toasts now show which source provided data (e.g. "via sega_fandom") and handle new error types (`sega_fandom_down`, `no_sources`)

### Changed
- Adding a new scrape source now only requires writing a fetch function and appending one entry to the `SCRAPE_SOURCES` list — no endpoint changes needed

## v2026.04.7 — 2026-04-18
### Added
- **Netflix-style Browse tab** — card-based horizontal scrolling interface for browsing the game library visually, with cover art cards, hover overlays, lazy-loaded rows via IntersectionObserver, per-row scroll buttons, system filter, and text search
- **Metadata editing suite** — click any game (from Browse tab or table view ✏️ button) to open a rich edit modal with game name, description, star rating, cover preview, cover download from URL, and scrape buttons
- **`/api/covers/download-url` endpoint** — download cover images from user-provided URLs with image validation (PNG/JPEG/GIF/WebP magic bytes), 10MB size limit, and automatic gamelist.xml update

## v2026.04.6 — 2026-04-14
### Fixed
- Connection indicator now updates to "Connected" after a successful scan — previously it stayed "Not found" if the Recalbox was offline when the page first loaded

## v2026.04.5 — 2026-04-13
### Added
- Bootleg Games Fandom wiki as secondary description source; used as fallback when ScreenScraper returns `not_found` or has no credentials

## v2026.04.4 — 2026-04-13
### Changed
- `start.bat` no longer has a hardcoded version string. It reads `APP_VERSION` from
  `server.py` at launch using `findstr`, so the banner always shows the correct version
  automatically.

## v2026.04.3 — 2026-04-13
### Fixed
- Missing Descriptions and Missing Covers stat cards now stay in sync with the tab badges.
  The Refresh button in both tabs now also refreshes dashboard stats, so the large indicator
  and the tab badge always show the same count. The page reload (init) also pre-loads both
  lists so tab badges are correct without needing a manual Refresh first.

## v2026.04.2 — 2026-04-13
### Changed
- Version is now defined once as `APP_VERSION` in `server.py` (single source of truth).
  All User-Agent strings and the `/api/config` response use this constant. The UI reads
  the version from the API instead of a hardcoded HTML string.

## v2026.04.1 — 2026-04-13
### Fixed
- Description/cover counts silently resetting to the original high number after reconnecting: when
  `write_gamelist_entry` failed to persist to `gamelist.xml`, the backend still marked ROMs as
  having a description in the in-memory cache, and the frontend showed "Description saved" —
  so the count looked correct within the session but jumped back on the next scan (which re-reads
  from disk). Backend now only updates the in-memory cache on a confirmed write; frontend now
  shows a specific error when `gamelist_updated` is false instead of a false success toast.
  Same fix applied to cover scraping.

## v2026.04.0 — 2026-04-12
### Added
- Initial release
- ROM scanning via SMB share (`\\RECALBOX\share`)
- Issue detection: misplaced ROMs, duplicates, orphaned files, BIOS validation
- Bulk move and safe delete (moves to `_trash/`, never permanent)
- ROM search across all systems
- Diagnostics tab
- ScreenScraper and LibRetro thumbnail integration
- Pagination for large ROM collections (100 per page)
