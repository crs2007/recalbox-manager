"""
Recalbox ROM Manager - Backend Server
Scans \\\\RECALBOX\\share via mapped network path, detects misplaced ROMs,
and provides a web API for organizing your collection.
"""

from __future__ import annotations

import os
import json
import shutil
import hashlib
import logging
import zipfile
import re
try:
    import py7zr
    PY7ZR_AVAILABLE = True
except ImportError:
    PY7ZR_AVAILABLE = False
import mimetypes
import configparser
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from collections import defaultdict
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

APP_VERSION = "2026.04.4"

# ─── Configuration ────────────────────────────────────────────────────────────
# Mutable config dict — avoids global keyword in route handlers.
# Access share-derived paths via _roms_root() / _bios_root() helpers.
_config: dict[str, str] = {
    "share": os.environ.get("RECALBOX_SHARE", r"\\RECALBOX\share"),
}

def _roms_root() -> str:
    return os.path.join(_config["share"], "roms")


def _bios_root() -> str:
    return os.path.join(_config["share"], "bios")

# ─── ROM Extension Database ──────────────────────────────────────────────────
# Maps each Recalbox system folder to its valid ROM extensions
SYSTEM_EXTENSIONS = {
    # Nintendo
    "nes":          {".nes", ".unf", ".unif", ".fds", ".zip", ".7z"},
    "snes":         {".smc", ".sfc", ".fig", ".swc", ".zip", ".7z"},
    "n64":          {".n64", ".z64", ".v64", ".zip", ".7z"},
    "gb":           {".gb", ".zip", ".7z"},
    "gbc":          {".gbc", ".gb", ".zip", ".7z"},
    "gba":          {".gba", ".zip", ".7z"},
    "nds":          {".nds", ".zip", ".7z"},
    "gamecube":     {".iso", ".gcm", ".ciso", ".gcz", ".rvz"},
    "wii":          {".iso", ".wbfs", ".ciso", ".gcz", ".rvz"},
    "virtualboy":   {".vb", ".zip", ".7z"},
    "fds":          {".fds", ".nes", ".zip", ".7z"},
    "satellaview":  {".bs", ".smc", ".sfc", ".zip", ".7z"},
    "sufami":       {".smc", ".sfc", ".zip", ".7z"},
    "pokemini":     {".min", ".zip", ".7z"},
    # Sega
    "megadrive":    {".md", ".bin", ".gen", ".smd", ".zip", ".7z"},
    "genesis":      {".md", ".bin", ".gen", ".smd", ".zip", ".7z"},
    "mastersystem": {".sms", ".bin", ".zip", ".7z"},
    "gamegear":     {".gg", ".zip", ".7z"},
    "sg1000":       {".sg", ".bin", ".zip", ".7z"},
    "sega32x":      {".32x", ".bin", ".zip", ".7z"},
    "segacd":       {".iso", ".bin", ".cue", ".chd"},
    "saturn":       {".iso", ".bin", ".cue", ".chd", ".mdf", ".mds"},
    "dreamcast":    {".gdi", ".cdi", ".chd", ".cue", ".bin", ".iso"},
    # Sony
    "psx":          {".iso", ".bin", ".cue", ".img", ".pbp", ".chd", ".m3u", ".mdf", ".mds", ".ecm"},
    "psp":          {".iso", ".cso", ".pbp"},
    # Atari
    "atari2600":    {".a26", ".bin", ".zip", ".7z"},
    "atari5200":    {".a52", ".bin", ".zip", ".7z"},
    "atari7800":    {".a78", ".bin", ".zip", ".7z"},
    "atarijaguar":  {".j64", ".jag", ".zip", ".7z"},
    "atarilynx":    {".lnx", ".zip", ".7z"},
    "atarist":      {".st", ".stx", ".msa", ".ipf", ".zip", ".7z"},
    # NEC
    "pcengine":     {".pce", ".zip", ".7z"},
    "pcenginecd":   {".cue", ".bin", ".iso", ".chd"},
    "supergrafx":   {".pce", ".sgx", ".zip", ".7z"},
    # SNK
    "neogeo":       {".zip", ".7z"},
    "neogeocd":     {".cue", ".bin", ".iso", ".chd"},
    "ngp":          {".ngp", ".zip", ".7z"},
    "ngpc":         {".ngc", ".ngpc", ".zip", ".7z"},
    # Arcade
    "mame":         {".zip", ".7z"},
    "fbneo":        {".zip", ".7z"},
    "fba":          {".zip", ".7z"},
    "fba_libretro": {".zip", ".7z"},
    "naomi":        {".zip", ".7z", ".dat", ".bin", ".lst"},
    "atomiswave":   {".zip", ".7z", ".bin", ".dat", ".lst"},
    # Computers
    "msx":          {".rom", ".mx1", ".mx2", ".dsk", ".cas", ".zip", ".7z"},
    "msx1":         {".rom", ".mx1", ".dsk", ".cas", ".zip", ".7z"},
    "msx2":         {".rom", ".mx2", ".dsk", ".cas", ".zip", ".7z"},
    "amstradcpc":   {".dsk", ".sna", ".tap", ".cdt", ".zip", ".7z"},
    "zxspectrum":   {".tzx", ".tap", ".z80", ".sna", ".szx", ".zip", ".7z"},
    "zx81":         {".p", ".tzx", ".zip", ".7z"},
    "c64":          {".d64", ".t64", ".prg", ".tap", ".crt", ".zip", ".7z"},
    "amiga":        {".adf", ".adz", ".dms", ".ipf", ".hdf", ".hdz", ".lha", ".zip", ".7z"},
    "amiga600":     {".adf", ".adz", ".dms", ".ipf", ".hdf", ".hdz", ".lha", ".zip", ".7z"},
    "amiga1200":    {".adf", ".adz", ".dms", ".ipf", ".hdf", ".hdz", ".lha", ".zip", ".7z"},
    "amigacd32":    {".iso", ".cue", ".bin", ".chd", ".lha"},
    "dos":          {".zip", ".7z", ".exe", ".com", ".bat", ".dosz"},
    "scummvm":      {".svm"},
    "pc88":         {".d88", ".zip", ".7z"},
    "pc98":         {".hdi", ".fdi", ".d88", ".zip", ".7z"},
    "x68000":       {".dim", ".hdf", ".2hd", ".zip", ".7z"},
    "thomson":      {".fd", ".sap", ".k7", ".m7", ".m5", ".zip"},
    # Misc
    "wonderswan":   {".ws", ".zip", ".7z"},
    "wonderswancolor": {".wsc", ".ws", ".zip", ".7z"},
    "vectrex":      {".vec", ".gam", ".bin", ".zip", ".7z"},
    "colecovision": {".col", ".bin", ".rom", ".zip", ".7z"},
    "intellivision":{".int", ".bin", ".rom", ".zip", ".7z"},
    "odyssey2":     {".bin", ".zip", ".7z"},
    "channelf":     {".bin", ".chf", ".zip", ".7z"},
    "lutro":        {".lua", ".lutro", ".zip", ".7z"},
    "cavestory":    {".zip"},
    "prboom":       {".wad"},
    "ports":        set(),  # anything goes
    "imageviewer":  {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tga", ".psd"},
}

# Reverse map: extension -> list of likely systems
EXTENSION_TO_SYSTEMS = defaultdict(set)
for sys_name, exts in SYSTEM_EXTENSIONS.items():
    for ext in exts:
        EXTENSION_TO_SYSTEMS[ext].add(sys_name)

# Extensions that are never ROMs — documentation, images, checksums bundled with ROM sets.
# Files with these extensions are silently skipped and never reported as issues.
IGNORED_EXTENSIONS = {
    ".txt", ".nfo", ".diz", ".sfv", ".url",  # readme / scene release files
    ".htm", ".html", ".pdf",                  # documentation
    ".jpg", ".jpeg", ".png", ".gif", ".bmp",  # box art / screenshots
    ".xml", ".backup", ".bak", ".log",        # EmulationStation / Recalbox system files
}

# Human-friendly system names
SYSTEM_DISPLAY_NAMES = {
    "nes": "Nintendo NES", "snes": "Super Nintendo", "n64": "Nintendo 64",
    "gb": "Game Boy", "gbc": "Game Boy Color", "gba": "Game Boy Advance",
    "nds": "Nintendo DS", "gamecube": "GameCube", "wii": "Nintendo Wii",
    "virtualboy": "Virtual Boy", "fds": "Famicom Disk System",
    "megadrive": "Sega Mega Drive / Genesis", "genesis": "Sega Genesis",
    "mastersystem": "Sega Master System", "gamegear": "Sega Game Gear",
    "sg1000": "Sega SG-1000", "sega32x": "Sega 32X",
    "segacd": "Sega CD", "saturn": "Sega Saturn", "dreamcast": "Sega Dreamcast",
    "psx": "Sony PlayStation", "psp": "Sony PSP",
    "atari2600": "Atari 2600", "atari5200": "Atari 5200", "atari7800": "Atari 7800",
    "atarijaguar": "Atari Jaguar", "atarilynx": "Atari Lynx", "atarist": "Atari ST",
    "pcengine": "PC Engine / TurboGrafx-16", "pcenginecd": "PC Engine CD",
    "supergrafx": "SuperGrafx", "neogeo": "Neo Geo", "neogeocd": "Neo Geo CD",
    "ngp": "Neo Geo Pocket", "ngpc": "Neo Geo Pocket Color",
    "mame": "MAME Arcade", "fbneo": "FBNeo Arcade", "fba": "FB Alpha Arcade",
    "naomi": "Sega NAOMI", "atomiswave": "Atomiswave",
    "msx": "MSX", "msx1": "MSX1", "msx2": "MSX2",
    "amstradcpc": "Amstrad CPC", "zxspectrum": "ZX Spectrum", "zx81": "ZX81",
    "c64": "Commodore 64", "amiga": "Amiga",
    "amiga600": "Amiga 600", "amiga1200": "Amiga 1200", "amigacd32": "Amiga CD32",
    "dos": "MS-DOS", "scummvm": "ScummVM",
    "wonderswan": "WonderSwan", "wonderswancolor": "WonderSwan Color",
    "vectrex": "Vectrex", "colecovision": "ColecoVision",
    "intellivision": "Intellivision", "odyssey2": "Odyssey 2",
    "prboom": "Doom (PrBoom)", "ports": "Ports",
    "pokemini": "Pokémon Mini", "satellaview": "Satellaview",
    "pc88": "NEC PC-88", "pc98": "NEC PC-98", "x68000": "Sharp X68000",
    "thomson": "Thomson", "channelf": "Fairchild Channel F",
    "lutro": "Lutro", "cavestory": "Cave Story",
}

# ─── ScreenScraper Integration ───────────────────────────────────────────────
# Maps Recalbox system folder names to ScreenScraper system IDs
SCREENSCRAPER_SYSTEM_IDS = {
    "nes": 18, "snes": 6, "n64": 14, "gb": 9, "gbc": 10, "gba": 12,
    "nds": 15, "gamecube": 13, "wii": 16, "megadrive": 1, "genesis": 1,
    "mastersystem": 2, "gamegear": 21, "sega32x": 19, "segacd": 20,
    "saturn": 22, "dreamcast": 23, "psx": 57, "psp": 61,
    "atari2600": 26, "atari5200": 40, "atari7800": 41, "atarilynx": 28,
    "atarijaguar": 29, "atarist": 42,
    "pcengine": 31, "pcenginecd": 4, "supergrafx": 105,
    "neogeo": 142, "neogeocd": 70, "ngp": 25, "ngpc": 82,
    "mame": 75, "fbneo": 75, "fba": 75, "naomi": 75, "atomiswave": 75,
    "msx": 60, "msx1": 60, "msx2": 60,
    "amstradcpc": 65, "zxspectrum": 76, "zx81": 77,
    "c64": 66, "amiga": 64, "amiga600": 64, "amiga1200": 64, "amigacd32": 130,
    "dos": 135, "scummvm": 123,
    "wonderswan": 45, "wonderswancolor": 46,
    "vectrex": 102, "colecovision": 48, "intellivision": 115,
    "sg1000": 24, "virtualboy": 11, "pokemini": 211,
    "pc88": 221, "pc98": 208, "x68000": 79,
}

# Maps Recalbox system folder names to Libretro Thumbnails CDN system directory names.
# Used as a no-auth fallback cover source: https://thumbnails.libretro.com/
LIBRETRO_SYSTEM_NAMES = {
    "nes":             "Nintendo - Nintendo Entertainment System",
    "snes":            "Nintendo - Super Nintendo Entertainment System",
    "n64":             "Nintendo - Nintendo 64",
    "gb":              "Nintendo - Game Boy",
    "gbc":             "Nintendo - Game Boy Color",
    "gba":             "Nintendo - Game Boy Advance",
    "nds":             "Nintendo - Nintendo DS",
    "gamecube":        "Nintendo - GameCube",
    "wii":             "Nintendo - Wii",
    "virtualboy":      "Nintendo - Virtual Boy",
    "fds":             "Nintendo - Family Computer Disk System",
    "pokemini":        "Nintendo - Pokemon Mini",
    "megadrive":       "Sega - Mega Drive - Genesis",
    "genesis":         "Sega - Mega Drive - Genesis",
    "mastersystem":    "Sega - Master System - Mark III",
    "gamegear":        "Sega - Game Gear",
    "sega32x":         "Sega - 32X",
    "segacd":          "Sega - Mega-CD - Sega CD",
    "saturn":          "Sega - Saturn",
    "dreamcast":       "Sega - Dreamcast",
    "sg1000":          "Sega - SG-1000",
    "psx":             "Sony - PlayStation",
    "psp":             "Sony - PlayStation Portable",
    "atari2600":       "Atari - 2600",
    "atari5200":       "Atari - 5200",
    "atari7800":       "Atari - 7800",
    "atarijaguar":     "Atari - Jaguar",
    "atarilynx":       "Atari - Lynx",
    "atarist":         "Atari - ST",
    "pcengine":        "NEC - PC Engine - TurboGrafx-16",
    "pcenginecd":      "NEC - PC Engine CD - TurboGrafx-CD",
    "supergrafx":      "NEC - PC Engine SuperGrafx",
    "neogeo":          "SNK - Neo-Geo",
    "neogeocd":        "SNK - Neo-Geo CD",
    "ngp":             "SNK - Neo Geo Pocket",
    "ngpc":            "SNK - Neo Geo Pocket Color",
    "mame":            "MAME",
    "fbneo":           "FBNeo - Arcade Games",
    "fba":             "FBNeo - Arcade Games",
    "amstradcpc":      "Amstrad - CPC",
    "zxspectrum":      "Sinclair - ZX Spectrum +3",
    "c64":             "Commodore - 64",
    "amiga":           "Commodore - Amiga",
    "amiga600":        "Commodore - Amiga",
    "amiga1200":       "Commodore - Amiga",
    "dos":             "DOS",
    "scummvm":         "ScummVM",
    "msx":             "Microsoft - MSX",
    "msx1":            "Microsoft - MSX",
    "msx2":            "Microsoft - MSX2",
    "x68000":          "Sharp - X68000",
    "pc88":            "NEC - PC-8801",
    "wonderswan":      "Bandai - WonderSwan",
    "wonderswancolor": "Bandai - WonderSwan Color",
    "vectrex":         "GCE - Vectrex",
    "colecovision":    "Coleco - ColecoVision",
    "intellivision":   "Mattel - Intellivision",
}


def _clean_rom_name(filename: str) -> str:
    """Strip extension and region/revision tags from a ROM filename for text search.

    "Aladdin (USA).zip"          → "Aladdin"
    "Super Mario Bros. (E).zip"  → "Super Mario Bros."
    "Sonic [!].zip"              → "Sonic"
    """
    stem = os.path.splitext(filename)[0]
    cleaned = re.split(r'[\(\[]', stem)[0]
    return cleaned.strip()


# Per-session ScreenScraper credentials.
# Priority: screenscraper.cfg > environment variables > empty (configure via UI)
def _load_ss_credentials():
    cfg_path = os.path.join(os.path.dirname(__file__), "screenscraper.cfg")
    cp = configparser.ConfigParser()
    if os.path.exists(cfg_path):
        try:
            cp.read(cfg_path, encoding="utf-8")
            return {
                "screenscraper_user": cp.get("screenscraper", "user", fallback="").strip(),
                "screenscraper_pass": cp.get("screenscraper", "pass", fallback="").strip(),
                "screenscraper_devid": cp.get("screenscraper", "devid", fallback="").strip(),
                "screenscraper_devpass": cp.get("screenscraper", "devpass", fallback="").strip(),
            }
        except configparser.Error:
            pass
    return {
        "screenscraper_user": os.environ.get("SS_USER", ""),
        "screenscraper_pass": os.environ.get("SS_PASS", ""),
        "screenscraper_devid": os.environ.get("SS_DEVID", ""),
        "screenscraper_devpass": os.environ.get("SS_DEVPASS", ""),
    }


ss_config = _load_ss_credentials()

# ─── BIOS Requirements ───────────────────────────────────────────────────────
# Maps system folder name to list of required/optional BIOS file descriptors.
# md5 is optional; if present, the file is hash-verified.
# in_roms=True means the BIOS lives inside the roms/<system>/ folder, not bios/.
BIOS_REQUIREMENTS = {
    "psx": [
        {"file": "scph1001.bin", "md5": "dc2b9bfbdef2696724abb246910b1438", "required": True, "desc": "BIOS v2.2 (USA)"},
        {"file": "scph5500.bin", "md5": "8dd7d5296a650fac7319bce665a6a53c", "required": False, "desc": "BIOS v3.0 (Japan)"},
        {"file": "scph5501.bin", "md5": "490f666e1afb15b7362b406ed1cea246", "required": False, "desc": "BIOS v3.0 (USA)"},
        {"file": "scph5502.bin", "md5": "32736f17079d0b2b7024407c39bd3050", "required": False, "desc": "BIOS v3.0 (Europe)"},
    ],
    "dreamcast": [
        {"file": "dc_boot.bin", "md5": "e10c53c2f8b90bab96ead2d368858623", "required": True, "desc": "Dreamcast BIOS"},
        {"file": "dc_flash.bin", "md5": "0a93f7940c455905bea6e392dfde92a4", "required": True, "desc": "Dreamcast Flash"},
    ],
    "gba": [
        {"file": "gba_bios.bin", "md5": "a860e8c0b6d573d191e4ec7db1b1e4f6", "required": False, "desc": "GBA BIOS (needed by gpSP)"},
    ],
    "segacd": [
        {"file": "bios_CD_U.bin", "md5": "2efd74e3232ff260e371b99f84024f7f", "required": True, "desc": "Sega CD BIOS (USA)"},
        {"file": "bios_CD_E.bin", "md5": "e66fa1dc5820d254611fdcdba0662372", "required": False, "desc": "Mega CD BIOS (Europe)"},
        {"file": "bios_CD_J.bin", "md5": "278a9397d192149e84e820ac621a8edd", "required": False, "desc": "Mega CD BIOS (Japan)"},
    ],
    "saturn": [
        {"file": "sega_101.bin", "md5": "224b8048a88c5467a383c6b83babda93", "required": True, "desc": "Saturn BIOS (Japan)"},
        {"file": "mpr-17933.bin", "md5": "3240872c70984b6cbfda1586cab68dbe", "required": False, "desc": "Saturn BIOS (USA/Europe)"},
    ],
    "neogeo": [
        {"file": "neogeo.zip", "required": True, "in_roms": True, "desc": "Neo Geo BIOS (must be in roms/neogeo/)"},
    ],
    "fds": [
        {"file": "disksys.rom", "md5": "ca30b50f880eb660a320674ed365ef7a", "required": True, "desc": "Famicom Disk System BIOS"},
    ],
    "pcenginecd": [
        {"file": "syscard3.pce", "md5": "ff1a674273fe3540ccef576376407d1d", "required": True, "desc": "PC Engine CD BIOS v3.0"},
    ],
    "neogeocd": [
        {"file": "neocd.bin", "required": True, "desc": "Neo Geo CD BIOS"},
    ],
    "amigacd32": [
        {"file": "kick40060.CD32", "required": True, "desc": "Amiga CD32 Kickstart 3.1"},
        {"file": "kick40060.CD32.ext", "required": True, "desc": "Amiga CD32 Extended ROM"},
    ],
    "3do": [
        {"file": "panafz10.bin", "md5": "51f2f43ae2f3508a14d9f56597e2d3ce", "required": True, "desc": "3DO BIOS (Panasonic FZ-10)"},
    ],
    "msx": [
        {"file": "MSX.ROM", "required": True, "desc": "MSX BIOS"},
        {"file": "MSX2.ROM", "required": False, "desc": "MSX2 BIOS"},
    ],
    "msx2": [
        {"file": "MSX2.ROM", "required": True, "desc": "MSX2 BIOS"},
        {"file": "MSX2EXT.ROM", "required": True, "desc": "MSX2 Extended BIOS"},
    ],
}

# ─── Diagnostic Solutions Knowledge Base ─────────────────────────────────────
# Maps diagnostic key -> human-readable guidance shown in the UI.
DIAGNOSTIC_SOLUTIONS = {
    "missing_cue": {
        "title": "Missing CUE file",
        "description": "CD-ROM games need a .cue file describing the disc track layout. Without it the emulator cannot read the disc.",
        "steps": [
            "Create a text file named exactly like the .bin but with .cue extension (same folder).",
            "Minimal single-track content:\n  FILE \"<game>.bin\" BINARY\n    TRACK 01 MODE2/2352\n      INDEX 01 00:00:00",
            "For multi-track games (audio CD) you need one TRACK line per track. Download matching .cue from redump.org or use a CUE generator.",
        ],
        "search_query": "create cue file for bin recalbox",
    },
    "missing_m3u": {
        "title": "Multi-disc game needs .m3u playlist",
        "description": "Games spread across multiple discs require an .m3u playlist so the emulator knows the disc order.",
        "steps": [
            "Create a plain-text file named after the game with .m3u extension in the same system folder.",
            "Each line should be one disc filename (e.g. 'Game (Disc 1).cue'). Use Unix line endings (LF).",
            "Recalbox will only show the .m3u in the game list — the individual disc files are hidden.",
        ],
        "search_query": "recalbox m3u multi disc playlist setup",
    },
    "broken_m3u": {
        "title": "M3U playlist references missing file(s)",
        "description": "The .m3u playlist file lists disc files that do not exist in the same folder.",
        "steps": [
            "Open the .m3u file in a text editor and check each line.",
            "Ensure every referenced disc file (e.g. .cue, .chd, .bin) is present in the same folder.",
            "Fix any typos, wrong paths, or Windows vs Unix path separator issues (use plain filenames, no folder prefix).",
        ],
        "search_query": "recalbox m3u playlist broken missing disc",
    },
    "missing_bios": {
        "title": "Required BIOS file missing",
        "description": "This system requires a BIOS ROM to boot. Without it the emulator will crash or show a black screen.",
        "steps": [
            "Check the BIOS tab for the exact filename and MD5 hash required.",
            "Place the BIOS file in \\\\\\\\RECALBOX\\\\share\\\\bios\\\\ (or roms/neogeo/ for Neo Geo).",
            "BIOS filenames are case-sensitive on Linux. Verify the exact casing matches.",
        ],
        "search_query": "recalbox bios setup required files",
    },
    "wrong_bios_md5": {
        "title": "BIOS file present but wrong version/region",
        "description": "The BIOS file exists but its MD5 hash does not match the expected value. It may be the wrong region or a bad dump.",
        "steps": [
            "Verify the MD5 of your BIOS file using a tool like CertUtil (Windows) or md5sum (Linux).",
            "Replace the file with a version matching the expected MD5 shown in the BIOS tab.",
            "Common issue: mixing regional variants (USA vs Japan vs Europe). Make sure region matches your ROMs.",
        ],
        "search_query": "recalbox bios md5 wrong version region",
    },
    "corrupt_archive": {
        "title": "ZIP/7z archive is corrupt or unreadable",
        "description": "The archive file fails integrity checks. The emulator will not be able to extract and load the ROM.",
        "steps": [
            "Try extracting the archive on your PC to confirm it is readable.",
            "Re-download the ROM from a reliable source.",
            "If the file seems fine, check if Recalbox supports .7z for this system — some cores require .zip.",
        ],
        "search_query": "recalbox corrupt zip rom fix",
    },
    "likely_overdump": {
        "title": "ROM appears to be an overdump",
        "description": "The file ends with a large block of repeated 0xFF or 0x00 bytes, which is the hallmark of a bad dump with padding.",
        "steps": [
            "The ROM may still work — some emulators handle overdumps gracefully.",
            "If it does not load, try to find a 'No-Intro' verified clean dump of the same game.",
            "You can trim the padding manually using a hex editor, but a clean re-download is safer.",
        ],
        "search_query": "rom overdump bad dump fix no-intro",
    },
    "empty_file": {
        "title": "File is empty or too small",
        "description": "The ROM file is 0 bytes or smaller than a valid ROM could ever be. It is almost certainly a corrupt or incomplete download.",
        "steps": [
            "Delete the file and re-download from a reliable source.",
            "Check disk space on the Recalbox share — a full disk can cause zero-byte files.",
        ],
        "search_query": "rom empty file corrupt download fix",
    },
    "wrong_zip_contents": {
        "title": "ZIP contains files for wrong system",
        "description": (
            "The archive container (.zip/.7z) is accepted here, but the files inside "
            "belong to a different system. The emulator opens the archive and finds nothing it can use."
        ),
        "steps": [
            "Open the archive on your PC to see what files are inside.",
            "If the inner files belong to a different system, move this archive to that system's folder.",
            "MAME/arcade ROM zips belong in roms/mame or roms/fbneo — not in a console folder.",
            "If the inner files match no known system, this may be a mislabelled download.",
        ],
        "search_query": "recalbox rom wrong system zip contents",
    },
    "smc_copier_header": {
        "title": "SNES ROM has legacy copier header",
        "description": (
            "This .smc file contains a 512-byte copier header added by old backup hardware. "
            "Many libretro SNES cores reject it, causing a black screen or crash on load."
        ),
        "steps": [
            "Rename the file from .smc to .sfc — some cores auto-detect and skip the header.",
            "If renaming does not fix it, strip the header using: dd if=game.smc of=game.sfc bs=512 skip=1",
            "Alternatively, find a clean No-Intro dump (.sfc) which never contains copier headers.",
        ],
        "search_query": "snes smc copier header strip recalbox",
    },
    "invalid_nes_header": {
        "title": "NES ROM has invalid iNES header",
        "description": (
            "This .nes file does not start with the expected iNES magic bytes (NES\\x1a). "
            "It may be a corrupt download, a renamed non-NES file, or a legacy bad dump."
        ),
        "steps": [
            "Re-download the ROM from a No-Intro verified source.",
            "Verify the file is actually a NES ROM and not a file with a renamed extension.",
            "If you have a hex editor, check that the first 4 bytes are: 4E 45 53 1A",
        ],
        "search_query": "nes ines header invalid bad dump no-intro",
    },
    "n64_non_canonical": {
        "title": "N64 ROM is in non-canonical byte order",
        "description": (
            "This file uses a byte-swapped (.v64) or little-endian (.n64) format. "
            "The canonical N64 format is big-endian (.z64). While Mupen64Plus-Next handles "
            "runtime conversion, some Recalbox cores may fail or perform slower with these formats."
        ),
        "steps": [
            "Convert to .z64 (big-endian) using Tool64 or a similar N64 ROM conversion utility.",
            "Rename the output file to .z64 after conversion.",
            "If the game works fine as-is, no action is required — this is an advisory warning.",
        ],
        "search_query": "n64 v64 z64 byte swap convert tool64",
    },
}

# CD-based systems that require .cue files alongside .bin
CD_SYSTEMS = {"psx", "segacd", "saturn", "dreamcast", "pcenginecd", "neogeocd", "amigacd32"}

# Systems where .zip/.7z IS the ROM format — inner content cannot be validated
ARCHIVE_ONLY_SYSTEMS = {
    "mame", "fbneo", "fba", "fba_libretro", "neogeo",
    "naomi", "atomiswave", "dos", "cavestory", "ports",
}

_CONTAINER_EXTS = {".zip", ".7z"}

# ─── Derived Lookups ──────────────────────────────────────────────────────────
# Frozenset of all valid system folder names — used for input validation.
VALID_SYSTEMS: frozenset[str] = frozenset(SYSTEM_EXTENSIONS.keys())

# ─── Internal Constants ───────────────────────────────────────────────────────
_LARGE_FILE_THRESHOLD = 500_000_000  # 500 MB — skip hash for duplicate detection above this size
_HASH_BLOCK_SIZE = 65_536            # 64 KB block used for quick (non-cryptographic) MD5

# ─── Scan Cache ───────────────────────────────────────────────────────────────
scan_cache = {
    "last_scan": None,
    "systems": {},
    "issues": [],
    "duplicates": [],
    "stats": {},
    "gamelists": {},
}


def get_file_hash(filepath: str, block_size: int = _HASH_BLOCK_SIZE) -> str | None:
    """Return MD5 hex digest of the first *block_size* bytes for quick duplicate detection.

    Only hashes one block — not a full-file hash. Returns None if the file cannot be read.
    """
    try:
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            buf = f.read(block_size)
            h.update(buf)
        return h.hexdigest()
    except (OSError, IOError):
        return None


def check_bios_status() -> dict:
    """Check which BIOS files are present/missing/wrong for all systems in BIOS_REQUIREMENTS."""
    result = {}
    for system, entries in BIOS_REQUIREMENTS.items():
        system_status = []
        for entry in entries:
            fname = entry["file"]
            required = entry.get("required", True)
            in_roms = entry.get("in_roms", False)

            if in_roms:
                fpath = os.path.join(_roms_root(), system, fname)
            else:
                fpath = os.path.join(_bios_root(), fname)

            actual_name = None  # set when wrong_case is detected
            if not os.path.exists(fpath):
                # Check for a case-insensitive match — BIOS filenames are case-sensitive on
                # the Pi (Linux ext4) but Windows SMB access is case-insensitive, so a file
                # named SCPH1001.BIN will be found by os.path.exists() on Windows but fail
                # to load on Recalbox.
                status = "missing"
                bios_dir = os.path.dirname(fpath)
                fname_lower = fname.lower()
                try:
                    for entry_fs in os.scandir(bios_dir):
                        if entry_fs.name.lower() == fname_lower and entry_fs.name != fname:
                            status = "wrong_case"
                            actual_name = entry_fs.name
                            break
                except OSError:
                    pass
            elif "md5" in entry:
                try:
                    actual_md5 = get_bios_md5(fpath)
                    status = "ok" if actual_md5 == entry["md5"] else "wrong_version"
                except (OSError, IOError):
                    status = "unreadable"
            else:
                status = "ok"

            bios_entry: dict = {
                "file": fname,
                "required": required,
                "status": status,
                "desc": entry.get("desc", ""),
                "expected_md5": entry.get("md5"),
                "path": fpath,
            }
            if actual_name is not None:
                bios_entry["actual_name"] = actual_name
            system_status.append(bios_entry)
        result[system] = {
            "display_name": SYSTEM_DISPLAY_NAMES.get(system, system),
            "bios_files": system_status,
            "all_required_present": all(
                f["status"] == "ok" for f in system_status if f["required"]
            ),
        }
    return result


def get_bios_md5(filepath: str) -> str:
    """Return MD5 hex digest of an entire file. Used for BIOS verification (files are small)."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_BLOCK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def get_core_extensions(system_key: str) -> set[str]:
    """Non-archive extensions valid for this system (what should be INSIDE a zip)."""
    if system_key in ARCHIVE_ONLY_SYSTEMS:
        return set()
    return SYSTEM_EXTENSIONS.get(system_key, set()) - _CONTAINER_EXTS


def _list_archive_contents(path: str, ext: str) -> list[str] | None:
    """Return list of filenames inside a .zip or .7z archive.

    Returns None if the archive is unreadable, unsupported, or py7zr is unavailable.
    """
    try:
        if ext == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                return zf.namelist()
        elif ext == ".7z":
            if not PY7ZR_AVAILABLE:
                return None
            with py7zr.SevenZipFile(path, mode="r") as sz:
                return sz.getnames()
    except (OSError, IOError, zipfile.BadZipFile, Exception):
        return None


def run_rom_diagnostics(system_key: str, system_path: str, roms: list[dict]) -> list[dict]:
    """
    Analyse files in a system folder and return a list of diagnostic issues.
    Each issue: {key, file, solution_title, description}
    Also augments each rom_info dict in-place with a 'diagnostics' list.
    """
    diag_issues = []

    # Build a set of filenames present in this folder for fast lookup
    try:
        all_names = {e.name for e in os.scandir(system_path) if e.is_file()}
    except OSError:
        return diag_issues

    # Index roms by name for quick in-place augmentation
    rom_map = {r["name"]: r for r in roms}
    for r in roms:
        r.setdefault("diagnostics", [])

    is_cd_system = system_key in CD_SYSTEMS

    # --- Check 1: .bin without matching .cue (CD systems only) ---
    if is_cd_system:
        bin_files = [n for n in all_names if n.lower().endswith(".bin")]
        cue_stems = {os.path.splitext(n)[0].lower() for n in all_names if n.lower().endswith(".cue")}
        for bf in bin_files:
            stem = os.path.splitext(bf)[0].lower()
            if stem not in cue_stems:
                diag = {
                    "key": "missing_cue",
                    "file": bf,
                    "system": system_key,
                    **{k: DIAGNOSTIC_SOLUTIONS["missing_cue"][k] for k in ("title", "description")},
                }
                diag_issues.append(diag)
                if bf in rom_map:
                    rom_map[bf]["diagnostics"].append("missing_cue")

    # --- Check 2: Multi-disc .cue/.chd files without .m3u ---
    if is_cd_system:
        disc_pattern = re.compile(r'\(disc\s*\d+\)', re.IGNORECASE)  # noqa: W605
        disc_files = [n for n in all_names if disc_pattern.search(n)
                      and os.path.splitext(n)[1].lower() in {".cue", ".chd", ".cdi", ".bin"}]
        m3u_files = {os.path.splitext(n)[0].lower() for n in all_names if n.lower().endswith(".m3u")}
        # Group by game base name (strip disc number)
        game_groups = defaultdict(list)
        for df in disc_files:
            base = disc_pattern.sub("", os.path.splitext(df)[0]).strip().lower()
            game_groups[base].append(df)
        for base, discs in game_groups.items():
            if len(discs) > 1 and base not in m3u_files:
                representative = sorted(discs)[0]
                diag = {
                    "key": "missing_m3u",
                    "file": representative,
                    "system": system_key,
                    "related_files": discs,
                    **{k: DIAGNOSTIC_SOLUTIONS["missing_m3u"][k] for k in ("title", "description")},
                }
                diag_issues.append(diag)
                for df in discs:
                    if df in rom_map:
                        rom_map[df]["diagnostics"].append("missing_m3u")

    # --- Check 3: Broken .m3u (references missing files) ---
    for mname in all_names:
        if not mname.lower().endswith(".m3u"):
            continue
        mpath = os.path.join(system_path, mname)
        try:
            with open(mpath, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            missing_refs = [l for l in lines if not os.path.exists(os.path.join(system_path, l))]
            if missing_refs:
                diag = {
                    "key": "broken_m3u",
                    "file": mname,
                    "system": system_key,
                    "missing_refs": missing_refs,
                    **{k: DIAGNOSTIC_SOLUTIONS["broken_m3u"][k] for k in ("title", "description")},
                }
                diag_issues.append(diag)
                if mname in rom_map:
                    rom_map[mname]["diagnostics"].append("broken_m3u")
        except OSError:
            pass

    # --- Check 4: Empty or tiny files ---
    for rom in roms:
        if rom["size"] < 512 and rom["ext"] not in {".m3u", ".svm"}:
            diag = {
                "key": "empty_file",
                "file": rom["name"],
                "system": system_key,
                **{k: DIAGNOSTIC_SOLUTIONS["empty_file"][k] for k in ("title", "description")},
            }
            diag_issues.append(diag)
            rom["diagnostics"].append("empty_file")

    # --- Check 5: Likely overdump (last 512 bytes all 0xFF or 0x00) ---
    # Skip systems where 0xFF tail padding is normal: N64 and GBA cartridges use erased-flash
    # (0xFF) to fill unused ROM address space, so clean verified dumps commonly end with 0xFF.
    _overdump_skip_systems = {"n64", "gba"}
    if system_key not in _overdump_skip_systems:
        for rom in roms:
            if rom["size"] < 65536:
                continue  # too small to meaningfully sample
            if rom["ext"] in {".zip", ".7z", ".cue", ".m3u", ".chd", ".iso", ".pbp"}:
                continue  # compressed/metadata formats
            try:
                fpath = rom["path"]
                with open(fpath, "rb") as f:
                    f.seek(-512, 2)
                    tail = f.read(512)
                if tail and (tail == bytes([tail[0]]) * len(tail)) and tail[0] in (0x00, 0xFF):
                    diag = {
                        "key": "likely_overdump",
                        "file": rom["name"],
                        "system": system_key,
                        **{k: DIAGNOSTIC_SOLUTIONS["likely_overdump"][k] for k in ("title", "description")},
                    }
                    diag_issues.append(diag)
                    rom["diagnostics"].append("likely_overdump")
            except OSError:
                pass

    # --- Check 6: Corrupt ZIP archives ---
    for rom in roms:
        if rom["ext"] not in {".zip"}:
            continue
        try:
            if not zipfile.is_zipfile(rom["path"]):
                diag = {
                    "key": "corrupt_archive",
                    "file": rom["name"],
                    "system": system_key,
                    **{k: DIAGNOSTIC_SOLUTIONS["corrupt_archive"][k] for k in ("title", "description")},
                }
                diag_issues.append(diag)
                rom["diagnostics"].append("corrupt_archive")
        except OSError:
            pass

    # --- Check 7: ZIP/7z content inspection ---
    core_exts = get_core_extensions(system_key)
    if core_exts:  # skip MAME/neogeo/archive-only systems
        for rom in roms:
            if rom["ext"] not in {".zip", ".7z"}:
                continue
            if "corrupt_archive" in rom.get("diagnostics", []):
                continue  # already flagged broken — skip

            inner_names = _list_archive_contents(rom["path"], rom["ext"])
            if inner_names is None:
                continue

            inner_exts = {
                os.path.splitext(n)[1].lower()
                for n in inner_names
                if os.path.splitext(n)[1]  # skip files with no extension
            }
            if not inner_exts:
                continue

            if inner_exts & core_exts:
                continue  # at least one inner file looks right — OK

            # None match — identify target system(s)
            suggested = set()
            for iext in inner_exts:
                suggested |= EXTENSION_TO_SYSTEMS.get(iext, set())
            suggested.discard(system_key)
            # Remove archive-only systems — .zip inner extension would otherwise map to every
            # system that accepts .zip, polluting suggestions with mame/fbneo/neogeo/etc.
            suggested -= ARCHIVE_ONLY_SYSTEMS

            # Fallback: opaque internals = almost certainly a MAME/arcade romset
            if not suggested:
                suggested_list = ["mame", "fbneo"]
            else:
                suggested_list = sorted(suggested)

            diag = {
                "key": "wrong_zip_contents",
                "file": rom["name"],
                "system": system_key,
                "inner_extensions": sorted(inner_exts),
                "suggested_systems": suggested_list,
                **{k: DIAGNOSTIC_SOLUTIONS["wrong_zip_contents"][k] for k in ("title", "description")},
            }
            diag_issues.append(diag)
            rom["diagnostics"].append("wrong_zip_contents")

    # --- Check 8: SNES .smc copier header ---
    # Unheadered SNES ROMs are exact multiples of 1 KB. A 512-byte legacy copier header
    # (added by old backup hardware like the Super Wild Card) makes file_size % 1024 == 512.
    # Many libretro SNES cores reject such files with a black screen or load failure.
    if system_key in {"snes", "satellaview", "sufami"}:
        for rom in roms:
            if rom["ext"] == ".smc" and rom["size"] > 512 and rom["size"] % 1024 == 512:
                diag = {
                    "key": "smc_copier_header",
                    "file": rom["name"],
                    "system": system_key,
                    **{k: DIAGNOSTIC_SOLUTIONS["smc_copier_header"][k] for k in ("title", "description")},
                }
                diag_issues.append(diag)
                rom["diagnostics"].append("smc_copier_header")

    # --- Check 9: NES iNES magic number ---
    # Valid NES ROMs always begin with the iNES magic: 0x4E 0x45 0x53 0x1A ("NES\x1a").
    # A .nes file without this signature is a corrupt download, a renamed non-NES file,
    # or a legacy bad dump with a "DiskDude!" header corruption.
    if system_key in {"nes", "fds"}:
        for rom in roms:
            if rom["ext"] != ".nes" or rom["size"] < 16:
                continue
            if "empty_file" in rom.get("diagnostics", []):
                continue  # already flagged
            try:
                with open(rom["path"], "rb") as f:
                    magic = f.read(4)
                if magic != b"NES\x1a":
                    diag = {
                        "key": "invalid_nes_header",
                        "file": rom["name"],
                        "system": system_key,
                        **{k: DIAGNOSTIC_SOLUTIONS["invalid_nes_header"][k] for k in ("title", "description")},
                    }
                    diag_issues.append(diag)
                    rom["diagnostics"].append("invalid_nes_header")
            except OSError:
                pass

    # --- Check 10: N64 non-canonical byte order ---
    # The canonical N64 format is big-endian (.z64). Byte-swapped (.v64) and little-endian
    # (.n64) dumps work in Mupen64Plus-Next via runtime conversion, but some Recalbox cores
    # may fail or perform slower. This is an advisory warning, not an error.
    if system_key == "n64":
        for rom in roms:
            if rom["ext"] in {".v64", ".n64"}:
                diag = {
                    "key": "n64_non_canonical",
                    "file": rom["name"],
                    "system": system_key,
                    "format": rom["ext"],
                    **{k: DIAGNOSTIC_SOLUTIONS["n64_non_canonical"][k] for k in ("title", "description")},
                }
                diag_issues.append(diag)
                rom["diagnostics"].append("n64_non_canonical")

    return diag_issues


def parse_gamelist(system_dir: str) -> dict:
    """
    Parse <_roms_root()>/<system_dir>/gamelist.xml and return a dict keyed by
    lowercased filename stem -> {path, name, image, image_exists, thumbnail, desc}.
    Returns {} if file is absent or unreadable — never raises.
    """
    xml_path = os.path.join(_roms_root(), system_dir, "gamelist.xml")
    result = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for game in root.findall("game"):
            path_el = game.find("path")
            if path_el is None or not path_el.text:
                continue
            # <path> is like ./game.smc — extract basename
            raw_path = path_el.text.lstrip("./").lstrip("\\")
            basename = os.path.basename(raw_path.replace("\\", "/"))
            stem = os.path.splitext(basename)[0].lower()

            image_el = game.find("image")
            image_rel = image_el.text if image_el is not None and image_el.text else None
            thumbnail_el = game.find("thumbnail")
            thumbnail_rel = thumbnail_el.text if thumbnail_el is not None and thumbnail_el.text else None
            name_el = game.find("name")
            game_name = name_el.text if name_el is not None and name_el.text else ""
            desc_el = game.find("desc")
            game_desc = desc_el.text if desc_el is not None and desc_el.text else ""

            # Resolve image path relative to the system folder (strip leading ./)
            image_exists = False
            if image_rel:
                image_clean = image_rel.lstrip("./").lstrip("\\").replace("/", os.sep)
                image_abs = os.path.join(_roms_root(), system_dir, image_clean)
                image_exists = os.path.exists(image_abs)
            else:
                image_abs = None

            result[stem] = {
                "path": basename,
                "name": game_name,
                "image": image_rel,
                "image_abs": image_abs,
                "image_exists": image_exists,
                "thumbnail": thumbnail_rel,
                "desc": game_desc,
            }
    except (ET.ParseError, OSError):
        pass
    return result


def _cover_url_for(system_dir, image_rel):
    """Build a /api/covers/image/... URL from a gamelist <image> relative path."""
    if not image_rel:
        return None
    # image_rel is like ./media/images/game.png — get just the filename
    img_basename = os.path.basename(image_rel.replace("\\", "/"))
    return f"/api/covers/image/{urllib.parse.quote(system_dir, safe='')}/{urllib.parse.quote(img_basename, safe='')}"


def scan_roms() -> dict:
    """Scan all ROM directories and build inventory. Returns the updated scan_cache dict."""
    logger.info(f"Starting ROM scan at {_roms_root()}")
    systems = {}
    issues = []
    all_hashes = defaultdict(list)  # hash -> list of (system, filename)
    total_files = 0
    total_size = 0

    if not os.path.exists(_roms_root()):
        logger.error(f"ROMs root not found: {_roms_root()}")
        return {"error": f"Cannot access {_roms_root()}. Is the Recalbox on and network share accessible?"}

    try:
        system_dirs = sorted([
            d for d in os.listdir(_roms_root())
            if os.path.isdir(os.path.join(_roms_root(), d)) and not d.startswith(".")
        ])
    except PermissionError:
        return {"error": f"Permission denied accessing {_roms_root()}"}

    for system_dir in system_dirs:
        system_path = os.path.join(_roms_root(), system_dir)
        system_key = system_dir.lower()
        known_system = system_key in SYSTEM_EXTENSIONS
        valid_exts = SYSTEM_EXTENSIONS.get(system_key, set())

        roms = []
        misplaced = []
        unknown_ext = []
        ignored_count = 0

        # Load gamelist.xml once per system for cover/metadata lookups
        gamelist = parse_gamelist(system_dir)
        scan_cache["gamelists"][system_dir] = gamelist

        try:
            for entry in os.scandir(system_path):
                if entry.is_file() and not entry.name.startswith("."):
                    ext = os.path.splitext(entry.name)[1].lower()

                    if ext in IGNORED_EXTENSIONS:
                        ignored_count += 1
                        continue

                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0

                    total_files += 1
                    total_size += size

                    # Detect suggested systems for this extension
                    suggested = list(EXTENSION_TO_SYSTEMS.get(ext, set()) - {system_key})

                    # Look up gamelist entry for cover/metadata
                    stem = os.path.splitext(entry.name)[0].lower()
                    gl_entry = gamelist.get(stem)

                    rom_info = {
                        "name": entry.name,
                        "ext": ext,
                        "size": size,
                        "size_human": format_size(size),
                        "path": entry.path,
                        "system": system_dir,
                        "game_name": gl_entry["name"] if gl_entry else "",
                        "has_metadata": bool(gl_entry),
                        "has_cover": gl_entry["image_exists"] if gl_entry else False,
                        "cover_url": _cover_url_for(system_dir, gl_entry["image"]) if gl_entry and gl_entry.get("image_exists") else None,
                        "has_description": bool(gl_entry and gl_entry.get("desc")),
                    }

                    # Check if file belongs here
                    if not known_system:
                        rom_info["issue"] = "unknown_system"
                        rom_info["suggested_systems"] = suggested
                        unknown_ext.append(rom_info)
                        issues.append({
                            "type": "unknown_system",
                            "file": entry.name,
                            "current_system": system_dir,
                            "ext": ext,
                            "size_human": format_size(size),
                        })
                    elif valid_exts and ext not in valid_exts:
                        rom_info["issue"] = "wrong_system"
                        rom_info["suggested_systems"] = suggested
                        misplaced.append(rom_info)
                        issues.append({
                            "type": "misplaced",
                            "file": entry.name,
                            "current_system": system_dir,
                            "suggested_systems": suggested,
                            "ext": ext,
                            "size_human": format_size(size),
                        })
                    else:
                        rom_info["issue"] = None

                    roms.append(rom_info)

                    # Hash for duplicate detection (skip very large files)
                    if size < _LARGE_FILE_THRESHOLD:
                        fhash = get_file_hash(entry.path)
                        if fhash:
                            all_hashes[fhash].append((system_dir, entry.name, size))

        except PermissionError:
            issues.append({"type": "permission_error", "system": system_dir})
            continue

        # Run per-system ROM diagnostics (augments roms in-place)
        diag_issues = run_rom_diagnostics(system_key, system_path, roms)
        diag_count = len(diag_issues)

        cover_count = sum(1 for r in roms if r.get("has_cover"))
        description_count = sum(1 for r in roms if r.get("has_description"))
        systems[system_dir] = {
            "name": SYSTEM_DISPLAY_NAMES.get(system_key, system_dir),
            "folder": system_dir,
            "known": known_system,
            "total_roms": len(roms),
            "misplaced_count": len(misplaced),
            "unknown_count": len(unknown_ext),
            "ignored_count": ignored_count,
            "ok_count": len(roms) - len(misplaced) - len(unknown_ext),
            "diagnostic_count": diag_count,
            "cover_count": cover_count,
            "description_count": description_count,
            "roms": roms,
            "valid_extensions": sorted(valid_exts) if valid_exts else [],
            "diagnostic_issues": diag_issues,
        }

    # Find duplicates
    duplicates = []
    for fhash, locations in all_hashes.items():
        if len(locations) > 1:
            duplicates.append({
                "hash": fhash,
                "copies": [{"system": s, "file": f, "size_human": format_size(sz)} for s, f, sz in locations],
            })
            issues.append({
                "type": "duplicate",
                "hash": fhash,
                "copies": [{"system": s, "file": f} for s, f, sz in locations],
            })

    total_diagnostics = sum(s["diagnostic_count"] for s in systems.values())
    total_with_covers = sum(s["cover_count"] for s in systems.values())
    total_missing_covers = sum(
        sum(1 for r in s["roms"] if not r.get("has_cover") and r.get("issue") is None)
        for s in systems.values()
    )
    total_with_descriptions = sum(s["description_count"] for s in systems.values())
    total_missing_descriptions = sum(
        sum(1 for r in s["roms"] if not r.get("has_description") and r.get("issue") is None)
        for s in systems.values()
    )

    stats = {
        "total_systems": len(systems),
        "total_files": total_files,
        "total_size": format_size(total_size),
        "total_misplaced": sum(s["misplaced_count"] for s in systems.values()),
        "total_duplicates": len(duplicates),
        "total_issues": len(issues),
        "total_ignored": sum(s["ignored_count"] for s in systems.values()),
        "total_diagnostics": total_diagnostics,
        "total_with_covers": total_with_covers,
        "total_missing_covers": total_missing_covers,
        "total_with_descriptions": total_with_descriptions,
        "total_missing_descriptions": total_missing_descriptions,
    }

    scan_cache.update({
        "last_scan": datetime.now().isoformat(),
        "systems": systems,
        "issues": issues,
        "duplicates": duplicates,
        "stats": stats,
    })

    logger.info(
        f"Scan complete: {stats['total_files']} files across {stats['total_systems']} systems, "
        f"{stats['total_issues']} issues, {total_diagnostics} diagnostic findings"
    )
    return scan_cache


def format_size(size_bytes: float) -> str:
    """Format a byte count as a human-readable string (e.g. '4.2 MB')."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# ─── API Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    """Return current configuration."""
    return jsonify({
        "version": APP_VERSION,
        "roms_root": _roms_root(),
        "share_path": _config["share"],
        "accessible": os.path.exists(_roms_root()),
        "screenscraper_user": ss_config.get("screenscraper_user", ""),
        "screenscraper_devid": ss_config.get("screenscraper_devid", ""),
        "screenscraper_configured": bool(
            ss_config.get("screenscraper_user") and ss_config.get("screenscraper_pass")
            and ss_config.get("screenscraper_devid") and ss_config.get("screenscraper_devpass")
        ),
    })


def _save_ss_credentials():
    """Persist current ss_config credentials to screenscraper.cfg."""
    cfg_path = os.path.join(os.path.dirname(__file__), "screenscraper.cfg")
    # Read existing file to preserve comments/keys we don't manage
    cp = configparser.ConfigParser()
    if os.path.exists(cfg_path):
        try:
            cp.read(cfg_path, encoding="utf-8")
        except configparser.Error:
            pass
    if not cp.has_section("screenscraper"):
        cp.add_section("screenscraper")
    cp.set("screenscraper", "user", ss_config.get("screenscraper_user", ""))
    cp.set("screenscraper", "pass", ss_config.get("screenscraper_pass", ""))
    cp.set("screenscraper", "devid", ss_config.get("screenscraper_devid", ""))
    cp.set("screenscraper", "devpass", ss_config.get("screenscraper_devpass", ""))
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            cp.write(f)
    except OSError as e:
        logger.warning(f"Could not save screenscraper.cfg: {e}")


@app.route("/api/config", methods=["POST"])
def set_config():
    """Update the share path and/or ScreenScraper credentials."""
    data = request.get_json(silent=True) or {}
    if "share_path" in data:
        _config["share"] = data["share_path"]
    ss_changed = False
    for key in ("screenscraper_user", "screenscraper_pass", "screenscraper_devid", "screenscraper_devpass"):
        if key in data:
            ss_config[key] = data[key]
            ss_changed = True
    if ss_changed:
        _save_ss_credentials()
    return jsonify({
        "ok": True,
        "roms_root": _roms_root(),
        "accessible": os.path.exists(_roms_root()),
        "screenscraper_configured": bool(ss_config["screenscraper_user"] and ss_config["screenscraper_pass"]),
    })


@app.route("/api/scan", methods=["POST"])
def trigger_scan():
    """Trigger a full ROM scan."""
    result = scan_roms()
    if "error" in result:
        return jsonify(result), 500
    return jsonify({"ok": True, "stats": scan_cache["stats"], "last_scan": scan_cache["last_scan"]})


@app.route("/api/status")
def status():
    """Return scan status and stats."""
    return jsonify({
        "last_scan": scan_cache["last_scan"],
        "stats": scan_cache.get("stats") or None,
    })


@app.route("/api/systems")
def list_systems():
    """List all scanned systems with summary info (no ROM lists)."""
    summaries = {}
    for key, sys_info in scan_cache.get("systems", {}).items():
        summaries[key] = {k: v for k, v in sys_info.items() if k != "roms"}
    return jsonify(summaries)


@app.route("/api/systems/<system_name>")
def get_system(system_name):
    """Get full details for a system including ROM list."""
    sys_info = scan_cache.get("systems", {}).get(system_name)
    if not sys_info:
        return jsonify({"error": "System not found"}), 404
    return jsonify(sys_info)


@app.route("/api/issues")
def list_issues():
    """List all detected issues."""
    issue_type = request.args.get("type")
    issues = scan_cache.get("issues", [])
    if issue_type:
        issues = [i for i in issues if i["type"] == issue_type]
    return jsonify(issues)


@app.route("/api/duplicates")
def list_duplicates():
    """List duplicate ROMs."""
    return jsonify(scan_cache.get("duplicates", []))


@app.route("/api/move", methods=["POST"])
def move_rom():
    """Move a ROM file from one system folder to another.

    Request body: {from_system, to_system, filename}
    Both system names must be known Recalbox system folders.
    """
    data = request.get_json(silent=True) or {}
    src_system = data.get("from_system")
    dst_system = data.get("to_system")
    filename = data.get("filename")

    if not all([src_system, dst_system, filename]):
        return jsonify({"error": "Missing from_system, to_system, or filename"}), 400

    if src_system not in VALID_SYSTEMS:
        return jsonify({"error": f"Invalid source system: {src_system}"}), 400
    if dst_system not in VALID_SYSTEMS:
        return jsonify({"error": f"Invalid destination system: {dst_system}"}), 400

    src_path = os.path.join(_roms_root(), src_system, filename)
    dst_dir = os.path.join(_roms_root(), dst_system)
    dst_path = os.path.join(dst_dir, filename)

    if not os.path.exists(src_path):
        return jsonify({"error": f"Source file not found: {filename}"}), 404

    if not os.path.isdir(dst_dir):
        return jsonify({"error": f"Destination system folder not found: {dst_system}"}), 404

    if os.path.exists(dst_path):
        src_hash = get_file_hash(src_path)
        dst_hash = get_file_hash(dst_path)
        if src_hash and dst_hash and src_hash == dst_hash:
            # Identical content — trash the misplaced source, destination already correct
            trash_dir = os.path.join(_roms_root(), "_trash", src_system)
            os.makedirs(trash_dir, exist_ok=True)
            shutil.move(src_path, os.path.join(trash_dir, filename))
            logger.info(f"Trashed misplaced duplicate {filename} from {src_system} (identical copy already in {dst_system})")
            return jsonify({
                "ok": True,
                "action": "trashed_duplicate",
                "message": f"Identical copy already exists in {dst_system} — misplaced file removed.",
                "moved": {"file": filename, "from": src_system, "to": dst_system},
            })
        return jsonify({"error": f"File already exists in {dst_system} (different content)"}), 409

    try:
        shutil.move(src_path, dst_path)
        logger.info(f"Moved {filename}: {src_system} -> {dst_system}")
        return jsonify({"ok": True, "moved": {"file": filename, "from": src_system, "to": dst_system}})
    except (OSError, shutil.Error) as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/delete", methods=["POST"])
def delete_rom():
    """Move a ROM file to _trash/<system>/ (safe delete — never permanent).

    Request body: {system, filename}
    """
    data = request.get_json(silent=True) or {}
    system = data.get("system")
    filename = data.get("filename")

    if not all([system, filename]):
        return jsonify({"error": "Missing system or filename"}), 400

    if system not in VALID_SYSTEMS:
        return jsonify({"error": f"Invalid system: {system}"}), 400

    src_path = os.path.join(_roms_root(), system, filename)
    if not os.path.exists(src_path):
        return jsonify({"error": "File not found"}), 404

    # Move to trash instead of deleting
    trash_dir = os.path.join(_roms_root(), "_trash", system)
    os.makedirs(trash_dir, exist_ok=True)
    trash_path = os.path.join(trash_dir, filename)

    try:
        shutil.move(src_path, trash_path)
        logger.info(f"Trashed {filename} from {system}")
        return jsonify({"ok": True, "trashed": {"file": filename, "system": system}})
    except (OSError, shutil.Error) as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bulk-move", methods=["POST"])
def bulk_move():
    """Move multiple ROM files at once.

    Request body: {moves: [{from_system, to_system, filename}, ...]}
    Each system name must be a known Recalbox system folder.
    Each move is attempted independently; failures are reported per-item.
    """
    data = request.get_json(silent=True) or {}
    moves = data.get("moves", [])
    results = []
    for m in moves:
        from_system = m.get("from_system", "")
        to_system = m.get("to_system", "")
        filename = m.get("filename", "")
        if from_system not in VALID_SYSTEMS or to_system not in VALID_SYSTEMS:
            results.append({"file": filename, "status": "error", "error": "invalid system"})
            continue
        src = os.path.join(_roms_root(), from_system, filename)
        dst_dir = os.path.join(_roms_root(), to_system)
        dst = os.path.join(dst_dir, filename)
        try:
            if os.path.exists(src) and os.path.isdir(dst_dir) and not os.path.exists(dst):
                shutil.move(src, dst)
                results.append({"file": filename, "status": "moved"})
            elif os.path.exists(src) and os.path.isdir(dst_dir) and os.path.exists(dst):
                src_hash = get_file_hash(src)
                dst_hash = get_file_hash(dst)
                if src_hash and dst_hash and src_hash == dst_hash:
                    trash_dir = os.path.join(_roms_root(), "_trash", from_system)
                    os.makedirs(trash_dir, exist_ok=True)
                    shutil.move(src, os.path.join(trash_dir, filename))
                    results.append({"file": filename, "status": "trashed_duplicate"})
                else:
                    results.append({"file": filename, "status": "skipped", "reason": "different content"})
            else:
                results.append({"file": filename, "status": "skipped"})
        except (OSError, shutil.Error) as e:
            results.append({"file": filename, "status": "error", "error": str(e)})
    return jsonify({"results": results})


@app.route("/api/search")
def search_roms():
    """Search ROMs by name across all systems."""
    query = request.args.get("q", "").lower().strip()
    if not query or len(query) < 2:
        return jsonify([])

    results = []
    for sys_name, sys_info in scan_cache.get("systems", {}).items():
        for rom in sys_info.get("roms", []):
            if query in rom["name"].lower():
                results.append(rom)
    results.sort(key=lambda r: r["name"].lower())
    return jsonify(results[:200])  # cap results


@app.route("/api/bios")
def get_bios_status():
    """Return BIOS presence/status for all systems that require BIOS files."""
    return jsonify(check_bios_status())


@app.route("/api/diagnostics")
def get_diagnostics():
    """Return all ROM diagnostic issues across all systems (or filtered by ?system=)."""
    system_filter = request.args.get("system")
    all_diags = []
    for sys_key, sys_info in scan_cache.get("systems", {}).items():
        if system_filter and sys_key != system_filter:
            continue
        for diag in sys_info.get("diagnostic_issues", []):
            all_diags.append(diag)
    return jsonify(all_diags)


# ─── Cover / Gamelist Routes ──────────────────────────────────────────────────

@app.route("/api/covers/image/<system_name>/<filename>")
def serve_cover_image(system_name, filename):
    """Proxy a cover image from the SMB share to the browser."""
    # Prevent path traversal
    system_name = os.path.basename(system_name)
    filename = os.path.basename(filename)

    # Try media/images first, then media/thumbnails as fallback
    for subdir in ("images", "thumbnails"):
        img_path = os.path.join(_roms_root(), system_name, "media", subdir, filename)
        if os.path.exists(img_path):
            mimetype, _ = mimetypes.guess_type(filename)
            mimetype = mimetype or "image/png"
            response = send_file(img_path, mimetype=mimetype)
            response.headers["Cache-Control"] = "public, max-age=3600"
            return response

    return jsonify({"error": "Image not found"}), 404


@app.route("/api/gamelist/<system_name>")
def get_gamelist(system_name):
    """Return parsed gamelist.xml data for a system (re-parsed fresh from disk)."""
    system_name = os.path.basename(system_name)
    gamelist = parse_gamelist(system_name)
    return jsonify(gamelist)


@app.route("/api/covers/missing")
def get_missing_covers():
    """Return all ROMs that lack cover images (not misplaced/unknown, just missing cover)."""
    if not scan_cache.get("last_scan"):
        return jsonify({"ok": False, "error": "no_scan"})
    system_filter = request.args.get("system")
    missing = []
    for sys_name, sys_info in scan_cache.get("systems", {}).items():
        if system_filter and sys_name != system_filter:
            continue
        for rom in sys_info.get("roms", []):
            if not rom.get("has_cover") and rom.get("issue") is None:
                missing.append({
                    **{k: rom[k] for k in ("name", "ext", "size_human", "system", "game_name", "has_metadata")},
                    "system_name": sys_info["name"],
                })
    return jsonify(missing)


@app.route("/api/descriptions/missing")
def get_missing_descriptions():
    """Return all ROMs that lack descriptions (not misplaced/unknown, just missing <desc>)."""
    if not scan_cache.get("last_scan"):
        return jsonify({"ok": False, "error": "no_scan"})
    system_filter = request.args.get("system")
    missing = []
    for sys_name, sys_info in scan_cache.get("systems", {}).items():
        if system_filter and sys_name != system_filter:
            continue
        for rom in sys_info.get("roms", []):
            if not rom.get("has_description") and rom.get("issue") is None:
                missing.append({
                    **{k: rom[k] for k in ("name", "ext", "size_human", "system", "game_name", "has_metadata")},
                    "system_name": sys_info["name"],
                })
    return jsonify(missing)


def write_gamelist_entry(system_dir, rom_filename, fields):
    """
    Safely merge or insert a <game> entry in gamelist.xml.
    fields may include: name, image, thumbnail, desc, rating.
    Returns {ok, created} — created=True if a new entry was added.
    """
    xml_path = os.path.join(_roms_root(), system_dir, "gamelist.xml")
    bak_path = xml_path + ".bak"
    tmp_path = xml_path + ".tmp"

    # Read existing XML or create a minimal tree
    if os.path.exists(xml_path):
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except ET.ParseError as e:
            return {"ok": False, "error": "xml_parse_error", "detail": str(e)}
    else:
        root = ET.Element("gameList")
        tree = ET.ElementTree(root)

    # Find existing <game> entry (case-insensitive basename match)
    target_basename = os.path.basename(rom_filename).lower()
    found = None
    for game in root.findall("game"):
        path_el = game.find("path")
        if path_el is not None and path_el.text:
            existing_basename = os.path.basename(path_el.text.lstrip("./").replace("\\", "/")).lower()
            if existing_basename == target_basename:
                found = game
                break

    created = found is None
    if found is None:
        found = ET.SubElement(root, "game")
        path_el = ET.SubElement(found, "path")
        path_el.text = "./" + os.path.basename(rom_filename)

    # Update provided fields (never blank out fields not in the request)
    for field_name in ("name", "image", "thumbnail", "desc", "rating"):
        if field_name in fields and fields[field_name] is not None:
            el = found.find(field_name)
            if el is None:
                el = ET.SubElement(found, field_name)
            el.text = str(fields[field_name])

    # Backup existing file before write
    if os.path.exists(xml_path):
        try:
            shutil.copy2(xml_path, bak_path)
        except OSError:
            pass  # Non-fatal — proceed without backup

    # Write atomically: tmp then rename
    try:
        try:
            ET.indent(root)
        except AttributeError:
            pass  # ET.indent requires Python 3.9+
        tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
        os.replace(tmp_path, xml_path)
    except OSError as e:
        # Clean up tmp file if it exists
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return {"ok": False, "error": "write_error", "detail": str(e)}

    # Refresh in-memory gamelist cache for this system
    scan_cache["gamelists"][system_dir] = parse_gamelist(system_dir)

    return {"ok": True, "created": created}


@app.route("/api/gamelist/update", methods=["POST"])
def update_gamelist():
    """Merge or insert a <game> entry in gamelist.xml."""
    data = request.json or {}
    system = data.get("system")
    filename = data.get("filename")
    if not system or not filename:
        return jsonify({"error": "Missing system or filename"}), 400
    fields = {k: data.get(k) for k in ("name", "image", "thumbnail", "desc", "rating")}
    result = write_gamelist_entry(system, filename, fields)
    return jsonify(result)


def fetch_screenscraper_cover(system_key, rom_filename, game_name=""):
    """
    Fetch cover art from ScreenScraper.fr for one ROM.
    Returns {ok, image_path?, cover_url?, error?}.
    Never raises — all errors returned in dict.
    """
    if not ss_config.get("screenscraper_user") or not ss_config.get("screenscraper_pass"):
        return {"ok": False, "error": "no_credentials"}

    if not ss_config.get("screenscraper_devid") or not ss_config.get("screenscraper_devpass"):
        return {"ok": False, "error": "no_devid"}

    system_id = SCREENSCRAPER_SYSTEM_IDS.get(system_key.lower())
    if not system_id:
        return {"ok": False, "error": "unsupported_system"}

    params = {
        "devid": ss_config["screenscraper_devid"],
        "devpassword": ss_config["screenscraper_devpass"],
        "softname": "recalbox-manager",
        "output": "json",
        "ssid": ss_config["screenscraper_user"],
        "sspassword": ss_config["screenscraper_pass"],
        "systemeid": system_id,
        "romnom": rom_filename,
    }
    search_term = game_name or _clean_rom_name(rom_filename)
    if search_term:
        params["romrecherche"] = search_term  # text search field (keeps romnom for hash matching)

    url = "https://www.screenscraper.fr/api2/jeuInfos.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"recalbox-manager/{APP_VERSION}"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (429, 430):
            return {"ok": False, "error": "rate_limited"}
        if e.code == 403:
            return {"ok": False, "error": "no_devid", "detail": "HTTP 403 — developer credentials rejected or missing"}
        if e.code == 404:
            return {"ok": False, "error": "not_found"}
        return {"ok": False, "error": "ss_down", "detail": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            return {"ok": False, "error": "timeout"}
        return {"ok": False, "error": "ss_down", "detail": str(e)}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": "not_found"}

    # Check for rate limit in response body
    ssuser = data.get("response", {}).get("ssuser", {})
    if ssuser.get("requeststoday") and ssuser.get("maxrequestsperday"):
        if int(ssuser.get("requeststoday", 0)) >= int(ssuser.get("maxrequestsperday", 1)):
            return {"ok": False, "error": "rate_limited"}

    # Navigate to media list
    jeu = data.get("response", {}).get("jeu")
    if not jeu:
        return {"ok": False, "error": "not_found"}

    medias = jeu.get("medias", [])
    if not medias:
        return {"ok": False, "error": "not_found"}

    # Pick best media: prefer box-2D front, then box-2D-back, then screenshot
    preferred_types = ["box-2D", "box-2D-back", "screenshot"]
    chosen = None
    for preferred in preferred_types:
        for media in medias:
            if media.get("type") == preferred:
                # Prefer English or neutral region
                region = media.get("region", "")
                if region in ("", "wor", "eu", "us", "ss"):
                    chosen = media
                    break
            if chosen:
                break
        if chosen:
            break

    if not chosen:
        chosen = medias[0]  # take whatever is first

    img_url = chosen.get("url")
    if not img_url:
        return {"ok": False, "error": "not_found"}

    # Determine extension from URL
    img_ext = os.path.splitext(urllib.parse.urlparse(img_url).path)[1] or ".png"
    rom_stem = os.path.splitext(rom_filename)[0]
    img_filename = rom_stem + img_ext

    # Download image
    try:
        with urllib.request.urlopen(img_url, timeout=15) as img_resp:
            img_data = img_resp.read()
    except Exception as e:
        return {"ok": False, "error": "timeout", "detail": str(e)}

    # Save to <system>/media/images/<stem><ext>
    img_dir = os.path.join(_roms_root(), system_key, "media", "images")
    os.makedirs(img_dir, exist_ok=True)
    img_path = os.path.join(img_dir, img_filename)
    try:
        with open(img_path, "wb") as f:
            f.write(img_data)
    except OSError as e:
        return {"ok": False, "error": "write_error", "detail": str(e)}

    logger.info(f"Saved cover for {rom_filename} -> {img_path}")

    cover_url = _cover_url_for(system_key, f"./media/images/{img_filename}")
    return {"ok": True, "image_path": img_path, "cover_url": cover_url,
            "img_filename": img_filename, "source": "screenscraper"}


def fetch_libretro_cover(system_key, rom_filename, game_name=""):
    """
    Fetch cover art from Libretro Thumbnails CDN (https://thumbnails.libretro.com/).
    No authentication required. Returns {ok, image_path?, cover_url?, error?}.
    Never raises — all errors returned in dict.
    """
    system_name = LIBRETRO_SYSTEM_NAMES.get(system_key.lower())
    if not system_name:
        return {"ok": False, "error": "unsupported_system"}

    search_name = game_name or _clean_rom_name(rom_filename)
    if not search_name:
        return {"ok": False, "error": "no_name"}

    # Libretro spec: replace forbidden chars with underscore, then URL-encode
    safe_name = re.sub(r'[&*/:<>?\\|]', '_', search_name)
    encoded_system = urllib.parse.quote(system_name, safe='')
    encoded_name = urllib.parse.quote(safe_name, safe='')
    img_url = f"https://thumbnails.libretro.com/{encoded_system}/Named_Boxarts/{encoded_name}.png"

    req = urllib.request.Request(img_url, headers={"User-Agent": f"recalbox-manager/{APP_VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            img_data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False, "error": "not_found"}
        return {"ok": False, "error": "libretro_down", "detail": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            return {"ok": False, "error": "timeout"}
        return {"ok": False, "error": "libretro_down", "detail": str(e)}

    rom_stem = os.path.splitext(rom_filename)[0]
    img_filename = rom_stem + ".png"
    img_dir = os.path.join(_roms_root(), system_key, "media", "images")
    os.makedirs(img_dir, exist_ok=True)
    img_path = os.path.join(img_dir, img_filename)
    try:
        with open(img_path, "wb") as f:
            f.write(img_data)
    except OSError as e:
        return {"ok": False, "error": "write_error", "detail": str(e)}

    logger.info(f"[Libretro] Saved cover for {rom_filename} -> {img_path}")
    cover_url = _cover_url_for(system_key, f"./media/images/{img_filename}")
    return {"ok": True, "image_path": img_path, "cover_url": cover_url,
            "img_filename": img_filename, "source": "libretro"}


def _extract_synopsis(jeu, preferred_lang="en"):
    """Extract synopsis text from a ScreenScraper jeu object.
    Prefers preferred_lang, falls back to first available language.
    Returns str or None.
    """
    for entry in jeu.get("synopsis", []):
        if entry.get("langue") == preferred_lang and entry.get("text"):
            return entry["text"]
    for entry in jeu.get("synopsis", []):
        if entry.get("text"):
            return entry["text"]
    return None


def fetch_screenscraper_description(system_key, rom_filename, game_name=""):
    """
    Fetch game description (synopsis) from ScreenScraper.fr for one ROM.
    Returns {ok, desc?, error?}.
    Never raises — all errors returned in dict.
    """
    if not ss_config.get("screenscraper_user") or not ss_config.get("screenscraper_pass"):
        return {"ok": False, "error": "no_credentials"}

    if not ss_config.get("screenscraper_devid") or not ss_config.get("screenscraper_devpass"):
        return {"ok": False, "error": "no_devid"}

    system_id = SCREENSCRAPER_SYSTEM_IDS.get(system_key.lower())
    if not system_id:
        return {"ok": False, "error": "unsupported_system"}

    params = {
        "devid": ss_config["screenscraper_devid"],
        "devpassword": ss_config["screenscraper_devpass"],
        "softname": "recalbox-manager",
        "output": "json",
        "ssid": ss_config["screenscraper_user"],
        "sspassword": ss_config["screenscraper_pass"],
        "systemeid": system_id,
        "romnom": rom_filename,
    }
    search_term = game_name or _clean_rom_name(rom_filename)
    if search_term:
        params["romrecherche"] = search_term

    url = "https://www.screenscraper.fr/api2/jeuInfos.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"recalbox-manager/{APP_VERSION}"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (429, 430):
            return {"ok": False, "error": "rate_limited"}
        if e.code == 403:
            return {"ok": False, "error": "no_devid", "detail": "HTTP 403 — developer credentials rejected or missing"}
        if e.code == 404:
            return {"ok": False, "error": "not_found"}
        return {"ok": False, "error": "ss_down", "detail": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            return {"ok": False, "error": "timeout"}
        return {"ok": False, "error": "ss_down", "detail": str(e)}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": "not_found"}

    ssuser = data.get("response", {}).get("ssuser", {})
    if ssuser.get("requeststoday") and ssuser.get("maxrequestsperday"):
        if int(ssuser.get("requeststoday", 0)) >= int(ssuser.get("maxrequestsperday", 1)):
            return {"ok": False, "error": "rate_limited"}

    jeu = data.get("response", {}).get("jeu")
    if not jeu:
        return {"ok": False, "error": "not_found"}

    desc = _extract_synopsis(jeu)
    if not desc:
        return {"ok": False, "error": "not_found"}

    logger.info(f"Got description for {rom_filename} ({len(desc)} chars)")
    return {"ok": True, "desc": desc}


@app.route("/api/covers/scrape", methods=["POST"])
def scrape_cover():
    """Fetch cover art from ScreenScraper for one ROM and update gamelist.xml."""
    data = request.json or {}
    filename = data.get("filename")
    system = data.get("system")
    game_name = data.get("game_name", "")

    if not filename or not system:
        return jsonify({"error": "Missing filename or system"}), 400

    result = fetch_screenscraper_cover(system, filename, game_name)

    # Fallback to Libretro Thumbnails when ScreenScraper can't help
    if not result["ok"] and result.get("error") in (
        "not_found", "no_credentials", "no_devid", "unsupported_system"
    ):
        logger.info(f"ScreenScraper miss ({result.get('error')}) for {filename}, trying Libretro Thumbnails...")
        result = fetch_libretro_cover(system, filename, game_name)

    if not result["ok"]:
        return jsonify(result)

    # Update gamelist.xml with the new image path (relative Unix path for Recalbox)
    img_filename = result["img_filename"]
    image_rel = f"./media/images/{img_filename}"
    rom_stem = os.path.splitext(filename)[0]

    # Get existing game_name from gamelist if not provided
    if not game_name:
        gl = scan_cache.get("gamelists", {}).get(system, {})
        gl_entry = gl.get(rom_stem.lower())
        if gl_entry:
            game_name = gl_entry.get("name", "")

    write_result = write_gamelist_entry(system, filename, {
        "name": game_name or rom_stem,
        "image": image_rel,
    })

    # Only update the in-memory cache when gamelist.xml was actually written.
    if write_result.get("ok"):
        sys_info = scan_cache.get("systems", {}).get(system)
        if sys_info:
            for rom in sys_info.get("roms", []):
                if rom["name"] == filename:
                    rom["has_cover"] = True
                    rom["cover_url"] = result["cover_url"]
                    if not rom.get("game_name") and game_name:
                        rom["game_name"] = game_name
                    break
            # Update cover_count on the system
            sys_info["cover_count"] = sum(1 for r in sys_info["roms"] if r.get("has_cover"))
        if scan_cache.get("stats"):
            scan_cache["stats"]["total_with_covers"] = sum(
                s.get("cover_count", 0) for s in scan_cache.get("systems", {}).values()
            )
            scan_cache["stats"]["total_missing_covers"] = sum(
                sum(1 for r in s.get("roms", []) if not r.get("has_cover") and r.get("issue") is None)
                for s in scan_cache.get("systems", {}).values()
            )

    return jsonify({**result, "gamelist_updated": write_result.get("ok", False)})


@app.route("/api/descriptions/scrape", methods=["POST"])
def scrape_description():
    """Fetch description from ScreenScraper for one ROM and update gamelist.xml."""
    data = request.json or {}
    filename = data.get("filename")
    system = data.get("system")
    game_name = data.get("game_name", "")

    if not filename or not system:
        return jsonify({"error": "Missing filename or system"}), 400

    result = fetch_screenscraper_description(system, filename, game_name)
    if not result["ok"]:
        return jsonify(result)

    rom_stem = os.path.splitext(filename)[0]
    if not game_name:
        gl = scan_cache.get("gamelists", {}).get(system, {})
        gl_entry = gl.get(rom_stem.lower())
        if gl_entry:
            game_name = gl_entry.get("name", "")

    write_result = write_gamelist_entry(system, filename, {
        "name": game_name or rom_stem,
        "desc": result["desc"],
    })

    # Only update the in-memory cache when gamelist.xml was actually written.
    # If the write failed, leave the cache unchanged so the UI stays honest —
    # marking has_description=True when the file wasn't saved would cause the
    # "missing descriptions" count to silently drop during the session but jump
    # back up on the next scan (which re-reads from gamelist.xml).
    if write_result.get("ok"):
        sys_info = scan_cache.get("systems", {}).get(system)
        if sys_info:
            for rom in sys_info.get("roms", []):
                if rom["name"] == filename:
                    rom["has_description"] = True
                    if not rom.get("game_name") and game_name:
                        rom["game_name"] = game_name
                    break
            sys_info["description_count"] = sum(1 for r in sys_info["roms"] if r.get("has_description"))
        if scan_cache.get("stats"):
            scan_cache["stats"]["total_with_descriptions"] = sum(
                s.get("description_count", 0) for s in scan_cache.get("systems", {}).values()
            )
            scan_cache["stats"]["total_missing_descriptions"] = sum(
                sum(1 for r in s.get("roms", []) if not r.get("has_description") and r.get("issue") is None)
                for s in scan_cache.get("systems", {}).values()
            )

    return jsonify({**result, "gamelist_updated": write_result.get("ok", False)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5123))
    # FLASK_RELOADER=false disables Werkzeug's reloader (used by test fixtures to
    # prevent orphan child processes that keep the port alive after the parent is killed)
    use_reloader = os.environ.get("FLASK_RELOADER", "true").lower() != "false"
    logger.info(f"Starting Recalbox ROM Manager on http://localhost:{port}")
    logger.info(f"Recalbox share path: {_config['share']}")
    logger.info(f"ROMs root: {_roms_root()}")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=use_reloader)
