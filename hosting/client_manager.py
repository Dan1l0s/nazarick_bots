"""Interactive client for the VPS supervisor (hosting/server_manager.py).

Run it with no arguments for a REPL that prints the bot's status and then
accepts commands; or import and call `send()` for one-shot CLI usage.

Every command is sent as `<password> <command>` over a fresh TCP connection -
the server closes the socket after each response, so connections are not
reused.
"""

from __future__ import annotations

import os
import socket
import sys

try:
    os.chdir(os.path.dirname(__file__))
    sys.path.append("..")
    from configs.private_config import hosting_ip, hosting_port, server_manager_password
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


def main():
    while True:
        sock = socket.socket(socket.AF_INET)

        try:
            host = hosting_ip
        except Exception:
            host = input('Input ADDRESS\n')

        try:
            port = hosting_port
        except Exception:
            port = input('Input PORT\n')

        print("Connecting...")
        try:
            sock.connect((socket.gethostbyname(host), int(port)))
        except Exception:
            print(f"Failed to connect to {host}:{port}\n")
            continue
        print(f"Connected to {host}:{port}\n")

        sock.sendall(f"{server_manager_password} status".encode("utf8"))
        response = receive_all(sock)
        sock.close()
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
            sock = socket.socket(socket.AF_INET)
            sock.connect((socket.gethostbyname(host), int(port)))
        except Exception:
            print(f"Failed to connect to {host}:{port}\n")
            continue
        cmd = server_manager_password + " " + cmd
        sock.sendall(cmd.encode('utf8'))

        response = receive_all(sock)
        sock.close()
        print(f'{response}\n')


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
