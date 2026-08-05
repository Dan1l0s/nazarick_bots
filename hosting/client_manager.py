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
    status - reveal current bot status
    run - run bot if its offline
    stop - stop the bot if its running
    reboot - restart the bot
    backup - create a manual backup
    update {branch} - checkout to selected branch, master by default
    clear - clears current list of errors
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
    main()
