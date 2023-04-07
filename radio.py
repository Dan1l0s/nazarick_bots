import disnake
from disnake.ext import commands

from embedder import Embed
import config
from logger import Logger
from radio_player import RadioPlayer
import helpers

bot = commands.InteractionBot(intents=disnake.Intents.all(
), activity=disnake.Activity(name="/radio", type=disnake.ActivityType.listening))
logger = Logger(True)
embedder = Embed()
player = RadioPlayer(logger, embedder)


@bot.event
async def on_message(message):
    if len(message.role_mentions) > 0 or len(message.mentions) > 0:
        client = message.guild.get_member(config.ids["radio"])
        if helpers.is_mentioned(client, message):
            if helpers.is_admin(message.author):
                if "ping" in message.content or "пинг" in message.content:
                    return await message.reply(f"Yes, my master. My ping is {round(bot.latency*1000)} ms")
                else:
                    return await message.reply("At your service, my master.")
            else:
                await message.author.timeout(10, reason="Ping by lower life form")
                return await message.reply(f"How dare you tag me? Know your place, trash")


@bot.event
async def on_ready():
    print(f"RadioBot is logged as {bot.user}")
    logger.enabled(bot)


@bot.slash_command(description="Plays songs from Anison.FM")
async def radio(inter):
    await player.radio(inter)


@bot.slash_command(description="Stops current playback")
async def stop(inter):
    await player.stop(inter)

bot.run(config.tokens["radio"])
