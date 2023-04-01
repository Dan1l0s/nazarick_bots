import disnake
from disnake.ext import commands

import config
import helpers

bot = commands.InteractionBot(intents=disnake.Intents.all(
), activity=disnake.Activity(name="/radio", type=disnake.ActivityType.listening))


@bot.event
async def on_ready():
    print(f"Bot is logged as {bot.user}")
    # log.enabled(bot)


@bot.slash_command(description="Plays songs from anison.fm")
async def radio(inter):
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
        if not helpers.is_admin(inter):
            return await inter.send("I'm already playing in another channel D:")

        else:
            await inter.channel.send("Yes, my master..")
            await voice.move_to(user_channel)

    elif voice.channel != user_channel:
        await voice.move_to(user_channel)

    if not voice:
        return await inter.send('Seems like your channel is unavailable :c')

    await inter.send('Now playing ANISON.FM!')

    if not voice.is_playing():
        voice.play(disnake.FFmpegPCMAudio(
            source=config.radio_url, **config.FFMPEG_OPTIONS))
        await helpers.radio_message(inter, voice)


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
