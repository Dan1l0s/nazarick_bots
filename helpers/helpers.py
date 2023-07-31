import disnake
from typing import List
from datetime import datetime, timezone
import time
import re
import aiosqlite
from yt_dlp import YoutubeDL
from youtube_search import YoutubeSearch
from enum import Enum

import asyncio
import configs.private_config as private_config
import configs.public_config as public_config
from helpers.embedder import Embed


class Rank:
    role_id: int
    voice_xp: int
    remove_on_promotion: bool

    def __init__(self, role_od: int, voice_xp: int, remove_on_promotion: bool):
        self.role_id = role_od
        self.voice_xp = voice_xp
        self.remove_on_promotion = remove_on_promotion


async def is_admin(member):
    return member.guild and member.id in await get_guild_option(member.guild.id, GuildOption.ADMIN_LIST) or is_supreme_being(member)


def is_supreme_being(member):
    try:
        if member.id in private_config.supreme_beings:
            return True
        else:
            return False
    except:
        return False


async def is_untouchable(member):
    return member.guild and member.id in await get_guild_option(member.guild.id, GuildOption.UNTOUCHABLES_LIST)


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
    category_id = await get_guild_option(member.guild.id, GuildOption.PRIVATE_CATEGORY)
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
    await tmp_channel.edit(bitrate=public_config.bitrate_values[member.guild.premium_tier])


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
    if await is_admin(member) or await is_untouchable(member):
        if member.voice.mute:
            await member.edit(mute=False)
            ff = True
        if member.voice.deaf:
            await member.edit(deafen=False)
            ff = True

        entry = await member.guild.audit_logs(limit=2, action=disnake.AuditLogAction.member_update).flatten()
        if len(entry) < 2:
            return ff
        entry = entry[1]
        delta = datetime.now(timezone.utc) - entry.created_at
        if entry.user != member and entry.user.id not in private_config.bot_ids.values() and (delta.total_seconds() < 2) and entry.user.id not in await get_guild_option(member.guild.id, GuildOption.ADMIN_LIST):
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

    amount = delta.seconds // 3600
    if amount > 0:
        if amount == 1:
            return "an hour ago"
        else:
            return f"{amount} hours ago"

    amount = delta.seconds // 60
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


class GuildOption(Enum):
    LOG_CHANNEL = 1,
    STATUS_LOG_CHANNEL = 2,
    WELCOME_CHANNEL = 3,
    PRIVATE_CATEGORY = 4,
    PRIVATE_CHANNEL = 5,
    ADMIN_LIST = 6,
    RANK_LIST = 7,
    RANK = 8,
    UNTOUCHABLES_LIST = 9,

    def to_str(self):
        match self:
            case GuildOption.LOG_CHANNEL:
                return "log_channel"
            case GuildOption.WELCOME_CHANNEL:
                return "welcome_channel"
            case GuildOption.STATUS_LOG_CHANNEL:
                return "status_log_channel"
            case GuildOption.PRIVATE_CATEGORY:
                return "private_category"
            case GuildOption.PRIVATE_CHANNEL:
                return "private_channel"
            case GuildOption.ADMIN_LIST:
                return "admin_list"
            case GuildOption.RANK_LIST | GuildOption.RANK:
                return "voice_xp, rank_id, remove_flag"
            case GuildOption.UNTOUCHABLES_LIST:
                return "untouchables_list"
            case _:
                return None

    def get_table(self):
        match self:
            case GuildOption.LOG_CHANNEL | GuildOption.WELCOME_CHANNEL | GuildOption.STATUS_LOG_CHANNEL | GuildOption.PRIVATE_CATEGORY | GuildOption.PRIVATE_CHANNEL | GuildOption.ADMIN_LIST | GuildOption.UNTOUCHABLES_LIST:
                return "server_options"
            case GuildOption.RANK_LIST | GuildOption.RANK:
                return "ranks_data"
            case _:
                return None


def convert_to_python(option: GuildOption, value):
    to_int = [GuildOption.LOG_CHANNEL, GuildOption.WELCOME_CHANNEL, GuildOption.STATUS_LOG_CHANNEL, GuildOption.PRIVATE_CATEGORY, GuildOption.PRIVATE_CHANNEL]
    to_int_list = [GuildOption.ADMIN_LIST, GuildOption.UNTOUCHABLES_LIST]
    match option:
        case option if option in to_int:
            if not value or not value[0]:
                return None
            else:
                return int(value[0])
        case option if option in to_int_list:
            if not value or not value[0]:
                return []
            else:
                return eval(value[0])
        case GuildOption.RANK_LIST:
            if not value:
                return []
            else:
                ans = []
                for rank in value:
                    ans.append(Rank(int(rank["rank_id"]), rank["voice_xp"], bool(rank["remove_flag"])))
                return ans
        case _:
            raise f"Wrong option {option}"


async def ensure_tables():
    db = await aiosqlite.connect('bot_database.db')
    await db.execute('''CREATE TABLE IF NOT EXISTS users_xp_data (guild_id TEXT, user_id TEXT, voice_xp INTEGER, text_xp INTEGER, UNIQUE(guild_id, user_id))''')
    await db.execute('''CREATE TABLE IF NOT EXISTS ranks_data (guild_id TEXT, rank_id TEXT, voice_xp INTEGER,  remove_flag INTEGER, UNIQUE(guild_id, rank_id))''')
    await db.execute('''CREATE TABLE IF NOT EXISTS server_options (
                        guild_id TEXT PRIMARY KEY,
                        log_channel TEXT,
                        status_log_channel TEXT,
                        welcome_channel TEXT,
                        private_category TEXT,
                        private_channel TEXT,
                        admin_list TEXT,
                        untouchables_list TEXT
                     )''')
    await db.commit()
    await db.close()


async def request_guild_option(guild_id, option: GuildOption):
    if not guild_id:
        return None
    opt_str = option.to_str()
    opt_table = option.get_table()
    if not opt_str or not opt_table:
        raise f"Wrong option {option}"
    await ensure_tables()
    db = await aiosqlite.connect('bot_database.db')
    db.row_factory = aiosqlite.Row
    cursor = await db.cursor()

    match option:
        case GuildOption.LOG_CHANNEL | GuildOption.WELCOME_CHANNEL | GuildOption.STATUS_LOG_CHANNEL | GuildOption.PRIVATE_CATEGORY | GuildOption.PRIVATE_CHANNEL | GuildOption.ADMIN_LIST | GuildOption.UNTOUCHABLES_LIST:
            await cursor.execute(f"SELECT {opt_str} FROM {option.get_table()} WHERE guild_id = ?", (str(guild_id),))
            res = await cursor.fetchone()
        case GuildOption.RANK_LIST:
            await cursor.execute(f"SELECT {opt_str} FROM {option.get_table()} WHERE guild_id = ?", (str(guild_id),))
            res = await cursor.fetchall()
        case _:
            await db.close()
            raise f"Wrong option {option}"
    await db.close()
    return res


async def get_guild_option(guild_id, option: GuildOption):
    ans = await request_guild_option(guild_id, option)
    return convert_to_python(option, ans)


async def add_guild_option(guild_id, option: GuildOption, value):
    if not guild_id:
        return

    await ensure_tables()
    db = await aiosqlite.connect('bot_database.db')
    db.row_factory = aiosqlite.Row
    cursor = await db.cursor()
    match option:
        case GuildOption.RANK:
            await cursor.execute(f"SELECT {option.to_str()} FROM {option.get_table()} WHERE guild_id = ? AND rank_id = ?", (str(guild_id), str(value.role_id),))
            res = await cursor.fetchone()
            res = bool(res)
            if not res:
                await cursor.execute(f"INSERT INTO {option.get_table()} (guild_id, {option.to_str()}) VALUES(?, ?, ?, ?)", (str(guild_id), int(value.voice_xp), str(value.role_id), int(value.remove_on_promotion)))
        case _:
            await db.close()
            raise f"Wrong option {option}"
    await db.commit()
    await db.close()
    return not res


async def remove_guild_option(guild_id, option: GuildOption, value):
    if not guild_id:
        return
    await ensure_tables()
    db = await aiosqlite.connect('bot_database.db')
    db.row_factory = aiosqlite.Row
    cursor = await db.cursor()
    match option:
        case GuildOption.RANK:
            await cursor.execute(f"SELECT {option.to_str()} FROM {option.get_table()} WHERE guild_id = ? AND rank_id = ?", (str(guild_id), str(value),))
            res = await cursor.fetchone()
            res = bool(res)
            if res:
                await cursor.execute(f"DELETE FROM {option.get_table()} WHERE guild_id = ? AND rank_id = ? ", (str(guild_id), str(value),))
        case _:
            await db.close()
            raise f"Wrong option {option}"
    await db.commit()
    await db.close()
    return res


async def set_guild_option(guild_id, option: GuildOption, value):
    if not guild_id:
        return
    opt_str = option.to_str()
    opt_table = option.get_table()
    if not opt_str or not opt_table:
        raise f"Wrong option {option}"
    await ensure_tables()
    db = await aiosqlite.connect('bot_database.db')
    db.row_factory = aiosqlite.Row
    cursor = await db.cursor()
    await cursor.execute(f"INSERT OR IGNORE INTO {opt_table} (guild_id) VALUES(?)", (str(guild_id),))
    await cursor.execute(f"UPDATE server_options SET {opt_str} = ? WHERE guild_id = ?", (str(value), str(guild_id),))
    await db.commit()
    await db.close()


async def get_user_xp(guild_id: int, user_id: int):
    if not guild_id or not user_id:
        return None

    await ensure_tables()
    db = await aiosqlite.connect('bot_database.db')
    db.row_factory = aiosqlite.Row
    cursor = await db.cursor()
    await cursor.execute(f"SELECT voice_xp, text_xp FROM users_xp_data WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id),))
    res = await cursor.fetchone()
    await db.close()
    if res:
        return res["voice_xp"], res["text_xp"]
    else:
        return 0, 0


async def modify_roles(member: disnake.Member, roles_to_remove: List[any] = [], roles_to_add: List[any] = []):
    if not member:
        return
    if not member.guild.me.guild_permissions.manage_roles:
        return
    guild = member.guild
    highest_role = guild.me.top_role
    roles = []
    for role_id in roles_to_add:
        if role_id in roles_to_remove:
            continue
        role = guild.get_role(int(role_id))
        if role and not role.managed and role < highest_role and role not in member.roles:
            roles.append(role)
    asyncio.create_task(add_roles_and_notify(member, roles))
    roles = []
    for role_id in roles_to_remove:
        if role_id in roles_to_add:
            continue
        role = guild.get_role(int(role_id))
        if role and not role.managed and role < highest_role and role in member.roles:
            roles.append(role)
    asyncio.create_task(member.remove_roles(*roles))


async def add_roles_and_notify(member: disnake.Member, roles: List[disnake.Role]):
    if len(roles) == 0:
        return

    embedder = Embed()
    await member.add_roles(*roles)
    embed = embedder.role_notification(member.guild, roles)
    try:
        await member.send(embed=embed)
    except:
        pass


async def set_user_xp(guild_id: int, user_id: int, voice_xp: int | None = None, text_xp: int | None = None):
    if not guild_id or not user_id or (voice_xp is None and text_xp is None):
        return None

    await ensure_tables()
    db = await aiosqlite.connect('bot_database.db')
    db.row_factory = aiosqlite.Row
    cursor = await db.cursor()
    await cursor.execute(f"INSERT OR IGNORE INTO users_xp_data (guild_id, user_id, voice_xp, text_xp) VALUES(?,?,?,?)", (str(guild_id), str(user_id), 0, 0))
    if voice_xp is not None:
        await cursor.execute(f"UPDATE users_xp_data SET voice_xp = ? WHERE guild_id = ? AND user_id = ?", (voice_xp, str(guild_id), str(user_id),))
    if text_xp is not None:
        await cursor.execute(f"UPDATE users_xp_data SET text_xp = ? WHERE guild_id = ? AND user_id = ?", (text_xp, str(guild_id), str(user_id),))
    await db.commit()
    await db.close()


async def reset_xp(guild_id: int):
    await ensure_tables()
    db = await aiosqlite.connect('bot_database.db')
    db.row_factory = aiosqlite.Row
    cursor = await db.cursor()
    await cursor.execute(f"DELETE FROM users_xp_data WHERE guild_id = ?", (str(guild_id),))
    await db.commit()
    await db.close()


async def reset_ranks(guild_id: int):
    await ensure_tables()
    db = await aiosqlite.connect('bot_database.db')
    db.row_factory = aiosqlite.Row
    cursor = await db.cursor()
    await cursor.execute(f"DELETE FROM ranks_data WHERE guild_id = ?", (str(guild_id),))
    await db.commit()
    await db.close()


async def add_user_xp(guild_id: int, user_id: int, voice_xp: int | None = None, text_xp: int | None = None):
    if not guild_id or not user_id or (not voice_xp and not text_xp):
        return None

    v_xp, t_xp = await get_user_xp(guild_id, user_id)
    if voice_xp:
        v_xp += voice_xp
    if text_xp:
        t_xp += text_xp
    await set_user_xp(guild_id, user_id, v_xp, t_xp)


def sort_ranks(ranks, increasing: bool = True):
    ans = sorted(ranks, key=lambda rank: (rank.voice_xp, rank.remove_on_promotion,))
    if not increasing:
        ans.reverse()
    return ans
