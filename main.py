import disnake
import asyncio
from yt_dlp import YoutubeDL
from disnake.ext import commands

import config
import helpers
from logger import *

# 1.1.1 - Testing methods from logger.py

songs_queue = {}
curr_ctx = {}

skip_flag = {}
repeat_flag = {}

bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(
), activity=disnake.Game(name="/help"))

log = logger(songs_queue)

@bot.event
async def on_ready():
    log.enabled()  #Added 'Bot is On' to logs.txt 

@bot.event
async def on_audit_log_entry_create(entry):
    log.logged(entry)    #Added audit_logs to logs.txt


@bot.event
async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
    member_nick = helpers.get_nickname(member)
    possible_channel_name = f"{member_nick}'s private"

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
async def bitrate(ctx):
    if not helpers.is_admin(ctx):
        return await ctx.send("Unauthorized access, you are not admin!")
    await ctx.send("Processing...")

    for channel in ctx.guild.voice_channels:
        await channel.edit(bitrate=384000)

    await ctx.edit_original_response("Done!")
    await asyncio.sleep(5)
    await ctx.delete_original_response()


@bot.slash_command(description="Plays a song from youtube (paste URL or type a query)", aliases="p")
async def play(ctx, url: str = commands.Param(description='Type a query or paste youtube URL')):

    curr_ctx[ctx.guild.id] = ctx

    voice = ctx.guild.voice_client

    try:
        user_channel = ctx.author.voice.channel
        if not user_channel:
            return await ctx.send("You're not connected to a voice channel!")
    except:
        return await ctx.send("You're not connected to a voice channel!")

    if not voice:
        voice = await user_channel.connect()

    elif voice.channel and user_channel != voice.channel and len(voice.channel.members) > 1:
        if not helpers.is_admin(ctx):
            return await ctx.send("I'm already playing in another channel D:")

        else:
            await ctx.channel.send("Yes, my master..")
            repeat_flag[ctx.guild.id] = False

            voice.stop()
            songs_queue[ctx.guild.id].clear()
            await voice.move_to(user_channel)

    elif voice.channel != user_channel:
        repeat_flag[ctx.guild.id] = False
        songs_queue[ctx.guild.id].clear()

        voice.stop()
        await voice.move_to(user_channel)

    if not voice:
        return await ctx.send('Seems like your channel is unavailable :c')

    await ctx.send('Searching...')

    voice = voice

    with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
        if "https://" in url:
            info = ytdl.extract_info(url, download=False)
        else:
            info = ytdl.extract_info(f"ytsearch:{url}", download=False)[
                'entries'][0]

    if ctx.guild.id not in songs_queue:
        songs_queue[ctx.guild.id] = []

    embed = helpers.song_embed_builder(ctx, info, "Song was added to queue!")

    info['original_message'] = await ctx.edit_original_response("", embed=embed)

    songs_queue[ctx.guild.id].append(info)

    log.added(info, ctx)    #Added songs to logs.txt

    if ctx.guild.id not in skip_flag:
        skip_flag[ctx.guild.id] = False

    if ctx.guild.id not in repeat_flag:
        repeat_flag[ctx.guild.id] = False

    if not voice.is_playing():
        try:
            while True:
                if len(songs_queue[ctx.guild.id]) == 0:
                    repeat_flag[ctx.guild.id] = False
                    skip_flag[ctx.guild.id] = False
                    await voice.disconnect()
                    await curr_ctx[ctx.guild.id].channel.send("Finished playing music!")
                    break

                link = songs_queue[ctx.guild.id][0].get("url", None)

                voice.play(disnake.FFmpegPCMAudio(
                    source=link, **config.FFMPEG_OPTIONS))
                embed = helpers.song_embed_builder(
                    ctx, songs_queue[ctx.guild.id][0], "Playing this song!")
                await songs_queue[ctx.guild.id][0]['original_message'].delete()
                await curr_ctx[ctx.guild.id].channel.send("", embed=embed)
                log.playing(ctx)    #Added playing songs to logs.txt
                while ((voice.is_playing() or voice.is_paused()) and not skip_flag[ctx.guild.id]):
                    await asyncio.sleep(1)

                if skip_flag[ctx.guild.id]:
                    voice.stop()
                    skip_flag[ctx.guild.id] = False

                if repeat_flag[ctx.guild.id]:
                    songs_queue[ctx.guild.id].insert(
                        0, songs_queue[ctx.guild.id][0])

                if len(songs_queue[ctx.guild.id]) > 0:
                    songs_queue[ctx.guild.id].pop(0)
                else:
                    break
        except Exception as e:
            print("ERROR:", e)
            pass


@ bot.slash_command(description="Pauses/resumes player")
async def pause(ctx: disnake.AppCmdInter):
    voice = ctx.guild.voice_client
    try:
        if voice.is_paused():
            voice.resume()
            await ctx.send("Player resumed!")

        else:
            voice.pause()
            await ctx.send("Player paused!")

    except Exception as err:
        log.error(err)    #Added error logs to logs.txt
        await ctx.send("I am not playing anything!")


@ bot.slash_command(description="Repeats current song")
async def repeat(ctx: disnake.AppCmdInter):
    voice = ctx.guild.voice_client
    if not voice.is_playing():
        return await ctx.send("I am not playing anything!")
    if repeat_flag[ctx.guild.id]:
        repeat_flag[ctx.guild.id] = False
        await ctx.send("Repeat mode is off!")
    else:
        repeat_flag[ctx.guild.id] = True
        await ctx.send("Repeat mode is on!")


@ bot.slash_command(description="Clears queue and disconnects bot")
async def stop(ctx: disnake.AppCmdInter):
    voice = ctx.guild.voice_client
    try:
        if not voice:
            return await ctx.send("I am not playing anything!")
        songs_queue[ctx.guild.id].clear()

        repeat_flag[ctx.guild.id] = False
        skip_flag[ctx.guild.id] = False

        voice.stop()
        log.finished(ctx)    #Added finished playing to logs.txt
        await voice.disconnect()
        await ctx.send("DJ decided to stop!")

    except Exception as err:
        log.error(err)
        await ctx.send("I am not playing anything!")


@ bot.slash_command(description="Skips current song")
async def skip(ctx: disnake.AppCmdInter):

    try:
        if len(songs_queue[ctx.guild.id]) > 0:
            skip_flag[ctx.guild.id] = True
            log.skip(ctx)   #Added skip to logs.txt
            await ctx.send("Skipped current track!")
        else:
            await ctx.send("I am not playing anything!")
    except Exception as err:
        log.error(err)
        await ctx.send("I am not playing anything!")


@ bot.slash_command(description="Shows current queue")
async def queue(ctx):
    try:
        if len(songs_queue[ctx.guild.id]) > 0:
            cnt = 1
            ans = "```Queue:\n"
            for track in songs_queue[ctx.guild.id]:
                ans += f"\n{cnt}) {track['title']}, duration: {track['duration'] // 3600}h{track['duration']//60 - (track['duration'] // 3600) * 60}m{track['duration']- (track['duration']//60)*60}s"
                cnt += 1
            ans += "\n```"
            await ctx.send(ans)
        else:
            await ctx.send("I am not playing anything!")
    except Exception as err:
        log.error(err)
        await ctx.send("I am not playing anything!")


@ bot.slash_command(description="Removes last added song from queue")
async def wrong(ctx: disnake.AppCmdInter):
    try:
        if len(songs_queue[ctx.guild.id]) > 1:
            title = songs_queue[ctx.guild.id][-1]['title']
            songs_queue[ctx.guild.id].pop(-1)
            await ctx.send(f"Removed {title} from queue!")
    except Exception as err:
        log.error(err)
        await ctx.send("I am not playing anything!")

@ bot.slash_command(description="Reviews list of commands")
async def help(ctx: disnake.AppCmdInter):
    await ctx.send(embed=disnake.Embed(color=0, description="Type /play to order a song (use URL from YT or just type the song's name)\nType /stop to stop playback\nType /pause to pause or resume playback\nType /repeat to repeat current track\nType /queue to get current list of songs"))


bot.run(config.token)
