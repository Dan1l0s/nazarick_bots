import disnake
from disnake.ext import commands
import asyncio

from music_instance import MusicBotInstance, Interaction
import helpers
import config


class MusicBotLeader(MusicBotInstance):
    instances = None

    def __init__(self, name, logger):
        super().__init__(name, logger)
        self.instances = []
        self.instances.append(self)
        self.instance_count = 0

        @self.bot.event
        async def on_audit_log_entry_create(entry):
            self.logger.logged(entry)

        @self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
            self.log_voice_state_update(member, before, after)

            await self.on_voice_event(member, before, after)

            if await self.temp_channels(member, before, after):
                return

            if await self.unmute_clients(member, before, after):
                return
            # for instance in self.instances:
            #     await instance.check_timeout(member, before, after)

        @self.bot.event
        async def on_message(message):
            if not message.guild:
                if message.author.id in config.admin_ids[569924343010689025]:
                    await message.reply("Your attention is an honor for me, my master.")
                return
            await self.check_mentions(message)
            await self.check_message_content(message)

        # @self.bot.event
        # async def on_member_join(member):
        #     if member.guild.id in config.welcome_ids:
        #         channel = config.welcome_ids[member.guild.id]
        #         if not channel:
        #             return
        #     elif member.guild.system_channel:
        #         channel = member.guild.system_channel
        #     else:
        #         return
            # await channel.send(f"Greetings! {member.mention}, welcome to the Great Tomb of Nazarick.")

        @self.bot.slash_command(description="temporary command")
        async def welcome(inter):
            if await self.check_dm(inter):
                return
            embed = self.embedder.welcome_message(inter.author)
            await inter.send(embed=embed)

        @self.bot.slash_command(description="Allows admin to fix voice channels' bitrate")
        async def bitrate(inter):
            if await self.check_dm(inter):
                return
            await self.set_bitrate(384000)

        @self.bot.slash_command(description="Clears voice channel (authorized use only)")
        async def purge(inter):
            if await self.check_dm(inter):
                return
            if inter.author.id != config.admin_ids[inter.guild.id][0]:
                return await inter.send("Unauthorized access, you are not the Greatest Supreme Being!")
            tasks = []
            for member in inter.author.voice.channel.members:
                if member != inter.author and member.id not in config.bot_ids.values():
                    tasks.append(member.move_to(None))
            await asyncio.gather(*tasks)

            await inter.send("Done!")
            await asyncio.sleep(5)
            await inter.delete_original_response()

        @self.bot.slash_command(description="Clears custom amount of messages")
        async def clear(inter: disnake.AppCmdInter, amount: int):
            if await self.check_dm(inter):
                return
            if helpers.is_admin(inter.author):
                await inter.channel.purge(limit=amount+1)
                await inter.send(f"Cleared {amount} messages")
                await asyncio.sleep(5)
                return await inter.delete_original_response()
            return await inter.send(f"Unathorized attempt to clear messages!")

        @self.bot.slash_command(description="Plays a song from youtube (paste URL or type a query)", aliases="p")
        async def play(inter, query: str = commands.Param(description='Type a query or paste youtube URL')):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            if not inter.author.voice or not inter.author.voice.channel:
                return await inter.edit_original_response("You are not in voice channel")
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                assigned_instance = await self.get_available_instance(inter)
            if not assigned_instance:
                return await inter.edit_original_response("There are no available bots, you can get more music bots in discord.gg/nazarick")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.play(new_inter, query)

        @self.bot.slash_command(description="Plays anime radio or custom online radio")
        async def radio(inter, url=config.radio_url):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            if not inter.author.voice or not inter.author.voice.channel:
                return await inter.edit_original_response("You are not in voice channel")
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                assigned_instance = await self.get_available_instance(inter)
            if not assigned_instance:
                return await inter.edit_original_response("There are no available bots, you can get more music bots in discord.gg/nazarick")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.play(new_inter, url, radio=True)

        @self.bot.slash_command(description="Plays a song from youtube (paste URL or type a query) at position #1 in the queue", aliases="p")
        async def playnow(inter, query: str = commands.Param(description='Type a query or paste youtube URL')):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            if not inter.author.voice or not inter.author.voice.channel:
                return await inter.send("You are not in voice channel")
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                assigned_instance = await self.get_available_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no available bots, you can get more music bots in discord.gg/nazarick")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.play(new_inter, query, True)

        @self.bot.slash_command(description="Pauses/resumes player")
        async def pause(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.pause(new_inter)

        @self.bot.slash_command(description="Repeats current song")
        async def repeat(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.repeat(new_inter)

        @self.bot.slash_command(description="Clears queue and disconnects bot")
        async def stop(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.stop(new_inter)

        @self.bot.slash_command(description="Skips current song")
        async def skip(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.skip(new_inter)

        @self.bot.slash_command(description="Shows current queue")
        async def queue(inter):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.queue(new_inter)

        @self.bot.slash_command(description="Removes last added song from queue")
        async def wrong(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.wrong(new_inter)

        @self.bot.slash_command(description="Shuffles current queue")
        async def shuffle(inter: disnake.AppCmdInter):
            if await self.check_dm(inter):
                return
            await inter.response.defer()
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.shuffle(new_inter)

        @self.bot.slash_command(description="Reviews list of commands")
        async def help(inter: disnake.AppCmdInter):
            await inter.response.defer()
            await inter.send(embed=disnake.Embed(color=0, description=self.help()))

    def add_instance(self, bot):
        self.instances.append(bot)


# *_______OnVoiceStateUpdate_________________________________________________________________________________________________________________________________________________________________________________________


    async def temp_channels(self, member, before: disnake.VoiceState, after: disnake.VoiceState):
        if after.channel and after.channel.name == "Создать приват":
            await helpers.create_private(member)
            return True
        if before.channel and "'s private" in before.channel.name and len(before.channel.members) == 0:
            await before.channel.delete()
            return True
        return False

    async def unmute_clients(self, member, before: disnake.VoiceState, after: disnake.VoiceState):
        if after.channel:
            await helpers.unmute_bots(member)
            await helpers.unmute_admin(member)
            return True
        return False

    def log_voice_state_update(self, member, before: disnake.VoiceState, after: disnake.VoiceState):
        if before.channel and after.channel:
            if before.channel.id != after.channel.id:
                self.logger.switched(member, before, after)
            else:
                if before.deaf != after.deaf:
                    if before.deaf:
                        self.logger.guild_undeafened(member)
                    else:
                        self.logger.guild_deafened(member)
                elif before.mute != after.mute:
                    if before.mute:
                        self.logger.guild_unmuted(member)
                    else:
                        self.logger.guild_muted(member)
                elif before.self_deaf != after.self_deaf:
                    if before.self_deaf:
                        self.logger.undeafened(member)
                    else:
                        self.logger.deafened(member)
                elif before.self_mute != after.self_mute:
                    if before.self_mute:
                        self.logger.unmuted(member)
                    else:
                        self.logger.muted(member)
                elif before.self_video != after.self_video:
                    if before.self_video:
                        self.logger.video_off(member)
                    else:
                        self.logger.video_on(member)
                elif before.self_stream != after.self_stream:
                    if before.self_stream:
                        self.logger.stream_off(member)
                    else:
                        self.logger.stream_on(member)
        elif before.channel:
            self.logger.disconnected(member, before)
        else:
            self.logger.connected(member, after)

# *_______OnMessage_________________________________________________________________________________________________________________________________________________________________________________________

    async def check_message_content(self, message):
        if "discord.gg" in message.content.lower():
            try:
                await message.delete()
                await message.author.send(
                    f"Do NOT try to invite anyone to another servers {config.emojis['banned']}")
            except:
                pass
            return True
        return False


# *______InstanceRelated____________________________________________________________________________________________________________________________________________________________________________________


    async def get_available_instance(self, inter):
        guild_id = inter.guild.id
        for instance in self.instances:
            if instance.contains_in_guild(guild_id) and instance.available(guild_id):
                # print("Returned fair instance")
                return instance
        for instance in self.instances:
            if instance.contains_in_guild(guild_id) and instance.check_timeout(guild_id):
                # print("Returned fair instance from timeout")
                return instance
        if helpers.is_admin(inter.author):
            # print("Returned admin instance")
            return self
        return None

    async def get_playing_instance(self, inter):
        guild_id = inter.guild.id
        author_vc = None
        if inter.author.voice:
            author_vc = inter.author.voice.channel
        for instance in self.instances:
            if instance.contains_in_guild(guild_id) and instance.current_voice_channel(guild_id) == author_vc:
                return instance
        return None

# *______SlashCommands______________________________________________________________________________________________________________________________________________________________________________________

    async def set_bitrate(self, inter, desired_bitrate):
        if not helpers.is_admin(inter.author):
            return await inter.send("Unauthorized access, you are not the Supreme Being!")
        await inter.send("Processing...")

        for channel in inter.guild.voice_channels:
            await channel.edit(bitrate=desired_bitrate)

        await inter.edit_original_response("Done!")
        await asyncio.sleep(5)
        await inter.delete_original_response()

    async def find_instance(self, inter):
        guild = inter.guild
        for instance in self.instances:
            if guild in instance.guilds:
                voice = instance.bot.get_guild(inter.guild.id).voice_client
                if voice and voice.channel == inter.author.voice.channel:
                    return instance
        for instance in self.instances:
            if guild in instance.guilds:
                voice = instance.bot.get_guild(inter.guild.id).voice_client
                if not voice or not voice.is_connected() or len(voice.channel.members) == 1:
                    return instance
        if not helpers.is_admin(inter.author):
            return None
        for instance in self.instances:
            if guild in instance.guilds:
                return instance

    def help(self):
        ans = "Type /play to order a song (use URL from YT or just type the song's name)\n"
        ans += "Type /stop to stop playback\n"
        ans += "Type /skip to skip current track\n"
        ans += "Type /queue to print current queue\n"
        ans += "Type /shuffle to shuffle tracks in the queue\n"
        ans += "Type /wrong to remove last added track\n"
        ans += "Type /repeat to toogle repeat mode for current track\n"
        ans += "Type /pause to pause/resume playback"
        return ans

    async def check_dm(self, inter):
        if not inter.guild:
            if inter.author.id in config.admin_ids[569924343010689025]:
                await inter.send(f"{config.dm_error_admin}")
            else:
                await inter.send(f"{config.dm_error}")
            return True
        return False
