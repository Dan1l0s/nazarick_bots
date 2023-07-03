import asyncio
import concurrent.futures as pool

from music_leader import MusicBotLeader
from music_instance import MusicBotInstance
from file_logger import FileLogger
from log_bot import AutoLog


async def main():
    
    process_pool = pool.ProcessPoolExecutor()
    file_logger = FileLogger(True)

    music_leader = MusicBotLeader("eclair1", file_logger, process_pool)
    music_instance1 = MusicBotInstance("eclair2", file_logger, process_pool)
    music_leader.add_instance(music_instance1)


    tasks = []
    tasks.append(music_leader.run())
    tasks.append(music_instance1.run())

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
