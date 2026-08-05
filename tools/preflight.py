#!/usr/bin/env python3
"""Pre-launch check: verifies this checkout can actually run before you start it.

Run from the repo root:

    python tools/preflight.py

Checks, in order of how badly they bite:

  1. configs/private_config.py exists and has every field the bots read
  2. db/ carries over your existing settings + XP (running without it silently
     starts from an EMPTY database - every guild's log channel, admin list and
     rank config, and every user's XP, would appear wiped)
  3. Python version, dependencies, and ffmpeg
  4. logs/ is writable

Exits non-zero if anything blocking is wrong. Nothing here contacts Discord.
"""

import importlib
import os
import shutil
import sqlite3
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# name -> whether the bots hard-require it
REQUIRED_CONFIG_FIELDS = ["bots", "bot_ids", "supreme_beings", "test_guilds"]
OPTIONAL_CONFIG_FIELDS = [
    "openai_api_key", "hosting_ip", "hosting_port", "server_manager_password",
    "backup_url", "backup_login", "backup_password",
]

VALID_BOT_TYPES = {"MusicLeader", "MusicInstance", "Admin", "Logger"}

problems = []
warnings = []


def ok(message):
    print(f"  [ ok ] {message}")


def fail(message, fix=None):
    print(f"  [FAIL] {message}")
    if fix:
        print(f"         fix: {fix}")
    problems.append(message)


def warn(message, fix=None):
    print(f"  [warn] {message}")
    if fix:
        print(f"         {fix}")
    warnings.append(message)


def check_python():
    print("\nPython")
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        ok(f"Python {major}.{minor} (README asks for 3.11+)")
    elif (major, minor) >= (3, 10):
        warn(f"Python {major}.{minor}; README asks for 3.11+",
             "the code runs on 3.10, but 3.11+ is what it's documented against")
    else:
        fail(f"Python {major}.{minor} is too old - match statements need 3.10+",
             "install Python 3.11 or newer")


def check_dependencies():
    print("\nDependencies")
    for module, label in [("disnake", "disnake"), ("aiosqlite", "aiosqlite"),
                          ("yt_dlp", "yt-dlp"), ("youtube_search", "youtube-search")]:
        try:
            mod = importlib.import_module(module)
            version = getattr(mod, "__version__", None)
            if version is None and hasattr(mod, "version"):
                version = getattr(mod.version, "__version__", "?")
            ok(f"{label} {version or '(version unknown)'}")
        except ImportError:
            fail(f"{label} is not installed",
                 "pip install -r requirements.txt")

    try:
        import nacl  # noqa: F401
        ok("PyNaCl (voice support)")
    except ImportError:
        fail("PyNaCl missing - voice will not work",
             "pip install 'disnake[voice]'")


def check_ffmpeg():
    print("\nFFmpeg")
    path = shutil.which("ffmpeg")
    if not path:
        fail("ffmpeg not found on PATH - music playback will fail",
             "Linux: sudo apt install ffmpeg   |   Windows: see README")
        return
    try:
        out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10)
        first = out.stdout.splitlines()[0] if out.stdout else "?"
        ok(f"{first}")
    except Exception as exc:
        warn(f"ffmpeg found at {path} but could not be run: {exc}")


def check_private_config():
    print("\nconfigs/private_config.py")
    path = os.path.join(REPO_ROOT, "configs", "private_config.py")
    if not os.path.exists(path):
        fail("missing - the bots cannot start without their tokens",
             "copy it from your original checkout: "
             "cp ../configs/private_config.py configs/")
        return None

    sys.path.insert(0, REPO_ROOT)
    try:
        import configs.private_config as private_config
    except Exception as exc:
        fail(f"exists but failed to import: {exc}")
        return None

    ok("present and importable")

    for field in REQUIRED_CONFIG_FIELDS:
        if not hasattr(private_config, field):
            fail(f"missing required field: {field}")
    for field in OPTIONAL_CONFIG_FIELDS:
        if not hasattr(private_config, field):
            warn(f"optional field not set: {field}",
                 "only needed for the hosting/backup scripts or the GPT feature")

    bots = getattr(private_config, "bots", [])
    if not bots:
        warn("`bots` is empty - nothing would start")
        return private_config

    counts = {}
    for spec in bots:
        if len(spec) != 3:
            fail(f"malformed bot entry (needs [name, type, token]): {spec!r}")
            continue
        name, bot_type, token = spec
        counts[bot_type] = counts.get(bot_type, 0) + 1
        if bot_type not in VALID_BOT_TYPES:
            fail(f"unknown bot type {bot_type!r} for {name!r} - it will be skipped",
                 f"valid types: {', '.join(sorted(VALID_BOT_TYPES))}")
        if not token or len(token) < 50:
            warn(f"token for {name!r} looks too short to be valid")
        if name not in getattr(private_config, "bot_ids", {}):
            warn(f"{name!r} has no entry in bot_ids",
                 "self-unmute and bot-detection logic keys off bot_ids")

    ok(f"{len(bots)} bot(s) configured: " +
       ", ".join(f"{n}x{t}" for t, n in sorted(counts.items())))

    # Same rules main.validate_bots() enforces, reported earlier and more clearly.
    for bot_type in ("MusicLeader", "Admin", "Logger"):
        if counts.get(bot_type, 0) > 1:
            fail(f"{counts[bot_type]} {bot_type} bots configured - only one is allowed",
                 "main.py will refuse to start")
    if counts.get("MusicInstance", 0) > 0 and counts.get("MusicLeader", 0) == 0:
        fail("MusicInstance bots configured without a MusicLeader",
             "instances are driven by the leader; main.py will refuse to start")

    return private_config


def check_databases():
    print("\ndb/  (settings + XP carry-over)")
    db_dir = os.path.join(REPO_ROOT, "db")
    main_db = os.path.join(db_dir, "bot_database.db")

    if not os.path.exists(main_db):
        fail("db/bot_database.db missing - the bots would start from an EMPTY "
             "database: every guild's log channel, admin list and ranks, and "
             "every user's XP, would appear wiped",
             "copy it from your original checkout: cp -r ../db .")
        return

    try:
        conn = sqlite3.connect(f"file:{main_db}?mode=ro", uri=True)
        cur = conn.cursor()
        summary = []
        for table, label in [("server_options", "guild settings"),
                             ("users_xp_data", "user XP rows"),
                             ("ranks_data", "ranks")]:
            try:
                count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                summary.append(f"{count} {label}")
            except sqlite3.Error:
                warn(f"table {table} not found in bot_database.db "
                     "(it will be created empty on first run)")
        conn.close()
        if summary:
            ok("bot_database.db carries " + ", ".join(summary))
    except sqlite3.Error as exc:
        fail(f"bot_database.db is unreadable: {exc}")

    logs_db = os.path.join(db_dir, "logs.db")
    if not os.path.exists(logs_db):
        warn("db/logs.db missing - it will be created empty",
             "only the historical audit trail is affected, not bot behavior")
    else:
        size_mb = os.path.getsize(logs_db) / (1024 * 1024)
        ok(f"logs.db present ({size_mb:.0f} MB)")
        if size_mb > 500:
            warn(f"logs.db is {size_mb:.0f} MB and grows unbounded",
                 "consider pruning old rows; the manual backup uploads this file")


def check_writable_paths():
    print("\nFilesystem")
    for name in ("logs", "db"):
        path = os.path.join(REPO_ROOT, name)
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                ok(f"{name}/ created")
            except OSError as exc:
                fail(f"cannot create {name}/: {exc}")
                continue
        if os.access(path, os.W_OK):
            ok(f"{name}/ is writable")
        else:
            fail(f"{name}/ is not writable")


def main():
    print("=" * 70)
    print("Nazarick bots - preflight check")
    print("=" * 70)

    check_python()
    check_dependencies()
    check_ffmpeg()
    check_private_config()
    check_databases()
    check_writable_paths()

    print("\n" + "=" * 70)
    if problems:
        print(f"NOT READY - {len(problems)} blocking problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        if warnings:
            print(f"\nplus {len(warnings)} warning(s) above.")
        print("=" * 70)
        return 1

    if warnings:
        print(f"READY, with {len(warnings)} warning(s) - review them above.")
    else:
        print("READY - all checks passed.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
