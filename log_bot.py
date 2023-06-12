from disnake.ext import commands
import asyncio
import disnake
from selection import *
from logger import *
from embedder import *
import dicts
import helpers
import config

class AutoLog():
    
    name = None
    bot = None
    embeds = None
    logger = None

    def __init__(self, name, logger):
        self.bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="with the slaves", type=disnake.ActivityType.playing))
        self.name = name
        self.embeds = Embed()
        self.logger = logger

    # --------------------- MESSAGES --------------------------------
        @self.bot.event
        async def on_message_edit(before, after):
            if before.author.guild and before.author.guild.id not in config.log_ids:
                return
            if before.author.id in config.bot_ids.values():
                return
            if before.content != after.content:
                await before.guild.get_channel(config.log_ids[before.guild.id]).send(embed=self.embeds.message_edit(before, after))
            if before.pinned != after.pinned:
                if before.pinned:
                    await before.guild.get_channel(config.log_ids[before.guild.id]).send(embed = self.embeds.message_unpin(before, after))
                else:
                    await before.guild.get_channel(config.log_ids[before.guild.id]).send(embed = self.embeds.message_pin(before, after))    
    
        @self.bot.event
        async def on_message_delete(message):
            if message.author.guild and message.author.guild.id not in config.log_ids:
                return
            if message.author.id not in config.bot_ids.values():
                await self.bot.get_channel(config.log_ids[message.channel.guild.id]).send(embed = self.embeds.message_delete(message))

    # --------------------- ACTIONS --------------------------------
        @self.bot.event
        async def on_audit_log_entry_create(entry):
            if entry.user.guild.id not in config.log_ids:
                return
            s = ''.join(('entry_', f'{entry.action}'[15:]))
            if hasattr(self.logger, s):
                log = getattr(self.logger, s)
                log(entry)
            if hasattr(self.embeds, s):
                s = getattr(self.embeds,s)
                await entry.guild.get_channel(config.log_ids[entry.guild.id]).send(embed=s(entry))  
                
        @self.bot.event
        async def on_member_update(before, after):
            if before.guild.id not in config.log_ids:
                return
            self.logger.member_update(after)
            await before.guild.get_channel(config.log_ids[before.guild.id]).send(embed=self.embeds.profile_upd(before, after))

        @self.bot.event
        async def on_raw_member_remove(payload):
            if payload.guild_id not in config.log_ids:
                return
            self.logger.member_remove(payload)
            await payload.user.guild.get_channel(config.log_ids[payload.user.guild.id]).send(embed=self.embeds.member_remove(payload))

        @self.bot.event
        async def on_member_join(member):
            if member.guild.id not in config.log_ids:
                return
            self.logger.member_join(member)
            await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.member_join(member))

        @self.bot.event
        async def on_member_ban(guild, user):
            if guild.id not in config.log_ids:
                return
            await guild.get_channel(config.log_ids[guild.id]).send(embed=self.embeds.ban(guild, user))

        @self.bot.event
        async def on_member_unban(guild, user):
            if guild.id not in config.log_ids:
                return
            await guild.get_channel(config.log_ids[guild.id]).send(embed=self.embeds.unban(guild, user))

    # --------------------- VOICE STATES --------------------------------
        @self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
            if member.guild.id not in config.log_ids:
                return
            if before.channel and after.channel:
                if before.channel.id != after.channel.id:
                    self.logger.switched(member, before, after)
                    if not after.afk: #REGULAR SWITCH
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.switched(member, before, after))
                    else: #AFK
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.afk(member, after))
                else:
                    for attr in dir(after):
                        if attr in dicts.on_v_s_update:
                            if getattr(after, attr) != getattr(before, attr) and hasattr(self.embeds, attr):
                                log = getattr(self.logger, attr)
                                log(member, after)
                                s = getattr(self.embeds, attr)
                                await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=s(member,after))
            elif before.channel:
                self.logger.disconnected(member, before)
                await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.disconnected(member, before))
            else:
                self.logger.connected(member, after)
                await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.connected(member, after))

    # --------------------- RANDOM --------------------------------
        @self.bot.event
        async def on_ready():
            self.logger.enabled(self.bot)
            print(f"{self.name} is logged as {self.bot.user}")

        @self.bot.event
        async def on_disconnect():
            self.logger.lost_connection(self.bot)
            print(f"{self.name} has disconnected from Discord")

    async def run(self):
        await self.bot.start(config.tokens[self.name])
        
    