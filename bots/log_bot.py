import disnake
from disnake.ext import commands
import asyncio
import sys
from typing import Dict

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers
import helpers.database_logger as database_logger
import helpers.embedder as embedder

from helpers.helpers import GuildOption


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
    activities = None
    updated = None

    def __init__(self, status):
        self.status = status
        self.activities = []
        self.updated = False

    def __eq__(self, other):
        a = set((x.acttype, x.actname) for x in self.activities)
        b = set((x.acttype, x.actname) for x in other.activities)
        return self.status == other.status and a == b


class LogBot():
    token = None
    name = None
    bot = None
    kicks_bans = None
    on_ready_flag = None

    def __init__(self, name: str, token: str):
        self.bot = commands.InteractionBot(intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="everyone o_o", type=disnake.ActivityType.watching))
        self.name = name
        self.token = token
        self.kick_bans = {}
        self.on_ready_flag = False

    # --------------------- MESSAGES --------------------------------

        @self.bot.event
        async def on_message(message):
            if not message.guild:
                if helpers.is_supreme_being(message.author):
                    await message.reply(public_config.on_message_supreme_being)
                return
            await helpers.check_mentions(message)

        @self.bot.event
        async def on_message_edit(before, after):
            if not hasattr(before.author, "guild") or not before.author.guild:
                return
            if before.author.id in private_config.bot_ids.values():
                return
            guild_id = before.author.guild.id
            channel_id = await helpers.get_guild_option(guild_id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(before.author.guild.id, GuildOption.LOG_CHANNEL, None)
                return

            if before.content != after.content:
                await helpers.try_function(channel.send, True, embed=embedder.message_edit(before, after))
            if before.pinned != after.pinned:
                if before.pinned:
                    await helpers.try_function(channel.send, True, embed=embedder.message_unpin(before, after))
                else:
                    await helpers.try_function(channel.send, True, embed=embedder.message_pin(before, after))

        @self.bot.event
        async def on_message_delete(message):
            if not hasattr(message.author, "guild") or not message.author.guild:
                return
            channel_id = await helpers.get_guild_option(message.author.guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return

            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(message.author.guild.id, GuildOption.LOG_CHANNEL, None)
                return
            if message.author.id not in private_config.bot_ids.values():
                await helpers.try_function(channel.send, True, embed=embedder.message_delete(message))

    # --------------------- ACTIONS --------------------------------
        @self.bot.event
        async def on_audit_log_entry_create(entry):
            channel_id = await helpers.get_guild_option(entry.user.guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(entry.user.guild.id, GuildOption.LOG_CHANNEL, None)
                return

            s = f"entry_{str(entry.action)[15:]}"
            entry_name = s
            if hasattr(database_logger, s):
                log = getattr(database_logger, s)
                await log(entry)
            if hasattr(embedder, s):
                s = getattr(embedder, s)
                await helpers.try_function(channel.send, True, embed=s(entry))
            try:
                if (entry_name == "entry_kick" or entry_name == "entry_ban") and entry.user.guild.id in private_config.test_guilds:
                    if entry.user.id not in self.kick_bans:
                        self.kick_bans[entry.user.id] = 0
                    self.kick_bans[entry.user.id] += 1
                    if self.kick_bans[entry.user.id] >= public_config.kick_ban_limit:
                        await helpers.try_function(entry.user.timeout, True, reason="Exceeded kick/ban limit", duration=1000000)
                        await helpers.try_function(self.bot.get_user(private_config.supreme_beings[0]).send, True, f"My apologies, Ainz-sama. User {self.bot.get_user(entry.user.id).mention} has exceeded kick/ban limit. Please, take measures.")
            except:
                pass

        @self.bot.event
        async def on_member_update(before, after):
            channel_id = await helpers.get_guild_option(before.guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(before.guild.id, GuildOption.LOG_CHANNEL, None)
                return
            # await database_logger.member_update(after)
            await helpers.try_function(channel.send, True, embed=embedder.profile_upd(before, after))

        @self.bot.event
        async def on_raw_member_remove(payload):
            channel_id = await helpers.get_guild_option(payload.guild_id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(payload.guild_id, GuildOption.LOG_CHANNEL, None)
                return
            await database_logger.member_remove(payload)
            await helpers.try_function(channel.send, True, embed=embedder.member_remove(payload))

        @self.bot.event
        async def on_member_join(member):
            welcome_channel_id = await helpers.get_guild_option(member.guild.id, GuildOption.WELCOME_CHANNEL)
            log_channel_id = await helpers.get_guild_option(member.guild.id, GuildOption.LOG_CHANNEL)

            if welcome_channel_id and not member.bot:
                welcome_channel = self.bot.get_channel(int(welcome_channel_id))
                if not welcome_channel:
                    await helpers.set_guild_option(member.guild.id, GuildOption.WELCOME_CHANNEL, None)
                else:
                    user = self.bot.get_user(member.id)
                    await helpers.try_function(welcome_channel.send, True, embed=embedder.welcome_message(member, user))
                    message = await welcome_channel.send(f"{member.mention}")
                    await message.delete()

            if log_channel_id:
                log_channel = self.bot.get_channel(int(log_channel_id))
                if not log_channel:
                    await helpers.set_guild_option(member.guild.id, GuildOption.LOG_CHANNEL, None)
                else:
                    await database_logger.member_join(member)
                    await helpers.try_function(log_channel.send, True, embed=embedder.member_join(member))

        @ self.bot.event
        async def on_member_ban(guild, user):
            channel_id = await helpers.get_guild_option(guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(guild.id, GuildOption.LOG_CHANNEL, None)
                return
            await helpers.try_function(channel.send, True, embed=embedder.ban(guild, user))

        @ self.bot.event
        async def on_member_unban(guild, user):
            channel_id = await helpers.get_guild_option(guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(guild.id, GuildOption.LOG_CHANNEL, None)
                return
            await helpers.try_function(channel.send, True, embed=embedder.unban(guild, user))

    # --------------------- VOICE STATES --------------------------------
        @ self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
            channel_id = await helpers.get_guild_option(member.guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(member.guild.id, GuildOption.LOG_CHANNEL, None)
                return

            if before.channel and after.channel:
                if before.channel.id != after.channel.id:
                    await database_logger.switched(member, before, after)
                    if not after.afk:
                        await helpers.try_function(channel.send, True, embed=embedder.switched(member, before, after))
                    else:
                        await helpers.try_function(channel.send, True, embed=embedder.afk(member, after))
                else:
                    for attr in dir(after):
                        if attr in public_config.on_v_s_update:
                            if getattr(after, attr) != getattr(before, attr) and hasattr(embedder, attr):
                                log = getattr(database_logger, attr)
                                await log(member, after)
                                s = getattr(embedder, attr)
                                if attr == "self_mute":
                                    embed = s(member, before, after)
                                else:
                                    embed = s(member, after)
                                await helpers.try_function(channel.send, True, embed=embed)
                    if before.self_mute == after.self_mute and before.self_deaf != after.self_deaf:
                        embed = embedder.self_mute(member, before, after)
                        await helpers.try_function(channel.send, True, embed=embed)
            elif before.channel:
                await database_logger.disconnected(member, before)
                await helpers.try_function(channel.send, True, embed=embedder.disconnected(member, before))
            else:
                await database_logger.connected(member, after)
                await helpers.try_function(channel.send, True, embed=embedder.connected(member, after))

    # --------------------- RANDOM --------------------------------
        @ self.bot.event
        async def on_ready():
            if not self.on_ready_flag:
                self.on_ready_flag = True
                await database_logger.enabled(self.bot)
                print(f"{self.name} is logged as {self.bot.user}")
                await self.status_check()

        @ self.bot.event
        async def on_disconnect():
            print(f"{self.name} has disconnected from Discord")

        @self.bot.event
        async def on_connect():
            print(f"{self.name} has connected to Discord")

    # --------------------- SLASH COMMANDS --------------------------------

        @self.bot.slash_command(dm_permission=False, description="Creates a welcome banner for a new member (manually)")
        async def welcome(inter: disnake.AppCmdInter,
                          member: disnake.Member = commands.Param(description="Specify the member to create banner for")):
            await inter.response.defer()
            user = self.bot.get_user(member.id)
            embed = embedder.welcome_message(member, user)
            await helpers.try_function(inter.delete_original_response, True)
            await inter.channel.send(embed=embed)
            await inter.channel.send(f"{member.mention}", delete_after=0.001)

        @ self.bot.slash_command(dm_permission=False)
        async def set(inter: disnake.AppCmdInter):
            pass

        @ set.sub_command_group()
        async def logs(inter: disnake.AppCmdInter):
            pass

        @ logs.sub_command(description="Allows admins to set a channel for common logs")
        async def common(inter: disnake.AppCmdInter,
                         channel: (disnake.TextChannel | None) = commands.Param(default=None, description='Select a text channel for common logs')):
            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not an admin!")

            if channel:
                await helpers.set_guild_option(inter.guild.id, GuildOption.LOG_CHANNEL, channel.id)
                await inter.edit_original_response(f'New log channel is {channel.mention}')
            else:
                await helpers.set_guild_option(inter.guild.id, GuildOption.LOG_CHANNEL, None)
                await inter.edit_original_response('Common logs are disabled.')

        @ logs.sub_command(description="Allows admins to set a channel for status logs")
        async def status(inter: disnake.AppCmdInter,
                         channel: (disnake.TextChannel | None) = commands.Param(default=None, description='Select a text channel for status logs')):
            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not an admin!")

            if channel:
                await helpers.set_guild_option(inter.guild.id, GuildOption.STATUS_LOG_CHANNEL, channel.id)
                await inter.edit_original_response(f'New status log channel is {channel.mention}')
            else:
                await helpers.set_guild_option(inter.guild.id, GuildOption.STATUS_LOG_CHANNEL, None)
                await inter.edit_original_response('Status logs are disabled.')

        @ logs.sub_command(description="Allows admins to set a channel for welcome logs")
        async def welcome(inter: disnake.AppCmdInter,
                          channel: (disnake.TextChannel | None) = commands.Param(default=None, description='Select a text channel for welcome logs')):
            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not an admin!")

            if channel:
                await helpers.set_guild_option(inter.guild.id, GuildOption.WELCOME_CHANNEL, channel.id)
                await inter.edit_original_response(f'New welcome channel is {channel.mention}')
            else:
                await helpers.set_guild_option(inter.guild.id, GuildOption.WELCOME_CHANNEL, None)
                await inter.edit_original_response('Welcome logs are disabled.')

        @ self.bot.slash_command(description="Reviews list of commands")
        async def help(inter: disnake.AppCmdInter):
            await inter.response.defer()
            await inter.send(embed=disnake.Embed(color=0, description=self.help()))

    # --------------------- METHODS --------------------------------

    async def run(self):
        await self.bot.start(self.token)

    async def status_check(self):
        prev_status = {}
        while True:
            try:
                delayed_tasks = []
                new_status = {}
                status_channels = {}
                guild_list = self.bot.guilds
                for guild in guild_list:
                    status_log_channel_id = await helpers.get_guild_option(guild.id, GuildOption.STATUS_LOG_CHANNEL)
                    if status_log_channel_id:
                        status_channels[guild.id] = status_log_channel_id
                        for member in guild.members:
                            if member.bot:
                                continue
                            new_status[member] = UserStatus(None)
                self.gen_status_and_activity(new_status)

                for member, status in new_status.items():
                    if not member in prev_status or status == prev_status[member]:
                        continue
                    status.updated = True
                    if status.status != prev_status[member].status:
                        delayed_tasks.append(database_logger.status_upd(member))
                    if status.activities != prev_status[member].activities:
                        delayed_tasks.append(database_logger.activity_upd(member, prev_status[member], status))
                for guild in guild_list:
                    if not guild.id in status_channels.keys():
                        continue
                    for member in guild.members:
                        if not member.bot and new_status[member].updated:
                            channel = self.bot.get_channel(status_channels[guild.id])
                            if not channel:
                                await helpers.set_guild_option(guild.id, GuildOption.STATUS_LOG_CHANNEL, None)
                                continue
                            delayed_tasks.append(helpers.try_function(channel.send, True, embed=embedder.activity_update(member, prev_status[member], new_status[member])))
                asyncio.create_task(helpers.run_delayed_tasks(delayed_tasks))
                prev_status = new_status
                await asyncio.sleep(0.5)
            except Exception as ex:
                print(f"Exception in status log: {ex}", file=sys.stderr)
                pass

    def gen_status_and_activity(self, status_dict: Dict[disnake.Member, UserStatus]):
        for member, status in status_dict.items():
            status.status = str(member.status)
            for activity in member.activities:
                if type(activity) == disnake.activity.Spotify:
                    status.activities.append(Activity(type(activity), f'{activity.artists[0]} - "{activity.title}"'))
                elif activity is not None:
                    status.activities.append(Activity(type(activity), f'{activity.name}'))

    def help(self):
        ans = "Type **/set logs common** to set a channel for common logs\n"
        ans += "Type **/set logs status** to set a channel for status logs\n"
        ans += "Type **/set logs welcome** to set a channel for welcome messages\n"
        ans += "Type **/welcome** to create a welcome banner manually\n"
        return ans
