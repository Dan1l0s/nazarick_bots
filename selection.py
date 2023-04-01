import disnake
import config


class SelectionPanel(disnake.ui.Select):
    def __init__(self, songs, func, author):
        self.author = author
        self.func = func
        options = []
        for song in songs:
            title = song['title']
            if len(title) > 45:
                title = title[:45]+"..."
            options.append(disnake.SelectOption(
                label=f"{title} : {song['duration']}", value=song['url_suffix']))
        super().__init__(placeholder="Choose your song!", options=options, custom_id="songs")

    async def callback(self, inter):
        if inter.author == self.author:
            await inter.response.defer()
            await inter.delete_original_response()
            await self.func(inter, f"https://www.youtube.com/{inter.values[0]}")
        else:
            try:
                await inter.author.send(f"Don't you even try to use someone's selection panel once again. {config.emojis['dead']}")
            except:
                pass
