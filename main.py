from multiprocessing import Process
from music_leader import MusicBotLeader
from music_instance import MusicBotInstance
from logger import Logger
from threading import Thread
import asyncio


async def main():
    logger = Logger(True)
    music_leader = MusicBotLeader("MusicLeader", logger)
    music_instance = MusicBotInstance("MusicInstance", logger)
    music_leader.add_instance(music_instance)
    await asyncio.gather(music_leader.run(), music_instance.run())

asyncio.run(main())
