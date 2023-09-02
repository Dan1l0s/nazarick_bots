import disnake
from disnake.ext import commands
import asyncio
import sys
import os
import datetime

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers
import helpers.database_logger as database_logger
import helpers.embedder as embedder

from helpers.helpers import GuildOption, Rank


class AdminBot():
    music_instances = None
    log_bot = None

    def __init__(self, name: str, token: str):
        self.bot = commands.InteractionBot(intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="with the subordinates", type=disnake.ActivityType.playing))
        self.name = name
        self.token = token
        self.music_instances = []

        @self.bot.event
        async def on_guild_join(guild):
            await self.add_admin(guild.id, guild.owner_id)

        @self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):

            if await self.temp_channels(member, before, after):
                return

            if await self.unmute_clients(member, after):
                return

            if not after.channel:
                if await helpers.check_admin_kick(member):
                    return

        @self.bot.event
        async def on_ready():
            await database_logger.enabled(self.bot)
            print(f"{self.name} is logged as {self.bot.user}")
            self.bot.loop.create_task(self.scan_timer())
            asyncio.create_task(self.monitor_errors())

            for guild in self.bot.guilds:
                await self.add_admin(guild.id, guild.owner_id)

        @self.bot.event
        async def on_disconnect():
            print(f"{self.name} has disconnected from Discord")
            # await database_logger.lost_connection(self.bot)

        @self.bot.event
        async def on_connect():
            print(f"{self.name} has connected to Discord")
            # await database_logger.lost_connection(self.bot)

        @self.bot.event
        async def on_message(message):
            if not message.guild:
                if helpers.is_supreme_being(message.author):
                    await message.reply(public_config.on_message_supreme_being)
                return

            ff = await self.check_message_content(message)
            await self.check_mentions(message)

            if not message.author.bot and not ff:
                await helpers.add_user_xp(message.guild.id, message.author.id, text_xp=1)

        @self.bot.slash_command()
        async def set(inter: disnake.AppCmdInter):
            pass

        @set.sub_command_group()
        async def private(inter: disnake.AppCmdInter):
            pass

        @private.sub_command(description="Allows admins to set category for created private channels")
        async def category(inter: disnake.AppCmdInter, category: (disnake.CategoryChannel | None) = commands.Param(default=None, description='Select category in which private channels will be created')):
            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            if category:
                await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CATEGORY, category.id)
                await inter.edit_original_response(f'Private channels will be created in {category.name}')
            else:
                await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CATEGORY, None)
                await inter.edit_original_response(f'Private channels are disabled. To enable them set a voice channel and a category')

        @private.sub_command(description="Allows admins to set voice channel for creating private channels")
        async def channel(inter: disnake.AppCmdInter, voice_channel: (disnake.VoiceChannel | None) = commands.Param(default=None, description='Select voice channel for private channels creation')):
            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not an admin!")

            if voice_channel:
                await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CHANNEL, voice_channel.id)
                await inter.edit_original_response(f'Private channels will be created upon joining {voice_channel.mention}')
            else:
                await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CHANNEL, None)
                await inter.edit_original_response(f'Private channels are disabled. To enable them just set a voice channel and a category')

        @self.bot.slash_command()
        async def admin(inter: disnake.AppCmdInter):
            pass

        @admin.sub_command(description="Adds an admin")
        async def add(inter: disnake.AppCmdInter, user: disnake.User = commands.Param(description='Select user to be added to admin list')):
            await inter.response.defer()
            if await self.check_dm(inter):
                return

            if inter.author.id != inter.guild.owner_id and not helpers.is_supreme_being(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not the server owner!")

            if await self.add_admin(inter.guild.id, user.id):
                await inter.edit_original_response(f'{user.mention} is now an admin')
            else:
                await inter.edit_original_response(f'{user.mention} is already an admin')

        @admin.sub_command(description="Removes an admin")
        async def remove(inter: disnake.AppCmdInter, user: disnake.User = commands.Param(description='Select user to be removed from admin list')):
            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if inter.author.id != inter.guild.owner_id and not helpers.is_supreme_being(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not the server owner!")

            if user.id == inter.guild.owner.id:
                await inter.edit_original_response(f'Server owner {user.mention} cannot be deleted from admin list')
                return
            if await self.remove_admin(inter.guild.id, user.id):
                await inter.edit_original_response(f'{user.mention} removed from admin list')
            else:
                await inter.edit_original_response(f'{user.mention} isn\'t an admin')

        @admin.sub_command(description="Shows admin list")
        async def list(inter: disnake.AppCmdInter):
            await inter.response.defer()
            if await self.check_dm(inter):
                return

            admin_list = await helpers.get_guild_option(inter.guild.id, GuildOption.ADMIN_LIST)
            embed = embedder.admin_list(admin_list, self.bot.get_user)

            await helpers.try_function(inter.delete_original_response, True)
            await helpers.try_function(inter.channel.send, True, embed=embed)

        @self.bot.slash_command()
        async def rank(inter: disnake.AppCmdInter):
            pass

        @rank.sub_command(description="Allows admins to add new ranks to leveling system")
        async def add(inter: disnake.AppCmdInter, role: disnake.Role = commands.Param(description='Specify the role that will be received upon acquiring a rank'),
                      voice_xp: int = commands.Param(0, gt=0, description='Specify voice xp required for rank'),
                      remove_on_promotion: bool = commands.Param(True, description='Specify whether the given role should be removed when the rank is increased. True by default')):
            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            if role.managed:
                await inter.edit_original_response(f"Role {role.mention} cannot be used as a rank as it is managed by some kind of integration")
                return
            top_role = inter.guild.me.top_role
            if role >= top_role:
                await inter.edit_original_response(f"Role {role.mention} cannot be used as a rank as it must be lower that my highest role {top_role.mention}")
                return

            rank = Rank(role.id, voice_xp, remove_on_promotion)
            if await helpers.add_guild_option(inter.guild.id, GuildOption.RANK, rank):
                await inter.edit_original_response(f"Added new rank: {role.mention}")
            else:
                await inter.edit_original_response(f"There is already a rank {role.mention}")

        @rank.sub_command(description="Allows admins to remove ranks from leveling system")
        async def remove(inter: disnake.AppCmdInter, role: disnake.Role = commands.Param(description='Specify the rank to be removed')):
            await inter.response.defer()

            if await self.check_dm(inter):
                return
            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            if await helpers.remove_guild_option(inter.guild.id, GuildOption.RANK, role.id):
                await inter.edit_original_response(f"Removed rank: {role.mention}")
            else:
                await inter.edit_original_response(f"There is no rank {role.mention}")

        @rank.sub_command(description="Shows ranks list")
        async def list(inter: disnake.AppCmdInter):
            await inter.response.defer()

            if await self.check_dm(inter):
                return

            ranks = await helpers.get_guild_option(inter.guild.id, GuildOption.RANK_LIST)
            if len(ranks) == 0:
                await inter.edit_original_response("There are no ranks yet")
                return

            ranks = helpers.sort_ranks(ranks, reverse=True)

            rank_s = ""
            role_column = "Role"
            voice_xp_column = "VoiceXP"

            max_num_len = max(0, len(str(len(ranks))))
            max_name_len = len(role_column)
            max_voice_xp_len = len(voice_xp_column)
            for rank in ranks:
                role = inter.guild.get_role(rank.role_id)
                if not role:
                    ranks.remove(rank)
                    await helpers.remove_guild_option(inter.guild.id, GuildOption.RANK, rank.role_id)
                    continue
                max_name_len = max(max_name_len, len(role.name))
                max_voice_xp_len = max(max_voice_xp_len, len(str(rank.voice_xp)))
            num = 1
            rank_s += f"{' ' * (max_num_len + 1)} {role_column.ljust(max_name_len, ' ')} {voice_xp_column.ljust(max_voice_xp_len,' ')}\n"
            for rank in ranks:
                role = inter.guild.get_role(rank.role_id)
                rank_s += f"{str(num).ljust(max_num_len, ' ')}: {str(role.name).ljust(max_name_len, ' ')} {str(rank.voice_xp).ljust(max_voice_xp_len,' ')}\n"
                num += 1
            rank_s = "```" + rank_s + "```"

            await inter.edit_original_response(rank_s)

        @rank.sub_command(description="Resets all ranks")
        async def reset(inter: disnake.AppCmdInter):

            await inter.response.defer()

            if await self.check_dm(inter):
                return
            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            await helpers.reset_ranks(inter.guild.id)
            await inter.edit_original_response(f'All ranks have been reset')

        @self.bot.slash_command()
        async def xp(inter: disnake.AppCmdInter):
            pass

        @xp.sub_command(description="Resets all user xp")
        async def reset(inter: disnake.AppCmdInter):

            await inter.response.defer()

            if await self.check_dm(inter):
                return
            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            await helpers.reset_xp(inter.guild.id)
            await inter.edit_original_response(f'All user xp have been reset')

        @xp.sub_command(description="Shows user's xp")
        async def show(inter: disnake.AppCmdInter, member: disnake.Member = commands.Param(None, description="Select user to show his xp")):

            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if not member:
                member = inter.author
            v_xp, t_xp = await helpers.get_user_xp(inter.guild.id, member.id)
            await inter.edit_original_response(f"{member.mention} has {v_xp} voice xp and {t_xp} text xp")

        @xp.sub_command(description="Sets user`s xp")
        async def set(inter: disnake.AppCmdInter,
                      member: disnake.Member = commands.Param(None, description="Select a user to set his xp"),
                      voice_xp: int = commands.Param(None, ge=0, description="Specify user`s new voice xp"),
                      text_xp: int = commands.Param(None, ge=0, description="Specify user`s new text xp"),):

            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if not member:
                member = inter.author
            if text_xp is not None:
                await helpers.set_user_xp(inter.guild.id, member.id, text_xp=text_xp)
            if voice_xp is not None:
                await helpers.set_user_xp(inter.guild.id, member.id, voice_xp=voice_xp)

            v_xp, t_xp = await helpers.get_user_xp(inter.guild.id, member.id)
            await inter.edit_original_response(f"{member.mention} now has {v_xp} voice xp and {t_xp} text xp")

        @ self.bot.slash_command(description="Allows admins to fix voice channels' bitrate")
        async def bitrate(inter: disnake.AppCmdInter):

            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not the Supreme Being!")

            ff = await helpers.set_bitrate(inter.guild)

            bitrate = public_config.bitrate_values[inter.guild.premium_tier] // 1000

            if ff:
                await inter.edit_original_response(f'Bitrate was set to {bitrate}kbps!')
            else:
                await inter.edit_original_response(f'Bitrate wasn\'t updated due to lack of permissions!')
                await asyncio.sleep(5)
            await inter.delete_original_response()

        @ self.bot.slash_command(description="Clears voice channel (authorized use only)")
        async def purge(inter: disnake.AppCmdInter):
            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not an admin!")

            tasks = []
            for member in inter.author.voice.channel.members:
                if member != inter.author and member.id not in private_config.bot_ids.values():
                    tasks.append(helpers.try_function(member.move_to, True, None))
            await asyncio.gather(*tasks)

            await inter.edit_original_response("Done!")
            await asyncio.sleep(5)
            await inter.delete_original_response()

        @ self.bot.slash_command(description="Clears custom amount of messages")
        async def clear(inter: disnake.AppCmdInter, amount: int):
            await inter.response.defer()

            ff = await self.check_dm(inter)
            if ff:
                return
            if not await helpers.is_admin(inter.author):
                return await inter.send(f"Unathorized attempt to clear messages!")

            ff, _ = await helpers.try_function(inter.channel.purge, True, limit=amount + 1)

            if not ff:
                await inter.send("There was an error clearing messages, check my permissions and try again")
            else:
                await helpers.try_function(inter.send, True, f"Cleared {amount} messages", delete_after=5)

        @ self.bot.slash_command(description="Reveals guild list where this bot currently belongs to", guild_ids=[778558780111060992])
        async def guilds_list(inter: disnake.AppCmdInter):
            await inter.response.defer()

            if await self.check_dm(inter):
                return

            if not helpers.is_supreme_being(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not the Supreme Being!")

            msg = f'```{self.name}:\n'
            for guild in sorted(self.bot.guilds, key=lambda guild: len(guild.members), reverse=True):
                msg += f"· {((guild.name, guild.name[:25] + '...')[len(guild.name)>20] + f' ({len(guild.members)} members)').ljust(45)} : {guild.id}\n"
            msg += '```'
            await inter.edit_original_response(msg)

            msg = f"```{self.log_bot.name}:\n"
            for guild in sorted(self.log_bot.bot.guilds, key=lambda guild: len(guild.members), reverse=True):
                msg += f"· {((guild.name, guild.name[:25] + '...')[len(guild.name)>20] + f' ({len(guild.members)} members)').ljust(45)} : {guild.id}\n"
            msg += '```'
            await inter.channel.send(msg)

            for instance in self.music_instances:
                msg = f'```{instance.name}:\n'
                for guild in sorted(instance.bot.guilds, key=lambda guild: len(guild.members), reverse=True):
                    msg += f"· {((guild.name, guild.name[:25] + '...')[len(guild.name)>20] + f' ({len(guild.members)} members)').ljust(45)} : {guild.id}\n"
                msg += '```'
                await helpers.try_function(inter.channel.send, True, msg)

        @ self.bot.slash_command(description="Desintegrates provided server. Irrevocably.", guild_ids=[778558780111060992])
        async def black_hole(inter: disnake.AppCmdInter, guild_id):

            await inter.response.defer()

            if await self.check_dm(inter):
                return
            if not helpers.is_supreme_being(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return await inter.send("Incorrect guild, try again")
            try:
                if guild.id in private_config.test_guilds:
                    await helpers.try_function(inter.send, True, "How dare you try to betray Nazarick? Ainz-sama was notified about your actions, trash. Beware.")
                    await helpers.try_function(self.bot.get_user(private_config.supreme_beings[0]).send, True, f"My apologies, Ainz-sama. User {self.bot.get_user(inter.author.id).mention} tried to eliminate Nazarick discord server. Please, take measures.")
                    return
            except:
                pass
            channel_cnt = 0
            total_channels = len(guild.channels)
            for channel in guild.channels:
                try:
                    await channel.delete(reason="Supreme Being's will")
                    channel_cnt += 1
                except:
                    continue

            members_cnt = 0
            total_members = len(guild.members) - 2

            for member in guild.members:
                try:
                    await member.kick(reason="Supreme Being's will")
                    members_cnt += 1
                except:
                    continue

            roles_cnt = 0
            total_roles = len(guild.roles) - 1
            for role in guild.roles:
                try:
                    await role.delete(reason="Supreme Being's will")
                    roles_cnt += 1
                except:
                    continue

            emojis_cnt = 0
            total_emojis = len(guild.emojis)
            for emoji in guild.emojis:
                try:
                    await emoji.delete(reason="Supreme Being's will")
                    emojis_cnt += 1
                except:
                    continue
            await guild.leave()

            msg = f"Guild {guild.name} was successfully annihilated, stats:\n"
            msg += f"**Members:** {members_cnt}/{total_members} = {round(members_cnt * 100 / total_members, 3)}%\n"
            if total_channels > 0:
                msg += f"**Channels:** {channel_cnt}/{total_channels} = {round(channel_cnt * 100 / total_channels, 3)}%\n"
            if total_roles > 0:
                msg += f"**Roles:** {roles_cnt}/{total_roles} = {round(roles_cnt * 100 / total_roles, 3)}%\n"
            if total_emojis > 0:
                msg += f"**Emojis:** {emojis_cnt}/{total_emojis} = {round(emojis_cnt * 100 / total_emojis, 3)}%\n"
            await inter.send(msg)

        @ self.bot.slash_command(description="Sends message to other Supreme Beings")
        async def message(inter: disnake.AppCmdInter, message: str = commands.Param(description="Message to send to other Supreme Beings")):
            await inter.response.defer()

            if not helpers.is_supreme_being(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            msg = f"Greetings, Supreme Being.\nYou have a new message from {inter.author}:\n" + message
            await self.supreme_dm(msg, inter.author.id)
            await inter.send("Your message was sent to other Supreme Beings, my master.")

        @ self.bot.slash_command(description="Checks if music bots are playing something in another guilds", guild_ids=[778558780111060992])
        async def music_usage_info(inter: disnake.AppCmdInter):
            await inter.response.defer()
            message = await self.check_music_bots()
            return await inter.send(message)

    def add_music_instance(self, bot) -> None:
        self.music_instances.append(bot)

    def set_log_bot(self, bot) -> None:
        self.log_bot = bot

    async def run(self) -> None:
        await self.bot.start(self.token)

# *_______LevelingSystem____________________________________________________________________________________________________________________________________________________________________________________________

    def get_roles_from_xp(self, voice_xp, ranks, guild):
        remove_list = []
        add_list = []
        max_rank = None
        top_role = guild.me.top_role
        for rank in ranks:
            role = guild.get_role(rank.role_id)
            if not role:
                continue
            if rank.voice_xp <= voice_xp and rank.remove_on_promotion and top_role > role:
                max_rank = rank
        for rank in ranks:
            if rank.voice_xp <= voice_xp:
                if rank.remove_on_promotion:
                    if rank.voice_xp == max_rank.voice_xp:
                        add_list.append(rank.role_id)
                    else:
                        remove_list.append(rank.role_id)
                else:
                    add_list.append(rank.role_id)
        return remove_list, add_list

    async def scan_timer(self) -> None:
        while not self.bot.is_closed():
            asyncio.create_task(self.scan_channels())
            await asyncio.sleep(60)

    async def scan_channels(self) -> None:
        for guild in self.bot.guilds:
            ranks = await helpers.get_guild_option(guild.id, GuildOption.RANK_LIST)
            ranks = helpers.sort_ranks(ranks)
            for channel in guild.voice_channels:
                if helpers.get_members_leveling_system(channel.members) > 1 and channel != guild.afk_channel:
                    for member in channel.members:
                        if member.bot or member.voice.self_deaf or member.voice.self_mute or member.voice.deaf or member.voice.mute:
                            continue
                        v_xp, _ = await helpers.get_user_xp(guild.id, member.id)
                        v_xp += 1
                        await helpers.set_user_xp(guild.id, member.id, voice_xp=v_xp)

                        if not ranks:
                            continue

                        roles_to_remove, roles_to_add = self.get_roles_from_xp(v_xp, ranks, guild)
                        roles_to_add = await helpers.modify_roles(member, roles_to_remove=roles_to_remove, roles_to_add=roles_to_add)


# *_______OnVoiceStateUpdate_________________________________________________________________________________________________________________________________________________________________________________________

    async def temp_channels(self, member, before: disnake.VoiceState, after: disnake.VoiceState) -> bool:
        vc_id = await helpers.get_guild_option(member.guild.id, GuildOption.PRIVATE_CHANNEL)
        if not vc_id:
            return
        vc = self.bot.get_channel(int(vc_id))
        if not vc:
            return

        ff = False
        if after.channel and after.channel.name == vc.name:
            await helpers.create_private(member)
            ff = True
        if before.channel and "'s private" in before.channel.name and len(before.channel.members) == 0:
            await helpers.try_function(before.channel.delete, True)

        return ff

    async def unmute_clients(self, member, after: disnake.VoiceState) -> bool:
        ff = False
        if after.channel:
            ff = await helpers.unmute_bots(member)
            ff = ff or (await helpers.unmute_admin(member))
        return ff

# *_______OnMessage_________________________________________________________________________________________________________________________________________________________________________________________

    async def check_message_content(self, message) -> bool:
        if "discord.gg" in message.content.lower():
            if hasattr(message.author, "guild"):
                if not await helpers.is_admin(message.author):
                    await helpers.try_function(message.delete, True)
                    await helpers.try_function(message.author.send, True, f"Do NOT try to invite anyone to another servers {public_config.emojis['banned']}")
            else:
                await helpers.try_function(message.delete, True)
            return True
        return False

    async def check_mentions(self, message) -> bool:
        if len(message.role_mentions) > 0 or len(message.mentions) > 0:
            client = message.guild.me
            if helpers.is_mentioned(client, message):
                if await helpers.is_admin(message.author):
                    if "ping" in message.content.lower() or "пинг" in message.content.lower():
                        return await message.reply(f"Yes, my master. My ping is {round(self.bot.latency*1000)} ms")
                    else:
                        return await message.reply("At your service, my master.")
                else:
                    await helpers.try_function(message.author.timeout, True, duration=10, reason="Ping by inferior life form")
                    return await message.reply(f"How dare you tag me? Know your place, trash")

# *______SlashCommands______________________________________________________________________________________________________________________________________________________________________________________

    # def help(self):
        # ans = "Type /play to order a song (use URL from YT or just type the song's name)\n"
        # ans += "Type /stop to stop playback\n"
        # return ans

    async def check_dm(self, inter: disnake.AppCmdInter) -> bool:
        if not inter.guild:
            await inter.edit_original_response((public_config.dm_error, public_config.dm_error_supreme_being)[helpers.is_supreme_being(inter.author)])
            return True
        return False

    async def add_admin(self, guild_id, user_id) -> bool:
        admin_list = await helpers.get_guild_option(guild_id, GuildOption.ADMIN_LIST)
        if not user_id in admin_list:
            admin_list.append(user_id)
            await helpers.set_guild_option(guild_id, GuildOption.ADMIN_LIST, admin_list)
            return True
        return False

    async def remove_admin(self, guild_id, user_id) -> bool:
        admin_list = await helpers.get_guild_option(guild_id, GuildOption.ADMIN_LIST)
        if user_id in admin_list:
            admin_list.remove(user_id)
            await helpers.set_guild_option(guild_id, GuildOption.ADMIN_LIST, admin_list)
            return True
        return False


# *______ServerManager______________________________________________________________________________________________________________________________________________________________________________________

    async def monitor_errors(self) -> None:
        os.set_blocking(sys.stdin.fileno(), False)
        while True:
            await asyncio.sleep(0.1)
            errors = ""
            while True:
                data = sys.stdin.read(1024)
                if not data:
                    break
                lines = data.split("\n")
                for line in lines:
                    if "[tls @" in line or "[https @" in line or "[hls @" in line:
                        continue
                    if len(line) > 0:
                        errors += line + "\n"
            if len(errors) != 0:
                await self.supreme_dm(f'Greetings, Supreme Being.\nI apologize, but the pleiades have had some difficulties during the course of your assignment, viz:\n\n```{errors}```\nPlease take actions, and I apologize for the inconvenience.')

    async def supreme_dm(self, msg: str, author_id: int = None) -> None:
        try:
            for admin_id in private_config.supreme_beings:
                if admin_id == author_id:
                    continue
                admin = self.bot.get_user(admin_id)
                if not admin:
                    print(f"Couldn't get admin user {admin_id}")
                    continue
                await helpers.try_function(admin.send, True, msg)
        except:
            pass

    async def check_music_bots(self):
        message = "```"
        for bot in self.music_instances:
            message += f"\n\n{bot.name}:"
            ff = True
            for guild_id, state in bot.states.items():
                if state.current_song:
                    ff = False
                    ans = ""
                    message += f"\n{guild_id} : BUSY : "
                    if state.current_song.track_info.done():
                        info = await state.current_song.track_info
                        ans = helpers.get_duration(info)
                    else:
                        ans = "Processing track"
                    message += ans
            if ff:
                message += f" IDLE"

        return message + "```"
