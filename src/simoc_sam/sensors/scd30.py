"""Driver for the SCD-30 CO2/temperature/humidity sensor."""
from . import utils
from .basesensor import AdafruitSensor


class SCD30(AdafruitSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from adafruit_scd30 import SCD30
        i2c = self.busio.I2C(self.board.SCL, self.board.SDA, frequency=50000)
        self.scd = SCD30(i2c)

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        reading = dict(
            co2=self.scd.CO2,  # ppm
            temperature=self.scd.temperature,  # °C
            humidity=self.scd.relative_humidity,  # %
        )
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(SCD30)
