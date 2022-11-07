import asyncio
import serial
import time


SRV_IP = "92.124.145.58"
SRV_PORT = 10001
MEASURER_REQUEST = "$03M\r"
MEASURER_ANSWER = b"!034017\r"
GET_DATA_REQUEST_FROM_SRV = "#03\r"
GET_DATA_REQUEST_TO_ADAM = "#01\r"
TIMEOUT_ADAM = 0.2
SERIAL_LIST = ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
               "COM7", "COM8", "COM9", "COM10", "COM11", "COM12"]


async def main(host, port, adam_serial_port):
    adam = serial.Serial(adam_serial_port)
    reader, writer = await asyncio.open_connection(host, port)
    print("Client connected")
    while True:
        # Receive command
        try:
            received_data = await reader.read(1024)
        except ConnectionError:
            print("Connection error")
            break
        try:
            received_data_str = received_data.decode()
            print(f"Received: {received_data_str}")
        except UnicodeError:
            print("Unicode Error")
        # Command to recognize the measurer
        if received_data_str == MEASURER_REQUEST:
            try:
                writer.write(MEASURER_ANSWER)
                await writer.drain()
            except ConnectionError:
                print("Connection error")
                break
        # Command to get data
        if received_data_str == GET_DATA_REQUEST_FROM_SRV:
            adam.write(GET_DATA_REQUEST_TO_ADAM.encode())
            await asyncio.sleep(TIMEOUT_ADAM)
            adam_data = adam.read(adam.in_waiting)
            try:
                writer.write(adam_data)
                await writer.drain()
            except ConnectionError:
                print("Connection error")
                break
            print(f"Send: {adam_data.decode()}")


def find_adam():
    for port_test in SERIAL_LIST:
        try:
            with serial.Serial(port_test) as adam_test:
                adam_test.write(b"$01M\r")
                time.sleep(TIMEOUT_ADAM)
                adam_data = adam_test.read(adam_test.in_waiting)
                if adam_data == b"!014017\r":
                    print(f"Adam found at {port_test}")
                    return port_test
        except serial.SerialException:
            continue
    print("Cannot find Adam module")
    exit(-1)


if __name__ == '__main__':
    asyncio.run(main(SRV_IP, SRV_PORT, find_adam()))
