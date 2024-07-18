"""Driver for the TSL2591 light sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()

import adafruit_tsl2591


TSL2591_DATA = utils.SENSOR_DATA['TSL2591']

class TSL2591(BaseSensor):
    """Represent a TSL2591 sensor."""
    sensor_type = TSL2591_DATA.name
    reading_info = TSL2591_DATA.data

    def __init__(self, *, name=None, description=None, verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, description=description, verbose=verbose)
        i2c = board.I2C()
        self.tsl = adafruit_tsl2591.TSL2591(i2c)

    def read_sensor_data(self):
        """Return sensor data (lux, visible, infrared) as a dict."""
        reading = dict(
            light=self.tsl.lux,  # lux
            visible=self.tsl.visible,  # 32 bit int between 0-2147483647
            infrared=self.tsl.infrared,  # 16 bit int between 0-65535
        )
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(TSL2591)
