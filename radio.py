import disnake
from disnake.ext import commands
from urllib.request import urlopen
import json
import re
import asyncio

from embedder import *
import config
import helpers

bot = commands.InteractionBot(intents=disnake.Intents.all(
), activity=disnake.Activity(name="/radio", type=disnake.ActivityType.listening))

embedder = embed()


@bot.event
async def on_message(message):
    if len(message.role_mentions) > 0 or len(message.mentions) > 0:
        client = message.guild.get_member(config.ids["radio"])
        for role in message.role_mentions:
            if role in client.roles:
                if helpers.is_admin(message.author):
                    if "ping" in message.content:
                        return await message.reply(f"Yes, my master. My ping is {round(bot.latency*1000)} ms")
                    else:
                        return await message.reply("At your service, my master.")
                else:
                    return await message.reply(f"How dare you tag me? Know your place, trash")
        if client in message.mentions:
            if helpers.is_admin(message.author):
                if "ping" in message.content:
                    return await message.reply(f"Yes, my master. My ping is {round(bot.latency*1000)} ms")
                else:
                    return await message.reply("At your service, my master.")
            else:
                return await message.reply(f"How dare you tag me? Know your place, trash")


@bot.event
async def on_ready():
    print(f"Bot is logged as {bot.user}")
    # log.enabled(bot)


@bot.slash_command(description="Plays songs from anison.fm")
async def radio(inter):
    await inter.response.defer()
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
            await voice.move_to(user_channel)

    elif voice.channel != user_channel:
        await voice.move_to(user_channel)

    if not voice:
        return await inter.send('Seems like your channel is unavailable :c')

    await inter.delete_original_response()

    if not voice.is_playing():
        voice.play(disnake.FFmpegPCMAudio(
            source=config.radio_url, **config.FFMPEG_OPTIONS))
        await radio_message(inter, voice)


async def radio_message(inter, voice):
    url = "http://anison.fm/status.php?widget=true"
    name = ""
    while voice.is_playing():
        response = urlopen(url)
        data_json = json.loads(response.read())
        duration = data_json["duration"] - 14
        new_name = re.search("151; (.+?)</span>", data_json['on_air']).group(1)
        if new_name == name:
            await asyncio.sleep(duration - 1)
            continue
        name = new_name
        anime = re.search("blank'>(.+?)</a>", data_json['on_air']).group(1)
        await inter.channel.send("", embed=embedder.radio(name, anime, duration))
        await asyncio.sleep(duration - 1)


@bot.slash_command(description="Stops current playback")
async def stop(inter: disnake.AppCmdInter):
    voice = inter.guild.voice_client
    try:
        if not voice:
            return await inter.send("I am not playing anything!")
        voice.stop()
        # log.finished(inter)
        await voice.disconnect()
        await inter.send("DJ decided to stop!")

    except Exception as err:
        # log.error(err, inter.guild)
        await inter.send("I am not playing anything!")

bot.run(config.radio_token)
