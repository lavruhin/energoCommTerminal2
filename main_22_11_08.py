import asyncio
import serial
import pynmeagps
import time


SRV_IP = "92.124.145.58"
SRV_PORT = 10001
MEASURER_REQUEST = "$03M\r"
MEASURER_ANSWER = b"!034017\r"
GET_DATA_REQUEST_FROM_SRV = "#03\r"
GET_DATA_REQUEST_TO_ADAM = "#01\r"
TIMEOUT_ADAM = 0.2
GPS_SERIAL_PORT = "COM9"
SERIAL_LIST = ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
               "COM7", "COM8", "COM9", "COM10", "COM11", "COM12"]


async def main(host, port, adam_serial_port, gps_serial_port):
    adam_dev = serial.Serial(adam_serial_port)
    gps_dev = serial.Serial(gps_serial_port)
    gps_reader = pynmeagps.NMEAReader(gps_dev)
    reader, writer = await asyncio.open_connection(host, port)
    print("Client connected")
    while True:
        gps_print(gps_reader)
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
        gps_print(gps_reader)
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
            adam_dev.write(GET_DATA_REQUEST_TO_ADAM.encode())
            await asyncio.sleep(TIMEOUT_ADAM)
            adam_data = adam_dev.read(adam_dev.in_waiting)
            try:
                writer.write(adam_data)
                await writer.drain()
            except ConnectionError:
                print("Connection error")
                break
            print(f"Send: {adam_data.decode()}")


def gps_print(gps_reader):
    raw_data, parsed_data = next(gps_reader)
    if parsed_data.msgID == "RMC":
        print(
            f"Date: {str(parsed_data.date)} Time: {str(parsed_data.time)} Lat: {str(parsed_data.lat)} Lon: {str(parsed_data.lon)}")


def find_adam_gps():
    adam_serial, gps_serial = "", ""
    for port_test in SERIAL_LIST:
        try:
            with serial.Serial(port_test) as adam_test:
                adam_test.write(b"$01M\r")
                time.sleep(TIMEOUT_ADAM)
                adam_data = adam_test.read(adam_test.in_waiting)
                if adam_data == b"!014017\r":
                    adam_serial = port_test
                    break
        except serial.SerialException:
            continue
    if adam_serial == "":
        print("Cannot find Adam module")
        exit(-1)
    gps_serial = GPS_SERIAL_PORT
    print(f"ADAM found at {adam_serial}")
    print(f"GPS found at {gps_serial}")
    return adam_serial, gps_serial


if __name__ == '__main__':
    adam_serial, gps_serial = find_adam_gps()
    asyncio.run(main(SRV_IP, SRV_PORT, adam_serial, gps_serial))
