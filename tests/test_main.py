"""Unit tests for main.py wiring and hosting/server_manager.py.

`validate_bots` decides which configurations are allowed to start, and the
wiring loop after it builds the cross-bot object graph the whole project
depends on - both are worth pinning since a mistake there is silent (bots come
up but can't see each other).
"""

import asyncio

import pytest

import main
from hosting import server_manager


# --------------------------------------------------------------------------- #
# validate_bots
# --------------------------------------------------------------------------- #

def validate(leaders=0, instances=0, admins=0, loggers=0):
    return asyncio.run(main.validate_bots(
        [object()] * leaders, [object()] * instances,
        [object()] * admins, [object()] * loggers))


def test_valid_full_setup():
    assert validate(leaders=1, instances=4, admins=1, loggers=1) is True


def test_leader_only_is_valid():
    """A single MusicLeader with no assistants is a supported setup - the
    leader is its own instance."""
    assert validate(leaders=1, instances=1) is True


def test_empty_config_is_allowed():
    """Quirk preserved from the original: an empty bot list prints a notice but
    still returns True; main() then gathers zero tasks and exits cleanly."""
    assert validate() is True


def test_two_leaders_rejected():
    assert validate(leaders=2, instances=2) is False


def test_two_admins_rejected():
    assert validate(admins=2) is False


def test_two_loggers_rejected():
    assert validate(loggers=2) is False


def test_instances_without_leader_rejected():
    assert validate(instances=3) is False


def test_admin_and_logger_without_music_is_valid():
    assert validate(admins=1, loggers=1) is True


# --------------------------------------------------------------------------- #
# server_manager error filter (same bug as admin_bot)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("line", [
    "[tls @ 0x55f1] Error in the pull function",
    "[https @ 0x7f2a] Will reconnect at 1024",
    "[hls @ 0x9911] Skip ('#EXT-X-VERSION:3')",
    "Stream ends prematurely, retrying with new connection",
])
def test_server_manager_filters_noise(line):
    assert server_manager.is_ignorable_error_line(line) is True


@pytest.mark.parametrize("line", [
    "Traceback (most recent call last):",
    "RuntimeError: boom",
    "disnake.errors.HTTPException: 500 Internal Server Error",
])
def test_server_manager_keeps_real_errors(line):
    """Before the fix this returned True for everything, so `status` always
    reported 'No errors' no matter how badly the bot was failing."""
    assert server_manager.is_ignorable_error_line(line) is False


def test_server_manager_and_admin_bot_filters_agree():
    """The two copies of this filter must stay in sync - they read the same
    stderr stream from opposite ends."""
    import bots.admin_bot as admin_bot
    assert (server_manager.IGNORED_ERROR_FRAGMENTS
            == admin_bot.IGNORED_ERROR_FRAGMENTS)


# --------------------------------------------------------------------------- #
# get_passed_time formatting
# --------------------------------------------------------------------------- #

def test_get_passed_time_none_returns_none():
    assert server_manager.Host.get_passed_time(None, None) is None


@pytest.mark.parametrize("delta_kwargs,expected", [
    ({"seconds": 30}, "a minute ago"),
    ({"minutes": 5}, "5 minutes ago"),
    ({"hours": 1}, "an hour ago"),
    ({"hours": 5}, "5 hours ago"),
    ({"days": 1}, "a day ago"),
    ({"days": 3}, "3 days ago"),
    ({"days": 8}, "a week ago"),
    ({"days": 40}, "a month ago"),
    ({"days": 400}, "a year ago"),
])
def test_get_passed_time_units(delta_kwargs, expected):
    from datetime import datetime, timedelta, timezone
    date = datetime.now(timezone.utc) - timedelta(**delta_kwargs)
    assert server_manager.Host.get_passed_time(None, date) == expected


# --------------------------------------------------------------------------- #
# Thread pool configuration
# --------------------------------------------------------------------------- #

def test_thread_pool_default_matches_original():
    """None = Python's default sizing, which is what the original used.
    Pinned so a future edit to this knob is a conscious decision."""
    assert main.THREAD_POOL_MAX_WORKERS is None
