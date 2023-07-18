import disnake
from datetime import datetime, timezone
import time
import re
import aiosqlite
from yt_dlp import YoutubeDL
from youtube_search import YoutubeSearch
from enum import Enum

import configs.private_config as private_config
import configs.public_config as public_config


async def is_admin(member):
    return member.guild and member.id in await get_server_option(member.guild.id, ServerOption.ADMIN_IDS)


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
    category_id = await get_server_option(member.guild.id, ServerOption.PRIVATE_CATEGORY)
    if not category_id:
        return
    possible_channel_name = f"{member.display_name}'s private"

    guild = member.guild
    category = guild.get_channel(int(category_id))

    tmp_channel = await category.create_voice_channel(name=possible_channel_name)

    await tmp_channel.set_permissions(guild.default_role, view_channel=False)

    await member.move_to(tmp_channel)

    perms = tmp_channel.overwrites_for(member)
    perms.view_channel = True
    perms.manage_permissions = True
    perms.manage_channels = True
    await tmp_channel.set_permissions(member, overwrite=perms)
    await tmp_channel.edit(bitrate=public_config.temporary_channels_settings['bitrate'])


async def unmute_bots(member):
    ff = False
    if member.id in private_config.bot_ids.values():
        if member.voice.mute:
            await member.edit(mute=False)
            ff = True
        if member.voice.deaf:
            await member.edit(deafen=False)
            ff = True
    return ff


async def unmute_admin(member):
    ff = False
    if await is_admin(member):
        if member.voice.mute:
            await member.edit(mute=False)
            ff = True
        if member.voice.deaf:
            await member.edit(deafen=False)
            ff = True

        entry = await member.guild.audit_logs(limit=2, action=disnake.AuditLogAction.member_update).flatten()
        entry = entry[1]
        delta = datetime.now(timezone.utc) - entry.created_at
        if entry.user != member and entry.user.id not in private_config.bot_ids.values() and (delta.total_seconds() < 2) and entry.user.id not in await get_server_option(member.guild.id, ServerOption.ADMIN_IDS):
            await entry.user.move_to(None)
            try:
                await entry.user.timeout(duration=60, reason="Attempt attacking The Supreme Being")
            except:
                pass
    return ff


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


def get_members_count(members):
    cnt = len(members)
    for member in members:
        if member.bot:
            cnt -= 1
    return cnt


def split_into_chunks(msg: list[str], chunk_size: int = 1990) -> list[str]:
    source = msg.split("\n")
    pattern = r'```[a-zA-Z]*\n'
    chunks = []
    chunk = ""
    length = 0
    for line in source:
        if length + len(line) > chunk_size:
            if chunk.count('`') % 2 == 1:
                prefix = re.findall(pattern, chunk)
                chunk += '```'
                chunks.append(chunk)

                chunk = prefix[-1]
                length = len(chunk)
            else:
                chunks.append(chunk)
                chunk = ""
                length = 0

        if (line.count('`') % 6 == 0):
            line = line.replace('```', '\\`\\`\\`')

        chunk += line
        length += len(line)

        if (line[-3:] != '```'):
            chunk += '\n'
            length += 1

    if chunk != "":
        chunks.append(chunk)
    return chunks


def parse_key(key):
    s = key.split('_')
    res = ""
    for i in range(0, len(s)):
        res += ((s[i][0].upper() + s[i][1:]) if i == 0 else s[i]) + " "
    return res


def ytdl_extract_info(url, download=True):
    with YoutubeDL(public_config.YTDL_OPTIONS) as ytdl:
        return ytdl.extract_info(url, download=download)


def yt_search(query, max_results=5):
    return YoutubeSearch(query, max_results=max_results).to_dict()


async def set_bitrate(guild):
    voice_channels = guild.voice_channels
    bitrate_value = public_config.bitrate_values[guild.premium_tier]
    for channel in voice_channels:
        if channel.bitrate != bitrate_value:
            await channel.edit(bitrate=bitrate_value)


class ServerOptionDataType(Enum):
    INT = 1,
    INT_LIST = 2,


class ServerOption(Enum):
    LOG_CHANNEL = 1,
    STATUS_LOG_CHANNEL = 2,
    WELCOME_CHANNEL = 3,
    PRIVATE_CATEGORY = 4,
    PRIVATE_CHANNEL = 5,
    ADMIN_IDS = 6,

    def to_str(self):
        match self:
            case ServerOption.LOG_CHANNEL:
                return "log_channel"
            case ServerOption.WELCOME_CHANNEL:
                return "welcome_channel"
            case ServerOption.STATUS_LOG_CHANNEL:
                return "status_log_channel"
            case ServerOption.PRIVATE_CATEGORY:
                return "private_category"
            case ServerOption.PRIVATE_CHANNEL:
                return "private_channel"
            case ServerOption.ADMIN_IDS:
                return "admin_ids"
            case _:
                return "unknown"

    def get_type(self):
        match self:
            case ServerOption.LOG_CHANNEL:
                return ServerOptionDataType.INT
            case ServerOption.WELCOME_CHANNEL:
                return ServerOptionDataType.INT
            case ServerOption.STATUS_LOG_CHANNEL:
                return ServerOptionDataType.INT
            case ServerOption.PRIVATE_CATEGORY:
                return ServerOptionDataType.INT
            case ServerOption.PRIVATE_CHANNEL:
                return ServerOptionDataType.INT
            case ServerOption.ADMIN_IDS:
                return ServerOptionDataType.INT_LIST
            case _:
                return "unknown"


async def ensure_server_option_table():
    db = await aiosqlite.connect('bot_database.db')
    await db.execute('''CREATE TABLE IF NOT EXISTS server_options (
                        guild_id TEXT PRIMARY KEY,
                        log_channel TEXT,
                        status_log_channel TEXT,
                        welcome_channel TEXT,
                        private_category TEXT,
                        private_channel TEXT,
                        admin_ids TEXT
                     )''')
    await db.commit()
    await db.close()


async def request_server_option(guild_id, option: ServerOption):
    if not guild_id:
        return None
    opt_str = option.to_str()
    if opt_str == "unknown":
        return None
    await ensure_server_option_table()
    db = await aiosqlite.connect('bot_database.db')
    cursor = await db.cursor()
    await cursor.execute(f"SELECT {opt_str} FROM server_options WHERE guild_id = ?", (str(guild_id),))
    res = await cursor.fetchone()
    await db.close()
    if not res:
        return None
    return res[0]


async def get_server_option(guild_id, option: ServerOption):
    ans = await request_server_option(guild_id, option)
    opt_type = option.get_type()
    match opt_type:
        case ServerOptionDataType.INT:
            if not ans:
                return None
            else:
                return int(ans)
        case ServerOptionDataType.INT_LIST:
            if not ans:
                return []
            else:
                return eval(ans)
    return None


async def set_server_option(guild_id, option: ServerOption, value):
    if not guild_id:
        return
    opt_str = option.to_str()
    if opt_str == "unknown":
        return None
    await ensure_server_option_table()
    db = await aiosqlite.connect('bot_database.db')
    cursor = await db.cursor()
    await cursor.execute(f"INSERT OR IGNORE INTO server_options (guild_id) VALUES(?)", (str(guild_id),))
    await cursor.execute(f"UPDATE server_options SET {opt_str} = ? WHERE guild_id = ?", (str(value), str(guild_id),))
    await db.commit()
    await db.close()
