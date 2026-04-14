# Changelog

All notable changes to Recalbox Manager are documented here.

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
