import datetime


class GpsData:
    dt = datetime.datetime.now()
    lat = 0
    lon = 0
    spd = 0
    isEmpty = True

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
        self.lat = lat
        self.lon = lon
        self.spd = spd
        self.isEmpty = False

    def add_second(self):
        self.dt += datetime.timedelta(seconds=1)
