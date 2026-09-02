"""Driver for the TSL2591 light sensor."""
from . import utils
from .basesensor import AdafruitSensor


class TSL2591(AdafruitSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from adafruit_tsl2591 import TSL2591
        i2c = self.board.I2C()
        self.tsl = TSL2591(i2c)

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
