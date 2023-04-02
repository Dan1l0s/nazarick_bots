import disnake
from disnake.ext import commands
from youtube_search import YoutubeSearch
from yt_dlp import YoutubeDL
from threading import Thread
import random
import asyncio

from selection import *
from logger import *
from embedder import *
import helpers
import config

songs_queue = {}
curr_inter = {}

skip_flag = {}
repeat_flag = {}

bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(
), activity=disnake.Activity(name="/play", type=disnake.ActivityType.listening))

log = logger(songs_queue, False)
embedder = embed()


@bot.event
async def on_message(message):
    if "discord.gg" in message.content.lower():
        try:
            await message.delete()
            await message.author.send(
                f"Do NOT try to invite anyone to another servers {config.emojis['banned']}")
        except:
            pass

    if len(message.role_mentions) > 0 or len(message.mentions) > 0:
        client = message.guild.get_member(config.ids["music"])
        if helpers.is_mentioned(client, message):
            if helpers.is_admin(message.author):
                if "ping" in message.content.lower() or "пинг" in message.content.lower():
                    return await message.reply(f"Yes, my master. My ping is {round(bot.latency*1000)} ms")
                else:
                    return await message.reply("At your service, my master.")
            else:
                return await message.reply(f"How dare you tag me? Know your place, trash")


@bot.event
async def on_ready():
    print(f"Bot is logged as {bot.user}")
    log.enabled(bot)


@bot.event
async def on_audit_log_entry_create(entry):
    log.logged(entry)
    # await entry.guild.get_channel(config.log_ids[entry.guild.id]).send(embed=embedder.action(entry))


@bot.event
async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
    member_nick = helpers.get_nickname(member)
    possible_channel_name = f"{member_nick}'s private"

    if before.channel and after.channel:
        if before.channel.id != after.channel.id:
            log.switched(member, before, after)
            # await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=embedder.switched(member, before, after))
        else:
            log.voice_update(member)
            # await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=embedder.voice_update(member))
    elif before.channel:
        log.disconnected(member, before)
        # await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=embedder.disconnected(member, before))
    else:
        log.connected(member, after)
        # await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=embedder.connected(member, after))

    if after.channel and after.channel.name == "Создать приват":
        guild = member.guild
        category = disnake.utils.get(
            guild.categories, id=config.categories_ids[guild.id])

        tmp_channel = await category.create_voice_channel(name=possible_channel_name)

        perms = tmp_channel.overwrites_for(guild.default_role)
        perms.view_channel = False
        await tmp_channel.set_permissions(guild.default_role, overwrite=perms)

        await member.move_to(tmp_channel)

        perms = tmp_channel.overwrites_for(member)
        perms.view_channel = True
        perms.manage_permissions = True
        perms.manage_channels = True
        await tmp_channel.set_permissions(member, overwrite=perms)

        await tmp_channel.edit(bitrate=384000)
    if before.channel:
        if "'s private" in before.channel.name:
            if len(before.channel.members) == 0:
                await before.channel.delete()


@bot.slash_command(description="Allows admin to fix voice channels' bitrate")
async def bitrate(inter):
    if not helpers.is_admin(inter.author):
        return await inter.send("Unauthorized access, you are not admin!")
    await inter.send("Processing...")

    for channel in inter.guild.voice_channels:
        await channel.edit(bitrate=384000)

    await inter.edit_original_response("Done!")
    await asyncio.sleep(5)
    await inter.delete_original_response()


def add_from_playlist(inter, url):
    with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
        info = ytdl.extract_info(url, download=False)
    for i in range(1, info['playlist_count']):
        info['entries'][i]['original_message'] = None
        songs_queue[inter.guild.id].append(info['entries'][i])
    if not inter.guild.voice_client or not inter.guild.voice_client.is_connected():
        songs_queue[inter.guild.id].clear()


async def custom_play(inter, url):
    if "list" in url:
        new_url = url[:url.find("list")-1]
    else:
        new_url = url
    with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
        info = ytdl.extract_info(new_url, download=False)
    if inter.guild.id not in songs_queue:
        songs_queue[inter.guild.id] = []
    voice = inter.guild.voice_client
    embed = embedder.songs(inter, info, "Song was added to queue!")
    info['original_message'] = await inter.channel.send("", embed=embed)
    songs_queue[inter.guild.id].append(info)
    log.added(inter)

    if inter.guild.id not in skip_flag:
        skip_flag[inter.guild.id] = False

    if inter.guild.id not in repeat_flag:
        repeat_flag[inter.guild.id] = False

    if not voice.is_playing():
        try:
            while True:
                if len(songs_queue[inter.guild.id]) == 0:
                    repeat_flag[inter.guild.id] = False
                    skip_flag[inter.guild.id] = False
                    await voice.disconnect()
                    await curr_inter[inter.guild.id].channel.send("Finished playing music!")
                    break
                current_track = songs_queue[inter.guild.id][0]
                songs_queue[inter.guild.id].pop(0)
                link = current_track.get("url", None)
                voice.play(disnake.FFmpegPCMAudio(
                    source=link, **config.FFMPEG_OPTIONS))
                embed = embedder.songs(
                    inter, current_track, "Playing this song!")
                if current_track['original_message']:
                    await current_track['original_message'].delete()
                await curr_inter[inter.guild.id].channel.send("", embed=embed)
                log.playing(inter)
                if new_url != url:
                    tmp_message = await inter.channel.send("Processing playlist, further tracks can be not accessable yet :c")
                    thread = Thread(target=add_from_playlist,
                                    args=(inter, url))
                    thread.start()
                    await tmp_message.delete()
                    new_url = url
                while ((voice.is_playing() or voice.is_paused()) and not skip_flag[inter.guild.id]):
                    await asyncio.sleep(1)

                if skip_flag[inter.guild.id]:
                    voice.stop()
                    skip_flag[inter.guild.id] = False

                elif repeat_flag[inter.guild.id]:
                    songs_queue[inter.guild.id].insert(
                        0, current_track)

                if len(songs_queue[inter.guild.id]) == 0:
                    break
        except Exception as err:
            log.error(err, inter.guild)
            pass

    elif new_url != url:
        tmp_message = await inter.channel.send("Processing playlist, please, don't use any commands!")
        add_from_playlist(inter, url)
        await tmp_message.delete()


@bot.slash_command(description="Plays a song from youtube (paste URL or type a query)", aliases="p")
async def play(inter, query: str = commands.Param(description='Type a query or paste youtube URL')):
    await inter.response.defer()
    curr_inter[inter.guild.id] = inter

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
            repeat_flag[inter.guild.id] = False

            voice.stop()
            songs_queue[inter.guild.id].clear()
            await voice.move_to(user_channel)

    elif voice.channel != user_channel:
        repeat_flag[inter.guild.id] = False
        songs_queue[inter.guild.id].clear()

        voice.stop()
        await voice.move_to(user_channel)

    if not voice:
        return await inter.send('Seems like your channel is unavailable :c')

    if not "https://" in query:
        songs = YoutubeSearch(query, max_results=5).to_dict()
        view = disnake.ui.View(timeout=30)
        select = SelectionPanel(songs, custom_play, inter.author)
        view.add_item(select)
        message = await inter.edit_original_response(view=view)
        try:
            for i in range(30):
                if not inter.guild.voice_client:
                    await message.delete()
                    break
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
        await custom_play(inter, query)


@ bot.slash_command(description="Pauses/resumes player")
async def pause(inter: disnake.AppCmdInter):
    voice = inter.guild.voice_client
    try:
        if voice.is_paused():
            voice.resume()
            await inter.send("Player resumed!")

        else:
            voice.pause()
            await inter.send("Player paused!")

    except Exception as err:
        log.error(err, inter.guild)
        await inter.send("I am not playing anything!")


@ bot.slash_command(description="Repeats current song")
async def repeat(inter: disnake.AppCmdInter):
    voice = inter.guild.voice_client
    if not voice.is_playing():
        return await inter.send("I am not playing anything!")
    if repeat_flag[inter.guild.id]:
        repeat_flag[inter.guild.id] = False
        await inter.send("Repeat mode is off!")
    else:
        repeat_flag[inter.guild.id] = True
        await inter.send("Repeat mode is on!")


@ bot.slash_command(description="Clears queue and disconnects bot")
async def stop(inter: disnake.AppCmdInter):
    voice = inter.guild.voice_client
    try:
        if not voice.channel:
            return await inter.send("I am not playing anything!")
        if inter.guild.id in songs_queue:
            songs_queue[inter.guild.id].clear()

        repeat_flag[inter.guild.id] = False
        skip_flag[inter.guild.id] = False

        voice.stop()
        await voice.disconnect()
        log.finished(inter)
        await inter.send("DJ decided to stop!")

    except Exception as err:
        log.error(err, inter.guild)
        await inter.send("I am not playing anything!")


@ bot.slash_command(description="Skips current song")
async def skip(inter: disnake.AppCmdInter):

    try:
        if len(songs_queue[inter.guild.id]) >= 0:
            skip_flag[inter.guild.id] = True
            log.skip(inter)
            await inter.send("Skipped current track!")
        else:
            await inter.send("I am not playing anything!")
    except Exception as err:
        log.error(err, inter.guild)
        await inter.send("I am not playing anything!")


@ bot.slash_command(description="Shows current queue")
async def queue(inter):
    try:
        if len(songs_queue[inter.guild.id]) > 0:
            cnt = 1
            ans = "```Queue:"
            for track in songs_queue[inter.guild.id][:15]:
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
        log.error(err, inter.guild)
        await inter.send("I am not playing anything!")


@ bot.slash_command(description="Removes last added song from queue")
async def wrong(inter: disnake.AppCmdInter):
    try:
        if len(songs_queue[inter.guild.id]) > 0:
            title = songs_queue[inter.guild.id][-1]['title']
            songs_queue[inter.guild.id].pop(-1)
            await inter.send(f"Removed {title} from queue!")
    except Exception as err:
        log.error(err, inter.guild)
        await inter.send("I am not playing anything!")


@bot.slash_command(description="Shuffles current queue")
async def shuffle(inter: disnake.AppCmdInter):
    try:
        if len(songs_queue[inter.guild.id]) > 1:
            random.shuffle(songs_queue[inter.guild.id])
            await inter.send("Shuffle completed successfully!")
        elif len(songs_queue[inter.guild.id]) == 1:
            await inter.send("There are no tracks to shuffle!")
        else:
            await inter.send("I am not playing anything!")
    except Exception as err:
        await inter.send("I am not playing anything!")


@ bot.slash_command(description="Reviews list of commands")
async def help(inter: disnake.AppCmdInter):
    await inter.send(embed=disnake.Embed(color=0, description="Type /play to order a song (use URL from YT or just type the song's name)\nType /stop to stop playback\nType /pause to pause or resume playback\nType /repeat to repeat current track\nType /queue to get current list of songs"))


@ bot.slash_command(description="Clears custom amount of messages")
async def clear(inter: disnake.AppCmdInter, amount: int):
    if helpers.is_admin(inter.author):
        await inter.channel.purge(limit=amount+1)
        await inter.send(f"Cleared {amount} messages")
        await asyncio.sleep(5)
        return await inter.delete_original_response()
    return await inter.send(f"Unathorized attempt to clear messages!")

bot.run(config.music_token)
