import config
import disnake
from datetime import datetime, timezone


def is_admin(member):
    if member.guild.id not in config.admin_ids or member.id not in config.admin_ids[member.guild.id]:
        return False
    return True


def get_nickname(member):
    if member.nick:
        return member.nick
    else:
        return member.name


def get_duration(duration):
    ans = ""
    hours = duration // 3600
    minutes = (duration // 60) - hours*60
    seconds = duration % 60
    if hours == 0:
        ans += "00"
    elif hours < 10:
        ans += "0"+str(hours)
    else:
        ans += str(hours)

    if minutes == 0:
        ans += ":00"
    elif minutes < 10:
        ans += ":0"+str(minutes)
    else:
        ans += ":"+str(minutes)

    if seconds == 0:
        ans += ":00"
    elif seconds < 10:
        ans += ":0"+str(seconds)
    else:
        ans += ":"+str(seconds)
    return ans


def is_mentioned(member, message):
    for role in message.role_mentions:
        if role in member.roles:
            return True
    if member in message.mentions:
        return True
    return False


async def create_private(member):
    possible_channel_name = f"{get_nickname(member)}'s private"

    guild = member.guild
    category = disnake.utils.get(
        guild.categories, id=config.categories_ids[guild.id])

    tmp_channel = await category.create_voice_channel(name=possible_channel_name)

    perms = tmp_channel.overwrites_for(guild.default_role)
    perms.view_channel = False
    await tmp_channel.set_permissions(guild.default_role, overwrite=perms)

    await member.move_to(tmp_channel)

    perms = tmp_channel.overwrites_for(member)
    perms.view_channel = True
    perms.manage_permissions = True
    perms.manage_channels = True
    await tmp_channel.set_permissions(member, overwrite=perms)
    await tmp_channel.edit(bitrate=384000)


async def unmute_client(member, tag):
    client = member.guild.get_member(config.ids[tag])
    if member == client:
        if client.voice.mute:
            await member.edit(mute=False)
        if client.voice.deaf:
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
        if entry.user != member and entry.user.id != config.ids["music"] and (delta.total_seconds() < 2) and entry.user.id not in config.supreme_beings_ids[member.guild.id]:
            await entry.user.timeout(duration=60, reason="Attempt attacking The Supreme Being")
            await entry.user.move_to(None)
