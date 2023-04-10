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


class PlayTask():
    curr_inter = None
    skip_flag = False
    repeat_flag = False
    song_queue = []


class Interaction():
    author = None
    channel = None
    guild = None
    response = None

    def __init__(self, inter, bot):
        self.guild = bot.get_guild(inter.guild.id)
        self.author = self.guild.get_member(inter.author.id)
        self.channel = bot.get_partial_messageable(inter.channel.id)


class GuildState():
    task = None


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
                f"{self.name} is logged as {self.bot.user}")
            self.logger.enabled(self.bot)
            for guild in self.bot.guilds:
                self.states[guild.id] = GuildState()

        @self.bot.event
        async def on_guild_join(guild):
            self.states[guild.id] = GuildState()

        # @self.bot.event
        # async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
        #     await self.check_timeout(member, before, after)

    async def run(self):
        await self.bot.start(config.tokens[self.name])

    async def empty_response(self, inter):
        await inter.response.defer()
        await inter.delete_original_response()

# *_______PlayerFuncs________________________________________________________________________________________________________________________________________

    async def check_timeout(self, member, before: disnake.VoiceState, after: disnake.VoiceState):
        voice = member.guild.voice_client
        if voice and before.channel and before.channel != after.channel and len(voice.channel.members) == 1:
            await self.timeout(member.guild.id)

    async def abort_task(self, guild_id, message="Finished playing music!"):
        state = self.states[guild_id]
        if not state.task:
            return
        print("Aborting task")
        voice = state.task.curr_inter.guild.voice_client
        try:
            voice.stop()
            await voice.disconnect()
            await state.task.curr_inter.channel.send(message)
        except:
            pass
        state.task = None

    async def process_song_query(self, guild_id, query):
        print("Proc query")
        if not "https://" in query:
            return await self.select_song(guild_id, query)
        else:
            await self.add_from_url_to_queue(guild_id, query)

    async def add_from_url_to_queue(self, guild_id, url):
        print("add_from_url_to_queue")
        task = self.states[guild_id].task
        if "list" in url:
            await self.add_from_url_to_queue(guild_id, url[:url.find("list")-1])
            thread = Thread(target=self.add_from_playlist,
                            args=(guild_id, url))
            thread.start()
        else:
            with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
                track_info = ytdl.extract_info(url, download=False)
            task.song_queue.append(track_info)
            voice = task.curr_inter.guild.voice_client
            if voice.is_playing() or voice.is_paused():
                embed = self.embedder.songs(
                    task.curr_inter, track_info, "Song was added to queue!")
                track_info['original_message'] = await task.curr_inter.channel.send("", embed=embed)
            else:
                track_info['original_message'] = None
            self.logger.added(task.curr_inter, track_info)

    async def select_song(self, guild_id, query):
        print("Selecting song")
        task = self.states[guild_id].task
        songs = YoutubeSearch(query, max_results=5).to_dict()
        view = disnake.ui.View(timeout=30)
        select = SelectionPanel(songs, self.add_from_url_to_queue,
                                task.curr_inter.author, guild_id)
        view.add_item(select)
        message = await task.curr_inter.channel.send(view=view)
        # TODO: Try find another timeout mechanism
        try:
            voice = task.curr_inter.guild.voice_client
            for i in range(30):
                if select.done:
                    return await message.delete()
                await asyncio.sleep(1)

            await message.delete()
            await voice.disconnect()
            message = await task.curr_inter.channel.send(f"{task.curr_inter.author.mention} You're out of time! Next time think faster!")
            await asyncio.sleep(5)
            await message.delete()
        except:
            pass

    # * Play command requires valid client of inter (in voice channel without MusicBotInstances or with that MusicBotInstance)
    async def play(self, inter, query):
        state = self.states[inter.guild.id]
        user_channel = inter.author.voice.channel

        voice = inter.guild.voice_client
        if state.task and voice.channel == user_channel:
            await self.process_song_query(inter.guild.id, query)
            return
        elif state.task:
            voice.stop()
            await voice.move_to(user_channel)
        else:
            voice = await user_channel.connect()

        state.task = PlayTask()
        task = state.task
        task.curr_inter = inter
        await self.process_song_query(inter.guild.id, query)

        asyncio.create_task(self.play_loop(inter.guild.id))

    async def play_loop(self, guild_id):
        task = self.states[guild_id].task
        voice = task.curr_inter.guild.voice_client
        try:
            print("Alive")
            while True:
                if not task.song_queue:  
                    await self.abort_task(guild_id)
                    break;
                current_track = task.song_queue[0]
                task.song_queue.pop(0)
                link = current_track.get("url", None)
                voice.play(disnake.FFmpegPCMAudio(
                    source=link, **config.FFMPEG_OPTIONS))
                embed = self.embedder.songs(
                    task.curr_inter, current_track, "Playing this song!")
                if current_track['original_message']:
                    await current_track['original_message'].delete()
                await task.curr_inter.channel.send("", embed=embed)
                self.logger.playing(task.curr_inter, current_track)
                while ((voice.is_playing() or voice.is_paused()) and not task.skip_flag):
                    await asyncio.sleep(1)

                if task.skip_flag:
                    voice.stop()
                    task.skip_flag = False

                elif task.repeat_flag:
                    task.song_queue.insert(
                        0, current_track)

                if not voice.is_connected():
                    break
        except Exception as err:
            print(f"Error occured in play loop: {err}")
            self.logger.error(err, task.curr_inter.guild)
            await self.abort_task(guild_id)
            pass

    async def check_timeout(self, member, before: disnake.VoiceState, after: disnake.VoiceState):
        voice = member.guild.voice_client
        if voice and before.channel and before.channel != after.channel and len(voice.channel.members) == 1:
            await self.timeout(member.guild.id)

    def add_from_playlist(self, guild_id, url):
        print(f"Adding from playlist: {url}")
        task = self.states[guild_id].task

        with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
            playlist_info = ytdl.extract_info(url, download=False)
        if not task:
            return
        for entry in playlist_info['entries'][1:]:
            print("Adding song")
            entry['original_message'] = None
            task.song_queue.append(entry)
        print("Added from playlist")

    def help(self):
        ans = "Type /play to order a song (use URL from YT or just type the song's name)\n"
        ans += "Type /stop to stop playback\n"
        ans += "Type /skip to skip current track\n"
        ans += "Type /queue to print current queue\n"
        ans += "Type /shuffle to shuffle tracks in the queue\n"
        ans += "Type /wrong to remove last added track\n"
        ans += "Type /repeat to toogle repeat mode for current track\n"
        ans += "Type /pause to pause/resume playback"
        return ans

    async def timeout(self, guild_id):
        task = self.states[guild_id].task
        message = await task.curr_inter.channel.send("I am left alone, I will leave VC in 30 seconds!")
        voice = task.curr_inter.guild.voice_client
        try:
            for i in range(30):
                if not voice or len(voice.channel.members) > 1:
                    await message.delete()
                    return
                await asyncio.sleep(1)
        except Exception as err:
            self.logger.error(err, task.curr_inter.guild)
        await self.abort_task(guild_id)

    async def stop(self, inter):
        await self.abort_task(inter.guild.id, message="DJ decided to stop!")

    async def pause(self, inter):
        if not self.states[inter.guild.id].task:
            return
        voice = inter.guild.voice_client
        if voice.is_paused():
            voice.resume()
            await inter.channel.send("Player resumed!")
        else:
            voice.pause()
            await inter.channel.send("Player paused!")

    async def repeat(self, inter):
        task = self.states[inter.guild.id]
        if not task:
            return

        if task.repeat_flag:
            task.repeat_flag = False
            await inter.channel.send("Repeat mode is off!")
        else:
            task.repeat_flag = True
            await inter.channel.send("Repeat mode is on!")

    async def skip(self, inter):
        task = self.states[inter.guild.id]
        if not task:
            return
        task.skip_flag = True
        self.logger.skip(inter)
        await inter.channel.send("Skipped current track!")

    async def queue(self, inter):
        task = self.states[inter.guild.id].task
        if not task:
            return
        if len(task.song_queue) > 0:
            cnt = 1
            ans = "```Queue:"
            for track in task.song_queue[:15]:
                if "live_status" in track and track['live_status'] == "is_live":
                    duration = "Live"
                else:
                    duration = helpers.get_duration(track)
                ans += f"\n{cnt}) {track['title']}, duration: {duration}"
                cnt += 1
            ans += "```"
            await inter.channel.send(ans)
        else:
            await inter.channel.send("There are no songs in the queue!")

    async def wrong(self, inter):
        task = self.states[inter.guild.id].task
        if not task:
            return
        if len(task.song_queue) > 0:
            title = task.song_queue[-1]['title']
            task.song_queue.pop(-1)
            await inter.channel.send(f"Removed {title} from queue!")
        else:
            await inter.channel.send("There are no songs in the queue!")

    async def shuffle(self, inter):
        task = self.states[inter.guild.id].task
        if not task:
            return
        if len(task.song_queue) > 1:
            random.shuffle(self.song_queue)
            await inter.channel.send("Shuffle completed successfully!")
        elif len(task.song_queue) == 1:
            await inter.channel.send("There are no tracks to shuffle!")
        else:
            await inter.channel.send("I am not playing anything!")
