import disnake
import asyncio

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers


class SelectionPanel(disnake.ui.View, disnake.ui.Select):
    def __init__(self, songs, func, inter, song, bot):
        self.author = inter.author
        self.song = song
        self.func = func
        self.inter = inter
        self.bot = bot
        self.done = False
        options = []
        for song in songs:
            title = song['title']
            suffix = song['url_suffix'][:song['url_suffix'].find("&")]
            sz = public_config.music_settings["SelectionPanelMaxNameLen"]
            if len(title) > sz:
                title = title[:sz] + "..."
            if song['duration'] == 0:
                song['duration'] = "Live"
            options.append(disnake.SelectOption(
                label=f"{title} : {song['duration']}", value=suffix))
        disnake.ui.View.__init__(
            self, timeout=public_config.music_settings["SelectionPanelTimeout"])
        disnake.ui.Select.__init__(self,
                                   placeholder="Choose your song!", options=options, custom_id="songs")
        self.add_item(self)

    async def send(self):
        _, self.message = await helpers.try_function(self.inter.text_channel.send, True, view=self)

    async def callback(self, inter):
        if inter.author == self.author or await helpers.is_admin(inter.author):
            await helpers.try_function(self.message.delete, True)
            await self.func(self.inter, self.song, f"https://www.youtube.com/{inter.values[0]}", respond=False)
            self.done = True
        else:
            await helpers.try_function(inter.author.send, True, f"Don't you even try to use someone's selection panel once again. {public_config.emojis['dead']}")

    async def on_timeout(self):
        if self.done:
            return
        try:
            await helpers.try_function(self.message.delete, True)
            voice = self.bot.states[self.inter.guild.id].voice
            self.done = True
            self.song.track_info.set_result(None)
            _, self.message = await helpers.try_function(self.inter.text_channel.send, True, f"{self.inter.author.mention} You're out of time! Next time think faster!")
            if not (voice.is_playing() or voice.is_paused()):
                await self.bot.abort_play(self.inter.guild.id, message="")
            await asyncio.sleep(5)
            await helpers.try_function(self.message.delete, True)
        except Exception as err:
            print(f"Caught exception in select: {err}")
            pass
