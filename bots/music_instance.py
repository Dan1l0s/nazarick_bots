import disnake
from disnake.ext import commands
import functools
import random
import asyncio
import json
import re
import datetime
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor


import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers
import helpers.database_logger as database_logger
import helpers.embedder as embedder

from helpers.view_panels import SongSelection, QueueList


class Interaction():
    orig_inter = None
    author = None
    guild = None
    text_channel = None
    voice_channel = None
    message = None

    def __init__(self, bot, inter):
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


class Song():
    track_info = None
    author = None
    original_message = None
    radio_mode = None

    def __init__(self, *, author="Unknown author", radio_mode=False):
        self.track_info = asyncio.Future()
        self.author = author
        self.radio_mode = radio_mode


class GuildState():
    current_song = None
    guild = None
    skip_flag = None
    repeat_flag = None
    paused = None
    last_inter = None
    voice = None
    cancel_timeout = None
    song_queue = None
    last_radio_message = None

    def __init__(self, guild):
        self.guild = guild
        self.skip_flag = False
        self.repeat_flag = False
        self.paused = False
        self.song_queue = []
        self.last_radio_message = []

    def reset(self):
        self.skip_flag = False
        self.repeat_flag = False
        self.paused = False
        self.current_song = None
        self.last_inter = None
        self.cancel_timeout = None
        self.song_queue.clear()
        self.last_radio_message.clear()

    async def connected_to(self, vc):
        while True:
            if self.voice.is_connected() and self.voice.channel == vc:
                break
            await asyncio.sleep(0.1)


class MusicBotInstance:
    bot = None
    name = None
    states = None
    process_pool = None
    token = None
    on_ready_flag = None

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

    async def run(self):
        await self.bot.start(self.token)

# *_______ForLeader________________________________________________________________________________________________________________________________________

    def contains_in_guild(self, guild_id):
        return guild_id in self.states

    def available(self, guild_id):
        return bool(self.states[guild_id].voice == None)

    def check_timeout(self, guild_id):
        if not self.states[guild_id].voice:
            return False
        return bool(self.states[guild_id].cancel_timeout != None)

    def current_voice_channel(self, guild_id):
        if not self.states[guild_id].voice:
            return None
        return self.states[guild_id].voice.channel

# *_______Helpers________________________________________________________________________________________________________________________________________

    async def run_in_process(self, func, *args, **kwargs):
        return await asyncio.get_running_loop().run_in_executor(self.process_pool, functools.partial(func, *args, **kwargs))

    async def timeout(self, guild_id):
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
        except:
            if len(self.states[guild_id].voice.channel.members) == 1:
                try:
                    await database_logger.finished(self.states[guild_id].guild.voice_client.channel)
                except:
                    pass
                await self.abort_play(guild_id, message="Left voice channel due to inactivity!")
        state.cancel_timeout = None

    async def cancel_timeout(self, guild_id, resume=True):
        state = self.states[guild_id]
        if state.cancel_timeout and not state.cancel_timeout.done():
            state.cancel_timeout.set_result(resume)

    async def on_voice_event(self, member, before, after):
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
            for member in channel.members:
                if member.id == self.bot.application_id:
                    return
            await database_logger.finished(before.channel)
            return await self.abort_play(guild_id)

        if helpers.get_true_members_count(state.voice.channel.members) < 1:
            if state.cancel_timeout == None:
                await self.timeout(guild_id)
        else: 
            await self.cancel_timeout(guild_id)

    async def abort_play(self, guild_id, message="Finished playing music!"):
        state = self.states[guild_id]
        if state.voice and message:
            try:
                voice = state.voice
                state.voice = None
                voice.stop()
                await helpers.try_function(voice.disconnect, True)
                await helpers.try_function(state.last_inter.text_channel.send, True, message)
            except:
                pass
        state.reset()

    async def process_song_query(self, inter, query, *, song=None, playnow=False, radio=False):
        state = self.states[inter.guild.id]
        if not song:
            song = Song(author=inter.author, radio_mode=radio)
            if playnow:
                state.song_queue.insert(0, song)
            else:
                state.song_queue.append(song)
        if not "https://" in query and not radio:
            asyncio.create_task(self.select_song(inter, song, query))
        else:
            asyncio.create_task(self.add_from_url_to_queue(inter, song, query, playnow=playnow))

    async def add_from_url_to_queue(self, inter, song, url, *, respond=True, playnow=False, playlist_future=None):
        state = self.states[inter.guild.id]
        if "?list=" in url or "&list=" in url:
            future = (None, asyncio.Future())["playlist" in url]
            orig_song = await self.add_from_url_to_queue(inter, song, url[:url.find("list=") - 1], playnow=playnow, playlist_future=future)
            if url.endswith("?list=LL") or "?list=LL&index=" in url:
                return
            if not orig_song:
                await self.add_from_playlist(inter, url, None, playnow=playnow, playlist_future=future)
            else:
                await self.add_from_playlist(inter, url, orig_song['webpage_url'], playnow=playnow, playlist_future=future)
            return
        else:
            if "playlist" in url:
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

    async def select_song(self, inter, song, query):
        songs = await self.run_in_process(helpers.yt_search, query)
        select = SongSelection(songs, self.add_from_url_to_queue, inter, song, self)
        await inter.orig_inter.delete_original_response()
        await select.send()

    async def add_from_playlist(self, inter, url, orig_url, *, playnow=False, playlist_future=None):
        state = self.states[inter.guild.id]
        msg = await inter.text_channel.send("Processing playlist...")
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

    async def play_loop(self, guild_id):
        state = self.states[guild_id]
        try:
            while state.song_queue:
                pos = -1
                for i in range(0, len(state.song_queue)):
                    if state.song_queue[i].track_info.done():
                        pos = i
                        break
                if pos == -1:
                    await asyncio.sleep(0)  # Do. Not. Ask.
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
                    if len(state.song_queue) > 0 and not state.song_queue[0].radio_mode:
                        state.song_queue.append(state.current_song)
                        continue
                    if state.current_song.original_message:
                        try:
                            await state.current_song.original_message.delete()
                        except:
                            pass
                    state.voice.play(disnake.FFmpegPCMAudio(
                        source=current_track, **public_config.FFMPEG_OPTIONS))
                    if (current_track == public_config.radio_url):
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
            except:
                pass
            await self.abort_play(guild_id)
        except Exception as err:
            print(f"Exception in play_loop: {err}")
            await database_logger.error(err, state.guild)
            await self.abort_play(guild_id)

    async def play_until_interrupt(self, guild_id):
        state = self.states[guild_id]
        try:
            while (state.voice and (state.voice.is_playing() or state.voice.is_paused()) and not state.skip_flag):
                await asyncio.sleep(1)
        except Exception as err:
            await self.abort_play(guild_id)
            await database_logger.error(err, state.guild)
            print(f"Caught exception in play_until_interrupt: {err}")


# *_______PlayerFuncs________________________________________________________________________________________________________________________________________

    async def play(self, inter, query, playnow=False, radio=False):
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

    async def stop(self, inter):
        state = self.states[inter.guild.id]
        await inter.orig_inter.delete_original_response()
        if not state.voice:
            return
        await database_logger.finished(inter.guild.voice_client.channel)
        await self.abort_play(inter.guild.id, message=f"DJ {inter.author.display_name} decided to stop!")

    async def pause(self, inter):
        state = self.states[inter.guild.id]
        track_info = await state.current_song.track_info
        if not state.voice:
            await inter.orig_inter.send("Wrong instance to process operation")
            return
        if state.paused:
            if state.voice.is_paused():
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

    async def repeat(self, inter):
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

    async def skip(self, inter):
        state = self.states[inter.guild.id]
        if not state.voice:
            return
        state.skip_flag = True
        await database_logger.skip(inter)
        await inter.orig_inter.send("Skipped current track!")

    async def queue(self, inter):
        state = self.states[inter.guild.id]
        if not state.voice:
            await inter.orig_inter.send("Wrong instance to process operation")
            return
        if not state.current_song:
            curr_song = {'title': "Nothing", 'webpage_url': "https://www.youtube.com/watch?v=dQw4w9WgXcQ", 'duration': 86399, 'artificial': True}
        else:
            curr_song = state.current_song.track_info.result()
        viewqueue = QueueList(state.song_queue, inter, curr_song, self)
        embed = embedder.queue(inter.guild, state.song_queue, 0, curr_song)
        await inter.orig_inter.delete_original_response()
        await viewqueue.send(embed=embed)

    async def wrong(self, inter):
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

    async def shuffle(self, inter):
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

    async def radio_message(self, state):
        url = public_config.radio_widget
        name = ""
        while state.current_song and state.current_song.radio_mode:
            try:
                response = urlopen(url)
                data = json.loads(response.read())
                data["duration"] -= 14
                data["name"] = re.search(
                    "151; (.+?)</span>", data['on_air']).group(1)
                if data["name"] == name or (state.voice and state.voice.is_paused()):
                    await asyncio.sleep(1)
                    continue
                if len(state.song_queue) > 0:
                    state.song_queue.append(state.current_song)
                    state.voice.stop()
                    return
                name = data["name"]
                data["source"] = re.search(
                    "blank'>(.+?)</a>", data['on_air']).group(1)
                data['channel'] = state.voice.channel
                if (state.last_radio_message == data):
                    return
                state.last_radio_message = data
                await state.last_inter.text_channel.send("", embed=embedder.radio(data))
                await database_logger.radio(state.last_inter.guild, data)
            except:
                pass
            finally:
                await asyncio.sleep(1)
