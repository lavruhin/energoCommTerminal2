import asyncio
import serial
import aioserial
import pynmeagps
import time


MEASURER_REQUEST = "$03M\r"
MEASURER_ANSWER = b"!034017\r"
SYNC_REQUEST = "#03\r"
TIMEOUT_ADAM = 0.2
TIMEOUT_SRV = 10
GPS_SERIAL_PORT = "COM9"
SRV_SERIAL_PORT = "COM1"
SERIAL_LIST = ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
               "COM7", "COM8", "COM9", "COM10", "COM11", "COM12"]
adam_data_lock = asyncio.Lock()
gps_data_lock = asyncio.Lock()
is_connected_lock = asyncio.Lock()
srv_lock = asyncio.Lock()
g_adam_data = ""
g_gps_data = ""
g_is_connected = False
g_is_synced = False
g_last_sync_time = time.time()
srv = None
file = open("C:\\Users\\Admin\\Desktop\\data.txt", "w")


async def srv_serial_ctrl_process(srv_port):
    global srv, g_is_connected, g_is_synced, g_last_sync_time
    srv = aioserial.aioserial.AioSerial(srv_port, timeout=0.25)
    while True:
        async with srv_lock:
            srv_request_bytes = await srv.read_until_async(expected=aioserial.CR)
        srv_request = srv_request_bytes.decode(errors='ignore')
        if not srv_request:
            if (time.time() - g_last_sync_time > TIMEOUT_SRV) & g_is_connected:
                g_is_connected, g_is_synced = False, False
                print("DISCONNECTED")
            await asyncio.sleep(0.5)
            continue
        print(f"Received: {srv_request}")
        if srv_request == MEASURER_REQUEST:
            g_is_connected = True
            async with srv_lock:
                await srv.write_async(MEASURER_ANSWER)
            print(f"Send to server: {MEASURER_ANSWER.decode(errors='ignore')}")
            print("CONNECTED")
            g_last_sync_time = time.time()
        if srv_request == SYNC_REQUEST:
            g_is_synced = True
            g_last_sync_time = time.time()
            print("SYNC")


async def srv_serial_data_process():
    global srv, g_is_connected, g_is_synced
    last_data_time = time.time() - 2
    while True:
        while time.time() - last_data_time < 4:
            await asyncio.sleep(1)
        last_data_time += 4.0
        if g_is_connected & g_is_synced:
            print(f"Data {time.time()}")
            async with adam_data_lock, gps_data_lock:
                global g_adam_data, g_gps_data
                adam_data = g_adam_data
                gps_data = g_gps_data
            send_data = adam_data[0:-1] + gps_data.encode()
            async with srv_lock:
                await srv.write_async(send_data)
            print(f"Send to server: {send_data.decode(errors='ignore')}")


async def adam_serial_process(adam_port):
    adam = aioserial.aioserial.AioSerial(adam_port)
    while True:
        await adam.write_async(SYNC_REQUEST.encode())
        await asyncio.sleep(TIMEOUT_ADAM)
        adam_data = await adam.read_until_async(expected=aioserial.CR)
        async with adam_data_lock, gps_data_lock:
            global g_adam_data, g_gps_data
            g_adam_data = adam_data
            gps_data = g_gps_data
        write_data = adam_data[0:-1] + gps_data.encode()
        # print("ADAM")
        # global file
        # file.write(write_data)
        # print("FILE")
        await asyncio.sleep(TIMEOUT_ADAM)


async def gps_serial_process(gps_port):
    gps_stream = aioserial.aioserial.AioSerial(gps_port)
    gps = pynmeagps.NMEAReader(gps_stream)
    while True:
        await asyncio.sleep(0.05)
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
    tasks = [ioloop.create_task(srv_serial_data_process()),
             ioloop.create_task(srv_serial_ctrl_process(srv_serial_port)),
             ioloop.create_task(adam_serial_process(adam_serial_port)),
             ioloop.create_task(gps_serial_process(gps_serial_port))]
    wait_tasks = asyncio.wait(tasks)
    ioloop.run_until_complete(wait_tasks)
    ioloop.close()
