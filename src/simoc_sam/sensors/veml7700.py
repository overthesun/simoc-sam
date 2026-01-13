"""Driver for the VEML7700 light sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()

import adafruit_veml7700


VEML7700_DATA = utils.SENSOR_DATA['veml7700']

class VEML7700(BaseSensor):
    """Represent a VEML7700 sensor."""
    sensor_type = VEML7700_DATA.name
    reading_info = VEML7700_DATA.data

    def __init__(self, *, name=None, description=None, verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, description=description, verbose=verbose)
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
