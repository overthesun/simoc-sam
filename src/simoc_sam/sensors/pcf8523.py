"""Driver for the PCF8523 Real-Time Clock (RTC)."""
from datetime import datetime

from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
from adafruit_pcf8523 import pcf8523


class PCF8523(BaseSensor):
    """Interface for the PCF8523 RTC module."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        i2c = board.I2C()
        self.rtc = pcf8523.PCF8523(i2c)

    def read_sensor_data(self):
        """Return RTC data (unix timestamp) as a dict."""
        rtc_time = self.rtc.datetime
        dt = datetime(*rtc_time[:6])
        reading = {'unix_ts': dt.timestamp()}
        self.print_reading(reading)
        return reading

    def get_datetime(self):
        """Get the current datetime from the RTC."""
        rtc_time = self.rtc.datetime
        return datetime(*rtc_time[:6])

    def set_datetime(self, dt):
        """Set the RTC datetime from a datetime object."""
        self.rtc.datetime = dt.timetuple()
        if self.verbose:
            print(f"RTC time set to: {dt.isoformat()}")


if __name__ == '__main__':
    utils.start_sensor(PCF8523)
