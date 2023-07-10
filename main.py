import asyncio
import concurrent.futures as process_pool

from bots.music_leader import MusicBotLeader
from bots.music_instance import MusicBotInstance
from bots.log_bot import AutoLog
from bots.admin_bot import AdminBot

from helpers.file_logger import FileLogger


async def main():
    pool = process_pool.ProcessPoolExecutor()
    file_logger = FileLogger(True)

    music_leader = MusicBotLeader("music_main", file_logger, pool)
    music_instance1 = MusicBotInstance("music_assistant1", file_logger, pool)
    music_instance2 = MusicBotInstance("music_assistant2", file_logger, pool)
    music_instance3 = MusicBotInstance("music_assistant3", file_logger, pool)

    music_leader.add_instance(music_instance1)
    music_leader.add_instance(music_instance2)
    music_leader.add_instance(music_instance3)

    log_bot = AutoLog("logs", file_logger)

    admin_bot = AdminBot("moderate", file_logger)

    admin_bot.add_music_instance(music_leader)
    admin_bot.add_music_instance(music_instance1)
    admin_bot.add_music_instance(music_instance2)
    admin_bot.add_music_instance(music_instance3)
    admin_bot.set_log_bot(log_bot)

    tasks = []
    tasks.append(music_leader.run())

    tasks.append(music_instance1.run())
    tasks.append(music_instance2.run())
    tasks.append(music_instance3.run())

    tasks.append(log_bot.run())

    tasks.append(admin_bot.run())

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
