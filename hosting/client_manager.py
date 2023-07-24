import socket
import sys


def main():
    while True:
        sock = socket.socket(socket.AF_INET)
        host = input('Input ADDRESS\n')
        port = input('Input PORT\n')
        print("Connecting...")
        try:
            sock.connect((socket.gethostbyname(host), int(port)))
        except Exception as e:
            print(f"Failed to connect to {host}:{port}\n")
            print(e)
            continue
        print(f"Connected to {host}:{port}\n")
        sock.close()
        break
    while True:
        cmd = input('Input your command or type "exit" to exit the program\n')

        if len(cmd) == 0:
            continue

        if cmd.lower() == 'exit':
            return 0

        if len(cmd) == 0:
            print("Command is empty, try again!")
            continue

        print("Connecting...")
        try:
            sock = socket.socket(socket.AF_INET)
            sock.connect((socket.gethostbyname(host), int(port)))
        except Exception as e:
            print(f"Failed to connect to {host}:{port}\n")
            print(e)
            continue
        print("Sending...")
        sock.sendall(cmd.encode('utf8'))
        print("Receiving...")
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
