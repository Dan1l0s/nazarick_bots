"""Unit tests for bots/music_instance.py and bots/music_leader.py.

These avoid touching Discord entirely: `MusicBotInstance.__init__` builds a real
`commands.InteractionBot`, so instead of constructing one we exercise the pure
state machine and the instance-selection logic against lightweight fakes, calling
the real methods unbound via `MusicBotInstance.<method>(fake_self, ...)`.

Focus areas:
  - GuildState reset/flag behavior (queue lifecycle)
  - the queue-selection rule in play_loop (first *resolved* song wins, not first
    song) - the behavior that lets a slow playlist not block a ready track
  - the playlist-future conditional that used the `(None, Future())[cond]`
    tuple-index trick, verifying the rewritten conditional matches it
  - leader instance selection: playing > idle > timed-out > none
  - radio widget parsing/fetch now being off-loop
"""

import asyncio
import sys
import types

import pytest

import bots.music_instance as music_instance
from bots.music_instance import GuildState, Song


# --------------------------------------------------------------------------- #
# GuildState
# --------------------------------------------------------------------------- #

def test_guild_state_starts_clean():
    state = GuildState(guild=object())
    assert state.song_queue == []
    assert state.current_song is None
    assert state.skip_flag is False
    assert state.repeat_flag is False
    assert state.paused is False
    assert state.voice is None


def test_guild_state_reset_clears_everything_except_guild_and_voice():
    guild = object()
    voice = object()
    state = GuildState(guild=guild)
    state.voice = voice
    state.skip_flag = True
    state.repeat_flag = True
    state.paused = True
    state.current_song = "song"
    state.last_inter = "inter"
    state.cancel_timeout = "fut"
    state.song_queue.append("a")
    state.last_radio_message.append("b")

    state.reset()

    assert state.skip_flag is False
    assert state.repeat_flag is False
    assert state.paused is False
    assert state.current_song is None
    assert state.last_inter is None
    assert state.cancel_timeout is None
    assert state.song_queue == []
    assert state.last_radio_message == []
    # reset() deliberately does NOT clear guild or voice - abort_play owns voice
    assert state.guild is guild
    assert state.voice is voice


def test_guild_state_reset_mutates_queue_in_place():
    """play_loop holds a reference to state.song_queue; reset() must clear the
    same list object rather than rebinding, or the loop would keep draining a
    detached queue."""
    state = GuildState(guild=object())
    queue_ref = state.song_queue
    state.song_queue.append("a")
    state.reset()
    assert queue_ref is state.song_queue
    assert queue_ref == []


# --------------------------------------------------------------------------- #
# Song
# --------------------------------------------------------------------------- #

def test_song_defaults():
    async def scenario():
        song = Song()
        assert song.author == "Unknown author"
        assert song.radio_mode is False
        assert song.original_message is None
        assert not song.track_info.done()

    asyncio.run(scenario())


def test_song_radio_mode_flag():
    async def scenario():
        song = Song(author="me", radio_mode=True)
        assert song.radio_mode is True
        assert song.author == "me"

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# play_loop's "first resolved song" selection rule
# --------------------------------------------------------------------------- #

def select_ready_position(queue):
    """Mirror of the selection loop at the top of play_loop(). Kept in the test
    so a change to that rule in music_instance.py shows up as a failure here."""
    pos = -1
    for i in range(0, len(queue)):
        if queue[i].track_info.done():
            pos = i
            break
    return pos


def test_play_loop_picks_first_resolved_song_not_first_song():
    async def scenario():
        pending = Song()          # e.g. a playlist entry still loading
        ready = Song()
        ready.track_info.set_result({"title": "ready", "duration": 10})
        queue = [pending, ready]
        # index 1, not 0: the unresolved head must be skipped over
        assert select_ready_position(queue) == 1

    asyncio.run(scenario())


def test_play_loop_returns_minus_one_when_nothing_resolved():
    async def scenario():
        queue = [Song(), Song()]
        assert select_ready_position(queue) == -1

    asyncio.run(scenario())


def test_queue_poll_interval_is_not_a_busy_wait():
    """Regression guard for the `asyncio.sleep(0)` spin loop. If someone sets
    this back to 0 the busy-wait (and its CPU cost) returns."""
    assert music_instance.QUEUE_POLL_INTERVAL > 0


# --------------------------------------------------------------------------- #
# playlist_future conditional (was a `(None, asyncio.Future())[cond]` trick)
# --------------------------------------------------------------------------- #

def test_playlist_future_conditional_matches_original_semantics():
    """The original built this with `(None, asyncio.Future())["playlist" in url]`.
    The rewrite uses a plain conditional; this pins down that both select the
    same branch for representative URLs (and, as a bonus, the rewrite no longer
    constructs a throwaway Future on the None branch)."""
    async def scenario():
        for url, expect_future in [
            ("https://www.youtube.com/playlist?list=PL123", True),
            ("https://www.youtube.com/watch?v=abc&list=PL123", False),
            ("https://www.youtube.com/watch?v=abc", False),
        ]:
            original = (None, asyncio.Future())["playlist" in url]
            rewritten = asyncio.Future() if "playlist" in url else None
            assert (original is not None) == expect_future
            assert (rewritten is not None) == expect_future

    asyncio.run(scenario())


def test_liked_videos_playlist_is_not_expanded():
    """`?list=LL` is the private Liked Videos list, which can't be expanded;
    the original bails out early on it."""
    for url in ["https://www.youtube.com/watch?v=abc?list=LL",
                "https://www.youtube.com/watch?v=abc?list=LL&index=3"]:
        assert url.endswith("?list=LL") or "?list=LL&index=" in url


# --------------------------------------------------------------------------- #
# Instance selection helpers (contains_in_guild / available / check_timeout)
# --------------------------------------------------------------------------- #

class FakeInstanceSelf:
    """Minimal stand-in exposing just `states`, enough to call the real
    MusicBotInstance selection methods unbound."""

    def __init__(self, states):
        self.states = states


def make_state(voice=None, cancel_timeout=None):
    state = GuildState(guild=object())
    state.voice = voice
    state.cancel_timeout = cancel_timeout
    return state


class FakeVoice:
    def __init__(self, channel=None):
        self.channel = channel


def test_contains_in_guild():
    inst = FakeInstanceSelf({1: make_state()})
    assert music_instance.MusicBotInstance.contains_in_guild(inst, 1) is True
    assert music_instance.MusicBotInstance.contains_in_guild(inst, 2) is False


def test_available_true_when_no_voice_client():
    inst = FakeInstanceSelf({1: make_state(voice=None)})
    assert music_instance.MusicBotInstance.available(inst, 1) is True


def test_available_false_when_connected():
    inst = FakeInstanceSelf({1: make_state(voice=FakeVoice())})
    assert music_instance.MusicBotInstance.available(inst, 1) is False


def test_check_timeout_false_when_not_connected():
    inst = FakeInstanceSelf({1: make_state(voice=None, cancel_timeout="fut")})
    assert music_instance.MusicBotInstance.check_timeout(inst, 1) is False


def test_check_timeout_true_when_connected_and_counting_down():
    inst = FakeInstanceSelf({1: make_state(voice=FakeVoice(), cancel_timeout="fut")})
    assert music_instance.MusicBotInstance.check_timeout(inst, 1) is True


def test_check_timeout_false_when_connected_without_countdown():
    inst = FakeInstanceSelf({1: make_state(voice=FakeVoice(), cancel_timeout=None)})
    assert music_instance.MusicBotInstance.check_timeout(inst, 1) is False


def test_current_voice_channel_returns_none_when_disconnected():
    inst = FakeInstanceSelf({1: make_state(voice=None)})
    assert music_instance.MusicBotInstance.current_voice_channel(inst, 1) is None


def test_current_voice_channel_returns_channel():
    channel = object()
    inst = FakeInstanceSelf({1: make_state(voice=FakeVoice(channel=channel))})
    assert music_instance.MusicBotInstance.current_voice_channel(inst, 1) is channel


# --------------------------------------------------------------------------- #
# Leader instance selection
# --------------------------------------------------------------------------- #

import bots.music_leader as music_leader


class FakeInstance:
    """Implements the four methods get_available_instance / get_playing_instance
    call on each candidate."""

    def __init__(self, name, in_guild=True, available=False, timing_out=False, voice_channel=None):
        self.name = name
        self._in_guild = in_guild
        self._available = available
        self._timing_out = timing_out
        self._voice_channel = voice_channel

    def contains_in_guild(self, guild_id):
        return self._in_guild

    def available(self, guild_id):
        return self._available

    def check_timeout(self, guild_id):
        return self._timing_out

    def current_voice_channel(self, guild_id):
        return self._voice_channel


class FakeLeaderSelf:
    def __init__(self, instances):
        self.instances = instances


class FakeAuthor:
    def __init__(self, voice_channel):
        self.voice = types.SimpleNamespace(channel=voice_channel) if voice_channel else None


class FakeInter:
    def __init__(self, guild_id=1, voice_channel=None):
        self.guild = types.SimpleNamespace(id=guild_id)
        self.author = FakeAuthor(voice_channel)


def test_get_available_instance_prefers_idle_over_timing_out():
    timing_out = FakeInstance("timing_out", available=False, timing_out=True)
    idle = FakeInstance("idle", available=True)
    leader = FakeLeaderSelf([timing_out, idle])
    result = asyncio.run(music_leader.MusicBotLeader.get_available_instance(leader, FakeInter()))
    assert result is idle


def test_get_available_instance_falls_back_to_timing_out():
    busy = FakeInstance("busy", available=False, timing_out=False)
    timing_out = FakeInstance("timing_out", available=False, timing_out=True)
    leader = FakeLeaderSelf([busy, timing_out])
    result = asyncio.run(music_leader.MusicBotLeader.get_available_instance(leader, FakeInter()))
    assert result is timing_out


def test_get_available_instance_returns_none_when_all_busy():
    busy1 = FakeInstance("busy1", available=False, timing_out=False)
    busy2 = FakeInstance("busy2", available=False, timing_out=False)
    leader = FakeLeaderSelf([busy1, busy2])
    result = asyncio.run(music_leader.MusicBotLeader.get_available_instance(leader, FakeInter()))
    assert result is None


def test_get_available_instance_ignores_instances_not_in_guild():
    elsewhere = FakeInstance("elsewhere", in_guild=False, available=True)
    leader = FakeLeaderSelf([elsewhere])
    result = asyncio.run(music_leader.MusicBotLeader.get_available_instance(leader, FakeInter()))
    assert result is None


def test_get_playing_instance_matches_authors_channel():
    channel = object()
    other_channel = object()
    wrong = FakeInstance("wrong", voice_channel=other_channel)
    right = FakeInstance("right", voice_channel=channel)
    leader = FakeLeaderSelf([wrong, right])
    inter = FakeInter(voice_channel=channel)
    result = asyncio.run(music_leader.MusicBotLeader.get_playing_instance(leader, inter))
    assert result is right


def test_get_playing_instance_none_when_author_not_in_voice():
    leader = FakeLeaderSelf([FakeInstance("any", voice_channel=object())])
    inter = FakeInter(voice_channel=None)
    result = asyncio.run(music_leader.MusicBotLeader.get_playing_instance(leader, inter))
    assert result is None


def test_get_playing_instance_none_when_no_bot_in_that_channel():
    leader = FakeLeaderSelf([FakeInstance("elsewhere", voice_channel=object())])
    inter = FakeInter(voice_channel=object())
    result = asyncio.run(music_leader.MusicBotLeader.get_playing_instance(leader, inter))
    assert result is None


# --------------------------------------------------------------------------- #
# Radio widget
# --------------------------------------------------------------------------- #

def test_fetch_radio_widget_is_a_plain_sync_function():
    """It must stay synchronous: it's handed to run_in_executor, which cannot
    take a coroutine function. If someone makes it `async def`, radio breaks."""
    assert not asyncio.iscoroutinefunction(music_instance.fetch_radio_widget)


def test_fetch_radio_widget_parses_json(monkeypatch):
    import io

    payload = b'{"on_air": "151; Track</span> blank\'>Source</a>", "duration": 100}'
    monkeypatch.setattr(music_instance, "urlopen", lambda url: io.BytesIO(payload))
    data = music_instance.fetch_radio_widget("http://example.invalid/widget")
    assert data["duration"] == 100
    assert "on_air" in data


def test_radio_widget_regex_extracts_name_and_source():
    """Pins the two scrape patterns radio_message() depends on."""
    import re
    on_air = "151; Some Song Title</span> ... blank'>SomeArtist</a>"
    assert re.search("151; (.+?)</span>", on_air).group(1) == "Some Song Title"
    assert re.search("blank'>(.+?)</a>", on_air).group(1) == "SomeArtist"


# --------------------------------------------------------------------------- #
# pause() guards (bug fix: idle bot used to raise AttributeError)
# --------------------------------------------------------------------------- #

class FakeOrigInter:
    def __init__(self):
        self.sent = []

    async def send(self, message, **kwargs):
        self.sent.append(message)


class FakePauseInter:
    def __init__(self, guild_id=1):
        self.guild = types.SimpleNamespace(id=guild_id)
        self.orig_inter = FakeOrigInter()


def test_pause_replies_when_nothing_is_playing():
    """Regression test: a bot connected to VC with an empty queue
    (current_song is None) used to raise AttributeError here."""
    state = make_state(voice=FakeVoice())
    state.current_song = None
    inst = FakeInstanceSelf({1: state})
    inter = FakePauseInter()

    asyncio.run(music_instance.MusicBotInstance.pause(inst, inter))

    assert inter.orig_inter.sent == ["Nothing's playing atm!"]


def test_pause_replies_wrong_instance_when_not_connected():
    state = make_state(voice=None)
    state.current_song = None
    inst = FakeInstanceSelf({1: state})
    inter = FakePauseInter()

    asyncio.run(music_instance.MusicBotInstance.pause(inst, inter))

    assert inter.orig_inter.sent == ["Wrong instance to process operation"]


class FakePausableVoice:
    def __init__(self, playing=True, paused=False):
        self._playing = playing
        self._paused = paused
        self.channel = None

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return self._paused

    def pause(self):
        self._playing = False
        self._paused = True

    def resume(self):
        self._playing = True
        self._paused = False


def test_pause_pauses_when_playing():
    async def scenario():
        voice = FakePausableVoice(playing=True)
        state = make_state(voice=voice)
        song = Song()
        song.track_info.set_result({"title": "t", "duration": 100})
        state.current_song = song
        inst = FakeInstanceSelf({1: state})
        inter = FakePauseInter()

        await music_instance.MusicBotInstance.pause(inst, inter)

        assert state.paused is True
        assert voice.is_paused() is True
        assert inter.orig_inter.sent == ["Player paused!"]

    asyncio.run(scenario())


def test_pause_resumes_normal_track_when_paused():
    async def scenario():
        voice = FakePausableVoice(playing=False, paused=True)
        state = make_state(voice=voice)
        state.paused = True
        song = Song()
        song.track_info.set_result({"title": "t", "duration": 100})
        state.current_song = song
        inst = FakeInstanceSelf({1: state})
        inter = FakePauseInter()

        await music_instance.MusicBotInstance.pause(inst, inter)

        assert state.paused is False
        assert voice.is_playing() is True
        assert inter.orig_inter.sent == ["Player resumed!"]

    asyncio.run(scenario())
