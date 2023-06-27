import disnake
from disnake.ext import commands
import asyncio

import private_config
import public_config
import helpers
from selection import *
from file_logger import *
from embedder import *


gl_flag = True


class Activity():
    acttype = None
    actname = None

    def __init__(self, acttype=None, actname=None):
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
    embedder = None
    file_logger = None

    def __init__(self, name, file_logger):
        self.bot = commands.InteractionBot(intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="everyone o_o", type=disnake.ActivityType.watching))
        self.name = name
        self.embedder = Embed()
        self.file_logger = file_logger

    # --------------------- MESSAGES --------------------------------
        @self.bot.event
        async def on_message_edit(before, after):
            if before.author.guild and before.author.guild.id not in private_config.log_ids:
                return
            if before.author.id in private_config.bot_ids.values():
                return
            if before.content != after.content:
                await before.guild.get_channel(private_config.log_ids[before.guild.id]).send(embed=self.embedder.message_edit(before, after))
            if before.pinned != after.pinned:
                if before.pinned:
                    await before.guild.get_channel(private_config.log_ids[before.guild.id]).send(embed=self.embedder.message_unpin(before, after))
                else:
                    await before.guild.get_channel(private_config.log_ids[before.guild.id]).send(embed=self.embedder.message_pin(before, after))

        @self.bot.event
        async def on_message_delete(message):
            if message.author.guild and message.author.guild.id not in private_config.log_ids:
                return
            if message.author.id not in private_config.bot_ids.values():
                await self.bot.get_channel(private_config.log_ids[message.channel.guild.id]).send(embed=self.embedder.message_delete(message))

    # --------------------- ACTIONS --------------------------------
        @self.bot.event
        async def on_audit_log_entry_create(entry):
            if entry.user.guild.id not in private_config.log_ids:
                return
            s = ''.join(('entry_', f'{entry.action}'[15:]))
            if hasattr(self.file_logger, s):
                log = getattr(self.file_logger, s)
                log(entry)
            if hasattr(self.embedder, s):
                s = getattr(self.embedder, s)
                await entry.guild.get_channel(private_config.log_ids[entry.guild.id]).send(embed=s(entry))

        @self.bot.event
        async def on_member_update(before, after):
            if before.guild.id not in private_config.log_ids:
                return
            self.file_logger.member_update(after)
            await before.guild.get_channel(private_config.log_ids[before.guild.id]).send(embed=self.embedder.profile_upd(before, after))

        @self.bot.event
        async def on_raw_member_remove(payload):
            if payload.guild_id not in private_config.log_ids:
                return
            self.file_logger.member_remove(payload)
            await payload.user.guild.get_channel(private_config.log_ids[payload.user.guild.id]).send(embed=self.embedder.member_remove(payload))

        @self.bot.event
        async def on_member_join(member):
            if member.guild.id in private_config.welcome_ids:
                channel = member.guild.get_channel(private_config.welcome_ids
                                                   [member.guild.id])
                await channel.send(embed=self.embedder.welcome_message(member))
                message = await channel.send(f"{member.mention}")
                await message.delete()

            if member.guild.id in private_config.log_ids:
                self.file_logger.member_join(member)
                await member.guild.get_channel(private_config.log_ids[member.guild.id]).send(embed=self.embedder.member_join(member))

        @ self.bot.event
        async def on_member_ban(guild, user):
            if guild.id not in private_config.log_ids:
                return
            await guild.get_channel(private_config.log_ids[guild.id]).send(embed=self.embedder.ban(guild, user))

        @ self.bot.event
        async def on_member_unban(guild, user):
            if guild.id not in private_config.log_ids:
                return
            await guild.get_channel(private_config.log_ids[guild.id]).send(embed=self.embedder.unban(guild, user))

    # --------------------- VOICE STATES --------------------------------
        @ self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
            if member.guild.id not in private_config.log_ids:
                return

            channel = member.guild.get_channel(
                private_config.log_ids[member.guild.id])

            if before.channel and after.channel:
                if before.channel.id != after.channel.id:
                    self.file_logger.switched(member, before, after)
                    if not after.afk:  # REGULAR SWITCH
                        await channel.send(embed=self.embedder.switched(member, before, after))
                    else:  # AFK
                        await channel.send(embed=self.embedder.afk(member, after))
                else:
                    for attr in dir(after):
                        if attr in public_config.on_v_s_update:
                            if getattr(after, attr) != getattr(before, attr) and hasattr(self.embedder, attr):
                                log = getattr(self.file_logger, attr)
                                log(member, after)
                                s = getattr(self.embedder, attr)
                                await channel.send(embed=s(member, after))
            elif before.channel:
                self.file_logger.disconnected(member, before)
                await channel.send(embed=self.embedder.disconnected(member, before))
            else:
                self.file_logger.connected(member, after)
                await channel.send(embed=self.embedder.connected(member, after))

    # --------------------- RANDOM --------------------------------
        @ self.bot.event
        async def on_ready():
            self.file_logger.enabled(self.bot)
            print(f"{self.name} is logged as {self.bot.user}")
            await self.status_check()

        @ self.bot.event
        async def on_disconnect():
            print(f"{self.name} has disconnected from Discord")
            self.file_logger.lost_connection(self.bot)
            global gl_flag
            gl_flag = False

    # --------------------- SLASH COMMANDS --------------------------------

        @self.bot.slash_command(description="Creates a welcome banner for a new member (manually)")
        async def welcome(inter, member: disnake.Member):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            embed = self.embedder.welcome_message(member)
            await inter.delete_original_response()
            await inter.channel.send(embed=embed)
            message = await inter.channel.send(f"{member.mention}")
            await message.delete()

        @ self.bot.slash_command(description="Check current status of user")
        async def status(inter: disnake.AppCmdInter, member: disnake.User):
            if await self.check_dm(inter):
                return
            await inter.send(embed=self.embedder.get_status(member))

        @ self.bot.slash_command(description="Stop checking current status of user")
        async def stopstatus(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.send("Stopping status_check running")
            global gl_flag
            gl_flag = False

        @ self.bot.slash_command(description="Check current status of users")
        async def startstatus(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.send("Starting status_check running")
            await self.status_check()

    # --------------------- METHODS --------------------------------

    async def run(self):
        await self.bot.start(private_config.tokens[self.name])

    async def check_dm(self, inter):
        if not inter.guild:
            if inter.author.id in private_config.admin_ids[list(private_config.admin_ids.keys())[0]]:
                await inter.send(f"{public_config.dm_error_admin}")
            else:
                await inter.send(f"{public_config.dm_error}")
            return True
        return False

    async def status_check(self):
        guild_list = self.bot.guilds
        global gl_flag
        gl_flag = True
        print("STARTED STATUS TRACKING")
        while True:
            old_list = {}

            for guild_num in range(len(guild_list)):
                if guild_list[guild_num].id in private_config.log_ids:
                    old_list[guild_list[guild_num].id] = self.gen_status_and_activity_list(
                        guild_list[guild_num].members)
            await asyncio.sleep(0.1)
            for guild_num in range(len(guild_list)):

                guild_id = guild_list[guild_num].id

                if guild_id in private_config.log_ids:
                    new_list = self.gen_status_and_activity_list(
                        guild_list[guild_num].members)
                    if len(new_list) == len(old_list[guild_id]):
                        for member_num in range(len(new_list)):

                            old_member = old_list[guild_id][member_num]
                            new_member = guild_list[guild_num].members[member_num]

                            if old_member != new_list[member_num] and not (new_member.bot and new_member.id not in private_config.bot_ids.values()):
                                if old_member.status != new_list[member_num].status:
                                    self.file_logger.status_upd(
                                        new_member)
                                if old_member.activities != new_list[member_num].activities:
                                    self.file_logger.activity_upd(
                                        new_member, old_member, new_list[member_num])
                                await new_member.guild.get_channel(private_config.status_log_ids[guild_id]).send(embed=self.embedder.activity_update(new_member, old_member, new_list[member_num]))
            if not gl_flag:
                print("STOPPED STATUS TRACKING")
                break

    def gen_status_and_activity_list(self, list):
        newlist = []
        for elem in list:
            new_user = UserStatus(str(elem.status))
            for acts in elem.activities:
                if f"{type(acts)}" == "<class 'disnake.activity.Spotify'>":
                    new_act = Activity(
                        type(acts), f'{acts.artists[0]} - "{acts.title}"')
                elif f"{type(acts)}" != "<class 'NoneType'>":
                    new_act = Activity(type(acts), f'{acts.name}')
                new_user.activities.append(new_act)
            newlist.append(new_user)
        return newlist
