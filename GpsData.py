import datetime
import win32api
from numpy import power, sqrt, min, max, zeros


class GpsData:
    def __init__(self):
        self.dt = datetime.datetime.now()
        self.lat = 0
        self.lon = 0
        self.spd = 0
        self.distance = 0
        self.isEmpty = True
        self.isSystemTimeSet = False
        try:
            with open("D:\\TerminalProgram\\route.csv", "r") as route_file:
                lines = route_file.readlines()
        except IOError:
            print("Can't read D:\\TerminalProgram\\route.csv")
            exit(-1)
        self.route_len = len(lines)
        self.route = zeros([self.route_len, 4])
        for n, line in enumerate(lines):
            vals = line.split(";")
            self.route[n, :] = [n, vals[0], vals[1], vals[2]]
        self.lat_min, self.lat_max = min(self.route[:, 2]), max(self.route[:, 2])
        self.lon_min, self.lon_max = min(self.route[:, 3]), max(self.route[:, 3])
        self.lat_delta, self.lon_delta = self.lat_max - self.lat_min, self.lon_max - self.lon_min
        self.lat_min, self.lat_max = self.lat_min - self.lat_delta / 30, self.lat_max + self.lat_delta / 30
        self.lon_min, self.lon_max = self.lon_min - self.lon_delta / 60, self.lon_max + self.lon_delta / 60

    @property
    def is_empty(self):
        return self.isEmpty

    @property
    def date_time(self):
        return f"{self.dt.date()}; {self.dt.time()}; "

    @property
    def lat_lon_spd_dst(self):
        return f"{self.lat:2.5f}; {self.lon:2.5f}; {self.spd:3.2f}; {self.distance:2.2f};"

    def update(self, date, time, lat, lon, spd):
        self.dt = datetime.datetime(year=date.year, month=date.month, day=date.day,
                                    hour=time.hour, minute=time.minute, second=time.second)
        self.dt += datetime.timedelta(hours=6)
        self.lat = lat
        self.lon = lon
        self.spd = spd
        self.isEmpty = False
        closest_point_1 = self.route[0]
        point = [None, None, self.lat, self.lon]
        if (point[2] < self.lat_min) | (point[2] > self.lat_max) | \
                (point[3] < self.lon_min) | (point[3] > self.lon_max):
            self.distance = 0
        else:
            for n in range(self.route_len):
                if power(point[2] - self.route[n, 2], 2) + power(point[3] - self.route[n, 3], 2) < \
                        power(point[2] - closest_point_1[2], 2) + power(point[3] - closest_point_1[3], 2):
                    closest_point_1 = self.route[n]
            num_1 = int(closest_point_1[0])
            if num_1 == 0:
                closest_point_2 = self.route[1]
            elif num_1 == len(self.route) - 1:
                closest_point_2 = self.route[num_1 - 1]
            else:
                point_2 = self.route[num_1 - 1]
                point_3 = self.route[num_1 + 1]
                if power(point[2] - point_2[2], 2) + power(point[3] - point_2[3], 2) < \
                        power(point[2] - point_3[2], 2) + power(point[3] - point_3[3], 2):
                    closest_point_2 = point_2
                else:
                    closest_point_2 = point_3
            dist1 = sqrt(power(closest_point_1[2] - point[2], 2) + power(closest_point_1[3] - point[3], 2))
            dist2 = sqrt(power(closest_point_2[2] - point[2], 2) + power(closest_point_2[3] - point[3], 2))
            d1 = closest_point_1[1]
            d2 = closest_point_2[1]
            self.distance = d1 + dist1 / (dist1 + dist2) * (d2 - d1)
            print(closest_point_1)
            print(closest_point_2)

    def add_second(self):
        self.dt += datetime.timedelta(seconds=1)

    def set_system_time(self):
        if not self.isSystemTimeSet:
            t = (self.dt.year, self.dt.month, self.dt.isocalendar()[2],
                 self.dt.day, self.dt.hour, self.dt.minute, self.dt.second, 0)
            win32api.SetSystemTime(*t)
            self.isSystemTimeSet = True

    def get_system_time(self):
        t = win32api.GetLocalTime()
        self.dt = datetime.datetime(year=t[0], month=t[1], day=t[3], hour=t[4], minute=t[5], second=t[6])
        return self
