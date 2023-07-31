import disnake
from disnake.ext import commands
import asyncio

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers

from helpers.selection import SelectionPanel
from helpers.file_logger import FileLogger
from helpers.embedder import Embed
from helpers.helpers import GuildOption


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
    token = None
    name = None
    bot = None
    embedder = None
    file_logger = None

    def __init__(self, name, token, file_logger):
        self.bot = commands.InteractionBot(intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="everyone o_o", type=disnake.ActivityType.watching))
        self.name = name
        self.embedder = Embed()
        self.file_logger = file_logger
        self.token = token

    # --------------------- MESSAGES --------------------------------

        @self.bot.event
        async def on_message(message):
            if not message.guild:
                if helpers.is_supreme_being(message.author):
                    await message.reply(private_config.on_message_supreme_being)
                return
            await self.check_mentions(message)

        @self.bot.event
        async def on_message_edit(before, after):
            if not before.author.guild:
                return
            if before.author.id in private_config.bot_ids.values():
                return
            guild_id = before.author.guild.id
            channel_id = await helpers.get_guild_option(guild_id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if before.content != after.content:
                await channel.send(embed=self.embedder.message_edit(before, after))
            if before.pinned != after.pinned:
                if before.pinned:
                    await channel.send(embed=self.embedder.message_unpin(before, after))
                else:
                    await channel.send(embed=self.embedder.message_pin(before, after))

        @self.bot.event
        async def on_message_delete(message):
            if not message.author.guild:
                return
            channel_id = await helpers.get_guild_option(message.author.guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if message.author.id not in private_config.bot_ids.values():
                await channel.send(embed=self.embedder.message_delete(message))

    # --------------------- ACTIONS --------------------------------
        @self.bot.event
        async def on_audit_log_entry_create(entry):
            channel_id = await helpers.get_guild_option(entry.user.guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            s = f"entry_{str(entry.action)[15:]}"
            if hasattr(self.file_logger, s):
                log = getattr(self.file_logger, s)
                log(entry)
            if hasattr(self.embedder, s):
                s = getattr(self.embedder, s)
                await channel.send(embed=s(entry))

        @self.bot.event
        async def on_member_update(before, after):
            channel_id = await helpers.get_guild_option(before.guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            # self.file_logger.member_update(after)
            await channel.send(embed=self.embedder.profile_upd(before, after))

        @self.bot.event
        async def on_raw_member_remove(payload):
            channel_id = await helpers.get_guild_option(payload.guild_id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            self.file_logger.member_remove(payload)
            await channel.send(embed=self.embedder.member_remove(payload))

        @self.bot.event
        async def on_member_join(member):
            welcome_channel_id = await helpers.get_guild_option(member.guild.id, GuildOption.WELCOME_CHANNEL)
            log_channel_id = await helpers.get_guild_option(member.guild.id, GuildOption.LOG_CHANNEL)

            if welcome_channel_id:
                welcome_channel = self.bot.get_channel(int(welcome_channel_id))
                user = self.bot.get_user(member.id)
                await welcome_channel.send(embed=self.embedder.welcome_message(member, user))
                message = await welcome_channel.send(f"{member.mention}")
                await message.delete()

            if log_channel_id:
                log_channel = self.bot.get_channel(int(log_channel_id))
                self.file_logger.member_join(member)
                await log_channel.send(embed=self.embedder.member_join(member))

        @ self.bot.event
        async def on_member_ban(guild, user):
            channel_id = await helpers.get_guild_option(guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            await channel.send(embed=self.embedder.ban(guild, user))

        @ self.bot.event
        async def on_member_unban(guild, user):
            channel_id = await helpers.get_guild_option(guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            await channel.send(embed=self.embedder.unban(guild, user))

    # --------------------- VOICE STATES --------------------------------
        @ self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
            channel_id = await helpers.get_guild_option(member.guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))

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
            # self.file_logger.lost_connection(self.bot)
            # global gl_flag
            # gl_flag = False

        @self.bot.event
        async def on_connect():
            print(f"{self.name} has connected to Discord")
            # await self.status_check()

    # --------------------- SLASH COMMANDS --------------------------------

        @self.bot.slash_command(description="Creates a welcome banner for a new member (manually)")
        async def welcome(inter, member: disnake.Member):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            user = self.bot.get_user(member.id)
            embed = self.embedder.welcome_message(member, user)
            await inter.delete_original_response()
            await inter.channel.send(embed=embed)
            message = await inter.channel.send(f"{member.mention}")
            await message.delete()

        @ self.bot.slash_command(description="Check current status of user")
        async def status(inter: disnake.AppCmdInter, member: disnake.User):
            if await self.check_dm(inter):
                return
            await inter.send(embed=self.embedder.get_status(member))

        @ self.bot.slash_command()
        async def set(inter):
            pass

        @ set.sub_command_group()
        async def logs(inter):
            pass

        @ logs.sub_command(description="Allows admin to set channel for common logs")
        async def common(inter, channel: disnake.TextChannel = commands.Param(description='Select text channel for common logs')):
            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            await helpers.set_guild_option(inter.guild.id, GuildOption.LOG_CHANNEL, channel.id)
            await inter.edit_original_response(f'New log channel is {channel.mention}')

        @ logs.sub_command(description="Allows admin to set channel for status logs")
        async def status(inter, channel: disnake.TextChannel = commands.Param(description='Select text channel for status logs')):
            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            await helpers.set_guild_option(inter.guild.id, GuildOption.STATUS_LOG_CHANNEL, channel.id)
            await inter.edit_original_response(f'New status log channel is {channel.mention}')

        @ logs.sub_command(description="Allows admin to set channel for welcome logs")
        async def welcome(inter, channel: disnake.TextChannel = commands.Param(description='Select text channel for welcomes logs')):
            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            await helpers.set_guild_option(inter.guild.id, GuildOption.WELCOME_CHANNEL, channel.id)
            await inter.edit_original_response(f'New welcome channel is {channel.mention}')

    # --------------------- METHODS --------------------------------

    async def run(self):
        await self.bot.start(self.token)

    async def check_dm(self, inter):
        if not inter.guild:
            await inter.send((private_config.dm_error, private_config.dm_error_supreme_being)[helpers.is_supreme_being(inter.author)])
            return True
        return False

    async def status_check(self):
        global gl_flag
        gl_flag = True
        print("STARTED STATUS TRACKING")
        while not self.bot.is_closed():
            guild_list = self.bot.guilds
            old_list = {}

            for guild in guild_list:
                status_log_channel_id = await helpers.get_guild_option(guild.id, GuildOption.STATUS_LOG_CHANNEL)
                if status_log_channel_id:
                    old_list[guild.id] = self.gen_status_and_activity_list(guild.members)
            await asyncio.sleep(0.1)
            for guild in guild_list:
                if not guild.id in old_list.keys():
                    continue
                guild_id = guild.id
                status_log_channel_id = await helpers.get_guild_option(guild_id, GuildOption.STATUS_LOG_CHANNEL)

                if status_log_channel_id:
                    new_list = self.gen_status_and_activity_list(guild.members)
                    if len(new_list) == len(old_list[guild_id]):
                        for member_num in range(len(new_list)):

                            old_member = old_list[guild_id][member_num]
                            new_member = guild.members[member_num]

                            if old_member != new_list[member_num] and not (new_member.bot and new_member.id not in private_config.bot_ids.values()):
                                if old_member.status != new_list[member_num].status:
                                    self.file_logger.status_upd(
                                        new_member)
                                if old_member.activities != new_list[member_num].activities:
                                    self.file_logger.activity_upd(
                                        new_member, old_member, new_list[member_num])
                                channel = self.bot.get_channel(int(status_log_channel_id))
                                asyncio.create_task(channel.send(embed=self.embedder.activity_update(new_member, old_member, new_list[member_num])))
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

    async def check_mentions(self, message):
        if len(message.role_mentions) > 0 or len(message.mentions) > 0:
            client = message.guild.me
            if helpers.is_mentioned(client, message):
                if await helpers.is_admin(message.author):
                    if "ping" in message.content.lower() or "пинг" in message.content.lower():
                        return await message.reply(f"Yes, my master. My ping is {round(self.bot.latency*1000)} ms")
                    else:
                        return await message.reply("At your service, my master.")
                else:
                    try:
                        await message.author.timeout(duration=10, reason="Ping by lower life form")
                    except:
                        pass
                    return await message.reply(f"How dare you tag me? Know your place, trash")
