import disnake
import asyncio
from disnake import TextInputStyle

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers

import helpers.embedder as embedder


class SongSelection(disnake.ui.View):
    url_list = None
    songs_list = None

    def __init__(self, songs, func, inter, song, bot):
        self.author = inter.author
        self.song = song
        self.url_list = []
        self.songs_list = songs
        self.func = func
        self.inter = inter
        self.bot = bot
        self.value = False
        for song in songs:
            url = f"https://www.youtube.com/{song['url_suffix'][:song['url_suffix'].find('&')]}"
            self.url_list.append(url)

        super().__init__(timeout=public_config.music_settings["SelectionPanelTimeout"])

    async def button_callback(self, button_num, inter):
        if inter.author == self.author or await helpers.is_admin(inter.author):
            await helpers.try_function(self.message.delete, True)
            await self.func(self.inter, self.song, self.url_list[button_num], respond=False)
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

    async def send(self):
        embed = embedder.song_selections(self.author, self.songs_list)
        _, self.message = await helpers.try_function(self.inter.text_channel.send, True, view=self, embed=embed)

    async def on_timeout(self):
        if self.value:
            return
        try:
            await helpers.try_function(self.message.delete, True)
            voice = self.bot.states[self.inter.guild.id].voice
            self.value = True
            self.song.track_info.set_result(None)
            _, self.message = await helpers.try_function(self.inter.text_channel.send, True, f"{self.inter.author.mention} You're out of time! Next time think faster!", delete_after=5)
            if not (voice.is_playing() or voice.is_paused()):
                await self.bot.abort_play(self.inter.guild.id, message=None)
        except Exception as err:
            print(f"Caught exception in select: {err}")
            pass


class QueueList(disnake.ui.View):
    embedder = None
    start_index = None

    def __init__(self, queue, inter, song, bot):
        self.author = inter.author
        self.queue = queue
        self.bot = bot
        self.inter = inter
        self.song = song
        self.start_index = 0

        super().__init__()

        self.update_buttons()

    async def button_callback(self, button_num, inter):
        await inter.response.defer()
        if inter.author == self.author or await helpers.is_admin(inter.author):
            if self.start_index + button_num >= 0 and self.start_index + button_num <= len(self.queue):
                self.start_index += button_num
                self.update_buttons()

                embed = embedder.queue(self.inter.guild, self.queue, self.start_index, self.song)
                await helpers.try_function(self.message.edit, True, view=self, embed=embed)
        else:
            await helpers.try_function(inter.author.send, True, f"Don't you even try to use someone's selection panel once again. {public_config.emojis['dead']}")

    @disnake.ui.button(label="<", style=disnake.ButtonStyle.secondary, custom_id="prev", disabled=True)
    async def prev_page(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(-10, inter)

    @disnake.ui.button(label=">", style=disnake.ButtonStyle.secondary, custom_id="next", disabled=True)
    async def next_page(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(10, inter)

    async def send(self, embed=None):
        _, self.message = await helpers.try_function(self.inter.text_channel.send, True, view=self, embed=embed)

    def update_buttons(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button) and child.custom_id and child.custom_id == "prev":
                child.disabled = (self.start_index == 0)
            if isinstance(child, disnake.ui.Button) and child.custom_id and child.custom_id == "next":
                child.disabled = (self.start_index + 10 > len(self.queue))


class MessageForm(disnake.ui.Modal):
    response = None

    def __init__(self, title="Message to Supreme Beings", response="Your message was sent to other Supreme Beings, my master."):
        components = [
            disnake.ui.TextInput(
                label="Message",
                placeholder="Type your message.",
                custom_id="msg",
                style=TextInputStyle.paragraph,
            ),
        ]
        self.response = response
        super().__init__(title=title, components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.send_message(self.response)
