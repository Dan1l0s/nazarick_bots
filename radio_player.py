import disnake
import asyncio
from urllib.request import urlopen
import json
import re

import config
import helpers


class RadioPlayer:
    logger = None
    embedder = None

    def __init__(self, logger, embedder):
        self.logger = logger
        self.embedder = embedder

    async def radio(self, inter):
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
            await self.radio_message(inter, voice)

    async def stop(self, inter):
        voice = inter.guild.voice_client
        try:
            if not voice:
                return await inter.send("I am not playing anything!")
            if (not inter.author.voice.channel or inter.author.voice.channel != voice.channel) and len(voice.channel.members) > 1:
                return await inter.send("You are not in my channel!")
            voice.stop()
            self.logger.finished(inter)
            await voice.disconnect()
            await inter.send("DJ decided to stop!")

        except Exception as err:
            self.logger.error(err, inter.guild)
            await inter.send("I am not playing anything!")

    async def radio_message(self, inter, voice):
        url = config.radio_widget
        name = ""
        while voice.is_playing():
            response = urlopen(url)
            data = json.loads(response.read())
            data["duration"] -= 14
            data["name"] = re.search(
                "151; (.+?)</span>", data['on_air']).group(1)
            if data["name"] == name:
                await asyncio.sleep(1)
                continue
            name = data["name"]
            data["source"] = re.search(
                "blank'>(.+?)</a>", data['on_air']).group(1)
            await inter.channel.send("", embed=self.embedder.radio(data))
            self.logger.radio(inter, data)
            await asyncio.sleep(1)
