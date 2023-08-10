import asyncio
import socket
from enum import Enum
import subprocess
from datetime import datetime
import sys
import os


try:
    os.chdir(os.path.dirname(__file__))
    sys.path.append("..")
    from configs.private_config import hosting_port, backup_login, backup_password, backup_url
    from configs.public_config import bot_backup_files
except:
    pass


class FileWithDates():
    file = None
    buffer = None

    def __init__(self, filename):
        if not os.path.exists(f"../logs/{filename}"):
            os.makedirs(f"../logs/{filename}")
        file_name = datetime.now().strftime('%d-%m-%Y') + ".txt"
        script_dir = os.path.dirname(__file__)
        rel_path = f"../logs/{filename}/{file_name}"
        abs_path = os.path.join(script_dir, rel_path)
        self.file = open(abs_path, "a", encoding="utf-8")
        self.buffer = ""

    def write(self, value):
        if len(value) == 0:
            return
        lines = value.split('\n')
        if len(lines) == 0:
            return
        remaining = None
        if value[-1] != '\n':
            remaining = lines[-1]
            lines = lines[:-1]
        if len(lines) != 0:
            lines[0] = self.buffer + lines[0]
        tm = datetime.now().strftime('%d.%m.%Y | %H.%M.%S')
        tm_s = f"[{tm}]: "
        for line in lines:
            if len(line) == 0:
                continue
            self.file.write(f"{tm_s}{line}\n")
        self.file.flush()
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


class Host:
    state = BotState.STOPPED
    errors = None
    process = None
    listener_socket = None
    port = None

    def __init__(self, port):
        self.listener_socket = socket.socket(family=socket.AF_INET)
        self.listener_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener_socket.bind(('', port))
        self.listener_socket.listen(1600)
        self.listener_socket.setblocking(False)
        self.port = port
        print("Host started")

    async def pull_errors(self):
        while self.process:
            await asyncio.sleep(0.1)
            while True:
                data = self.process.stderr.read(1024)
                if not data:
                    break
                try:
                    lines = data.decode('utf-8', errors='replace').split('\n')
                    for line in lines:
                        if "Error in the pull function" in line or "Will reconnect at" in line:
                            continue
                        self.errors += "\n"
                        self.errors += line
                        print(f"ERROR IN BOT: {line}")
                except Exception as e:
                    self.errors += f"\nNON UTF-8 ERROR: {e}\n"

    async def process_command(self, command):
        args = command.split()
        print(f"Processing command {args}")
        if len(args) == 0:
            return None
        args[0] = args[0].lower()
        match args[0]:
            case "run" | "start":
                return await self.run()
            case "stop":
                return await self.stop()
            case "status":
                return await self.status()
            case "reboot" | "reload" | "restart":
                return await self.reboot()
            case "backup":
                return await self.backup()
            case "update":
                branch = "master"
                if len(args) > 1:
                    branch = args[1]
                return await self.update(branch)
            case "clear":
                return await self.clear_errors()
            case _:
                return None

    async def handle_client(self, client, addr):
        try:
            command = (await asyncio.get_running_loop().sock_recv(client, 1024)).decode('utf8')
        except Exception as ex:
            print(f"Failed to recieve command from {addr} due: {ex}")
            return

        print(f"Recieved command from {addr}")
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
        while self.state == BotState.RUNNING:
            hours = datetime.now().hour
            minutes = datetime.now().minute
            if (hours == 12 or hours == 0) and minutes == 0:
                await self.commit_backup()
                await asyncio.sleep(42900)
            await asyncio.sleep(55)

    async def commit_backup(self, manual=False):
        ans = ""
        for file in bot_backup_files:
            cmd = f'curl -T ../{file} --user "{backup_login}:{backup_password}" {backup_url}{file[:-3]}_{"manual" if manual else "12pm" if datetime.now().hour == 12 else "12am"}{file[-3:]}'
            if os.system(cmd) != 0:
                ans += f"\nFailed to commit {file}"
        if ans == "":
            ans = "Backup successful"
        return ans

    async def start(self, run: bool):
        if run:
            await self.run()

        while self.state != BotState.SHUTDOWN:
            client, addr = await asyncio.get_running_loop().sock_accept(self.listener_socket)
            asyncio.create_task(self.handle_client(client, addr))

    async def backup(self):
        ans = await self.commit_backup(manual=True)
        return ans

    async def run(self):
        if self.state == BotState.RUNNING:
            return "Bot is already running"

        self.errors = ""
        self.process = subprocess.Popen(
            ["python3.11", "../main.py"], close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        self.process.terminate()
        self.errors = None
        self.state = BotState.STOPPED
        self.process = None
        os.system("pkill -f ../main.py")
        return ans

    async def clear_errors(self):
        self.errors = ""
        return "Errors cleared"

    async def status(self):
        active_branch = self.get_current_branch()
        current_commit = self.get_current_commit()
        ans = f"Current state: {self.state.name}\nCurrent branch: {active_branch}\nCurrent commit: {current_commit}"
        if self.state == BotState.RUNNING:
            if len(self.errors) == 0:
                ans += "\nError status: No errors"
            else:
                ans += f"\nError status: Several erros occured\n{self.errors}"
        return ans

    async def reboot(self):
        ans = ""
        if self.state == BotState.RUNNING:
            ans += await self.stop()
        os.system("pkill -f ../main.py")
        ans += '\n' + await self.run()
        return ans

    async def update(self, branch):
        was_running = False
        if self.state == BotState.RUNNING:
            await self.stop()
            was_running = True
        os.system("pkill -f ../main.py")
        os.system("git -C .. stash")
        if os.system(f"git -C .. fetch --depth=1") != 0:
            os.system("git -C .. stash pop")
            return "Failed to fetch updates from origin"
        os.system(f"git -C .. checkout --detach")
        os.system(f"git -C .. branch -f -D {branch}")
        os.system(f"git -C .. checkout {branch}")
        os.system(f"git -C .. stash clear")

        self.state = BotState.SHUTDOWN
        self.listener_socket.close()
        arg = ""
        if was_running:
            arg = "-r"
        cmd = f"python3.11 server_manager.py {self.port} {arg} &"
        print(f"Executing: {cmd}\n")
        os.system(cmd)
        return f"Updated to branch {branch}"

    def get_current_branch(self):
        active_branch = os.popen("git -C .. rev-parse --abbrev-ref HEAD").read()
        return active_branch.replace('\n', '')

    def get_current_commit(self):
        current_commit = os.popen("git -C .. rev-parse HEAD").read()
        return current_commit.replace('\n', '')


async def main():
    try:
        port = hosting_port
    except:
        port = int(sys.argv[1])

    h = Host(port)

    start = bool(sys.argv[-1] == "-r")
    if start:
        print("Starting bots...")
    await h.start(start)

if __name__ == "__main__":
    f = FileWithDates("host")
    sys.stdout = f
    sys.stderr = f
    asyncio.run(main())
