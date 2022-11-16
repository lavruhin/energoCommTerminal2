import asyncio
import serial
import aioserial
import pynmeagps
import time


MEASURER_REQUEST = "$03M\r"
MEASURER_ANSWER = b"!034017\r"
GET_DATA_REQUEST = "#03\r"
TIMEOUT_ADAM = 0.2
GPS_SERIAL_PORT = "COM9"
SRV_SERIAL_PORT = "COM11"
SERIAL_LIST = ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
               "COM7", "COM8", "COM9", "COM10", "COM11", "COM12"]
adam_data_lock = asyncio.Lock()
gps_data_lock = asyncio.Lock()
is_connected = False
g_adam_data = ""
g_gps_data = ""


async def srv_serial_process(srv_port):
    global is_connected
    srv = aioserial.aioserial.AioSerial(srv_port)
    while True:
        if not is_connected:
            srv_request_bytes = await srv.read_until_async(expected=aioserial.CR)
            srv_request = srv_request_bytes.decode(errors='ignore')
            print(f"Received from server: {srv_request}")
        if srv_request == MEASURER_REQUEST:
            await srv.write_async(MEASURER_ANSWER)
            print(f"Send to server: {MEASURER_ANSWER.decode(errors='ignore')}")
        if srv_request == GET_DATA_REQUEST:
            async with adam_data_lock, gps_data_lock:
                global g_adam_data, g_gps_data
                adam_data = g_adam_data
                gps_data = g_gps_data
            send_data = adam_data[0:-1] + gps_data.encode()
            await srv.write_async(send_data)
            print(f"Send to server: {send_data.decode(errors='ignore')}")


async def adam_serial_process(adam_port):
    adam = aioserial.aioserial.AioSerial(adam_port)
    while True:
        await adam.write_async(GET_DATA_REQUEST.encode())
        await asyncio.sleep(TIMEOUT_ADAM)
        adam_data = await adam.read_until_async(expected=aioserial.CR)
        async with adam_data_lock:
            global g_adam_data
            g_adam_data = adam_data


async def gps_serial_process(gps_port):
    gps_stream = aioserial.aioserial.AioSerial(gps_port)
    gps = pynmeagps.NMEAReader(gps_stream)
    while True:
        await asyncio.sleep(0.01)
        raw_data, parsed_data = next(gps)
        if parsed_data.msgID == "RMC":
            gps_data = f" {str(parsed_data.date)} " \
                       f"{str(parsed_data.time)} " \
                       f"{parsed_data.lat:2.5f} " \
                       f"{parsed_data.lon:2.5f} " \
                       f"{parsed_data.spd:3.2f}"
            print(gps_data)
            async with gps_data_lock:
                global g_gps_data
                g_gps_data = gps_data


def find_serial():
    adam_serial, gps_serial, srv_serial = "", "", ""
    for port_test in SERIAL_LIST:
        try:
            with serial.Serial(port_test) as adam_test:
                adam_test.write(MEASURER_REQUEST.encode())
                time.sleep(TIMEOUT_ADAM)
                data = adam_test.read(adam_test.in_waiting)
                if data == MEASURER_ANSWER:
                    adam_serial = port_test
                    break
        except serial.SerialException:
            continue
    if adam_serial == "":
        print("Cannot find Adam module")
        exit(-1)

    # gps_stream = aioserial.aioserial.AioSerial(gps_port)
    # gps = pynmeagps.NMEAReader(gps_stream)
    # while True:
    #     await asyncio.sleep(0.01)
    #     raw_data, parsed_data = next(gps)
    #     if parsed_data.msgID == "RMC":

    gps_serial = GPS_SERIAL_PORT
    srv_serial = SRV_SERIAL_PORT
    print(f"ADAM found at {adam_serial}")
    print(f"GPS found at {gps_serial}")
    return adam_serial, gps_serial, srv_serial


if __name__ == '__main__':
    (adam_serial_port, gps_serial_port, srv_serial_port) = find_serial()
    ioloop = asyncio.get_event_loop()
    tasks = [ioloop.create_task(srv_serial_process(srv_serial_port)),
             ioloop.create_task(adam_serial_process(adam_serial_port)),
             ioloop.create_task(gps_serial_process(gps_serial_port))]
    wait_tasks = asyncio.wait(tasks)
    ioloop.run_until_complete(wait_tasks)
    ioloop.close()
