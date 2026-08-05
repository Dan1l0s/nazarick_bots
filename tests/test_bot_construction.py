"""Construction smoke tests: build every bot for real and assert the command
surface it registers.

No network and no tokens are used - `commands.InteractionBot` is constructed
locally and `bot.start()` is never called. This is the only test module that
executes each bot's `__init__`, which is where all the event handlers and slash
commands are declared, so it's what catches:

  - a decorator that stops registering a command (silent in every other check)
  - a name collision between two commands or subcommands
  - an import or attribute error at class-definition time
  - the cross-bot wiring in main.py not linking up

`tools/compare_commands.py` does the same thing but diffs the result against the
original repo; these assertions pin the expected shape so the suite fails even
without the original checkout to compare against.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

import main
from bots.admin_bot import AdminBot
from bots.log_bot import LogBot
from bots.music_instance import MusicBotInstance
from bots.music_leader import MusicBotLeader

# Every command each bot is expected to register, as of the refactor. Update
# these deliberately when adding a command - an accidental change fails here.
EXPECTED_LEADER_COMMANDS = {
    "help", "pause", "play", "playnow", "queue", "radio",
    "repeat", "shuffle", "skip", "stop", "wrong",
}
EXPECTED_ADMIN_COMMANDS = {
    "admin", "bitrate", "black_hole", "clear", "dm_user", "find_user",
    "get_guild_info", "guilds_list", "help", "manage_untouchable", "message",
    "move_user", "music_usage_info", "purge", "rank", "set", "summon_user", "xp",
}
EXPECTED_LOGGER_COMMANDS = {"help", "set", "welcome"}


@pytest.fixture
def pool():
    executor = ThreadPoolExecutor(max_workers=1)
    yield executor
    executor.shutdown(wait=False)


@pytest.fixture
def leader(pool):
    return MusicBotLeader("music_main", "token", pool)


@pytest.fixture
def instance(pool):
    return MusicBotInstance("music_assistant1", "token", pool)


@pytest.fixture
def admin():
    return AdminBot("moderate", "token")


@pytest.fixture
def logger_bot():
    return LogBot("logs", "token")


def command_names(bot):
    return {c.name for c in bot.bot.slash_commands}


def subcommand_names(bot, command_name):
    for command in bot.bot.slash_commands:
        if command.name == command_name:
            return set(getattr(command, "children", {}) or {})
    raise AssertionError(f"command {command_name!r} not registered")


# --------------------------------------------------------------------------- #
# Command registration
# --------------------------------------------------------------------------- #

def test_leader_registers_expected_commands(leader):
    assert command_names(leader) == EXPECTED_LEADER_COMMANDS


def test_admin_registers_expected_commands(admin):
    assert command_names(admin) == EXPECTED_ADMIN_COMMANDS


def test_logger_registers_expected_commands(logger_bot):
    assert command_names(logger_bot) == EXPECTED_LOGGER_COMMANDS


def test_plain_instance_registers_no_commands(instance):
    """Assistant bots are driven entirely by the leader; if they registered
    their own commands the user would see duplicates in the picker."""
    assert command_names(instance) == set()


@pytest.mark.parametrize("group,expected", [
    ("admin", {"add", "remove", "list"}),
    ("rank", {"add", "remove", "list", "reset"}),
    ("xp", {"reset", "show", "top", "set"}),
    ("set", {"private", "giveaway"}),
])
def test_admin_subcommand_groups(admin, group, expected):
    assert subcommand_names(admin, group) == expected


def test_logger_set_group_has_logs_subgroup(logger_bot):
    assert subcommand_names(logger_bot, "set") == {"logs"}


def test_no_duplicate_command_names(leader, admin, logger_bot):
    """disnake silently keeps only the last registration on a name collision,
    so a duplicate would shrink the set rather than raise."""
    for bot, expected in ((leader, EXPECTED_LEADER_COMMANDS),
                          (admin, EXPECTED_ADMIN_COMMANDS),
                          (logger_bot, EXPECTED_LOGGER_COMMANDS)):
        assert len(bot.bot.slash_commands) == len(expected)


# --------------------------------------------------------------------------- #
# Initial state
# --------------------------------------------------------------------------- #

def test_leader_includes_itself_as_an_instance(leader):
    """A single-bot deployment works because the leader is its own instance."""
    assert leader.instances == [leader]


def test_instance_starts_with_no_guild_state(instance):
    assert instance.states == {}
    assert instance.on_ready_flag is False


def test_admin_starts_with_no_references(admin):
    assert admin.music_instances == []
    assert admin.log_bot is None
    assert admin.on_ready_flag is False


def test_logger_starts_with_empty_kick_ban_counter(logger_bot):
    assert logger_bot.kick_bans == {}
    assert logger_bot.on_ready_flag is False


def test_bots_expose_their_configured_name_and_token(leader, admin):
    assert leader.name == "music_main"
    assert leader.token == "token"
    assert admin.name == "moderate"


# --------------------------------------------------------------------------- #
# Help text
# --------------------------------------------------------------------------- #

def test_leader_help_mentions_every_music_command(leader):
    text = leader.help()
    for command in ["/play", "/stop", "/skip", "/queue", "/shuffle",
                    "/wrong", "/repeat", "/pause", "/playnow", "/radio"]:
        assert command in text


def test_admin_help_mentions_key_commands(admin):
    text = admin.help()
    for command in ["/admin add", "/clear", "/bitrate", "/purge",
                    "/xp show", "/rank list", "/set private channel"]:
        assert command in text


def test_logger_help_mentions_every_command(logger_bot):
    text = logger_bot.help()
    for command in ["/set logs common", "/set logs status",
                    "/set logs welcome", "/welcome"]:
        assert command in text


# --------------------------------------------------------------------------- #
# Cross-bot wiring (the object graph main.py builds)
# --------------------------------------------------------------------------- #

def test_wiring_links_leader_instances_and_admin_references(leader, instance, admin, logger_bot):
    leader.add_instance(instance)
    admin.add_music_instance(leader)
    admin.add_music_instance(instance)
    admin.set_log_bot(logger_bot)

    assert [i.name for i in leader.instances] == ["music_main", "music_assistant1"]
    assert [i.name for i in admin.music_instances] == ["music_main", "music_assistant1"]
    assert admin.log_bot is logger_bot


def test_music_usage_report_shows_idle_and_busy(leader, instance, admin):
    """check_music_bots() walks every instance's per-guild state; with no state
    at all every bot must report IDLE rather than raising."""
    admin.add_music_instance(leader)
    admin.add_music_instance(instance)

    report = asyncio.run(admin.check_music_bots())

    assert "music_main: IDLE" in report
    assert "music_assistant1: IDLE" in report
    assert report.startswith("```") and report.endswith("```")


def test_music_usage_report_marks_busy_instance(leader, admin):
    from bots.music_instance import GuildState, Song

    async def scenario():
        state = GuildState(guild=None)
        song = Song()
        song.track_info.set_result({"title": "T", "duration": 60})
        state.current_song = song
        leader.states[123] = state
        admin.add_music_instance(leader)
        return await admin.check_music_bots()

    report = asyncio.run(scenario())
    assert "BUSY" in report
    assert "123" in report


def test_music_usage_report_handles_unresolved_track(leader, admin):
    from bots.music_instance import GuildState, Song

    async def scenario():
        state = GuildState(guild=None)
        state.current_song = Song()          # still loading
        leader.states[456] = state
        admin.add_music_instance(leader)
        return await admin.check_music_bots()

    assert "Processing track" in asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# main.py end-to-end wiring
# --------------------------------------------------------------------------- #

def test_main_builds_and_wires_every_bot_type(monkeypatch):
    """Runs main() far enough to construct and wire all four bot types, with
    the network calls stubbed out."""
    import configs.private_config as private_config

    monkeypatch.setattr(private_config, "bots", [
        ["music_main", "MusicLeader", "t1"],
        ["music_assistant1", "MusicInstance", "t2"],
        ["logs", "Logger", "t3"],
        ["moderate", "Admin", "t4"],
    ], raising=False)

    started = []

    async def fake_run(self):
        started.append(self.name)

    monkeypatch.setattr(MusicBotLeader, "run", fake_run, raising=False)
    monkeypatch.setattr(MusicBotInstance, "run", fake_run, raising=False)
    monkeypatch.setattr(AdminBot, "run", fake_run, raising=False)
    monkeypatch.setattr(LogBot, "run", fake_run, raising=False)
    monkeypatch.setattr(main.os, "chdir", lambda path: None)

    asyncio.run(main.main())

    assert sorted(started) == ["logs", "moderate", "music_assistant1", "music_main"]


def test_main_ignores_unknown_bot_type(monkeypatch, capsys):
    import configs.private_config as private_config

    monkeypatch.setattr(private_config, "bots", [
        ["mystery", "NotARealType", "t1"],
    ], raising=False)
    monkeypatch.setattr(main.os, "chdir", lambda path: None)

    asyncio.run(main.main())

    assert "There is no bot type NotARealType" in capsys.readouterr().out


def test_main_stops_on_invalid_configuration(monkeypatch):
    """Two MusicLeaders is rejected by validate_bots; main() must not start
    anything."""
    import configs.private_config as private_config

    monkeypatch.setattr(private_config, "bots", [
        ["a", "MusicLeader", "t1"],
        ["b", "MusicLeader", "t2"],
    ], raising=False)
    monkeypatch.setattr(main.os, "chdir", lambda path: None)

    started = []

    async def fake_run(self):
        started.append(self.name)

    monkeypatch.setattr(MusicBotLeader, "run", fake_run, raising=False)

    async def scenario():
        # main() calls loop.stop() on invalid config, which asyncio.run objects
        # to; call it directly on the running loop instead.
        await main.main()

    try:
        asyncio.run(scenario())
    except RuntimeError:
        pass  # loop.stop() inside asyncio.run

    assert started == []
