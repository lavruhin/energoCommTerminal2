import asyncio
import serial
import aioserial
import pynmeagps
import time


MEASURER_REQUEST = "$03M\r"
MEASURER_ANSWER = b"!034017\r"
GET_DATA_REQUEST = "#03\r"
TIMEOUT_ADAM = 0.2
TIMEOUT_DATA = 5
TIMEOUT_SRV = 10
GPS_SERIAL_PORT = "COM9"
SRV_SERIAL_PORT = "COM11"
SERIAL_LIST = ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
               "COM7", "COM8", "COM9", "COM10", "COM11", "COM12"]
g_is_connected = False
last_ping_time = time.time()
last_data_time = time.time()


async def srv_serial_process(srv_port, adam_port):
    global last_ping_time, last_data_time, g_is_connected
    srv = aioserial.aioserial.AioSerial(srv_port)
    adam = aioserial.aioserial.AioSerial(adam_port)
    while True:
        if time.time() - last_data_time > TIMEOUT_DATA:
            await adam.write_async(GET_DATA_REQUEST.encode())
            await asyncio.sleep(TIMEOUT_ADAM)
            adam_data = await adam.read_until_async(expected=aioserial.CR)
            await srv.write_async(adam_data)
            print(f"Send to server: {adam_data.decode(errors='ignore')}")
        srv_request_bytes = await srv.read_until_async(expected=aioserial.CR)
        srv_request = srv_request_bytes.decode(errors='ignore')
        print(f"Received from server: {srv_request}")
        if srv_request == MEASURER_REQUEST:
            await srv.write_async(MEASURER_ANSWER)
            print(f"Send to server: {MEASURER_ANSWER.decode(errors='ignore')}")
            is_connected = True
            last_ping_time = time.time()
        if srv_request == GET_DATA_REQUEST:
            is_connected = True
            last_ping_time = time.time()


async def gps_serial_process(gps_port):
    gps_stream = aioserial.aioserial.AioSerial(gps_port)
    gps = pynmeagps.NMEAReader(gps_stream)
    while True:
        await asyncio.sleep(0.01)
        raw_data, parsed_data = next(gps)
        if parsed_data.msgID == "RMC":
            print(f"Date: {str(parsed_data.date)} Time: {str(parsed_data.time)} Lat: {str(parsed_data.lat)} Lon: {str(parsed_data.lon)}")


async def check_connection():
    while True:
        await asyncio.sleep(2)
        if time.time() - last_ping_time > TIMEOUT_SRV:
            print("Disconnected from server")


def find_serial():
    adam_serial, gps_serial, srv_serial = "", "", ""
    for port_test in SERIAL_LIST:
        try:
            with serial.Serial(port_test) as adam_test:
                adam_test.write(MEASURER_REQUEST.encode())
                time.sleep(TIMEOUT_ADAM)
                adam_data = adam_test.read(adam_test.in_waiting)
                if adam_data == MEASURER_ANSWER:
                    adam_serial = port_test
                    break
        except serial.SerialException:
            continue
    if adam_serial == "":
        print("Cannot find Adam module")
        exit(-1)
    gps_serial = GPS_SERIAL_PORT
    srv_serial = SRV_SERIAL_PORT
    print(f"ADAM found at {adam_serial}")
    print(f"GPS found at {gps_serial}")
    return adam_serial, gps_serial, srv_serial


if __name__ == '__main__':
    (adam_serial_port, gps_serial_port, srv_serial_port) = find_serial()
    ioloop = asyncio.get_event_loop()
    tasks = [ioloop.create_task(srv_serial_process(srv_serial_port, adam_serial_port)),
             ioloop.create_task(gps_serial_process(gps_serial_port)),
             ioloop.create_task(check_connection())]
    wait_tasks = asyncio.wait(tasks)
    ioloop.run_until_complete(wait_tasks)
    ioloop.close()


async def main1(host, port, serial_ports):
    adam_dev = serial.Serial(adam_serial_port)
    # gps_dev = serial.Serial(gps_serial_port)
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