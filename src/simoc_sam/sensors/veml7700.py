"""Driver for the VEML7700 light sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()

import adafruit_veml7700


class VEML7700(BaseSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        i2c = board.I2C()
        self.tsl = adafruit_veml7700.VEML7700(i2c)

    def read_sensor_data(self):
        """Return sensor data (light) as a dict."""
        reading = dict(
            light=self.tsl.light,  # lux
        )
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(VEML7700)
