import disnake
from disnake.ext import commands
import asyncio

from logger import Logger
from embedder import Embed
from player import Player
import helpers
import config

songs_queue = {}
curr_inter = {}

skip_flag = {}
repeat_flag = {}


bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all(
), activity=disnake.Activity(name="/play", type=disnake.ActivityType.listening))

logger = Logger(True)
embedder = Embed()

player = Player(logger, embedder)


@bot.event
async def on_message(message):
    if "discord.gg" in message.content.lower():
        try:
            await message.delete()
            await message.author.send(
                f"Do NOT try to invite anyone to another servers {config.emojis['banned']}")
        except:
            pass

    if len(message.role_mentions) > 0 or len(message.mentions) > 0:
        client = message.guild.get_member(config.ids["music"])
        if helpers.is_mentioned(client, message):
            if helpers.is_admin(message.author):
                if "ping" in message.content.lower() or "пинг" in message.content.lower():
                    return await message.reply(f"Yes, my master. My ping is {round(bot.latency*1000)} ms")
                else:
                    return await message.reply("At your service, my master.")
            else:
                await message.author.timeout(duration=10, reason="Ping by lower life form")
                return await message.reply(f"How dare you tag me? Know your place, trash")


@bot.event
async def on_ready():
    print(f"MusicBot is logged as {bot.user}")
    logger.enabled(bot)


@bot.event
async def on_audit_log_entry_create(entry):
    logger.logged(entry)
    # await entry.guild.get_channel(config.log_ids[entry.guild.id]).send(embed=embedder.action(entry))


@bot.event
async def on_voice_state_update(member, before: disnake.VoiceState, after: disnake.VoiceState):
    if before.channel and after.channel:
        if before.channel.id != after.channel.id:
            logger.switched(member, before, after)
            # await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=embedder.switched(member, before, after))
        else:
            logger.voice_update(member)
            # await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=embedder.voice_update(member))
    elif before.channel:
        logger.disconnected(member, before)
        # await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=embedder.disconnected(member, before))
    else:
        logger.connected(member, after)
        # await member.guild.get_channel(config.log_ids[member.guild.id]).send(embed=embedder.connected(member, after))

    if after.channel and after.channel.name == "Создать приват":
        await helpers.create_private(member)
    if before.channel:
        if "'s private" in before.channel.name:
            if len(before.channel.members) == 0:
                await before.channel.delete()
    if after.channel and member:
        await helpers.unmute_clients(member)
        await helpers.unmute_admin(member)


@bot.slash_command(description="Allows admin to fix voice channels' bitrate")
async def bitrate(inter):
    if not helpers.is_admin(inter.author):
        return await inter.send("Unauthorized access, you are not the Supreme Being!")
    await inter.send("Processing...")

    for channel in inter.guild.voice_channels:
        await channel.edit(bitrate=384000)

    await inter.edit_original_response("Done!")
    await asyncio.sleep(5)
    await inter.delete_original_response()


@bot.slash_command(description="Clears voice channel (authorized use only)")
async def purge(inter):
    if inter.author.id != config.admin_ids[inter.guild.id][0]:
        return await inter.send("Authorized access, you are not the Greatest Supreme Being!")
    for member in inter.author.voice.channel.members:
        if member != inter.author and member.id not in config.ids.values():
            await member.move_to(None)
    await inter.send("Done!")
    await asyncio.sleep(5)
    await inter.delete_original_response()


@ bot.slash_command(description="Clears custom amount of messages")
async def clear(inter: disnake.AppCmdInter, amount: int):
    if helpers.is_admin(inter.author):
        await inter.channel.purge(limit=amount+1)
        await inter.send(f"Cleared {amount} messages")
        await asyncio.sleep(5)
        return await inter.delete_original_response()
    return await inter.send(f"Unathorized attempt to clear messages!")


@bot.slash_command(description="Plays a song from youtube (paste URL or type a query)", aliases="p")
async def play(inter, query: str = commands.Param(description='Type a query or paste youtube URL')):
    await player.play(inter, query)


@ bot.slash_command(description="Pauses/resumes player")
async def pause(inter: disnake.AppCmdInter):
    await player.pause(inter)


@ bot.slash_command(description="Repeats current song")
async def repeat(inter: disnake.AppCmdInter):
    await player.repeat(inter)


@ bot.slash_command(description="Clears queue and disconnects bot")
async def stop(inter: disnake.AppCmdInter):
    await player.stop(inter)


@ bot.slash_command(description="Skips current song")
async def skip(inter: disnake.AppCmdInter):
    await player.skip(inter)


@ bot.slash_command(description="Shows current queue")
async def queue(inter):
    await player.queue(inter)


@ bot.slash_command(description="Removes last added song from queue")
async def wrong(inter: disnake.AppCmdInter):
    await player.wrong(inter)


@bot.slash_command(description="Shuffles current queue")
async def shuffle(inter: disnake.AppCmdInter):
    await player.shuffle(inter)


@ bot.slash_command(description="Reviews list of commands")
async def help(inter: disnake.AppCmdInter):
    ans = player.help()
    await inter.send(embed=disnake.Embed(color=0, description=ans))


bot.run(config.tokens["music"])
