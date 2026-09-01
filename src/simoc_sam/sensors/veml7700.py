"""Driver for the VEML7700 light sensor."""
from . import utils
from .basesensor import AdafruitSensor


class VEML7700(AdafruitSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from adafruit_veml7700 import VEML7700
        i2c = self.board.I2C()
        self.veml = VEML7700(i2c)

    def read_sensor_data(self):
        """Return sensor data (light) as a dict."""
        reading = dict(
            light=self.veml.light,  # lux
        )
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(VEML7700)
