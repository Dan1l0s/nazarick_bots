"""Unit tests for bots/log_bot.py.

Covers the presence-diffing value objects (which decide whether a status change
gets logged at all), the audit-log dynamic dispatch naming, and the
status-channel lookup/caching helper.
"""

import asyncio
import types

import pytest

import bots.log_bot as log_bot
import helpers.database_logger as database_logger
import helpers.embedder as embedder
import helpers.helpers as helpers
from bots.log_bot import Activity, UserStatus


# --------------------------------------------------------------------------- #
# Activity / UserStatus equality (drives "did this member's presence change?")
# --------------------------------------------------------------------------- #

def test_activity_equality():
    assert Activity("game", "Minecraft") == Activity("game", "Minecraft")
    assert not (Activity("game", "Minecraft") == Activity("game", "Factorio"))
    assert not (Activity("game", "Minecraft") == Activity("spotify", "Minecraft"))


def test_user_status_equal_when_same_status_and_activities():
    a = UserStatus("online")
    a.activities = [Activity("game", "Minecraft")]
    b = UserStatus("online")
    b.activities = [Activity("game", "Minecraft")]
    assert a == b


def test_user_status_differs_on_status_change():
    a = UserStatus("online")
    b = UserStatus("idle")
    assert not (a == b)


def test_user_status_differs_on_activity_change():
    a = UserStatus("online")
    a.activities = [Activity("game", "Minecraft")]
    b = UserStatus("online")
    b.activities = [Activity("game", "Factorio")]
    assert not (a == b)


def test_user_status_ignores_activity_ordering():
    """Discord doesn't guarantee activity ordering; a reorder alone must not
    be reported as a presence change (this is why __eq__ compares sets)."""
    a = UserStatus("online")
    a.activities = [Activity("game", "Minecraft"), Activity("spotify", "Song")]
    b = UserStatus("online")
    b.activities = [Activity("spotify", "Song"), Activity("game", "Minecraft")]
    assert a == b


def test_user_status_starts_not_updated():
    assert UserStatus("online").updated is False


# --------------------------------------------------------------------------- #
# gen_status_and_activity
# --------------------------------------------------------------------------- #

class FakeGameActivity:
    def __init__(self, name):
        self.name = name


class FakeMember:
    def __init__(self, status, activities=(), is_bot=False, member_id=1):
        self.status = status
        self.activities = list(activities)
        self.bot = is_bot
        self.id = member_id

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, FakeMember) and self.id == other.id


def test_gen_status_and_activity_populates_status_and_names():
    member = FakeMember("online", [FakeGameActivity("Minecraft")])
    status_dict = {member: UserStatus(None)}

    log_bot.LogBot.gen_status_and_activity(None, status_dict)

    assert status_dict[member].status == "online"
    assert len(status_dict[member].activities) == 1
    assert status_dict[member].activities[0].actname == "Minecraft"


def test_gen_status_and_activity_handles_no_activities():
    member = FakeMember("dnd")
    status_dict = {member: UserStatus(None)}

    log_bot.LogBot.gen_status_and_activity(None, status_dict)

    assert status_dict[member].status == "dnd"
    assert status_dict[member].activities == []


# --------------------------------------------------------------------------- #
# Audit-log dynamic dispatch naming
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("action_repr,expected", [
    ("AuditLogAction.channel_create", "entry_channel_create"),
    ("AuditLogAction.kick", "entry_kick"),
    ("AuditLogAction.sticker_delete", "entry_sticker_delete"),
    ("AuditLogAction.guild_scheduled_event_update", "entry_guild_scheduled_event_update"),
])
def test_audit_action_name_slicing(action_repr, expected):
    """on_audit_log_entry_create derives the handler name with `str(action)[15:]`;
    this pins that the slice offset still lines up with disnake's repr."""
    assert f"entry_{action_repr[15:]}" == expected


def test_sticker_handlers_resolve_on_both_modules():
    """Regression test tied to the Stage 1 embedder fix: before it, the
    sticker-create embed was shadowed and sticker-delete had no embed at all,
    so this dispatch silently produced no message for sticker deletions."""
    for name in ("entry_sticker_create", "entry_sticker_update", "entry_sticker_delete"):
        assert hasattr(database_logger, name), f"database_logger missing {name}"
        assert hasattr(embedder, name), f"embedder missing {name}"


def test_voice_state_attrs_have_matching_handlers():
    """Every attribute in public_config.on_v_s_update that has an embedder
    function must also have a database_logger function - the voice handler
    calls `getattr(database_logger, attr)` guarded only by a check on
    `embedder`, so a mismatch would raise AttributeError at runtime."""
    import configs.public_config as public_config
    for attr in public_config.on_v_s_update:
        if hasattr(embedder, attr):
            assert hasattr(database_logger, attr), (
                f"embedder has {attr} but database_logger does not - "
                "on_voice_state_update would raise AttributeError")


# --------------------------------------------------------------------------- #
# Status channel lookup / caching
# --------------------------------------------------------------------------- #

class FakeGuild:
    def __init__(self, guild_id):
        self.id = guild_id


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "bot_database.db")
    monkeypatch.setattr(helpers, "DB_PATH", path)
    return path


def test_get_status_channels_only_includes_configured_guilds(db_path):
    async def scenario():
        await helpers.set_guild_option(1, helpers.GuildOption.STATUS_LOG_CHANNEL, 555)
        # guild 2 deliberately left unconfigured
        guilds = [FakeGuild(1), FakeGuild(2)]
        return await log_bot.LogBot._get_status_channels(None, guilds, {})

    assert asyncio.run(scenario()) == {1: 555}


def test_get_status_channels_uncached_rereads_every_call(db_path, monkeypatch):
    """Default behavior (cache disabled) must match the original: a settings
    change takes effect on the very next poll."""
    monkeypatch.setattr(log_bot, "STATUS_CHANNEL_CACHE_SECONDS", 0)

    async def scenario():
        guilds = [FakeGuild(1)]
        cache = {}
        await helpers.set_guild_option(1, helpers.GuildOption.STATUS_LOG_CHANNEL, 555)
        first = await log_bot.LogBot._get_status_channels(None, guilds, cache)
        await helpers.set_guild_option(1, helpers.GuildOption.STATUS_LOG_CHANNEL, 777)
        second = await log_bot.LogBot._get_status_channels(None, guilds, cache)
        return first, second

    first, second = asyncio.run(scenario())
    assert first == {1: 555}
    assert second == {1: 777}


def test_get_status_channels_cached_serves_stale_within_ttl(db_path, monkeypatch):
    monkeypatch.setattr(log_bot, "STATUS_CHANNEL_CACHE_SECONDS", 300)

    async def scenario():
        guilds = [FakeGuild(1)]
        cache = {}
        await helpers.set_guild_option(1, helpers.GuildOption.STATUS_LOG_CHANNEL, 555)
        first = await log_bot.LogBot._get_status_channels(None, guilds, cache)
        await helpers.set_guild_option(1, helpers.GuildOption.STATUS_LOG_CHANNEL, 777)
        second = await log_bot.LogBot._get_status_channels(None, guilds, cache)
        return first, second

    first, second = asyncio.run(scenario())
    assert first == {1: 555}
    # within TTL the old value is intentionally still served
    assert second == {1: 555}


def test_status_poll_interval_matches_original_default():
    assert log_bot.STATUS_POLL_INTERVAL == 0.5


def test_status_channel_cache_disabled_by_default():
    """Cache off by default = original behavior preserved. Turning it on is an
    explicit opt-in because it delays settings changes."""
    assert log_bot.STATUS_CHANNEL_CACHE_SECONDS == 0


# --------------------------------------------------------------------------- #
# ensure_tables schema caching (perf fix in helpers.py)
# --------------------------------------------------------------------------- #

def test_ensure_tables_only_creates_schema_once_per_path(tmp_path, monkeypatch):
    path = str(tmp_path / "cached.db")
    monkeypatch.setattr(helpers, "DB_PATH", path)

    calls = {"n": 0}
    real_connect = helpers.aiosqlite.connect

    def counting_connect(*args, **kwargs):
        calls["n"] += 1
        return real_connect(*args, **kwargs)

    async def scenario():
        monkeypatch.setattr(helpers.aiosqlite, "connect", counting_connect)
        await helpers.ensure_tables()
        after_first = calls["n"]
        await helpers.ensure_tables()
        await helpers.ensure_tables()
        return after_first, calls["n"]

    after_first, after_third = asyncio.run(scenario())
    assert after_first == 1
    # subsequent calls must not open a connection at all
    assert after_third == 1


def test_ensure_tables_still_creates_schema_for_a_new_path(tmp_path, monkeypatch):
    """The cache is keyed by path, so pointing DB_PATH somewhere new (as the
    tests do) still creates the schema there."""
    async def scenario():
        path_a = str(tmp_path / "a.db")
        monkeypatch.setattr(helpers, "DB_PATH", path_a)
        await helpers.set_guild_option(1, helpers.GuildOption.LOG_CHANNEL, 111)

        path_b = str(tmp_path / "b.db")
        monkeypatch.setattr(helpers, "DB_PATH", path_b)
        await helpers.set_guild_option(1, helpers.GuildOption.LOG_CHANNEL, 222)
        return await helpers.get_guild_option(1, helpers.GuildOption.LOG_CHANNEL)

    assert asyncio.run(scenario()) == 222
