import disnake
import datetime
import os
import asyncio
import aiosqlite

import helpers.helpers as helpers


class DatabaseLogger:

    async def error(self, err, guild):
        await self.commit_to_database("common", guild_id=str(guild.id), tag="ERROR", comment=str(err))

# ---------------- BASIC BOT ----------------------------------------------------------------

    async def enabled(self, bot):
        await self.commit_to_database("bots", tag="STARTUP", comment=f"Bot is logged as {bot.user}")

    async def lost_connection(self, bot):
        await self.commit_to_database("bots", tag="ERROR", comment=f"Bot {bot.user} lost connection to Discord servers")


# ---------------- MUSIC BOT ----------------------------------------------------------------

    async def skip(self, inter):
        await self.commit_to_database("common", guild_id=str(inter.guild.id), tag="SKIP", comment=f"Skipped track in VC: {inter.guild.voice_client.channel}")

    async def added(self, guild, track):
        await self.commit_to_database("common", guild_id=str(guild.id), tag="PLAY", comment=f"Added {track['title']} to queue with duration of {helpers.get_duration(track)}")

    async def playing(self, guild, track):
        await self.commit_to_database("common", guild_id=str(guild.id), tag="PLAY", comment=f"Playing {track['title']} in VC: {guild.voice_client.channel}")

    async def radio(self, guild, data):
        await self.commit_to_database("common", guild_id=str(guild.id), tag="RADIO", comment=f"Playing {data['name']} in VC: {guild.voice_client.channel}")

    async def finished(self, guild):
        await self.commit_to_database("common", guild_id=str(guild.id), tag="STOP", comment=f"Finished playing in VC: {guild.voice_client.channel}")

# ---------------- ACTIONS ----------------------------------------------------------------

    async def switched(self, member, before, after):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} switched VC from {before.channel.name} to {after.channel.name}")

    async def connected(self, member, after):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} joined VC {after.channel.name}")

    async def disconnected(self, member, before):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} left VC {before.channel.name}")

    async def deaf(self, member, after):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} was {('un','')[after.deaf]}deafened in guild")

    async def mute(self, member, after):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} was {('un','')[after.mute]}muted in guild")

    async def self_deaf(self, member, after):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} {('un','')[after.self_deaf]}deafened themself")

    async def self_mute(self, member, after):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} {('un','')[after.mute]}muted themself")

    async def self_video(self, member, after):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} turned {('off','on')[after.self_video]} their camera")

    async def self_stream(self, member, after):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="VC", comment=f"User {member} {('stopped','started')[after.self_stream]} sharing their screen")

    async def member_join(self, member):
        await self.commit_to_database("common", guild_id=str(member.guild.id), tag="GUILD", comment=f"User {member} has joined the server")

    async def member_remove(self, payload):
        await self.commit_to_database("common", guild_id=str(payload.guild.id), tag="GUILD", comment=f"User {payload.user} has joined the server")

    async def member_update(self, after):
        await self.commit_to_database("common", guild_id=str(after.guild.id), tag="GUILD", comment=f"User {after.name} updated their profile")

    async def status_upd(self, member):
        await self.commit_to_database("status", guild_id=str(member.guild.id), user_id=str(member.id), comment=f"User {member.name} has gone {member.status}")

    async def activity_upd(self, member, old_user_status, new_user_status):
        comment = [f"User {member.name} has updated their activities"]

        for acts in old_user_status.activities:
            if acts not in new_user_status.activities:
                comment.append(f' - {acts.actname}')
        for acts in new_user_status.activities:
            if acts not in old_user_status.activities:
                comment.append(f' + {acts.actname}')
        comment = '\n'.join(comment)

        await self.commit_to_database("status", guild_id=str(member.guild.id), user_id=str(member.id), comment=comment)

# ---------------- ENTRY_ACTION ----------------------------------------------------------------

    async def entry_channel_create(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has created channel {entry.target.name}")

    async def entry_channel_update(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has updated channel {entry.target.name}")

    async def entry_channel_delete(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has deleted channel {entry.before.name}")

    async def entry_thread_create(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has created thread {entry.target.name}")

    async def entry_thread_update(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has updated thread {entry.target.name}")

    async def entry_thread_delete(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has deleted thread {entry.before.name}")

    async def entry_role_create(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has created role {entry.target.name}")

    async def entry_role_update(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has updated role {entry.target.name}")

    async def entry_role_delete(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has created role {entry.before.name}")

    async def entry_emoji_create(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has created emoji {entry.target.name}")

    async def entry_emoji_update(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has updated emoji {entry.target.name}")

    async def entry_emoji_delete(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has deleted emoji {entry.before.name}")

    async def entry_invite_create(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has created an invite")

    async def entry_invite_update(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has updated an invite")

    async def entry_invite_delete(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has deleted an invite")

    async def entry_sticker_create(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has created a sticker")

    async def entry_sticker_update(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has updated a sticker")

    async def entry_sticker_delete(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has deleted a sticker")

    async def entry_guild_scheduled_event_create(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has created a scheduled guild event")

    async def entry_guild_scheduled_event_update(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has updated a scheduled guild event")

    async def entry_guild_scheduled_event_delete(self, entry):
        await self.commit_to_database("common", guild_id=str(entry.guild.id), tag="ENTRY", comment=f"User {entry.user} has deleted a scheduled guild event")

# ---------------- GPT ----------------------------------------------------------------

    async def gpt(self, member, messages, guild_id="gpt"):
        await self.commit_to_database("gpt", user_id=str(member.id), query=messages[0], response=messages[1])

# ---------------- HELPING METHODS  ----------------------------------------------------------------

    async def commit_to_database(self, table_name: str, guild_id: str = None, tag: str = None, comment: str = None, query: str = None, response: str = None, user_id: str = None):
        await helpers.ensure_tables_logger()

        db = await aiosqlite.connect('logs.db')
        cursor = await db.cursor()

        date = datetime.datetime.now().strftime('%Y-%m-%d')
        time = datetime.datetime.now().strftime("%H:%M:%S")

        match table_name:
            case "common":
                await cursor.execute(f"INSERT INTO common VALUES(?, ?, ?, ?, ?)", (guild_id, date, time, tag, comment))
            case "bots":
                await cursor.execute(f"INSERT INTO bots VALUES(?, ?, ?, ?)", (date, time, tag, comment))
            case "gpt":
                await cursor.execute(f"INSERT INTO gpt VALUES(?, ?, ?, ?, ?)", (date, time, user_id, query, response))
            case "status":
                await cursor.execute(f"INSERT INTO status VALUES(?, ?, ?, ?, ?)", (guild_id, date, time, user_id, comment))
            case _:
                await db.close()
                raise (f"Incorrect table name '{table_name}' in commit_to_database!")

        await db.commit()
        await db.close()
