"""Driver for the SCD-4x CO2/temperature/humidity sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
import adafruit_scd4x


class SCD41(BaseSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        i2c = board.I2C()
        self.scd = adafruit_scd4x.SCD4X(i2c)
        self.scd.start_periodic_measurement()

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        reading = dict(
            co2 = self.scd.CO2,  # ppm
            temperature = self.scd.temperature,  # °C
            humidity = self.scd.relative_humidity,  # %
        )
        if any(value is None for value in reading.values()):
            return  # sensor not ready yet
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(SCD41)
