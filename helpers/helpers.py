import disnake
import time
import re
import aiosqlite
import asyncio
from typing import List
from datetime import datetime, timezone
from yt_dlp import YoutubeDL
from youtube_search import YoutubeSearch
from enum import Enum
from typing import Any

import configs.private_config as private_config
import configs.public_config as public_config
import helpers.embedder as embedder


class Rank:
    role_id: int
    voice_xp: int
    remove_on_promotion: bool

    def __init__(self, role_id: int, voice_xp: int, remove_on_promotion: bool):
        self.role_id = role_id
        self.voice_xp = voice_xp
        self.remove_on_promotion = remove_on_promotion


async def is_admin(member) -> bool:
    return member.guild and member.id in await get_guild_option(member.guild.id, GuildOption.ADMIN_LIST) or is_supreme_being(member)


def is_supreme_being(member) -> bool:
    try:
        if member.id in private_config.supreme_beings:
            return True
        else:
            return False
    except:
        return False


async def is_untouchable(member) -> bool:
    return member.guild and member.id in await get_guild_option(member.guild.id, GuildOption.UNTOUCHABLES_LIST)


def get_duration(info) -> str:
    if type(info) == str or ("live_status" in info and info['live_status'] == "is_live") or info['duration'] == 0:
        ans = "Live"
    else:
        ans = time.strftime('%H:%M:%S', time.gmtime(info['duration']))
        days = info['duration'] // 86400
        if days > 10:
            ans = f"{days}:{ans}"
        elif days > 0:
            ans = f"0{days}:{ans}"
    return ans


def is_mentioned(member, message) -> bool:
    for role in message.role_mentions:
        if role in member.roles:
            return True
    if member in message.mentions:
        return True
    return False


async def create_private(member) -> None:
    category_id = await get_guild_option(member.guild.id, GuildOption.PRIVATE_CATEGORY)
    if not category_id:
        return
    possible_channel_name = f"{member.display_name}'s private"

    guild = member.guild
    category = guild.get_channel(int(category_id))

    ff, tmp_channel = await try_function(category.create_voice_channel, True, name=possible_channel_name)
    if not ff:
        return

    ff, _ = await try_function(tmp_channel.set_permissions, True, guild.default_role, view_channel=False)
    if not ff:
        await try_function(tmp_channel.delete, True)
        return

    await try_function(member.move_to, True, tmp_channel)

    perms = tmp_channel.overwrites_for(member)
    perms.view_channel = True
    perms.manage_permissions = True
    perms.manage_channels = True
    await try_function(tmp_channel.set_permissions, True, member, overwrite=perms)
    await try_function(tmp_channel.edit, True, bitrate=public_config.bitrate_values[member.guild.premium_tier])


async def unmute_bots(member) -> bool:
    ff = False
    if member.id in private_config.bot_ids.values():
        if member.voice.mute:
            await try_function(member.edit, True, mute=False)
            ff = True
        if member.voice.deaf:
            await try_function(member.edit, True, deafen=False)
            ff = True
    return ff


async def unmute_admin(member) -> bool:
    ff = False
    if await is_admin(member) or await is_untouchable(member):
        if member.voice.mute:
            await try_function(member.edit, True, mute=False)
            ff = True
        if member.voice.deaf:
            await try_function(member.edit, True, deafen=False)
            ff = True

        try:
            entry = await member.guild.audit_logs(limit=2, action=disnake.AuditLogAction.member_update).flatten()
        except:
            return ff

        if len(entry) < 2:
            return ff
        entry = entry[1]
        delta = datetime.now(timezone.utc) - entry.created_at
        if entry.user != member and entry.user.id not in private_config.bot_ids.values() and (delta.total_seconds() < 2) and (not await is_admin(entry.user) and not await is_untouchable(entry.user)):
            await try_function(entry.user.move_to, True, None)
            await try_function(entry.user.timeout, True, duration=60, reason="Attempt attacking the Supreme Being")
    return ff


async def check_admin_kick(member) -> bool:
    ff = False
    if await is_admin(member) or await is_untouchable(member):
        try:
            entry = await member.guild.audit_logs(limit=1, action=disnake.AuditLogAction.member_disconnect).flatten()
        except:
            return ff
        if not entry:
            return ff
        entry = entry[0]
        delta = datetime.now(timezone.utc) - entry.created_at
        if entry.user != member and entry.user.id not in private_config.bot_ids.values() and delta.total_seconds() < 2 and (not await is_admin(entry.user) and not await is_untouchable(entry.user)):
            await try_function(entry.user.move_to, True, None)
            await try_function(entry.user.timeout, True, duration=60, reason="Attempt attacking the Supreme Being")
            ff = True
    return ff


async def check_mentions(message, bot):
    if len(message.role_mentions) > 0 or len(message.mentions) > 0:
        client = message.guild.me

        if is_mentioned(client, message):

            if message.mention_everyone:
                return

            if await is_admin(message.author):
                if "ping" in message.content.lower() or "пинг" in message.content.lower():
                    return await message.reply(f"Yes, my master. My ping is {round(bot.latency*1000)} ms")
                else:
                    return await message.reply("At your service, my master.")
            else:
                await try_function(message.author.timeout, True, duration=10, reason="Ping by inferior life form")
                return await message.reply(f"How dare you tag me? Know your place, trash")


def get_guild_name(guild) -> str:
    if guild.name == "Nazarick":
        return "the Great Tomb of Nazarick"
    return guild.name


def get_members_leveling_system(members) -> int:
    cnt = len(members)
    for member in members:
        if member.bot or member.voice.self_deaf or member.voice.self_mute or member.voice.deaf or member.voice.mute:
            cnt -= 1
    return cnt


def get_true_members_count(members) -> int:
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


def parse_key(key) -> str:
    s = key.split('_')
    res = ""
    for i in range(0, len(s)):
        res += ((s[i][0].upper() + s[i][1:]) if i == 0 else s[i]) + " "
    return res


def ytdl_extract_info(url, download=False):
    try:
        with YoutubeDL(public_config.YTDL_OPTIONS) as ytdl:
            return ytdl.extract_info(url, download=download)
    except:
        return None


def yt_search(query, max_results=5) -> (list | str):
    try:
        return YoutubeSearch(query, max_results=max_results).to_dict()
    except:
        return None


async def set_bitrate(guild) -> bool:
    ff = True
    voice_channels = guild.voice_channels
    bitrate_value = public_config.bitrate_values[guild.premium_tier]
    for channel in voice_channels:
        if channel.bitrate != bitrate_value:
            ff, _ = await try_function(channel.edit, True, bitrate=bitrate_value)

    return ff


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
    GIVEAWAY_MESSAGE = 10,
    GIVEAWAY_ROLE = 11,

    def to_str(self) -> (str | None):
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
            case GuildOption.GIVEAWAY_MESSAGE:
                return "giveaway_message"
            case GuildOption.GIVEAWAY_ROLE:
                return "giveaway_role"
            case _:
                return None

    def get_table(self) -> (str | None):
        match self:
            case GuildOption.LOG_CHANNEL | GuildOption.WELCOME_CHANNEL | GuildOption.STATUS_LOG_CHANNEL | GuildOption.PRIVATE_CATEGORY | GuildOption.PRIVATE_CHANNEL | GuildOption.ADMIN_LIST | GuildOption.UNTOUCHABLES_LIST | GuildOption.GIVEAWAY_MESSAGE | GuildOption.GIVEAWAY_ROLE:
                return "server_options"
            case GuildOption.RANK_LIST | GuildOption.RANK:
                return "ranks_data"
            case _:
                return None


def convert_to_python(option: GuildOption, value) -> (int | list):
    to_int = [GuildOption.LOG_CHANNEL, GuildOption.WELCOME_CHANNEL, GuildOption.STATUS_LOG_CHANNEL, GuildOption.PRIVATE_CATEGORY, GuildOption.PRIVATE_CHANNEL, GuildOption.GIVEAWAY_MESSAGE, GuildOption.GIVEAWAY_ROLE]
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


async def ensure_tables() -> None:
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users_xp_data (
                            guild_id INTEGER,
                            user_id INTEGER,
                            voice_xp INTEGER,
                            text_xp INTEGER,
                            last_activity INTEGER,
                            UNIQUE(guild_id, user_id)
                        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS ranks_data (
                            guild_id INTEGER,
                            rank_id INTEGER,
                            voice_xp INTEGER,
                            remove_flag INTEGER,
                            UNIQUE(guild_id, rank_id)
                        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS server_options (
                            guild_id INTEGER PRIMARY KEY,
                            log_channel INTEGER,
                            status_log_channel INTEGER,
                            welcome_channel INTEGER,
                            private_category INTEGER,
                            private_channel INTEGER,
                            admin_list TEXT,
                            untouchables_list TEXT,
                            giveaway_message INTEGER,
                            giveaway_role INTEGER
                        )''')

        await db.commit()


async def ensure_tables_logger() -> None:
    async with aiosqlite.connect('db/logs.db', timeout=1000) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS status (
                            date TEXT,
                            time TEXT,
                            user_id INTEGER,
                            comment TEXT
                        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS gpt (
                            date TEXT,
                            time TEXT,
                            user_id INTEGER,
                            query TEXT,
                            response TEXT
                        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS bots (
                            date TEXT,
                            time TEXT,
                            tag TEXT,
                            comment TEXT
                        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS common (
                            guild_id INTEGER,
                            date TEXT,
                            time TEXT,
                            tag TEXT,
                            comment TEXT
                        )''')

        await db.commit()


async def request_guild_option(guild_id: int, option: GuildOption):
    if not guild_id:
        return None
    opt_str = option.to_str()
    opt_table = option.get_table()
    if not opt_str or not opt_table:
        raise f"Wrong option {option}"
    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()

        match option:
            case GuildOption.LOG_CHANNEL | GuildOption.WELCOME_CHANNEL | GuildOption.STATUS_LOG_CHANNEL | GuildOption.PRIVATE_CATEGORY | GuildOption.PRIVATE_CHANNEL | GuildOption.ADMIN_LIST | GuildOption.UNTOUCHABLES_LIST | GuildOption.GIVEAWAY_MESSAGE | GuildOption.GIVEAWAY_ROLE:
                await cursor.execute(f"SELECT {opt_str} FROM {option.get_table()} WHERE guild_id = ?", (guild_id,))
                res = await cursor.fetchone()
            case GuildOption.RANK_LIST:
                await cursor.execute(f"SELECT {opt_str} FROM {option.get_table()} WHERE guild_id = ?", (guild_id,))
                res = await cursor.fetchall()
            case _:
                raise f"Wrong option {option}"
    return res


async def get_guild_option(guild_id: int, option: GuildOption):
    ans = await request_guild_option(guild_id, option)
    return convert_to_python(option, ans)


async def add_guild_option(guild_id: int, option: GuildOption, value):
    if not guild_id:
        return

    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        match option:
            case GuildOption.RANK:
                await cursor.execute(f"SELECT {option.to_str()} FROM {option.get_table()} WHERE guild_id = ? AND rank_id = ?", (guild_id, value.role_id,))
                res = await cursor.fetchone()
                res = bool(res)
                if not res:
                    await cursor.execute(f"INSERT INTO {option.get_table()} (guild_id, {option.to_str()}) VALUES(?, ?, ?, ?)", (guild_id, int(value.voice_xp), value.role_id, int(value.remove_on_promotion)))
            case _:
                raise f"Wrong option {option}"
        await db.commit()
    return not res


async def remove_guild_option(guild_id: int, option: GuildOption, value):
    if not guild_id:
        return
    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        match option:
            case GuildOption.RANK:
                await cursor.execute(f"SELECT {option.to_str()} FROM {option.get_table()} WHERE guild_id = ? AND rank_id = ?", (guild_id, int(value),))
                res = await cursor.fetchone()
                res = bool(res)
                if res:
                    await cursor.execute(f"DELETE FROM {option.get_table()} WHERE guild_id = ? AND rank_id = ? ", (guild_id, int(value),))
            case _:
                raise f"Wrong option {option}"
        await db.commit()
    return res


async def set_guild_option(guild_id: int, option: GuildOption, value):
    if not guild_id:
        return
    opt_str = option.to_str()
    opt_table = option.get_table()
    if not opt_str or not opt_table:
        raise f"Wrong option {option}"
    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        await cursor.execute(f"INSERT OR IGNORE INTO {opt_table} (guild_id) VALUES(?)", (guild_id,))
        if value:
            if option == GuildOption.ADMIN_LIST or option == GuildOption.UNTOUCHABLES_LIST:
                await cursor.execute(f"UPDATE server_options SET {opt_str} = ? WHERE guild_id = ?", (str(value), guild_id,))
            else:
                await cursor.execute(f"UPDATE server_options SET {opt_str} = ? WHERE guild_id = ?", (int(value), guild_id,))
        else:
            await cursor.execute(f"UPDATE server_options SET {opt_str} = NULL WHERE guild_id = ?", (guild_id,))
        await db.commit()


async def get_user_xp(guild_id: int, user_id: int):
    if not guild_id or not user_id:
        return None

    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        await cursor.execute(f"SELECT voice_xp, text_xp FROM users_xp_data WHERE guild_id = ? AND user_id = ?", (guild_id, user_id,))
        res = await cursor.fetchone()
    if res:
        return res["voice_xp"], res["text_xp"]
    else:
        return 0, 0


async def get_guild_top(guild_id: int, xp_type_voice: bool):
    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        await cursor.execute(f"SELECT user_id, voice_xp, text_xp FROM users_xp_data WHERE guild_id = ?", (guild_id,))
        users = await cursor.fetchall()

    if not users:
        return []

    ans = []
    users = sorted(users, key=lambda user: user[(2, 1)[xp_type_voice]], reverse=True)

    for user in users:
        if user[(2, 1)[xp_type_voice]] != 0:
            ans.append([int(user["user_id"]), user["voice_xp"], user["text_xp"]])
    del users
    return ans


async def get_next_rank(member: disnake.Member):
    v_xp, t_xp = await get_user_xp(member.guild.id, member.id)
    ranks = await get_guild_option(member.guild.id, GuildOption.RANK_LIST)
    ranks = sort_ranks(ranks)
    max_rank = None
    next_rank = None
    for rank in ranks:
        if rank.voice_xp <= v_xp and rank.remove_on_promotion:
            max_rank = rank
        elif rank.remove_on_promotion:
            next_rank = rank
            break
    return max_rank, next_rank


async def modify_roles(member: disnake.Member, roles_to_remove: List[Any] = [], roles_to_add: List[Any] = []) -> None:
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
    asyncio.create_task(try_function(member.remove_roles, True, *roles))


async def add_roles_and_notify(member: disnake.Member, roles: List[disnake.Role]) -> None:
    if len(roles) == 0:
        return

    await try_function(member.add_roles, True, *roles)
    embed = embedder.role_notification(member.guild, roles)
    await try_function(member.send, True, embed=embed)


async def set_user_xp(guild_id: int, user_id: int, voice_xp: int | None = None, text_xp: int | None = None) -> None:
    if not guild_id or not user_id or (voice_xp is None and text_xp is None):
        return None

    last_activity = int(time.time())
    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        await cursor.execute(f"INSERT OR IGNORE INTO users_xp_data (guild_id, user_id, voice_xp, text_xp) VALUES(?,?,?,?)", (guild_id, user_id, 0, 0))
        if voice_xp is not None:
            await cursor.execute(f"UPDATE users_xp_data SET voice_xp = ?, last_activity = ? WHERE guild_id = ? AND user_id = ?", (voice_xp, last_activity, guild_id, user_id,))
        if text_xp is not None:
            await cursor.execute(f"UPDATE users_xp_data SET text_xp = ?, last_activity = ? WHERE guild_id = ? AND user_id = ?", (text_xp, last_activity, guild_id, user_id,))
        await db.commit()

async def get_activity_info():
    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        await cursor.execute(f"SELECT guild_id, user_id, last_activity FROM users_xp_data")
        res = await cursor.fetchall()
        return res


async def reset_xp(guild_id: int) -> None:
    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        await cursor.execute(f"DELETE FROM users_xp_data WHERE guild_id = ?", (guild_id,))
        await db.commit()


async def reset_ranks(guild_id: int) -> None:
    await ensure_tables()
    async with aiosqlite.connect('db/bot_database.db', timeout=1000) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        await cursor.execute(f"DELETE FROM ranks_data WHERE guild_id = ?", (guild_id,))
        await db.commit()


async def add_user_xp(guild_id: int, user_id: int, voice_xp: int | None = None, text_xp: int | None = None) -> None:
    if not guild_id or not user_id or (not voice_xp and not text_xp):
        return None

    v_xp, t_xp = await get_user_xp(guild_id, user_id)
    if voice_xp:
        v_xp += voice_xp
    if text_xp:
        t_xp += text_xp
    await set_user_xp(guild_id, user_id, v_xp, t_xp)


def sort_ranks(ranks: list, reverse: bool = False) -> list:
    return sorted(ranks, key=lambda rank: (rank.voice_xp, rank.remove_on_promotion,), reverse=reverse)


async def try_function(function, await_flag: bool, *args, **kwargs):
    tmp = None
    try:
        if await_flag:
            tmp = await function(*args, **kwargs)
        else:
            tmp = function(*args, **kwargs)
        return True, tmp
    except:
        return False, tmp


async def run_delayed_tasks(tasks: list) -> None:
    await asyncio.gather(*tasks)


async def dm_user(message: str, user_id: int, bot, embed=None, components=None, view=None, suppress_embeds=False) -> bool:
    user = bot.get_user(user_id)
    if not user:
        return False
    ff, _ = await try_function(user.send, True, message, embed=embed, components=components, view=view, suppress_embeds=suppress_embeds)
    return ff


async def add_playlist_delayed_task(function, await_flag: bool, playlist_future: asyncio.Future, *args, **kwargs) -> None:
    while not playlist_future.done():
        await asyncio.sleep(1)
    if await_flag:
        await function(*args, **kwargs)
    else:
        function(*args, **kwargs)


def get_user_num_badge(index: int) -> str:
    match index:
        case 0:
            pos = public_config.emojis['first_place']
        case 1:
            pos = public_config.emojis['second_place']
        case 2:
            pos = public_config.emojis['third_place']
        case _:
            pos = f"{index+1}."
    return pos


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return (f"#{hex(r)[2:]:0>2}{hex(g)[2:]:0>2}{hex(b)[2:]:0>2}").upper()


def get_queue_duration(queue: list) -> None | str:
    ans = ""
    duration = 0
    live_tracks = 0

    for song in queue:
        if not song.track_info.done():
            continue
        info = song.track_info.result()
        if (isinstance(info, str)):
            live_tracks += 1
        else:
            if "live_status" in info and info['live_status'] == "is_live" or info['duration'] == 0:
                live_tracks += 1
            else:
                duration += info['duration']

    if duration > 0:
        duration = {'duration': duration}
        ans = f"**Queue duration: **{get_duration(duration)}"
        if live_tracks > 0:
            ans += f" and {('Live', f'{live_tracks} live tracks')[live_tracks > 1]}"
    else:
        if live_tracks == 0:
            return None
        else:
            return f"**Queue duration: ** {('Live', f'{live_tracks} live tracks')[live_tracks > 1]}"
    return ans
