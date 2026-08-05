"""Logging configuration for the bot process.

Replaces the previous arrangement, which was inverted: everything the process
wrote to stderr was treated as a potential incident, and a growing denylist of
substrings tried to guess which lines were harmless. That can only ever lose -
ffmpeg, disnake and the warnings module all emit routine text, and any new
library adds new phrases nobody has denylisted yet.

Here severity is decided where it is known - at the point of logging - and the
readers only report what has been explicitly marked:

    logger.error(...)   from nazarick.*   -> marked, reported to the owner
    logger.info(...)    from nazarick.*   -> log file only
    anything from disnake / yt_dlp / etc  -> log file only
    warnings.warn(...)                    -> log file only
    ffmpeg's own stderr                   -> log file only
    an unhandled exception                -> marked, reported to the owner

The marker is a literal prefix on the stderr line. stderr is the only channel
back to the supervisor (it pipes it into the bot's stdin for the admin bot to
read), so the signal has to survive as text - but it is now an explicit
allowlist of one token rather than a guess.

Everything, marked or not, is also written to a rotating file under logs/, so
nothing is lost.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import sys
import threading
import warnings

#: Prefix stamped onto stderr lines that should reach a human.
#:
#: Chosen to be unmistakable and impossible to produce accidentally: no library
#: writes this, so a marked line is always one we marked. Kept ASCII so it
#: survives any encoding the pipe applies.
ALERT_MARKER = "[[NZ-ALERT]]"

#: Our own logger namespace. Only records from here can be marked.
ROOT_LOGGER_NAME = "nazarick"

#: Third-party loggers that are informative rather than actionable. Held at
#: WARNING so their INFO chatter never even reaches a file handler, and pinned
#: explicitly because disnake in particular logs every gateway reconnect at INFO.
NOISY_LOGGERS = (
    "disnake",
    "websockets",
    "asyncio",
    "urllib3",
    "yt_dlp",
    "aiosqlite",
)

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "nazarick.log")

#: 10 MB x 10 files. The previous scheme wrote one unbounded file per day and
#: never removed any; db/logs.db had reached 407 MB by the same logic.
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 10

FILE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_configured = False


class AlertFilter(logging.Filter):
    """Passes only records that should reach a human.

    That means WARNING and above is *not* enough: a warning is something to read
    later, not something to be woken by. Only ERROR and CRITICAL, and only from
    our own namespace, qualify.
    """

    def __init__(self, level: int = logging.ERROR, namespace: str = ROOT_LOGGER_NAME):
        super().__init__()
        self.level = level
        self.namespace = namespace

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < self.level:
            return False
        return record.name == self.namespace or record.name.startswith(self.namespace + ".")


class AlertFormatter(logging.Formatter):
    """Stamps ALERT_MARKER on every line of the emitted record.

    Every line, not just the first: a traceback spans many lines, and the reader
    judges lines independently. Marking only the first would report
    "RuntimeError: ..." while silently dropping the stack that explains it.
    """

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        return "\n".join(f"{ALERT_MARKER} {line}" for line in text.splitlines())


def configure(level: str | None = None, log_dir: str = LOG_DIR,
              force: bool = False) -> logging.Logger:
    """Sets up logging for the bot process. Idempotent.

    Returns the `nazarick` logger.

    Level applies to our own logging only, and comes from NAZARICK_LOG_LEVEL if
    not given. Third-party loggers stay at WARNING regardless - raising our own
    verbosity should not also unleash disnake's.
    """
    global _configured
    own = logging.getLogger(ROOT_LOGGER_NAME)

    if _configured and not force:
        return own

    level_name = (level or os.environ.get("NAZARICK_LOG_LEVEL", "INFO")).upper()
    resolved = getattr(logging, level_name, logging.INFO)

    own.setLevel(resolved)
    # Deliberately not propagating to root: the root logger is left alone so a
    # third-party library that calls basicConfig cannot start duplicating our
    # records onto stderr, unmarked.
    own.propagate = False
    for handler in list(own.handlers):
        own.removeHandler(handler)

    # 1. Everything goes to a rotating file - the complete record, unmarked.
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, os.path.basename(LOG_FILE)),
            maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
        own.addHandler(file_handler)
    except OSError as exc:
        # A read-only or missing logs/ must not stop the bots from starting.
        print(f"WARNING: file logging disabled ({exc})", file=sys.stderr)

    # 2. Only ERROR+ from our own code goes to stderr, marked for reporting.
    alert_handler = logging.StreamHandler(sys.stderr)
    alert_handler.setLevel(logging.ERROR)
    alert_handler.addFilter(AlertFilter())
    alert_handler.setFormatter(AlertFormatter(FILE_FORMAT))
    own.addHandler(alert_handler)

    # 3. Third-party libraries: file only, and only when they have something
    #    at least warning-worthy to say.
    for name in NOISY_LOGGERS:
        third_party = logging.getLogger(name)
        third_party.setLevel(logging.WARNING)
        third_party.propagate = False
        for handler in list(third_party.handlers):
            third_party.removeHandler(handler)
        for handler in own.handlers:
            # Share the file handler but never the alert handler, so a library
            # error is recorded without paging anyone.
            if not isinstance(handler.formatter, AlertFormatter):
                third_party.addHandler(handler)

    # 4. warnings.warn() becomes a log record instead of raw stderr text. This
    #    is what stopped DeprecationWarnings being reported as incidents: they
    #    are now WARNING-level records, which the alert filter rejects.
    logging.captureWarnings(True)
    py_warnings = logging.getLogger("py.warnings")
    py_warnings.setLevel(logging.WARNING)
    py_warnings.propagate = False
    for handler in list(py_warnings.handlers):
        py_warnings.removeHandler(handler)
    for handler in own.handlers:
        if not isinstance(handler.formatter, AlertFormatter):
            py_warnings.addHandler(handler)

    _install_exception_hooks(own)

    _configured = True
    return own


def _install_exception_hooks(logger: logging.Logger) -> None:
    """Routes every unhandled failure through logging.

    Without this, an unhandled exception prints a raw traceback to stderr with no
    marker - so under an allowlist it would be silently dropped, which is the one
    thing that must never happen. Covers the three places Python surfaces them:
    the main thread, other threads, and asyncio tasks.
    """

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Ctrl+C is a request, not a fault.
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Unhandled exception",
                        exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

    def handle_thread_exception(args):
        if issubclass(args.exc_type, SystemExit):
            return
        logger.critical("Unhandled exception in thread %s",
                        getattr(args.thread, "name", "?"),
                        exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = handle_thread_exception


def install_asyncio_handler(loop: asyncio.AbstractEventLoop,
                            logger: logging.Logger | None = None) -> None:
    """Reports exceptions from asyncio tasks.

    Must be called with a running loop, so it is separate from configure().
    asyncio's default handler writes "Task exception was never retrieved"
    straight to stderr, which under an allowlist would vanish.
    """
    log = logger or logging.getLogger(ROOT_LOGGER_NAME)

    def handler(_loop, context):
        message = context.get("message", "unhandled asyncio error")
        exception = context.get("exception")
        if exception is not None:
            log.error("asyncio: %s", message, exc_info=exception)
        else:
            log.error("asyncio: %s (%r)", message, context)

    loop.set_exception_handler(handler)


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor: get_logger("music") -> the nazarick.music logger."""
    if name.startswith(ROOT_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
