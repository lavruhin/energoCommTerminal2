import asyncio
import os.path
import serial
import aioserial
import pynmeagps
import threading
import time
import datetime
import OpenOPC
from GpsData import GpsData
from RepeatTimer import RepeatTimer
from Utils import serial_ports

useAdam, useOwen, useGps = False, True, True
POINT_NUM = 0
PERIOD_SRV = 3
PATH = "D:\\Data"
COEFS = {1: [18990, 500, 500],
         2: [19050, 500, 500],
         3: [11658, 150, 0],
         4: [10050, 150, 0]}

echo_srv_recv, echo_gps, echo_adam, echo_file = False, True, False, False
MEASURER_REQUEST = "$" + f"{POINT_NUM:02}" + "M\r"
MEASURER_ANSWER = ("!" + f"{POINT_NUM:02}" + "4017\r").encode()
SYNC_REQUEST = "#" + f"{POINT_NUM:02}" + "\r"
TIMEOUT_ADAM = 0.2
TIMEOUT_SRV = 20
OWEN_SERIAL_PORT = "COM1"
OWEN_OPC_TAG1 = "Локомотив.МВ110-8АС.Оперативные параметры.Измеренное значение.Вход 1"
OWEN_OPC_TAG2 = "Локомотив.МВ110-8АС.Оперативные параметры.Измеренное значение.Вход 2"
OWEN_OPC_TAG3 = "Локомотив.МВ110-8АС.Оперативные параметры.Измеренное значение.Вход 3"
g_gps_data = GpsData()
g_file_data = ""
g_srv_data = b""
gps_data_lock = threading.Lock()
file_data_lock = threading.Lock()
srv_data_lock = threading.Lock()
ready_to_sent = threading.Event()
srv_data_ready = threading.Event()
srv_is_connected = threading.Event()
measurer_data_ready = threading.Event()
file_data_ready = threading.Event()
last_sys_time = int(time.time())
global isGpsOk
isGpsOk = False


def srv_process(srv_port):
    MEASURER_REQUEST = "$" + f"{POINT_NUM:02}" + "M\r"
    MEASURER_ANSWER = ("!" + f"{POINT_NUM:02}" + "4017\r").encode()
    SYNC_REQUEST = "#" + f"{POINT_NUM:02}" + "\r"
    last_sync_time = time.time()
    srv = serial.Serial(srv_port, timeout=2)
    while True:
        try:
            srv_request_bytes = srv.read_until(expected=serial.CR)
        except TimeoutError:
            continue
        srv_request = srv_request_bytes.decode(errors='ignore')
        if (len(srv_request_bytes) == 0) & srv_is_connected.is_set():
            if time.time() - last_sync_time > TIMEOUT_SRV:
                print("DISCONNECTED")
                srv_is_connected.clear()
            time.sleep(0.25)
            continue
        if echo_srv_recv:
            print(f"Received at {time.time()}: {srv_request}")
        if srv_request == MEASURER_REQUEST:
            srv.write(MEASURER_ANSWER)
            print(f"Send to server: {MEASURER_ANSWER.decode(errors='ignore')}")
            print("CONNECTED")
            last_sync_time = time.time()
        if srv_request == SYNC_REQUEST:
            srv_is_connected.set()
            last_sync_time = time.time()
            srv_data_ready.wait()
            srv_data_ready.clear()
            with srv_data_lock:
                global g_srv_data
                srv_data = g_srv_data
                g_srv_data = b""
            srv.write(srv_data)
            print(f"Send to server:\n{srv_data[0:-1].decode(errors='ignore')}")


def adam_process(adam_port):
    SYNC_REQUEST = "#" + f"{POINT_NUM:02}" + "\r"
    adam = serial.Serial(adam_port)
    while True:
        measurer_data_ready.wait()
        measurer_data_ready.clear()
        adam.write(SYNC_REQUEST.encode())
        time.sleep(TIMEOUT_ADAM)
        adam_data = adam.read_until(expected=aioserial.CR)
        val = [0, 0, 0]
        if POINT_NUM <= 2:
            for n in range(3):
                try:
                    val[n] = float(adam_data[1 + n * 7:8 + n * 7]) * COEFS[POINT_NUM][n]
                except ValueError:
                    val[n] = 0
        else:
            for n in range(2):
                try:
                    val[n] = float(adam_data[1 + n * 7:8 + n * 7]) * COEFS[POINT_NUM][n]
                except ValueError:
                    val[n] = 0
            try:
                val[2] = (float(adam_data[1 + n * 7:8 + n * 7]) - 0.48) * 2000 / 1.92
                if val[2] < 0:
                    val[2] = 0
            except ValueError:
                val[2] = 0
        with gps_data_lock:
            global g_gps_data
            gps_data = g_gps_data
        file_data = f"{POINT_NUM:02}; {gps_data.date_time}{val[0]:01.0f}; " \
                    f"{val[1]:01.2f}; {val[2]:01.2f}; {gps_data.lat_lon_spd}\n"
        srv_data = file_data.encode()
        with file_data_lock, srv_data_lock:
            global g_file_data, g_srv_data
            g_file_data = file_data
            g_srv_data = g_srv_data + srv_data
        if echo_adam:
            print(f"ADAM {time.time()}")
        file_data_ready.set()
        if ready_to_sent.is_set():
            ready_to_sent.clear()
            srv_data_ready.set()


def owen_process():
    opc = OpenOPC.client()
    opc.connect("Owen.OPCNet.DA.1")
    while True:
        measurer_data_ready.wait()
        measurer_data_ready.clear()
        val = [opc.properties(OWEN_OPC_TAG1, id=2) * COEFS[POINT_NUM][0],
               opc.properties(OWEN_OPC_TAG2, id=2) * COEFS[POINT_NUM][1],
               (opc.properties(OWEN_OPC_TAG3, id=2) - 0.48) * 2000 / 1.92]
        if val[2] < 0:
            val[2] = 0
        with gps_data_lock:
            global g_gps_data
            gps_data = g_gps_data
        file_data = f"{POINT_NUM:02}; {gps_data.date_time}{val[0]:01.0f}; " \
                    f"{val[1]:01.2f}; {val[2]:01.2f}; {gps_data.lat_lon_spd}\n"
        srv_data = file_data.encode()
        with file_data_lock, srv_data_lock:
            global g_file_data, g_srv_data
            g_file_data = file_data
            g_srv_data = g_srv_data + srv_data
        if echo_adam:
            print(f"OWEN {time.time()}")
        file_data_ready.set()
        if ready_to_sent.is_set():
            ready_to_sent.clear()
            srv_data_ready.set()


def gps_process(gps_port):
    last_good_gps_data = GpsData()
    gps_stream = serial.Serial(gps_port)
    gps = pynmeagps.NMEAReader(gps_stream)
    while True:
        time.sleep(0.1)
        for i in range(4):
            try:
                raw_data, parsed_data = next(gps)
            except (StopIteration, serial.serialutil.SerialException):
                global isGpsOk
                isGpsOk = False
                break
            if parsed_data.msgID == "RMC":
                measurer_data_ready.set()
                if (parsed_data.status != "A") & (not last_good_gps_data.is_empty):
                    print('GPS is not valid')
                    last_good_gps_data.add_second()
                if parsed_data.status == "A":
                    last_good_gps_data.update(date=parsed_data.date, time=parsed_data.time,
                                              lat=parsed_data.lat, lon=parsed_data.lon,
                                              spd=parsed_data.spd)
                    # last_good_gps_data.set_system_time()
                if not last_good_gps_data.is_empty:
                    with gps_data_lock:
                        global g_gps_data
                        g_gps_data = last_good_gps_data
                    if echo_gps:
                        print(f"GPS: " + last_good_gps_data.date_time + last_good_gps_data.lat_lon_spd)
                if parsed_data.time.second % PERIOD_SRV == 0:
                    ready_to_sent.set()
                isGpsOk = True


def file_process():
    while True:
        dt = datetime.datetime.now()
        filename = f"{PATH}\\{POINT_NUM:02}_{dt.year:04}_{dt.month:02}_{dt.day:02}.csv"
        if not os.path.isfile(filename):
            with open(filename, mode="w") as file:
                file.write("Объект; Дата; Время; Напряжение; Ток-1; Ток-2; Широта; Долгота; Скорость; Расстояние\n")
        with open(filename, mode="a") as file:
            for item in range(10):
                file_data_ready.wait()
                file_data_ready.clear()
                with file_data_lock:
                    global g_file_data
                    file_data = g_file_data
                file.write(file_data)
                if echo_file:
                    print(f"FILE {time.time()}")


def find_serial(use_adam: bool, use_owen: bool, use_gps: bool):
    MEASURER_REQUEST = "$" + f"{POINT_NUM:02}" + "M\r"
    MEASURER_ANSWER = ("!" + f"{POINT_NUM:02}" + "4017\r").encode()
    adam_serial, owen_serial, gps_serial, srv_serial = "", "", "", ""
    serial_list = serial_ports()
    if use_adam:
        for port in serial_list:
            try:
                with serial.Serial(port) as adam:
                    adam.write(MEASURER_REQUEST.encode())
                    time.sleep(TIMEOUT_ADAM)
                    data = adam.read(adam.in_waiting)
                    if data == MEASURER_ANSWER:
                        adam_serial = port
                        serial_list.remove(port)
                        print(f"ADAM found at {adam_serial}")
                        break
            except serial.SerialException:
                continue
        if adam_serial == "":
            print("Cannot find ADAM module")
            exit(-1)
    if use_owen:
        owen_serial = OWEN_SERIAL_PORT
        try:
            serial_list.remove(owen_serial)
        except ValueError:
            None
    if use_gps:
        for port in serial_list:
            try:
                with serial.Serial(port, timeout=1) as gps_test:
                    gps = pynmeagps.NMEAReader(gps_test)
                    try:
                        if next(gps)[0].decode()[0:2] == "$G":
                            gps_serial = port
                            serial_list.remove(port)
                            print(f"GPS found at {gps_serial}")
                            break
                    except StopIteration:
                        continue
            except serial.SerialException:
                continue
        if gps_serial == "":
            print("Cannot find GPS module")
            exit(-1)
    srv_serial = serial_list[-1]
    print(f"Terminal found at {srv_serial}")
    return adam_serial, owen_serial, gps_serial, srv_serial


def timeout():
    global last_sys_time
    if int(time.time()) != last_sys_time:
        last_sys_time = int(time.time())
        if not isGpsOk:
            measurer_data_ready.set()
            with gps_data_lock:
                global g_gps_data
                g_gps_data = GpsData().get_system_time()
                if g_gps_data.dt.second % PERIOD_SRV == 0:
                    ready_to_sent.set()


async def main():
    try:
        with open("d:\\TerminalProgram\\point.ini", "r") as file:
            global POINT_NUM, useAdam, useOwen, useGps
            POINT_NUM = int(file.readline())
            if file.readline()[0:5] == "False":
                useAdam = False
            if file.readline()[0:5] == "False":
                useOwen = False
            if file.readline()[0:5] == "False":
                useGps = False
    except (IOError, ValueError):
        print("Can't read d:\\TerminalProgram\\point.ini")
        exit(-1)
    if not os.path.exists(PATH):
        try:
            os.mkdir(PATH)
        except OSError:
            print("Folder cannot be created")
            exit(-1)
    global isGpsOk
    isGpsOk = False
    (adam_serial_port, owen_serial_port, gps_serial_port, srv_serial_port) = find_serial(useAdam, useOwen, useGps)
    file_thread = threading.Thread(target=file_process)
    srv_thread = threading.Thread(target=srv_process, args=[srv_serial_port])
    timer = RepeatTimer(0.1, timeout)
    if useGps:
        gps_thread = threading.Thread(target=gps_process, args=[gps_serial_port])
        gps_thread.start()
    if useAdam:
        adam_thread = threading.Thread(target=adam_process, args=[adam_serial_port])
        adam_thread.start()
    else:
        owen_thread = threading.Thread(target=owen_process)
        owen_thread.start()
    file_thread.start()
    srv_thread.start()
    timer.start()


if __name__ == '__main__':
    asyncio.run(main())
    # (adam_serial_port, gps_serial_port, srv_serial_port) = find_serial()
    # ioloop = asyncio.get_event_loop()
    # tasks = [ioloop.create_task(srv_serial_data_process()),
    #          ioloop.create_task(srv_serial_ctrl_process(srv_serial_port)),
    #          ioloop.create_task(gps_serial_process(gps_serial_port)),
    #          ioloop.create_task(adam_serial_process(adam_serial_port)),
    #          ioloop.create_task(file_process())]
    # wait_tasks = asyncio.wait(tasks)
    # ioloop.run_until_complete(wait_tasks)
    # ioloop.close()

#
# async def adam_serial_process(adam_port):
#     adam = aioserial.aioserial.AioSerial(adam_port)
#     while True:
#         await adam.write_async(SYNC_REQUEST.encode())
#         await asyncio.sleep(TIMEOUT_ADAM * 5)
#         adam_data = await adam.read_until_async(expected=aioserial.CR)
#         async with adam_data_lock, gps_data_locker:
#             global g_adam_data, g_gps_data
#             g_adam_data = adam_data
#             gps_data = g_gps_data
#         file_data = adam_data[0:-1].decode() + gps_data + "\n"
#         async with file_data_locker:
#             global g_file_data
#             g_file_data = file_data
#         print("ADAM")
#         # await asyncio.sleep(0.9 - TIMEOUT_ADAM)
#
#
# async def gps_serial_process(gps_port):
#     gps_stream = aioserial.aioserial.AioSerial(gps_port)
#     gps = pynmeagps.NMEAReader(gps_stream)
#     print("Hi")
#     while True:
#         await asyncio.sleep(0.25)
#         for i in range(5):
#             raw_data, parsed_data = next(gps)
#             if parsed_data.msgID == "RMC":
#                 gps_data = f" {str(parsed_data.date)} " \
#                            f"{str(parsed_data.time)} " \
#                            f"{parsed_data.lat:2.5f} " \
#                            f"{parsed_data.lon:2.5f} " \
#                            f"{parsed_data.spd:3.2f}"
#                 print(gps_data)
#                 async with gps_data_locker:
#                     global g_gps_data
#                     g_gps_data = gps_data
#
#
# async def srv_serial_data_process():
#     global srv, g_is_connected, g_is_synced
#     last_data_time = time.time() - 2
#     while True:
#         while time.time() - last_data_time < 4:
#             await asyncio.sleep(1)
#         last_data_time += 4.0
#         if g_is_connected & g_is_synced:
#             print(f"Data {time.time()}")
#             async with adam_data_lock, gps_data_locker:
#                 global g_adam_data, g_gps_data
#                 adam_data = g_adam_data
#                 gps_data = g_gps_data
#             send_data = adam_data[0:-1] + gps_data.encode()
#             async with srv_lock:
#                 await srv.write_async(send_data)
#             print(f"Send to server: {send_data.decode(errors='ignore')}")
#
#
# async def srv_data_process():
#     await asyncio.sleep(0.25)
#     # global srv
#     while True:
#         await asyncio.sleep(0.25)
#         # if srv_data_ready.is_set() & srv_is_connected.is_set():
#         #     srv_data_ready.clear()
#         #     with srv_data_lock:
#         #         srv_data = g_srv_data
#         #     await srv.write_async(srv_data)
#         #     print(f"Send to server: {srv_data.decode(errors='ignore')}")
#
#
# async def file_process():
#     async with aiofiles.open("C:\\Users\\Admin\\Desktop\\data.txt", mode="w") as file:
#         while True:
#             start = time.time()
#             async with file_data_lock:
#                 global g_file_data
#                 file_data = g_file_data
#             await file.write(file_data)
#             print(f"FILE {time.time() - start}")
#             await asyncio.sleep(1.0)
