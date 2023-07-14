import socket
import sys

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
        sock.connect((socket.gethostbyname(host),int(port)))
    except:
        print(f"Failed to connect to {host}:{port}")
        return 
    print("Sending...")
    sock.sendall(command.encode('utf8'))
    print("Receiving...")
    response = sock.recv(1024).decode('utf8')
    print(response)

if __name__ == "__main__":
    send()