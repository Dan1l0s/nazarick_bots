import disnake
from disnake.ext import commands
import asyncio

from logger import Logger
from embedder import Embed
from player import Player
import helpers
import config

bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(
), activity=disnake.Activity(name="/play", type=disnake.ActivityType.listening))

logger = Logger(True)
embedder = Embed()
player = Player(logger, embedder)


@bot.event
async def on_message(message):
    if len(message.role_mentions) > 0 or len(message.mentions) > 0:
        client = message.guild.get_member(config.ids["music_reserve"])
        if helpers.is_mentioned(client, message):
            if helpers.is_admin(message.author):
                if "ping" in message.content.lower() or "пинг" in message.content.lower():
                    return await message.reply(f"Yes, my master. My ping is {round(bot.latency*1000)} ms")
                else:
                    return await message.reply("At your service, my master.")
            else:
                await message.author.timeout(duration=10, reason="Ping by lower life form")
                return await message.reply(f"How dare you tag me? Know your place, trash")


@bot.event
async def on_ready():
    print(f"MusicReserveBot is logged as {bot.user}")
    logger.enabled(bot)


@bot.event
async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
    voice = member.guild.voice_client
    if voice and before.channel and before.channel != after.channel:
        if len(voice.channel.members) == 1:
            await player.timeout(member.guild.id)


@bot.slash_command(description="Plays a song from youtube (paste URL or type a query)", aliases="p")
async def play(inter, query: str = commands.Param(description='Type a query or paste youtube URL')):
    await player.play(inter, query)


@ bot.slash_command(description="Pauses/resumes player")
async def pause(inter: disnake.AppCmdInter):
    await player.pause(inter)


@ bot.slash_command(description="Repeats current song")
async def repeat(inter: disnake.AppCmdInter):
    await player.repeat(inter)


@ bot.slash_command(description="Clears queue and disconnects bot")
async def stop(inter: disnake.AppCmdInter):
    await player.stop(inter)


@ bot.slash_command(description="Skips current song")
async def skip(inter: disnake.AppCmdInter):
    await player.skip(inter)


@ bot.slash_command(description="Shows current queue")
async def queue(inter):
    await player.queue(inter)


@ bot.slash_command(description="Removes last added song from queue")
async def wrong(inter: disnake.AppCmdInter):
    await player.wrong(inter)


@bot.slash_command(description="Shuffles current queue")
async def shuffle(inter: disnake.AppCmdInter):
    await player.shuffle(inter)


@ bot.slash_command(description="Reviews list of commands")
async def help(inter: disnake.AppCmdInter):
    ans = player.help()
    await inter.send(embed=disnake.Embed(color=0, description=ans))


bot.run(config.tokens["music_reserve"])
