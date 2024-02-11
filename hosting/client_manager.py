import socket
import sys
import os

try:
    os.chdir(os.path.dirname(__file__))
    sys.path.append("..")
    from configs.private_config import hosting_ip, hosting_port, server_manager_password
except:
    pass


def main():
    while True:
        sock = socket.socket(socket.AF_INET)

        try:
            host = hosting_ip
        except:
            host = input('Input ADDRESS\n')

        try:
            port = hosting_port
        except:
            port = input('Input PORT\n')

        print("Connecting...")
        try:
            sock.connect((socket.gethostbyname(host), int(port)))
        except:
            print(f"Failed to connect to {host}:{port}\n")
            continue
        print(f"Connected to {host}:{port}\n")

        sock.sendall(f"{server_manager_password} status".encode("utf8"))
        response = ""
        while True:
            data = sock.recv(1024)
            if data:
                data = data.decode('utf8')
                response += data
            else:
                break
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
            print("""List of possible commands:
    status - reveal current bot status
    run - run bot if its offline
    stop - stop the bot if its running
    reboot - restart the bot
    backup - create a manual backup
    update {branch} - checkout to selected branch, master by default
    clear - clears current list of errors\n""")
            continue

        try:
            sock = socket.socket(socket.AF_INET)
            sock.connect((socket.gethostbyname(host), int(port)))
        except:
            print(f"Failed to connect to {host}:{port}\n")
            continue
        cmd = server_manager_password + " " + cmd
        sock.sendall(cmd.encode('utf8'))

        response = ""
        while True:
            data = sock.recv(1024)
            if data:
                data = data.decode('utf8')
                response += data
            else:
                break
        sock.close()
        print(f'{response}\n')


def send():
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
    except:
        print(f"Failed to connect to {host}:{port}")
        return
    print("Sending...")
    sock.sendall(command.encode('utf8'))
    print("Receiving...")
    response = ""
    while True:
        data = sock.recv(1024)
        if data:
            data = data.decode('utf8')
            response += data
        else:
            break
    print(response)


if __name__ == "__main__":
    main()
