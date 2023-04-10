from music_leader import MusicBotLeader
from music_instance import MusicBotInstance
from logger import Logger
import asyncio


async def main():
    logger = Logger(True)
    tasks = []
    music_leader = MusicBotLeader("MusicLeader", logger)
    music_instance = MusicBotInstance("MusicInstance", logger)

    tasks.append(music_leader.run())
    tasks.append(music_instance.run())

    music_leader.add_instance(music_instance)

    await asyncio.gather(*tasks)

asyncio.run(main())
