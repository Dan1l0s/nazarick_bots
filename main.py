from music_leader import MusicBotLeader
from music_instance import MusicBotInstance
from logger import Logger
import time
import asyncio



async def main():
    logger = Logger(True)
    music_leader = MusicBotLeader("MusicLeader", logger)
    music_instance = MusicBotInstance("MusicInstance", logger)
    music_leader.add_instance(music_instance)

    tasks = []
    tasks.append(music_leader.run())
    tasks.append(music_instance.run())

    await asyncio.gather(*tasks)

asyncio.run(main())
