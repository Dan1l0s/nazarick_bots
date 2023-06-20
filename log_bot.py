from disnake.ext import commands
import asyncio
import disnake
from selection import *
from logger import *
from embedder import *
import dicts
import helpers
import config

gl_flag = True

class Activity():
    acttype = None
    actname = None
    def __init__(self, acttype = None, actname = None):
        self.acttype = acttype
        self.actname = actname
    def __eq__(self, other):
        return self.acttype == other.acttype and self.actname == other.actname

class UserStatus():

    status = None
    activities = []
    def __init__(self, status):
        self.status = status
        self.activities = []    
    def __eq__(self, other):
        a = set((x.acttype, x.actname) for x in self.activities)
        b = set((x.acttype, x.actname) for x in other.activities)
        return self.status == other.status and a == b
    
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
            await self.status_check()

        @self.bot.event
        async def on_disconnect():
            self.logger.lost_connection(self.bot)
            print(f"{self.name} has disconnected from Discord")
            global gl_flag
            gl_flag = False

    # --------------------- SLASH COMMANDS --------------------------------

        @self.bot.slash_command(description="Chech current status of user")
        async def status(inter: disnake.AppCmdInter, member: disnake.Member):
            if await self.check_dm(inter):
                return
            await inter.send(embed = self.embeds.get_status(member))         

        @self.bot.slash_command(description="Stop checking current status of user")
        async def stopstatus(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.send("Stopping status_check running")
            global gl_flag
            gl_flag = False     

        @self.bot.slash_command(description="Check current status of users")
        async def startstatus(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.send("Starting status_check running")
            await self.status_check()         

    # --------------------- METHODS --------------------------------

    async def run(self):
        await self.bot.start(config.tokens[self.name])

    async def check_dm(self, inter):
        if not inter.guild:
            if inter.author.id in config.admin_ids[569924343010689025]:
                await inter.send(f"{dicts.dm_error_admin}")
            else:
                await inter.send(f"{dicts.dm_error}")
            return True
        return False   
    
    async def status_check(self):
        guild_list = self.bot.guilds
        global gl_flag
        gl_flag = True
        print("STARTED STATUS TRACKING")
        while True:
            for x in range(len(guild_list)):
                if guild_list[x].id in config.log_ids:
                    old_list = self.gen_status_and_activity_list(guild_list[x].members)
                    await asyncio.sleep(0.25)
                    new_list = self.gen_status_and_activity_list(guild_list[x].members)
                    #print(id(new_list))
                    if len(new_list) == len(old_list):
                        for y in range(len(new_list)):
                            if old_list[y] != new_list[y] and not (guild_list[x].members[y].bot and guild_list[x].members[y].id not in config.bot_ids.values()):
                                if old_list[y].status != new_list[y].status:
                                    self.logger.status_upd(guild_list[x].members[y])
                                if old_list[y].activities != new_list[y].activities:
                                    self.logger.activity_upd(guild_list[x].members[y], old_list[y], new_list[y])    
                                await guild_list[x].members[y].guild.get_channel(config.log_ids[guild_list[x].id]).send(embed=self.embeds.activity_update(guild_list[x].members[y], old_list[y], new_list[y]))
            if not gl_flag:
                print("STOPPED STATUS TRACKING")
                break

    def gen_status_and_activity_list(self, list):
        newlist = []
        for elem in list:
            new_user = UserStatus(str(elem.status))
            for acts in elem.activities:
                if f"{type(acts)}" == "<class 'disnake.activity.Spotify'>":
                    new_act = Activity(type(acts), f'{acts.artists[0]} - "{acts.title}"')
                elif f"{type(acts)}" != "<class 'NoneType'>":
                    new_act = Activity(type(acts), f'{acts.name}')
                new_user.activities.append(new_act)
            newlist.append(new_user)
        return newlist