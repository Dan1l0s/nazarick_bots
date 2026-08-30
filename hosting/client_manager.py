"""Interactive client for the VPS supervisor (hosting/server_manager.py).

Run it with no arguments for a REPL that prints the bot's status and then
accepts commands; or import and call `send()` for one-shot CLI usage.

Every command is sent as `<password> <command>` over a fresh TCP connection -
the server closes the socket after each response, so connections are not
reused.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time

try:
    os.chdir(os.path.dirname(__file__))
    sys.path.append("..")
    from configs import private_config as _private_config
    hosting_ip = _private_config.hosting_ip
    hosting_port = _private_config.hosting_port
    server_manager_password = _private_config.server_manager_password
    manager_ssh_host = getattr(_private_config, "manager_ssh_host", None)
except Exception:
    # Without private_config the REPL falls back to prompting for host/port
    # (see main()); the password reference will then fail, which is the
    # original behavior.
    pass

HELP_TEXT = """List of possible commands:

  Immediate                     Deferred (waits for playback to finish)
    reboot                        reboot-idle
    update {branch}               update-idle {branch}
    upgrade                       upgrade-idle

    reboot  - restart the bots now, cutting off anything currently playing
    update  - checkout the selected branch (master by default), reinstall
              dependencies, then restart
    upgrade - update yt-dlp, and restart only if the version actually changed

  Other
    status  - current state, branch, commit, yt-dlp version, playback,
              queued action and recent errors
    run     - start the bots if they are offline
    stop    - stop the bots if they are running
    backup  - create a manual backup
    cancel  - drop a queued deferred action
    clear   - clear the current list of errors

A deferred action is queued until no bot is playing music, and runs anyway after
6 hours so a bot stuck reporting "playing" cannot block it forever. Queueing a
new one replaces any action already waiting. `status` shows what is queued.

The `-idle` suffix is shorthand: `reboot-idle` and `reboot when-idle` are the
same command, so either form works.
"""


def receive_all(sock: socket.socket) -> str:
    """Reads until the server closes the connection."""
    response = ""
    while True:
        data = sock.recv(1024)
        if data:
            response += data.decode('utf8')
        else:
            break
    return response


def build_ssh_tunnel_command(ssh_executable: str, ssh_host: str,
                             local_port: int, remote_port: int) -> list[str]:
    """Builds the OpenSSH command used for the private manager connection."""
    return [
        ssh_executable,
        "-T",
        "-N",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-L", f"127.0.0.1:{local_port}:127.0.0.1:{remote_port}",
        ssh_host,
    ]


class SshTunnel:
    """Temporary loopback forwarding owned by the interactive client."""

    def __init__(self, ssh_host: str, remote_port: int,
                 startup_timeout: float = 15.0):
        self.ssh_host = ssh_host
        self.remote_port = int(remote_port)
        self.startup_timeout = startup_timeout
        self.local_port = None
        self.process = None

    def start(self) -> int:
        ssh_executable = shutil.which("ssh")
        if not ssh_executable:
            raise RuntimeError(
                "OpenSSH client was not found in PATH. Install the Windows "
                "OpenSSH Client optional feature, then reopen the terminal.")

        # Let the OS choose an unused local port. This still works when 10000
        # is occupied by a local development supervisor.
        reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        reservation.bind(("127.0.0.1", 0))
        self.local_port = reservation.getsockname()[1]
        reservation.close()

        command = build_ssh_tunnel_command(
            ssh_executable, self.ssh_host, self.local_port, self.remote_port)
        try:
            # Inherit the terminal so host-key confirmation and key-passphrase
            # prompts remain interactive on first use.
            self.process = subprocess.Popen(command)
        except OSError as exc:
            raise RuntimeError(f"failed to start SSH: {exc}") from exc

        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            return_code = self.process.poll()
            if return_code is not None:
                self.close()
                raise RuntimeError(
                    f"SSH to {self.ssh_host} exited with code {return_code}. "
                    f"Check that `ssh {self.ssh_host}` works in this terminal.")
            try:
                probe = socket.create_connection(
                    ("127.0.0.1", self.local_port), timeout=0.25)
                probe.close()
                return self.local_port
            except OSError:
                time.sleep(0.1)

        self.close()
        raise RuntimeError(
            f"SSH tunnel to {self.ssh_host} did not become ready within "
            f"{self.startup_timeout:g}s")

    def close(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def main():
    try:
        host = hosting_ip
    except Exception:
        host = input('Input ADDRESS\n')

    try:
        port = int(hosting_port)
    except Exception:
        port = int(input('Input PORT\n'))

    tunnel = None
    try:
        ssh_host = globals().get("manager_ssh_host")
        if ssh_host:
            print(f"Opening SSH tunnel through {ssh_host}...")
            tunnel = SshTunnel(ssh_host, port)
            port = tunnel.start()
            host = "127.0.0.1"
            print(f"SSH tunnel is ready on 127.0.0.1:{port}\n")

        while True:
            print("Connecting...")
            try:
                response = send_command("status", host, port)
            except RuntimeError as exc:
                print(f"Failed to connect: {exc}\n")
                if tunnel:
                    return 1
                continue
            print(f"Connected to {host}:{port}\n")
            print(f'{response}\n')
            break

        while True:
            cmd = input('Input your command (type "help" to get commands list) or type "exit" to exit the program\n')

            if len(cmd) == 0:
                continue

            if cmd.lower() == 'exit':
                return 0

            if cmd.lower() == 'help':
                print(HELP_TEXT)
                continue

            try:
                response = send_command(cmd, host, port)
            except RuntimeError as exc:
                print(f"Failed to connect: {exc}\n")
                continue
            print(f'{response}\n')
    except RuntimeError as exc:
        print(f"Failed to open SSH tunnel: {exc}", file=sys.stderr)
        return 1
    finally:
        if tunnel:
            tunnel.close()


def send_command(command: str, host: str = "127.0.0.1", port: int = None,
                 timeout: int = 30) -> str:
    """Sends one password-prefixed command and returns the reply.

    Non-interactive counterpart to main(), used by hosting/deploy.sh (and
    therefore by CI). Defaults to 127.0.0.1 so the deploy path never sends the
    manager password over the network - the SSH tunnel is the only thing that
    crosses the internet.

    Raises RuntimeError on connection failure so callers get a non-zero exit.
    """
    if port is None:
        port = hosting_port

    sock = socket.socket(socket.AF_INET)
    sock.settimeout(timeout)
    try:
        sock.connect((socket.gethostbyname(host), int(port)))
    except ConnectionRefusedError as exc:
        # Nothing is bound. On loopback the kernel refuses instantly, so this is
        # unambiguous: the supervisor is not running.
        raise RuntimeError(
            f"nothing is listening on {host}:{port} - the supervisor is not "
            f"running. Start it with `systemctl start nazarick` "
            f"(or check `systemctl status nazarick`)") from exc
    except OSError as exc:
        raise RuntimeError(
            f"could not open a connection to {host}:{port}: {exc}") from exc

    # Past this point the socket is connected, so a timeout means the supervisor
    # accepted the work and has not answered yet - NOT that it is unreachable.
    # Distinguishing the two matters: the original message said "could not reach
    # the manager ... timed out" for a supervisor that was alive and mid-`pip
    # install`, which sent the investigation after the network instead of the
    # blocking call. Note the socket stays bound with a deep listen() backlog, so
    # the kernel completes the handshake even while nothing calls accept().
    try:
        sock.sendall(f"{server_manager_password} {command}".encode("utf8"))
        return receive_all(sock)
    except socket.timeout as exc:
        raise RuntimeError(
            f"connected to {host}:{port} but got no reply within {timeout}s. "
            f"The supervisor is running; '{command}' is either still working or "
            f"its event loop is blocked. Check logs/ on the server and retry "
            f"`status`, which is cheap") from exc
    except OSError as exc:
        raise RuntimeError(
            f"connected to {host}:{port} but the exchange failed: {exc}") from exc
    finally:
        sock.close()


def cli() -> int:
    """`python hosting/client_manager.py --command "update master when-idle"`"""
    import argparse

    parser = argparse.ArgumentParser(description="Send one command to the bot supervisor.")
    parser.add_argument("--command", required=True,
                        help='e.g. "status", "update master when-idle", "upgrade when-idle"')
    parser.add_argument("--host", default="127.0.0.1",
                        help="default 127.0.0.1 - keeps the password off the network")
    parser.add_argument("--port", type=int, default=None,
                        help="defaults to hosting_port from private_config")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        print(send_command(args.command, args.host, args.port, args.timeout))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def send():
    """One-shot mode: python client_manager.py ADDRESS PORT COMMAND [args...]

    Note this path sends the command verbatim, without prefixing the password -
    preserved from the original, so the caller must include it in COMMAND.
    """
    if len(sys.argv) < 4:
        print(f"Usage: python controller.py ADDRESS PORT COMMAND [optional_args]")
        return
    host = sys.argv[1]
    port = sys.argv[2]
    command = ' '.join(sys.argv[3:])
    if len(command) == 0:
        print("Empty command was ignored")
        return
    sock = socket.socket(socket.AF_INET)
    print("Connecting...")
    try:
        sock.connect((socket.gethostbyname(host), int(port)))
    except Exception:
        print(f"Failed to connect to {host}:{port}")
        return
    print("Sending...")
    sock.sendall(command.encode('utf8'))
    print("Receiving...")
    response = receive_all(sock)
    print(response)


if __name__ == "__main__":
    # --command runs the scriptable one-shot path; no arguments starts the REPL.
    if "--command" in sys.argv:
        sys.exit(cli())
    main()
