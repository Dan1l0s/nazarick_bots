import disnake
import config
from yt_dlp import YoutubeDL
from disnake.ext import commands


YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': 'True',
                'simulate': 'True', 'key': 'FFmpegExtractAudio'}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

vcs = {}
bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all())


@bot.remove_command('help')
@bot.command()
async def help(ctx):
    ctx.send("Тебе уже ничего не поможет")


@bot.event
async def on_ready():
    print("Bot is turned on")


@bot.slash_command(description="Test slash-command")
async def test(interaction: disnake.AppCmdInter, num: int):
    await interaction.send(f"test {num}")


@bot.slash_command(description="Plays a song from youtube (paste URL or type a query)")
async def play(ctx: disnake.AppCmdInter, url: str):
    print(url)
    if ctx.author.voice:
        try:
            vc = await ctx.author.voice.channel.connect()
            vcs[vc.guild.id] = vc
        except:
            print("error")
        with YoutubeDL(YTDL_OPTIONS) as ytdl:
            if "https://" in url:
                info = ytdl.extract_info(url, download=False)
            else:
                info = ytdl.extract_info(f"ytsearch:{url}", download=False)[
                    'entries'][0]
        link = info.get("url", None)
        title = info['title']

        vcs[ctx.guild.id].play(disnake.FFmpegPCMAudio(
            executable="E:\\Study\\discord\\bot_script\\ffmpeg\\ffmpeg.exe", source=link, **FFMPEG_OPTIONS))
        await ctx.send(f"Playing {title}")
        # ctx.send(embed=disnake.Embed(f"Add to queue: "))
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
        vcs[ctx.guild.id].stop()
        await vcs[ctx.guild.id].disconnect()
        await ctx.send("DJ decided to stop!")
    except Exception as err:
        await ctx.send("I am not playing anything!")


@bot.command()
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"Deleted {amount} messages")


@bot.command()
async def play(ctx, url: str):
    print(url)
    if ctx.message.author.voice:
        try:
            vc = await ctx.author.voice.channel.connect()
            vcs[vc.guild.id] = vc
        except:
            print("error")
        with YoutubeDL(YTDL_OPTIONS) as ytdl:
            if "https://" in url:
                info = ytdl.extract_info(url, download=False)
            else:
                info = ytdl.extract_info(f"ytsearch:{url}", download=False)[
                    'entries'][0]
        link = info.get("url", None)
        title = info['title']

        vcs[ctx.guild.id].play(disnake.FFmpegPCMAudio(
            executable="E:\\Study\\discord\\bot_script\\ffmpeg\\ffmpeg.exe", source=link, **FFMPEG_OPTIONS))
        await ctx.send(f"Playing {title}")
        # ctx.send(embed=disnake.Embed(f"Add to queue: "))
    else:
        await ctx.send(f"Please, connect a voice channel")


@bot.command()
async def pause(ctx):
    try:
        vcs[ctx.guild.id].pause()
        await ctx.send("Player paused!")
    except Exception as err:
        await ctx.send("I am not playing anything!")


@bot.command()
async def resume(ctx):
    try:
        vcs[ctx.guild.id].resume()
        await ctx.send("Player resumed!")
    except Exception as err:
        await ctx.send("There's nothing to play!")


@bot.command()
async def stop(ctx):
    try:
        vcs[ctx.guild.id].stop()
        await vcs[ctx.guild.id].disconnect()
        await ctx.send("DJ decided to stop!")
    except Exception as err:
        await ctx.send("I am not playing anything!")

bot.run(config.token)
