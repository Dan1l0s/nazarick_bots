from music_leader import MusicBotLeader
from music_instance import MusicBotInstance
from logger import Logger
import time
import asyncio


async def main():
    logger = Logger(True)

    music_leader = MusicBotLeader("music_main", logger)
    music_instance1 = MusicBotInstance("music_assistant1", logger)
    music_instance2 = MusicBotInstance("music_assistant2", logger)

    music_leader.add_instance(music_instance1)
    music_leader.add_instance(music_instance2)

    tasks = []
    tasks.append(music_leader.run())
    tasks.append(music_instance1.run())
    tasks.append(music_instance2.run())

    await asyncio.gather(*tasks)

asyncio.run(main())
