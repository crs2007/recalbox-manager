#!/usr/bin/env python3
"""
build_catalog.py — Offline generator for the ROM download catalog.

Hits the archive.org metadata API (https://archive.org/metadata/<identifier>) for each
configured system, filters the item's file list down to usable per-game ROM files, and
writes catalog/<system>.json — a static, committed catalog the running app serves.

This is a DEV/BUILD tool. The running server never calls it; it only reads the JSON.
Re-run it to refresh the committed catalogs:

    python tools/build_catalog.py            # all systems
    python tools/build_catalog.py nes snes   # just these

Notes / caveats:
  - The archive.org identifiers below are curated, per-game items (one file == one game).
    If an item is removed or restructured, update CATALOG_SOURCES and re-run. The live app
    degrades gracefully — a download from a stale URL just returns an error.
  - Covers are NOT downloaded here. Each entry stores a deterministic Libretro Named_Boxarts
    URL (same encoding rules as server.fetch_libretro_cover) that the browser loads directly.
    Systems with no Libretro mapping (e.g. MAME) get cover_url=None and show a placeholder.
  - MAME caveat: the reference set uses short codes (sf2.zip) as filenames, so even where a
    Libretro mapping exists, boxart matching mostly misses. Placeholders are expected there.
"""

from __future__ import annotations

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import date

# Reuse the single source of truth from the server module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402  (SYSTEM_EXTENSIONS, LIBRETRO_SYSTEM_NAMES, helpers)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_DIR = os.path.join(REPO_ROOT, "catalog")

# Per-system archive.org sources. Each source is one item:
#   identifier — archive.org item id (the <id> in archive.org/download/<id>/...)
#   subdir     — optional path prefix inside the item where the ROM files live ("" = root)
# Multiple sources may be listed per system (e.g. an alphabetised split); they are merged.
# Files are kept only if their extension is valid for the system (server.SYSTEM_EXTENSIONS).
CATALOG_SOURCES: dict[str, list[dict]] = {
    # Arcade — per-game .zip under roms/ (the example from the feature request).
    "mame": [
        {"identifier": "mame-2003-plus-reference-set", "subdir": "roms"},
    ],
    # NES — Myrient No-Intro, per-game .zip at root. Alphabetised split items.
    "nes": [
        {"identifier": "no-intro-nes-roms-from-myrient-m-r", "subdir": ""},
        {"identifier": "no-intro-nes-roms-from-myrient-s-z", "subdir": ""},
    ],
    # SNES — per-game .zip under SNES/.
    "snes": [
        {"identifier": "snes-collection-no-intro", "subdir": "SNES"},
    ],
    # Genesis / Mega Drive — No-Intro, per-game .zip at root.
    "megadrive": [
        {"identifier": "NoIntroSegaMegaDriveGenesis2019July30", "subdir": ""},
    ],
    # Game Boy Advance — Recalbox 1G1R, per-game .7z at root.
    "gba": [
        {"identifier": "recalbox-nointro-gba-1g1r-retroninjasamurai", "subdir": ""},
    ],
}

# Archive housekeeping files to never treat as games, regardless of extension filter.
_META_SUFFIXES = ("_meta.xml", "_files.xml", "_reviews.xml", "_meta.sqlite", "__ia_thumb.jpg")


def _libretro_cover_url(system_key: str, full_name: str) -> str | None:
    """Deterministic Libretro Named_Boxarts URL — mirrors server.fetch_libretro_cover encoding.
    `full_name` is the full No-Intro ROM stem (region/rev tags kept), which is what Libretro
    boxart filenames use. Returns None for systems Libretro doesn't map (e.g. MAME)."""
    system_name = server.LIBRETRO_SYSTEM_NAMES.get(system_key.lower())
    if not system_name or not full_name:
        return None
    safe_name = re.sub(r'[&*/:<>?\\|]', '_', full_name)
    encoded_system = urllib.parse.quote(system_name, safe='')
    encoded_name = urllib.parse.quote(safe_name, safe='')
    return f"https://thumbnails.libretro.com/{encoded_system}/Named_Boxarts/{encoded_name}.png"


def _fetch_metadata(identifier: str) -> dict:
    url = f"https://archive.org/metadata/{urllib.parse.quote(identifier)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"recalbox-manager/{server.APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _build_system(system_key: str, sources: list[dict]) -> dict:
    valid_exts = server.SYSTEM_EXTENSIONS.get(system_key, set())
    games: dict[str, dict] = {}  # keyed by filename to dedupe across split sources
    identifiers: list[str] = []

    for src in sources:
        identifier = src["identifier"]
        subdir = (src.get("subdir") or "").strip("/")
        identifiers.append(identifier)
        print(f"  [{system_key}] fetching {identifier} ...", flush=True)
        meta = _fetch_metadata(identifier)
        files = meta.get("files", [])
        prefix = (subdir + "/") if subdir else None

        kept = 0
        for f in files:
            name = f.get("name", "")
            if not name or name.endswith(_META_SUFFIXES):
                continue
            if prefix:
                if not name.startswith(prefix):
                    continue
                rel = name[len(prefix):]
            else:
                rel = name
            if "/" in rel:  # nested deeper than expected — skip
                continue
            ext = os.path.splitext(rel)[1].lower()
            if ext not in valid_exts:
                continue

            stem = os.path.splitext(rel)[0]
            display = server._clean_rom_name(rel)
            try:
                size = int(f.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            # Download path within the item (include subdir), URL-encoded per segment.
            dl_path = "/".join(urllib.parse.quote(p) for p in name.split("/"))
            games[rel] = {
                "filename": rel,
                "name": display,
                "size": size,
                "size_human": server.format_size(size) if size else "",
                "url": f"https://archive.org/download/{urllib.parse.quote(identifier)}/{dl_path}",
                # Libretro Named_Boxarts filenames keep the full No-Intro name (region/rev
                # tags included), so match on the full stem rather than the cleaned display name.
                "cover_url": _libretro_cover_url(system_key, stem),
            }
            kept += 1
        print(f"    kept {kept} games ({len(files)} files in item)", flush=True)

    ordered = sorted(games.values(), key=lambda g: g["name"].lower())
    return {
        "system": system_key,
        "name": server.SYSTEM_DISPLAY_NAMES.get(system_key, system_key),
        "source_identifiers": identifiers,
        "source": "archive.org",
        "built": date.today().isoformat(),
        "count": len(ordered),
        "games": ordered,
    }


def main(argv: list[str]) -> int:
    os.makedirs(CATALOG_DIR, exist_ok=True)
    targets = argv[1:] or list(CATALOG_SOURCES.keys())
    unknown = [s for s in targets if s not in CATALOG_SOURCES]
    if unknown:
        print(f"Unknown system(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Available: {', '.join(CATALOG_SOURCES)}", file=sys.stderr)
        return 2

    for system_key in targets:
        print(f"Building catalog for {system_key} ...", flush=True)
        try:
            catalog = _build_system(system_key, CATALOG_SOURCES[system_key])
        except urllib.error.URLError as e:
            print(f"  ERROR fetching {system_key}: {e}", file=sys.stderr)
            continue
        out_path = os.path.join(CATALOG_DIR, f"{system_key}.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(catalog, fh, ensure_ascii=False, indent=2)
        print(f"  wrote {out_path} ({catalog['count']} games)\n", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
