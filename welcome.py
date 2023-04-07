import disnake
from disnake.ext import commands
import random
import asyncio

import helpers
import config

bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(
), activity=disnake.Activity(name="for new members", type=disnake.ActivityType.watching))


@bot.event
async def on_ready():
    print(f"Bot is logged as {bot.user}")


@bot.event
async def on_member_join(member):
    log_channel = config.log_ids[member.guild.id]
    await log_channel.send(f"{member.mention}, приветствую в Великой Гробнице Назарик!")

bot.run(config.tokens["welcome"])
