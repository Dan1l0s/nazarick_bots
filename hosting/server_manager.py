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
    from configs.private_config import hosting_ip, hosting_port
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

    async def process_command(self, command):
        args = command.split()
        print(f"Processing command {args}")
        if len(args) == 0:
            return None
        args[0] = args[0].lower()
        if args[0] == "run":
            return await self.run()
        if args[0] == "stop":
            return await self.stop()
        if args[0] == "status":
            return await self.status()
        if args[0] == "reboot":
            return await self.reboot()
        if args[0] == "update":
            branch = "master"
            if len(args) > 1:
                branch = args[1]
            return await self.update(branch)
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

    async def start(self, run: bool):
        if run:
            await self.run()

        while self.state != BotState.SHUTDOWN:
            client, addr = await asyncio.get_running_loop().sock_accept(self.listener_socket)
            asyncio.create_task(self.handle_client(client, addr))

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
        return f"Started bot process with PID: {self.process.pid}"

    async def stop(self):
        if self.state == BotState.STOPPED:
            return f"Bot is already stopped"

        ans = f"Stopped bot process with PID: {self.process.pid}"
        self.process.terminate()
        self.errors = None
        self.state = BotState.STOPPED
        self.process = None
        return ans

    async def status(self):
        active_branch = self.get_current_branch()
        current_commit = self.get_current_commit()
        ans = f"Current state: {self.state.name}\nCurrent branch: {active_branch}\nCurrent commit: {current_commit}"
        if self.state == BotState.RUNNING:
            while True:
                data = self.process.stderr.read(1024)
                if not data:
                    break
                else:
                    self.errors += data.decode("utf-8")
            if len(self.errors) == 0:
                ans += "\nError status: No errors"
            else:
                ans += f"\nError status: Several erros occured\n{self.errors}"
        return ans

    async def reboot(self):
        ans = ""
        if self.state == BotState.RUNNING:
            ans += await self.stop()
        ans += '\n' + await self.run()
        return ans

    async def update(self, branch):
        was_running = False
        if self.state == BotState.RUNNING:
            await self.stop()
            was_running = True
        if os.system("git stash") != 0:
            return "Failed to stash local changes"
        if os.system(f"git fetch") != 0:
            os.system("git stash pop")
            return "Failed to fetch updates from origin"
        os.system(f"git checkout --detach")
        os.system(f"git branch -f -D {branch}")
        os.system(f"git checkout {branch}")
        os.system(f"git stash clear")
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
        active_branch = os.popen("git rev-parse --abbrev-ref HEAD").read()
        return active_branch.replace('\n', '')

    def get_current_commit(self):
        current_commit = os.popen("git rev-parse HEAD").read()
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
