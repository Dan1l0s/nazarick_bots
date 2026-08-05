"""Unit tests for helpers/helpers.py.

Covers the pure-logic functions (formatting, sorting, permission checks) plus
the guild-options / xp sqlite store, run against a throwaway sqlite file per
test via the `db_path` fixture. Special attention to `convert_to_python` /
`set_guild_option` for ADMIN_LIST and UNTOUCHABLES_LIST, since that's where
`eval()` was replaced with `json` (see helpers.py module docstring) - these
tests confirm round-tripping still works, including reading a row written the
*old* way (Python's `str(list_of_ints)`), so existing db/bot_database.db data
does not need a migration.
"""

import asyncio
import sys
import types

import pytest

import helpers.helpers as helpers


# --------------------------------------------------------------------------- #
# Pure formatting / logic functions
# --------------------------------------------------------------------------- #

def test_get_duration_normal():
    assert helpers.get_duration({"duration": 125}) == "00:02:05"


def test_get_duration_live_string_input():
    # radio "now playing" info is a bare URL string, not a dict
    assert helpers.get_duration("http://pool.anison.fm:9000/AniSonFM(320)") == "Live"


def test_get_duration_live_status():
    assert helpers.get_duration({"live_status": "is_live", "duration": 999}) == "Live"


def test_get_duration_zero_duration_is_live():
    assert helpers.get_duration({"duration": 0}) == "Live"


def test_get_duration_multi_day():
    # 2 days, 1 hour -> "02:HH:MM:SS" style prefix per original logic
    info = {"duration": 2 * 86400 + 3600}
    assert helpers.get_duration(info).startswith("02:")


def test_split_into_chunks_keeps_code_fence_balanced():
    long_block = "```python\n" + "\n".join(f"line {i}" for i in range(400)) + "\n```"
    chunks = helpers.split_into_chunks(long_block, chunk_size=200)
    assert len(chunks) > 1
    # every chunk must have an even number of ``` fences (never split mid-fence)
    for chunk in chunks:
        assert chunk.count("```") % 2 == 0


def test_split_into_chunks_short_message_single_chunk():
    assert helpers.split_into_chunks("hello world") == ["hello world\n"]


def test_parse_key():
    assert helpers.parse_key("self_deaf") == "Self deaf "
    assert helpers.parse_key("name") == "Name "


def test_rgb_to_hex():
    assert helpers.rgb_to_hex(0, 0, 0) == "#000000"
    assert helpers.rgb_to_hex(255, 255, 255) == "#FFFFFF"
    assert helpers.rgb_to_hex(150, 255, 255) == "#96FFFF"


def test_get_user_num_badge_medals_then_numeric():
    assert helpers.get_user_num_badge(0) == helpers.public_config.emojis["first_place"]
    assert helpers.get_user_num_badge(1) == helpers.public_config.emojis["second_place"]
    assert helpers.get_user_num_badge(2) == helpers.public_config.emojis["third_place"]
    assert helpers.get_user_num_badge(3) == "4."


def test_sort_ranks_orders_by_voice_xp():
    r1 = helpers.Rank(role_id=1, voice_xp=100, remove_on_promotion=True)
    r2 = helpers.Rank(role_id=2, voice_xp=10, remove_on_promotion=True)
    r3 = helpers.Rank(role_id=3, voice_xp=50, remove_on_promotion=True)
    ordered = helpers.sort_ranks([r1, r2, r3])
    assert [r.voice_xp for r in ordered] == [10, 50, 100]


def test_is_supreme_being_true_and_false():
    class FakeMember:
        def __init__(self, id_):
            self.id = id_
    assert helpers.is_supreme_being(FakeMember(111111111111111111)) is True
    assert helpers.is_supreme_being(FakeMember(999999999999999999)) is False


def test_get_true_members_count_excludes_bots():
    class M:
        def __init__(self, bot):
            self.bot = bot
    members = [M(False), M(True), M(False)]
    assert helpers.get_true_members_count(members) == 2


class FakeFuture:
    """Minimal stand-in for the asyncio.Future stored on Song.track_info, since
    get_queue_duration only calls .done()/.result() on it."""
    def __init__(self, result):
        self._result = result

    def done(self):
        return True

    def result(self):
        return self._result


class FakeSong:
    def __init__(self, result):
        self.track_info = FakeFuture(result)


def test_get_queue_duration_sums_durations():
    queue = [FakeSong({"duration": 60}), FakeSong({"duration": 120})]
    assert helpers.get_queue_duration(queue) == "**Queue duration: **00:03:00"


def test_get_queue_duration_all_live_returns_live_label():
    queue = [FakeSong("http://radio.example/stream")]
    assert "Live" in helpers.get_queue_duration(queue)


def test_get_queue_duration_empty_queue_returns_none():
    assert helpers.get_queue_duration([]) is None


# --------------------------------------------------------------------------- #
# GuildOption store (sqlite) - json.loads/json.dumps replacing eval()/str()
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "bot_database.db")
    monkeypatch.setattr(helpers, "DB_PATH", path)
    return path


def test_admin_list_round_trip(db_path):
    async def scenario():
        guild_id = 123
        assert await helpers.get_guild_option(guild_id, helpers.GuildOption.ADMIN_LIST) == []
        await helpers.set_guild_option(guild_id, helpers.GuildOption.ADMIN_LIST, [111, 222])
        return await helpers.get_guild_option(guild_id, helpers.GuildOption.ADMIN_LIST)

    result = asyncio.run(scenario())
    assert result == [111, 222]


def test_admin_list_reads_legacy_str_repr_rows(db_path):
    """Rows written by the *old* code used Python's str(list) (e.g. "[111, 222]"),
    not json.dumps. Since that happens to be valid JSON for a list of ints, the
    new json.loads()-based reader must still parse it correctly with no
    migration needed."""
    import aiosqlite

    async def scenario():
        await helpers.ensure_tables()
        async with aiosqlite.connect(db_path) as db:
            await db.execute("INSERT OR IGNORE INTO server_options (guild_id) VALUES (?)", (555,))
            await db.execute("UPDATE server_options SET admin_list = ? WHERE guild_id = ?", (str([333, 444]), 555))
            await db.commit()
        return await helpers.get_guild_option(555, helpers.GuildOption.ADMIN_LIST)

    assert asyncio.run(scenario()) == [333, 444]


def test_untouchables_list_round_trip(db_path):
    async def scenario():
        guild_id = 999
        await helpers.set_guild_option(guild_id, helpers.GuildOption.UNTOUCHABLES_LIST, [42])
        return await helpers.get_guild_option(guild_id, helpers.GuildOption.UNTOUCHABLES_LIST)

    assert asyncio.run(scenario()) == [42]


def test_channel_option_round_trip_is_int(db_path):
    async def scenario():
        guild_id = 42
        await helpers.set_guild_option(guild_id, helpers.GuildOption.LOG_CHANNEL, 987654321)
        return await helpers.get_guild_option(guild_id, helpers.GuildOption.LOG_CHANNEL)

    result = asyncio.run(scenario())
    assert result == 987654321
    assert isinstance(result, int)


def test_unset_channel_option_returns_none(db_path):
    async def scenario():
        return await helpers.get_guild_option(1, helpers.GuildOption.LOG_CHANNEL)

    assert asyncio.run(scenario()) is None


def test_user_xp_round_trip(db_path):
    async def scenario():
        await helpers.set_user_xp(1, 2, voice_xp=10, text_xp=5)
        return await helpers.get_user_xp(1, 2)

    assert asyncio.run(scenario()) == (10, 5)


def test_add_user_xp_accumulates(db_path):
    async def scenario():
        await helpers.add_user_xp(1, 2, voice_xp=10)
        await helpers.add_user_xp(1, 2, voice_xp=5)
        return await helpers.get_user_xp(1, 2)

    assert asyncio.run(scenario()) == (15, 0)


def test_rank_add_list_remove_round_trip(db_path):
    async def scenario():
        guild_id = 7
        rank = helpers.Rank(role_id=555, voice_xp=100, remove_on_promotion=True)
        added = await helpers.add_guild_option(guild_id, helpers.GuildOption.RANK, rank)
        assert added is True
        # adding the same rank again should report "already exists"
        added_again = await helpers.add_guild_option(guild_id, helpers.GuildOption.RANK, rank)
        assert added_again is False

        ranks = await helpers.get_guild_option(guild_id, helpers.GuildOption.RANK_LIST)
        assert len(ranks) == 1
        assert ranks[0].role_id == 555
        assert ranks[0].voice_xp == 100

        removed = await helpers.remove_guild_option(guild_id, helpers.GuildOption.RANK, 555)
        assert removed is True
        ranks_after = await helpers.get_guild_option(guild_id, helpers.GuildOption.RANK_LIST)
        assert ranks_after == []

    asyncio.run(scenario())


def test_convert_to_python_invalid_option_raises_valueerror():
    # regression test for the `raise f"..."` bug (raised a bare string, which
    # is a TypeError in Python 3, not a catchable/expected error type)
    with pytest.raises(ValueError):
        helpers.convert_to_python(helpers.GuildOption.RANK, [])
