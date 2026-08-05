"""Unit tests for the moderation and role-management helpers in helpers/helpers.py.

This is the code that decides who gets un-muted, who gets timed out for pinging
the bot, and who gets punished for disconnecting an admin - i.e. the parts that
take punitive action automatically. Worth pinning precisely.
"""

import asyncio
import types
from datetime import datetime, timedelta, timezone

import pytest

import configs.private_config as private_config
import helpers.helpers as helpers


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

class FakeVoiceState:
    def __init__(self, mute=False, deaf=False):
        self.mute = mute
        self.deaf = deaf


class FakeMember:
    def __init__(self, member_id=1, guild=None, mute=False, deaf=False, roles=None):
        self.id = member_id
        self.guild = guild
        self.voice = FakeVoiceState(mute, deaf)
        self.roles = roles or []
        self.edits = []
        self.timeouts = []
        self.moves = []
        self.added_roles = []
        self.removed_roles = []
        self.dms = []

    async def edit(self, **kwargs):
        self.edits.append(kwargs)

    async def timeout(self, **kwargs):
        self.timeouts.append(kwargs)

    async def move_to(self, channel, **kwargs):
        self.moves.append(channel)

    async def add_roles(self, *roles, **kwargs):
        self.added_roles.extend(roles)

    async def remove_roles(self, *roles, **kwargs):
        self.removed_roles.extend(roles)

    async def send(self, *args, **kwargs):
        self.dms.append((args, kwargs))


class FakeAuditEntry:
    def __init__(self, user, seconds_ago=0):
        self.user = user
        self.created_at = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)


class FakeAuditLogs:
    """Mimics `guild.audit_logs(...)` -> object with `.flatten()`."""

    def __init__(self, entries):
        self._entries = entries

    async def flatten(self):
        return self._entries


class FakeGuild:
    def __init__(self, guild_id=1, audit_entries=None, raise_on_audit=False):
        self.id = guild_id
        self.name = "Guild"
        self._audit_entries = audit_entries or []
        self._raise = raise_on_audit
        self.me = types.SimpleNamespace(
            guild_permissions=types.SimpleNamespace(manage_roles=True),
            top_role=FakeRole(999, position=100),
        )
        self.roles_by_id = {}

    def audit_logs(self, limit=1, action=None):
        if self._raise:
            raise RuntimeError("no audit log access")
        return FakeAuditLogs(self._audit_entries[:limit])

    def get_role(self, role_id):
        return self.roles_by_id.get(role_id)


class FakeRole:
    def __init__(self, role_id, position=1, managed=False, name="Role"):
        self.id = role_id
        self.position = position
        self.managed = managed
        self.name = name
        self.mention = f"<@&{role_id}>"

    def __lt__(self, other):
        return self.position < other.position

    def __gt__(self, other):
        return self.position > other.position

    def __eq__(self, other):
        return isinstance(other, FakeRole) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "bot_database.db")
    monkeypatch.setattr(helpers, "DB_PATH", path)
    return path


@pytest.fixture
def bot_ids(monkeypatch):
    monkeypatch.setattr(private_config, "bot_ids", {"music": 1001, "admin": 1002}, raising=False)
    return private_config.bot_ids


# --------------------------------------------------------------------------- #
# is_admin / is_untouchable
# --------------------------------------------------------------------------- #

def test_is_admin_reads_the_guild_admin_list(db_path):
    async def scenario():
        guild = FakeGuild(guild_id=5)
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        admin = FakeMember(42, guild)
        outsider = FakeMember(99, guild)
        return await helpers.is_admin(admin), await helpers.is_admin(outsider)

    is_admin, is_not = asyncio.run(scenario())
    assert is_admin is True
    assert bool(is_not) is False


def test_supreme_being_is_always_admin(db_path, monkeypatch):
    monkeypatch.setattr(private_config, "supreme_beings", [777], raising=False)

    async def scenario():
        return await helpers.is_admin(FakeMember(777, FakeGuild(5)))

    assert asyncio.run(scenario()) is True


def test_is_untouchable(db_path):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.UNTOUCHABLES_LIST, [42])
        return (await helpers.is_untouchable(FakeMember(42, FakeGuild(5))),
                await helpers.is_untouchable(FakeMember(43, FakeGuild(5))))

    touched, untouched = asyncio.run(scenario())
    assert touched is True
    assert bool(untouched) is False


# --------------------------------------------------------------------------- #
# unmute_bots
# --------------------------------------------------------------------------- #

def test_unmute_bots_unmutes_and_undeafens_a_known_bot(bot_ids):
    async def scenario():
        member = FakeMember(1001, FakeGuild(), mute=True, deaf=True)
        result = await helpers.unmute_bots(member)
        return result, member

    result, member = asyncio.run(scenario())
    assert result is True
    assert {"mute": False} in member.edits
    assert {"deafen": False} in member.edits


def test_unmute_bots_ignores_non_bot_members(bot_ids):
    async def scenario():
        member = FakeMember(5, FakeGuild(), mute=True, deaf=True)
        return await helpers.unmute_bots(member), member

    result, member = asyncio.run(scenario())
    assert result is False
    assert member.edits == []


def test_unmute_bots_noop_when_bot_is_not_muted(bot_ids):
    async def scenario():
        member = FakeMember(1001, FakeGuild(), mute=False, deaf=False)
        return await helpers.unmute_bots(member), member

    result, member = asyncio.run(scenario())
    assert result is False
    assert member.edits == []


# --------------------------------------------------------------------------- #
# unmute_admin - retaliation against whoever muted an admin
# --------------------------------------------------------------------------- #

def test_unmute_admin_punishes_the_recent_muter(db_path, bot_ids, monkeypatch):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        attacker = FakeMember(66, None)
        guild = FakeGuild(5, audit_entries=[
            FakeAuditEntry(FakeMember(42), 0),      # entry[0] ignored
            FakeAuditEntry(attacker, 1),            # entry[1] is the actor
        ])
        admin = FakeMember(42, guild, mute=True)
        result = await helpers.unmute_admin(admin)
        return result, admin, attacker

    result, admin, attacker = asyncio.run(scenario())
    assert result is True
    assert {"mute": False} in admin.edits
    assert attacker.moves == [None]                 # kicked from voice
    assert attacker.timeouts and attacker.timeouts[0]["duration"] == 60


def test_unmute_admin_ignores_stale_audit_entries(db_path, bot_ids):
    """Only actions within the last 2 seconds are attributed - anything older
    is unrelated to this un-mute."""
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        attacker = FakeMember(66, None)
        guild = FakeGuild(5, audit_entries=[
            FakeAuditEntry(FakeMember(42), 0),
            FakeAuditEntry(attacker, 60),           # a minute ago
        ])
        await helpers.unmute_admin(FakeMember(42, guild, mute=True))
        return attacker

    attacker = asyncio.run(scenario())
    assert attacker.timeouts == []


def test_unmute_admin_does_not_punish_another_admin(db_path, bot_ids):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42, 66])
        other_admin = FakeMember(66, None)
        guild = FakeGuild(5, audit_entries=[
            FakeAuditEntry(FakeMember(42), 0),
            FakeAuditEntry(other_admin, 1),
        ])
        other_admin.guild = guild
        await helpers.unmute_admin(FakeMember(42, guild, mute=True))
        return other_admin

    other_admin = asyncio.run(scenario())
    assert other_admin.timeouts == []


def test_unmute_admin_does_not_punish_our_own_bots(db_path, bot_ids):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        our_bot = FakeMember(1001, None)
        guild = FakeGuild(5, audit_entries=[
            FakeAuditEntry(FakeMember(42), 0),
            FakeAuditEntry(our_bot, 1),
        ])
        await helpers.unmute_admin(FakeMember(42, guild, mute=True))
        return our_bot

    assert asyncio.run(scenario()).timeouts == []


def test_unmute_admin_survives_missing_audit_log_permission(db_path, bot_ids):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        guild = FakeGuild(5, raise_on_audit=True)
        admin = FakeMember(42, guild, mute=True)
        return await helpers.unmute_admin(admin), admin

    result, admin = asyncio.run(scenario())
    # still un-muted; just can't identify who did it
    assert result is True
    assert {"mute": False} in admin.edits


def test_unmute_admin_ignores_non_admins(db_path, bot_ids):
    async def scenario():
        guild = FakeGuild(5)
        member = FakeMember(7, guild, mute=True)
        return await helpers.unmute_admin(member), member

    result, member = asyncio.run(scenario())
    assert result is False
    assert member.edits == []


# --------------------------------------------------------------------------- #
# check_admin_kick
# --------------------------------------------------------------------------- #

def test_check_admin_kick_punishes_the_disconnector(db_path, bot_ids):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        attacker = FakeMember(66, None)
        guild = FakeGuild(5, audit_entries=[FakeAuditEntry(attacker, 1)])
        result = await helpers.check_admin_kick(FakeMember(42, guild))
        return result, attacker

    result, attacker = asyncio.run(scenario())
    assert result is True
    assert attacker.moves == [None]
    assert attacker.timeouts[0]["duration"] == 60


def test_check_admin_kick_returns_false_with_no_audit_entries(db_path, bot_ids):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        guild = FakeGuild(5, audit_entries=[])
        return await helpers.check_admin_kick(FakeMember(42, guild))

    assert asyncio.run(scenario()) is False


def test_check_admin_kick_ignores_non_admins(db_path, bot_ids):
    async def scenario():
        return await helpers.check_admin_kick(FakeMember(7, FakeGuild(5)))

    assert asyncio.run(scenario()) is False


# --------------------------------------------------------------------------- #
# check_mentions
# --------------------------------------------------------------------------- #

class FakeMessage:
    def __init__(self, guild, author, mentions=(), role_mentions=(),
                 content="", mention_everyone=False):
        self.guild = guild
        self.author = author
        self.mentions = list(mentions)
        self.role_mentions = list(role_mentions)
        self.content = content
        self.mention_everyone = mention_everyone
        self.replies = []

    async def reply(self, text, **kwargs):
        self.replies.append(text)
        return text


def guild_with_me(me_member, guild_id=5):
    guild = FakeGuild(guild_id)
    guild.me = me_member
    return guild


def test_check_mentions_replies_politely_to_an_admin(db_path):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        me = FakeMember(999)
        guild = guild_with_me(me)
        admin = FakeMember(42, guild)
        message = FakeMessage(guild, admin, mentions=[me], content="hey @bot")
        await helpers.check_mentions(message, types.SimpleNamespace(latency=0.05))
        return message

    message = asyncio.run(scenario())
    assert message.replies == ["At your service, my master."]


def test_check_mentions_reports_ping_for_admins(db_path):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        me = FakeMember(999)
        guild = guild_with_me(me)
        message = FakeMessage(guild, FakeMember(42, guild), mentions=[me], content="ping")
        await helpers.check_mentions(message, types.SimpleNamespace(latency=0.123))
        return message

    message = asyncio.run(scenario())
    assert "123 ms" in message.replies[0]


def test_check_mentions_accepts_the_russian_spelling(db_path):
    async def scenario():
        await helpers.set_guild_option(5, helpers.GuildOption.ADMIN_LIST, [42])
        me = FakeMember(999)
        guild = guild_with_me(me)
        message = FakeMessage(guild, FakeMember(42, guild), mentions=[me], content="пинг")
        await helpers.check_mentions(message, types.SimpleNamespace(latency=0.01))
        return message

    assert "ms" in asyncio.run(scenario()).replies[0]


def test_check_mentions_times_out_non_admins(db_path):
    async def scenario():
        me = FakeMember(999)
        guild = guild_with_me(me)
        author = FakeMember(7, guild)
        message = FakeMessage(guild, author, mentions=[me], content="oi @bot")
        await helpers.check_mentions(message, types.SimpleNamespace(latency=0.05))
        return message, author

    message, author = asyncio.run(scenario())
    assert author.timeouts[0]["duration"] == 10
    assert "Know your place" in message.replies[0]


def test_check_mentions_ignores_everyone_pings(db_path):
    async def scenario():
        me = FakeMember(999)
        guild = guild_with_me(me)
        author = FakeMember(7, guild)
        message = FakeMessage(guild, author, mentions=[me],
                              content="@everyone", mention_everyone=True)
        await helpers.check_mentions(message, types.SimpleNamespace(latency=0.05))
        return message, author

    message, author = asyncio.run(scenario())
    assert message.replies == []
    assert author.timeouts == []


def test_check_mentions_ignores_messages_without_mentions(db_path):
    async def scenario():
        me = FakeMember(999)
        guild = guild_with_me(me)
        message = FakeMessage(guild, FakeMember(7, guild), content="just chatting")
        await helpers.check_mentions(message, types.SimpleNamespace(latency=0.05))
        return message

    assert asyncio.run(scenario()).replies == []


def test_check_mentions_matches_role_mentions(db_path):
    """Being pinged via a role the bot holds counts as being mentioned."""
    async def scenario():
        role = FakeRole(3)
        me = FakeMember(999, roles=[role])
        guild = guild_with_me(me)
        author = FakeMember(7, guild)
        message = FakeMessage(guild, author, role_mentions=[role], content="hey")
        await helpers.check_mentions(message, types.SimpleNamespace(latency=0.05))
        return author

    assert asyncio.run(scenario()).timeouts != []


def test_is_mentioned_direct_and_via_role():
    role = FakeRole(3)
    me = FakeMember(999, roles=[role])
    assert helpers.is_mentioned(me, FakeMessage(None, None, mentions=[me])) is True
    assert helpers.is_mentioned(me, FakeMessage(None, None, role_mentions=[role])) is True
    assert helpers.is_mentioned(me, FakeMessage(None, None)) is False


# --------------------------------------------------------------------------- #
# modify_roles
# --------------------------------------------------------------------------- #

def test_modify_roles_adds_and_removes(db_path):
    async def scenario():
        keep = FakeRole(1, position=5)
        drop = FakeRole(2, position=5)
        guild = FakeGuild(5)
        guild.roles_by_id = {1: keep, 2: drop}
        member = FakeMember(7, guild, roles=[drop])
        await helpers.modify_roles(member, roles_to_remove=[2], roles_to_add=[1])
        await asyncio.sleep(0)   # the helper dispatches via create_task
        await asyncio.sleep(0)
        return member, keep, drop

    member, keep, drop = asyncio.run(scenario())
    assert keep in member.added_roles
    assert drop in member.removed_roles


def test_modify_roles_skips_roles_above_the_bot(db_path):
    async def scenario():
        too_high = FakeRole(1, position=500)   # above me.top_role (100)
        guild = FakeGuild(5)
        guild.roles_by_id = {1: too_high}
        member = FakeMember(7, guild)
        await helpers.modify_roles(member, roles_to_add=[1])
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return member

    assert asyncio.run(scenario()).added_roles == []


def test_modify_roles_skips_managed_integration_roles(db_path):
    async def scenario():
        managed = FakeRole(1, position=5, managed=True)
        guild = FakeGuild(5)
        guild.roles_by_id = {1: managed}
        member = FakeMember(7, guild)
        await helpers.modify_roles(member, roles_to_add=[1])
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return member

    assert asyncio.run(scenario()).added_roles == []


def test_modify_roles_ignores_roles_in_both_lists(db_path):
    async def scenario():
        role = FakeRole(1, position=5)
        guild = FakeGuild(5)
        guild.roles_by_id = {1: role}
        member = FakeMember(7, guild)
        await helpers.modify_roles(member, roles_to_remove=[1], roles_to_add=[1])
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return member

    member = asyncio.run(scenario())
    assert member.added_roles == []
    assert member.removed_roles == []


def test_modify_roles_noop_without_manage_roles_permission(db_path):
    async def scenario():
        role = FakeRole(1, position=5)
        guild = FakeGuild(5)
        guild.me.guild_permissions.manage_roles = False
        guild.roles_by_id = {1: role}
        member = FakeMember(7, guild)
        await helpers.modify_roles(member, roles_to_add=[1])
        await asyncio.sleep(0)
        return member

    assert asyncio.run(scenario()).added_roles == []


def test_modify_roles_handles_missing_member(db_path):
    asyncio.run(helpers.modify_roles(None, roles_to_add=[1]))   # must not raise


# --------------------------------------------------------------------------- #
# set_bitrate
# --------------------------------------------------------------------------- #

class FakeVoiceChannel:
    def __init__(self, bitrate, fail=False):
        self.bitrate = bitrate
        self.fail = fail
        self.edits = []

    async def edit(self, **kwargs):
        if self.fail:
            raise RuntimeError("missing permissions")
        self.edits.append(kwargs)
        self.bitrate = kwargs.get("bitrate", self.bitrate)


def test_set_bitrate_raises_channels_to_the_tier_maximum():
    async def scenario():
        low = FakeVoiceChannel(64000)
        already = FakeVoiceChannel(384000)
        guild = types.SimpleNamespace(voice_channels=[low, already], premium_tier=3)
        result = await helpers.set_bitrate(guild)
        return result, low, already

    result, low, already = asyncio.run(scenario())
    assert result is True
    assert low.bitrate == 384000
    assert already.edits == []      # already correct, left alone


def test_set_bitrate_reports_failure_without_permission():
    async def scenario():
        channel = FakeVoiceChannel(64000, fail=True)
        guild = types.SimpleNamespace(voice_channels=[channel], premium_tier=1)
        return await helpers.set_bitrate(guild)

    assert asyncio.run(scenario()) is False


# --------------------------------------------------------------------------- #
# get_next_rank
# --------------------------------------------------------------------------- #

def test_get_next_rank_reports_current_and_upcoming(db_path):
    async def scenario():
        guild = FakeGuild(5)
        member = FakeMember(7, guild)
        await helpers.set_user_xp(5, 7, voice_xp=60)
        for rank in (helpers.Rank(1, 10, True), helpers.Rank(2, 50, True), helpers.Rank(3, 100, True)):
            await helpers.add_guild_option(5, helpers.GuildOption.RANK, rank)
        return await helpers.get_next_rank(member)

    current, upcoming = asyncio.run(scenario())
    assert current.voice_xp == 50
    assert upcoming.voice_xp == 100


def test_get_next_rank_with_no_ranks_configured(db_path):
    async def scenario():
        member = FakeMember(7, FakeGuild(5))
        return await helpers.get_next_rank(member)

    current, upcoming = asyncio.run(scenario())
    assert current is None and upcoming is None


# --------------------------------------------------------------------------- #
# try_function / dm_user / delayed tasks
# --------------------------------------------------------------------------- #

def test_try_function_returns_result_on_success():
    async def scenario():
        async def works(value):
            return value * 2
        return await helpers.try_function(works, True, 21)

    assert asyncio.run(scenario()) == (True, 42)


def test_try_function_swallows_exceptions():
    async def scenario():
        async def explodes():
            raise RuntimeError("boom")
        return await helpers.try_function(explodes, True)

    assert asyncio.run(scenario()) == (False, None)


def test_try_function_supports_sync_callables():
    async def scenario():
        return await helpers.try_function(lambda a, b: a + b, False, 2, 3)

    assert asyncio.run(scenario()) == (True, 5)


def test_try_function_sync_failure():
    async def scenario():
        def explodes():
            raise ValueError("nope")
        return await helpers.try_function(explodes, False)

    assert asyncio.run(scenario()) == (False, None)


def test_dm_user_sends_when_user_is_resolvable():
    async def scenario():
        user = FakeMember(7)
        bot = types.SimpleNamespace(get_user=lambda _: user)
        return await helpers.dm_user("hello", 7, bot), user

    sent, user = asyncio.run(scenario())
    assert sent is True
    assert user.dms[0][0][0] == "hello"


def test_dm_user_returns_false_for_unknown_user():
    async def scenario():
        bot = types.SimpleNamespace(get_user=lambda _: None)
        return await helpers.dm_user("hello", 7, bot)

    assert asyncio.run(scenario()) is False


def test_run_delayed_tasks_awaits_everything():
    async def scenario():
        done = []

        async def task(n):
            done.append(n)

        await helpers.run_delayed_tasks([task(1), task(2), task(3)])
        return done

    assert sorted(asyncio.run(scenario())) == [1, 2, 3]


def test_add_playlist_delayed_task_waits_for_the_future(monkeypatch):
    """The real helper polls with sleep(1); patched to run instantly here."""
    async def scenario():
        real_sleep = asyncio.sleep

        async def fast_sleep(_):
            await real_sleep(0)

        monkeypatch.setattr(helpers.asyncio, "sleep", fast_sleep)

        future = asyncio.Future()
        called = []

        async def action(value):
            called.append(value)

        task = asyncio.create_task(
            helpers.add_playlist_delayed_task(action, True, future, "done"))
        await real_sleep(0)
        assert called == []          # still waiting
        future.set_result(None)
        await task
        return called

    assert asyncio.run(scenario()) == ["done"]


def test_add_playlist_delayed_task_supports_sync_callables(monkeypatch):
    async def scenario():
        real_sleep = asyncio.sleep
        monkeypatch.setattr(helpers.asyncio, "sleep", lambda _: real_sleep(0))
        future = asyncio.Future()
        future.set_result(None)
        called = []
        await helpers.add_playlist_delayed_task(called.append, False, future, "x")
        return called

    assert asyncio.run(scenario()) == ["x"]


# --------------------------------------------------------------------------- #
# create_private
# --------------------------------------------------------------------------- #

class FakeCategory:
    def __init__(self, fail=False):
        self.fail = fail
        self.created = []

    async def create_voice_channel(self, name):
        if self.fail:
            raise RuntimeError("no permission")
        channel = FakeCreatedChannel(name)
        self.created.append(channel)
        return channel


class FakeCreatedChannel:
    def __init__(self, name):
        self.name = name
        self.permissions = []
        self.edits = []
        self.deleted = False

    def overwrites_for(self, member):
        return types.SimpleNamespace(view_channel=None, manage_permissions=None, manage_channels=None)

    async def set_permissions(self, target, **kwargs):
        self.permissions.append((target, kwargs))

    async def edit(self, **kwargs):
        self.edits.append(kwargs)

    async def delete(self, **kwargs):
        self.deleted = True


def test_create_private_builds_and_locks_down_the_channel(db_path):
    async def scenario():
        category = FakeCategory()
        guild = FakeGuild(5)
        guild.default_role = "everyone"
        guild.get_channel = lambda _: category
        guild.premium_tier = 2
        member = FakeMember(7, guild)
        member.display_name = "Dan"
        await helpers.set_guild_option(5, helpers.GuildOption.PRIVATE_CATEGORY, 111)
        await helpers.create_private(member)
        return category, member

    category, member = asyncio.run(scenario())
    channel = category.created[0]
    assert channel.name == "Dan's private"
    # hidden from @everyone, then granted to the owner
    assert channel.permissions[0][0] == "everyone"
    assert channel.permissions[0][1]["view_channel"] is False
    assert member.moves == [channel]
    assert channel.edits[0]["bitrate"] == 256000     # tier 2


def test_create_private_does_nothing_without_a_category(db_path):
    async def scenario():
        member = FakeMember(7, FakeGuild(5))
        await helpers.create_private(member)     # no PRIVATE_CATEGORY set
        return member

    assert asyncio.run(scenario()).moves == []


def test_create_private_cleans_up_when_lockdown_fails(db_path):
    async def scenario():
        category = FakeCategory()
        guild = FakeGuild(5)
        guild.default_role = "everyone"
        guild.get_channel = lambda _: category
        guild.premium_tier = 0
        member = FakeMember(7, guild)
        member.display_name = "Dan"
        await helpers.set_guild_option(5, helpers.GuildOption.PRIVATE_CATEGORY, 111)

        original = FakeCreatedChannel.set_permissions

        async def failing(self, target, **kwargs):
            raise RuntimeError("denied")

        FakeCreatedChannel.set_permissions = failing
        try:
            await helpers.create_private(member)
        finally:
            FakeCreatedChannel.set_permissions = original
        return category

    category = asyncio.run(scenario())
    assert category.created[0].deleted is True
