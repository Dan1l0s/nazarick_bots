"""Audit-trail bot: mirrors server events (messages, moderation actions, voice
state, member joins/leaves, presence changes) into configured log channels as
embeds, and writes the same events to db/logs.db.

Most handlers follow the same shape: look up the guild's configured log
channel, bail out (clearing the setting) if the channel no longer exists, then
send an embed built by helpers/embedder.py.

Two of the handlers dispatch dynamically by name - `on_audit_log_entry_create`
builds `entry_<action>` and looks it up on both `database_logger` and
`embedder`, and the voice-state handler looks up `<attr>` for each changed
voice property. That's why adding a new logged event is usually just a matter
of adding matching functions to those two modules (and why the duplicated
`entry_sticker_create` fixed in Stage 1 silently produced no sticker-delete
logs).

Behavior preserved from the original, plus one loop fix and one performance
knob in `status_check` - see CHANGES.md "Stage 4".
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Dict

import disnake
from disnake.ext import commands

import configs.private_config as private_config
import configs.public_config as public_config
import helpers.database_logger as database_logger
import helpers.embedder as embedder
import helpers.helpers as helpers
from helpers.helpers import GuildOption

logger = logging.getLogger("nazarick.logger")

# How often status_check() re-reads every member's presence. 0.5s matches the
# original exactly. See CHANGES.md "Stage 4" for why this loop is the most
# expensive thing in the process and what the cost of raising it is.
STATUS_POLL_INTERVAL = 0.5

# Seconds to cache each guild's status-log-channel setting inside
# status_check(). The original re-queried sqlite for every guild on every pass
# (i.e. guild_count x 2 queries/second, each opening its own connection).
# 0 disables the cache and restores the original query-every-pass behavior.
# Any positive value means a change to /set logs status takes up to that many
# seconds to take effect.
STATUS_CHANNEL_CACHE_SECONDS = 0


class Activity:
    """One presence activity (game, Spotify track, custom status...)."""

    def __init__(self, acttype=None, actname=None):
        self.acttype = acttype
        self.actname = actname

    def __eq__(self, other):
        return self.acttype == other.acttype and self.actname == other.actname


class UserStatus:
    """A member's online status plus their current activities, used to diff
    presence between polls."""

    def __init__(self, status):
        self.status = status
        self.activities = []
        self.updated = False

    def __eq__(self, other):
        # Compared as sets: activity ordering from Discord isn't stable, and
        # a reorder alone shouldn't count as a change.
        a = set((x.acttype, x.actname) for x in self.activities)
        b = set((x.acttype, x.actname) for x in other.activities)
        return self.status == other.status and a == b


class LogBot:

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
            await helpers.check_mentions(message, self.bot)

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

            # Dynamic dispatch: disnake's action repr looks like
            # "AuditLogAction.channel_create"; [15:] strips the enum prefix,
            # giving "entry_channel_create" to look up in both modules. A
            # missing function on either side is silently skipped.
            s = f"entry_{str(entry.action)[15:]}"
            entry_name = s
            if hasattr(database_logger, s):
                log = getattr(database_logger, s)
                await log(entry)
            if hasattr(embedder, s):
                s = getattr(embedder, s)
                await helpers.try_function(channel.send, True, embed=s(entry))
            try:
                # Anti-nuke tripwire: on the project's own guilds, a moderator
                # exceeding the kick/ban budget within one bot uptime gets
                # timed out and the owner notified.
                if (entry_name == "entry_kick" or entry_name == "entry_ban") and entry.user.guild.id in private_config.test_guilds:
                    if entry.user.id not in self.kick_bans:
                        self.kick_bans[entry.user.id] = 0
                    self.kick_bans[entry.user.id] += 1
                    if self.kick_bans[entry.user.id] >= public_config.kick_ban_limit:
                        await helpers.try_function(entry.user.timeout, True, reason="Exceeded kick/ban limit", duration=1000000)
                        await helpers.try_function(self.bot.get_user(private_config.supreme_beings[0]).send, True, f"My apologies, Ainz-sama. User {self.bot.get_user(entry.user.id).mention} has exceeded kick/ban limit. Please, take measures.")
            except Exception:
                logger.debug("on_audit_log_entry_create: kick/ban tripwire failed", exc_info=True)

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
                    # Ping-and-delete: fires the member's notification without
                    # leaving a bare mention in the channel.
                    message = await welcome_channel.send(f"{member.mention}")
                    await message.delete()

            if log_channel_id:
                log_channel = self.bot.get_channel(int(log_channel_id))
                if not log_channel:
                    await helpers.set_guild_option(member.guild.id, GuildOption.LOG_CHANNEL, None)
                else:
                    await database_logger.member_join(member)
                    await helpers.try_function(log_channel.send, True, embed=embedder.member_join(member))

        @self.bot.event
        async def on_member_ban(guild, user):
            channel_id = await helpers.get_guild_option(guild.id, GuildOption.LOG_CHANNEL)
            if not channel_id:
                return
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                await helpers.set_guild_option(guild.id, GuildOption.LOG_CHANNEL, None)
                return
            await helpers.try_function(channel.send, True, embed=embedder.ban(guild, user))

        @self.bot.event
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
        @self.bot.event
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
                    # Same channel: diff the individual voice properties listed
                    # in public_config.on_v_s_update and log each change.
                    for attr in dir(after):
                        if attr in public_config.on_v_s_update:
                            if getattr(after, attr) != getattr(before, attr) and hasattr(embedder, attr):
                                # BUGFIX: the embedder side was guarded by
                                # hasattr but database_logger was not, so a
                                # property with an embed function and no
                                # matching logger function would raise
                                # AttributeError and abort the whole handler
                                # (losing the remaining voice-state logs for
                                # this event). Now guarded symmetrically.
                                if hasattr(database_logger, attr):
                                    log = getattr(database_logger, attr)
                                    await log(member, after)
                                s = getattr(embedder, attr)
                                if attr == "self_mute":
                                    embed = s(member, before, after)
                                else:
                                    embed = s(member, after)
                                await helpers.try_function(channel.send, True, embed=embed)
                    # Deafening yourself also mutes you client-side, so a
                    # deafen-only change wouldn't be caught by the loop above
                    # (self_mute is unchanged); this covers that case.
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
        @self.bot.event
        async def on_ready():
            if not self.on_ready_flag:
                self.on_ready_flag = True
                await database_logger.enabled(self.bot)
                print(f"{self.name} is logged as {self.bot.user}")
                await self.status_check()

        @self.bot.event
        async def on_disconnect():
            print(f"{self.name} has disconnected from Discord")

        @self.bot.event
        async def on_connect():
            print(f"{self.name} has connected to Discord")

    # --------------------- SLASH COMMANDS --------------------------------

        @self.bot.slash_command(contexts=helpers.GUILD_ONLY, description="Creates a welcome banner for a new member (manually)")
        async def welcome(inter: disnake.AppCmdInter,
                          member: disnake.Member = commands.Param(description="Specify the member to create banner for")):
            await inter.response.defer()
            user = self.bot.get_user(member.id)
            embed = embedder.welcome_message(member, user)
            await helpers.try_function(inter.delete_original_response, True)
            await inter.channel.send(embed=embed)
            await inter.channel.send(f"{member.mention}", delete_after=0.001)

        @self.bot.slash_command(contexts=helpers.GUILD_ONLY)
        async def set(inter: disnake.AppCmdInter):
            pass

        @set.sub_command_group()
        async def logs(inter: disnake.AppCmdInter):
            pass

        @logs.sub_command(description="Allows admins to set a channel for common logs")
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

        @logs.sub_command(description="Allows admins to set a channel for status logs")
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

        @logs.sub_command(description="Allows admins to set a channel for welcome logs")
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

        @self.bot.slash_command(description="Reviews list of commands")
        async def help(inter: disnake.AppCmdInter):
            await inter.response.defer()
            await inter.send(embed=disnake.Embed(color=0, description=self.help()))

    # --------------------- METHODS --------------------------------

    async def run(self):
        await self.bot.start(self.token)

    async def _get_status_channels(self, guild_list, cache):
        """Returns {guild_id: status_log_channel_id} for guilds that have one.

        Optionally memoized for STATUS_CHANNEL_CACHE_SECONDS - see the constant
        at the top of this module. With the cache disabled (the default, and
        the original behavior) this issues one sqlite query per guild per poll.
        """
        status_channels = {}
        now = time.monotonic()
        for guild in guild_list:
            if STATUS_CHANNEL_CACHE_SECONDS > 0:
                cached = cache.get(guild.id)
                if cached and now - cached[0] < STATUS_CHANNEL_CACHE_SECONDS:
                    channel_id = cached[1]
                else:
                    channel_id = await helpers.get_guild_option(guild.id, GuildOption.STATUS_LOG_CHANNEL)
                    cache[guild.id] = (now, channel_id)
            else:
                channel_id = await helpers.get_guild_option(guild.id, GuildOption.STATUS_LOG_CHANNEL)
            if channel_id:
                status_channels[guild.id] = channel_id
        return status_channels

    async def status_check(self):
        """Polling loop that diffs every member's presence and posts changes to
        each guild's status-log channel.

        This is by far the most expensive thing in the process: it walks every
        member of every guild that has status logging enabled, twice a second.
        See CHANGES.md "Stage 4" before tuning STATUS_POLL_INTERVAL or enabling
        STATUS_CHANNEL_CACHE_SECONDS.
        """
        prev_status = {}
        channel_cache = {}
        while True:
            try:
                delayed_tasks = []
                new_status = {}
                guild_list = self.bot.guilds
                status_channels = await self._get_status_channels(guild_list, channel_cache)
                for guild in guild_list:
                    if guild.id not in status_channels:
                        continue
                    for member in guild.members:
                        if member.bot:
                            continue
                        new_status[member] = UserStatus(None)
                self.gen_status_and_activity(new_status)

                for member, status in new_status.items():
                    # Members absent from the previous pass are skipped rather
                    # than reported, so a restart doesn't dump every member's
                    # current status into the log channel.
                    if member not in prev_status or status == prev_status[member]:
                        continue
                    status.updated = True
                    if status.status != prev_status[member].status:
                        delayed_tasks.append(database_logger.status_upd(member))
                    if status.activities != prev_status[member].activities:
                        delayed_tasks.append(database_logger.activity_upd(member, prev_status[member], status))
                for guild in guild_list:
                    if guild.id not in status_channels.keys():
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
            except Exception as ex:
                print(f"Exception in status log: {ex}", file=sys.stderr)
            finally:
                # BUGFIX: the sleep used to live at the end of the `try` block,
                # so any exception skipped it and the loop respun immediately
                # with no delay - a hot loop that pegged a core for as long as
                # the error condition persisted. Moving it to `finally`
                # guarantees the interval is always honored.
                await asyncio.sleep(STATUS_POLL_INTERVAL)

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
