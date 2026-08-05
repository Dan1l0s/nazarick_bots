"""Unit tests for helpers/embedder.py.

Two layers:

1. A **sweep** over every `entry_*` audit-log embed builder, driven by the
   permissive `Anything` fake. It asserts each one returns a real
   `disnake.Embed` without raising. This is exactly the class of check that
   would have caught the duplicated `entry_sticker_create` in the original -
   a shadowed function is invisible to `grep` but obvious when you enumerate
   and call every handler.

2. **Precise tests** for the embedders with real formatting logic (durations,
   pagination, empty states), where a permissive fake would prove nothing.
"""

import disnake
import pytest

import configs.public_config as public_config
import helpers.embedder as embedder
import helpers.helpers as helpers
from tests.fakes import Anything, FakeAuthor, FakeGuild, FakeMember, FakeRole, track


# --------------------------------------------------------------------------- #
# Sweep: every entry_* builder must run and return an Embed
# --------------------------------------------------------------------------- #

ENTRY_BUILDERS = sorted(
    name for name in dir(embedder)
    if name.startswith("entry_") and callable(getattr(embedder, name))
)


def test_sweep_covers_a_realistic_number_of_builders():
    # guards against the sweep silently collecting nothing
    assert len(ENTRY_BUILDERS) >= 30


@pytest.mark.parametrize("name", ENTRY_BUILDERS)
def test_entry_builder_returns_embed(name):
    builder = getattr(embedder, name)
    result = builder(Anything("entry"))
    assert isinstance(result, disnake.Embed)


@pytest.mark.parametrize("name", ENTRY_BUILDERS)
def test_entry_builder_embed_serializes(name):
    """to_dict() is what disnake calls before sending; it will raise on any
    field the builder populated with an unsendable value."""
    builder = getattr(embedder, name)
    payload = builder(Anything("entry")).to_dict()
    assert isinstance(payload, dict)


def test_sticker_create_and_delete_are_distinct():
    """Regression test for the Stage 1 duplicate-definition bug: both must
    exist and produce different text."""
    created = embedder.entry_sticker_create(Anything("e")).to_dict()
    deleted = embedder.entry_sticker_delete(Anything("e")).to_dict()
    assert "added a sticker" in created["description"]
    assert "deleted a sticker" in deleted["description"]
    assert created["description"] != deleted["description"]


# --------------------------------------------------------------------------- #
# Music embeds
# --------------------------------------------------------------------------- #

def test_songs_embed_fields():
    author = FakeAuthor(display_name="Dan", channel_name="Music")
    embed = embedder.songs(author, track(title="Test Track"), "Playing this song!").to_dict()

    assert embed["title"] == "Test Track"
    assert embed["description"] == "Playing this song!"
    values = {f["name"]: f["value"] for f in embed["fields"]}
    assert values["*Duration*"] == "00:02:05"
    assert values["*Requested by*"] == "Dan"
    assert values["*Channel*"] == "Music"


def test_songs_embed_unwraps_search_result_entries():
    """yt-dlp search results arrive wrapped in an 'entries' list; the embedder
    unwraps the first entry."""
    author = FakeAuthor()
    wrapped = {"entries": [track(title="Inner Track")]}
    embed = embedder.songs(author, wrapped, "text").to_dict()
    assert embed["title"] == "Inner Track"


def test_songs_embed_live_track_shows_live():
    author = FakeAuthor()
    embed = embedder.songs(author, track(live=True), "text").to_dict()
    values = {f["name"]: f["value"] for f in embed["fields"]}
    assert values["*Duration*"] == "Live"


def test_radio_embed():
    data = {
        "name": "Anime Song",
        "source": "Artist",
        "duration": 200,
        "channel": type("C", (), {"name": "Radio VC"})(),
    }
    embed = embedder.radio(data).to_dict()
    assert embed["title"] == "Anime Song"
    assert "ANISON.FM" in embed["description"]


# --------------------------------------------------------------------------- #
# Queue embed
# --------------------------------------------------------------------------- #

class FakeFuture:
    def __init__(self, result, done=True):
        self._result = result
        self._done = done

    def done(self):
        return self._done

    def result(self):
        return self._result


class FakeSong:
    def __init__(self, result, done=True):
        self.track_info = FakeFuture(result, done)


def test_queue_embed_lists_tracks():
    guild = FakeGuild()
    queue = [FakeSong(track(title="One")), FakeSong(track(title="Two"))]
    embed = embedder.queue(guild, queue, 0, track(title="Now Playing")).to_dict()

    assert "Now Playing" in embed["description"]
    joined = " ".join(f["value"] for f in embed["fields"])
    assert "One" in joined and "Two" in joined


def test_queue_embed_empty_queue():
    embed = embedder.queue(FakeGuild(), [], 0, track(title="Now")).to_dict()
    assert any("Queue is currently empty!" in f["value"] for f in embed["fields"])


def test_queue_embed_artificial_current_song_renders_empty():
    """`/queue` with nothing playing passes a sentinel carrying 'artificial';
    the embedder must treat that as the empty state even if songs are queued."""
    sentinel = {'title': "Nothing", 'webpage_url': "https://youtu.be/x",
                'duration': 86399, 'artificial': True}
    queue = [FakeSong(track(title="Queued"))]
    embed = embedder.queue(FakeGuild(), queue, 0, sentinel).to_dict()
    assert any("Queue is currently empty!" in f["value"] for f in embed["fields"])


def test_queue_embed_radio_entry_renders_as_live():
    queue = [FakeSong("http://radio.example/stream")]
    embed = embedder.queue(FakeGuild(), queue, 0, track()).to_dict()
    joined = " ".join(f["value"] for f in embed["fields"])
    assert "Radio" in joined and "Live" in joined


def test_queue_embed_current_radio_track():
    embed = embedder.queue(FakeGuild(), [], 0, "http://radio.example/stream").to_dict()
    assert "Radio" in embed["description"]


# --------------------------------------------------------------------------- #
# Leveling embeds
# --------------------------------------------------------------------------- #

def test_xp_show_with_rank_and_next_rank():
    member = FakeMember()
    embed = embedder.xp_show(member, [member.id, 150, 20],
                             FakeRole(1, "Bronze"), FakeRole(2, "Silver"), 50).to_dict()
    values = {f["name"]: f["value"] for f in embed["fields"]}
    assert values["**Voice XP**"] == "**150**"
    assert values["**Text XP**"] == "**20**"
    assert "50 voice xp" in values["**Next rank**"]
    assert "currently has" in embed["description"]


def test_xp_show_without_any_rank():
    member = FakeMember()
    embed = embedder.xp_show(member, [member.id, 5, 0], None, None, None).to_dict()
    assert "no ranks" in embed["description"]
    assert not any(f["name"] == "**Next rank**" for f in embed["fields"])


def test_xp_top_lists_users_and_marks_author():
    guild = FakeGuild()
    author_info = [1, 100, 10]
    top = [author_info, [2, 50, 5]]
    users = {1: FakeMember(1, "First"), 2: FakeMember(2, "Second")}
    embed = embedder.xp_top(guild, top, 0, author_info, users.get, True).to_dict()

    assert embed["title"] == "Type: Voice"
    # author is inside the visible page, so no separate summary line is added
    # (an empty description is omitted from the payload entirely)
    assert embed.get("description", "") == ""
    assert len(embed["fields"]) == 2


def test_xp_top_text_type_uses_text_xp():
    guild = FakeGuild()
    author_info = [1, 100, 10]
    users = {1: FakeMember(1, "First")}
    embed = embedder.xp_top(guild, [author_info], 0, author_info, users.get, False).to_dict()
    assert embed["title"] == "Type: Text"
    assert "10xp" in embed["fields"][0]["value"]


def test_xp_top_falls_back_to_raw_mention_for_unknown_user():
    """get_user returns None for users the bot can't see; the embed must still
    render a mention rather than crash."""
    guild = FakeGuild()
    author_info = [1, 100, 10]
    embed = embedder.xp_top(guild, [author_info], 0, author_info, lambda _: None, True).to_dict()
    assert "<@1>" in embed["fields"][0]["value"]


def test_rank_list_embed():
    guild = FakeGuild()
    guild.get_role = lambda rid: FakeRole(rid, f"Role{rid}")
    ranks = [helpers.Rank(1, 100, True), helpers.Rank(2, 200, True)]
    embed = embedder.rank_list(ranks, guild).to_dict()
    assert "Rank list" in embed["description"]
    assert len(embed["fields"]) == 2
    assert "100 XP" in embed["fields"][0]["value"]


def test_admin_list_embed_skips_unresolvable_users():
    guild = FakeGuild()
    users = {1: FakeMember(1, "A")}
    embed = embedder.admin_list([1, 999], users.get, guild).to_dict()
    value = embed["fields"][0]["value"]
    assert "<@1>" in value
    assert "999" not in value


def test_role_notification_singular_and_plural():
    guild = FakeGuild()
    one = embedder.role_notification(guild, [FakeRole(1, "Alpha")]).to_dict()
    many = embedder.role_notification(guild, [FakeRole(1, "Alpha"), FakeRole(2, "Beta")]).to_dict()
    assert "a new role" in one["description"]
    assert "new roles" in many["description"]


# --------------------------------------------------------------------------- #
# Song selection panel
# --------------------------------------------------------------------------- #

def test_song_selections_numbers_results_and_marks_live():
    author = FakeAuthor()
    songs = [
        {"title": "First", "url_suffix": "/watch?v=aaa&pp=x", "duration": "3:00"},
        {"title": "Second", "url_suffix": "/watch?v=bbb&pp=x", "duration": 0},
    ]
    embed = embedder.song_selections(author, songs).to_dict()
    value = embed["fields"][0]["value"]
    assert "**1.**" in value and "**2.**" in value
    assert "First" in value and "Second" in value
    # duration 0 is rewritten to "Live" in place
    assert "(Live)" in value
    assert songs[1]["duration"] == "Live"


def test_song_selections_footer_mentions_timeout():
    embed = embedder.song_selections(FakeAuthor(), []).to_dict()
    timeout = public_config.music_settings["SelectionPanelTimeout"]
    assert str(timeout) in embed["footer"]["text"]


# --------------------------------------------------------------------------- #
# Member / message / voice embeds
# --------------------------------------------------------------------------- #

def test_welcome_message_uses_friendly_guild_name():
    member = FakeMember()
    member.guild = FakeGuild(name="Nazarick")
    embed = embedder.welcome_message(member, member).to_dict()
    assert "the Great Tomb of Nazarick" in embed["description"]


def test_welcome_message_uses_plain_name_for_other_guilds():
    member = FakeMember()
    member.guild = FakeGuild(name="Some Server")
    embed = embedder.welcome_message(member, member).to_dict()
    assert "Some Server" in embed["description"]


def test_member_join_and_ban_embeds():
    member = FakeMember()
    join = embedder.member_join(member).to_dict()
    assert "has joined the server" in join["description"]

    guild = FakeGuild()
    banned = embedder.ban(guild, member).to_dict()
    assert "has been banned" in banned["description"]

    unbanned = embedder.unban(guild, member).to_dict()
    assert "has been unbanned" in unbanned["description"]


@pytest.mark.parametrize("builder,attr,value", [
    (embedder.mute, "mute", True),
    (embedder.deaf, "deaf", True),
    (embedder.self_stream, "self_stream", True),
    (embedder.self_video, "self_video", False),
])
def test_voice_state_embeds(builder, attr, value):
    member = FakeMember()
    after = type("VS", (), {attr: value})()
    embed = builder(member, after).to_dict()
    assert embed["fields"][0]["value"] in ("Yes", "No")


def test_self_mute_embed_reports_deafen_transition():
    member = FakeMember()
    before = type("VS", (), {"self_mute": False, "self_deaf": True})()
    after = type("VS", (), {"self_mute": True, "self_deaf": False})()
    embed = embedder.self_mute(member, before, after).to_dict()
    names = [f["name"] for f in embed["fields"]]
    assert any("Muted" in n for n in names)
    assert any("Deafened" in n for n in names)


def test_message_delete_truncates_long_content():
    long_content = "x" * 2000
    message = type("M", (), {
        "author": FakeMember(),
        "content": long_content,
        "channel": type("C", (), {"mention": "<#1>", "guild": FakeGuild()})(),
    })()
    embed = embedder.message_delete(message).to_dict()
    assert "..." in embed["fields"][0]["value"]
    assert len(embed["fields"][0]["value"]) < 1100


def test_message_delete_keeps_short_content_intact():
    message = type("M", (), {
        "author": FakeMember(),
        "content": "short message",
        "channel": type("C", (), {"mention": "<#1>", "guild": FakeGuild()})(),
    })()
    embed = embedder.message_delete(message).to_dict()
    assert "short message" in embed["fields"][0]["value"]


# --------------------------------------------------------------------------- #
# create_embed itself
# --------------------------------------------------------------------------- #

def test_create_embed_applies_color_from_tag():
    embed = embedder.create_embed(color_tag="ban_leave")
    assert embed.colour.r == 255 and embed.colour.g == 0 and embed.colour.b == 0


def test_create_embed_unknown_color_tag_raises():
    with pytest.raises(KeyError):
        embedder.create_embed(color_tag="does_not_exist")


def test_create_embed_footer_icon_without_text():
    """Regression test: `set_footer(icon_url=...)` without `text` raises
    TypeError in disnake. The branch was unreachable in practice, but it was
    broken - it now passes an empty text so the call is valid."""
    embed = embedder.create_embed(color_tag="xp", footer_icon_url="https://example.invalid/i.png").to_dict()
    assert embed["footer"]["icon_url"] == "https://example.invalid/i.png"


def test_embed_field_defaults():
    field = embedder.EmbedField()
    assert field.name == "" and field.value == "" and field.inline is False
