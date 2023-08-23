import disnake
import asyncio

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers


class SelectionPanel(disnake.ui.View):
    songs_list = None

    def __init__(self, songs, func, inter, song, bot):
        self.author = inter.author
        self.song = song
        self.songs_list = []
        self.func = func
        self.inter = inter
        self.bot = bot
        self.value = False
        for song in songs:
            url = f"https://www.youtube.com/{song['url_suffix'][:song['url_suffix'].find('&')]}"
            self.songs_list.append(url)

        super().__init__(timeout=public_config.music_settings["SelectionPanelTimeout"])

    async def button_callback(self, button_num, inter):
        if inter.author == self.author or await helpers.is_admin(inter.author):
            await helpers.try_function(self.message.delete, True)
            await self.func(self.inter, self.song, self.songs_list[button_num], respond=False)
            self.value = True
        else:
            await helpers.try_function(inter.author.send, True, f"Don't you even try to use someone's selection panel once again. {public_config.emojis['dead']}")

    @disnake.ui.button(label="1", style=disnake.ButtonStyle.secondary)
    async def first_song(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(0, inter)

    @disnake.ui.button(label="2", style=disnake.ButtonStyle.secondary)
    async def second_song(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(1, inter)

    @disnake.ui.button(label="3", style=disnake.ButtonStyle.secondary)
    async def third_song(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(2, inter)

    @disnake.ui.button(label="4", style=disnake.ButtonStyle.secondary)
    async def fourth_song(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(3, inter)

    @disnake.ui.button(label="5", style=disnake.ButtonStyle.secondary)
    async def fifth_song(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(4, inter)

    async def send(self, embed=None):
        _, self.message = await helpers.try_function(self.inter.text_channel.send, True, view=self, embed=embed)

    async def on_timeout(self):
        if self.value:
            return
        try:
            await helpers.try_function(self.message.delete, True)
            voice = self.bot.states[self.inter.guild.id].voice
            self.value = True
            self.song.track_info.set_result(None)
            _, self.message = await helpers.try_function(self.inter.text_channel.send, True, f"{self.inter.author.mention} You're out of time! Next time think faster!")
            if not (voice.is_playing() or voice.is_paused()):
                await self.bot.abort_play(self.inter.guild.id, message=None)
            await asyncio.sleep(5)
            await helpers.try_function(self.message.delete, True)
        except Exception as err:
            print(f"Caught exception in select: {err}")
            pass
