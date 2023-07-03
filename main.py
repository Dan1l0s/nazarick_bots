import asyncio
import concurrent.futures as process_pool

from music_leader import MusicBotLeader
from music_instance import MusicBotInstance
from file_logger import FileLogger
from log_bot import AutoLog


async def main():
    pool = process_pool.ProcessPoolExecutor()
    file_logger = FileLogger(True)

    music_leader = MusicBotLeader("music_main", file_logger, pool)
    music_instance1 = MusicBotInstance("music_assistant1", file_logger, pool)
    music_instance2 = MusicBotInstance("music_assistant2", file_logger, pool)
    music_instance3 = MusicBotInstance("music_assistant3", file_logger, pool)

    music_leader.add_instance(music_instance1)


    tasks = []
    tasks.append(music_leader.run())
    tasks.append(music_instance1.run())

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
