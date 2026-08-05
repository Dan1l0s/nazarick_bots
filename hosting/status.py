"""Shared playback-status file, written by the bot process and read by the
supervisor.

`main.py` and `hosting/server_manager.py` are separate OS processes, so the
supervisor has no way to see whether any bot is mid-song - `check_music_bots()`
lives inside the admin bot. This module is the bridge: the bot process
periodically writes a small JSON file, and the supervisor reads it to decide
whether a deferred restart may proceed.

A file was chosen over a socket deliberately: it needs no new listener, no
protocol, and it degrades correctly when either process dies. A stale file
(nobody updating it) is treated as idle, so a crashed or wedged bot can never
block a deploy forever.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Iterable

logger = logging.getLogger("nazarick.status")

# Written relative to the repo root.
STATUS_PATH = os.path.join("run", "status.json")

# How often the bot process refreshes the file.
WRITE_INTERVAL = 15

# If the file has not been touched in this long, the bot process is assumed
# dead or hung and is reported idle. Must be comfortably larger than
# WRITE_INTERVAL so a slow write is not mistaken for a crash.
STALE_AFTER = 120


def count_active_plays(instances: Iterable) -> tuple[int, int, dict]:
    """Returns (active_plays, connected_channels, per-bot breakdown).

    `active_plays` counts guilds where a track is actually loaded and playing;
    that is what gates a deferred restart. `connected` additionally counts
    guilds where a bot sits in a voice channel with nothing playing - reported
    for visibility but not used to block, since those disconnect on their own
    after PlayTimeout.
    """
    active = 0
    connected = 0
    breakdown = {}
    for instance in instances:
        name = getattr(instance, "name", "?")
        states = getattr(instance, "states", {}) or {}
        bot_active = 0
        bot_connected = 0
        for state in states.values():
            if getattr(state, "voice", None) is not None:
                bot_connected += 1
            if getattr(state, "current_song", None) is not None:
                bot_active += 1
        active += bot_active
        connected += bot_connected
        if bot_active or bot_connected:
            breakdown[name] = {"playing": bot_active, "connected": bot_connected}
    return active, connected, breakdown


def write_status(instances: Iterable, path: str = STATUS_PATH) -> dict:
    """Writes the status file atomically (temp file + rename) so the supervisor
    never reads a half-written document."""
    active, connected, breakdown = count_active_plays(instances)
    payload = {
        "pid": os.getpid(),
        "updated_at": time.time(),
        "active_plays": active,
        "connected_channels": connected,
        "bots": breakdown,
    }
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(tmp, path)
    return payload


def read_status(path: str = STATUS_PATH) -> dict | None:
    """Returns the parsed status file, or None if absent/unreadable/corrupt."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def is_idle(path: str = STATUS_PATH, stale_after: int = STALE_AFTER) -> tuple[bool, str]:
    """Returns (idle, human-readable reason).

    Idle means "safe to restart now". Missing or stale status counts as idle on
    purpose: if the bot process is not writing, it is not playing music either,
    and refusing to restart would leave a broken deployment stuck.
    """
    status = read_status(path)
    if status is None:
        return True, "no status file (bot not running, or never reported)"

    age = time.time() - status.get("updated_at", 0)
    if age > stale_after:
        return True, f"status is stale ({int(age)}s old) - bot process assumed dead or hung"

    active = status.get("active_plays", 0)
    if active > 0:
        connected = status.get("connected_channels", 0)
        return False, f"{active} active play(s) across {connected} voice channel(s)"

    return True, "no active plays"


async def status_writer(instances: Iterable, path: str = STATUS_PATH,
                        interval: int = WRITE_INTERVAL) -> None:
    """Background task: refreshes the status file forever.

    Never raises - a failure here must not take the bots down, so write errors
    are logged and retried on the next tick.
    """
    while True:
        try:
            write_status(instances, path)
        except Exception:
            logger.exception("failed to write status file at %s", path)
        await asyncio.sleep(interval)


def clear_status(path: str = STATUS_PATH) -> None:
    """Removes the status file. Called by the supervisor after stopping the bot
    so a leftover file from the previous run can't be mistaken for a live one."""
    try:
        os.remove(path)
    except OSError:
        pass
