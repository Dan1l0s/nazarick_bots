"""Tests for the slash-command bodies themselves.

disnake stores each command's function on `.callback`, so the handlers can be
invoked directly with a fake interaction - no gateway connection required. This
is where the **authorization** logic lives (`is_admin`, `is_supreme_being`,
server-owner checks), so it's worth testing precisely: a regression here means
unauthorized users gaining moderator powers.

Each test asserts on what the user is told, which is also the observable
contract of the command.
"""

import asyncio
import types
from concurrent.futures import ThreadPoolExecutor

import pytest

import configs.private_config as private_config
import helpers.helpers as helpers
from bots.admin_bot import AdminBot
from bots.log_bot import LogBot
from bots.music_leader import MusicBotLeader


# --------------------------------------------------------------------------- #
# Fake interaction
# --------------------------------------------------------------------------- #

class FakeResponse:
    def __init__(self):
        self.deferred = False
        self.modals = []

    async def defer(self, *args, **kwargs):
        self.deferred = True

    async def send_modal(self, modal):
        self.modals.append(modal)


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kwargs):
        self.sent.append(content if content is not None else kwargs.get("embed"))
        return types.SimpleNamespace(delete=_noop, edit=_noop)

    async def purge(self, **kwargs):
        self.sent.append(("purge", kwargs))
        return []


async def _noop(*args, **kwargs):
    return None


class FakeInter:
    """Covers the surface the command bodies touch."""

    def __init__(self, author, guild, channel=None):
        self.author = author
        self.guild = guild
        self.channel = channel or FakeChannel()
        self.response = FakeResponse()
        self.replies = []
        self.deleted = False

    async def send(self, content=None, **kwargs):
        self.replies.append(content if content is not None else kwargs.get("embed"))

    async def edit_original_response(self, content=None, **kwargs):
        self.replies.append(content if content is not None else kwargs.get("embed"))

    async def delete_original_response(self):
        self.deleted = True

    @property
    def last_reply(self):
        return self.replies[-1] if self.replies else None


class FakeUser:
    def __init__(self, user_id, name="User"):
        self.id = user_id
        self.name = name
        self.display_name = name
        self.mention = f"<@{user_id}>"
        self.timeouts = []

    async def timeout(self, **kwargs):
        self.timeouts.append(kwargs)


class FakeRole:
    def __init__(self, role_id=10, position=5, managed=False):
        self.id = role_id
        self.position = position
        self.managed = managed
        self.name = f"Role{role_id}"
        self.mention = f"<@&{role_id}>"

    def __lt__(self, other):
        return self.position < other.position

    def __ge__(self, other):
        return self.position >= other.position

    def __gt__(self, other):
        return self.position > other.position


class FakeGuild:
    def __init__(self, guild_id=5, owner_id=1, premium_tier=0):
        self.id = guild_id
        self.name = "Guild"
        self.owner_id = owner_id
        self.owner = FakeUser(owner_id, "Owner")
        self.premium_tier = premium_tier
        self.voice_channels = []
        self.me = types.SimpleNamespace(top_role=FakeRole(999, position=100))
        self.icon = types.SimpleNamespace(url="https://example.invalid/i.png")
        self._roles = {}

    def get_role(self, role_id):
        return self._roles.get(role_id)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "bot_database.db")
    monkeypatch.setattr(helpers, "DB_PATH", path)
    return path


@pytest.fixture
def admin_bot_fixture():
    return AdminBot("moderate", "token")


@pytest.fixture
def logger_bot_fixture():
    return LogBot("logs", "token")


@pytest.fixture
def leader_fixture():
    pool = ThreadPoolExecutor(max_workers=1)
    bot = MusicBotLeader("music_main", "token", pool)
    yield bot
    pool.shutdown(wait=False)


def command(bot, name, *path):
    """Resolves a (sub)command's callback by name."""
    node = {c.name: c for c in bot.bot.slash_commands}[name]
    for part in path:
        node = node.children[part]
    return node.callback


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --------------------------------------------------------------------------- #
# Authorization: /admin add|remove require server ownership
# --------------------------------------------------------------------------- #

def test_admin_add_rejects_non_owner(db_path, admin_bot_fixture, monkeypatch):
    monkeypatch.setattr(private_config, "supreme_beings", [], raising=False)
    guild = FakeGuild(owner_id=1)
    inter = FakeInter(FakeUser(2, "NotOwner"), guild)

    run(command(admin_bot_fixture, "admin", "add")(inter, user=FakeUser(3)))

    assert "not the server owner" in inter.last_reply


def test_admin_add_allows_owner(db_path, admin_bot_fixture, monkeypatch):
    monkeypatch.setattr(private_config, "supreme_beings", [], raising=False)
    guild = FakeGuild(owner_id=1)
    inter = FakeInter(FakeUser(1, "Owner"), guild)

    run(command(admin_bot_fixture, "admin", "add")(inter, user=FakeUser(3)))

    assert "is now an admin" in inter.last_reply


def test_admin_add_is_idempotent(db_path, admin_bot_fixture, monkeypatch):
    monkeypatch.setattr(private_config, "supreme_beings", [], raising=False)
    guild = FakeGuild(owner_id=1)
    add = command(admin_bot_fixture, "admin", "add")

    run(add(FakeInter(FakeUser(1), guild), user=FakeUser(3)))
    second = FakeInter(FakeUser(1), guild)
    run(add(second, user=FakeUser(3)))

    assert "already an admin" in second.last_reply


def test_admin_remove_refuses_to_demote_the_owner(db_path, admin_bot_fixture, monkeypatch):
    monkeypatch.setattr(private_config, "supreme_beings", [], raising=False)
    guild = FakeGuild(owner_id=1)
    inter = FakeInter(FakeUser(1), guild)

    run(command(admin_bot_fixture, "admin", "remove")(inter, user=guild.owner))

    assert "cannot be deleted from admin list" in inter.last_reply


def test_admin_remove_reports_when_user_was_not_an_admin(db_path, admin_bot_fixture, monkeypatch):
    monkeypatch.setattr(private_config, "supreme_beings", [], raising=False)
    guild = FakeGuild(owner_id=1)
    inter = FakeInter(FakeUser(1), guild)

    run(command(admin_bot_fixture, "admin", "remove")(inter, user=FakeUser(77)))

    assert "isn't an admin" in inter.last_reply


def test_supreme_being_bypasses_the_owner_check(db_path, admin_bot_fixture, monkeypatch):
    monkeypatch.setattr(private_config, "supreme_beings", [42], raising=False)
    guild = FakeGuild(owner_id=1)
    inter = FakeInter(FakeUser(42, "Supreme"), guild)

    run(command(admin_bot_fixture, "admin", "add")(inter, user=FakeUser(3)))

    assert "is now an admin" in inter.last_reply


def test_admin_list_posts_an_embed(db_path, admin_bot_fixture):
    guild = FakeGuild()
    inter = FakeInter(FakeUser(1), guild)
    admin_bot_fixture.bot.get_user = lambda uid: FakeUser(uid)

    run(command(admin_bot_fixture, "admin", "list")(inter))

    assert inter.deleted is True
    assert inter.channel.sent          # embed posted to the channel


# --------------------------------------------------------------------------- #
# Authorization: admin-gated commands
# --------------------------------------------------------------------------- #

@pytest.fixture
def as_admin(monkeypatch):
    async def yes(member):
        return True
    monkeypatch.setattr(helpers, "is_admin", yes)


@pytest.fixture
def as_non_admin(monkeypatch):
    async def no(member):
        return False
    monkeypatch.setattr(helpers, "is_admin", no)


@pytest.mark.parametrize("path", [
    ("rank", "add"),
    ("rank", "remove"),
    ("rank", "reset"),
    ("xp", "reset"),
    ("set", "private", "category"),
    ("set", "private", "channel"),
    ("set", "giveaway", "message"),
    ("set", "giveaway", "role"),
])
def test_admin_gated_commands_reject_non_admins(db_path, admin_bot_fixture, as_non_admin, path):
    inter = FakeInter(FakeUser(2), FakeGuild())
    kwargs = {}
    if path == ("rank", "add"):
        kwargs = {"role": FakeRole(), "voice_xp": 10, "remove_on_promotion": True}
    elif path == ("rank", "remove"):
        kwargs = {"role": FakeRole()}

    run(command(admin_bot_fixture, *path)(inter, **kwargs))

    assert "not an admin" in inter.last_reply


def test_bitrate_rejects_non_admins(db_path, admin_bot_fixture, as_non_admin):
    inter = FakeInter(FakeUser(2), FakeGuild())
    run(command(admin_bot_fixture, "bitrate")(inter))
    assert "not the Supreme Being" in inter.last_reply


def test_clear_rejects_non_admins(db_path, admin_bot_fixture, as_non_admin):
    inter = FakeInter(FakeUser(2), FakeGuild())
    run(command(admin_bot_fixture, "clear")(inter, amount=5))
    assert "Unathorized attempt to clear messages!" in inter.last_reply


def test_clear_purges_amount_plus_the_command_message(db_path, admin_bot_fixture, as_admin):
    inter = FakeInter(FakeUser(1), FakeGuild())
    run(command(admin_bot_fixture, "clear")(inter, amount=5))
    purge_call = [c for c in inter.channel.sent if isinstance(c, tuple) and c[0] == "purge"]
    assert purge_call and purge_call[0][1]["limit"] == 6
    assert "Cleared 5 messages" in inter.replies


# --------------------------------------------------------------------------- #
# Rank management
# --------------------------------------------------------------------------- #

def test_rank_add_rejects_managed_roles(db_path, admin_bot_fixture, as_admin):
    inter = FakeInter(FakeUser(1), FakeGuild())
    run(command(admin_bot_fixture, "rank", "add")(
        inter, role=FakeRole(managed=True), voice_xp=100))
    assert "managed by some kind of integration" in inter.last_reply


def test_rank_add_rejects_roles_above_the_bot(db_path, admin_bot_fixture, as_admin):
    inter = FakeInter(FakeUser(1), FakeGuild())
    run(command(admin_bot_fixture, "rank", "add")(
        inter, role=FakeRole(position=500), voice_xp=100))
    assert "must be lower that my highest role" in inter.last_reply


def test_rank_add_then_duplicate(db_path, admin_bot_fixture, as_admin):
    """NOTE: `remove_on_promotion` is passed explicitly. Calling the callback
    directly bypasses disnake's parameter resolution, so its declared default
    would arrive as a ParamInfo object rather than True."""
    guild = FakeGuild()
    add = command(admin_bot_fixture, "rank", "add")

    first = FakeInter(FakeUser(1), guild)
    run(add(first, role=FakeRole(10), voice_xp=100, remove_on_promotion=True))
    assert "Added new rank" in first.last_reply

    second = FakeInter(FakeUser(1), guild)
    run(add(second, role=FakeRole(10), voice_xp=100, remove_on_promotion=True))
    assert "There is already a rank" in second.last_reply


def test_rank_remove_reports_unknown_rank(db_path, admin_bot_fixture, as_admin):
    inter = FakeInter(FakeUser(1), FakeGuild())
    run(command(admin_bot_fixture, "rank", "remove")(inter, role=FakeRole(77)))
    assert "There is no rank" in inter.last_reply


def test_rank_list_when_empty(db_path, admin_bot_fixture, as_admin):
    inter = FakeInter(FakeUser(1), FakeGuild())
    run(command(admin_bot_fixture, "rank", "list")(inter))
    assert "There are no ranks yet" in inter.last_reply


def test_rank_reset_clears_every_rank(db_path, admin_bot_fixture, as_admin):
    guild = FakeGuild()
    run(command(admin_bot_fixture, "rank", "add")(
        FakeInter(FakeUser(1), guild), role=FakeRole(10), voice_xp=100,
        remove_on_promotion=True))

    inter = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "rank", "reset")(inter))
    assert "All ranks have been reset" in inter.last_reply

    remaining = run(helpers.get_guild_option(guild.id, helpers.GuildOption.RANK_LIST))
    assert remaining == []


# --------------------------------------------------------------------------- #
# XP commands
# --------------------------------------------------------------------------- #

def test_xp_set_voice_and_text(db_path, admin_bot_fixture):
    guild = FakeGuild()
    member = FakeUser(7)
    set_xp = command(admin_bot_fixture, "xp", "set")

    inter = FakeInter(FakeUser(1), guild)
    run(set_xp(inter, member=member, type="Voice", xp=250))
    assert "250 voice xp" in inter.last_reply

    inter2 = FakeInter(FakeUser(1), guild)
    run(set_xp(inter2, member=member, type="Text", xp=30))
    assert "30 text xp" in inter2.last_reply


def test_xp_reset_wipes_the_guild(db_path, admin_bot_fixture, as_admin):
    guild = FakeGuild()
    run(command(admin_bot_fixture, "xp", "set")(
        FakeInter(FakeUser(1), guild), member=FakeUser(7), type="Voice", xp=100))

    inter = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "xp", "reset")(inter))
    assert "All user xp have been reset" in inter.last_reply

    assert run(helpers.get_user_xp(guild.id, 7)) == (0, 0)


def test_xp_show_reports_totals(db_path, admin_bot_fixture):
    guild = FakeGuild()
    member = FakeUser(7)
    member.guild = guild
    member.display_avatar = types.SimpleNamespace(url="https://example.invalid/a.png")
    run(command(admin_bot_fixture, "xp", "set")(
        FakeInter(FakeUser(1), guild), member=member, type="Voice", xp=42))

    inter = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "xp", "show")(inter, member=member))
    # an embed was sent rather than plain text
    assert inter.last_reply is not None


# --------------------------------------------------------------------------- #
# Giveaway + private channel settings
# --------------------------------------------------------------------------- #

def test_set_private_category_enables_and_disables(db_path, admin_bot_fixture, as_admin):
    guild = FakeGuild()
    category = types.SimpleNamespace(id=222, name="Private")

    on = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "set", "private", "category")(on, category=category))
    assert "will be created in Private" in on.last_reply

    off = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "set", "private", "category")(off, category=None))
    assert "are disabled" in off.last_reply


def test_set_private_channel_enables_and_disables(db_path, admin_bot_fixture, as_admin):
    guild = FakeGuild()
    channel = types.SimpleNamespace(id=333, mention="<#333>")

    on = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "set", "private", "channel")(on, voice_channel=channel))
    assert "<#333>" in on.last_reply

    off = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "set", "private", "channel")(off, voice_channel=None))
    assert "are disabled" in off.last_reply


def test_set_giveaway_role_enables_and_disables(db_path, admin_bot_fixture, as_admin):
    guild = FakeGuild()

    on = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "set", "giveaway", "role")(on, role=FakeRole(44)))
    assert "was set to" in on.last_reply

    off = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "set", "giveaway", "role")(off, role=None))
    assert "was removed" in off.last_reply


def test_set_giveaway_message_stores_the_id(db_path, admin_bot_fixture, as_admin):
    guild = FakeGuild()
    admin_bot_fixture.bot.get_message = lambda mid: None

    inter = FakeInter(FakeUser(1), guild)
    run(command(admin_bot_fixture, "set", "giveaway", "message")(inter, message_id="12345"))
    assert "12345" in inter.last_reply

    stored = run(helpers.get_guild_option(guild.id, helpers.GuildOption.GIVEAWAY_MESSAGE))
    assert stored == 12345


# --------------------------------------------------------------------------- #
# Supreme-being gated commands
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,kwargs", [
    ("guilds_list", {}),
    ("manage_untouchable", {"user_id": "1", "guild_id": "2", "type": "Add"}),
])
def test_supreme_only_commands_reject_others(db_path, admin_bot_fixture, monkeypatch, name, kwargs):
    monkeypatch.setattr(private_config, "supreme_beings", [999], raising=False)
    inter = FakeInter(FakeUser(2), FakeGuild())
    run(command(admin_bot_fixture, name)(inter, **kwargs))
    assert "not the Supreme Being" in inter.last_reply


def test_manage_untouchable_add_and_remove(db_path, admin_bot_fixture, monkeypatch):
    monkeypatch.setattr(private_config, "supreme_beings", [1], raising=False)
    manage = command(admin_bot_fixture, "manage_untouchable")

    added = FakeInter(FakeUser(1), FakeGuild())
    run(manage(added, user_id="55", guild_id="5", type="Add"))
    assert "is now an untouchable user" in added.last_reply

    again = FakeInter(FakeUser(1), FakeGuild())
    run(manage(again, user_id="55", guild_id="5", type="Add"))
    assert "is already an untouchable user" in again.last_reply

    removed = FakeInter(FakeUser(1), FakeGuild())
    run(manage(removed, user_id="55", guild_id="5", type="Remove"))
    assert "is no longer an untouchable user" in removed.last_reply


# --------------------------------------------------------------------------- #
# Logger bot settings commands
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("sub,option", [
    ("common", helpers.GuildOption.LOG_CHANNEL),
    ("status", helpers.GuildOption.STATUS_LOG_CHANNEL),
    ("welcome", helpers.GuildOption.WELCOME_CHANNEL),
])
def test_logger_set_commands_store_and_clear(db_path, logger_bot_fixture, as_admin, sub, option):
    guild = FakeGuild()
    channel = types.SimpleNamespace(id=888, mention="<#888>")

    on = FakeInter(FakeUser(1), guild)
    run(command(logger_bot_fixture, "set", "logs", sub)(on, channel=channel))
    assert run(helpers.get_guild_option(guild.id, option)) == 888

    off = FakeInter(FakeUser(1), guild)
    run(command(logger_bot_fixture, "set", "logs", sub)(off, channel=None))
    assert run(helpers.get_guild_option(guild.id, option)) is None
    assert "disabled" in off.last_reply


@pytest.mark.parametrize("sub", ["common", "status", "welcome"])
def test_logger_set_commands_reject_non_admins(db_path, logger_bot_fixture, as_non_admin, sub):
    inter = FakeInter(FakeUser(2), FakeGuild())
    run(command(logger_bot_fixture, "set", "logs", sub)(inter, channel=None))
    assert "not an admin" in inter.last_reply


# --------------------------------------------------------------------------- #
# /help on every bot
# --------------------------------------------------------------------------- #

def test_help_commands_send_an_embed(db_path, admin_bot_fixture, logger_bot_fixture, leader_fixture):
    for bot in (admin_bot_fixture, logger_bot_fixture, leader_fixture):
        inter = FakeInter(FakeUser(1), FakeGuild())
        run(command(bot, "help")(inter))
        assert inter.last_reply is not None
        assert inter.response.deferred is True


# --------------------------------------------------------------------------- #
# Music leader command routing
# --------------------------------------------------------------------------- #

def test_play_requires_the_user_to_be_in_voice(db_path, leader_fixture):
    author = FakeUser(1)
    author.voice = None
    inter = FakeInter(author, FakeGuild())

    run(command(leader_fixture, "play")(inter, query="test"))

    assert inter.last_reply == "You are not in voice channel"


def test_play_reports_when_no_instance_is_free(db_path, leader_fixture):
    author = FakeUser(1)
    author.voice = types.SimpleNamespace(channel=object())
    inter = FakeInter(author, FakeGuild())
    # leader has no state for this guild, so it is neither playing nor available
    run(command(leader_fixture, "play")(inter, query="test"))

    assert "There are no available bots" in inter.last_reply


@pytest.mark.parametrize("name", ["pause", "repeat", "stop", "skip", "queue", "wrong", "shuffle"])
def test_playback_commands_report_when_no_bot_is_present(db_path, leader_fixture, name):
    author = FakeUser(1)
    author.voice = types.SimpleNamespace(channel=object())
    inter = FakeInter(author, FakeGuild())

    run(command(leader_fixture, name)(inter))

    assert inter.last_reply == "There are no bots in your voice channel"


def test_radio_requires_voice(db_path, leader_fixture):
    author = FakeUser(1)
    author.voice = None
    inter = FakeInter(author, FakeGuild())
    run(command(leader_fixture, "radio")(inter, url="http://example.invalid/s"))
    assert inter.last_reply == "You are not in voice channel"


def test_playnow_requires_voice(db_path, leader_fixture):
    author = FakeUser(1)
    author.voice = None
    inter = FakeInter(author, FakeGuild())
    run(command(leader_fixture, "playnow")(inter, query="x"))
    assert inter.last_reply == "You are not in voice channel"
