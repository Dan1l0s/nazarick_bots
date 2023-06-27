import asyncio
import concurrent.futures as pool

from music_leader import MusicBotLeader
from music_instance import MusicBotInstance
from file_logger import FileLogger
from log_bot import AutoLog


async def main():
    process_pool = pool.ProcessPoolExecutor()
    file_logger = FileLogger(True)

    music_leader = MusicBotLeader("music_main", file_logger, process_pool)
    music_instance1 = MusicBotInstance("music_assistant1", file_logger, process_pool)
    music_instance2 = MusicBotInstance("music_assistant2", file_logger, process_pool)
    music_instance3 = MusicBotInstance("music_assistant3", file_logger, process_pool)

    music_leader.add_instance(music_instance1)
    music_leader.add_instance(music_instance2)
    music_leader.add_instance(music_instance3)

    log_bot = AutoLog("logs", file_logger)

    tasks = []
    tasks.append(music_leader.run())

    tasks.append(music_instance1.run())
    tasks.append(music_instance2.run())
    tasks.append(music_instance3.run())
    tasks.append(log_bot.run())

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
