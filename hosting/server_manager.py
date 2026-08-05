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

# Substrings identifying routine ffmpeg/network chatter that should not be
# treated as an error. Kept in sync with bots/admin_bot.py's copy - see the
# BUGFIX note in is_ignorable_error_line() below.
IGNORED_ERROR_FRAGMENTS = (
    "[tls @",
    "[https @",
    "[hls @",
    "retrying with new connection",
)


def is_ignorable_error_line(line: str) -> bool:
    """True if `line` is routine ffmpeg/network noise rather than a real error.

    BUGFIX: the original condition was

        if "[tls @" in line or "[https @" in line or "[hls @" or "retrying..." in line:

    The third clause is a bare truthy string literal (missing `in line`), so the
    whole condition was always True and every line was skipped - meaning
    `self.errors` was never populated and `status` always reported "No errors".
    Identical bug to the one in bots/admin_bot.py; see CHANGES.md "Stage 5".
    """
    return any(fragment in line for fragment in IGNORED_ERROR_FRAGMENTS)


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

    def check_filename(self) -> None:
        if not os.path.exists(f"../logs"):
            os.makedirs(f"../logs")
        file_name = datetime.now().strftime('%d-%m-%Y') + ".txt"
        script_dir = os.path.dirname(__file__)
        rel_path = f"../logs/{file_name}"
        abs_path = os.path.join(script_dir, rel_path)
        self.file = open(abs_path, "a", encoding="utf-8")

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
        self.listener_socket.bind(('', port))
        self.listener_socket.listen(1600)
        self.listener_socket.setblocking(False)
        print("Host started")

    async def pull_errors(self):
        """Tails the child's stderr, echoes it back into the child's stdin (so
        AdminBot.monitor_errors can DM it), and accumulates it for `status`."""
        while self.process:
            await asyncio.sleep(0.1)
            while True:
                data = self.process.stderr.read(1024)
                if not data:
                    break
                try:
                    self.process.stdin.write(data)
                    self.process.stdin.flush()
                    lines = data.decode('utf-8', errors='replace').split('\n')
                    for line in lines:
                        if is_ignorable_error_line(line):
                            continue
                        if len(line) > 0:
                            self.errors += "\n" + line
                        print(f"ERROR IN BOT: {line}")
                except Exception as e:
                    self.errors += f"\nNON UTF-8 ERROR: {e}\n"

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

# *_______Dependencies_______________________________________________________________________________________

    def get_ytdlp_version(self) -> str:
        """Version of yt-dlp as the *bot* process would import it, or None."""
        try:
            result = subprocess.run(
                ["python", "-c", "import yt_dlp; print(yt_dlp.version.__version__)"],
                capture_output=True, text=True, timeout=60)
            return result.stdout.strip() or None
        except Exception:
            return None

    async def run_ytdlp_upgrade(self) -> str:
        """Upgrades yt-dlp and restarts only if the version actually changed.

        Restarting on every check would be pointless churn; yt-dlp publishes
        frequently but most days there is nothing new.
        """
        before = self.get_ytdlp_version()
        try:
            result = subprocess.run(
                ["python", "-m", "pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True, text=True, timeout=600)
        except Exception as ex:
            return f"yt-dlp upgrade failed to run: {ex}"

        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
            return "yt-dlp upgrade failed:\n" + "\n".join(tail)

        after = self.get_ytdlp_version()
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

        before = self.get_ytdlp_version()
        try:
            result = subprocess.run(
                ["python", "-m", "pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True, text=True, timeout=600)
        except Exception as ex:
            return f"yt-dlp upgrade failed to run: {ex}"
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
            return "yt-dlp upgrade failed:\n" + "\n".join(tail)

        after = self.get_ytdlp_version()
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
            cmd = f'curl -T ../{file} --user "{backup_login}:{backup_password}" {backup_url}{file[:-3]}_{"manual" if manual else "12pm" if datetime.now().hour == 12 else "12am"}{file[-3:]}'
            if os.system(cmd) != 0:
                ans += f"\nFailed to commit {file}"
        if ans == "":
            ans = "Backup successful"
        return ans

    async def start(self, run: bool):
        if run:
            await self.run()

        asyncio.create_task(self.deferred_watcher())

        while self.state != BotState.SHUTDOWN:
            client, addr = await asyncio.get_running_loop().sock_accept(self.listener_socket)
            asyncio.create_task(self.handle_client(client, addr))

    async def backup(self):
        ans = await self.commit_backup(manual=True)
        return ans

    async def run(self):
        if self.state == BotState.RUNNING:
            return "Bot is already running"
        self.last_start = datetime.now(timezone.utc)
        self.errors = ""
        self.process = subprocess.Popen(
            ["python", "../main.py"], close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
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

        ans = f"Stopped bot process with PID: {self.process.pid}"
        os.system(f"pkill -f {self.process.pid}")
        self.process.terminate()
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
        """Pulls the selected branch, reinstalls dependencies, then re-execs
        this supervisor (the running copy can't update its own code in place)."""
        was_running = False
        if self.state == BotState.RUNNING:
            await self.stop()
            was_running = True
        os.system("git -C .. stash")
        if os.system(f"git -C .. fetch --depth=1") != 0:
            os.system("git -C .. stash pop")
            return "Failed to fetch updates from origin"
        os.system(f"git -C .. checkout --detach")
        os.system(f"git -C .. branch -f -D {branch}")
        os.system(f"git -C .. checkout {branch}")
        os.system(f"git -C .. stash clear")
        os.system(f"bash setup.sh")

        self.state = BotState.SHUTDOWN
        self.listener_socket.close()
        arg = ""
        if was_running:
            arg = "-r"
        cmd = f"python server_manager.py {self.port} {arg} & disown"
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
