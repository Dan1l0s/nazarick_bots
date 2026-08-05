"""Unit tests for the MusicBotInstance player commands and teardown paths.

These call the real methods unbound against fakes, the same approach as
test_music.py, but focus on the command handlers (`skip`, `stop`, `wrong`,
`shuffle`, `queue`, `repeat`, `abort_play`, `cancel_timeout`) rather than the
state machine.
"""

import asyncio
import types

import pytest

import bots.music_instance as music_instance
import helpers.database_logger as database_logger
import helpers.helpers as helpers
from bots.music_instance import GuildState, Song


class Recorder:
    """Collects everything sent back to the user."""

    def __init__(self):
        self.sent = []
        self.deleted_original = False

    async def send(self, message=None, **kwargs):
        self.sent.append(message)

    async def delete_original_response(self):
        self.deleted_original = True


class FakeTextChannel:
    def __init__(self):
        self.sent = []

    async def send(self, message=None, **kwargs):
        self.sent.append(message)
        return types.SimpleNamespace(delete=_noop_async, edit=_noop_async)


async def _noop_async(*args, **kwargs):
    return None


class FakeInter:
    def __init__(self, guild_id=1, author_name="Dan"):
        self.guild = types.SimpleNamespace(
            id=guild_id,
            voice_client=types.SimpleNamespace(channel=types.SimpleNamespace(guild=types.SimpleNamespace(id=guild_id))),
        )
        self.author = types.SimpleNamespace(display_name=author_name, id=7)
        self.orig_inter = Recorder()
        self.text_channel = FakeTextChannel()


class FakeVoice:
    def __init__(self, playing=True, connected=True, channel=None):
        self._playing = playing
        self._connected = connected
        self.channel = channel
        self.stopped = False
        self.disconnected = False

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return False

    def is_connected(self):
        return self._connected

    def stop(self):
        self.stopped = True
        self._playing = False

    async def disconnect(self, **kwargs):
        self.disconnected = True


class FakeSelf:
    """Stands in for `self`. `abort_play` is bound to the real implementation so
    teardown paths that delegate to it (stop, timeout) exercise the real code."""

    def __init__(self, states):
        self.states = states

    async def abort_play(self, guild_id, message="Finished playing music!"):
        return await music_instance.MusicBotInstance.abort_play(self, guild_id, message=message)


@pytest.fixture(autouse=True)
def silence_database_logger(monkeypatch):
    """The player methods log to db/logs.db; stub those out so tests don't
    touch the filesystem."""
    for name in ("skip", "finished", "playing", "added", "radio", "error"):
        monkeypatch.setattr(database_logger, name, _noop_async)


def state_with_voice(voice=None, current_song=None, queue=None):
    state = GuildState(guild=types.SimpleNamespace(id=1))
    state.voice = voice
    state.current_song = current_song
    if queue:
        state.song_queue.extend(queue)
    return state


# --------------------------------------------------------------------------- #
# skip
# --------------------------------------------------------------------------- #

def test_skip_sets_flag_and_replies():
    state = state_with_voice(voice=FakeVoice())
    inter = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.skip(FakeSelf({1: state}), inter))
    assert state.skip_flag is True
    assert inter.orig_inter.sent == ["Skipped current track!"]


def test_skip_is_a_noop_when_not_connected():
    state = state_with_voice(voice=None)
    inter = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.skip(FakeSelf({1: state}), inter))
    assert state.skip_flag is False
    assert inter.orig_inter.sent == []


# --------------------------------------------------------------------------- #
# repeat
# --------------------------------------------------------------------------- #

def test_repeat_toggles_on_then_off():
    state = state_with_voice(voice=FakeVoice())
    me = FakeSelf({1: state})

    inter = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.repeat(me, inter))
    assert state.repeat_flag is True
    assert inter.orig_inter.sent == ["Repeat mode is on!"]

    inter2 = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.repeat(me, inter2))
    assert state.repeat_flag is False
    assert inter2.orig_inter.sent == ["Repeat mode is off!"]


def test_repeat_rejects_wrong_instance():
    state = state_with_voice(voice=None)
    inter = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.repeat(FakeSelf({1: state}), inter))
    assert inter.orig_inter.sent == ["Wrong instance to process operation"]


# --------------------------------------------------------------------------- #
# wrong (remove last queued track)
# --------------------------------------------------------------------------- #

def test_wrong_removes_last_resolved_track_by_title():
    async def scenario():
        song = Song()
        song.track_info.set_result({"title": "Last Song", "duration": 10})
        state = state_with_voice(voice=FakeVoice(), queue=[song])
        inter = FakeInter()
        await music_instance.MusicBotInstance.wrong(FakeSelf({1: state}), inter)
        return state, inter

    state, inter = asyncio.run(scenario())
    assert state.song_queue == []
    assert inter.orig_inter.sent == ["Removed Last Song from queue!"]


def test_wrong_reports_placeholder_for_unresolved_track():
    async def scenario():
        song = Song()  # still loading
        state = state_with_voice(voice=FakeVoice(), queue=[song])
        inter = FakeInter()
        await music_instance.MusicBotInstance.wrong(FakeSelf({1: state}), inter)
        return state, inter

    state, inter = asyncio.run(scenario())
    assert state.song_queue == []
    assert inter.orig_inter.sent == ["Removed (Not yet loaded) from queue!"]


def test_wrong_on_empty_queue():
    state = state_with_voice(voice=FakeVoice())
    inter = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.wrong(FakeSelf({1: state}), inter))
    assert inter.orig_inter.sent == ["There are no songs in the queue!"]


# --------------------------------------------------------------------------- #
# shuffle
# --------------------------------------------------------------------------- #

def test_shuffle_with_multiple_tracks():
    async def scenario():
        state = state_with_voice(voice=FakeVoice(), queue=[Song(), Song(), Song()])
        inter = FakeInter()
        await music_instance.MusicBotInstance.shuffle(FakeSelf({1: state}), inter)
        return state, inter

    state, inter = asyncio.run(scenario())
    assert len(state.song_queue) == 3
    assert inter.orig_inter.sent == ["Shuffle completed successfully!"]


def test_shuffle_with_single_track():
    async def scenario():
        state = state_with_voice(voice=FakeVoice(), queue=[Song()])
        inter = FakeInter()
        await music_instance.MusicBotInstance.shuffle(FakeSelf({1: state}), inter)
        return inter

    inter = asyncio.run(scenario())
    assert inter.orig_inter.sent == ["There are no tracks to shuffle!"]


def test_shuffle_with_empty_queue():
    state = state_with_voice(voice=FakeVoice())
    inter = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.shuffle(FakeSelf({1: state}), inter))
    assert inter.orig_inter.sent == ["I am not playing anything!"]


def test_shuffle_rejects_wrong_instance():
    state = state_with_voice(voice=None)
    inter = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.shuffle(FakeSelf({1: state}), inter))
    assert inter.orig_inter.sent == ["Wrong instance to process operation"]


# --------------------------------------------------------------------------- #
# stop
# --------------------------------------------------------------------------- #

def test_stop_disconnects_and_names_the_dj():
    voice = FakeVoice()
    state = state_with_voice(voice=voice)
    state.last_inter = FakeInter()
    # hold our own reference: reset() clears state.last_inter during teardown
    channel = state.last_inter.text_channel
    inter = FakeInter(author_name="Dan")

    asyncio.run(music_instance.MusicBotInstance.stop(FakeSelf({1: state}), inter))

    assert inter.orig_inter.deleted_original is True
    assert voice.disconnected is True
    assert state.voice is None
    assert state.last_inter is None
    assert any("Dan decided to stop!" in m for m in channel.sent)


def test_stop_when_not_connected_only_clears_the_response():
    state = state_with_voice(voice=None)
    inter = FakeInter()
    asyncio.run(music_instance.MusicBotInstance.stop(FakeSelf({1: state}), inter))
    assert inter.orig_inter.deleted_original is True


# --------------------------------------------------------------------------- #
# abort_play
# --------------------------------------------------------------------------- #

def test_abort_play_stops_disconnects_and_resets():
    async def scenario():
        voice = FakeVoice()
        song = Song()
        state = state_with_voice(voice=voice, current_song=song, queue=[Song()])
        state.last_inter = FakeInter()
        state.repeat_flag = True
        await music_instance.MusicBotInstance.abort_play(FakeSelf({1: state}), 1)
        return state, voice

    state, voice = asyncio.run(scenario())
    assert voice.stopped is True
    assert voice.disconnected is True
    assert state.voice is None
    assert state.current_song is None
    assert state.song_queue == []
    assert state.repeat_flag is False


def test_abort_play_with_message_none_skips_the_notice():
    async def scenario():
        voice = FakeVoice()
        state = state_with_voice(voice=voice)
        state.last_inter = FakeInter()
        await music_instance.MusicBotInstance.abort_play(FakeSelf({1: state}), 1, message=None)
        return state, voice

    state, voice = asyncio.run(scenario())
    # message=None means the whole disconnect block is skipped; only reset runs
    assert voice.disconnected is False
    assert state.current_song is None


def test_abort_play_when_already_disconnected_still_resets():
    async def scenario():
        state = state_with_voice(voice=None, queue=[Song()])
        state.skip_flag = True
        await music_instance.MusicBotInstance.abort_play(FakeSelf({1: state}), 1)
        return state

    state = asyncio.run(scenario())
    assert state.song_queue == []
    assert state.skip_flag is False


# --------------------------------------------------------------------------- #
# cancel_timeout
# --------------------------------------------------------------------------- #

def test_cancel_timeout_resolves_the_future():
    async def scenario():
        state = state_with_voice(voice=FakeVoice())
        state.cancel_timeout = asyncio.Future()
        await music_instance.MusicBotInstance.cancel_timeout(FakeSelf({1: state}), 1, resume=True)
        return state.cancel_timeout

    fut = asyncio.run(scenario())
    assert fut.done() and fut.result() is True


def test_cancel_timeout_passes_resume_false_through():
    async def scenario():
        state = state_with_voice(voice=FakeVoice())
        state.cancel_timeout = asyncio.Future()
        await music_instance.MusicBotInstance.cancel_timeout(FakeSelf({1: state}), 1, resume=False)
        return state.cancel_timeout

    fut = asyncio.run(scenario())
    assert fut.result() is False


def test_cancel_timeout_is_safe_when_no_countdown_running():
    async def scenario():
        state = state_with_voice(voice=FakeVoice())
        state.cancel_timeout = None
        await music_instance.MusicBotInstance.cancel_timeout(FakeSelf({1: state}), 1)

    asyncio.run(scenario())  # must not raise


def test_cancel_timeout_does_not_resolve_twice():
    async def scenario():
        state = state_with_voice(voice=FakeVoice())
        fut = asyncio.Future()
        fut.set_result("already")
        state.cancel_timeout = fut
        await music_instance.MusicBotInstance.cancel_timeout(FakeSelf({1: state}), 1)
        return fut

    fut = asyncio.run(scenario())
    assert fut.result() == "already"


# --------------------------------------------------------------------------- #
# process_song_query routing
# --------------------------------------------------------------------------- #

def test_process_song_query_routes_url_to_downloader(monkeypatch):
    async def scenario():
        state = state_with_voice(voice=FakeVoice())
        me = FakeSelf({1: state})
        calls = []

        async def fake_add(*args, **kwargs):
            calls.append("url")

        async def fake_select(*args, **kwargs):
            calls.append("search")

        me.add_from_url_to_queue = fake_add
        me.select_song = fake_select
        inter = FakeInter()

        await music_instance.MusicBotInstance.process_song_query(
            me, inter, "https://www.youtube.com/watch?v=abc")
        await asyncio.sleep(0)   # let the created task run
        return calls, state

    calls, state = asyncio.run(scenario())
    assert calls == ["url"]
    assert len(state.song_queue) == 1


def test_process_song_query_routes_text_to_search():
    async def scenario():
        state = state_with_voice(voice=FakeVoice())
        me = FakeSelf({1: state})
        calls = []

        async def fake_add(*args, **kwargs):
            calls.append("url")

        async def fake_select(*args, **kwargs):
            calls.append("search")

        me.add_from_url_to_queue = fake_add
        me.select_song = fake_select

        await music_instance.MusicBotInstance.process_song_query(
            me, FakeInter(), "never gonna give you up")
        await asyncio.sleep(0)
        return calls

    assert asyncio.run(scenario()) == ["search"]


def test_process_song_query_playnow_inserts_at_front():
    async def scenario():
        existing = Song()
        state = state_with_voice(voice=FakeVoice(), queue=[existing])
        me = FakeSelf({1: state})
        me.add_from_url_to_queue = _noop_async
        me.select_song = _noop_async

        await music_instance.MusicBotInstance.process_song_query(
            me, FakeInter(), "https://youtu.be/x", playnow=True)
        await asyncio.sleep(0)
        return state, existing

    state, existing = asyncio.run(scenario())
    assert state.song_queue[0] is not existing
    assert state.song_queue[1] is existing


def test_process_song_query_radio_skips_search_even_without_url():
    async def scenario():
        state = state_with_voice(voice=FakeVoice())
        me = FakeSelf({1: state})
        calls = []

        async def fake_add(*args, **kwargs):
            calls.append("url")

        async def fake_select(*args, **kwargs):
            calls.append("search")

        me.add_from_url_to_queue = fake_add
        me.select_song = fake_select

        await music_instance.MusicBotInstance.process_song_query(
            me, FakeInter(), "not-a-url", radio=True)
        await asyncio.sleep(0)
        return calls, state

    calls, state = asyncio.run(scenario())
    assert calls == ["url"]
    assert state.song_queue[0].radio_mode is True
