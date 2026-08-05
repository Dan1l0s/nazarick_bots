"""Unit tests for bots/admin_bot.py.

Same approach as test_music.py: `AdminBot.__init__` builds a real disnake bot,
so the pure logic is exercised unbound against fakes instead.

Focus areas:
  - the error-line filter (the always-true-condition bug)
  - get_roles_from_xp: the rank promotion/demotion rules
  - admin/untouchable list mutation against a real sqlite file
  - check_message_content's two-signal spam scoring
"""

import asyncio

import pytest

import bots.admin_bot as admin_bot
import helpers.helpers as helpers


# --------------------------------------------------------------------------- #
# Error-line filter (BUGFIX: original condition was always True)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("line", [
    "[tls @ 0x55f1] Error in the pull function",
    "[https @ 0x7f2a] Will reconnect at 1024",
    "[hls @ 0x9911] Skip ('#EXT-X-VERSION:3')",
    "Stream ends prematurely, retrying with new connection",
])
def test_ignorable_noise_lines_are_filtered(line):
    assert admin_bot.is_ignorable_error_line(line) is True


@pytest.mark.parametrize("line", [
    "Traceback (most recent call last):",
    "RuntimeError: something actually broke",
    "  File \"main.py\", line 42, in <module>",
    "disnake.errors.Forbidden: 403 Forbidden",
])
def test_real_errors_are_not_filtered(line):
    """Regression test for the original bug: the condition contained a bare
    `or "[hls @"` (a truthy constant, missing `in line`), making it always True
    so *every* line was skipped and error reporting silently did nothing."""
    assert admin_bot.is_ignorable_error_line(line) is False


def test_original_buggy_condition_matched_everything():
    """Documents the old behavior so the fix is unambiguous: reproduce the
    original expression and show it swallows a real traceback."""
    line = "Traceback (most recent call last):"
    original = ("[tls @" in line or "[https @" in line or "[hls @"
                or "retrying with new connection" in line)
    assert bool(original) is True          # bug: real error was filtered out
    assert admin_bot.is_ignorable_error_line(line) is False   # fixed


# --------------------------------------------------------------------------- #
# get_roles_from_xp
# --------------------------------------------------------------------------- #

class FakeRole:
    def __init__(self, role_id, position=1):
        self.id = role_id
        self.position = position

    def __lt__(self, other):
        return self.position < other.position

    def __gt__(self, other):
        return self.position > other.position


class FakeGuild:
    """Exposes just get_role() and me.top_role, which is all
    get_roles_from_xp touches."""

    def __init__(self, roles, top_role_position=100):
        self._roles = {r.id: r for r in roles}
        self.me = type("Me", (), {"top_role": FakeRole(-1, top_role_position)})()

    def get_role(self, role_id):
        return self._roles.get(role_id)


def rank(role_id, voice_xp, remove_on_promotion=True):
    return helpers.Rank(role_id, voice_xp, remove_on_promotion)


def test_get_roles_from_xp_keeps_only_highest_exclusive_rank():
    ranks = [rank(1, 10), rank(2, 50), rank(3, 100)]
    guild = FakeGuild([FakeRole(1), FakeRole(2), FakeRole(3)])

    remove, add = admin_bot.AdminBot.get_roles_from_xp(None, 60, ranks, guild)

    # 10 and 50 are earned; only 50 (the highest earned) is kept
    assert add == [2]
    assert sorted(remove) == [1]
    # 100 not earned yet, so untouched either way
    assert 3 not in add and 3 not in remove


def test_get_roles_from_xp_stacks_non_exclusive_ranks():
    ranks = [rank(1, 10, remove_on_promotion=False),
             rank(2, 20, remove_on_promotion=False),
             rank(3, 30, remove_on_promotion=True)]
    guild = FakeGuild([FakeRole(1), FakeRole(2), FakeRole(3)])

    remove, add = admin_bot.AdminBot.get_roles_from_xp(None, 100, ranks, guild)

    # cumulative ranks all stack, plus the single highest exclusive one
    assert sorted(add) == [1, 2, 3]
    assert remove == []


def test_get_roles_from_xp_awards_nothing_below_first_threshold():
    ranks = [rank(1, 10), rank(2, 50)]
    guild = FakeGuild([FakeRole(1), FakeRole(2)])

    remove, add = admin_bot.AdminBot.get_roles_from_xp(None, 5, ranks, guild)

    assert add == []
    assert remove == []


def test_get_roles_from_xp_exact_threshold_counts_as_earned():
    ranks = [rank(1, 10)]
    guild = FakeGuild([FakeRole(1)])

    remove, add = admin_bot.AdminBot.get_roles_from_xp(None, 10, ranks, guild)

    assert add == [1]


def test_get_roles_from_xp_handles_rank_role_above_bot(monkeypatch):
    """Regression test: when the only earned exclusive rank's role sits above
    the bot's own top role, the first loop never assigns max_rank. The original
    then dereferenced None and raised AttributeError; now it grants nothing and
    strips the ungrantable rank instead."""
    ranks = [rank(1, 10)]
    # role position 500 > bot's top_role position 100 -> bot cannot grant it
    guild = FakeGuild([FakeRole(1, position=500)], top_role_position=100)

    remove, add = admin_bot.AdminBot.get_roles_from_xp(None, 50, ranks, guild)

    assert add == []
    assert remove == [1]


def test_get_roles_from_xp_handles_deleted_rank_role():
    """Same guard, other trigger: the rank's role no longer exists in the guild
    at all, so get_role() returns None and the first loop skips it."""
    ranks = [rank(1, 10)]
    guild = FakeGuild([])   # role 1 deleted

    remove, add = admin_bot.AdminBot.get_roles_from_xp(None, 50, ranks, guild)

    assert add == []
    assert remove == [1]


# --------------------------------------------------------------------------- #
# Admin / untouchable lists (sqlite round-trip)
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "bot_database.db")
    monkeypatch.setattr(helpers, "DB_PATH", path)
    return path


class BareAdminBot:
    """Stands in for `self` - none of the list methods touch other attributes."""
    pass


def test_add_admin_is_idempotent(db_path):
    async def scenario():
        me = BareAdminBot()
        assert await admin_bot.AdminBot.add_admin(me, 1, 100) is True
        assert await admin_bot.AdminBot.add_admin(me, 1, 100) is False
        return await helpers.get_guild_option(1, helpers.GuildOption.ADMIN_LIST)

    assert asyncio.run(scenario()) == [100]


def test_remove_admin_round_trip(db_path):
    async def scenario():
        me = BareAdminBot()
        await admin_bot.AdminBot.add_admin(me, 1, 100)
        await admin_bot.AdminBot.add_admin(me, 1, 200)
        assert await admin_bot.AdminBot.remove_admin(me, 1, 100) is True
        assert await admin_bot.AdminBot.remove_admin(me, 1, 100) is False
        return await helpers.get_guild_option(1, helpers.GuildOption.ADMIN_LIST)

    assert asyncio.run(scenario()) == [200]


def test_admin_lists_are_per_guild(db_path):
    async def scenario():
        me = BareAdminBot()
        await admin_bot.AdminBot.add_admin(me, 1, 100)
        await admin_bot.AdminBot.add_admin(me, 2, 999)
        g1 = await helpers.get_guild_option(1, helpers.GuildOption.ADMIN_LIST)
        g2 = await helpers.get_guild_option(2, helpers.GuildOption.ADMIN_LIST)
        return g1, g2

    g1, g2 = asyncio.run(scenario())
    assert g1 == [100]
    assert g2 == [999]


def test_untouchable_round_trip(db_path):
    async def scenario():
        me = BareAdminBot()
        assert await admin_bot.AdminBot.add_untouchable(me, 1, 55) is True
        assert await admin_bot.AdminBot.add_untouchable(me, 1, 55) is False
        assert await admin_bot.AdminBot.remove_untouchable(me, 1, 55) is True
        assert await admin_bot.AdminBot.remove_untouchable(me, 1, 55) is False
        return await helpers.get_guild_option(1, helpers.GuildOption.UNTOUCHABLES_LIST)

    assert asyncio.run(scenario()) == []


# --------------------------------------------------------------------------- #
# check_message_content spam scoring
# --------------------------------------------------------------------------- #

class FakeAuthor:
    def __init__(self, has_guild=True):
        if has_guild:
            self.guild = object()
        self.actions = []

    async def send(self, *args, **kwargs):
        self.actions.append("dm")

    async def ban(self, *args, **kwargs):
        self.actions.append("ban")

    async def timeout(self, *args, **kwargs):
        self.actions.append("timeout")


class FakeMessage:
    def __init__(self, content, author=None):
        self.content = content
        self.author = author or FakeAuthor()
        self.deleted = False

    async def delete(self, *args, **kwargs):
        self.deleted = True


@pytest.fixture
def non_admin(monkeypatch):
    async def fake_is_admin(member):
        return False
    monkeypatch.setattr(helpers, "is_admin", fake_is_admin)


class SpamHost:
    """Minimal stand-in for `self`: check_message_content reads only the
    anti-spam config and history off it."""

    def __init__(self, **overrides):
        from helpers import antispam
        self.spam_config = antispam.SpamConfig(**overrides)
        self.message_history = antispam.MessageHistory()


def check(msg, host=None):
    return asyncio.run(admin_bot.AdminBot.check_message_content(
        host or SpamHost(), msg))


def test_clean_message_is_untouched(non_admin):
    msg = FakeMessage("hello everyone, nice server")
    result = check(msg)
    assert result is False
    assert msg.deleted is False
    assert msg.author.actions == []


def test_single_signal_invite_link_times_out(non_admin):
    msg = FakeMessage("join discord.gg/something")
    result = check(msg)
    assert result is True
    assert msg.deleted is True
    assert "timeout" in msg.author.actions
    assert "ban" not in msg.author.actions


def test_single_signal_keyword_times_out(non_admin):
    msg = FakeMessage("free leaks here")
    result = check(msg)
    assert result is True
    assert "timeout" in msg.author.actions
    assert "ban" not in msg.author.actions


def test_both_signals_ban(non_admin):
    """Two signals still bans, as before - now because 50 + 50 crosses
    ban_score, rather than because a counter reached 2."""
    msg = FakeMessage("free leaks at discord.gg/spam")
    result = check(msg)
    assert msg.deleted is True
    assert "ban" in msg.author.actions
    assert "timeout" not in msg.author.actions
    # Regression test: the ban branch used to fall through to `return False`,
    # so on_message carried on and awarded text XP to the banned user.
    assert result is True


def test_admins_are_exempt(monkeypatch):
    async def fake_is_admin(member):
        return True
    monkeypatch.setattr(helpers, "is_admin", fake_is_admin)

    msg = FakeMessage("free leaks at discord.gg/spam")
    result = check(msg)
    assert msg.deleted is False
    assert msg.author.actions == []
    assert result is False


@pytest.mark.parametrize("content", [
    "join discordapp.com/invite/x",
    "join DISCORDAPP.COM/INVITE/x",
    "join DiscordApp.com/Invite/x",
    "join DISCORD.GG/x",
])
def test_invite_check_is_case_insensitive(non_admin, content):
    """Regression test: the original lowercased the content for the discord.gg
    comparison but compared discordapp.com/invite against the raw string, so
    any uppercase in that URL bypassed the filter entirely."""
    msg = FakeMessage(content)
    result = check(msg)
    assert result is True
    assert msg.deleted is True
    assert "timeout" in msg.author.actions


# --------------------------------------------------------------------------- #
# find_user_guild (BUGFIX: was a for...else that reported false negatives)
# --------------------------------------------------------------------------- #

class FakeChannel:
    def __init__(self, members):
        self.members = members


class FakeMemberRef:
    def __init__(self, member_id):
        self.id = member_id


class FakeSearchGuild:
    def __init__(self, name, voice_channels):
        self.name = name
        self.voice_channels = voice_channels


class FakeBot:
    def __init__(self, guilds):
        self.guilds = guilds


def test_find_user_guild_finds_user_in_first_bot():
    target = FakeSearchGuild("g1", [FakeChannel([FakeMemberRef(42)])])
    bots = [FakeBot([target]), FakeBot([])]
    assert admin_bot.AdminBot.find_user_guild(None, bots, 42) is target


def test_find_user_guild_finds_user_in_last_bot_last_guild():
    """This is the exact case the original got wrong: the outer loop only
    `break`s at the *start* of an iteration, so a hit while scanning the final
    bot let the loop finish normally and fire the `else`, replying
    'Provided user was not found!' despite having found them."""
    target = FakeSearchGuild("last", [FakeChannel([FakeMemberRef(42)])])
    bots = [FakeBot([FakeSearchGuild("other", [FakeChannel([])])]),
            FakeBot([target])]
    assert admin_bot.AdminBot.find_user_guild(None, bots, 42) is target


def test_find_user_guild_returns_none_when_absent():
    bots = [FakeBot([FakeSearchGuild("g", [FakeChannel([FakeMemberRef(1)])])])]
    assert admin_bot.AdminBot.find_user_guild(None, bots, 999) is None


def test_find_user_guild_skips_empty_channels():
    target = FakeSearchGuild("g", [FakeChannel([]), FakeChannel([FakeMemberRef(7)])])
    assert admin_bot.AdminBot.find_user_guild(None, [FakeBot([target])], 7) is target


def test_find_user_guild_handles_no_bots():
    assert admin_bot.AdminBot.find_user_guild(None, [], 1) is None
