from disnake.ext import commands
import asyncio
import disnake
from selection import *
from logger import *
from embedder import *
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
            if hasattr(self.embeds, s):
                s = getattr(self.embeds,s)
                await entry.guild.get_channel(config.log_ids[entry.guild.id]).send(embed=s(entry))  
                
        @self.bot.event
        async def on_raw_member_update(member):
            if member.guild.id not in config.log_ids:
                return
            await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.profile_upd(member))

        @self.bot.event
        async def on_raw_member_remove(payload):
            if payload.guild_id not in config.log_ids:
                return
            await payload.user.guild.get_channel(config.log_ids[payload.user.guild.id]).send(embed=self.embeds.member_remove(payload))

        @self.bot.event
        async def on_member_join(member):
            if member.guild.id not in config.log_ids:
                return
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
                    if not after.afk: #REGULAR SWITCH
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.switched(member, before, after))
                    else: #AFK
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.afk(member, after))
                else:
                    if before.mute != after.mute: #SERVER MUTE
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.sv_mute(member, after))
                    elif before.deaf != after.deaf: #SERVER DEAF
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.sv_deaf(member, after))
                    elif before.self_deaf != after.self_deaf: #SELF DEAF
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.self_deaf(member, after))
                    elif before.self_mute != after.self_mute: #SELF MUTE
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.self_mute(member, after))
                    elif before.self_stream != after.self_stream: #STREAM
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.stream(member,after))
                    elif before.self_video != after.self_video: #VIDEO
                        await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.video(member, after))
                    #await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.voice_update(member))
            elif before.channel:
                await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.disconnected(member, before))
            else:
                await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=self.embeds.connected(member, after))

        
    async def run(self):
        self.logger.enabled(self.bot)
        await self.bot.start(config.tokens[self.name])
        
    