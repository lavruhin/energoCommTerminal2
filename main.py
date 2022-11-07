import socket
import serial
import time


HOST = "92.124.145.58"
PORT = 10001
IS_RECONNECT_ENABLED = True


def main():
    adam = serial.Serial("COM8")
    is_started = False
    while IS_RECONNECT_ENABLED or not is_started:
        is_started = True
        print("Create client")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((HOST, PORT))
            print("Client connected")
            while True:
                data_bytes = sock.recv(1024)
                try:
                    data_str = data_bytes.decode()
                    print(f"Received: {data_str}")
                except UnicodeError:
                    print("Unicode Error!")
                if data_str == "$03M\r":
                    sock.send(b"!034017\r")
                if data_str == "#03\r":
                    adam.write("#01\r".encode())
                    time.sleep(0.2)
                    data = adam.read(adam.in_waiting)
                    sock.send(data)
                    print(f"Send: {data.decode()}")


if __name__ == '__main__':
    main()
