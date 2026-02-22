"""Driver for the PCF8523 Real-Time Clock (RTC)."""
import datetime as dt

from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
import adafruit_pcf8523


class PCF8523(BaseSensor):
    """Interface for the PCF8523 RTC module."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        i2c = board.I2C()
        self.rtc = adafruit_pcf8523.PCF8523(i2c)

    def read_sensor_data(self):
        """Return RTC data (unix timestamp) as a dict."""
        rtc_time = self.rtc.datetime
        dt = dt.datetime(*rtc_time[:6])
        reading = {'unix_ts': dt.timestamp()}
        self.print_reading(reading)
        return reading

    def get_datetime(self):
        """Get the current datetime from the RTC."""
        rtc_time = self.rtc.datetime
        return dt.datetime(*rtc_time[:6])

    def set_datetime(self, dt_obj):
        """Set the RTC datetime from a datetime object."""
        self.rtc.datetime = dt_obj.timetuple()
        if self.verbose:
            print(f"RTC time set to: {dt_obj.isoformat()}")


if __name__ == '__main__':
    utils.start_sensor(PCF8523)
