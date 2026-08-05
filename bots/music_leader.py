"""The music bot that users actually interact with.

Only this bot registers the /play, /skip, /queue, ... slash commands. When a
command comes in it picks which `MusicBotInstance` should handle it (the one
already in the user's voice channel, or an idle one) and delegates, rebinding
the interaction onto that instance via `Interaction`. The leader is itself an
instance too - `self.instances` includes `self` - so with zero assistants
configured it just plays everything by itself.

Selection order (see `get_available_instance`): a bot with no voice client at
all is preferred; failing that, one that is mid-inactivity-timeout (about to
disconnect anyway) is reused.

Behavior preserved from the original. The commented-out ChatGPT block is
retained but updated for the openai>=1.0 SDK - see CHANGES.md "Stage 2".
"""

from __future__ import annotations

import asyncio
import logging

import disnake
from disnake.ext import commands

import configs.private_config as private_config
import configs.public_config as public_config
import helpers.database_logger as database_logger
import helpers.helpers as helpers
from bots.music_instance import Interaction, MusicBotInstance

logger = logging.getLogger("nazarick.music.leader")


class MusicBotLeader(MusicBotInstance):

    def __init__(self, name, token, process_pool):
        super().__init__(name, token, process_pool)
        self.instances = []
        self.instances.append(self)
        self.instance_count = 0
        # self.chatgpt_messages = {}
        # self.openai_client = openai.AsyncOpenAI(api_key=private_config.openai_api_key)

        @self.bot.event
        async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
            await self.on_voice_event(member, before, after)

            if await self.unmute_clients(member, before, after):
                return

            # Only act as a fallback moderator when the dedicated admin bot is
            # absent from this guild - otherwise admin_bot handles it.
            if member.guild.get_member(private_config.bot_ids["moderate"]) is None:
                if not after.channel:
                    if await helpers.check_admin_kick(member):
                        return

        @self.bot.event
        async def on_message(message):
            # if await self.check_gpt_interaction(message):
            #     return

            if not message.guild:
                if helpers.is_supreme_being(message.author):
                    await message.reply(public_config.on_message_supreme_being)
                return

            # Same fallback-moderation rule as above: only filter invites when
            # the admin bot isn't around to do it.
            if self.bot.get_user(private_config.bot_ids["moderate"]) is None:
                await self.check_message_content(message)
            await helpers.check_mentions(message, self.bot)

        @self.bot.slash_command(dm_permission=False, description="Plays a song from youtube (paste URL or type a query)", aliases="p")
        async def play(inter: disnake.AppCmdInter,
                       query: str = commands.Param(description='Type a query or paste youtube URL')):
            await inter.response.defer()

            if not inter.author.voice or not inter.author.voice.channel:
                return await inter.send("You are not in voice channel")
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                assigned_instance = await self.get_available_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no available bots, you can get more music bots in discord.gg/nazarick")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.play(new_inter, query)

        @self.bot.slash_command(dm_permission=False, description="Plays anime radio or custom online radio")
        async def radio(inter: disnake.AppCmdInter,
                        url: str = commands.Param(default=public_config.radio_url, description="URL of online radio (mp3 player)")):
            await inter.response.defer()

            if not inter.author.voice or not inter.author.voice.channel:
                return await inter.send("You are not in voice channel")
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                assigned_instance = await self.get_available_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no available bots, you can get more music bots in discord.gg/nazarick")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.play(new_inter, url, radio=True)

        @self.bot.slash_command(dm_permission=False, description="Plays a song from youtube (paste URL or type a query) at position #1 in the queue", aliases="p")
        async def playnow(inter: disnake.AppCmdInter,
                          query: str = commands.Param(description='Type a query or paste youtube URL')):
            await inter.response.defer()

            if not inter.author.voice or not inter.author.voice.channel:
                return await inter.send("You are not in voice channel")
            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                assigned_instance = await self.get_available_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no available bots, you can get more music bots in discord.gg/nazarick")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.play(new_inter, query, playnow=True)

        @self.bot.slash_command(dm_permission=False, description="Pauses/resumes player")
        async def pause(inter: disnake.AppCmdInter):
            await inter.response.defer()

            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.pause(new_inter)

        @self.bot.slash_command(dm_permission=False, description="Repeats current song")
        async def repeat(inter: disnake.AppCmdInter):
            await inter.response.defer()

            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.repeat(new_inter)

        @self.bot.slash_command(dm_permission=False, description="Clears queue and disconnects bot")
        async def stop(inter: disnake.AppCmdInter):
            await inter.response.defer()

            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.stop(new_inter)

        @self.bot.slash_command(dm_permission=False, description="Skips current song")
        async def skip(inter: disnake.AppCmdInter):
            await inter.response.defer()

            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.skip(new_inter)

        @self.bot.slash_command(dm_permission=False, description="Shows current queue")
        async def queue(inter: disnake.AppCmdInter):
            await inter.response.defer()

            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.queue(new_inter)

        @self.bot.slash_command(dm_permission=False, description="Removes last added song from queue")
        async def wrong(inter: disnake.AppCmdInter):
            await inter.response.defer()

            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.wrong(new_inter)

        @self.bot.slash_command(dm_permission=False, description="Shuffles current queue")
        async def shuffle(inter: disnake.AppCmdInter):
            await inter.response.defer()

            assigned_instance = await self.get_playing_instance(inter)
            if not assigned_instance:
                return await inter.send("There are no bots in your voice channel")
            new_inter = Interaction(assigned_instance.bot, inter)
            await assigned_instance.shuffle(new_inter)

        # ChatGPT integration - disabled in the original and left disabled here.
        # The code below has been updated from the openai v0 SDK
        # (`openai.ChatCompletion.create`, removed in openai>=1.0) to the
        # current async client API, so it will actually run if uncommented.
        # To enable: uncomment these two commands, the `self.chatgpt_messages`
        # and `self.openai_client` lines in __init__, the `check_gpt_interaction`
        # call in on_message, the `import openai` at the top of this file, and
        # add `openai` to requirements.txt.

        # @self.bot.slash_command(description="Allows to use ChatGPT")
        # async def gpt(inter: disnake.AppCmdInter,
        #               message: str = commands.Param(description="Type a query to get ChatGPT's reply")):
        #     await inter.response.defer()

        #     new_inter = Interaction(self.bot, inter)
        #     asyncio.create_task(self.gpt_helper(new_inter, message))

        # @self.bot.slash_command(description="Clears chat history with ChatGPT (it will forget all your messages)")
        # async def gpt_clear(inter: disnake.AppCmdInter):
        #     await inter.response.defer()

        #     self.chatgpt_messages[inter.author.id] = []
        #     await inter.send("Done!", delete_after=5)

        @self.bot.slash_command(description="Reviews list of commands")
        async def help(inter: disnake.AppCmdInter):
            await inter.response.defer()
            await inter.send(embed=disnake.Embed(color=0, description=self.help()))

    def add_instance(self, bot) -> None:
        self.instances.append(bot)


# *_______OnVoiceStateUpdate_________________________________________________________________________________________________________________________________________________________________________________________

    async def unmute_clients(self, member, before: disnake.VoiceState, after: disnake.VoiceState) -> bool:
        # Deliberately inverted relative to admin_bot: the leader only does this
        # when the admin bot is *not* in the guild, to avoid both bots racing to
        # unmute the same member.
        if member.guild.get_member(private_config.bot_ids["moderate"]) is not None:
            return False

        if after.channel:
            await helpers.unmute_bots(member)
            await helpers.unmute_admin(member)
            return True
        return False

# *_______OnMessage_________________________________________________________________________________________________________________________________________________________________________________________

    async def check_message_content(self, message) -> bool:
        """Deletes Discord invite links posted by non-admins (fallback for when
        the admin bot isn't in the guild)."""
        if "discord.gg" in message.content.lower() or "discordapp.com/invite" in message.content.lower():
            if hasattr(message.author, "guild"):
                if not await helpers.is_admin(message.author):
                    await helpers.try_function(message.delete, True)
                    await helpers.try_function(message.author.send, True, f"Do NOT try to invite anyone to another servers {public_config.emojis['banned']}")
            else:
                await helpers.try_function(message.delete, True)
            return True
        return False

    async def check_gpt_interaction(self, message) -> bool:
        """Routes DMs and replies-to-the-bot into the ChatGPT handler.

        Dormant along with the rest of the GPT feature (see the commented
        commands in __init__); kept intact so the feature can be restored."""
        if message.author.bot:
            return False
        if not message.guild:
            inter = Interaction(self.bot, message)
            inter.orig_inter = None
            inter.message = message
            asyncio.create_task(self.gpt_helper(inter, message.content))
            return True
        if message.reference:
            ff, replied_message = await helpers.try_function(message.channel.fetch_message, True, message.reference.message_id)
            if not ff:
                return False
            if message.author.id not in self.chatgpt_messages or replied_message.author.id != self.bot.user.id:
                return False
            try:
                # Confirms the replied-to message is really the tail of this
                # user's conversation before continuing it.
                if replied_message.content[10:100] in self.chatgpt_messages[message.author.id][-1]["content"]:
                    inter = Interaction(self.bot, message)
                    inter.orig_inter = None
                    inter.message = message
                    asyncio.create_task(self.gpt_helper(inter, message.content))
                    return True
            except Exception as err:
                print(err)
        return False

# *______InstanceRelated____________________________________________________________________________________________________________________________________________________________________________________

    async def get_available_instance(self, inter):
        """Picks a free instance: first a fully idle one, then one already
        counting down its inactivity timeout."""
        guild_id = inter.guild.id
        for instance in self.instances:
            if instance.contains_in_guild(guild_id) and instance.available(guild_id):
                # print("Returned fair instance")
                return instance
        for instance in self.instances:
            if instance.contains_in_guild(guild_id) and instance.check_timeout(guild_id):
                # print("Returned fair instance from timeout")
                return instance
        return None

    async def find_instance(self, inter):
        """Alternative instance lookup - prefers the bot in the author's channel,
        then any disconnected/alone bot, then (for admins only) any instance at
        all.

        Not called by any command handler; `get_playing_instance` +
        `get_available_instance` are used instead. Kept because it encodes a
        different (admin-privileged) selection policy that may be wanted later.

        BUGFIX: this function could not have run as written. It referenced
        `instance.guilds`, which does not exist on MusicBotInstance (the
        attribute is `instance.bot.guilds`), and called
        `helpers.get_members_cont`, which does not exist either (the real name
        is `get_true_members_count`). Both are corrected below; being dead code,
        neither error was ever surfaced at runtime.
        """
        guild = inter.guild
        for instance in self.instances:
            if guild in instance.bot.guilds:
                voice = instance.bot.get_guild(inter.guild.id).voice_client
                if voice and voice.channel == inter.author.voice.channel:
                    return instance
        for instance in self.instances:
            if guild in instance.bot.guilds:
                voice = instance.bot.get_guild(inter.guild.id).voice_client
                if not voice or not voice.is_connected() or helpers.get_true_members_count(voice.channel.members) == 1:
                    return instance
        if not await helpers.is_admin(inter.author):
            return None
        for instance in self.instances:
            if guild in instance.bot.guilds:
                return instance

    async def get_playing_instance(self, inter):
        """Returns the instance already connected to the author's voice channel,
        which is what makes /skip, /queue etc. address the right bot."""
        guild_id = inter.guild.id
        author_vc = None
        if inter.author.voice:
            author_vc = inter.author.voice.channel
        else:
            return None
        for instance in self.instances:
            if instance.contains_in_guild(guild_id) and instance.current_voice_channel(guild_id) == author_vc:
                return instance
        return None

# *______SlashCommands______________________________________________________________________________________________________________________________________________________________________________________

    async def gpt_helper(self, inter, message):
        """Sends the user's rolling conversation to ChatGPT and posts the reply,
        split into Discord-sized chunks.

        Dormant (see the commented commands in __init__). Updated from the
        removed openai v0 `ChatCompletion.create` API to the openai>=1.0 async
        client. On failure it drops the oldest exchange and retries, which is
        the original's crude way of recovering from context-length errors.
        """
        if inter.author.id not in self.chatgpt_messages:
            self.chatgpt_messages[inter.author.id] = []
        messages_list = self.chatgpt_messages[inter.author.id]
        messages_list.append({"role": "user", "content": message})

        while True:
            try:
                response = await self.openai_client.chat.completions.create(model="gpt-3.5-turbo", messages=messages_list)
                response = response.choices[0].message.content
                break
            except Exception as e:
                print(e)
                if len(messages_list) > 1:
                    messages_list = messages_list[2:]

        chunks = helpers.split_into_chunks(response)

        if inter.orig_inter:
            await inter.orig_inter.edit_original_response(chunks[0])
        else:
            await inter.message.reply(chunks[0])
        for i in range(1, len(chunks)):
            await inter.text_channel.send(chunks[i])
        messages_list.append({"role": "assistant", "content": response})
        await database_logger.gpt(inter.author, [message, response])

    def help(self) -> str:
        ans = "Type **/play** to order a song (use URL from YT or just type the song's name)\n"
        ans += "Type **/stop** to stop playback\n"
        ans += "Type **/skip** to skip current track\n"
        ans += "Type **/queue** to print current queue\n"
        ans += "Type **/shuffle** to shuffle tracks in the queue\n"
        ans += "Type **/wrong** to remove last added track\n"
        ans += "Type **/repeat** to toogle repeat mode for current track\n"
        ans += "Type **/pause** to pause/resume playback\n"
        ans += "Type **/playnow** to order a song at pos #1 in the queue\n"
        ans += "Type **/radio** to play online radio (by default plays ANISON.FM)"
        return ans
