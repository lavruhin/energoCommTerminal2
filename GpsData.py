import datetime
import win32api


class GpsData:
    dt = datetime.datetime.now()
    lat = 0
    lon = 0
    spd = 0
    isEmpty = True
    isSystemTimeSet = False

    @property
    def is_empty(self):
        return self.isEmpty

    @property
    def date_time(self):
        return f"{self.dt.date()}; {self.dt.time()}; "

    @property
    def lat_lon_spd(self):
        return f"{self.lat:2.5f}; {self.lon:2.5f}; {self.spd:3.2f}; "

    def update(self, date, time, lat, lon, spd):
        self.dt = datetime.datetime(year=date.year, month=date.month, day=date.day,
                                    hour=time.hour, minute=time.minute, second=time.second)
        self.dt += datetime.timedelta(hours=6)
        self.lat = lat
        self.lon = lon
        self.spd = spd
        self.isEmpty = False

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
        self.dt = datetime.datetime(year=t[0], month=t[1], day=t[3],
                                    hour=t[4], minute=t[5], second=t[6])
        return self
