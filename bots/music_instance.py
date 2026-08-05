"""A single music bot instance: owns one Discord connection, one voice client
per guild, and the per-guild playback state (queue, current song, repeat/skip
flags, inactivity timeout).

`MusicBotLeader` (music_leader.py) subclasses this and adds the slash commands;
plain instances have no commands of their own and are driven entirely by the
leader delegating to them. That's the "several bots, one set of commands"
design described in the README.

Behavior is preserved from the original, including every minor conditional and
edge-case fix, with two exceptions - both performance fixes, both documented in
CHANGES.md and both tunable via constants at the top of this file:

  1. `radio_message()` used a blocking `urlopen()` directly on the event loop.
  2. `play_loop()` used `await asyncio.sleep(0)` as a busy-wait.

See CHANGES.md "Stage 2" for the full rationale on each.
"""

from __future__ import annotations

import asyncio
import datetime
import functools
import json
import logging
import random
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

import disnake
from disnake.ext import commands

import configs.private_config as private_config
import configs.public_config as public_config
import helpers.database_logger as database_logger
import helpers.embedder as embedder
import helpers.helpers as helpers
from helpers.view_panels import QueueList, SongSelection

logger = logging.getLogger("nazarick.music")

# How long play_loop() waits between polls while the head of the queue is still
# being resolved by yt-dlp in the background. The original used
# `asyncio.sleep(0)`, which yields to the event loop but reschedules
# immediately - a hot spin loop that pegs a CPU core for the entire duration of
# track resolution, on every bot that's loading a track. At 0.05s the worst-case
# added latency before playback starts is 50ms (inaudible), while CPU usage of
# this loop drops by orders of magnitude. Set to 0 to restore the original
# busy-wait behavior exactly.
QUEUE_POLL_INTERVAL = 0.05

# Poll interval for the radio "now playing" widget. Matches the original's
# 1-second cadence.
RADIO_POLL_INTERVAL = 1

# Poll interval used while waiting for the current track to finish. Matches the
# original's 1-second cadence.
PLAYBACK_POLL_INTERVAL = 1


def fetch_radio_widget(url: str) -> dict:
    """Fetches and parses the anison.fm status widget.

    Blocking on purpose: this is always called through `run_in_process()` (the
    shared thread pool), never directly on the event loop. In the original this
    body lived inline inside the async `radio_message()` coroutine, which meant
    a synchronous HTTP request ran on the event loop roughly once per second for
    as long as any bot was playing radio - stalling *every* bot in the process
    (they all share one loop), including their voice packet pacing and Discord
    heartbeats. Extracting it here lets it run off-loop like every other
    blocking call in this file (yt-dlp extraction, youtube search).
    """
    response = urlopen(url)
    return json.loads(response.read())


class Interaction:
    """Rebinds a slash-command interaction from the leader bot onto whichever
    instance bot will actually handle it.

    The user always types commands at the leader, but a different bot may be the
    one connected to their voice channel. This re-resolves guild/author/channel
    objects through the *target* bot's cache so the handling instance operates on
    its own objects, while `orig_inter` is kept so responses still go back to the
    original interaction the user is waiting on.
    """

    def __init__(self, bot, inter):
        self.orig_inter = None
        self.author = None
        self.guild = None
        self.text_channel = None
        self.voice_channel = None
        self.message = None

        if inter.guild:
            self.guild = bot.get_guild(inter.guild.id)
        if inter.guild:
            self.author = self.guild.get_member(inter.author.id)
            if self.author.voice:
                self.voice_channel = self.author.voice.channel
        else:
            self.author = inter.author
        self.text_channel = bot.get_partial_messageable(inter.channel.id)
        self.orig_inter = inter


class Song:
    """One queue entry.

    `track_info` is a Future rather than a plain dict because songs are queued
    immediately (to hold their position in the queue) while yt-dlp resolves them
    in the background. `play_loop` skips over entries whose Future isn't done yet
    and plays the first one that is ready, which is what lets a slow playlist
    load without blocking a quick single-track request behind it.
    """

    def __init__(self, *, author="Unknown author", radio_mode: bool = False):
        self.track_info = asyncio.Future()
        self.author = author
        self.original_message = None
        self.radio_mode = radio_mode


class GuildState:
    """Per-guild playback state for one instance."""

    def __init__(self, guild):
        self.guild = guild
        self.current_song = None
        self.skip_flag = False
        self.repeat_flag = False
        self.paused = False
        self.last_inter = None
        self.voice = None
        self.cancel_timeout = None
        self.song_queue = []
        self.last_radio_message = []

    def reset(self) -> None:
        self.skip_flag = False
        self.repeat_flag = False
        self.paused = False
        self.current_song = None
        self.last_inter = None
        self.cancel_timeout = None
        self.song_queue.clear()
        self.last_radio_message.clear()

    async def connected_to(self, vc) -> None:
        """Waits until the voice client reports it is connected to `vc`.

        Used after `move_to()` so the caller doesn't start pushing audio at a
        channel the client hasn't finished switching to yet."""
        while True:
            if self.voice.is_connected() and self.voice.channel == vc:
                break
            await asyncio.sleep(0.1)


class MusicBotInstance:

# *_______ToInherit___________________________________________________________________________________________________________________________________________

    def __init__(self, name: str, token: str, process_pool: ThreadPoolExecutor):
        self.bot = commands.InteractionBot(intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="/play", type=disnake.ActivityType.listening))
        self.name = name
        self.token = token
        self.states = {}
        self.process_pool = process_pool
        self.on_ready_flag = False

        @self.bot.event
        async def on_ready():
            if not self.on_ready_flag:
                self.on_ready_flag = True
                for guild in self.bot.guilds:
                    self.states[guild.id] = GuildState(guild)
                await database_logger.enabled(self.bot)
                print(f"{self.name} is logged as {self.bot.user}")

        @self.bot.event
        async def on_message(message):
            if not message.guild:
                if helpers.is_supreme_being(message.author):
                    await message.reply(public_config.on_message_supreme_being)
                return
            await helpers.check_mentions(message, self.bot)

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            await self.on_voice_event(member, before, after)

        @self.bot.event
        async def on_guild_join(guild):
            self.states[guild.id] = GuildState(guild)

        @self.bot.event
        async def on_disconnect():
            print(f"{self.name} has disconnected from Discord")
            # await database_logger.lost_connection(self.bot)

        @self.bot.event
        async def on_connect():
            print(f"{self.name} has connected to Discord")
            # await database_logger.lost_connection(self.bot)

    async def run(self) -> None:
        await self.bot.start(self.token)

# *_______ForLeader________________________________________________________________________________________________________________________________________

    def contains_in_guild(self, guild_id) -> bool:
        return guild_id in self.states

    def available(self, guild_id) -> bool:
        return bool(self.states[guild_id].voice is None)

    def check_timeout(self, guild_id) -> bool:
        if not self.states[guild_id].voice:
            return False
        return bool(self.states[guild_id].cancel_timeout is not None)

    def current_voice_channel(self, guild_id):
        if not self.states[guild_id].voice:
            return None
        return self.states[guild_id].voice.channel

# *_______Helpers________________________________________________________________________________________________________________________________________

    async def run_in_process(self, func, *args, **kwargs):
        """Runs a blocking callable off the event loop.

        NOTE: despite the name (kept unchanged so the leader/admin bots keep
        working), `process_pool` is a *ThreadPoolExecutor* - these run in
        threads, not processes. That's fine for everything it's used for here
        (yt-dlp extraction, youtube search, the radio widget fetch) since those
        are I/O-bound and release the GIL while waiting on the network.
        """
        return await asyncio.get_running_loop().run_in_executor(self.process_pool, functools.partial(func, *args, **kwargs))

    async def timeout(self, guild_id) -> None:
        """Starts the "everyone left the channel" countdown. Pauses playback and
        disconnects after PlayTimeout seconds unless `cancel_timeout()` fires
        first (i.e. somebody rejoins)."""
        state = self.states[guild_id]
        tm = public_config.music_settings["PlayTimeout"]
        message = await state.last_inter.text_channel.send(f"I am left alone, I will leave VC in {tm} seconds!")
        if state.voice.is_playing():
            state.voice.pause()
        state.cancel_timeout = asyncio.Future()
        try:
            resume = await asyncio.wait_for(state.cancel_timeout, tm)
            await message.delete()
            if resume and not state.paused:
                state.voice.resume()
        except Exception:
            if len(self.states[guild_id].voice.channel.members) == 1:
                try:
                    await database_logger.finished(self.states[guild_id].guild.voice_client.channel)
                except Exception:
                    logger.debug("timeout: could not log 'finished' for guild=%s", guild_id)
                await self.abort_play(guild_id, message="Left voice channel due to inactivity!")
        state.cancel_timeout = None

    async def cancel_timeout(self, guild_id, resume: bool = True) -> None:
        state = self.states[guild_id]
        if state.cancel_timeout and not state.cancel_timeout.done():
            state.cancel_timeout.set_result(resume)

    async def on_voice_event(self, member, before, after) -> None:
        guild_id = member.guild.id
        state = self.states[guild_id]
        if not state.voice:
            return
        if before.channel != state.voice.channel and after.channel != state.voice.channel:
            return

        if before.channel == after.channel:
            if helpers.get_members_except_deaf_count(state.voice.channel.members) < 1:
                if state.voice.is_playing():
                    state.voice.pause()
            elif not state.paused and not state.voice.is_playing():
                state.voice.resume()

        if member.id == self.bot.application_id and not after.channel:
            await asyncio.sleep(1)
            channel = member.guild.get_channel(before.channel.id)
            # If this bot is somehow still present in the channel after the
            # disconnect event, treat it as a transient blip and do nothing.
            for channel_member in channel.members:
                if channel_member.id == self.bot.application_id:
                    return
            await database_logger.finished(before.channel)
            return await self.abort_play(guild_id)

        if helpers.get_true_members_count(state.voice.channel.members) < 1:
            if state.cancel_timeout is None:
                await self.timeout(guild_id)
        else:
            await self.cancel_timeout(guild_id)

    async def abort_play(self, guild_id, message: str = "Finished playing music!") -> None:
        state = self.states[guild_id]
        if state.voice and message:
            try:
                voice = state.voice
                state.voice = None
                voice.stop()
                await helpers.try_function(voice.disconnect, True)
                await helpers.try_function(state.last_inter.text_channel.send, True, message)
            except Exception:
                logger.debug("abort_play: cleanup failed for guild=%s", guild_id)
        state.reset()

    async def process_song_query(self, inter, query, *, song=None, playnow: bool = False, radio: bool = False) -> None:
        state = self.states[inter.guild.id]
        if not song:
            song = Song(author=inter.author, radio_mode=radio)
            if playnow:
                state.song_queue.insert(0, song)
            else:
                state.song_queue.append(song)
        if "https://" not in query and not radio:
            asyncio.create_task(self.select_song(inter, song, query))
        else:
            asyncio.create_task(self.add_from_url_to_queue(inter, song, query, playnow=playnow))

    async def add_from_url_to_queue(self, inter, song, url, *, respond: bool = True, playnow: bool = False, playlist_future=None):
        state = self.states[inter.guild.id]
        if "?list=" in url or "&list=" in url:
            # A URL that carries a playlist id: queue the single video first
            # (so playback can start immediately), then expand the rest of the
            # playlist behind it.
            future = asyncio.Future() if "playlist" in url else None
            orig_song = await self.add_from_url_to_queue(inter, song, url[:url.find("list=") - 1], playnow=playnow, playlist_future=future)
            # "LL" is the user's private Liked Videos list - not expandable.
            if url.endswith("?list=LL") or "?list=LL&index=" in url:
                return
            if not orig_song:
                await self.add_from_playlist(inter, url, None, playnow=playnow, playlist_future=future)
            else:
                await self.add_from_playlist(inter, url, orig_song['webpage_url'], playnow=playnow, playlist_future=future)
            return
        else:
            if "playlist" in url:
                # Bare /playlist URL with no video to play first: this placeholder
                # song is removed once the playlist finishes expanding.
                asyncio.create_task(helpers.add_playlist_delayed_task(helpers.try_function, True, playlist_future, state.song_queue.remove, False, song))
                if respond:
                    await inter.orig_inter.delete_original_response()
                return
            if not song.radio_mode:
                track_info = await self.run_in_process(helpers.ytdl_extract_info, url)
                if track_info is None:
                    if respond:
                        await helpers.try_function(inter.orig_inter.delete_original_response, True)
                    await inter.text_channel.send("Error processing video, try another one!")
                    await helpers.try_function(state.song_queue.remove, False, song)
                    if not state.current_song:
                        await helpers.try_function(state.voice.disconnect, True)
                    return
                song.track_info.set_result(track_info)
                if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
                    embed = embedder.songs(
                        song.author, track_info, "Song was added to queue!")
                    song.original_message = await inter.text_channel.send("", embed=embed)
                if respond:
                    await helpers.try_function(inter.orig_inter.delete_original_response, True)
                await database_logger.added(state.guild, track_info)
            else:
                if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
                    song.original_message = await inter.text_channel.send("Radio was added to queue!")
                if respond:
                    await helpers.try_function(inter.orig_inter.delete_original_response, True)
                song.track_info.set_result(url)
            return song.track_info.result()

    async def select_song(self, inter, song, query) -> None:
        songs = await self.run_in_process(helpers.yt_search, query)
        select = SongSelection(songs, self.add_from_url_to_queue, inter, song, self)
        await inter.orig_inter.delete_original_response()
        await select.send()

    async def add_from_playlist(self, inter, url, orig_url, *, playnow: bool = False, playlist_future=None) -> None:
        state = self.states[inter.guild.id]
        msg = await inter.text_channel.send("Processing playlist...")
        # Placeholder entry that keeps the queue non-empty (and therefore keeps
        # play_loop alive) while the playlist is being resolved.
        tmp_song = Song(author=datetime.datetime.now())
        state.song_queue.append(tmp_song)
        playlist_info = await self.run_in_process(helpers.ytdl_extract_info, url)
        if playlist_info is None:
            await msg.delete()
            await inter.text_channel.send("Error processing playlist, try another one!")
            await helpers.try_function(state.song_queue.remove, False, tmp_song)
            if playlist_future:
                playlist_future.set_result(None)
            return

        if not state.voice:
            await msg.delete()
            return

        videos_amount = playlist_info['playlist_count']
        if playnow:
            # Reversed, and each entry inserted at position 0, so the playlist
            # ends up in its original order at the front of the queue.
            for entry in playlist_info['entries'][::-1]:
                if "entries" in entry:
                    url = entry["entries"][0]['webpage_url']
                else:
                    url = entry['webpage_url']
                if orig_url == url:
                    continue
                track_info = await self.run_in_process(helpers.ytdl_extract_info, url)
                if not state.voice:
                    await msg.delete()
                    return
                if not track_info:
                    videos_amount -= 1
                    continue
                song = Song(author=inter.author)
                song.track_info.set_result(track_info)
                state.song_queue.insert(0, song)
        else:
            for entry in playlist_info['entries']:
                if "entries" in entry:
                    url = entry["entries"][0]['url']
                else:
                    url = entry['url']
                if orig_url == url:
                    continue
                track_info = await self.run_in_process(helpers.ytdl_extract_info, url)
                if not state.voice:
                    await msg.delete()
                    return
                if not track_info:
                    videos_amount -= 1
                    continue
                song = Song(author=inter.author)
                song.track_info.set_result(track_info)
                state.song_queue.append(song)

        new_msg = "Playlist has been processed!"
        if videos_amount != playlist_info['playlist_count']:
            new_msg += f"\nAdded {videos_amount} out of {playlist_info['playlist_count']} tracks"
        await msg.edit(new_msg, delete_after=10)
        await helpers.try_function(state.song_queue.remove, False, tmp_song)
        if playlist_future:
            playlist_future.set_result(None)

    async def play_loop(self, guild_id) -> None:
        """Main playback loop for one guild. Runs until the queue drains or
        playback is aborted."""
        state = self.states[guild_id]
        try:
            while state.song_queue:
                # Find the first entry whose metadata has finished resolving.
                # Entries still loading are skipped rather than waited on, so a
                # slow playlist never blocks a ready single track behind it.
                pos = -1
                for i in range(0, len(state.song_queue)):
                    if state.song_queue[i].track_info.done():
                        pos = i
                        break
                if pos == -1:
                    # Nothing ready yet. The original spun here with
                    # `asyncio.sleep(0)` ("Do. Not. Ask."), which is a busy-wait
                    # that burns a core for the whole resolution window. See
                    # QUEUE_POLL_INTERVAL at the top of this file.
                    await asyncio.sleep(QUEUE_POLL_INTERVAL)
                    continue
                state.current_song = state.song_queue.pop(pos)
                current_track = await state.current_song.track_info
                if not current_track:
                    continue

                if not state.current_song.radio_mode:
                    link = current_track.get("url", None)

                    state.voice.play(disnake.FFmpegPCMAudio(source=link, **public_config.FFMPEG_OPTIONS))

                    if state.current_song.original_message:
                        await helpers.try_function(state.current_song.original_message.delete, True)

                    embed = embedder.songs(state.current_song.author, current_track, "Playing this song!")
                    await state.last_inter.text_channel.send("", embed=embed)
                    await database_logger.playing(state.guild, current_track)
                else:
                    # Radio yields to real tracks: if anything else is queued,
                    # push radio to the back and play the track instead.
                    if len(state.song_queue) > 0 and not state.song_queue[0].radio_mode:
                        state.song_queue.append(state.current_song)
                        continue
                    if state.current_song.original_message:
                        try:
                            await state.current_song.original_message.delete()
                        except Exception:
                            logger.debug("play_loop: could not delete radio original_message")
                    state.voice.play(disnake.FFmpegPCMAudio(
                        source=current_track, **public_config.FFMPEG_OPTIONS))
                    if current_track == public_config.radio_url:
                        asyncio.create_task(self.radio_message(state))

                await self.play_until_interrupt(guild_id)
                if not state.voice:
                    break

                if state.skip_flag:
                    state.voice.stop()
                    state.skip_flag = False
                elif state.repeat_flag:
                    state.song_queue.insert(
                        0, state.current_song)
            try:
                await database_logger.finished(self.states[guild_id].guild.voice_client.channel)
            except Exception:
                logger.debug("play_loop: could not log 'finished' for guild=%s", guild_id)
            await self.abort_play(guild_id)
        except Exception as err:
            print(f"Exception in play_loop: {err}")
            await database_logger.error(err, state.guild)
            await self.abort_play(guild_id)

    async def play_until_interrupt(self, guild_id) -> None:
        state = self.states[guild_id]
        try:
            while (state.voice and (state.voice.is_playing() or state.voice.is_paused()) and not state.skip_flag):
                await asyncio.sleep(PLAYBACK_POLL_INTERVAL)
        except Exception as err:
            await self.abort_play(guild_id)
            await database_logger.error(err, state.guild)
            print(f"Caught exception in play_until_interrupt: {err}")


# *_______PlayerFuncs________________________________________________________________________________________________________________________________________

    async def play(self, inter, query, playnow: bool = False, radio: bool = False):
        state = self.states[inter.guild.id]
        state.last_inter = inter
        query = query.strip()
        if not state.voice:
            ff, state.voice = await helpers.try_function(inter.voice_channel.connect, True, timeout=10)
            if not ff or not state.voice:
                await helpers.try_function(inter.orig_inter.send, True, "Couldn't connect to your voice channel, check my permissions and try again")
                await self.abort_play(inter.guild.id, message=None)
                return
            await self.process_song_query(inter, query, playnow=playnow, radio=radio)
            return asyncio.create_task(self.play_loop(inter.guild.id))

        if state.voice and inter.voice_channel == state.voice.channel:
            return await self.process_song_query(inter, query, playnow=playnow, radio=radio)

        if state.voice and inter.voice_channel != state.voice.channel:
            # Being pulled into a different channel: drop the old queue, move,
            # and start fresh with this request.
            state.voice.stop()
            await self.cancel_timeout(inter.guild.id, False)
            state.reset()
            state.last_inter = inter
            if radio:
                song = Song(author=inter.author, radio_mode=radio)
            else:
                song = Song(author=inter.author)
            if playnow:
                state.song_queue.insert(0, song)
            else:
                state.song_queue.append(song)

            ff, _ = await helpers.try_function(state.voice.move_to, True, inter.voice_channel)
            await state.connected_to(inter.voice_channel)

            await self.process_song_query(inter, query, song=song, playnow=playnow, radio=radio)

    async def stop(self, inter) -> None:
        state = self.states[inter.guild.id]
        await inter.orig_inter.delete_original_response()
        if not state.voice:
            return
        await database_logger.finished(inter.guild.voice_client.channel)
        await self.abort_play(inter.guild.id, message=f"DJ {inter.author.display_name} decided to stop!")

    async def pause(self, inter) -> None:
        state = self.states[inter.guild.id]
        # BUGFIX: the original resolved `state.current_song.track_info` *before*
        # these guards, so /pause on a bot that was connected but idle
        # (current_song is None) raised AttributeError instead of replying.
        # Both guards now run first; the track_info lookup below is only
        # reached once we know a song is actually loaded.
        if not state.voice:
            await inter.orig_inter.send("Wrong instance to process operation")
            return
        if not state.current_song:
            await inter.orig_inter.send("Nothing's playing atm!")
            return
        track_info = await state.current_song.track_info
        if state.paused:
            if state.voice.is_paused():
                # Live sources (radio, livestreams) can't be resumed - the
                # buffered position is meaningless - so they're restarted from
                # the live edge instead.
                if state.current_song.radio_mode:
                    state.voice.stop()
                    state.voice.play(disnake.FFmpegPCMAudio(
                        source=track_info, **public_config.FFMPEG_OPTIONS))
                elif helpers.get_duration(track_info) == "Live":
                    link = track_info.get("url", None)
                    state.voice.stop()
                    state.voice.play(disnake.FFmpegPCMAudio(
                        source=link, **public_config.FFMPEG_OPTIONS))
                else:
                    state.voice.resume()
            state.paused = False
            await inter.orig_inter.send("Player resumed!")
        else:
            state.paused = True
            if state.voice.is_playing():
                state.voice.pause()
            await inter.orig_inter.send("Player paused!")

    async def repeat(self, inter) -> None:
        state = self.states[inter.guild.id]
        if not state.voice:
            await inter.orig_inter.send("Wrong instance to process operation")
            return

        if state.repeat_flag:
            state.repeat_flag = False
            await inter.orig_inter.send("Repeat mode is off!")
        else:
            state.repeat_flag = True
            await inter.orig_inter.send("Repeat mode is on!")

    async def skip(self, inter) -> None:
        state = self.states[inter.guild.id]
        if not state.voice:
            return
        state.skip_flag = True
        await database_logger.skip(inter)
        await inter.orig_inter.send("Skipped current track!")

    async def queue(self, inter) -> None:
        state = self.states[inter.guild.id]
        if not state.voice:
            await inter.orig_inter.send("Wrong instance to process operation")
            return
        if not state.current_song:
            # Sentinel "nothing playing" entry; the 'artificial' key is what
            # embedder.queue() checks to render the empty-queue state.
            curr_song = {'title': "Nothing", 'webpage_url': "https://www.youtube.com/watch?v=dQw4w9WgXcQ", 'duration': 86399, 'artificial': True}
        else:
            curr_song = state.current_song.track_info.result()
        viewqueue = QueueList(state.song_queue, inter, curr_song, self)
        embed = embedder.queue(inter.guild, state.song_queue, 0, curr_song)
        await inter.orig_inter.delete_original_response()
        await viewqueue.send(embed=embed)

    async def wrong(self, inter) -> None:
        state = self.states[inter.guild.id]
        if not state.voice:
            await inter.orig_inter.send("Wrong instance to process operation")
            return

        if len(state.song_queue) > 0:
            title = "(Not yet loaded)"
            song = state.song_queue[-1]
            state.song_queue.pop(-1)
            if song.track_info.done():
                title = song.track_info.result()['title']
            await inter.orig_inter.send(f"Removed {title} from queue!")
        else:
            await inter.orig_inter.send("There are no songs in the queue!")

    async def shuffle(self, inter) -> None:
        state = self.states[inter.guild.id]
        if not state.voice:
            await inter.orig_inter.send("Wrong instance to process operation")
            return

        if len(state.song_queue) > 1:
            random.shuffle(state.song_queue)
            await inter.orig_inter.send("Shuffle completed successfully!")
        elif len(state.song_queue) == 1:
            await inter.orig_inter.send("There are no tracks to shuffle!")
        else:
            await inter.orig_inter.send("I am not playing anything!")

    async def radio_message(self, state) -> None:
        """Polls the anison.fm widget while radio is playing and posts an embed
        whenever the track changes."""
        url = public_config.radio_widget
        name = ""
        while state.current_song and state.current_song.radio_mode:
            try:
                # BUGFIX: this fetch used to run inline on the event loop (see
                # fetch_radio_widget's docstring). It now runs in the shared
                # thread pool like every other blocking call here.
                data = await self.run_in_process(fetch_radio_widget, url)
                data["duration"] -= 14
                data["name"] = re.search(
                    "151; (.+?)</span>", data['on_air']).group(1)
                if data["name"] == name or (state.voice and state.voice.is_paused()):
                    await asyncio.sleep(RADIO_POLL_INTERVAL)
                    continue
                # A real track was queued while radio was playing: hand the
                # channel over to it.
                if len(state.song_queue) > 0:
                    state.song_queue.append(state.current_song)
                    state.voice.stop()
                    return
                name = data["name"]
                data["source"] = re.search(
                    "blank'>(.+?)</a>", data['on_air']).group(1)
                data['channel'] = state.voice.channel
                if state.last_radio_message == data:
                    return
                state.last_radio_message = data
                await state.last_inter.text_channel.send("", embed=embedder.radio(data))
                await database_logger.radio(state.last_inter.guild, data)
            except Exception:
                logger.debug("radio_message: poll iteration failed", exc_info=True)
            finally:
                await asyncio.sleep(RADIO_POLL_INTERVAL)
