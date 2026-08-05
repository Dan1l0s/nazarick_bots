"""Entry point: builds every bot listed in configs/private_config.py, wires the
cross-bot references, and runs them all concurrently on one event loop.

Wiring performed here (this is the object graph the whole project depends on):
  - each MusicLeader gets a reference to every MusicInstance, so it can
    delegate slash commands to whichever bot is free
  - the Admin bot gets references to every music instance and to the Logger,
    for the owner-only cross-bot commands
  - a single shared ThreadPoolExecutor is handed to every music bot for
    blocking work (yt-dlp extraction, youtube search, radio widget fetch)

All bots share one process and one event loop by design - the cross-bot
references above are direct Python object references, not IPC.

A background task also publishes playback status to run/status.json, which is
how hosting/server_manager.py decides whether a deferred restart may proceed
(see hosting/status.py).
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import signal
import sys
from concurrent.futures import ThreadPoolExecutor

import configs.private_config as private_config
from bots.admin_bot import AdminBot
from bots.log_bot import LogBot
from bots.music_instance import MusicBotInstance
from bots.music_leader import MusicBotLeader
from hosting import status

# Worker count for the shared blocking-work pool. None keeps Python's default
# (min(32, cpu_count + 4)), which is what the original used. Raise it if
# playlist loading feels serialized on a many-core box; lower it if yt-dlp
# extraction is starving ffmpeg for CPU on a small VPS.
THREAD_POOL_MAX_WORKERS = None


def configure_logging() -> None:
    """Routes the `nazarick.*` loggers introduced during the refactor to stderr.

    The hosting layer (hosting/server_manager.py) captures the child process's
    stderr, so anything logged here reaches the log files and the admin bot's
    error monitor. Level is INFO by default; set NAZARICK_LOG_LEVEL=DEBUG to
    see the routine try_function failures too.
    """
    level_name = os.environ.get("NAZARICK_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def validate_bots(leaders, instances, admins, loggers):
    """Rejects configurations the wiring below can't support.

    Note the asymmetry, preserved from the original: an empty config only
    prints a notice and still returns True (main() then gathers zero tasks and
    exits cleanly), whereas the duplicate/orphan cases return False.
    """
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
    """Drains in-flight pool work before stopping the loop, so a restart from
    the server manager doesn't kill a half-finished yt-dlp extraction."""
    pool.shutdown(wait=True, cancel_futures=False)
    loop.stop()


def worker_init():
    """Silences pool worker threads.

    yt-dlp writes progress and warnings straight to stdout/stderr; without this
    that noise would be interleaved into the process output that
    hosting/server_manager.py captures and the admin bot reports as errors.
    """
    f = open(os.devnull, 'w')
    sys.stdout = f
    sys.stderr = f


async def main():
    os.chdir(os.path.dirname(__file__))
    configure_logging()
    pool = ThreadPoolExecutor(max_workers=THREAD_POOL_MAX_WORKERS, initializer=worker_init)

    try:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(
            signal.SIGTERM,
            functools.partial(on_sigterm, loop, pool))
    except Exception:
        # add_signal_handler is unavailable on Windows; the bots still run,
        # they just don't drain the pool on SIGTERM.
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
            # The leader is also a playable instance, so it appears in both
            # lists - that's what lets a single-bot setup work.
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

    # Publishes run/status.json so the supervisor can tell whether a deferred
    # restart is safe. Written even with no music bots configured, so the
    # supervisor can still distinguish "running and idle" from "not running".
    #
    # Deliberately a side task rather than a member of `tasks`: it loops
    # forever, so gathering it would stop main() from ever returning once the
    # bots themselves exit.
    status_task = asyncio.create_task(status.status_writer(instances))

    try:
        await asyncio.gather(*tasks)
    finally:
        status_task.cancel()
        # Leaving a "playing" snapshot behind would make the supervisor defer
        # the next restart until the file went stale.
        status.clear_status()


if __name__ == '__main__':
    asyncio.run(main())
