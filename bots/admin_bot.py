import disnake
from disnake.ext import commands
import asyncio
import sys
import os
import time

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers
import helpers.database_logger as database_logger
import helpers.embedder as embedder

from helpers.helpers import GuildOption, Rank
from helpers.view_panels import MessageForm, TopXP


class AdminBot():
    music_instances = None
    on_ready_flag = None
    log_bot = None
    bot = None
    name = None
    token = None

    def __init__(self, name: str, token: str):
        self.bot = commands.InteractionBot(intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="with the subordinates", type=disnake.ActivityType.playing))
        self.name = name
        self.token = token
        self.music_instances = []
        self.on_ready_flag = False

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
            if not self.on_ready_flag:
                await database_logger.enabled(self.bot)
                print(f"{self.name} is logged as {self.bot.user}")
                self.on_ready_flag = True
                self.bot.loop.create_task(self.scan_timer())
                self.bot.loop.create_task(self.scan_activity())
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
            if ff:
                return

            await helpers.check_mentions(message, self.bot)

            if not message.author.bot and not ff:
                await helpers.add_user_xp(message.guild.id, message.author.id, text_xp=1)

        @self.bot.slash_command(dm_permission=False)
        async def set(inter: disnake.AppCmdInter):
            pass

        @set.sub_command_group()
        async def private(inter: disnake.AppCmdInter):
            pass

        @private.sub_command(description="Allows admins to set category for created private channels")
        async def category(inter: disnake.AppCmdInter,
                           category: (disnake.CategoryChannel | None) = commands.Param(default=None, description='Select category in which private channels will be created')):
            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            if category:
                await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CATEGORY, category.id)
                await inter.edit_original_response(f'Private channels will be created in {category.name}')
            else:
                await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CATEGORY, None)
                await inter.edit_original_response(f'Private channels are disabled. To enable them set a voice channel and a category')

        @private.sub_command(description="Allows admins to set voice channel for creating private channels")
        async def channel(inter: disnake.AppCmdInter,
                          voice_channel: (disnake.VoiceChannel | None) = commands.Param(default=None, description='Select voice channel for private channels creation')):
            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not an admin!")

            if voice_channel:
                await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CHANNEL, voice_channel.id)
                await inter.edit_original_response(f'Private channels will be created upon joining {voice_channel.mention}')
            else:
                await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CHANNEL, None)
                await inter.edit_original_response(f'Private channels are disabled. To enable them just set a voice channel and a category')

        @self.bot.slash_command(dm_permission=False)
        async def admin(inter: disnake.AppCmdInter):
            pass

        @admin.sub_command(description="Adds an admin")
        async def add(inter: disnake.AppCmdInter,
                      user: disnake.User = commands.Param(description='Select user to be added to admin list')):
            await inter.response.defer()

            if inter.author.id != inter.guild.owner_id and not helpers.is_supreme_being(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not the server owner!")

            if await self.add_admin(inter.guild.id, user.id):
                await inter.edit_original_response(f'{user.mention} is now an admin')
            else:
                await inter.edit_original_response(f'{user.mention} is already an admin')

        @admin.sub_command(description="Removes an admin")
        async def remove(inter: disnake.AppCmdInter,
                         user: disnake.User = commands.Param(description='Select user to be removed from admin list')):
            await inter.response.defer()

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

            admin_list = await helpers.get_guild_option(inter.guild.id, GuildOption.ADMIN_LIST)
            embed = embedder.admin_list(admin_list, self.bot.get_user, inter.guild)

            await helpers.try_function(inter.delete_original_response, True)
            await helpers.try_function(inter.channel.send, True, embed=embed)

        @self.bot.slash_command(dm_permission=False)
        async def rank(inter: disnake.AppCmdInter):
            pass

        @rank.sub_command(description="Allows admins to add new ranks to leveling system")
        async def add(inter: disnake.AppCmdInter,
                      role: disnake.Role = commands.Param(description='Specify the role that will be received upon acquiring a rank'),
                      voice_xp: int = commands.Param(gt=0, description='Specify voice xp required for rank'),
                      remove_on_promotion: bool = commands.Param(default=True, description='Specify whether the given role should be removed when the rank is increased. True by default')):
            await inter.response.defer()

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
        async def remove(inter: disnake.AppCmdInter,
                         role: disnake.Role = commands.Param(description='Specify the rank to be removed')):
            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            if await helpers.remove_guild_option(inter.guild.id, GuildOption.RANK, role.id):
                await inter.edit_original_response(f"Removed rank: {role.mention}")
            else:
                await inter.edit_original_response(f"There is no rank {role.mention}")

        @rank.sub_command(description="Shows ranks list")
        async def list(inter: disnake.AppCmdInter):
            await inter.response.defer()

            ranks = await helpers.get_guild_option(inter.guild.id, GuildOption.RANK_LIST)
            if len(ranks) == 0:
                await inter.edit_original_response("There are no ranks yet")
                return
            ranks = helpers.sort_ranks(ranks, reverse=True)

            for rank in ranks:
                role = inter.guild.get_role(rank.role_id)
                if not role:
                    ranks.remove(rank)
                    await helpers.remove_guild_option(inter.guild.id, GuildOption.RANK, rank.role_id)
                    continue

            embed = embedder.rank_list(ranks, inter.guild)
            await inter.send(embed=embed)

        @rank.sub_command(description="Resets all ranks")
        async def reset(inter: disnake.AppCmdInter):
            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            await helpers.reset_ranks(inter.guild.id)
            await inter.edit_original_response(f'All ranks have been reset')

        @self.bot.slash_command(dm_permission=False)
        async def xp(inter: disnake.AppCmdInter):
            pass

        @xp.sub_command(description="Resets all user xp")
        async def reset(inter: disnake.AppCmdInter):

            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not an admin!")

            await helpers.reset_xp(inter.guild.id)
            await inter.edit_original_response(f'All user xp have been reset')

        @xp.sub_command(description="Shows user's xp")
        async def show(inter: disnake.AppCmdInter,
                       member: disnake.Member = commands.Param(description="Select user to show his xp")):

            await inter.response.defer()

            v_xp, t_xp = await helpers.get_user_xp(inter.guild.id, member.id)
            user_info = [member.id, v_xp, t_xp]
            curr_rank, next_rank = await helpers.get_next_rank(member)
            if not next_rank:
                next_role = None
                required_xp = None
            else:
                next_role = inter.guild.get_role(next_rank.role_id)
                required_xp = next_rank.voice_xp - v_xp
            if not curr_rank:
                curr_role = None
            else:
                curr_role = inter.guild.get_role(curr_rank.role_id)
            embed = embedder.xp_show(member, user_info, curr_role, next_role, required_xp)
            await inter.send(embed=embed)

        @xp.sub_command(description="Shows server's top XP users")
        async def top(inter: disnake.AppCmdInter, type: str = commands.Param(description="Specify the type of server top", choices=["Voice", "Text"])):
            await inter.response.defer()

            guild_top = await helpers.get_guild_top(inter.guild.id, (False, True)[type == "Voice"])
            v_xp, t_xp = await helpers.get_user_xp(inter.guild.id, inter.author.id)
            author_info = [inter.author.id, v_xp, t_xp]
            top_list = TopXP(guild_top, inter, author_info, self.bot, (False, True)[type == "Voice"])
            embed = embedder.xp_top(inter.guild, guild_top, 0, author_info, self.bot.get_user, (False, True)[type == "Voice"])
            await helpers.try_function(inter.delete_original_response, True)
            await top_list.send(embed=embed)

        @xp.sub_command(description="Sets user`s xp")
        async def set(inter: disnake.AppCmdInter,
                      member: disnake.Member = commands.Param(description="Select a user to set his xp"),
                      type: str = commands.Param(description="Specify the type of granted xp", choices=["Voice", "Text"]),
                      xp: int = commands.Param(ge=0, description="Specify user`s new voice xp")):

            await inter.response.defer()

            if type == "Text":
                await helpers.set_user_xp(inter.guild.id, member.id, text_xp=xp)
            else:
                await helpers.set_user_xp(inter.guild.id, member.id, voice_xp=xp)

            v_xp, t_xp = await helpers.get_user_xp(inter.guild.id, member.id)
            await inter.edit_original_response(f"{member.mention} now has {v_xp} voice xp and {t_xp} text xp")

        @ self.bot.slash_command(dm_permission=False, description="Allows admins to fix voice channels' bitrate")
        async def bitrate(inter: disnake.AppCmdInter):
            await inter.response.defer()

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

        @ self.bot.slash_command(dm_permission=False, description="Clears voice channel (authorized use only)")
        async def purge(inter: disnake.AppCmdInter):
            await inter.response.defer()

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

        @ self.bot.slash_command(dm_permission=False, description="Clears custom amount of messages")
        async def clear(inter: disnake.AppCmdInter,
                        amount: int = commands.Param(description="The number of messages to clear")):
            await inter.response.defer()

            if not await helpers.is_admin(inter.author):
                return await inter.send(f"Unathorized attempt to clear messages!")

            ff, _ = await helpers.try_function(inter.channel.purge, True, limit=amount + 1)

            if not ff:
                await inter.send("There was an error clearing messages, check my permissions and try again")
            else:
                await helpers.try_function(inter.send, True, f"Cleared {amount} messages", delete_after=5)

        @ self.bot.slash_command(dm_permission=False, description="Reveals guild list where this bot currently belongs to", guild_ids=[778558780111060992])
        async def guilds_list(inter: disnake.AppCmdInter):
            await inter.response.defer()

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

        @ self.bot.slash_command(dm_permission=False, description="Desintegrates provided server. Irrevocably.", guild_ids=[778558780111060992])
        async def black_hole(inter: disnake.AppCmdInter,
                             guild_id: str = commands.Param(description="ID of the guild to be eliminated")):
            await inter.response.defer()

            if not helpers.is_supreme_being(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            bots = [self.bot, self.log_bot.bot]
            for music_instance in self.music_instances:
                bots.append(music_instance.bot)
            guild = None
            for bot in bots:
                guild = bot.get_guild(int(guild_id))
                if guild:
                    break
            else:
                return await inter.send("Incorrect guild!")

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

        @ self.bot.slash_command(dm_permission=False, description="Returns guild info", guild_ids=[778558780111060992])
        async def get_guild_info(inter: disnake.AppCmdInter,
                                 guild_id: str = commands.Param(description="ID of the required guild")):
            await inter.response.defer()

            bots = [self.bot, self.log_bot.bot]
            for music_instance in self.music_instances:
                bots.append(music_instance.bot)
            guild = None
            for bot in bots:
                guild = bot.get_guild(int(guild_id))
                if guild:
                    break
            else:
                return await inter.send("Incorrect guild!")

            embed = await self.get_guild_info(guild, bots)

            await inter.send(embed=embed)

        @ self.bot.slash_command(dm_permission=False, description="Returns guild info", guild_ids=[778558780111060992])
        async def find_user(inter: disnake.AppCmdInter, user_id: str = commands.Param(description="ID of the user")):
            await inter.response.defer()

            bots = [self.bot, self.log_bot.bot]
            for music_instance in self.music_instances:
                bots.append(music_instance.bot)

            desired_guild = None
            user_id = int(user_id)
            for bot in bots:
                if desired_guild:
                    break

                for guild in bot.guilds:
                    if desired_guild:
                        break

                    for channel in guild.voice_channels:
                        if desired_guild:
                            break
                        if len(channel.members) == 0:
                            continue

                        for member in channel.members:
                            if member.id == user_id:
                                desired_guild = guild
                                break
            else:
                return await inter.send("Provided user was not found!")

            embed = await self.get_guild_info(desired_guild, bots)
            await inter.send(embed=embed)

        @ self.bot.slash_command(dm_permission=False, description="Moves provided user to provided channel", guild_ids=[778558780111060992])
        async def move_user(inter: disnake.AppCmdInter, guild_id: str = commands.Param(description="Target guild ID"), channel_id: str = commands.Param(description="Target voice channel ID"), user_id: str = commands.Param(default=None, description="ID of the user")):
            await inter.response.defer()

            bots = [self.bot, self.log_bot.bot]
            for music_instance in self.music_instances:
                bots.append(music_instance.bot)

            desired_bot, guild = None, None
            if not user_id:
                user_id = inter.author.id
            else:
                user_id = int(user_id)
            guild_id = int(guild_id)

            for bot in bots:
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue

                if guild.me.guild_permissions.move_members:
                    desired_bot = bot
                    break
            else:
                return await inter.send("Incorrect guild or lack of move members permission!")

            target_member = None
            for channel in guild.voice_channels:
                if len(channel.members) == 0:
                    continue

                for member in channel.members:
                    if member.id == user_id:
                        target_member = member
                        break

                if target_member:
                    break
            else:
                return await inter.send("Provided user was not found in any voice channel!")

            target_channel = guild.get_channel(int(channel_id))

            if not target_channel:
                return await inter.send("Incorrect channel ID!")

            await helpers.try_function(target_member.move_to, True, target_channel)

            await inter.send("The user has been moved successfully, my master.", delete_after=5)

        @ self.bot.slash_command(description="Sends message to other Supreme Beings")
        async def message(inter: disnake.AppCmdInter):
            # await inter.response.defer()

            if not helpers.is_supreme_being(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.response.send_modal(MessageForm())
            modal_inter = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.author.id == inter.author.id,
                timeout=3600)
            message = modal_inter.data.components[0]['components'][0]['value']
            msg = f"Greetings, Supreme Being.\nYou have a new message from {inter.author}:\n" + message
            await self.supreme_dm(msg, inter.author.id)

        @ self.bot.slash_command(dm_permission=False, description="Checks if music bots are playing something in another guilds", guild_ids=[778558780111060992])
        async def music_usage_info(inter: disnake.AppCmdInter):
            await inter.response.defer()
            message = await self.check_music_bots()
            return await inter.send(message)

        @ self.bot.slash_command(dm_permission=False, description="Sends DM to provided user", guild_ids=[778558780111060992])
        async def dm_user(inter: disnake.AppCmdInter,
                          user_id: str = commands.Param(description="User's id")):
            await inter.response.send_modal(MessageForm(title="Message to a user", response="Your message was sent to the provided user, my master."))

            modal_inter = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.author.id == inter.author.id,
                timeout=3600)

            message = modal_inter.data.components[0]['components'][0]['value']
            msg = f"Greetings.\nYou have a new message from Supreme Being {inter.author}:\n" + message
            await helpers.dm_user(msg, int(user_id), self.bot)

        @ self.bot.slash_command(dm_permission=False, description="Summons user to provided channel (check provided url twice)", guild_ids=[778558780111060992])
        async def summon_user(inter: disnake.AppCmdInter,
                              channel_link: str = commands.Param(description="Link to the target channel"),
                              user_id: str = commands.Param(description="User's id"),
                              user2_id: str = commands.Param(default=None, description="2nd user's id"),
                              user3_id: str = commands.Param(default=None, description="3rd user's id")):
            await inter.response.defer()

            message = f'Greetings.\n**The Great One** would like to speak with you in {channel_link}.\nPlease, be thankful for the attention and proceed to the mentioned channel as soon as possible.'
            errors = ""

            if not await helpers.dm_user(message, int(user_id), self.bot, suppress_embeds=True):
                errors += f"{user_id}"
            if user2_id is not None:
                if not await helpers.dm_user(message, int(user2_id), self.bot, suppress_embeds=True):
                    errors += f", {user2_id}"
            if user3_id is not None:
                if not await helpers.dm_user(message, int(user3_id), self.bot, suppress_embeds=True):
                    errors += f", {user3_id}"

            if len(errors) == 0:
                await inter.send(f"The {('user was', 'users were')[bool(user2_id is not None or user3_id is not None)]} notified successfully, my master.")
            else:
                await inter.send(f"Couldn't send message to `{errors}`, my master.")

        @ self.bot.slash_command(dm_permission=False, description="Manages user in the untouchables list", guild_ids=[778558780111060992])
        async def manage_untouchable(inter: disnake.AppCmdInter,
                                     user_id: str = commands.Param(description="User's id"),
                                     guild_id: str = commands.Param(description="Guild's id"),
                                     type: str = commands.Param(description="Choose the action", choices=["Add", "Remove"])):
            await inter.response.defer()

            if not helpers.is_supreme_being(inter.author):
                return await inter.edit_original_response("Unauthorized access, you are not the Supreme Being!")

            user_id = int(user_id)
            guild_id = int(guild_id)

            if type == "Add":
                if await self.add_untouchable(guild_id, user_id):
                    await inter.edit_original_response(f'{user_id} is now an untouchable user in guild {guild_id}')
                else:
                    await inter.edit_original_response(f'{user_id} is already an untouchable user in guild {guild_id}')
            else:
                if await self.remove_untouchable(guild_id, user_id):
                    await inter.edit_original_response(f'{user_id} is no longer an untouchable user in guild {guild_id}')
                else:
                    await inter.edit_original_response(f'{user_id} wasn\'t an untouchable user in guild {guild_id}')

        @ self.bot.slash_command(description="Reviews list of commands")
        async def help(inter: disnake.AppCmdInter):
            await inter.response.defer()
            await inter.send(embed=disnake.Embed(color=0, description=self.help()))

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

    async def scan_activity(self) -> None:
        while True:
            timestamp = int(time.time())
            guilds_ranks = {}
            activity_info = await helpers.get_activity_info()
            for row in activity_info:
                guild = self.bot.get_guild(row['guild_id'])
                if not guild:
                    continue
                member = guild.get_member(row['user_id'])
                if not member:
                    continue

                if guild.id not in guilds_ranks.keys():
                    guilds_ranks[guild.id] = await helpers.get_guild_option(guild.id, GuildOption.RANK_LIST)                    

                last_activity = row['last_activity']
                if timestamp - last_activity >= 5_184_000:
                    roles_to_remove = []
                    for role in member.roles:
                        if any(rank.role_id == role.id for rank in guilds_ranks[guild.id]):
                            roles_to_remove.append(role)
                    if roles_to_remove:
                        asyncio.create_task(helpers.try_function(member.remove_roles, True, *roles_to_remove))

            await asyncio.sleep(86400)

    async def scan_timer(self) -> None:
        while True:
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
                        await helpers.modify_roles(member, roles_to_remove=roles_to_remove, roles_to_add=roles_to_add)


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


# *______SlashCommands______________________________________________________________________________________________________________________________________________________________________________________


    async def get_guild_info(self, guild: disnake.Guild, bots: list) -> disnake.Embed:
        invites = None
        for bot in bots:
            tmp_guild = bot.get_guild(guild.id)
            if not tmp_guild:
                continue
            required_bot = bot
            _, vanity_invite = await helpers.try_function(tmp_guild.vanity_invite, True)
            ff, invites = await helpers.try_function(tmp_guild.invites, True)
            if ff:
                required_bot = bot
                break

        return embedder.guild_info(guild, required_bot, invites, vanity_invite)

    async def add_admin(self, guild_id: int, user_id: int) -> bool:
        admin_list = await helpers.get_guild_option(guild_id, GuildOption.ADMIN_LIST)
        if not user_id in admin_list:
            admin_list.append(user_id)
            await helpers.set_guild_option(guild_id, GuildOption.ADMIN_LIST, admin_list)
            return True
        return False

    async def remove_admin(self, guild_id: int, user_id: int) -> bool:
        admin_list = await helpers.get_guild_option(guild_id, GuildOption.ADMIN_LIST)
        if user_id in admin_list:
            admin_list.remove(user_id)
            await helpers.set_guild_option(guild_id, GuildOption.ADMIN_LIST, admin_list)
            return True
        return False

    async def add_untouchable(self, guild_id: int, user_id: int) -> bool:
        untouchables_list = await helpers.get_guild_option(guild_id, GuildOption.UNTOUCHABLES_LIST)
        if not user_id in untouchables_list:
            untouchables_list.append(user_id)
            await helpers.set_guild_option(guild_id, GuildOption.UNTOUCHABLES_LIST, untouchables_list)
            return True
        return False

    async def remove_untouchable(self, guild_id: int, user_id: int) -> bool:
        untouchables_list = await helpers.get_guild_option(guild_id, GuildOption.UNTOUCHABLES_LIST)
        if user_id in untouchables_list:
            untouchables_list.remove(user_id)
            await helpers.set_guild_option(guild_id, GuildOption.UNTOUCHABLES_LIST, untouchables_list)
            return True
        return False

    def help(self) -> str:
        ans = "All commands can be used only by admins\n"
        ans += "Type **/admin add** to add a new server admin (can be used only by server owner)\n"
        ans += "Type **/admin remove** to remove an admin (can be used only by server owner)\n"
        ans += "Type **/admin list** to show server admins list\n"
        ans += "Type **/clear** to clear a custom amount of messages\n"
        ans += "Type **/bitrate** to set all voice channels' bitrate to max\n"
        ans += "Type **/purge** to disconnect each user from voice channel except music bots and command author\n"
        ans += "Type **/xp show** to print user's voice and text xp\n"
        ans += "Type **/xp set** to pause/resume playback\n"
        ans += "Type **/xp reset** to reset all users' xp for this server\n"
        ans += "Type **/rank list** to print all ranks for this server\n"
        ans += "Type **/rank add** to add a new rank for this server\n"
        ans += "Type **/rank remove** to remove a rank from this server\n"
        ans += "Type **/rank reset** to reset all ranks for this server\n"
        ans += "Type **/set private channel** to set a channel to create a temporary channel on connection to\n"
        ans += "Type **/set private category** to set a category in which temporary channel will be created"
        return ans


# *______ServerManager______________________________________________________________________________________________________________________________________________________________________________________

    async def monitor_errors(self) -> None:
        try:
            os.set_blocking(sys.stdin.fileno(), False)
        except:
            return

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
                ff = await helpers.dm_user(msg, admin_id, self.bot)
                if not ff:
                    print(f"Couldn't send to admin with id {admin_id}")
        except:
            pass

    async def check_music_bots(self):
        message = "```"
        for bot in self.music_instances:
            message += f"\n\n{bot.name}:"
            ff = True
            for guild_id, state in bot.states.items():
                if state.current_song:
                    if ff:
                        message += " BUSY"
                        ff = False
                    ans = ""
                    message += f"\n{guild_id} : "
                    queue_duration = helpers.get_queue_duration(state.song_queue)
                    if state.current_song.track_info.done():
                        info = await state.current_song.track_info
                        ans = helpers.get_duration(info)
                    else:
                        ans = "Processing track"

                    if queue_duration:
                        ans += " and queue duration: " + queue_duration[20:]
                    message += ans
            if ff:
                message += f" IDLE"

        return message + "```"
