import disnake
from disnake.ext import commands
import asyncio

from music_instance import MusicBotInstance, Interaction
import helpers
import config


class MusicBotLeader(MusicBotInstance):
    instances = None

    def __init__(self, name, logger):
        MusicBotInstance.__init__(self, name, logger)
        self.instances = []
        self.instances.append(self)

        @self.bot.event
        async def on_audit_log_entry_create(entry):
            self.logger.logged(entry)

        @self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
            self.log_voice_state_update(member, before, after)
            if await self.manager_private(member, before, after):
                return
            if await self.umute_clients(member, before, after):
                return
            for instance in self.instances:
                await instance.check_timout(member, before, after)

        @self.bot.event
        async def on_message(message):
            await self.check_message_content(message)

        @self.bot.slash_command(description="Allows admin to fix voice channels' bitrate")
        async def bitrate(inter):
            await self.set_bitrate(384000)

        @self.bot.slash_command(description="Clears voice channel (authorized use only)")
        async def purge(inter):
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
            if helpers.is_admin(inter.author):
                await inter.channel.purge(limit=amount+1)
                await inter.send(f"Cleared {amount} messages")
                await asyncio.sleep(5)
                return await inter.delete_original_response()
            return await inter.send(f"Unathorized attempt to clear messages!")

        @self.bot.slash_command(description="Plays a song from youtube (paste URL or type a query)", aliases="p")
        async def play(inter, query: str = commands.Param(description='Type a query or paste youtube URL')):
            await self.empty_response(inter)
            new_inter = Interaction(inter, self.instances[0].bot)
            await self.instances[0].play(new_inter, query)

        @self.bot.slash_command(description="Pauses/resumes self.player")
        async def pause(inter: disnake.AppCmdInter):
            await self.player.pause(inter)

        @self.bot.slash_command(description="Repeats current song")
        async def repeat(inter: disnake.AppCmdInter):
            await self.player.repeat(inter)

        @self.bot.slash_command(description="Clears queue and disconnects bot")
        async def stop(inter: disnake.AppCmdInter):
            await self.player.stop(inter)

        @self.bot.slash_command(description="Skips current song")
        async def skip(inter: disnake.AppCmdInter):
            await self.player.skip(inter)

        @self.bot.slash_command(description="Shows current queue")
        async def queue(inter):
            await self.player.queue(inter)

        @self.bot.slash_command(description="Removes last added song from queue")
        async def wrong(inter: disnake.AppCmdInter):
            await self.player.wrong(inter)

        @self.bot.slash_command(description="Shuffles current queue")
        async def shuffle(inter: disnake.AppCmdInter):
            await self.player.shuffle(inter)

        @self.bot.slash_command(description="Reviews list of commands")
        async def help(inter: disnake.AppCmdInter):
            ans = self.player.help()
            await inter.send(embed=disnake.Embed(color=0, description=ans))

    def add_instance(self, bot):
        self.instances.append(bot)

# *_______OnVoiceStateUpdate_________________________________________________________________________________________________________________________________________________________________________________________

    async def manager_private(self, member, before: disnake.VoiceState, after: disnake.VoiceState):
        if after.channel and after.channel.name == "Создать приват":
            await helpers.create_private(member)
            return True
        if before.channel and "'s private" in before.channel.name and len(before.channel.members) == 0:
            await before.channel.delete()
            return True
        return False

    async def umute_clients(self, member, before: disnake.VoiceState, after: disnake.VoiceState):
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
                self.logger.voice_update(member)
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

    async def check_mentions(self, message):
        if len(message.role_mentions) > 0 or len(message.mentions) > 0:
            client = message.guild.get_member(self.bot.user.id)
            if helpers.is_mentioned(client, message):
                if helpers.is_admin(message.author):
                    if "ping" in message.content.lower() or "пинг" in message.content.lower():
                        return await message.reply(f"Yes, my master. My ping is {round(self.bot.latency*1000)} ms")
                    else:
                        return await message.reply("At your service, my master.")
                else:
                    await message.author.timeout(duration=10, reason="Ping by lower life form")
                    return await message.reply(f"How dare you tag me? Know your place, trash")

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
