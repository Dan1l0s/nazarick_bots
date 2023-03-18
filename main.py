import disnake
import asyncio
import config
import helpers
import math
from yt_dlp import YoutubeDL
from disnake.ext import commands

songs_queue = {}
curr_ctx = {}
vcs = {}

skip_flag = {}
repeat_flag = {}
playing_flag = {}

bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(
), activity=disnake.Game(name="/help"))


@bot.event
async def on_ready():
    print("Bot is on")


@bot.event
async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
    if member.nick:
        member_nick = member.nick
    else:
        member_nick = member.name
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
        return await ctx.response.send_message("Unauthorized access, you are not admin!")

    await ctx.response.send_message("Processing...")
    guild = ctx.guild

    for channel in guild.voice_channels:
        await channel.edit(bitrate=384000)

    await ctx.edit_original_response("Done!")
    await asyncio.sleep(5)
    await ctx.delete_original_response()


@bot.slash_command(description="Plays a song from youtube (paste URL or type a query)", aliases="p")
async def play(ctx, url: str):

    curr_ctx[ctx.guild.id] = ctx

    voice = disnake.utils.get(bot.voice_clients, guild=ctx.guild)
    channel = ctx.author.voice.channel
    if not channel:
        return await ctx.response.send_message("You're not connected to a voice channel!")

    if not voice:
        voice = await channel.connect()
    elif vcs[voice.guild.id].channel and channel != vcs[voice.guild.id].channel and len(vcs[voice.guild.id].channel.members) > 1:
        if not helpers.is_admin(ctx):
            return await ctx.response.send_message("I'm already playing in another channel D:")
        else:
            await ctx.channel.send("Yes, my master..")
            playing_flag[ctx.guild.id] = False
            repeat_flag[ctx.guild.id] = False

            vcs[ctx.guild.id].stop()
            songs_queue[ctx.guild.id].clear()
            await voice.move_to(channel)
    elif vcs[voice.guild.id].channel != channel:
        repeat_flag[ctx.guild.id] = False
        playing_flag[ctx.guild.id] = False
        songs_queue[ctx.guild.id].clear()

        vcs[ctx.guild.id].stop()
        await voice.move_to(channel)

    if not voice:
        return await ctx.response.send_message('Seems like your channel is unavailable :c')

    await ctx.response.send_message('Adding to queue...')

    vcs[ctx.guild.id] = voice

    with YoutubeDL(config.YTDL_OPTIONS) as ytdl:
        if "https://" in url:
            info = ytdl.extract_info(url, download=False)
            print(info)
        else:
            info = ytdl.extract_info(f"ytsearch:{url}", download=False)[
                'entries'][0]

    if ctx.guild.id not in songs_queue:
        songs_queue[ctx.guild.id] = []
    songs_queue[ctx.guild.id].append(info)
    await ctx.edit_original_response(f"{info['title']} was added to queue!")

    if ctx.guild.id not in skip_flag:
        skip_flag[ctx.guild.id] = False

    if ctx.guild.id not in repeat_flag:
        repeat_flag[ctx.guild.id] = False

    if ctx.guild.id not in playing_flag:
        playing_flag[ctx.guild.id] = False

    if not playing_flag[ctx.guild.id]:
        try:
            playing_flag[ctx.guild.id] = True
            while playing_flag[ctx.guild.id]:
                if len(songs_queue[ctx.guild.id]) == 0:
                    repeat_flag[ctx.guild.id] = False
                    playing_flag[ctx.guild.id] = False
                    skip_flag[ctx.guild.id] = False
                    await vcs[ctx.guild.id].disconnect()
                    await curr_ctx[ctx.guild.id].channel.send_message("Finished playing music!")
                    break

                link = songs_queue[ctx.guild.id][0].get("url", None)
                title = songs_queue[ctx.guild.id][0]['title']

                vcs[ctx.guild.id].play(disnake.FFmpegPCMAudio(
                    executable="E:\\Study\\discord\\bot_script\\ffmpeg\\ffmpeg.exe", source=link, **config.FFMPEG_OPTIONS))
                await curr_ctx[ctx.guild.id].channel.send(f"Now playing: {title}")

                while ((voice.is_playing() or voice.is_paused()) and not skip_flag[ctx.guild.id]):
                    await asyncio.sleep(1)

                if skip_flag[ctx.guild.id]:
                    vcs[ctx.guild.id].stop()
                    skip_flag[ctx.guild.id] = False

                if repeat_flag[ctx.guild.id]:
                    songs_queue[ctx.guild.id].insert(
                        0, songs_queue[ctx.guild.id][0])
                songs_queue[ctx.guild.id].pop(0)
        except Exception as e:
            pass


@ bot.slash_command(description="Pauses/resumes player")
async def pause(ctx: disnake.AppCmdInter):
    try:
        if vcs[ctx.guild.id].is_paused():
            vcs[ctx.guild.id].resume()
            await ctx.send("Player resumed!")

        else:
            vcs[ctx.guild.id].pause()
            await ctx.send("Player paused!")

    except Exception as err:
        await ctx.send("I am not playing anything!")


@ bot.slash_command(description="Repeats current song")
async def repeat(ctx: disnake.AppCmdInter):
    if not playing_flag[ctx.guild.id]:
        await ctx.send("I am not playing anything!")
        return
    if repeat_flag[ctx.guild.id]:
        repeat_flag[ctx.guild.id] = False
        await ctx.send("Repeat mode is off!")
    else:
        repeat_flag[ctx.guild.id] = True
        await ctx.send("Repeat mode is on!")


@ bot.slash_command(description="Clears queue and disconnects bot")
async def stop(ctx: disnake.AppCmdInter):
    try:
        songs_queue[ctx.guild.id].clear()

        repeat_flag[ctx.guild.id] = False
        playing_flag[ctx.guild.id] = False
        skip_flag[ctx.guild.id] = False

        vcs[ctx.guild.id].stop()
        await vcs[ctx.guild.id].disconnect()
        await ctx.send("DJ decided to stop!")

    except Exception as err:
        await ctx.send("I am not playing anything!")


@ bot.slash_command(description="Skips current song")
async def skip(ctx: disnake.AppCmdInter):

    try:
        if len(songs_queue[ctx.guild.id]) > 0:
            skip_flag[ctx.guild.id] = True
            await ctx.send("Skipped current track!")
        else:
            await ctx.send("I am not playing anything!")
    except Exception as err:
        await ctx.send("I am not playing anything!")


@ bot.slash_command(description="Shows current queue")
async def queue(ctx):
    try:
        if len(songs_queue[ctx.guild.id]) > 0:
            cnt = 1
            ans = "Queue:"
            for track in songs_queue[ctx.guild.id]:
                ans += f"\n{cnt}) {track['title']}, duration: {math.floor(track['duration']/60)}m{track['duration']- math.floor(track['duration']/60)*60}s"
                cnt += 1

            await ctx.response.send_message(ans)
        else:
            await ctx.response.send_message("I am not playing anything!")
    except Exception as err:
        await ctx.response.send_message("I am not playing anything!")


@ bot.slash_command(description="Reviews list of commands")
async def help(ctx: disnake.AppCmdInter):
    await ctx.send(embed=disnake.Embed(color=0, description="Type /play to order a song (use URL from YT or just type the song's name)\nType /stop to stop playback\nType /pause to pause or resume playback\nType /repeat to repeat current track\nType /queue to get current list of songs"))


bot.run(config.token)
