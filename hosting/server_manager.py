"""Supervisor that runs on the VPS and controls the bot process.

Listens on a TCP port for password-prefixed commands from
hosting/client_manager.py (run/stop/status/reboot/backup/update/clear), spawns
`main.py` as a child process, tails the child's stderr, and uploads the sqlite
databases to WebDAV twice a day.

Stdout/stderr of this supervisor are redirected into dated files under logs/.

Note on the error pipeline: `pull_errors()` reads the child's stderr and writes
it back into the child's *stdin*, which is how `AdminBot.monitor_errors()`
receives it and DMs the owners. That's an unusual loop, but it's deliberate -
it lets the bot report its own crashes over Discord.
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import sys
from datetime import datetime, timezone
from enum import Enum

os.chdir(os.path.dirname(__file__))
sys.path.append("..")

# Imported before the config block on purpose: it has no config dependency, and
# putting it inside the try below would leave it undefined whenever
# private_config is missing.
from hosting import status as status_module  # noqa: E402
from helpers import log_filter  # noqa: E402

try:
    from configs.private_config import hosting_port, backup_login, backup_password, backup_url, server_manager_password
    from configs.public_config import auto_backup_files, manual_backup_files
except Exception:
    # Matches the original's tolerance for a missing/partial private_config:
    # the port can still be supplied via argv, and backup/auth commands will
    # fail at call time instead of at import time.
    pass

# This process runs with hosting/ as its working directory; the bot process
# runs from the repo root, so the shared status file needs the ".." prefix here.
STATUS_PATH = os.path.join("..", status_module.STATUS_PATH)

# How often the deferred-action watcher re-checks whether the bots are idle.
DEFERRED_POLL_INTERVAL = 20

# A deferred action gives up waiting and executes anyway after this long, so a
# bot stuck reporting "playing" can never block a deploy indefinitely.
DEFERRED_FORCE_AFTER = 6 * 3600

# How long to keep the supervisor's dated logs/<date>.txt files. They were never
# pruned, so they grew for the lifetime of the deployment. Note the bot process
# writes elsewhere - helpers/logging_setup.py rotates logs/nazarick.log at
# 10 MB x 10 - so this only covers the supervisor's own stream.
RETAIN_DAYS = 30

# The noise list and the report-worthiness decision live in
# helpers/log_filter.py, shared with bots/admin_bot.py so the two readers of
# this stream cannot drift apart. Re-exported under the original names because
# the tests refer to server_manager.IGNORED_ERROR_FRAGMENTS.
IGNORED_ERROR_FRAGMENTS = log_filter.IGNORED_ERROR_FRAGMENTS
is_ignorable_error_line = log_filter.is_ignorable_error_line
is_reportable = log_filter.is_reportable


async def _to_thread(func, *args, **kwargs):
    """Runs a blocking call in a worker thread.

    Every long-running call in this module used to run directly on the event
    loop. That loop is also the thing serving the control port, so a slow call
    froze the supervisor: `sock_accept` never ran, and because the listener
    socket stays bound with a 1600-deep backlog the kernel still completed the
    TCP handshake for incoming clients. From the client's side the connection
    "succeeded" and then hung, so client_manager hit its 30 s socket timeout and
    reported `could not reach the manager at 127.0.0.1:PORT: timed out` - which
    reads like the supervisor was dead when it was in fact alive and busy.

    `pip install --upgrade yt-dlp` takes well over 30 s on a small VPS, so the
    CI yt-dlp job hit this every time it had real work to do. Note the failure
    is self-concealing: the upgrade still completes on the server, the client
    just never hears about it and exits non-zero.
    """
    return await asyncio.to_thread(func, *args, **kwargs)


def _stop_process_tree(proc, force: bool = False) -> None:
    """Stops the bot process and the ffmpeg children it spawned.

    POSIX: main.py is started with start_new_session=True, so it leads its own
    process group and a single killpg reaches every ffmpeg under it. This is what
    replaced `pkill -f <pid>`, which matched that number anywhere in any command
    line and could kill unrelated processes.

    Windows: os.killpg and os.getpgid do not exist, and neither does SIGKILL.
    Popen.terminate()/kill() map to TerminateProcess, which stops only this
    process - stray ffmpeg children may outlive it. Accepted deliberately:
    Windows is a development platform for this project, not where the bots are
    hosted. Without this branch stop() raised AttributeError on Windows and the
    bots could not be stopped at all.
    """
    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
        try:
            os.killpg(os.getpgid(proc.pid),
                      signal.SIGKILL if force else signal.SIGTERM)
            return
        except (ProcessLookupError, PermissionError, OSError):
            # Already gone, or not permitted - fall through to the single process.
            pass
    if force:
        proc.kill()
    else:
        proc.terminate()


async def _pip_install_ytdlp():
    """Shared by run_ytdlp_upgrade and the deferred path, which had drifted into
    two copies of the same subprocess call (and the same `python` bug)."""
    return await _to_thread(
        subprocess.run,
        [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
        capture_output=True, text=True, timeout=600)


class FileWithDates:
    """A stdout/stderr replacement that timestamps every line and writes it to
    a per-day file under logs/.

    Reopens and closes the file on each write so the log is always flushed to
    disk (the supervisor is expected to be killed abruptly), and so the
    filename rolls over at midnight without any scheduling.
    """

    def __init__(self):
        self.file = None
        self.buffer = ""
        # Which file we last pruned for, so the sweep happens once per day
        # rather than on every single write.
        self._pruned_for = None

    def check_filename(self) -> None:
        if not os.path.exists(f"../logs"):
            os.makedirs(f"../logs")
        file_name = datetime.now().strftime('%d-%m-%Y') + ".txt"
        script_dir = os.path.dirname(__file__)
        rel_path = f"../logs/{file_name}"
        abs_path = os.path.join(script_dir, rel_path)
        self.file = open(abs_path, "a", encoding="utf-8")
        self.prune_old_logs(os.path.dirname(abs_path))

    def prune_old_logs(self, log_dir: str) -> None:
        """Deletes dated log files beyond RETAIN_DAYS.

        These files accumulated forever: one per day, for the life of the
        deployment, with no rotation. On a small VPS that is a slow disk leak,
        and a full disk is a genuinely nasty failure - sshd can accept a TCP
        connection but then fail to create a session, which looks like
        "Connection timed out during banner exchange" and locks you out of the
        box that would let you fix it.

        Only runs when the date rolls over, so this is once a day rather than on
        every write. Deliberately silent: a failure to prune must never stop the
        supervisor from logging, which is the one thing that explains outages.
        """
        if self._pruned_for == self.file.name:
            return
        self._pruned_for = self.file.name
        cutoff = datetime.now().timestamp() - RETAIN_DAYS * 86400
        try:
            for name in os.listdir(log_dir):
                if not name.endswith(".txt"):
                    continue
                path = os.path.join(log_dir, name)
                # Compare on mtime, not the filename: the date format here is
                # day-first, so lexical order is meaningless, and a partially
                # written or renamed file should not confuse this.
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
        except OSError:
            pass

    def write(self, value) -> None:
        if len(value) == 0:
            return
        lines = value.split('\n')
        if len(lines) == 0:
            return
        remaining = None
        # A trailing fragment without a newline is held back until the rest of
        # the line arrives, so timestamps land at real line boundaries.
        if value[-1] != '\n':
            remaining = lines[-1]
            lines = lines[:-1]
        if len(lines) != 0:
            lines[0] = self.buffer + lines[0]
        tm = datetime.now().strftime('%d.%m.%Y | %H.%M.%S')
        tm_s = f"[{tm}]: "
        self.check_filename()
        for line in lines:
            if len(line) == 0:
                continue
            self.file.write(f"{tm_s}{line}\n")
        self.file.flush()
        self.file.close()
        if remaining:
            self.buffer = remaining
        else:
            self.buffer = ""

    def flush(self):
        return


class BotState(Enum):
    STOPPED = 0
    RUNNING = 1
    SHUTDOWN = 2


def exception_handler(loop, context):
    print("Caught exception")


def force_exit():
    sys.stdout = None
    sys.stderr = None
    exit()


class PendingAction:
    """An action waiting for the bots to stop playing before it runs."""

    def __init__(self, kind: str, branch: str = None):
        self.kind = kind              # "update" | "reboot" | "upgrade"
        self.branch = branch
        self.requested_at = datetime.now(timezone.utc)
        self.last_reason = "not checked yet"

    def deadline_passed(self) -> bool:
        elapsed = (datetime.now(timezone.utc) - self.requested_at).total_seconds()
        return elapsed >= DEFERRED_FORCE_AFTER

    def describe(self) -> str:
        target = f" {self.branch}" if self.branch else ""
        waited = int((datetime.now(timezone.utc) - self.requested_at).total_seconds())
        return (f"{self.kind}{target} (queued {waited}s ago; "
                f"waiting because: {self.last_reason})")


class Host:

    def __init__(self, port):
        self.state = BotState.STOPPED
        self.errors = None
        self.errors_cnt = 0
        self.last_start = None
        self.process = None
        self.port = port
        self.pending = None
        self.listener_socket = socket.socket(family=socket.AF_INET)
        self.listener_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.listener_socket.bind(('', port))
        except OSError as ex:
            # NOTE: this catches the case on Linux, which is what the VPS runs.
            # On Windows SO_REUSEADDR permits a second socket to bind the same
            # port outright, so the bind succeeds and this never fires. Windows
            # would need SO_EXCLUSIVEADDRUSE to behave the same way - not worth
            # it, since the double-supervisor problem is a hosting problem.
            #
            # Two supervisors fighting over one bot process is the worst failure
            # mode this program has: each starts and stops main.py behind the
            # other's back. Refuse to be the second one, and say so clearly -
            # this used to surface as a bare traceback in a dated log file.
            raise SystemExit(
                f"Cannot bind port {port}: {ex}\n"
                f"Another server_manager.py is almost certainly already running.\n"
                f"Check with:  ps -ax | grep server_manager\n"
                f"If one is an orphan not managed by systemd, stop the service, "
                f"kill the orphan, then start the service again."
            ) from ex
        self.listener_socket.listen(1600)
        self.listener_socket.setblocking(False)
        print("Host started")

    async def pull_errors(self):
        """Tails the child's stderr, echoes it back into the child's stdin (so
        AdminBot.monitor_errors can DM it), and accumulates it for `status`.

        Uses the same ErrorReporter as the admin bot, so `status` and the owner
        DMs agree on what counts as a problem - and so a message split across
        two reads is assembled before being judged."""
        reporter = log_filter.ErrorReporter()
        while self.process:
            await asyncio.sleep(0.1)
            while True:
                data = self.process.stderr.read(1024)
                if not data:
                    break
                try:
                    # Echo verbatim: the bot's own monitor_errors does its own
                    # filtering, so it must receive the unmodified stream.
                    self.process.stdin.write(data)
                    self.process.stdin.flush()
                    reporter.feed(data.decode('utf-8', errors='replace'))
                except Exception as e:
                    self.errors += f"\nNON UTF-8 ERROR: {e}\n"

            report = reporter.drain()
            if report:
                self.errors += "\n" + report
                print(f"ERROR IN BOT: {report}")

    async def process_command(self, command):
        args = command.split()
        # Never print the command verbatim - args[0] is the password.
        print(f"Processing command {args[1:] if len(args) > 1 else '(empty)'}")
        if len(args) < 2:
            return None
        if args[0] != server_manager_password:
            return "Unauthorized access"
        args[1] = args[1].lower()

        # A trailing `when-idle` on update/reboot/upgrade queues the action
        # instead of running it immediately; the watcher fires it once no bot is
        # playing. Anything else keeps the original immediate behavior.
        deferred = False
        rest = args[2:]
        if rest and rest[-1].lower() in ("when-idle", "when_idle", "whenidle"):
            deferred = True
            rest = rest[:-1]

        # `<verb>-idle` is an alias for `<verb> when-idle`. The suffix form was
        # only documented as a footnote, so the deferred variants were easy to
        # miss; as single words they can sit next to the immediate ones in the
        # help. Handled here rather than as extra `case` arms so update-idle and
        # upgrade-idle come along for free and cannot drift apart.
        for suffix in ("-idle", "_idle"):
            if args[1].endswith(suffix) and len(args[1]) > len(suffix):
                deferred = True
                args[1] = args[1][:-len(suffix)]
                break

        match args[1]:
            case "run" | "start":
                return await self.run()
            case "stop":
                return await self.stop()
            case "status":
                return await self.status()
            case "reboot" | "reload" | "restart":
                if deferred:
                    return self.queue_action("reboot")
                return await self.reboot()
            case "backup":
                return await self.backup()
            case "update":
                branch = rest[0] if rest else self.get_current_branch()
                if deferred:
                    return self.queue_action("update", branch)
                return await self.update(branch)
            case "upgrade":
                return await self.upgrade_ytdlp(deferred=deferred)
            case "cancel":
                return self.cancel_pending()
            case "clear":
                return await self.clear_errors()
            case _:
                return None

# *_______DeferredActions____________________________________________________________________________________

    def queue_action(self, kind: str, branch: str = None) -> str:
        """Queues an action to run once the bots stop playing.

        A newly queued action replaces any existing one - the most recent
        request wins, which is what you want when several deploys land in a row.
        """
        replaced = self.pending
        self.pending = PendingAction(kind, branch)
        idle, reason = status_module.is_idle(STATUS_PATH)
        self.pending.last_reason = reason
        message = f"Queued: {self.pending.describe()}"
        if replaced:
            message = f"Replaced pending {replaced.kind}.\n{message}"
        if idle:
            message += "\nBots are idle now - it will run within " \
                       f"{DEFERRED_POLL_INTERVAL}s."
        else:
            message += f"\nWill force-run after {DEFERRED_FORCE_AFTER // 3600}h regardless."
        return message

    def cancel_pending(self) -> str:
        if not self.pending:
            return "Nothing is queued"
        cancelled = self.pending.describe()
        self.pending = None
        return f"Cancelled: {cancelled}"

    async def deferred_watcher(self) -> None:
        """Polls the bot's status file and runs the queued action once it is
        safe (or once the force deadline passes)."""
        while self.state != BotState.SHUTDOWN:
            await asyncio.sleep(DEFERRED_POLL_INTERVAL)
            if not self.pending:
                continue

            idle, reason = status_module.is_idle(STATUS_PATH)
            self.pending.last_reason = reason
            forced = self.pending.deadline_passed()
            if not idle and not forced:
                continue

            action = self.pending
            self.pending = None
            trigger = "force deadline reached" if forced and not idle else reason
            print(f"Running deferred {action.kind} ({trigger})")
            try:
                if action.kind == "update":
                    print(await self.update(action.branch))
                elif action.kind == "reboot":
                    print(await self.reboot())
                elif action.kind == "upgrade":
                    print(await self.run_ytdlp_upgrade())
            except Exception as ex:
                print(f"Deferred {action.kind} failed: {ex}")

            # BUGFIX: a deferred `update` left the whole stack dead.
            #
            # update() stops the bots, closes the listener socket and sets
            # SHUTDOWN, on the understanding that the process then exits so it
            # comes back running the new code. handle_client() does exactly that
            # after replying - but only for an `update` a client sent directly.
            # Nothing did it here, so a deferred deploy ended with a live
            # process, the bots stopped and the control port closed: bots
            # offline, manager unreachable, and systemd still seeing the unit as
            # active, so Restart=always never fired. It stayed down until
            # someone restarted it by hand.
            #
            # This is the path CI uses: `deploy` sends `update <branch>
            # when-idle`, which queues and returns immediately - so the workflow
            # goes green well before any of this runs.
            if self.state == BotState.SHUTDOWN:
                print("Deferred action requested shutdown; exiting so the "
                      "supervisor restarts on the new code")
                force_exit()

# *_______Dependencies_______________________________________________________________________________________

    def get_ytdlp_version(self) -> str:
        """Version of yt-dlp as the *bot* process would import it, or None.

        BUGFIX: this used a literal "python", which does not exist on Debian
        (only python3 is shipped; `python` needs python-is-python3). The
        FileNotFoundError was swallowed by the except below, so `before` and
        `after` in run_ytdlp_upgrade were both None, compared equal, and the
        upgrade reported "already current (None); no restart needed" forever.
        sys.executable also guarantees we read the version from the same
        interpreter - and the same venv - the bots actually run under.
        """
        try:
            result = subprocess.run(
                [sys.executable, "-c",
                 "import yt_dlp; print(yt_dlp.version.__version__)"],
                capture_output=True, text=True, timeout=60)
            return result.stdout.strip() or None
        except Exception:
            return None

    async def run_ytdlp_upgrade(self) -> str:
        """Upgrades yt-dlp and restarts only if the version actually changed.

        Restarting on every check would be pointless churn; yt-dlp publishes
        frequently but most days there is nothing new.
        """
        before = await asyncio.to_thread(self.get_ytdlp_version)
        try:
            result = await _pip_install_ytdlp()
        except Exception as ex:
            return f"yt-dlp upgrade failed to run: {ex}"

        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
            return "yt-dlp upgrade failed:\n" + "\n".join(tail)

        after = await asyncio.to_thread(self.get_ytdlp_version)
        if before == after:
            return f"yt-dlp already current ({after}); no restart needed"

        message = f"yt-dlp upgraded {before} -> {after}"
        if self.state == BotState.RUNNING:
            message += "\n" + await self.reboot()
        else:
            message += "\nBot is not running; nothing to restart"
        return message

    async def upgrade_ytdlp(self, deferred: bool = False) -> str:
        """`upgrade` entry point. Deferred mode still installs immediately - only
        the restart waits, so a fix is on disk the moment playback ends."""
        if not deferred:
            return await self.run_ytdlp_upgrade()

        before = await asyncio.to_thread(self.get_ytdlp_version)
        try:
            result = await _pip_install_ytdlp()
        except Exception as ex:
            return f"yt-dlp upgrade failed to run: {ex}"
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
            return "yt-dlp upgrade failed:\n" + "\n".join(tail)

        after = await asyncio.to_thread(self.get_ytdlp_version)
        if before == after:
            return f"yt-dlp already current ({after}); nothing queued"
        return (f"yt-dlp upgraded {before} -> {after}\n"
                + self.queue_action("reboot"))

    async def handle_client(self, client, addr):
        try:
            command = (await asyncio.get_running_loop().sock_recv(client, 1024)).decode('utf8')
        except Exception as ex:
            print(f"Failed to recieve command from {addr} due: {ex}")
            return

        print(f"Recieved command from {addr}")
        respond = None
        try:
            respond = await self.process_command(command)
        except Exception as ex:
            print(f"Failed to process command due: {ex}")
        if not respond or len(respond) == 0:
            respond = "Unknown command"

        print(f"Respond to command: {respond}")
        try:
            await asyncio.get_running_loop().sock_sendall(client, respond.encode('utf8'))
        except Exception as ex:
            print(f"Respond was not delivered because: {ex}")

        client.close()
        if self.state == BotState.SHUTDOWN:
            force_exit()

    async def backup_create(self):
        """Fires a backup at 00:00 and 12:00, then sleeps ~12h to avoid
        re-triggering within the same minute."""
        while self.state == BotState.RUNNING:
            hours = datetime.now().hour
            minutes = datetime.now().minute
            if (hours == 12 or hours == 0) and minutes == 0:
                asyncio.create_task(self.commit_backup())
                await asyncio.sleep(42900)
            await asyncio.sleep(50)

    async def commit_backup(self, manual=False):
        ans = ""
        for file in (auto_backup_files, manual_backup_files)[manual]:
            # file[:-3] / file[-3:] split the ".db" extension off so the label
            # lands before it (e.g. bot_database_12pm.db).
            cmd = f'curl --max-time 300 -T ../{file} --user "{backup_login}:{backup_password}" {backup_url}{file[:-3]}_{"manual" if manual else "12pm" if datetime.now().hour == 12 else "12am"}{file[-3:]}'
            if await _to_thread(os.system, cmd) != 0:
                ans += f"\nFailed to commit {file}"
        if ans == "":
            ans = "Backup successful"
        return ans

    async def start(self, run: bool):
        if run:
            await self.run()

        asyncio.create_task(self.deferred_watcher())

        while self.state != BotState.SHUTDOWN:
            try:
                client, addr = await asyncio.get_running_loop().sock_accept(self.listener_socket)
            except OSError as ex:
                # Second line of defence for the same failure: update() closes
                # this socket underneath us, and a blocked sock_accept on a
                # closed fd is not guaranteed to raise - asyncio may simply leave
                # the future pending forever. Where it does raise, leaving the
                # loop lets the process exit so systemd restarts it, instead of
                # dumping a traceback and hanging.
                print(f"Listener closed ({ex}); shutting down")
                break
            asyncio.create_task(self.handle_client(client, addr))

    async def backup(self):
        ans = await self.commit_backup(manual=True)
        return ans

    async def run(self):
        if self.state == BotState.RUNNING:
            return "Bot is already running"
        self.last_start = datetime.now(timezone.utc)
        self.errors = ""
        # sys.executable rather than a bare "python": Debian ships python3 with
        # no `python` alias, so the literal name works only where someone has
        # installed python-is-python3. This also guarantees the bots run under
        # the same interpreter as the supervisor, including inside a venv.
        # start_new_session puts the bots in their own process group, so stop()
        # can signal the group and take their ffmpeg children with them. Without
        # it, killpg would target the supervisor's own group - i.e. itself.
        # POSIX-only; subprocess ignores it on Windows, where _stop_process_tree
        # falls back to terminating just this process.
        self.process = subprocess.Popen(
            [sys.executable, "../main.py"], close_fds=True, start_new_session=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        os.set_blocking(self.process.stderr.fileno(), False)
        if not self.process:
            return "Failed to create bot process"

        self.state = BotState.RUNNING
        asyncio.create_task(self.backup_create())
        asyncio.create_task(self.pull_errors())
        return f"Started bot process with PID: {self.process.pid}"

    async def stop(self):
        if self.state == BotState.STOPPED:
            return f"Bot is already stopped"

        proc = self.process
        ans = f"Stopped bot process with PID: {proc.pid}"

        # BUGFIX: this was `os.system(f"pkill -f {self.process.pid}")`, which is
        # both wrong and dangerous. `pkill -f` matches the pattern anywhere in
        # any process's full command line, so a bare PID like 12409 also kills
        # unrelated processes that merely mention that number in their arguments.
        # It also did not reliably reach the ffmpeg children it was aiming for.
        #
        # main.py is now started in its own session (start_new_session=True), so
        # signalling the process group takes the bots and every ffmpeg they
        # spawned down together, and nothing else.
        _stop_process_tree(proc)

        # BUGFIX: nothing ever reaped the child. terminate() only asks it to
        # exit; without a wait() it stays a <defunct> zombie for as long as the
        # supervisor lives. `ps -ax` on the VPS showed these accumulating, one
        # per stop, which is also why "the bots are offline" looked identical to
        # "the bots are running" at a glance.
        try:
            await _to_thread(proc.wait, 15)
        except subprocess.TimeoutExpired:
            print(f"Bot process {proc.pid} ignored the stop request; forcing")
            _stop_process_tree(proc, force=True)
            await _to_thread(proc.wait)

        self.errors = None
        self.state = BotState.STOPPED
        self.process = None
        # The stopped process can no longer refresh run/status.json; removing it
        # stops a leftover "playing" snapshot from blocking the next deferred
        # action until it goes stale.
        status_module.clear_status(STATUS_PATH)
        return ans

    async def clear_errors(self):
        self.errors = ""
        return "Errors cleared"

    async def status(self):
        active_branch = self.get_current_branch()
        current_commit = self.get_current_commit()
        try:
            time_passed = self.get_passed_time(self.last_start)
        except Exception:
            time_passed = None

        if not time_passed:
            time_passed = ""
        else:
            time_passed = "\nLast launch: " + time_passed
        ans = f"Current state: {self.state.name}\nCurrent branch: {active_branch}\nCurrent commit: {current_commit}{time_passed}"

        ytdlp_version = self.get_ytdlp_version()
        if ytdlp_version:
            ans += f"\nyt-dlp: {ytdlp_version}"

        idle, reason = status_module.is_idle(STATUS_PATH)
        ans += f"\nPlayback: {reason}"
        if self.pending:
            ans += f"\nQueued action: {self.pending.describe()}"

        if self.state == BotState.RUNNING:
            if len(self.errors) == 0:
                ans += "\nError status: No errors"
            else:
                errors_cnt = self.errors.count("Traceback") + self.errors.count("Runtime")
                ans += f"\nError status: {('There was 1 error', f'There were {errors_cnt} errors')[errors_cnt > 1]}:\n{self.errors}"
        return ans

    async def reboot(self):
        ans = ""
        if self.state == BotState.RUNNING:
            ans += await self.stop()
        ans += '\n' + await self.run()
        return ans

    async def update(self, branch):
        """Pulls the selected branch, reinstalls dependencies, then hands over to
        a fresh copy of this supervisor (a running process can't swap out its own
        code in place)."""
        was_running = False
        if self.state == BotState.RUNNING:
            await self.stop()
            was_running = True
        await _to_thread(os.system, "git -C .. stash")
        if await _to_thread(os.system, "git -C .. fetch --depth=1") != 0:
            await _to_thread(os.system, "git -C .. stash pop")
            return "Failed to fetch updates from origin"
        await _to_thread(os.system, "git -C .. checkout --detach")
        await _to_thread(os.system, f"git -C .. branch -f -D {branch}")
        await _to_thread(os.system, f"git -C .. checkout {branch}")
        await _to_thread(os.system, "git -C .. stash clear")

        # BUGFIX: this ran `bash setup.sh`, but the working directory is
        # hosting/ while setup.sh lives at the repo root - so every update
        # printed "bash: setup.sh: No such file or directory" and silently
        # skipped the dependency install.
        setup_script = os.path.join("..", "setup.sh")
        if os.path.exists(setup_script):
            await _to_thread(os.system, f"bash {setup_script}")
        else:
            print(f"Skipping dependency install: {setup_script} not found")

        self.state = BotState.SHUTDOWN
        self.listener_socket.close()

        # Under systemd there is nothing to re-exec: exiting is enough, because
        # Restart=always brings the supervisor back running the new code. This
        # is both simpler and more reliable than spawning our own replacement.
        if os.environ.get("INVOCATION_ID"):
            print("Running under systemd; exiting so the service restarts with the new code")
            return (f"Updated to branch {branch}\n"
                    "systemd is restarting the supervisor")

        arg = "-r" if was_running else ""
        # BUGFIX: the old command ended in `& disown`. os.system() runs through
        # /bin/sh, which on Debian is dash, and `disown` is a bash builtin - so
        # this failed with "sh: 1: disown: not found" and the replacement
        # supervisor was never detached properly.
        #
        # `setsid` detaches from the controlling terminal and process group,
        # which is what disown was reaching for, and works in any POSIX shell.
        # sys.executable is used rather than a bare `python` because Debian does
        # not ship a `python` alias - only `python3`.
        cmd = (f"setsid nohup {sys.executable} server_manager.py "
               f"{self.port} {arg} >/dev/null 2>&1 &")
        print(f"Executing: {cmd}\n")
        os.system(cmd)
        return f"Updated to branch {branch}"

    def get_current_branch(self):
        active_branch = os.popen("git -C .. rev-parse --abbrev-ref HEAD").read()
        return active_branch.replace('\n', '')

    def get_current_commit(self):
        current_commit = os.popen("git -C .. rev-parse HEAD").read()
        return current_commit.replace('\n', '')

    def get_passed_time(self, date) -> str:
        """Coarse "x ago" formatting, largest applicable unit only."""
        if not date:
            return None
        delta = datetime.now(timezone.utc) - date
        amount = delta.days // 365
        if amount > 0:
            if amount == 1:
                return "a year ago"
            else:
                return f"{amount} years ago"

        amount = delta.days // 30
        if amount > 0:
            if amount == 1:
                return "a month ago"
            else:
                return f"{amount} months ago"

        amount = delta.days // 7
        if amount > 0:
            if amount == 1:
                return "a week ago"
            else:
                return f"{amount} weeks ago"

        amount = delta.days
        if amount > 0:
            if amount == 1:
                return "a day ago"
            else:
                return f"{amount} days ago"

        amount = delta.seconds // 3600
        if amount > 0:
            if amount == 1:
                return "an hour ago"
            else:
                return f"{amount} hours ago"

        amount = delta.seconds // 60
        if amount <= 1:
            return "a minute ago"
        return f"{amount} minutes ago"


async def main():
    try:
        port = hosting_port
    except Exception:
        port = int(sys.argv[1])

    h = Host(port)

    start = bool(sys.argv[-1] == "-r")
    if start:
        print("Starting bots...")
    await h.start(start)


if __name__ == "__main__":
    f = FileWithDates()
    sys.stdout = f
    sys.stderr = f
    asyncio.run(main())
