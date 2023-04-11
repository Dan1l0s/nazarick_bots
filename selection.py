import disnake
import config
import helpers
import asyncio


class SelectionPanel(disnake.ui.View, disnake.ui.Select):
    def __init__(self, songs, func, inter, song):
        self.author = inter.author
        self.song = song
        self.func = func
        self.inter = inter
        self.select_done = asyncio.Future()
        options = []
        for song in songs:
            title = song['title']
            sz = config.music_settings["SelectionPanelMaxNameLen"]
            if len(title) > sz:
                title = title[:sz]+"..."
            if song['duration'] == 0:
                song['duration'] = "Live"
            options.append(disnake.SelectOption(
                label=f"{title} : {song['duration']}", value=song['url_suffix']))
        disnake.ui.View.__init__(
            self, timeout=config.music_settings["SelectionPanelTimeout"])
        disnake.ui.Select.__init__(self,
                                   placeholder="Choose your song!", options=options, custom_id="songs")
        self.add_item(self)

    async def send(self):
        self.message = await self.inter.text_channel.send(view=self)

    async def callback(self, inter):
        print("Called callback")
        if inter.author == self.author or helpers.is_admin(inter.author):
            await self.message.delete()
            await self.func(self.inter, self.song, f"https://www.youtube.com/{inter.values[0]}", respond=False)
            self.select_done.set_result(1)
        else:
            try:
                await inter.author.send(f"Don't you even try to use someone's selection panel once again. {config.emojis['dead']}")
            except:
                pass

    async def on_timeout(self):
        if self.select_done.done():
            return
        try:
            print("Called on timeout")
            await self.message.delete()
            self.select_done.set_result(1)
            self.message = await self.inter.channel.send(f"{self.inter.author.mention} You're out of time! Next time think faster!")
            await asyncio.sleep(5)
            await self.message.delete()
        except Exception as err:
            print(f"Caught exception in select: {err}")
            pass
