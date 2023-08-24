import disnake
import asyncio

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers
from helpers.embedder import Embed

class ViewQueue(disnake.ui.View):
    embedder = None
    range_start = None

    def __init__(self, queue, inter, song, bot):
        self.author = inter.author
        self.queue = queue
        self.bot = bot
        self.inter = inter
        self.song = song
        self.range_start = 0
        self.embedder = Embed()

        super().__init__()
    
    async def button_callback(self, button_num, inter):
        if inter.author == self.author or await helpers.is_admin(inter.author):
            if self.range_start + button_num >= 0 and self.range_start + button_num <= len(self.queue):
                self.range_start += button_num
                for child in self.children:
                        if isinstance(child, disnake.ui.Button) and child.custom_id and child.custom_id == "prev":
                            if self.range_start == 0:
                                child.disabled = True 
                            else:
                                child.disabled = False
                        if isinstance(child, disnake.ui.Button) and child.custom_id and child.custom_id == "next":
                            if self.range_start + 10 > len(self.queue):
                                child.disabled = True 
                            else:
                                child.disabled = False        
                embed = self.embedder.queue(self.inter.guild, self.queue, self.range_start, self.song)
                await helpers.try_function(self.message.edit, True, view=self, embed=embed)
            else:
                pass
            await inter.response.defer()    
        else:
            await helpers.try_function(inter.author.send, True, f"Don't you even try to use someone's selection panel once again. {public_config.emojis['dead']}")


    @disnake.ui.button(label="<", style=disnake.ButtonStyle.secondary, custom_id = "prev", disabled = True)
    async def prev_page(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(-10, inter)

    @disnake.ui.button(label=">", style=disnake.ButtonStyle.secondary, custom_id = "next")
    async def next_page(self, button: disnake.ui.Button, inter: disnake.AppCmdInter):
        await self.button_callback(10, inter)    

    async def send(self, embed = None):
        _, self.message = await helpers.try_function(self.inter.text_channel.send, True, view=self, embed=embed)    