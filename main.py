import asyncio
import configs.private_config
import concurrent.futures as process_pool

from bots.music_leader import MusicBotLeader
from bots.music_instance import MusicBotInstance
from bots.log_bot import AutoLog
from bots.admin_bot import AdminBot

from helpers.file_logger import FileLogger


async def main():
    pool = process_pool.ProcessPoolExecutor()
    file_logger = FileLogger(True)

    leaders = []
    instances = []
    admins = []
    loggers = []
    tasks = []

    for specification in configs.private_config.bots:
        bot = None
        if specification[1] == "MusicLeader":
            bot = MusicBotLeader(
                specification[0], specification[2], file_logger, pool)
            leaders.append(bot)
            instances.append(bot)
        elif specification[1] == "MusicInstance":
            bot = MusicBotInstance(
                specification[0], specification[2], file_logger, pool)
            instances.append(bot)
        elif specification[1] == "Logger":
            bot = AutoLog(specification[0], specification[2], file_logger)
            loggers.append(bot)
        elif specification[1] == "Admin":
            bot = AdminBot(specification[0], specification[2], file_logger)
            admins.append(bot)
        else:
            print(f"WARNING: There is no bot type {specification[1]}, this bot specification will be ignored")
            continue
        tasks.append(bot.run())
    if len(admins) > 0:
        if len(loggers) == 0:
            print(f"FATAL: Admin bot must have logger bot")
            return
        if len(loggers) > 1:
            print(f"WARNING: Created more than one logger bot. Only first one will be used in other bots")
    for leader in leaders:
        for instance in instances:
            if leader != instance:
                leader.add_instance(instance)
    for admin in admins:
        for instance in instances:
            admin.add_music_instance(instance)
        admin.set_log_bot(loggers[0])
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
