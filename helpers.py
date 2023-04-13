import config
import disnake
from datetime import datetime, timezone
import time


def is_admin(member):
    if member.guild and member.guild.id not in config.admin_ids or member.id not in config.admin_ids[member.guild.id]:
        return False
    return True


def get_duration(info):
    if "live_status" in info and info['live_status'] == "is_live" or info['duration'] == 0:
        ans = "Live"
    else:
        ans = time.strftime('%H:%M:%S', time.gmtime(info['duration']))
    return ans


def is_mentioned(member, message):
    for role in message.role_mentions:
        if role in member.roles:
            return True
    if member in message.mentions:
        return True
    return False


async def create_private(member):

    if member.guild.id not in config.categories_ids:
        return
    possible_channel_name = f"{member.display_name}'s private"

    guild = member.guild
    category = disnake.utils.get(
        guild.categories, id=config.categories_ids[guild.id])

    tmp_channel = await category.create_voice_channel(name=possible_channel_name)

    await tmp_channel.set_permissions(guild.default_role, view_channel=False)

    await member.move_to(tmp_channel)

    perms = tmp_channel.overwrites_for(member)
    perms.view_channel = True
    perms.manage_permissions = True
    perms.manage_channels = True
    await tmp_channel.set_permissions(member, overwrite=perms)
    await tmp_channel.edit(bitrate=384000)


async def unmute_bots(member):
    if member.id in config.bot_ids.values():
        if member.voice.mute:
            await member.edit(mute=False)
        if member.voice.deaf:
            await member.edit(deafen=False)


async def unmute_admin(member):
    if member.guild.id in config.supreme_beings_ids and member.id in config.supreme_beings_ids[member.guild.id]:
        if member.voice.mute:
            await member.edit(mute=False)
        if member.voice.deaf:
            await member.edit(deafen=False)
        entry = await member.guild.audit_logs(limit=2, action=disnake.AuditLogAction.member_update).flatten()
        entry = entry[1]
        delta = datetime.now(timezone.utc) - entry.created_at
        if entry.user != member and entry.user.id not in config.bot_ids and (delta.total_seconds() < 2) and entry.user.id not in config.supreme_beings_ids[member.guild.id]:
            await entry.user.move_to(None)
            await entry.user.timeout(duration=60, reason="Attempt attacking The Supreme Being")


def get_guild_name(guild):
    if guild.name == "Nazarick":
        return "the Great Tomb of Nazarick"
    return guild.name


def get_welcome_time(date):
    delta = datetime.now(timezone.utc) - date
    amount = delta.days // 365
    if amount > 0:
        if amount == 1:
            return "a year ago"
        else:
            return f"{amount} years ago"

    amount = delta.days // 30
    if amount > 0:
        if amount == 1:
            return "a month ago"
        else:
            return f"{amount} months ago"

    amount = delta.days // 7
    if amount > 0:
        if amount == 1:
            return "a week ago"
        else:
            return f"{amount} weeks ago"

    amount = delta.days
    if amount > 0:
        if amount == 1:
            return "a day ago"
        else:
            return f"{amount} days ago"

    amount = delta.hours
    if amount > 0:
        if amount == 1:
            return "an hour ago"
        else:
            return f"{amount} hours ago"

    amount = delta.minutes
    if amount <= 1:
        return "a minute ago"
    return f"{amount} minutes ago"
