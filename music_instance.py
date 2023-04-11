import disnake
from disnake.ext import commands
from youtube_search import YoutubeSearch
from yt_dlp import YoutubeDL
from threading import Thread
import random
import asyncio

import config
import helpers
from embedder import Embed
from selection import SelectionPanel


class Interaction():
    orig_inter = None
    author = None
    guild = None
    text_channel = None
    voice_channel = None

    def __init__(self, bot, inter):
        self.guild = bot.get_guild(inter.guild.id)
        self.author = self.guild.get_member(inter.author.id)
        self.text_channel = bot.get_partial_messageable(inter.channel.id)
        self.orig_inter = inter
        if self.author.voice:
            self.voice_channel = self.author.voice.channel


class Song():
    track_info = None
    author = None
    original_message = None

    def __init__(self, author="Unknown author"):
        self.track_info = asyncio.Future()
        self.author = author


class GuildState():
    guild = None
    skip_flag = False
    repeat_flag = False
    paused = False
    last_inter = None
    song_queue = []

    def __init__(self, guild):
        self.guild = guild

    def reset(self):
        self.skip_flag = False
        self.repeat_flag = False
        self.paused = False
        last_inter = None


class MusicBotInstance:
    bot = None
    name = None
    logger = None
    embedder = None
    states = {}

# *_______ToInherit___________________________________________________________________________________________________________________________________________

    def __init__(self, name, logger):
        self.bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="/play", type=disnake.ActivityType.listening))
        self.name = name
        self.logger = logger
        self.embedder = Embed()

        @self.bot.event
        async def on_ready():
            print(
                f"{self.name} is logged as {self.bot.user} (ID: {self.bot.application_id})")
            self.logger.enabled(self.bot)
            for guild in self.bot.guilds:
                self.states[guild.id] = GuildState(guild)

        @self.bot.event
        async def on_guild_join(guild):
            self.states[guild.id] = GuildState(guild)

        @self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
            pass
            # guild_id = member.guild.id
            # state = self.states[guild_id]
            # voice = self.bot.get_guild(guild_id).voice_client
            # if not voice or before == after:
            #     return

            # if len(voice.channel.members) == 1:
            #     await self.timeout(member.guild.id)
            # elif state.task.cancel_timeout:
            #     state.task.cancel_timeout.set_result(1)

    async def run(self):
        await self.bot.start(config.tokens[self.name])

# *_______Helpers________________________________________________________________________________________________________________________________________

    async def timeout(self, guild_id):
        task = self.states[guild_id].task
        tm = config.music_settings["PlayTimeout"]
        message = await task.curr_inter.channel.send(f"I am left alone, I will leave VC in {tm} seconds!")
        voice = task.curr_inter.guild.voice_client
        if voice.is_playing():
            voice.pause()
        task.cancel_timeout = asyncio.Future()
        await asyncio.wait_for(task.cancel_timeout, tm)
        if not task.cancel_timeout.done():
            await self.abort_play(guild_id, message="Timeout")
        else:
            await message.delete()
            if not task.paused:
                voice.resume()
        task.cancel_timeout = None

    async def abort_play(self, guild_id, message="Finished playing music!"):
        state = self.states[guild_id]
        if not state.task:
            return
        print(f"Aborting task with message: {message}")
        voice = state.guild.voice_client
        try:
            await voice.disconnect()
            await state.task.curr_inter.channel.send(message)
        except:
            pass
        state.task = None

    async def process_song_query(self, inter, query):
        state = self.states[inter.guild.id]
        song = Song(inter.author)
        state.song_queue.append(song)
        if not "https://" in query:
            asyncio.create_task(self.select_song(inter, song, query))
        else:
            asyncio.create_task(self.add_from_url_to_queue(inter, song, query))

    async def add_from_url_to_queue(self, inter, song, url, respond=True):
        state = self.states[inter.guild.id]
        if "list" in url:
            await self.add_from_url_to_queue(inter, song, url[:url.find("list")-1])
            return self.add_from_playlist(inter, url)
        else:
            print("Downloading")    
            with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
                track_info = ytdl.extract_info(url, download=False)
            print("Downloaded")
            song.track_info.set_result(track_info)
            print(f"Added song: {track_info['webpage_url']}")
            voice = state.guild.voice_client
            if voice and (voice.is_playing() or voice.is_paused()):
                embed = self.embedder.songs(
                    song.author, track_info, "Song was added to queue!")
                song.original_message = await inter.text_channel.send("", embed=embed)
            if respond:
                await inter.orig_inter.delete_original_response()
            self.logger.added(state.guild, track_info)

    async def select_song(self, inter, song, query):
        songs = YoutubeSearch(query, max_results=5).to_dict()
        select = SelectionPanel(songs, self.add_from_url_to_queue, inter, song)
        await inter.orig_inter.delete_original_response()
        await select.send()

    def add_from_playlist(self, inter, url):
        state = self.states[inter.guild.id]
        print("Downloading")
        with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
            playlist_info = ytdl.extract_info(url, download=False)
        print("Downloaded")
        # TODO: Proper condition for not adding
        for entry in playlist_info['entries'][1:]:
            song = Song(inter.author)
            song.track_info.set_result(entry)
            state.song_queue.append(song)
            print(f"Added song: {entry['webpage_url']}")

    async def play_loop(self, guild_id):
        state = self.states[guild_id]
        try:
            print("Entered play loop")
            while state.song_queue:
                current_song = state.song_queue[0]
                state.song_queue.pop(0)
                current_track = await current_song.track_info
                if not current_track:
                    print(f"Invalid Track")
                    continue

                link = current_track.get("url", None)
                voice = state.guild.voice_client    
                voice.play(disnake.FFmpegPCMAudio(
                    source=link, **config.FFMPEG_OPTIONS))
                if current_song.original_message:
                    await current_song.original_message.delete()
                embed = self.embedder.songs(
                    current_song.author, current_track, "Playing this song!")
                await state.last_inter.text_channel.send("", embed=embed)
                await self.play_before_interrupt(guild_id)
                if not voice.is_connected():
                    break

                if state.skip_flag:
                    voice.stop()
                    state.skip_flag = False
                elif state.repeat_flag:
                    state.song_queue.insert(
                        0, current_song)
            if not state.song_queue:
                print("Queue empty")
            await self.abort_play(guild_id)
        except Exception as err:
            print(f"Execption in play_loop: {err}")
            self.logger.error(err, state.guild)
            pass

    async def play_before_interrupt(self, guild_id):
        state = self.states[guild_id]
        voice = state.guild.voice_client
        while ((voice.is_playing() or voice.is_paused()) and not state.skip_flag):
            await asyncio.sleep(1)

# *_______PlayerFuncs________________________________________________________________________________________________________________________________________

    # *Requires author of inter to be in voice channel
    async def play(self, inter, query, playnow=False):
        state = self.states[inter.guild.id]
        state.last_inter = inter
        voice = state.guild.voice_client
        voice_channel = None
        if voice:
            voice_channel = voice.channel

        if not voice or not voice.is_connected():
            voice = await inter.voice_channel.connect()
            if not voice:
                print("Failed to connect")
            await self.process_song_query(inter, query)
            return asyncio.create_task(self.play_loop(inter.guild.id))

        if voice and voice.is_connected() and inter.voice_channel == voice_channel:
            return await self.process_song_query(inter, query)

        if voice and voice.is_connected() and inter.voice_channel != voice_channel:
            # TODO: this is wrong
            print("Haha got u")
            state.reset()
            await voice.move_to(inter.voice_channel)
            voice.pause()
            await self.process_song_query(inter, query)
            state.task.skip_flag = True

    async def stop(self, inter):
        state = self.states[inter.guild.id]
        voice = state.guild.voice_client
        await inter.orig_inter.delete_original_response()
        if not voice:
            await inter.text_channel.send("Wrong instance to process operation")
            return
        
        await self.abort_play(inter.guild.id, message="DJ decided to stop!")

    async def pause(self, inter):
        state = self.states[inter.guild.id]
        voice = state.guild.voice_client
        await inter.orig_inter.delete_original_response()
        if not voice:
            await inter.text_channel.send("Wrong instance to process operation")
            return
        if state.paused:
            state.paused = False
            if voice.is_paused():
                voice.resume()
            await inter.text_channel.send("Player resumed!")
        else:
            state.paused = True
            if voice.is_playing():
                voice.pause()
            await inter.text_channel.send("Player paused!")

    async def repeat(self, inter):
        state = self.states[inter.guild.id]
        voice = state.guild.voice_client
        await inter.orig_inter.delete_original_response()
        if not voice:
            await inter.text_channel.send("Wrong instance to process operation")
            return

        if state.repeat_flag:
            state.repeat_flag = False
            await inter.text_channel.send("Repeat mode is off!")
        else:
            state.repeat_flag = True
            await inter.text_channel.send("Repeat mode is on!")

    async def skip(self, inter):
        state = self.states[inter.guild.id]
        voice = state.guild.voice_client
        await inter.orig_inter.delete_original_response()
        if not voice:
            await inter.text_channel.send("Wrong instance to process operation")
            return
        state.skip_flag = True
        await inter.text_channel.send("Skipped current track!")

    async def queue(self, inter):
        state = self.states[inter.guild.id]
        voice = state.guild.voice_client
        await inter.orig_inter.delete_original_response()
        if not voice:
            await inter.text_channel.send("Wrong instance to process operation")
            return

        if len(state.song_queue) > 0:
            cnt = 1
            ans = "```Queue:"
            for song in state.song_queue[:15]:
                # TODO: Maybe show that song being loaded
                if not song.track_info.done():
                    continue
                track = song.track_info.result()
                if "live_status" in track and track['live_status'] == "is_live":
                    duration = "Live"
                else:
                    duration = helpers.get_duration(track)
                ans += f"\n{cnt}) {track['title']}, duration: {duration}"
                cnt += 1
            ans += "```"
            await inter.text_channel.send(ans)
        else:
            await inter.text_channel.send("There are no songs in the queue!")

    async def wrong(self, inter):
        state = self.states[inter.guild.id]
        voice = state.guild.voice_client
        await inter.orig_inter.delete_original_response()
        if not voice:
            await inter.text_channel.send("Wrong instance to process operation")
            return

        if len(state.song_queue) > 0:
            title = "(Not yet loaded)"
            song = state.song_queue[-1]
            state.song_queue.pop(-1)
            if song.track_info.done():
                title = song.track_info.result()['title']
            await inter.text_channel.send(f"Removed {title} from queue!")
        else:
            await inter.text_channel.send("There are no songs in the queue!")

    async def shuffle(self, inter):
        state = self.states[inter.guild.id]
        voice = state.guild.voice_client
        await inter.orig_inter.delete_original_response()
        if not voice:
            await inter.text_channel.send("Wrong instance to process operation")
            return

        if len(state.song_queue) > 1:
            random.shuffle(state.song_queue)
            await inter.text_channel.send("Shuffle completed successfully!")
        elif len(state.song_queue) == 1:
            await inter.text_channel.send("There are no tracks to shuffle!")
        else:
            await inter.text_channel.send("I am not playing anything!")
