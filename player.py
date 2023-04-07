import disnake
from youtube_search import YoutubeSearch
from yt_dlp import YoutubeDL
from threading import Thread
import random
import asyncio

import config
import helpers
from selection import SelectionPanel


class Player:
    songs_queue = {}
    curr_inter = {}
    skip_flag = {}
    repeat_flag = {}
    logger = None
    embedder = None

    def __init__(self, logger, embedder):
        self.logger = logger
        self.embedder = embedder

    def add_from_playlist(self, inter, url):
        with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
            info = ytdl.extract_info(url, download=False)
        for i in range(1, info['playlist_count']):
            info['entries'][i]['original_message'] = None
            self.songs_queue[inter.guild.id].append(info['entries'][i])
        if not inter.guild.voice_client or not inter.guild.voice_client.is_connected():
            self.songs_queue[inter.guild.id].clear()

    async def custom_play(self, inter, url):
        if "list" in url:
            new_url = url[:url.find("list")-1]
        else:
            new_url = url
        with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
            info = ytdl.extract_info(new_url, download=False)
        if inter.guild.id not in self.songs_queue:
            self.songs_queue[inter.guild.id] = []
        voice = inter.guild.voice_client
        await voice.move_to(inter.author.voice.channel)
        self.songs_queue[inter.guild.id].append(info)
        if voice.is_playing():
            embed = self.embedder.songs(
                inter, info, "Song was added to queue!")
            info['original_message'] = await inter.channel.send("", embed=embed)
        else:
            info['original_message'] = None
        self.logger.added(inter, info)

        if inter.guild.id not in self.skip_flag:
            self.skip_flag[inter.guild.id] = False

        if inter.guild.id not in self.repeat_flag:
            self.repeat_flag[inter.guild.id] = False

        if not voice.is_playing():
            try:
                while True:
                    if len(self.songs_queue[inter.guild.id]) == 0:
                        self.repeat_flag[inter.guild.id] = False
                        self.skip_flag[inter.guild.id] = False
                        await voice.disconnect()
                        await self.curr_inter[inter.guild.id].channel.send("Finished playing music!")
                        break
                    current_track = self.songs_queue[inter.guild.id][0]
                    self.songs_queue[inter.guild.id].pop(0)
                    link = current_track.get("url", None)
                    voice.play(disnake.FFmpegPCMAudio(
                        source=link, **config.FFMPEG_OPTIONS))
                    embed = self.embedder.songs(
                        inter, current_track, "Playing this song!")
                    if current_track['original_message']:
                        await current_track['original_message'].delete()
                    await self.curr_inter[inter.guild.id].channel.send("", embed=embed)
                    self.logger.playing(inter, current_track)
                    if new_url != url:
                        tmp_message = await inter.channel.send("Processing playlist, further tracks can be not accessable yet :c")
                        thread = Thread(target=self.add_from_playlist,
                                        args=(inter, url))
                        thread.start()
                        await tmp_message.delete()
                        new_url = url
                    while ((voice.is_playing() or voice.is_paused()) and not self.skip_flag[inter.guild.id]):
                        await asyncio.sleep(1)

                    if self.skip_flag[inter.guild.id]:
                        voice.stop()
                        self.skip_flag[inter.guild.id] = False

                    elif self.repeat_flag[inter.guild.id]:
                        self.songs_queue[inter.guild.id].insert(
                            0, current_track)

                    if len(self.songs_queue[inter.guild.id]) == 0 and not inter.guild.voice_client:
                        break
            except Exception as err:
                self.logger.error(err, inter.guild)
                pass

        elif new_url != url:
            tmp_message = await inter.channel.send("Processing playlist, please, don't use any commands!")
            self.add_from_playlist(inter, url)
            await tmp_message.delete()

    async def play(self, inter, query):
        await inter.response.defer()
        self.curr_inter[inter.guild.id] = inter

        voice = inter.guild.voice_client

        try:
            user_channel = inter.author.voice.channel
            if not user_channel:
                return await inter.send("You're not connected to a voice channel!")
        except:
            return await inter.send("You're not connected to a voice channel!")

        if not voice:
            voice = await user_channel.connect()

        elif voice.channel and user_channel != voice.channel and len(voice.channel.members) > 1:
            if not helpers.is_admin(inter.author):
                return await inter.send("I'm already playing in another channel D:")

            else:
                await inter.channel.send("Yes, my master..")
                self.repeat_flag[inter.guild.id] = False

                voice.stop()
                self.songs_queue[inter.guild.id].clear()
                await voice.move_to(user_channel)

        elif voice.channel != user_channel:
            self.repeat_flag[inter.guild.id] = False
            self.songs_queue[inter.guild.id].clear()

            voice.stop()
            await voice.move_to(user_channel)

        if not voice:
            return await inter.send('Seems like your channel is unavailable :c')

        if not "https://" in query:
            songs = YoutubeSearch(query, max_results=5).to_dict()
            view = disnake.ui.View(timeout=30)
            select = SelectionPanel(songs, self.custom_play, inter.author)
            view.add_item(select)
            message = await inter.edit_original_response(view=view)
            try:
                for i in range(30):
                    if not inter.guild.voice_client:
                        return await message.delete()
                    await asyncio.sleep(1)

                await message.delete()
                await voice.disconnect()
                message = await inter.channel.send(f"{inter.author.mention} You're out of time! Next time think faster!")
                await asyncio.sleep(5)
                await message.delete()
            except:
                pass

        else:
            await inter.delete_original_response()
            await self.custom_play(inter, query)

    async def stop(self, inter):
        voice = inter.guild.voice_client
        try:
            if not voice:
                return await inter.send("I am not playing anything!")

            if (not inter.author.voice or inter.author.voice.channel != voice.channel) and len(voice.channel.members) > 1:
                return await inter.send("You are not in my channel!")

            if inter.guild.id in self.songs_queue:
                self.songs_queue[inter.guild.id].clear()
            self.repeat_flag[inter.guild.id] = False
            self.skip_flag[inter.guild.id] = False

            self.logger.finished(inter)
            voice.stop()
            await voice.disconnect()
            await inter.send("DJ decided to stop!")

        except Exception as err:
            print('error')
            self.logger.error(err, inter.guild)
            await inter.send("I am not playing anything!")

    async def pause(self, inter):
        voice = inter.guild.voice_client
        try:
            if not inter.author.voice or inter.author.voice.channel != voice.channel:
                return await inter.send("You are not in my channel!")
            if voice.is_paused():
                voice.resume()
                await inter.send("Player resumed!")

            else:
                voice.pause()
                await inter.send("Player paused!")

        except Exception as err:
            self.logger.error(err, inter.guild)
            await inter.send("I am not playing anything!")

    async def repeat(self, inter):
        voice = inter.guild.voice_client
        if not voice:
            return await inter.send("I am not playing anything!")
        if not inter.author.voice.channel or inter.author.voice.channel != voice.channel:
            return await inter.send("You are not in my channel!")
        if self.repeat_flag[inter.guild.id]:
            self.repeat_flag[inter.guild.id] = False
            await inter.send("Repeat mode is off!")
        else:
            self.repeat_flag[inter.guild.id] = True
            await inter.send("Repeat mode is on!")

    async def skip(self, inter):
        voice = inter.guild.voice_client
        try:
            if (not inter.author.voice.channel or inter.author.voice.channel != voice.channel) and len(voice.channel.members) > 1:
                return await inter.send("You are not in my channel!")
            if len(self.songs_queue[inter.guild.id]) >= 0:
                self.skip_flag[inter.guild.id] = True
                self.logger.skip(inter)
                await inter.send("Skipped current track!")
            else:
                await inter.send("I am not playing anything!")
        except Exception as err:
            self.logger.error(err, inter.guild)
            await inter.send("I am not playing anything!")

    async def queue(self, inter):
        try:
            if len(self.songs_queue[inter.guild.id]) > 0:
                cnt = 1
                ans = "```Queue:"
                for track in self.songs_queue[inter.guild.id][:15]:
                    if "live_status" in track and track['live_status'] == "is_live":
                        duration = "Live"
                    else:
                        duration = helpers.get_duration(track['duration'])
                    ans += f"\n{cnt}) {track['title']}, duration: {duration}"
                    cnt += 1
                ans += "```"
                await inter.send(ans)
            else:
                await inter.send("There are no songs in the queue!")
        except Exception as err:
            self.logger.error(err, inter.guild)
            await inter.send("I am not playing anything!")

    async def wrong(self, inter):
        voice = inter.guild.voice_client
        try:
            if (not inter.author.voice.channel or inter.author.voice.channel != voice.channel) and len(voice.channel.members) > 1:
                return await inter.send("You are not in my channel!")
            if len(self.songs_queue[inter.guild.id]) > 0:
                title = self.songs_queue[inter.guild.id][-1]['title']
                self.songs_queue[inter.guild.id].pop(-1)
                await inter.send(f"Removed {title} from queue!")
        except Exception as err:
            self.logger.error(err, inter.guild)
            await inter.send("I am not playing anything!")

    async def shuffle(self, inter):
        voice = inter.guild.voice_client
        try:
            if (not inter.author.voice.channel or inter.author.voice.channel != voice.channel) and len(voice.channel.members) > 1:
                return await inter.send("You are not in my channel!")
            if len(self.songs_queue[inter.guild.id]) > 1:
                random.shuffle(self.songs_queue[inter.guild.id])
                await inter.send("Shuffle completed successfully!")
            elif len(self.songs_queue[inter.guild.id]) == 1:
                await inter.send("There are no tracks to shuffle!")
            else:
                await inter.send("I am not playing anything!")
        except Exception as err:
            await inter.send("I am not playing anything!")

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
