"""Driver for the SCD-30 CO2/temperature/humidity sensor."""
from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
busio = utils.import_busio()
import adafruit_scd30


SCD30_DATA = utils.SENSOR_DATA['SCD-30']

class SCD30(BaseSensor):
    """Represent a SCD-30 sensor."""
    sensor_type = SCD30_DATA.name
    reading_info = SCD30_DATA.data

    def __init__(self, *, name=None, description=None, verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, description=description, verbose=verbose)
        i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
        self.scd = adafruit_scd30.SCD30(i2c)

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
