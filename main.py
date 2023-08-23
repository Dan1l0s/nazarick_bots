import asyncio
import os
import sys
import signal
import functools
from concurrent.futures import ProcessPoolExecutor

import configs.private_config as private_config

from bots.music_leader import MusicBotLeader
from bots.music_instance import MusicBotInstance
from bots.log_bot import LogBot
from bots.admin_bot import AdminBot


async def validate_bots(leaders, instances, admins, loggers):
    if len(leaders) + len(instances) + len(admins) + len(loggers) == 0:
        print(f"No bots to run. You can add some in configs/private_config.py via bots field")
    if len(leaders) > 1:
        print(f"Cannot run more than one MusicLeader at the same time. Please delete a few MusicLeader bots in configs/private_config.py")
        return False
    if len(admins) > 1:
        print(f"Cannot run more than one Admin at the same time. Please delete a few Admin bots in configs/private_config.py")
        return False
    if len(loggers) > 1:
        print(f"Cannot run more than one Logger at the same time. Please delete a few Logger bots in configs/private_config.py")
        return False
    if len(instances) > 0 and len(leaders) == 0:
        print(f"MusicInstance bots may be used only with MusicLeader. Please add MusicLeader bot or delete all existing MusicInstance bots in configs/private_config.py")
        return False
    return True


def on_sigterm(loop, pool):
    pool.shutdown(wait=True, cancel_futures=False)
    loop.stop()
    pass


def worker_init():
    f = open(os.devnull, 'w')
    sys.stdout = f
    sys.stderr = f


async def main():
    os.chdir(os.path.dirname(__file__))
    pool = ProcessPoolExecutor(initializer=worker_init)

    try:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(
            signal.SIGTERM,
            functools.partial(on_sigterm, loop, pool))
    except:
        pass

    leaders = []
    instances = []
    admins = []
    loggers = []
    tasks = []

    for specification in private_config.bots:
        bot = None
        if specification[1] == "MusicLeader":
            bot = MusicBotLeader(
                specification[0], specification[2], pool)
            leaders.append(bot)
            instances.append(bot)
        elif specification[1] == "MusicInstance":
            bot = MusicBotInstance(
                specification[0], specification[2], pool)
            instances.append(bot)
        elif specification[1] == "Logger":
            bot = LogBot(specification[0], specification[2])
            loggers.append(bot)
        elif specification[1] == "Admin":
            bot = AdminBot(specification[0], specification[2])
            admins.append(bot)
        else:
            print(f"""WARNING: There is no bot type {specification[1]},
                this bot specification will be ignored""")
            continue
    if not await validate_bots(leaders, instances, admins, loggers):
        loop = asyncio.get_running_loop()
        loop.stop()
        return
    for leader in leaders:
        for instance in instances:
            if leader != instance:
                leader.add_instance(instance)
    for admin in admins:
        for instance in instances:
            admin.add_music_instance(instance)
        if len(loggers) > 0:
            admin.set_log_bot(loggers[0])

    for instance in instances:
        tasks.append(instance.run())
    for admin in admins:
        tasks.append(admin.run())
    for logger in loggers:
        tasks.append(logger.run())
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
