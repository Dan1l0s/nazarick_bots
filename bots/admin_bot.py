import disnake
from disnake.ext import commands
import asyncio
from enum import Enum

import configs.private_config as private_config
import configs.public_config as public_config
import helpers.helpers as helpers
from helpers.embedder import Embed
from helpers.helpers import GuildOption, Rank
import datetime


class AdminBot():
    music_instances = None
    log_bot = None

    def __init__(self, name, token, logger):
        self.bot = commands.InteractionBot(intents=disnake.Intents.all(
        ), activity=disnake.Activity(name="with the subordinates", type=disnake.ActivityType.playing))
        self.name = name
        self.token = token
        self.file_logger = logger
        self.embedder = Embed()
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

        @self.bot.event
        async def on_ready():
            self.file_logger.enabled(self.bot)
            print(f"{self.name} is logged as {self.bot.user}")
            self.bot.loop.create_task(self.scan_timer())
            for guild in self.bot.guilds:
                await self.add_admin(guild.id, guild.owner_id)

        @self.bot.event
        async def on_disconnect():
            print(f"{self.name} has disconnected from Discord")
            self.file_logger.lost_connection(self.bot)

        @self.bot.event
        async def on_connect():
            print(f"{self.name} has connected to Discord")
            # self.file_logger.lost_connection(self.bot)

        @self.bot.event
        async def on_message(message):
            if not message.guild:
                try:
                    if message.author.id in private_config.supreme_beings:
                        await message.reply(private_config.on_message_supreme_being)
                except:
                    pass
                return

            await self.check_message_content(message)
            await self.check_mentions(message)

        @self.bot.slash_command()
        async def set(inter):
            pass

        @set.sub_command_group()
        async def private(inter):
            pass

        @private.sub_command(description="Allows admin to set category for created private channels")
        async def category(inter, category: disnake.CategoryChannel = commands.Param(description='Select category in which private channels will be created')):
            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CATEGORY, category.id)
            await inter.edit_original_response(f'New private channels will be created in {category.name}')

        @private.sub_command(description="Allows admin to set voice channel for creating private channels")
        async def channel(inter, vc: disnake.VoiceChannel = commands.Param(description='Select voice channel for private channels creation')):
            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            await helpers.set_guild_option(inter.guild.id, GuildOption.PRIVATE_CHANNEL, vc.id)
            await inter.edit_original_response(f'Private channels will be created upon joining {vc.mention}')

        @self.bot.slash_command()
        async def admin(inter):
            pass

        @admin.sub_command(description="Adds admin")
        async def add(inter, user: disnake.User = commands.Param(description='Select user to be added to admin list')):
            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            if await self.add_admin(inter.guild.id, user.id):
                await inter.edit_original_response(f'{user.mention} is now admin')
            else:
                await inter.edit_original_response(f'{user.mention} is already admin')

        @admin.sub_command(description="Removes admin")
        async def remove(inter, user: disnake.User = commands.Param(description='Select user to be removed from admin list')):
            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            if user.id == inter.guild.owner.id:
                await inter.edit_original_response(f'Guild owner {user.mention} cannot be deleted from admin list')
                return
            if await self.remove_admin(inter.guild.id, user.id):
                await inter.edit_original_response(f'{user.mention} removed from admin list')
            else:
                await inter.edit_original_response(f'{user.mention} isn\'t admin')

        @admin.sub_command(description="Shows admin list")
        async def list(inter):
            if await self.check_dm(inter):
                return

            await inter.send("Processing...")
            admin_list = await helpers.get_guild_option(inter.guild.id, GuildOption.ADMIN_LIST)

            embed = disnake.Embed(
                color=disnake.Colour.from_rgb(
                    *public_config.embed_colors["voice_update"]),
                timestamp=datetime.datetime.now())
            admin_s = ""
            num = 1
            for admin in admin_list:
                user = self.bot.get_user(admin)
                if user:
                    admin_s += f"{num}: {user.mention}\n"
                    num += 1

            embed.add_field(name="Admin list:", value=admin_s, inline=False)

            await inter.delete_original_response()
            await inter.channel.send(embed=embed)

        @self.bot.slash_command()
        async def rank(inter):
            pass

        @rank.sub_command(description="Allows admin to add new ranks to leveling system")
        async def add(inter, role: disnake.Role = commands.Param(description='Specify the role that will be received upon acquiring a rank'),
                      voice_xp: int = commands.Param(0, gt=0, description='Specify voice xp required for rank'),
                      remove_on_promotion: bool = commands.Param(True, description='Specify whether the given role should be removed when the rank is increased. True by default')):
            if await self.check_dm(inter):
                return
            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
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

        @rank.sub_command(description="Allows admin to remove ranks from leveling system")
        async def remove(inter, role: disnake.Role = commands.Param(description='Specify the rank to be removed')):
            if await self.check_dm(inter):
                return
            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            if await helpers.remove_guild_option(inter.guild.id, GuildOption.RANK, role.id):
                await inter.edit_original_response(f"Removed rank: {role.mention}")
            else:
                await inter.edit_original_response(f"There is no rank {role.mention}")

        @rank.sub_command(description="Shows list of ranks")
        async def list(inter):
            if await self.check_dm(inter):
                return
            await inter.send("Processing...")

            ranks = await helpers.get_guild_option(inter.guild.id, GuildOption.RANK_LIST)
            if len(ranks) == 0:
                await inter.edit_original_response("There are no ranks yet")
                return

            ranks = helpers.sort_ranks(ranks, increasing=False)

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
        async def reset(inter):
            if await self.check_dm(inter):
                return
            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            await helpers.reset_ranks(inter.guild.id)
            await inter.edit_original_response(f'All ranks have been reset')

        @self.bot.slash_command()
        async def xp(inter):
            pass

        @xp.sub_command(description="Resets all user xp")
        async def reset(inter):
            if await self.check_dm(inter):
                return
            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")
            await helpers.reset_xp(inter.guild.id)
            await inter.edit_original_response(f'All user xp have been reset')

        @xp.sub_command(description="Shows user's xp")
        async def show(inter, member: disnake.Member = commands.Param(None, description="Select user to show his xp")):
            if await self.check_dm(inter):
                return
            await inter.send("Processing...")
            if not member:
                member = inter.author
            v_xp, t_xp = await helpers.get_user_xp(inter.guild.id, member.id)
            await inter.edit_original_response(f"{member.mention} has {v_xp} voice xp and {t_xp} text xp")

        @xp.sub_command(description="Sets user xp")
        async def set(inter,
                      member: disnake.Member = commands.Param(None, description="Select user to set his xp"),
                      voice_xp: int = commands.Param(None, ge=0, description="Specify users new voice xp"),
                      text_xp: int = commands.Param(None, ge=0, description="Specify users new text xp"),):
            if await self.check_dm(inter):
                return
            await inter.send("Processing...")
            if not member:
                member = inter.author
            if text_xp is not None:
                await helpers.set_user_xp(inter.guild.id, member.id, text_xp=text_xp)
            if voice_xp is not None:
                await helpers.set_user_xp(inter.guild.id, member.id, voice_xp=voice_xp)

            v_xp, t_xp = await helpers.get_user_xp(inter.guild.id, member.id)
            await inter.edit_original_response(f"{member.mention} now has {v_xp} voice xp and {t_xp} text xp")

        @ self.bot.slash_command(description="Allows admin to fix voice channels' bitrate")
        async def bitrate(inter):
            if await self.check_dm(inter):
                return

            if not await helpers.is_admin(inter.author):
                return await inter.send("Unauthorized access, you are not the Supreme Being!")

            await inter.send("Processing...")

            await helpers.set_bitrate(inter.guild)

            bitrate = public_config.bitrate_values[inter.guild.premium_tier] // 1000

            await inter.edit_original_response(f'Bitrate was set to {bitrate}kbps!')
            await asyncio.sleep(5)
            await inter.delete_original_response()

        @ self.bot.slash_command(description="Clears voice channel (authorized use only)")
        async def purge(inter):
            if await self.check_dm(inter):
                return
            if inter.author.id != inter.guild.owner_id:
                return await inter.send("Unauthorized access, you are not the Greatest Supreme Being!")
            tasks = []
            for member in inter.author.voice.channel.members:
                if member != inter.author and member.id not in private_config.bot_ids.values():
                    tasks.append(member.move_to(None))
            await asyncio.gather(*tasks)

            await inter.send("Done!")
            await asyncio.sleep(5)
            await inter.delete_original_response()

        @ self.bot.slash_command(description="Clears custom amount of messages")
        async def clear(inter: disnake.AppCmdInter, amount: int):
            if await self.check_dm(inter):
                return
            if not await helpers.is_admin(inter.author):
                return await inter.send(f"Unathorized attempt to clear messages!")

            await inter.channel.purge(limit=amount)
            await inter.send(f"Cleared {amount} messages")
            await asyncio.sleep(5)
            return await inter.delete_original_response()

    def add_music_instance(self, bot):
        self.music_instances.append(bot)

    def set_log_bot(self, bot):
        self.log_bot = bot

    async def run(self):
        await self.bot.start(self.token)

# *_______LevelingSystem____________________________________________________________________________________________________________________________________________________________________________________________

    def get_roles_from_exp(self, voice_xp, ranks, guild):
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

    async def scan_timer(self):
        while not self.bot.is_closed():
            asyncio.create_task(self.scan_channels())
            await asyncio.sleep(60)

    async def scan_channels(self):
        for guild in self.bot.guilds:
            ranks = await helpers.get_guild_option(guild.id, GuildOption.RANK_LIST)
            ranks = helpers.sort_ranks(ranks)
            for channel in guild.voice_channels:
                if helpers.get_members_count(channel.members) > 1 and channel != guild.afk_channel:
                    for member in channel.members:
                        if member.bot:
                            continue
                        v_xp, _ = await helpers.get_user_xp(guild.id, member.id)
                        v_xp += 1
                        await helpers.set_user_xp(guild.id, member.id, voice_xp=v_xp)

                        if not ranks:
                            continue

                        roles_to_remove, roles_to_add = self.get_roles_from_exp(v_xp, ranks, guild)
                        roles_to_add = await helpers.modify_roles(member, roles_to_remove=roles_to_remove, roles_to_add=roles_to_add)


# *_______OnVoiceStateUpdate_________________________________________________________________________________________________________________________________________________________________________________________

    async def temp_channels(self, member, before: disnake.VoiceState, after: disnake.VoiceState):
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
            await before.channel.delete()
            ff = True
        return ff

    async def unmute_clients(self, member, after: disnake.VoiceState):
        ff = False
        if after.channel:
            ff = await helpers.unmute_bots(member)
            ff = ff or (await helpers.unmute_admin(member))
        return ff

# *_______OnMessage_________________________________________________________________________________________________________________________________________________________________________________________

    async def check_message_content(self, message):
        if "discord.gg" in message.content.lower():
            try:
                await message.delete()
                await message.author.send(
                    f"Do NOT try to invite anyone to another servers {public_config.emojis['banned']}")
            except BaseException:
                pass
            return True
        return False

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
                    except BaseException:
                        pass
                    return await message.reply(f"How dare you tag me? Know your place, trash")

# *______SlashCommands______________________________________________________________________________________________________________________________________________________________________________________

    # def help(self):
        # ans = "Type /play to order a song (use URL from YT or just type the song's name)\n"
        # ans += "Type /stop to stop playback\n"
        # return ans

    async def check_dm(self, inter):
        if not inter.guild:
            try:
                if inter.author.id in private_config.supreme_beings:
                    await inter.send(f"{private_config.dm_error_supreme_being}")
            except:
                await inter.send(f"{public_config.dm_error}")
            return True
        return False

    async def add_admin(self, guild_id, user_id):
        admin_list = await helpers.get_guild_option(guild_id, GuildOption.ADMIN_LIST)
        if not user_id in admin_list:
            admin_list.append(user_id)
            await helpers.set_guild_option(guild_id, GuildOption.ADMIN_LIST, admin_list)
            return True
        return False

    async def remove_admin(self, guild_id, user_id):
        admin_list = await helpers.get_guild_option(guild_id, GuildOption.ADMIN_LIST)
        if user_id in admin_list:
            admin_list.remove(user_id)
            await helpers.set_guild_option(guild_id, GuildOption.ADMIN_LIST, admin_list)
            return True
        return False
