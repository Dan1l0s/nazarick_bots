import disnake
import asyncio
import config
from yt_dlp import YoutubeDL
from disnake.ext import commands


YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': 'True',
                'simulate': 'True', 'key': 'FFmpegExtractAudio'}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

queue = []  
skip_flag = False
playing_flag = False
vcs = {}
bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(), activity=disnake.Game(name="/help"))


@bot.event
async def on_ready():
    print("Bot is turned on")


@bot.remove_command('help')
@bot.command()
async def help(ctx):
    await ctx.send("Тебе уже ничего не поможет")


# @bot.slash_command(description="Test slash-command")
# async def test(interaction: disnake.AppCmdInter, num: int):
#     await interaction.send(f"test {num}")


@bot.slash_command(description="Plays a song from youtube (paste URL or type a query)")
async def play(ctx, url: str):
    global voice
    voice = disnake.utils.get(bot.voice_clients, guild = ctx.guild)
    channel = ctx.author.voice.channel
    if channel:
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()
            if not voice and not voice.is_connected():
                return await ctx.response.send_message('Seems like your channel is unavailable :c')
            
        queue.append(url)
        await ctx.send(f"Added to queue!")
        global playing_flag
        global skip_flag
        vcs[voice.guild.id] = voice

        if not playing_flag:
            try:
                playing_flag = True
                while True:
                    if len(queue) == 0:
                        playing_flag = False
                        skip_flag = False
                        vcs[ctx.guild.id].stop()
                        await vcs[ctx.guild.id].disconnect()
                        break
                    with YoutubeDL(YTDL_OPTIONS) as ytdl:
                        if "https://" in queue[0]:
                            info = ytdl.extract_info(queue[0], download=False)
                        else:
                            info = ytdl.extract_info(f"ytsearch:{queue[0]}", download=False)[
                                'entries'][0]
                    link = info.get("url", None)
                    title = info['title']

                    vcs[ctx.guild.id].play(disnake.FFmpegPCMAudio(executable="E:\\Study\\discord\\bot_script\\ffmpeg\\ffmpeg.exe", source=link, **FFMPEG_OPTIONS))
                    await ctx.send(f"Now playing: {title}")
                    while (voice.is_playing() or voice.is_paused()) and not skip_flag:
                        await asyncio.sleep(2)
                        
                    if (not voice.is_playing() and not voice.is_paused()) or skip_flag:
                        if (skip_flag):
                            vcs[ctx.guild.id].stop()
                            skip_flag = False
                        queue.pop(0)
            except:
                pass
    else:
        await ctx.send(f"Please, connect a voice channel")


@bot.slash_command(description="Pauses current song")
async def pause(ctx: disnake.AppCmdInter):
    try:
        vcs[ctx.guild.id].pause()
        await ctx.send("Player paused!")
    except Exception as err:
        await ctx.send("I am not playing anything!")


@bot.slash_command(description="Resumes current song")
async def resume(ctx: disnake.AppCmdInter):
    try:
        vcs[ctx.guild.id].resume()
        await ctx.send("Player resumed!")
    except Exception as err:
        await ctx.send("There's nothing to play!")


@bot.slash_command(description="Clears queue and disconnects bot")
async def stop(ctx: disnake.AppCmdInter):
    try:
        queue.clear()
        vcs[ctx.guild.id].stop()
        await vcs[ctx.guild.id].disconnect()
        await ctx.send("DJ decided to stop!")
    except Exception as err:
        await ctx.send("I am not playing anything!")

@bot.slash_command(description="Skips current song")
async def skip(ctx: disnake.AppCmdInter):
    global skip_flag
    if len(queue) > 0:
        skip_flag = True
        await ctx.send("Skipped current track!")
    else:
        await ctx.send("I am not playing anything!")


@bot.slash_command(description="Reviews list of commands")
async def help(ctx: disnake.AppCmdInter):
    await ctx.send(embed=disnake.Embed(description="Type /play to order a song (use URL from YT or just type the song's name)\nType /stop to stop playback\nType /pause to pause playback\nType /resume to resume playback"))


# @bot.command()
# async def clear(ctx, amount: int):
#     await ctx.channel.purge(limit=amount+1)
#     await ctx.send(f"Deleted {amount} messages")


@bot.command()
async def play(ctx, url: str):
    global voice
    voice = disnake.utils.get(bot.voice_clients, guild = ctx.guild)
    channel = ctx.author.voice.channel
    if channel:
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()
            if not voice and not voice.is_connected():
                return await ctx.response.send_message('Seems like your channel is unavailable :c')
            
        queue.append(url)
        await ctx.send(f"Added to queue!")
        global playing_flag
        global skip_flag
        vcs[voice.guild.id] = voice

        if not playing_flag:
            try:
                playing_flag = True
                while True:
                    if len(queue) == 0:
                        playing_flag = False
                        skip_flag = False
                        vcs[ctx.guild.id].stop()
                        await vcs[ctx.guild.id].disconnect()
                        break
                    with YoutubeDL(YTDL_OPTIONS) as ytdl:
                        if "https://" in queue[0]:
                            info = ytdl.extract_info(queue[0], download=False)
                        else:
                            info = ytdl.extract_info(f"ytsearch:{queue[0]}", download=False)[
                                'entries'][0]
                    link = info.get("url", None)
                    title = info['title']

                    vcs[ctx.guild.id].play(disnake.FFmpegPCMAudio(executable="E:\\Study\\discord\\bot_script\\ffmpeg\\ffmpeg.exe", source=link, **FFMPEG_OPTIONS))
                    await ctx.send(f"Now playing: {title}")
                    while (voice.is_playing() or voice.is_paused()) and not skip_flag:
                        await asyncio.sleep(2)
                        
                    if (not voice.is_playing() and not voice.is_paused()) or skip_flag:
                        if (skip_flag):
                            vcs[ctx.guild.id].stop()
                            skip_flag = False
                        queue.pop(0)
            except:
                pass
    else:
        await ctx.send(f"Please, connect a voice channel")


@bot.command()
async def pause(ctx):
    try:
        vcs[ctx.guild.id].pause()
        await ctx.send("Player paused!")
    except Exception as error:
        print(error)
        await ctx.send("I am not playing anything!")


@bot.command()
async def resume(ctx):
    try:
        vcs[ctx.guild.id].resume()
        await ctx.send("Player resumed!")
    except Exception as error:
        print(error)
        await ctx.send("There's nothing to play!")


@bot.command()
async def stop(ctx):
    try:
        queue.clear()
        vcs[ctx.guild.id].stop()
        await vcs[ctx.guild.id].disconnect()
        await ctx.send("DJ decided to stop!")
    except Exception as err:
        await ctx.send("I am not playing anything!")

@bot.command()
async def skip(ctx):
    global skip_flag
    if len(queue) > 0:
        skip_flag = True
        await ctx.send("Skipped current track!")
    else:
        await ctx.send("I am not playing anything!")

bot.run(config.token)
